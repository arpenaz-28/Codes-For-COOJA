/* ==========================================================================
 * sn-node.c  —  Sensor Node (SNn) for Zhou et al. scheme
 *
 * Faithful implementation of the Sensor Node entity from:
 *   "Security-Enhanced Lightweight and Anonymity-Preserving User
 *    Authentication Scheme for IoT-Based Healthcare"
 *   Zhou et al., IEEE IoT Journal, Vol. 11, No. 6, March 2024
 *
 * The sensor node has an embedded PUF and participates in:
 *   1. Sensor Node Registration Phase (Section IV.B)
 *   2. Authentication & Key Exchange Phase (Section IV.C) — handles M2, sends M3
 *
 * Registration:
 *   Step 1: SN sends SNn to GW (secure channel) → POST /test/sn_reg
 *   Step 2: GW replies with AES_enc(K_GW_SN, [SIDn(32) | Cn(1)])
 *   Step 3: SN computes Rn ← PUF(Cn), sends AES_enc(K_GW_SN, [Rn(1)])
 *           GW stores (SNn, SIDn, (Cn,Rn), bn)
 *
 * Authentication (M2 → M3):
 *   M2 received from GW: {SKn(64), β(32), Cn(1)} = 97 bytes
 *     SN: Rn ← PUF(Cn)
 *         (SK'||SIDn_new') = SKn ⊕ H2(Rn)    [H2 = double-hash for 64B mask]
 *         β' = h(SK'||Rn||SIDn||SIDn_new')
 *         Verify β' == β
 *         Accept SK', store SIDn_new'
 *         γ = h(SIDn_new'||SK')
 *     M3 reply: {γ(32)} = 32 bytes
 *
 * Hash count: 3 hashes per auth (matches paper Table VI)
 * ========================================================================== */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include "contiki.h"
#include "coap-engine.h"
#include "coap-blocking-api.h"
#include "aes.h"
#include "sha256.h"
#include "net/ipv6/uip-ds6.h"
#include "sys/node-id.h"
#include "random.h"
#include "project-conf.h"
#include "sys/energest.h"

/* --------------------------------------------------------------------------
 * Shared long-term key between GW and Sensor — 16 bytes (secure channel)
 * -------------------------------------------------------------------------- */
static const uint8_t K_GW_SN[16] = {
    0x73,0x6E,0x67,0x77,0x20,0x6B,0x65,0x79,
    0x5F,0x73,0x65,0x63,0x75,0x72,0x65,0x00
};

/* --------------------------------------------------------------------------
 * Sensor state
 * -------------------------------------------------------------------------- */
static uint8_t sn_id;            /* SNn — real identity (= node_id)       */
static uint8_t SIDn[32];         /* Pseudonym assigned by GW              */
static uint8_t session_key[32];  /* Current session key SK                */
static uint8_t registered = 0;   /* 1 after registration completes        */

/* --------------------------------------------------------------------------
 * Energest
 * -------------------------------------------------------------------------- */
#define CURRENT_CPU    1.8e-3
#define CURRENT_LPM    0.0545e-3
#define CURRENT_TX     17.4e-3
#define CURRENT_RX     18.8e-3
#define SUPPLY_VOLTAGE 3.0

static double cpu_enroll_before, energy_enroll_before;
static double cpu_enroll_after,  energy_enroll_after;
static double cpu_auth_before,   energy_auth_before;
static double cpu_auth_after,    energy_auth_after;
static uint8_t auth_count = 0;

