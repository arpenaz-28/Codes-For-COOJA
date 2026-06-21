/* ==========================================================================
 * user-node.c  —  User/Doctor Device for Zhou et al. scheme
 *                 DESYNCHRONISATION-RECOVERY DEMO (faithful, separate nodes)
 *
 * Derived verbatim from Zhou-Scheme/user-node.c (the faithful main sim) so
 * that ALL real operations are preserved:
 *   - fuzzy extractor Gen/Rep (simulated), secret salt ri, CPWi = h(ki||IDi||ri)
 *   - bi_new, Ni = bi_new XOR h(ki), alpha = h(bi_new||ki||DIDi||SIDn)
 *   - M1 = {Ni, alpha, DIDi, SIDn} (128 B), M4 = {SKi(96), lambda(32)}
 *   - M4 unmask via H3(ki) XOR, lambda verification
 * The Medical Gateway (gw-server.c) and Sensor Node (sn-node.c) are SEPARATE
 * COOJA motes running the unmodified main-sim firmware, so the real M2/M3
 * gateway<->sensor sub-exchange (PUF, beta, gamma) happens on the wire.
 *
 * Desynchronisation scenario (M4 loss at the device):
 *   Round 1 : normal auth — device, GW and SN all synced.
 *   Round 2 : auth completes at GW+SN (they rotate to the new SIDn/DIDi), but
 *             the device DISCARDS M4 -> device keeps its old DIDi and SIDn.
 *             The device is now behind GW+SN.
 *   Round 3 : device re-authenticates with its stale DIDi/SIDn.  The sensor
 *             holds the advanced SIDn, so the gateway<->sensor beta check
 *             fails and no M4 is returned (auth FAILS).  Zhou has no
 *             dual-state recovery, so the device performs a full
 *             RE-REGISTRATION (fresh DIDi) + sensor re-bind (current SIDn) and
 *             retries -> success.  This re-registration is the recovery cost.
 *   Round 4 : normal post-recovery auth.
 *
 * Per-round ENERGEST is logged as DESYNC_{ENROLL,ROUND1..4}_ENERGY so the same
 * plot_desync_bar.py (Round 1 = normal, Round 3 = recovery) can be reused.
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

/* Shared long-term key with GW (secure registration channel) */
static const uint8_t K_GW_U[16] = {
    0x67,0x77,0x75,0x73,0x20,0x6D,0x79,0x20,
    0x4B,0x75,0x6F,0x67,0x20,0x46,0x75,0x00
};

/* --------------------------------------------------------------------------
 * User state (paper notation)
 * -------------------------------------------------------------------------- */
static uint8_t id_d;
static uint8_t id_gw_server;
static uint8_t bound_sn;

static uint8_t ki[32];           /* Secret key from Gen(BIOi)                */
static uint8_t hidi;             /* Auxiliary parameter from Gen(BIOi)       */
static uint8_t ri;               /* Secret salt (8-bit)                      */
static uint8_t CPWi[32];         /* CPWi = h(ki||IDi||ri)                    */

static uint8_t DIDi[32];         /* Current user pseudonym                   */
static uint8_t SIDn[32];         /* Current sensor pseudonym                 */
static uint8_t session_key[32];

static uint8_t auth_round = 0;   /* 0 = enrol; 1 = warm-up; 2..5 = R1..R4     */
static uint8_t warmups    = 0;   /* completed warm-up auths                   */

/* M1 context needed to verify the matching M4 */
static uint8_t m1_DIDi[32];

/* --------------------------------------------------------------------------
 * Energest
 * -------------------------------------------------------------------------- */
#define CURRENT_CPU    1.8e-3
#define CURRENT_LPM    0.0545e-3
#define CURRENT_TX     17.4e-3
#define CURRENT_RX     18.8e-3
#define SUPPLY_VOLTAGE 3.0

static double cpu_before, energy_before;
static double cpu_after,  energy_after;

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
 * Crypto helpers (identical to main sim)
 * -------------------------------------------------------------------------- */
