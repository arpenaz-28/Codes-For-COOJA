/* ==========================================================================
 * device-node.c  —  IoT Device Node  (DAuth / Das[1] BASE SCHEME — TWO-ROUND)
 *
 * This is the base scheme (das2026comsnets) measured with the SAME
 * delta-snapshot Energest methodology and the SAME two-round auth+keyex
 * structure as the Proposed (anonymity) scheme, so the two are directly
 * comparable.  The ONLY protocol difference vs Proposed:
 *   - NO pseudonym: the real ID_D is sent on the open channel (no PID).
 *   - NO PID rotation, NO dual-state / desync recovery (single m_d).
 *
 * State machine:
 *   reg == 0                        → Enrollment : /test/reg + /test/reg1
 *   reg == 1, auth_done  == 0       → Round 1    : /test/auth   [AUTH_ENERGY]
 *   reg == 1, auth_done  == 1,
 *             keyex_done == 0       → Round 2    : /test/keyex  [KEYEX_ENERGY]
 *   keyex_done == 1                 → Data loop  : /test/data
 *
 * Packet sizes (smaller than Proposed — no 32-byte PID):
 *   /test/reg   send  16 B  AES_enc(K_AS_D, [id_d|pad])
 *   /test/reg1  send  48 B  AES_enc(K_AS_D, [id_d|Y_dH(32)|R_d|c_as_d|pad])
 *   /test/auth  send  34 B  id_d(1) | Y_asd(32) | ts_1(1)
 *   /test/auth  recv   2 B  ACK(1)  | ts_2(1)            ← NO key material
 *   /test/keyex send   2 B  id_d(1) | ts_2(1)
 *   /test/keyex recv  32 B  m_H(32)
 *   /test/data  send  17 B  id_d(1) | AES_enc(K_GW_D[0..15], data(16))
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
 * Shared long-term key — EXACTLY 16 bytes
 * -------------------------------------------------------------------------- */
static const uint8_t K_AS_D[16] = {
    0x67,0x61,0x74,0x73,0x20,0x6D,0x79,0x20,
    0x4B,0x75,0x6F,0x67,0x20,0x46,0x75,0x00
};

/* --------------------------------------------------------------------------
 * Device state
 * -------------------------------------------------------------------------- */
static uint8_t id_d;
static uint8_t id_as;

static uint8_t c_d;
static uint8_t c_as_d = 3;
static uint8_t y_d    = 2;
static uint8_t h_d;
static uint8_t ts_1      = 1;
static uint8_t ts_2_last = 0;   /* ts_2 received from AS in Round 1 */

static uint8_t m_d[32];
static uint8_t k_gw_d[32];
static uint8_t auth_Y_dH[32];   /* Y_dH computed in Round 1, reused in Round 2 */

/* State flags */
static uint8_t reg        = 0;  /* 0 = not enrolled        */
static uint8_t auth_done  = 0;  /* 0 = Round 1 not done    */
static uint8_t keyex_done = 0;  /* 0 = Round 2 not done    */

/* --------------------------------------------------------------------------
 * Energest — identical variable names / positions to Proposed scheme
 * -------------------------------------------------------------------------- */
#define CURRENT_CPU    1.8e-3
#define CURRENT_LPM    0.0545e-3
#define CURRENT_TX     17.4e-3
#define CURRENT_RX     18.8e-3
#define SUPPLY_VOLTAGE 3.0

/* Enrollment measurement */
double cpu_enroll_before, energy_enroll_before;
double cpu_enroll_after,  energy_enroll_after;

/* Round 1 — auth only */
double cpu_auth_before,   energy_auth_before;
double cpu_auth_after,    energy_auth_after;

/* Round 2 — key exchange only */
double cpu_keyex_before,  energy_keyex_before;
double cpu_keyex_after,   energy_keyex_after;

/* Combined auth+keyex window */
double cpu_reg,    energy_reg;    /* snapshot BEFORE Round 1      */
double cpu_auth,   energy_auth;   /* snapshot AFTER  Round 2      */

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
 * Endpoints
 * -------------------------------------------------------------------------- */
static coap_endpoint_t  ep_as, ep_gw;
static coap_message_t   request[1];

/* --------------------------------------------------------------------------
 * Helpers (identical to base scheme)
 * -------------------------------------------------------------------------- */
static uint8_t simulate_puf_response(uint8_t c)
{
    uint8_t path1 = random_rand() ^ c;
    uint8_t path2 = random_rand() ^ c;
    return (path1 > path2) ? 1 : 0;
}

