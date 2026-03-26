/* ==========================================================================
 * device-node.c  —  IoT Device Node  (PUF-based Proposed Scheme — TWO-ROUND)
 *
 * Aligns with Base Scheme structure: Auth and Key Exchange are SEPARATE
 * CoAP rounds so each can be independently measured with Energest.
 *
 * State machine:
 *   reg == 0              → Enrollment   : /test/reg + /test/reg1 (same tick)
 *   reg == 1, auth_done==0 → Round 1 Auth : /test/auth   [AUTH_ENERGY]
 *   reg == 1, auth_done==1,
 *             keyex_done==0 → Round 2 KeyEx: /test/keyex  [KEYEX_ENERGY]
 *   keyex_done==1          → Data loop   : /test/data
 *
 * Packet sizes:
 *   /test/reg   send   16 B  (AES enc)
 *   /test/reg1  send   48 B  (AES enc)
 *   /test/auth  send   65 B  PID(32)|Y_asd(32)|ts_1(1)
 *   /test/auth  recv    2 B  ACK(1)|ts_2(1)      ← key material NOT included
 *   /test/keyex send   33 B  PID(32)|ts_2(1)
 *   /test/keyex recv   32 B  m_H(32)
 *   /test/data  send   48 B  PID(32)|AES_enc(data,16)
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
 * Shared long-term key (same as original proposed scheme)
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
static uint8_t ts_1   = 1;
static uint8_t ts_2_last = 0;   /* ts_2 received from AS in Round 1 */

static uint8_t m_d[32];
static uint8_t k_gw_d[32];
static uint8_t PID[32];
static uint8_t auth_PID[32];    /* PID sent during auth, held for keyex calc */
static uint8_t auth_Y_dH[32];   /* Y_dH sent during auth, held for keyex calc */

/* State flags */
static uint8_t reg        = 0;  /* 0 = not enrolled           */
static uint8_t auth_done  = 0;  /* 0 = Round 1 not done       */
static uint8_t keyex_done = 0;  /* 0 = Round 2 not done       */

/* --------------------------------------------------------------------------
 * Energest
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
double cpu_keyex_before,  energy_keyex_before;
double cpu_keyex_after,   energy_keyex_after;

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
 * Helpers
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

/* --- Enrollment Reg-0 reply: c_d + m_d (AES enc, 48 B) --- */
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

/* --- Enrollment Reg-1 reply: "Registered" --- */
static void client_reg1_handler(coap_message_t *resp)
{
    if (!resp) {
        printf("Node %u: Reg-1 dropped\n", id_d);
        return;
    }
    printf("Node %u: Enrolled\n", id_d);
}

/* ==========================================================================
 * Round 1 — /test/auth reply handler
 *
 * AS returns ONLY: ACK(1) | ts_2(1) = 2 bytes
 * Key material (m_H) is NOT included — it comes in Round 2.
 * ========================================================================== */
static void client_auth_handler(coap_message_t *resp)
{
    const uint8_t *chunk;
    if (!resp || coap_get_payload(resp, &chunk) < 2) {
        printf("Node %u: Auth reply dropped\n", id_d);
        return;
    }

    uint8_t ack  = chunk[0];
    uint8_t ts_2 = chunk[1];

    if (ack != 0xAC) {
        printf("Node %u: Bad ACK 0x%02x in auth round\n", id_d, ack);
        return;
    }
    if (!ts2_seq_fresh(ts_2, ts_2_last)) {
        printf("Node %u: Stale ts_2=%u in auth round\n", id_d, ts_2);
        return;
    }

    ts_2_last = ts_2;
    auth_done = 1;
    printf("Node %u: Round 1 Auth OK. ts_2=%u\n", id_d, ts_2);
}

/* ==========================================================================
 * Round 2 — /test/keyex reply handler
 *
 * AS returns: m_H(32) = 32 bytes
 * Device uses m_H to derive m_new, then K_GW_D and new PID.
 * ========================================================================== */
static void client_keyex_handler(coap_message_t *resp)
{
    const uint8_t *chunk;
    if (!resp || coap_get_payload(resp, &chunk) < 32) {
        printf("Node %u: KeyEx reply dropped\n", id_d);
        return;
    }

    uint8_t m_H[32];
    memcpy(m_H, chunk, 32);

    /* Key exchange — device side (same computation as original scheme) */
    uint8_t R_d = regenerate_response(c_d, h_d);
    uint8_t Y_dH[32];
    memcpy(Y_dH, auth_Y_dH, 32);

    /* Recover m_new: mH_mask = H(Y_dH || m_d || R_d || ID_AS || auth_PID || ts_2) */
    uint8_t mh_in[99], mh_mask[32], m_new[32];
    memcpy(mh_in,      Y_dH,     32);
    memcpy(mh_in + 32, m_d,      32);
    mh_in[64] = R_d;
    mh_in[65] = id_as;
    memcpy(mh_in + 66, auth_PID, 32);
    mh_in[98] = ts_2_last;
    H(mh_in, 99, mh_mask);
    for (int i = 0; i < 32; i++) m_new[i] = m_H[i] ^ mh_mask[i];

    /* K_GW_D = H(R_d || m_new) */
    uint8_t kd_in[33];
    kd_in[0] = R_d;
    memcpy(kd_in + 1, m_new, 32);
    H(kd_in, 33, k_gw_d);

    /* Rotate m_d and PID */
    memcpy(m_d, m_new, 32);
    uint8_t pid_buf[33];
    pid_buf[0] = id_d;
    memcpy(pid_buf + 1, m_new, 32);
    H(pid_buf, 33, PID);

    ts_1++;
    keyex_done = 1;
    printf("Node %u: Round 2 KeyEx OK. New PID=%02x%02x%02x\n",
           id_d, PID[0], PID[1], PID[2]);
}

