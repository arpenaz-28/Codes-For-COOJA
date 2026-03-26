/* ==========================================================================
 * user-node.c  —  User/Doctor Device for Zhou et al. scheme
 *
 * Faithful implementation of the User entity from:
 *   "Security-Enhanced Lightweight and Anonymity-Preserving User
 *    Authentication Scheme for IoT-Based Healthcare"
 *   Zhou et al., IEEE IoT Journal, Vol. 11, No. 6, March 2024
 *
 * The User device:
 *  - Has biometrics + fuzzy extractor (simulated)
 *  - Uses secret salt ri for password strengthening
 *  - Participates in User Registration Phase (Section IV.A)
 *  - Sends M1, receives M4 in Auth & Key Exchange Phase (Section IV.C)
 *
 * State machine:
 *   reg == 0  → Registration (User Reg + Sensor binding)
 *   reg == 1, count < 1  → Auth (send M1, wait M4) + Data
 *   count >= 1  → Ongoing data
 *
 * Hash count: 4 hashes per auth (matches paper Table VI)
 *
 * Acts as BOTH CoAP client (M1, data) and server (receives M4).
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
 * Shared long-term key with GW (for secure registration) — 16 bytes
 * -------------------------------------------------------------------------- */
static const uint8_t K_GW_U[16] = {
    0x67,0x77,0x75,0x73,0x20,0x6D,0x79,0x20,
    0x4B,0x75,0x6F,0x67,0x20,0x46,0x75,0x00
};

/* --------------------------------------------------------------------------
 * User state (paper notation)
 * -------------------------------------------------------------------------- */
static uint8_t id_d;             /* Node ID                                 */
static uint8_t id_gw_server;     /* Which GW server to talk to              */

/* Biometric/fuzzy extractor state (simulated) */
static uint8_t ki[32];           /* Secret key from Gen(BIOi)               */
static uint8_t hidi;             /* Auxiliary parameter from Gen(BIOi)       */
static uint8_t ri;               /* Secret salt (8-bit)                      */
static uint8_t CPWi[32];         /* CPWi = h(ki||IDi||ri)                    */

/* Pseudonyms */
static uint8_t DIDi[32];         /* Current user pseudonym                   */
static uint8_t SIDn[32];         /* Current sensor pseudonym (bound sensor)  */

/* Session state */
static uint8_t session_key[32];  /* SK from M4                               */
static uint8_t reg   = 0;

/* --------------------------------------------------------------------------
 * Energest — identical variable naming for comparison
 * -------------------------------------------------------------------------- */
#define CURRENT_CPU    1.8e-3
#define CURRENT_LPM    0.0545e-3
#define CURRENT_TX     17.4e-3
#define CURRENT_RX     18.8e-3
#define SUPPLY_VOLTAGE 3.0

double cpu_enroll_before, energy_enroll_before;
double cpu_enroll_after,  energy_enroll_after;
double cpu_auth_before,   energy_auth_before;
double cpu_auth_after,    energy_auth_after;

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
static void H(const uint8_t *in, uint16_t len, uint8_t *out)
{
    SHA256_CTX ctx;
    sha256_init(&ctx);
    sha256_update(&ctx, in, len);
    sha256_final(&ctx, out);
}

/* Triple-hash: H3(x) = H(x||0) || H(x||1) || H(x||2) for 96-byte output */
static void H3(const uint8_t *in, uint16_t len, uint8_t *out96)
{
    uint8_t buf[256];
    if (len > 253) len = 253;
    memcpy(buf, in, len);
    buf[len] = 0x00; H(buf, len + 1, out96);
    buf[len] = 0x01; H(buf, len + 1, out96 + 32);
    buf[len] = 0x02; H(buf, len + 1, out96 + 64);
}

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

static void gen_random(uint8_t *buf, uint8_t len)
{
    for (uint8_t i = 0; i < len; i++) {
        uint16_t r = random_rand();
        buf[i] = (uint8_t)((r & 0xFF) ^ (uint8_t)(clock_time() >> (i & 7)));
    }
}