static void print_energest_stats(double *seconds_cpu, double *total_energy)
{
    energest_flush();
    unsigned long cpu_ticks = energest_type_time(ENERGEST_TYPE_CPU);
    unsigned long lpm_ticks = energest_type_time(ENERGEST_TYPE_LPM);
    unsigned long tx_ticks  = energest_type_time(ENERGEST_TYPE_TRANSMIT);
    unsigned long rx_ticks  = energest_type_time(ENERGEST_TYPE_LISTEN);

    *seconds_cpu       = cpu_ticks / (double)ENERGEST_SECOND;
    double seconds_lpm = lpm_ticks / (double)ENERGEST_SECOND;
    double seconds_tx  = tx_ticks  / (double)ENERGEST_SECOND;
    double seconds_rx  = rx_ticks  / (double)ENERGEST_SECOND;

    double energy_cpu = *seconds_cpu * CURRENT_CPU * SUPPLY_VOLTAGE;
    double energy_lpm = seconds_lpm  * CURRENT_LPM * SUPPLY_VOLTAGE;
    double energy_tx  = seconds_tx   * CURRENT_TX  * SUPPLY_VOLTAGE;
    double energy_rx  = seconds_rx   * CURRENT_RX  * SUPPLY_VOLTAGE;

    *total_energy = energy_cpu + energy_lpm + energy_tx + energy_rx;
}

/* --------------------------------------------------------------------------
 * Crypto helpers
 * -------------------------------------------------------------------------- */

/* PUF simulation — deterministic: same challenge Cn always → same Rn.
 * Models an ideal PUF as Rn = SHA256(node_id || Cn)[0].
 * This ensures registration and auth produce identical Rn. */
static uint8_t simulate_puf_response(uint8_t c)
{
    uint8_t in[2], out[32];
    in[0] = (uint8_t)node_id;
    in[1] = c;
    SHA256_CTX ctx;
    sha256_init(&ctx);
    sha256_update(&ctx, in, 2);
    sha256_final(&ctx, out);
    return out[0];
}

/* SHA-256 one-shot */
static void H(const uint8_t *in, uint16_t len, uint8_t *out)
{
    SHA256_CTX ctx;
    sha256_init(&ctx);
    sha256_update(&ctx, in, len);
    sha256_final(&ctx, out);
}

/* Double-hash to produce 64-byte mask from short input.
 * H2(x) = H(x || 0x00) || H(x || 0x01)
 * Used where paper XORs (SK||SIDn_new) [64B] with h(Rn) [32B].
 * The paper counts this as 1 hash conceptually; we need 2 calls
 * to cover 64 bytes. */
static void H2(const uint8_t *in, uint16_t len, uint8_t *out64)
{
    uint8_t buf[256];
    if (len > 254) len = 254;
    memcpy(buf, in, len);

    buf[len] = 0x00;
    H(buf, len + 1, out64);

    buf[len] = 0x01;
    H(buf, len + 1, out64 + 32);
}

/* AES-ECB encrypt/decrypt n consecutive 16-byte blocks in-place */
static void aes_enc(const uint8_t *key, uint8_t *buf, uint8_t n)
{
    struct AES_ctx ctx;
    for (uint8_t i = 0; i < n; i++) {
        AES_init_ctx(&ctx, key);
        AES_ECB_encrypt(&ctx, buf + i * 16);
    }
}
static void aes_dec(const uint8_t *key, uint8_t *buf, uint8_t n)
{
    struct AES_ctx ctx;
    for (uint8_t i = 0; i < n; i++) {
        AES_init_ctx(&ctx, key);
        AES_ECB_decrypt(&ctx, buf + i * 16);
    }
}

/* --------------------------------------------------------------------------
 * Endpoints
 * -------------------------------------------------------------------------- */
static coap_endpoint_t ep_gw_server;
static coap_message_t  request[1];

static void discover_gw_server(void)
{
    uip_ipaddr_t a;
    /* Sensor nodes <= GW_SN_SPLIT → GW server 2, others → GW server 3 */
    uint8_t gw_id = (sn_id <= GW_SN_SPLIT) ? (uint8_t)GW_SERVER_ID : (uint8_t)GW_SERVER_ID2;
    uip_ip6addr_u8(&a, 0xfd,0,0,0,0,0,0,0,
                   0x02,gw_id,0,gw_id,0,gw_id,0,gw_id);
    uip_ipaddr_copy(&ep_gw_server.ipaddr, &a);
    ep_gw_server.port = UIP_HTONS(COAP_DEFAULT_PORT);
}

/* ==========================================================================
 * Registration handlers
 * ========================================================================== */

/* Reg Step 2 response: receives AES_enc(K_GW_SN, [SIDn(32) | Cn(1) | pad]) */
static uint8_t reg_Cn;  /* challenge received from GW */