/* --- Data reply handler --- */
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
PROCESS(device_node, "Device Node (Two-Round)");
AUTOSTART_PROCESSES(&device_node);
static struct etimer et;

PROCESS_THREAD(device_node, ev, data)
{
    PROCESS_BEGIN();

    id_d  = (uint8_t)node_id;
    id_as = (node_id <= 90) ? (uint8_t)AS_NODE_ID : (uint8_t)AS_NODE_ID2;

    discover_endpoints();
    etimer_set(&et, CLOCK_SECOND * (5 + node_id));

    while (1) {
        PROCESS_YIELD();

        if (etimer_expired(&et)) {

            /* ============================================================
             * ENROLLMENT — reg == 0
             * Two-step: /test/reg (Reg-0) + /test/reg1 (Reg-1), same tick
             * ============================================================ */
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
                uint8_t R_d = simulate_puf_response(c_d);
                uint8_t secret;
                generate_helper(R_d, &h_d, &secret);

                uint8_t Y_dH[32];
                H(&y_d, 1, Y_dH);

                uint8_t p1[48];
                memset(p1, 0, 48);
                p1[0] = id_d;
                memcpy(p1 + 1, Y_dH, 32);
                p1[33] = R_d;
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

            /* ============================================================
             * ROUND 1 — AUTHENTICATION ONLY (/test/auth)
             * Sends: PID(32) | Y_asd(32) | ts_1(1) = 65 B
             * Expects: ACK(1) | ts_2(1) = 2 B  (NO key material)
             * ============================================================ */
            } else if (reg == 1 && auth_done == 0) {

                print_energest_stats(&cpu_auth_before, &energy_auth_before);

                /* Build auth payload (identical to original scheme) */
                uint8_t R_d = regenerate_response(c_d, h_d);

                uint8_t pid_buf[33];
                pid_buf[0] = id_d;
                memcpy(pid_buf + 1, m_d, 32);
                H(pid_buf, 33, auth_PID);

                H(&y_d, 1, auth_Y_dH);

                uint8_t mask_in[66], mask[32];
                mask_in[0] = R_d;
                memcpy(mask_in + 1,  m_d,      32);
                memcpy(mask_in + 33, auth_PID, 32);
                mask_in[65] = ts_1;
                H(mask_in, 66, mask);

                uint8_t y_asd[32];
                for (int i = 0; i < 32; i++) y_asd[i] = auth_Y_dH[i] ^ mask[i];

                uint8_t pa[65];
                memcpy(pa,      auth_PID, 32);
                memcpy(pa + 32, y_asd,   32);
                pa[64] = ts_1;

                coap_init_message(request, COAP_TYPE_CON, COAP_POST, 2);
                coap_set_header_uri_path(request, "test/auth");
                coap_set_payload(request, pa, 65);
                printf("Node %u: Round 1 — Sending auth. PID=%02x%02x%02x ts_1=%u\n",
                       id_d, auth_PID[0], auth_PID[1], auth_PID[2], ts_1);
                COAP_BLOCKING_REQUEST(&ep_as, request, client_auth_handler);

                print_energest_stats(&cpu_auth_after, &energy_auth_after);
                printf("\nAUTH_ENERGY|%u|cpu_s=%f|energy_j=%f",
                       id_d,
                       cpu_auth_after - cpu_auth_before,
                       energy_auth_after - energy_auth_before);

            /* ============================================================
             * ROUND 2 — KEY EXCHANGE (/test/keyex) — separate CoAP round
             * Sends: PID(32) | ts_2(1) = 33 B
             * Expects: m_H(32) = 32 B
             * AS also forwards token to GW in this handler.
             * ============================================================ */
            } else if (reg == 1 && auth_done == 1 && keyex_done == 0) {

                print_energest_stats(&cpu_keyex_before, &energy_keyex_before);

                uint8_t pk[33];
                memcpy(pk,    auth_PID,  32);   /* PID used during auth */
                pk[32] = ts_2_last;             /* ts_2 received in Round 1 */

                coap_init_message(request, COAP_TYPE_CON, COAP_POST, 3);
                coap_set_header_uri_path(request, "test/keyex");
                coap_set_payload(request, pk, 33);
                printf("Node %u: Round 2 — Sending keyex request\n", id_d);
                COAP_BLOCKING_REQUEST(&ep_as, request, client_keyex_handler);

                print_energest_stats(&cpu_keyex_after, &energy_keyex_after);
                printf("\nKEYEX_ENERGY|%u|cpu_s=%f|energy_j=%f",
                       id_d,
                       cpu_keyex_after - cpu_keyex_before,
                       energy_keyex_after - energy_keyex_before);

            /* ============================================================
             * DATA LOOP — keyex_done == 1
             * ============================================================ */
            } else if (keyex_done == 1) {

                uint8_t sensor[16];
                memset(sensor, 0, 16);
                sensor[0] = 9;

                uint8_t K_AES[16];
                memcpy(K_AES, k_gw_d, 16);
                struct AES_ctx ctx;
                AES_init_ctx(&ctx, K_AES);
                AES_ECB_encrypt(&ctx, sensor);

                uint8_t pd[48];
                memcpy(pd,      PID,    32);
                memcpy(pd + 32, sensor, 16);

                coap_init_message(request, COAP_TYPE_CON, COAP_POST, 4);
                coap_set_header_uri_path(request, "test/data");
                coap_set_payload(request, pd, 48);
                COAP_BLOCKING_REQUEST(&ep_gw, request, client_data_handler);
            }

            etimer_reset(&et);
        }
    }

    PROCESS_END();
}