/* --------------------------------------------------------------------------
 * Endpoints
 * -------------------------------------------------------------------------- */
static coap_endpoint_t ep_gw_server, ep_gw_router;
static coap_message_t  request[1];

static void discover_endpoints(void)
{
    uip_ipaddr_t a;
    uint8_t gw_s = id_gw_server;
    uint8_t gw_r = (uint8_t)GW_NODE_ID;

    uip_ip6addr_u8(&a, 0xfd,0,0,0,0,0,0,0,
                   0x02,gw_s,0,gw_s,0,gw_s,0,gw_s);
    uip_ipaddr_copy(&ep_gw_server.ipaddr, &a);
    ep_gw_server.port = UIP_HTONS(COAP_DEFAULT_PORT);

    uip_ip6addr_u8(&a, 0xfd,0,0,0,0,0,0,0,
                   0x02,gw_r,0,gw_r,0,gw_r,0,gw_r);
    uip_ipaddr_copy(&ep_gw_router.ipaddr, &a);
    ep_gw_router.port = UIP_HTONS(COAP_DEFAULT_PORT);
}

/* --------------------------------------------------------------------------
 * M4 reception (CoAP server endpoint)
 * -------------------------------------------------------------------------- */
static volatile uint8_t m4_received = 0;
static uint8_t m4_SKi[96];
static uint8_t m4_lambda[32];
PROCESS_NAME(user_proc);
static process_event_t ev_m4_done;

static void res_m4_handler(coap_message_t *req, coap_message_t *resp,
                            uint8_t *buf, uint16_t ps, int32_t *off)
{
    const uint8_t *chunk;
    int len = coap_get_payload(req, &chunk);
    if (len < 128) {
        printf("User %u: M4 too short (%d)\n", id_d, len);
        return;
    }

    memcpy(m4_SKi,    chunk,      96);
    memcpy(m4_lambda, chunk + 96, 32);
    m4_received = 1;

    uint8_t ack = 0xAC;
    coap_set_payload(resp, &ack, 1);

    printf("User %u: M4 received\n", id_d);
    process_post(&user_proc, ev_m4_done, NULL);
}

RESOURCE(res_m4, "title=\"M4\"", NULL, res_m4_handler, NULL, NULL);

/* --------------------------------------------------------------------------
 * Registration response handlers
 * -------------------------------------------------------------------------- */
static void client_user_reg_handler(coap_message_t *resp)
{
    const uint8_t *chunk;
    if (!resp || coap_get_payload(resp, &chunk) < 48) {
        printf("User %u: User reg reply dropped\n", id_d);
        return;
    }
    uint8_t plain[48];
    memcpy(plain, chunk, 48);
    aes_dec(K_GW_U, plain, 3);
    memcpy(DIDi, plain, 32);
    printf("User %u: User reg OK. DIDi=%02x%02x%02x\n",
           id_d, DIDi[0], DIDi[1], DIDi[2]);
}

/* get_sid response handler */
static void client_get_sid_handler(coap_message_t *resp)
{
    const uint8_t *chunk;
    if (!resp || coap_get_payload(resp, &chunk) < 48) {
        printf("User %u: get_sid reply dropped or sensor not enrolled\n", id_d);
        return;
    }
    uint8_t plain[48];
    memcpy(plain, chunk, 48);
    aes_dec(K_GW_U, plain, 3);
    memcpy(SIDn, plain, 32);
    printf("User %u: Got SIDn=%02x%02x%02x\n",
           id_d, SIDn[0], SIDn[1], SIDn[2]);
}

/* M1 ACK handler */
static void client_m1_handler(coap_message_t *resp)
{
    if (!resp) {
        printf("User %u: M1 ACK dropped\n", id_d);
        return;
    }
    const uint8_t *chunk;
    int len = coap_get_payload(resp, &chunk);
    if (len >= 1 && chunk[0] == 0xAC) {
        printf("User %u: M1 ACK received\n", id_d);
    } else {
        printf("User %u: M1 rejected\n", id_d);
    }
}