static void client_reg_handler(coap_message_t *resp)
{
    const uint8_t *chunk;
    if (!resp || coap_get_payload(resp, &chunk) < 48) {
        printf("SN %u: Reg reply dropped\n", sn_id);
        return;
    }
    uint8_t plain[48];
    memcpy(plain, chunk, 48);
    aes_dec(K_GW_SN, plain, 3);

    memcpy(SIDn, plain, 32);
    reg_Cn = plain[32];

    printf("SN %u: Reg-0 OK. SIDn=%02x%02x%02x, Cn=%u\n",
           sn_id, SIDn[0], SIDn[1], SIDn[2], reg_Cn);
}

/* Reg Step 3 confirm: sends Rn back, gets ack */
static void client_reg1_handler(coap_message_t *resp)
{
    if (!resp) {
        printf("SN %u: Reg-1 dropped\n", sn_id);
        return;
    }
    registered = 1;
    printf("SN %u: Registration complete\n", sn_id);
}

/* ==========================================================================
 * Authentication handler — receives M2, replies with M3
 *
 * M2 from GW: {SKn(64) | β(32) | Cn(1)} = 97 bytes
 *
 * SN processing:
 *   1. Rn ← PUF(Cn)                                          [1 PUF]
 *   2. (SK'||SIDn_new') = SKn ⊕ H2(Rn)                       [~1 hash]
 *   3. β' = h(SK'||Rn||SIDn||SIDn_new')                       [1 hash]
 *   4. Verify β' == β
 *   5. γ = h(SIDn_new'||SK')                                  [1 hash]
 *
 * M3 reply: {γ(32)} = 32 bytes
 * ========================================================================== */
static void res_auth_sn_handler(coap_message_t *req, coap_message_t *resp,
                                 uint8_t *buf, uint16_t ps, int32_t *off)
{
    const uint8_t *chunk;
    int len = coap_get_payload(req, &chunk);
    if (len < 97) {
        printf("SN %u: M2 too short (%d)\n", sn_id, len);
        return;
    }

    /* === AUTH BEFORE snapshot === */
    if (auth_count == 0) {
        print_energest_stats(&cpu_auth_before, &energy_auth_before);
    }

    /* Parse M2 */
    uint8_t SKn[64], beta[32], Cn;
    memcpy(SKn,  chunk,      64);
    memcpy(beta, chunk + 64, 32);
    Cn = chunk[96];

    /* Step 1: Rn ← PUF(Cn) */
    uint8_t Rn = simulate_puf_response(Cn);

    /* Step 2: (SK'||SIDn_new') = SKn ⊕ H2(Rn)
     * H2 produces 64-byte mask from Rn */
    uint8_t rn_buf[1] = {Rn};
    uint8_t mask64[64];
    H2(rn_buf, 1, mask64);

    uint8_t SK_prime[32], SIDn_new_prime[32];
    for (int i = 0; i < 32; i++) SK_prime[i]       = SKn[i]      ^ mask64[i];
    for (int i = 0; i < 32; i++) SIDn_new_prime[i]  = SKn[32 + i] ^ mask64[32 + i];

    /* Step 3: β' = h(SK'||Rn||SIDn||SIDn_new') */
    uint8_t beta_in[97];     /* 32+1+32+32 = 97 */
    memcpy(beta_in,      SK_prime,       32);
    beta_in[32] = Rn;
    memcpy(beta_in + 33, SIDn,           32);
    memcpy(beta_in + 65, SIDn_new_prime, 32);
    uint8_t beta_prime[32];
    H(beta_in, 97, beta_prime);

    /* Step 4: Verify β' == β */
    if (memcmp(beta_prime, beta, 32) != 0) {
        printf("SN %u: M2 verification FAILED — β mismatch\n", sn_id);
        /* Reject: delete SK' and SIDn_new' */
        return;
    }

    /* Accept SK', store SIDn_new' */
    memcpy(session_key, SK_prime, 32);
    memcpy(SIDn, SIDn_new_prime, 32);
    printf("SN %u: M2 verified OK. New SIDn=%02x%02x%02x\n",
           sn_id, SIDn[0], SIDn[1], SIDn[2]);

    /* Step 5: γ = h(SIDn_new'||SK') */
    uint8_t gamma_in[64];    /* 32+32 = 64 */
    memcpy(gamma_in,      SIDn_new_prime, 32);
    memcpy(gamma_in + 32, SK_prime,       32);
    uint8_t gamma[32];
    H(gamma_in, 64, gamma);

    /* M3 reply: {γ(32)} */
    coap_set_payload(resp, gamma, 32);

    printf("SN %u: Sent M3 (γ)\n", sn_id);

    /* === AUTH AFTER snapshot === */
    if (auth_count == 0) {
        print_energest_stats(&cpu_auth_after, &energy_auth_after);
        printf("\nAUTH_ENERGY_SN|%u|cpu_s=%f|energy_j=%f",
               sn_id,
               (cpu_auth_after - cpu_auth_before),
               (energy_auth_after - energy_auth_before));
        auth_count++;
    }
}