static void H(const uint8_t *in, uint16_t len, uint8_t *out)
{
    SHA256_CTX ctx;
    sha256_init(&ctx);
    sha256_update(&ctx, in, len);
    sha256_final(&ctx, out);
}

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
static volatile uint8_t m4_received = 0;   /* 1 once a valid M4 (128B) arrived */
static volatile uint8_t m4_fail = 0;       /* 1 if GW signalled auth failure   */
static uint8_t m4_SKi[96];
static uint8_t m4_lambda[32];
PROCESS_NAME(user_proc);
static process_event_t ev_m4_done;

static void res_m4_handler(coap_message_t *req, coap_message_t *resp,
                            uint8_t *buf, uint16_t ps, int32_t *off)
{
    const uint8_t *chunk;
    int len = coap_get_payload(req, &chunk);

    uint8_t ack = 0xAC;
    coap_set_payload(resp, &ack, 1);

    if (len < 128) {
        /* Gateway fail notification — recover without idle-waiting */
        m4_fail = 1;
        process_post(&user_proc, ev_m4_done, NULL);
        return;
    }

    memcpy(m4_SKi,    chunk,      96);
    memcpy(m4_lambda, chunk + 96, 32);
    m4_received = 1;
    process_post(&user_proc, ev_m4_done, NULL);
}
RESOURCE(res_m4, "title=\"M4\"", NULL, res_m4_handler, NULL, NULL);

/* --------------------------------------------------------------------------
 * Registration / bind / M1 / data response handlers
 * -------------------------------------------------------------------------- */
static void client_user_reg_handler(coap_message_t *resp)
{
    const uint8_t *chunk;
    if (!resp || coap_get_payload(resp, &chunk) < 48) return;
    uint8_t plain[48];
    memcpy(plain, chunk, 48);
    aes_dec(K_GW_U, plain, 3);
    memcpy(DIDi, plain, 32);
}

static void client_get_sid_handler(coap_message_t *resp)
{
    const uint8_t *chunk;
    if (!resp || coap_get_payload(resp, &chunk) < 48) return;
    uint8_t plain[48];
    memcpy(plain, chunk, 48);
    aes_dec(K_GW_U, plain, 3);
    memcpy(SIDn, plain, 32);
}

static void client_m1_handler(coap_message_t *resp) { (void)resp; }
static void client_data_handler(coap_message_t *resp) { (void)resp; }

/* --------------------------------------------------------------------------
 * Compute helpers (no protothread waits — safe to call from the thread)
 * -------------------------------------------------------------------------- */

/* Simulate (ki, hidi) = Gen(BIOi) and derive CPWi.  Used at enrolment and on
 * recovery re-registration (fresh ki, as a full re-enrolment would). */
static void compute_fe_and_cpwi(void)
{
    gen_random(ki, 32);
    hidi = (uint8_t)(random_rand() & 0xFF);
    ri   = (uint8_t)(random_rand() & 0xFF);
    uint8_t cpw_in[34];
    memcpy(cpw_in, ki, 32);
    cpw_in[32] = id_d;
    cpw_in[33] = ri;
    H(cpw_in, 34, CPWi);
}

/* Build M1 (128 B) from current DIDi/SIDn.  Records m1_DIDi for M4 check. */
static void prepare_m1(uint8_t *m1)
{
    /* Step 1-2: Rep + verify CPWi (compute the hash for measurement) */
    uint8_t cpw_in[34], cpw_check[32];
    memcpy(cpw_in, ki, 32);
    cpw_in[32] = id_d;
    cpw_in[33] = ri;
    H(cpw_in, 34, cpw_check);              /* CPWi verification hash         */

    uint8_t bi_new[32];
    gen_random(bi_new, 32);

    uint8_t h_ki[32];
    H(ki, 32, h_ki);                       /* Hash 1                         */
    uint8_t Ni[32];
    for (int j = 0; j < 32; j++) Ni[j] = bi_new[j] ^ h_ki[j];   /* XOR       */

    uint8_t alpha_in[128], alpha[32];
    memcpy(alpha_in,      bi_new, 32);
    memcpy(alpha_in + 32, ki,     32);
    memcpy(alpha_in + 64, DIDi,   32);
    memcpy(alpha_in + 96, SIDn,   32);
    H(alpha_in, 128, alpha);               /* Hash 2                         */

    memcpy(m1,      Ni,    32);
    memcpy(m1 + 32, alpha, 32);
    memcpy(m1 + 64, DIDi,  32);
    memcpy(m1 + 96, SIDn,  32);

    memcpy(m1_DIDi, DIDi, 32);
}