/* Data handler */
static void client_data_handler(coap_message_t *resp)
{
    if (!resp) {
        printf("User %u: Data ACK missing\n", id_d);
        return;
    }
    printf("User %u: Data confirmed\n", id_d);
}

/* ==========================================================================
 * Main process
 * ========================================================================== */
PROCESS(user_proc, "User Device");
AUTOSTART_PROCESSES(&user_proc);
static struct etimer et;

PROCESS_THREAD(user_proc, ev, data)
{
    PROCESS_BEGIN();

    id_d = (uint8_t)node_id;
    /* Users 81–90 → GW server 2,  Users 91–100 → GW server 3 */
    id_gw_server = (node_id <= 90) ? (uint8_t)GW_SERVER_ID : (uint8_t)GW_SERVER_ID2;

    discover_endpoints();

    /* Initialize CoAP engine (for BOTH client and server) */
    coap_engine_init();
    ev_m4_done = process_alloc_event();
    coap_activate_resource(&res_m4, "test/auth_complete");

    /* Staggered start — one-time offset to spread enrollment */
    etimer_set(&et, CLOCK_SECOND * (5 + node_id));
    /* After first fire, timer resets to AUTH_INTERVAL seconds */
#define AUTH_INTERVAL 30

    while (1) {
        PROCESS_YIELD();

        if (etimer_expired(&et)) {

            /* ============================================================
             * REGISTRATION — reg == 0
             * Paper Section IV.A: User Registration Phase
             * ============================================================ */
            if (reg == 0) {
                print_energest_stats(&cpu_enroll_before, &energy_enroll_before);

                /* ---- Simulate fuzzy extractor: (ki, hidi) = Gen(BIOi) ---- */
                gen_random(ki, 32);
                hidi = (uint8_t)(random_rand() & 0xFF);

                /* ---- Generate secret salt ri (8-bit) ---- */
                ri = (uint8_t)(random_rand() & 0xFF);

                /* ---- CPWi = h(ki||IDi||ri) ---- */
                uint8_t cpw_in[34]; /* 32+1+1 */
                memcpy(cpw_in, ki, 32);
                cpw_in[32] = id_d;
                cpw_in[33] = ri;
                H(cpw_in, 34, CPWi);

                /* ---- Send {IDi, ki} to GW via secure channel ----
                 * AES_enc(K_GW_U, [IDi(1) | ki(32) | pad(15)]) = 48 bytes */
                uint8_t p0[48];
                memset(p0, 0, 48);
                p0[0] = id_d;
                memcpy(p0 + 1, ki, 32);
                aes_enc(K_GW_U, p0, 3);

                coap_init_message(request, COAP_TYPE_CON, COAP_POST, 0);
                coap_set_header_uri_path(request, "test/user_reg");
                coap_set_payload(request, p0, 48);
                printf("User %u: Sending user registration\n", id_d);
                COAP_BLOCKING_REQUEST(&ep_gw_server, request, client_user_reg_handler);

                /* ---- Bind sensor: query GW for sensor's SIDn ----
                 * User i (81–100) → Sensor (i-77) (4–23)
                 * POST /test/get_sid with AES_enc(K_GW_U, [sn_id|pad]) */
                static uint8_t bound_sn;
                bound_sn = id_d - 77;  /* sensor node_id */
                {
                    static uint8_t gs[16];
                    memset(gs, 0, 16);
                    gs[0] = bound_sn;
                    aes_enc(K_GW_U, gs, 1);

                    coap_init_message(request, COAP_TYPE_CON, COAP_POST, 1);
                    coap_set_header_uri_path(request, "test/get_sid");
                    coap_set_payload(request, gs, 16);
                    printf("User %u: Querying SIDn for sensor %u\n", id_d, bound_sn);
                    COAP_BLOCKING_REQUEST(&ep_gw_server, request,
                        client_get_sid_handler);
                }
                printf("User %u: Bound to sensor %u, SIDn=%02x%02x%02x\n",
                       id_d, bound_sn, SIDn[0], SIDn[1], SIDn[2]);

                reg = 1;

                print_energest_stats(&cpu_enroll_after, &energy_enroll_after);
                printf("\nENROLL_ENERGY|%u|cpu_s=%f|energy_j=%f",
                       id_d,
                       (cpu_enroll_after - cpu_enroll_before),
                       (energy_enroll_after - energy_enroll_before));

            /* ============================================================
             * AUTH + DATA — reg == 1
             * Paper Section IV.C: Authentication & Key Exchange Phase
             * Runs every timer tick for repeated measurement.
             *
             * User side operations:
             *   1. ki = Rep(hidi, BIOi)  [simulated: ki already in memory]
             *   2. Try ri: CPWi' = h(ki||IDi||ri), verify CPWi' == CPWi
             *   3. Generate bi_new (32 bytes)
             *   4. Ni = bi_new ⊕ h(ki)                    [Hash 1]
             *   5. α = h(bi_new||ki||DIDi||SIDn)           [Hash 2]
             *   6. Send M1: {Ni, α, DIDi, SIDn}
             *   7. Wait for M4: {SKi, λ}
             *   8. (SIDn_new'||SK'||DIDi_new') = SKi ⊕ H3(ki)  [Hash 3]
             *   9. λ' = h(SK'||DIDi||ki||DIDi_new'||SIDn_new') [Hash 4]
             *  10. Verify λ' == λ
             *  11. Accept SK', update DIDi and SIDn
             * ============================================================ */
            } else {

                /* === AUTH BEFORE snapshot === */
                print_energest_stats(&cpu_auth_before, &energy_auth_before);

                /* Step 1: Simulate ki = Rep(hidi, BIOi) — ki already set */
                /* Step 2: Verify CPWi (try ri a few times)
                 * In practice: try ri in [0, 2^8). Since we know ri, it matches
                 * immediately. We still compute the hash for measurement. */
                {
                    uint8_t cpw_in[34];
                    memcpy(cpw_in, ki, 32);
                    cpw_in[32] = id_d;
                    cpw_in[33] = ri;
                    uint8_t cpw_check[32];
                    H(cpw_in, 34, cpw_check);
                    if (memcmp(cpw_check, CPWi, 32) != 0) {
                        printf("User %u: CPWi check FAILED\n", id_d);
                        etimer_reset(&et);
                        continue;
                    }
                }

                /* Step 3: Generate bi_new */
                uint8_t bi_new[32];
                gen_random(bi_new, 32);

                /* Step 4: Ni = bi_new ⊕ h(ki) */
                uint8_t h_ki[32];
                H(ki, 32, h_ki);                     /* Hash 1 */
                uint8_t Ni[32];
                for (int j = 0; j < 32; j++)
                    Ni[j] = bi_new[j] ^ h_ki[j];

                /* Step 5: α = h(bi_new||ki||DIDi||SIDn) */
                uint8_t alpha_in[128]; /* 32+32+32+32 */
                memcpy(alpha_in,      bi_new, 32);
                memcpy(alpha_in + 32, ki,     32);
                memcpy(alpha_in + 64, DIDi,   32);
                memcpy(alpha_in + 96, SIDn,   32);
                uint8_t alpha[32];
                H(alpha_in, 128, alpha);              /* Hash 2 */

                /* Step 6: Send M1: {Ni(32), α(32), DIDi(32), SIDn(32)} = 128B */
                uint8_t m1[128];
                memcpy(m1,      Ni,    32);
                memcpy(m1 + 32, alpha, 32);
                memcpy(m1 + 64, DIDi,  32);
                memcpy(m1 + 96, SIDn,  32);

                coap_init_message(request, COAP_TYPE_CON, COAP_POST, 2);
                coap_set_header_uri_path(request, "test/auth");
                coap_set_payload(request, m1, 128);
                printf("User %u: Sending M1. DIDi=%02x%02x%02x\n",
                       id_d, DIDi[0], DIDi[1], DIDi[2]);
                m4_received = 0;
                COAP_BLOCKING_REQUEST(&ep_gw_server, request, client_m1_handler);

                /* Step 7: Wait for M4 from GW (arrives on /test/auth_complete) */
                printf("User %u: Waiting for M4...\n", id_d);
                if (!m4_received) {
                    PROCESS_WAIT_EVENT_UNTIL(ev == ev_m4_done);
                }

                /* Step 8: (SIDn_new'||SK'||DIDi_new') = SKi ⊕ H3(ki) */
                uint8_t mask96[96];
                H3(ki, 32, mask96);                    /* Hash 3 */

                uint8_t SIDn_new_prime[32], SK_prime[32], DIDi_new_prime[32];
                for (int j = 0; j < 32; j++) SIDn_new_prime[j]  = m4_SKi[j]      ^ mask96[j];
                for (int j = 0; j < 32; j++) SK_prime[j]        = m4_SKi[32 + j] ^ mask96[32 + j];
                for (int j = 0; j < 32; j++) DIDi_new_prime[j]  = m4_SKi[64 + j] ^ mask96[64 + j];

                /* Step 9: λ' = h(SK'||DIDi||ki||DIDi_new'||SIDn_new') */
                uint8_t lambda_in[160]; /* 32+32+32+32+32 */
                memcpy(lambda_in,       SK_prime,        32);
                memcpy(lambda_in + 32,  DIDi,            32);
                memcpy(lambda_in + 64,  ki,              32);
                memcpy(lambda_in + 96,  DIDi_new_prime,  32);
                memcpy(lambda_in + 128, SIDn_new_prime,  32);
                uint8_t lambda_prime[32];
                H(lambda_in, 160, lambda_prime);       /* Hash 4 */

                /* Step 10: Verify λ' == λ */
                if (memcmp(lambda_prime, m4_lambda, 32) != 0) {
                    printf("User %u: M4 verification FAILED — λ mismatch\n", id_d);
                    /* Reject SK' and DIDi_new' */
                    etimer_reset(&et);
                    continue;
                }

                /* Step 11: Accept SK', update pseudonyms */
                memcpy(session_key, SK_prime, 32);
                memcpy(DIDi, DIDi_new_prime, 32);
                memcpy(SIDn, SIDn_new_prime, 32);
                printf("User %u: Auth OK. New DIDi=%02x%02x%02x SK=%02x%02x\n",
                       id_d, DIDi[0], DIDi[1], DIDi[2],
                       session_key[0], session_key[1]);

                /* === AUTH AFTER snapshot — log per-round cost === */
                print_energest_stats(&cpu_auth_after, &energy_auth_after);
                printf("\nAUTH_ENERGY|%u|cpu_s=%f|energy_j=%f",
                       id_d,
                       (cpu_auth_after - cpu_auth_before),
                       (energy_auth_after - energy_auth_before));

                /* ---- Data CoAP ---- */
                uint8_t sensor[16];
                memset(sensor, 0, 16);
                sensor[0] = 9;

                uint8_t K_AES[16];
                memcpy(K_AES, session_key, 16);
                aes_enc(K_AES, sensor, 1);

                uint8_t pd[48];
                memcpy(pd,      DIDi,   32);
                memcpy(pd + 32, sensor, 16);

                coap_init_message(request, COAP_TYPE_CON, COAP_POST, 3);
                coap_set_header_uri_path(request, "test/data");
                coap_set_payload(request, pd, 48);
                printf("User %u: Sending data\n", id_d);
                COAP_BLOCKING_REQUEST(&ep_gw_router, request, client_data_handler);
            }

            /* After first iteration (enrollment done), use fixed 30s interval */
            if (reg == 1)
                etimer_set(&et, CLOCK_SECOND * AUTH_INTERVAL);
            else
                etimer_reset(&et);
        }
    }

    PROCESS_END();
}