/* --------------------------------------------------------------------------
 * CoAP resource declaration
 * -------------------------------------------------------------------------- */
RESOURCE(res_auth_sn, "title=\"AuthSN\"", NULL, res_auth_sn_handler, NULL, NULL);

/* ==========================================================================
 * Main process
 * ========================================================================== */
PROCESS(sn_proc, "Sensor Node");
AUTOSTART_PROCESSES(&sn_proc);
static struct etimer et;

PROCESS_THREAD(sn_proc, ev, data)
{
    PROCESS_BEGIN();

    sn_id = (uint8_t)node_id;
    discover_gw_server();

    /* Start CoAP engine for receiving M2 */
    coap_engine_init();
    coap_activate_resource(&res_auth_sn, "test/auth_sn");

    /* Staggered start */
    etimer_set(&et, CLOCK_SECOND * (5 + node_id));

    while (1) {
        PROCESS_YIELD();

        if (etimer_expired(&et)) {

            if (!registered) {
                /* === ENROLLMENT BEFORE snapshot === */
                print_energest_stats(&cpu_enroll_before, &energy_enroll_before);

                /* ---- Sensor Registration Step 1 ----
                 * Send SNn to GW over secure channel.
                 * Payload: AES_enc(K_GW_SN, [SNn | pad]) = 16 bytes */
                uint8_t p0[16];
                memset(p0, 0, 16);
                p0[0] = sn_id;
                aes_enc(K_GW_SN, p0, 1);

                coap_init_message(request, COAP_TYPE_CON, COAP_POST, 0);
                coap_set_header_uri_path(request, "test/sn_reg");
                coap_set_payload(request, p0, 16);
                printf("SN %u: Sending registration\n", sn_id);
                COAP_BLOCKING_REQUEST(&ep_gw_server, request, client_reg_handler);

                /* ---- Sensor Registration Step 3 ----
                 * Compute Rn ← PUF(Cn), send Rn back to GW
                 * Payload: AES_enc(K_GW_SN, [Rn | sn_id | pad]) = 16 bytes */
                uint8_t Rn = simulate_puf_response(reg_Cn);

                uint8_t p1[16];
                memset(p1, 0, 16);
                p1[0] = Rn;
                p1[1] = sn_id;
                aes_enc(K_GW_SN, p1, 1);

                coap_init_message(request, COAP_TYPE_CON, COAP_POST, 1);
                coap_set_header_uri_path(request, "test/sn_reg1");
                coap_set_payload(request, p1, 16);
                printf("SN %u: Sending PUF response Rn=%u\n", sn_id, Rn);
                COAP_BLOCKING_REQUEST(&ep_gw_server, request, client_reg1_handler);

                /* === ENROLLMENT AFTER snapshot === */
                print_energest_stats(&cpu_enroll_after, &energy_enroll_after);
                printf("\nENROLL_ENERGY_SN|%u|cpu_s=%f|energy_j=%f",
                       sn_id,
                       (cpu_enroll_after - cpu_enroll_before),
                       (energy_enroll_after - energy_enroll_before));
            }

            etimer_reset(&et);
        }
    }

    PROCESS_END();
}