static void generate_helper(uint8_t response, uint8_t *helper, uint8_t *secret)
{
    *secret = 1;
    *helper = *secret & response;
}

static uint8_t regenerate_response(uint8_t challenge, uint8_t helper)
{
    return (helper == 0) ? (helper & challenge) : (helper || challenge);
}

static void H(const uint8_t *in, uint16_t len, uint8_t *out)
{
    SHA256_CTX ctx;
    sha256_init(&ctx);
    sha256_update(&ctx, in, len);
    sha256_final(&ctx, out);
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

static int ts2_seq_fresh(uint8_t recv, uint8_t last)
{
    int diff = ((int)recv - (int)last + 256) % 256;
    return (diff > 0 && diff <= 200);
}

static void discover_endpoints(void)
{
    uip_ipaddr_t a;
    uint8_t a_id = id_as;
    uint8_t g_id = (uint8_t)GW_NODE_ID;

    uip_ip6addr_u8(&a, 0xfd,0,0,0,0,0,0,0,
                   0x02,a_id,0,a_id,0,a_id,0,a_id);
    uip_ipaddr_copy(&ep_as.ipaddr, &a);
    ep_as.port = UIP_HTONS(COAP_DEFAULT_PORT);

    uip_ip6addr_u8(&a, 0xfd,0,0,0,0,0,0,0,
                   0x02,g_id,0,g_id,0,g_id,0,g_id);
    uip_ipaddr_copy(&ep_gw.ipaddr, &a);
    ep_gw.port = UIP_HTONS(COAP_DEFAULT_PORT);
}

/* ==========================================================================
 * CoAP response handlers
 * ========================================================================== */

static void client_reg_handler(coap_message_t *resp)
{
    const uint8_t *chunk;
    if (!resp || coap_get_payload(resp, &chunk) < 48) {
        printf("Node %u: Reg-0 dropped\n", id_d);
        return;
    }
    uint8_t plain[48];
    memcpy(plain, chunk, 48);
    aes_dec(K_AS_D, plain, 3);
    c_d = plain[0];
    memcpy(m_d, plain + 1, 32);
    printf("Node %u: Reg-0 OK. c_d=%u\n", id_d, c_d);
}

static void client_reg1_handler(coap_message_t *resp)
{
    if (!resp) {
        printf("Node %u: Reg-1 dropped\n", id_d);
        return;
    }
    printf("Node %u: Enrolled\n", id_d);
}

/* --------------------------------------------------------------------------
 * Round 1 reply: ACK(1) | ts_2(1) = 2 B
 * Key material NOT included — comes in Round 2.
 * -------------------------------------------------------------------------- */
static void client_auth_handler(coap_message_t *resp)
{
    const uint8_t *chunk;
    if (!resp || coap_get_payload(resp, &chunk) < 2) {
        printf("Node %u: Auth (Round 1) reply dropped\n", id_d);
        return;
    }

    uint8_t ack  = chunk[0];
    uint8_t ts_2 = chunk[1];

    if (ack != 0xAC) {
        printf("Node %u: Bad ACK 0x%02x in Round 1\n", id_d, ack);
        return;
    }
    if (!ts2_seq_fresh(ts_2, ts_2_last)) {
        printf("Node %u: Stale ts_2=%u in Round 1\n", id_d, ts_2);
        return;
    }

    ts_2_last = ts_2;
    auth_done = 1;
    printf("Node %u: Round 1 Auth OK. ts_2=%u\n", id_d, ts_2);
}

/* --------------------------------------------------------------------------
 * Round 2 reply: m_H(32) = 32 B
 * Device derives m_new → K_GW_D.  No PID rotation (base scheme).
 * -------------------------------------------------------------------------- */
static void client_keyex_handler(coap_message_t *resp)
{
    const uint8_t *chunk;
    if (!resp || coap_get_payload(resp, &chunk) < 32) {
        printf("Node %u: KeyEx (Round 2) reply dropped\n", id_d);
        return;
    }

    uint8_t m_H[32];
    memcpy(m_H, chunk, 32);

    /* Recover m_new from m_H */
    uint8_t R_d = regenerate_response(c_d, h_d);
    uint8_t Y_dH[32];
    memcpy(Y_dH, auth_Y_dH, 32);

    /* mH_mask = H(Y_dH || m_d || R_d || ID_AS || id_d || ts_2) = 68-byte input */
    uint8_t mh_in[68], mh_mask[32], m_new[32];
    memcpy(mh_in,      Y_dH, 32);
    memcpy(mh_in + 32, m_d,  32);
    mh_in[64] = R_d;
    mh_in[65] = id_as;
    mh_in[66] = id_d;
    mh_in[67] = ts_2_last;
    H(mh_in, 68, mh_mask);
    for (int i = 0; i < 32; i++) m_new[i] = m_H[i] ^ mh_mask[i];

    /* K_GW_D = H(R_d || m_new) */
    uint8_t kd_in[33];
    kd_in[0] = R_d;
    memcpy(kd_in + 1, m_new, 32);
    H(kd_in, 33, k_gw_d);

    /* Update m_d (single state — no rotation history, no PID) */
    memcpy(m_d, m_new, 32);

    ts_1++;
    keyex_done = 1;
    printf("Node %u: Round 2 KeyEx OK. K_GW_D=%02x%02x%02x\n",
           id_d, k_gw_d[0], k_gw_d[1], k_gw_d[2]);
}

static void client_data_handler(coap_message_t *resp)
{
    if (!resp) {
        printf("Node %u: Data ACK missing\n", id_d);
        return;
    }
    printf("Node %u: Data confirmed\n", id_d);
}

/* ==========================================================================
 * Main process
 * ========================================================================== */
PROCESS(device_node, "Device Node (DAuth Base — Two-Round)");
AUTOSTART_PROCESSES(&device_node);
static struct etimer et;

PROCESS_THREAD(device_node, ev, data)
{
    PROCESS_BEGIN();

    id_d  = (uint8_t)node_id;
    id_as = (uint8_t)(AS_NODE_ID + ((node_id - FIRST_DEVICE_ID) % NUM_AS));

    discover_endpoints();

    /* Staggered start — IDENTICAL to Proposed scheme.  Waits out RPL
     * convergence so the enrollment delta captures crypto + a converged
     * round-trip, NOT the RPL boot wait. */
    etimer_set(&et, CLOCK_SECOND * (5 + node_id));

    while (1) {
        PROCESS_YIELD();

        if (etimer_expired(&et)) {

            /* ================================================================
             * ENROLLMENT — reg == 0
             * Reg-0 + Reg-1 in same timer tick (identical to base scheme)
             * ================================================================ */
            if (reg == 0) {

                print_energest_stats(&cpu_enroll_before, &energy_enroll_before);

                /* --- Reg-0 --- */
                uint8_t p0[16];
                memset(p0, 0, 16);
                p0[0] = id_d;
                aes_enc(K_AS_D, p0, 1);
                coap_init_message(request, COAP_TYPE_CON, COAP_GET, 0);
                coap_set_header_uri_path(request, "test/reg");
                coap_set_payload(request, p0, 16);
                printf("Node %u: Sending Reg-0\n", id_d);
                COAP_BLOCKING_REQUEST(&ep_as, request, client_reg_handler);

                /* --- Reg-1 --- */
                uint8_t R_d_enroll = simulate_puf_response(c_d);
                uint8_t secret;
                generate_helper(R_d_enroll, &h_d, &secret);

                uint8_t Y_dH_enroll[32];
                H(&y_d, 1, Y_dH_enroll);

                uint8_t p1[48];
                memset(p1, 0, 48);
                p1[0] = id_d;
                memcpy(p1 + 1, Y_dH_enroll, 32);
                p1[33] = R_d_enroll;
                p1[34] = c_as_d;
                aes_enc(K_AS_D, p1, 3);
                coap_init_message(request, COAP_TYPE_CON, COAP_POST, 1);
                coap_set_header_uri_path(request, "test/reg1");
                coap_set_payload(request, p1, 48);
                printf("Node %u: Sending Reg-1\n", id_d);
                COAP_BLOCKING_REQUEST(&ep_as, request, client_reg1_handler);

                reg = 1;

                print_energest_stats(&cpu_enroll_after, &energy_enroll_after);
                printf("\nENROLL_ENERGY|%u|cpu_s=%f|energy_j=%f",
                       id_d,
                       cpu_enroll_after - cpu_enroll_before,
                       energy_enroll_after - energy_enroll_before);

            /* ================================================================
             * ROUND 1 — AUTHENTICATION ONLY (/test/auth)
             *
             * Sends:   id_d(1) | Y_asd(32) | ts_1(1)  = 34 B
             * Expects: ACK(1)  | ts_2(1)              =  2 B  (NO key material)
             * ================================================================ */
            } else if (reg == 1 && auth_done == 0) {

                /* BEFORE snapshot (combined auth+keyex window) */
                print_energest_stats(&cpu_reg, &energy_reg);
                /* Round 1 individual snapshot */
                print_energest_stats(&cpu_auth_before, &energy_auth_before);

                /* Build auth payload */
                uint8_t R_d = regenerate_response(c_d, h_d);

                H(&y_d, 1, auth_Y_dH);

                /* mask = H(R_d(1) | m_d(32) | id_d(1) | ts_1(1)) = 35-byte input */
                uint8_t mask_in[35], mask[32];
                mask_in[0] = R_d;
                memcpy(mask_in + 1, m_d, 32);
                mask_in[33] = id_d;
                mask_in[34] = ts_1;
                H(mask_in, 35, mask);

                uint8_t y_asd[32];
                for (int i = 0; i < 32; i++) y_asd[i] = auth_Y_dH[i] ^ mask[i];

                uint8_t pa[34];
                pa[0] = id_d;
                memcpy(pa + 1, y_asd, 32);
                pa[33] = ts_1;

                coap_init_message(request, COAP_TYPE_CON, COAP_POST, 2);
                coap_set_header_uri_path(request, "test/auth");
                coap_set_payload(request, pa, 34);
                printf("Node %u: Round 1 — Sending auth. ts_1=%u\n", id_d, ts_1);
                COAP_BLOCKING_REQUEST(&ep_as, request, client_auth_handler);

                print_energest_stats(&cpu_auth_after, &energy_auth_after);
                printf("\nAUTH_ENERGY|%u|cpu_s=%f|energy_j=%f",
                       id_d,
                       cpu_auth_after - cpu_auth_before,
                       energy_auth_after - energy_auth_before);

            /* ================================================================
             * ROUND 2 — KEY EXCHANGE (/test/keyex)
             *
             * Sends:   id_d(1) | ts_2(1)  = 2 B
             * Expects: m_H(32)            = 32 B
             * ================================================================ */
            } else if (reg == 1 && auth_done == 1 && keyex_done == 0) {

                print_energest_stats(&cpu_keyex_before, &energy_keyex_before);

                uint8_t pk[2];
                pk[0] = id_d;
                pk[1] = ts_2_last;          /* echo ts_2 to prove Round 1 receipt */

                coap_init_message(request, COAP_TYPE_CON, COAP_POST, 3);
                coap_set_header_uri_path(request, "test/keyex");
                coap_set_payload(request, pk, 2);
                printf("Node %u: Round 2 — Sending keyex. ts_2=%u\n", id_d, ts_2_last);
                COAP_BLOCKING_REQUEST(&ep_as, request, client_keyex_handler);

                print_energest_stats(&cpu_keyex_after, &energy_keyex_after);
                printf("\nKEYEX_ENERGY|%u|cpu_s=%f|energy_j=%f",
                       id_d,
                       cpu_keyex_after - cpu_keyex_before,
                       energy_keyex_after - energy_keyex_before);

                /* AFTER snapshot for combined auth+keyex window */
                print_energest_stats(&cpu_auth, &energy_auth);
                printf("\n The CPU time and energy at the end of authentication 1 for client %u are %f and %f",
                       id_d,
                       cpu_auth - cpu_reg,
                       energy_auth - energy_reg);

            /* ================================================================
             * DATA LOOP — keyex_done == 1
             * ================================================================ */
            } else if (keyex_done == 1) {

                uint8_t sensor[16];
                memset(sensor, 0, 16);
                sensor[0] = 9;

                uint8_t K_AES[16];
                memcpy(K_AES, k_gw_d, 16);
                struct AES_ctx ctx;
                AES_init_ctx(&ctx, K_AES);
                AES_ECB_encrypt(&ctx, sensor);

                uint8_t pd[17];
                pd[0] = id_d;
                memcpy(pd + 1, sensor, 16);

                coap_init_message(request, COAP_TYPE_CON, COAP_POST, 4);
                coap_set_header_uri_path(request, "test/data");
                coap_set_payload(request, pd, 17);
                COAP_BLOCKING_REQUEST(&ep_gw, request, client_data_handler);
            }

            etimer_reset(&et);
        }
    }

    PROCESS_END();
}