/* Process a received M4: unmask via H3(ki), verify lambda.
 * Returns 1 if valid (and fills out_SK/out_DIDi/out_SIDn), 0 otherwise. */
static int process_m4(uint8_t *out_SK, uint8_t *out_DIDi, uint8_t *out_SIDn)
{
    uint8_t mask96[96];
    H3(ki, 32, mask96);                    /* Hash 3                         */

    uint8_t SIDn_new[32], SK[32], DIDi_new[32];
    for (int j = 0; j < 32; j++) SIDn_new[j] = m4_SKi[j]      ^ mask96[j];
    for (int j = 0; j < 32; j++) SK[j]       = m4_SKi[32 + j] ^ mask96[32 + j];
    for (int j = 0; j < 32; j++) DIDi_new[j] = m4_SKi[64 + j] ^ mask96[64 + j];

    uint8_t lambda_in[160], lambda_chk[32];
    memcpy(lambda_in,       SK,        32);
    memcpy(lambda_in + 32,  m1_DIDi,   32);  /* DIDi used in the matching M1 */
    memcpy(lambda_in + 64,  ki,        32);
    memcpy(lambda_in + 96,  DIDi_new,  32);
    memcpy(lambda_in + 128, SIDn_new,  32);
    H(lambda_in, 160, lambda_chk);         /* Hash 4                         */

    if (memcmp(lambda_chk, m4_lambda, 32) != 0) return 0;

    memcpy(out_SK,   SK,       32);
    memcpy(out_DIDi, DIDi_new, 32);
    memcpy(out_SIDn, SIDn_new, 32);
    return 1;
}

static void build_user_reg(uint8_t *p0)
{
    memset(p0, 0, 48);
    p0[0] = id_d;
    memcpy(p0 + 1, ki, 32);
    aes_enc(K_GW_U, p0, 3);
}

static void build_get_sid(uint8_t *gs)
{
    memset(gs, 0, 16);
    gs[0] = bound_sn;
    aes_enc(K_GW_U, gs, 1);
}

static void build_data(uint8_t *pd)
{
    uint8_t sensor[16];
    memset(sensor, 0, 16);
    sensor[0] = 9;
    uint8_t K_AES[16];
    memcpy(K_AES, session_key, 16);
    aes_enc(K_AES, sensor, 1);
    memcpy(pd,      DIDi,   32);
    memcpy(pd + 32, sensor, 16);
}

/* ==========================================================================
 * Main process
 * ========================================================================== */
PROCESS(user_proc, "User Device (desync demo)");
AUTOSTART_PROCESSES(&user_proc);
static struct etimer et;
static struct etimer et_wait;

#define AUTH_INTERVAL  20      /* seconds between rounds                     */
#define M4_TIMEOUT      6      /* seconds to wait for M4 before declaring fail */
#define N_WARMUP        3      /* unmeasured warm-up auths to settle routes  */

PROCESS_THREAD(user_proc, ev, data)
{
    static uint8_t m1[128], p0[48], gs[16], pd[48];
    static uint8_t r_SK[32], r_DIDi[32], r_SIDn[32];
    static int ok;

    PROCESS_BEGIN();

    id_d = (uint8_t)node_id;
    id_gw_server = (node_id <= GW_USER_SPLIT) ? (uint8_t)GW_SERVER_ID
                                              : (uint8_t)GW_SERVER_ID2;
    bound_sn = id_d - SN_USER_OFFSET;
    discover_endpoints();

    coap_engine_init();
    ev_m4_done = process_alloc_event();
    coap_activate_resource(&res_m4, "test/auth_complete");

    /* Wide per-user stagger so the 20 users do NOT all recover in the same
     * window (avoids simulated network congestion contaminating the per-device
     * recovery cost — a real desync hits one device at a time). */
    etimer_set(&et, CLOCK_SECOND * (5 + 5 * (node_id - FIRST_USER_ID)));

    while (1) {
        PROCESS_YIELD();
        if (!etimer_expired(&et)) continue;

        /* ================================================================
         * ENROLMENT
         * ================================================================ */
        if (auth_round == 0) {
            printf("DESYNC_LOG|Node %u|=== ENROLLMENT START ===\n", id_d);
            print_energest_stats(&cpu_before, &energy_before);

            compute_fe_and_cpwi();

            build_user_reg(p0);
            coap_init_message(request, COAP_TYPE_CON, COAP_POST, 0);
            coap_set_header_uri_path(request, "test/user_reg");
            coap_set_payload(request, p0, 48);
            COAP_BLOCKING_REQUEST(&ep_gw_server, request, client_user_reg_handler);

            build_get_sid(gs);
            coap_init_message(request, COAP_TYPE_CON, COAP_POST, 1);
            coap_set_header_uri_path(request, "test/get_sid");
            coap_set_payload(request, gs, 16);
            COAP_BLOCKING_REQUEST(&ep_gw_server, request, client_get_sid_handler);

            auth_round = 1;
            print_energest_stats(&cpu_after, &energy_after);
            printf("\nDESYNC_ENROLL_ENERGY|%u|cpu_s=%f|energy_j=%f\n",
                   id_d, cpu_after - cpu_before, energy_after - energy_before);
            printf("DESYNC_LOG|Node %u|=== ENROLLMENT COMPLETE === DIDi=%02x%02x SIDn=%02x%02x\n",
                   id_d, DIDi[0], DIDi[1], SIDn[0], SIDn[1]);
            etimer_set(&et, CLOCK_SECOND * AUTH_INTERVAL);
            continue;
        }

        /* ================================================================
         * WARM-UP — several unmeasured normal auths so the RPL network (esp.
         * the downward GW->user routes that carry M4) is fully settled before
         * Round 1 is measured.  This keeps the Round-1 baseline clean and equal
         * to the post-recovery Round 4.  NOT logged with a DESYNC marker.
         * ================================================================ */
        if (auth_round == 1) {
            printf("DESYNC_LOG|Node %u|WARM-UP AUTH %u (unmeasured)\n", id_d, warmups);
            prepare_m1(m1);
            m4_received = 0; m4_fail = 0;
            coap_init_message(request, COAP_TYPE_CON, COAP_POST, 2);
            coap_set_header_uri_path(request, "test/auth");
            coap_set_payload(request, m1, 128);
            COAP_BLOCKING_REQUEST(&ep_gw_server, request, client_m1_handler);
            etimer_set(&et_wait, CLOCK_SECOND * M4_TIMEOUT);
            PROCESS_WAIT_EVENT_UNTIL(m4_received || m4_fail || etimer_expired(&et_wait));
            if (m4_received && process_m4(r_SK, r_DIDi, r_SIDn)) {
                memcpy(session_key, r_SK, 32);
                memcpy(DIDi, r_DIDi, 32);
                memcpy(SIDn, r_SIDn, 32);
                build_data(pd);
                coap_init_message(request, COAP_TYPE_CON, COAP_POST, 3);
                coap_set_header_uri_path(request, "test/data");
                coap_set_payload(request, pd, 48);
                COAP_BLOCKING_REQUEST(&ep_gw_router, request, client_data_handler);
            }
            warmups++;
            if (warmups >= N_WARMUP) auth_round = 2;   /* proceed to measured rounds */
            etimer_set(&et, CLOCK_SECOND * AUTH_INTERVAL);
            continue;
        }

        /* ================================================================
         * ROUND 1 — normal auth (establish sync)
         * ================================================================ */
        if (auth_round == 2) {
            printf("DESYNC_LOG|Node %u|Round 1|NORMAL AUTH\n", id_d);
            print_energest_stats(&cpu_before, &energy_before);

            prepare_m1(m1);
            m4_received = 0; m4_fail = 0;
            coap_init_message(request, COAP_TYPE_CON, COAP_POST, 2);
            coap_set_header_uri_path(request, "test/auth");
            coap_set_payload(request, m1, 128);
            COAP_BLOCKING_REQUEST(&ep_gw_server, request, client_m1_handler);

            etimer_set(&et_wait, CLOCK_SECOND * M4_TIMEOUT);
            PROCESS_WAIT_EVENT_UNTIL(m4_received || m4_fail || etimer_expired(&et_wait));

            if (m4_received && process_m4(r_SK, r_DIDi, r_SIDn)) {
                memcpy(session_key, r_SK, 32);
                memcpy(DIDi, r_DIDi, 32);
                memcpy(SIDn, r_SIDn, 32);
                build_data(pd);
                coap_init_message(request, COAP_TYPE_CON, COAP_POST, 3);
                coap_set_header_uri_path(request, "test/data");
                coap_set_payload(request, pd, 48);
                COAP_BLOCKING_REQUEST(&ep_gw_router, request, client_data_handler);
                printf("DESYNC_LOG|Node %u|Round 1|SUCCESS\n", id_d);
            }

            print_energest_stats(&cpu_after, &energy_after);
            printf("\nDESYNC_ROUND1_ENERGY|%u|cpu_s=%f|energy_j=%f\n",
                   id_d, cpu_after - cpu_before, energy_after - energy_before);
            auth_round = 3;
            etimer_set(&et, CLOCK_SECOND * AUTH_INTERVAL);
            continue;
        }

        /* ================================================================
         * ROUND 2 — DESYNC TRIGGER: auth completes at GW+SN, device drops M4
         * (device keeps stale DIDi/SIDn; GW+SN advance)
         * ================================================================ */
        if (auth_round == 3) {
            printf("DESYNC_LOG|Node %u|Round 2|DESYNC TRIGGER (drop M4)\n", id_d);
            print_energest_stats(&cpu_before, &energy_before);

            prepare_m1(m1);
            m4_received = 0; m4_fail = 0;
            coap_init_message(request, COAP_TYPE_CON, COAP_POST, 2);
            coap_set_header_uri_path(request, "test/auth");
            coap_set_payload(request, m1, 128);
            COAP_BLOCKING_REQUEST(&ep_gw_server, request, client_m1_handler);

            etimer_set(&et_wait, CLOCK_SECOND * M4_TIMEOUT);
            PROCESS_WAIT_EVENT_UNTIL(m4_received || m4_fail || etimer_expired(&et_wait));

            /* M4 deliberately DISCARDED — do NOT update DIDi/SIDn, no data. */
            print_energest_stats(&cpu_after, &energy_after);
            printf("\nDESYNC_ROUND2_ENERGY|%u|cpu_s=%f|energy_j=%f\n",
                   id_d, cpu_after - cpu_before, energy_after - energy_before);
            printf("DESYNC_LOG|Node %u|Round 2|DESYNCHRONIZED (kept old DIDi=%02x%02x)\n",
                   id_d, DIDi[0], DIDi[1]);
            auth_round = 4;
            etimer_set(&et, CLOCK_SECOND * AUTH_INTERVAL);
            continue;
        }

        /* ================================================================
         * ROUND 3 — RECOVERY: stale auth fails at SN (beta mismatch),
         * then full re-registration + sensor re-bind + retry.
         * ================================================================ */
        if (auth_round == 4) {
            printf("DESYNC_LOG|Node %u|Round 3|RECOVERY (stale auth -> re-register)\n", id_d);
            print_energest_stats(&cpu_before, &energy_before);

            /* (a) Failed attempt with stale credentials */
            prepare_m1(m1);
            m4_received = 0; m4_fail = 0;
            coap_init_message(request, COAP_TYPE_CON, COAP_POST, 2);
            coap_set_header_uri_path(request, "test/auth");
            coap_set_payload(request, m1, 128);
            COAP_BLOCKING_REQUEST(&ep_gw_server, request, client_m1_handler);
            etimer_set(&et_wait, CLOCK_SECOND * M4_TIMEOUT);
            PROCESS_WAIT_EVENT_UNTIL(m4_received || m4_fail || etimer_expired(&et_wait));

            ok = (m4_received && process_m4(r_SK, r_DIDi, r_SIDn));

            if (!ok) {
                /* (b) RE-REGISTRATION — Zhou has no dual-state fallback */
                printf("DESYNC_LOG|Node %u|Round 3|auth failed -> re-registering\n", id_d);
                compute_fe_and_cpwi();
                build_user_reg(p0);
                coap_init_message(request, COAP_TYPE_CON, COAP_POST, 0);
                coap_set_header_uri_path(request, "test/user_reg");
                coap_set_payload(request, p0, 48);
                COAP_BLOCKING_REQUEST(&ep_gw_server, request, client_user_reg_handler);

                /* (c) sensor re-bind to learn current SIDn */
                build_get_sid(gs);
                coap_init_message(request, COAP_TYPE_CON, COAP_POST, 1);
                coap_set_header_uri_path(request, "test/get_sid");
                coap_set_payload(request, gs, 16);
                COAP_BLOCKING_REQUEST(&ep_gw_server, request, client_get_sid_handler);

                /* (d) retry auth with fresh DIDi + current SIDn */
                prepare_m1(m1);
                m4_received = 0; m4_fail = 0;
                coap_init_message(request, COAP_TYPE_CON, COAP_POST, 2);
                coap_set_header_uri_path(request, "test/auth");
                coap_set_payload(request, m1, 128);
                COAP_BLOCKING_REQUEST(&ep_gw_server, request, client_m1_handler);
                etimer_set(&et_wait, CLOCK_SECOND * M4_TIMEOUT);
                PROCESS_WAIT_EVENT_UNTIL(m4_received || m4_fail || etimer_expired(&et_wait));
                ok = (m4_received && process_m4(r_SK, r_DIDi, r_SIDn));
            }

            if (ok) {
                memcpy(session_key, r_SK, 32);
                memcpy(DIDi, r_DIDi, 32);
                memcpy(SIDn, r_SIDn, 32);
                build_data(pd);
                coap_init_message(request, COAP_TYPE_CON, COAP_POST, 3);
                coap_set_header_uri_path(request, "test/data");
                coap_set_payload(request, pd, 48);
                COAP_BLOCKING_REQUEST(&ep_gw_router, request, client_data_handler);
                printf("DESYNC_LOG|Node %u|Round 3|RECOVERY SUCCESS\n", id_d);
            } else {
                printf("DESYNC_LOG|Node %u|Round 3|RECOVERY FAILED\n", id_d);
            }

            print_energest_stats(&cpu_after, &energy_after);
            printf("\nDESYNC_ROUND3_ENERGY|%u|cpu_s=%f|energy_j=%f\n",
                   id_d, cpu_after - cpu_before, energy_after - energy_before);
            auth_round = 5;
            etimer_set(&et, CLOCK_SECOND * AUTH_INTERVAL);
            continue;
        }

        /* ================================================================
         * ROUND 4 — post-recovery normal auth
         * ================================================================ */
        if (auth_round == 5) {
            printf("DESYNC_LOG|Node %u|Round 4|POST-RECOVERY NORMAL AUTH\n", id_d);
            print_energest_stats(&cpu_before, &energy_before);

            prepare_m1(m1);
            m4_received = 0; m4_fail = 0;
            coap_init_message(request, COAP_TYPE_CON, COAP_POST, 2);
            coap_set_header_uri_path(request, "test/auth");
            coap_set_payload(request, m1, 128);
            COAP_BLOCKING_REQUEST(&ep_gw_server, request, client_m1_handler);
            etimer_set(&et_wait, CLOCK_SECOND * M4_TIMEOUT);
            PROCESS_WAIT_EVENT_UNTIL(m4_received || m4_fail || etimer_expired(&et_wait));

            if (m4_received && process_m4(r_SK, r_DIDi, r_SIDn)) {
                memcpy(session_key, r_SK, 32);
                memcpy(DIDi, r_DIDi, 32);
                memcpy(SIDn, r_SIDn, 32);
                build_data(pd);
                coap_init_message(request, COAP_TYPE_CON, COAP_POST, 3);
                coap_set_header_uri_path(request, "test/data");
                coap_set_payload(request, pd, 48);
                COAP_BLOCKING_REQUEST(&ep_gw_router, request, client_data_handler);
                printf("DESYNC_LOG|Node %u|Round 4|SUCCESS\n", id_d);
            }

            print_energest_stats(&cpu_after, &energy_after);
            printf("\nDESYNC_ROUND4_ENERGY|%u|cpu_s=%f|energy_j=%f\n",
                   id_d, cpu_after - cpu_before, energy_after - energy_before);
            printf("DESYNC_LOG|Node %u|=== DEMO COMPLETE ===\n", id_d);
            auth_round = 6;
            etimer_set(&et, CLOCK_SECOND * AUTH_INTERVAL);
            continue;
        }

        /* Done — idle */
        etimer_set(&et, CLOCK_SECOND * AUTH_INTERVAL);
    }

    PROCESS_END();
}
