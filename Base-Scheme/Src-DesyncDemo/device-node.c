/* ==========================================================================
 * device-node.c  —  Desync Demonstration Device Node (Base Scheme)
 *
 * Demonstrates the LACK of desynchronization recovery in the base scheme
 * (single-state only — no dual-state storage).
 *
 * Protocol rounds:
 *   Round 0: Enrollment (reg step-0 + reg step-1) with AS
 *   Round 1: Normal auth → success (both sides in sync)
 *   Round 2: Auth sent, AS processes & advances M_d → device DROPS the reply
 *            → AS has new M_d, device stuck on old M_d = DESYNC
 *   Round 3: Device retries with OLD M_d → AS hash mismatch → auth FAILS
 *            → Device detects failure → RE-ENROLLS → retries auth
 *            → TOTAL energy of Round 3 = re-enroll + auth costs
 *   Round 4: Normal auth post-recovery → confirms system re-synced
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
 * Shared long-term key (AS and device share this)
 * -------------------------------------------------------------------------- */
static const uint8_t k_as_d[16] = {
    0x67,0x61,0x74,0x73,0x20,0x6D,0x79,0x20,
    0x4B,0x75,0x6F,0x67,0x20,0x46,0x75,0x00
};

/* --------------------------------------------------------------------------
 * Device state
 * -------------------------------------------------------------------------- */
static uint8_t id_d;
static uint8_t id_as;

static uint8_t y_d    = 2;
static uint8_t c_as_d = 3;
static uint8_t c_d;
static uint8_t h_d;       /* helper value from PUF */
static uint8_t ts_1   = 0;
static uint8_t last_ts2 = 0;

/* Single-state M_d (base scheme: no old/new dual-state) */
static uint8_t M_d[32];
static uint8_t k_gw_d[32];

static uint8_t reg        = 0;
static uint8_t auth_round = 0;  /* 0=enroll, 1=round1, 2=round2-drop, 3=round3-recovery, 4=round4-postrecovery */

/* Flag: when 1, device intentionally ignores the AS reply to trigger desync */
static uint8_t simulate_drop = 0;

/* Store whether last auth succeeded */
static uint8_t last_auth_ok = 0;

/* Buffers shared between prepare_auth and client_auth_handler */
static uint8_t hpayload[34];

/* --------------------------------------------------------------------------
 * ENERGEST energy measurement
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
 * Crypto helpers
 * -------------------------------------------------------------------------- */
static void H(const uint8_t *in, uint16_t len, uint8_t *out)
{
    SHA256_CTX ctx;
    sha256_init(&ctx);
    sha256_update(&ctx, in, len);
    sha256_final(&ctx, out);
}

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

static int ts2_seq_fresh(uint8_t recv, uint8_t last)
{
    int diff = ((int)recv - (int)last + 256) % 256;
    return (diff > 0 && diff <= 200);
}

/* --------------------------------------------------------------------------
 * Endpoints
 * -------------------------------------------------------------------------- */
static coap_endpoint_t ep_as, ep_gw;
static coap_message_t  request[1];

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

/* reg step-0: receive [c_d, M_d[0]] AES-encrypted */
static uint8_t reg_payload[16];

static void client_reg_handler(coap_message_t *resp)
{
    const uint8_t *chunk;
    if (!resp || coap_get_payload(resp, &chunk) < 16) {
        printf("DESYNC_LOG|Node %u|Reg-0 dropped\n", id_d);
        return;
    }
    memcpy(reg_payload, chunk, 16);
    struct AES_ctx ctx;
    AES_init_ctx(&ctx, k_as_d);
    AES_ECB_decrypt(&ctx, reg_payload);
    c_d = reg_payload[0];
    memset(M_d, 0, 32);
    M_d[0] = reg_payload[1];
    printf("DESYNC_LOG|Node %u|Reg-0 OK|c_d=%u|M_d[0]=%u\n", id_d, c_d, M_d[0]);
}

/* reg step-1: just confirm enrollment */
static void client_reg1_handler(coap_message_t *resp)
{
    if (!resp) {
        printf("DESYNC_LOG|Node %u|Reg-1 dropped\n", id_d);
        return;
    }
    printf("DESYNC_LOG|Node %u|Reg-1 OK|Enrolled\n", id_d);
}

/* auth reply: [AS_id(1), masked_key(32), ts_2(1)] = 34 bytes
 * Base scheme: only single-state M_d — if AS fails to match, it sends
 * no payload (< 34 bytes), so last_auth_ok = 0.
 */
static void client_auth_handler(coap_message_t *resp)
{
    const uint8_t *chunk;
    if (!resp || coap_get_payload(resp, &chunk) < 34) {
        printf("DESYNC_LOG|Node %u|Round %u|Auth reply not received (auth FAILED — hash mismatch or no response)\n",
               id_d, auth_round);
        last_auth_ok = 0;
        return;
    }

    /* ---- DESYNC TRIGGER: On round 2, device ignores the valid AS reply ---- */
    if (simulate_drop) {
        printf("DESYNC_LOG|Node %u|Round %u|SIMULATED DROP — ignoring valid AS reply\n",
               id_d, auth_round);
        printf("DESYNC_LOG|Node %u|Round %u|Device keeps OLD M_d\n", id_d, auth_round);
        printf("DESYNC_LOG|Node %u|Round %u|AS has ALREADY ADVANCED M_d → STATE IS DESYNCHRONIZED\n",
               id_d, auth_round);
        simulate_drop = 0;  /* only drop once */
        last_auth_ok = 0;
        /* Do NOT update M_d or k_gw_d — device stays on old state */
        return;
    }

    memcpy(hpayload, chunk, 34);

    uint8_t as_id = hpayload[0];
    uint8_t ts_2  = hpayload[33];

    if (!ts2_seq_fresh(ts_2, last_ts2)) {
        printf("DESYNC_LOG|Node %u|Round %u|Stale ts_2\n", id_d, auth_round);
        last_auth_ok = 0;
        return;
    }

    /* Regenerate R_d from stored helper h_d */
    uint8_t R_d = regenerate_response(c_d, h_d);

    /* Recompute Y_d_H = SHA256(y_d) */
    uint8_t Y_d_H[32];
    H(&y_d, 1, Y_d_H);

    /* Recompute mask: SHA256([Y_d_H, M_d(32), R_d, id_as, id_d, ts_2]) */
    uint8_t data_dash[68];
    memset(data_dash, 0, 68);
    memcpy(data_dash,      Y_d_H, 32);
    memcpy(data_dash + 32, M_d,   32);
    data_dash[64] = R_d;
    data_dash[65] = as_id;
    data_dash[66] = id_d;
    data_dash[67] = ts_2;

    uint8_t hash[32];
    H(data_dash, 68, hash);

    /* Unmask received key: M_d_new = received[1..32] XOR hash */
    uint8_t M_d_new[32];
    memcpy(M_d_new, hpayload + 1, 32);
    for (int i = 0; i < 32; i++)
        M_d_new[i] = M_d_new[i] ^ hash[i];

    /* k_gw_d = SHA256([R_d, M_d_new]) */
    uint8_t key_in[33];
    key_in[0] = R_d;
    memcpy(key_in + 1, M_d_new, 32);
    H(key_in, 33, k_gw_d);

    /* Commit new state */
    memcpy(M_d, M_d_new, 32);
    last_ts2 = ts_2;
    ts_1++;
    last_auth_ok = 1;

    printf("DESYNC_LOG|Node %u|Round %u|Auth OK|M_d updated|SYNCED\n",
           id_d, auth_round);
}

static void client_keyupdate_handler(coap_message_t *resp)
{
    const uint8_t *chunk;
    if (!resp || coap_get_payload(resp, &chunk) < 16) {
        printf("DESYNC_LOG|Node %u|Round %u|Key exchange reply missing\n", id_d, auth_round);
        return;
    }
    uint8_t reply[16];
    memcpy(reply, chunk, 16);
    struct AES_ctx _ctx;
    AES_init_ctx(&_ctx, k_gw_d);
    AES_ECB_decrypt(&_ctx, reply);
    printf("DESYNC_LOG|Node %u|Round %u|Key Exchange OK|nonce_resp=%u\n",
           id_d, auth_round, reply[0]);
}

static void client_data_handler(coap_message_t *resp)
{
    if (!resp) {
        printf("DESYNC_LOG|Node %u|Round %u|Data ACK missing\n", id_d, auth_round);
        return;
    }
    printf("DESYNC_LOG|Node %u|Round %u|Data confirmed by GW\n", id_d, auth_round);
}

/* ==========================================================================
 * Auth payload preparation
 * Auth payload = [id_d(1) | masked_Y_dH(32) | ts_1(1)] = 34 bytes
 * Matches Base-Scheme as-node.c res_auth_handler expectations.
 * ========================================================================== */
static uint8_t auth_payload[34];
static uint8_t data_payload[17];

static void prepare_auth(void)
{
    uint8_t R_d = regenerate_response(c_d, h_d);

    /* Y_d_H = SHA256(y_d) */
    uint8_t Y_d_H[32];
    H(&y_d, 1, Y_d_H);

    /* hash = SHA256([R_d, M_d(32), id_d, ts_1]) */
    uint8_t data_c[35];
    memset(data_c, 0, 35);
    data_c[0] = R_d;
    memcpy(data_c + 1, M_d, 32);
    data_c[33] = id_d;
    data_c[34] = ts_1;

    uint8_t hash[32];
    H(data_c, 35, hash);

    /* mask Y_d_H: hash XOR Y_d_H */
    for (int i = 0; i < 32; i++)
        hash[i] = hash[i] ^ Y_d_H[i];

    auth_payload[0] = id_d;
    memcpy(auth_payload + 1, hash, 32);
    auth_payload[33] = ts_1;

    printf("DESYNC_LOG|Node %u|Round %u|Sending auth|id_d=%u|ts_1=%u|M_d[0]=%u\n",
           id_d, auth_round, id_d, ts_1, M_d[0]);
}

static void prepare_data(void)
{
    uint8_t sensor = 9;
    uint8_t K[16];
    memcpy(K, k_gw_d, 16);
    uint8_t payload[16];
    memset(payload, 0, 16);
    payload[0] = sensor;
    struct AES_ctx ctx;
    AES_init_ctx(&ctx, K);
    AES_ECB_encrypt(&ctx, payload);
    data_payload[0] = id_d;
    memcpy(data_payload + 1, payload, 16);
}

/* key exchange payload: [id_d(1), AES(k_gw_d, [nonce,...])(16)] = 17 B */
static uint8_t ku_payload[17];

static void prepare_keyupdate(void)
{
    uint8_t ku_block[16];
    memset(ku_block, 0, 16);
    ku_block[0] = ts_1;   /* nonce = current ts_1 */
    struct AES_ctx _ctx;
    AES_init_ctx(&_ctx, k_gw_d);
    AES_ECB_encrypt(&_ctx, ku_block);
    ku_payload[0] = id_d;
    memcpy(ku_payload + 1, ku_block, 16);
}

/* shared buffer for enrollment steps (inlined in PROCESS_THREAD) */
static uint8_t enroll_payload[16];

/* ==========================================================================
 * Main process
 * ========================================================================== */
PROCESS(device_node, "Device Node (Base Desync Demo)");
AUTOSTART_PROCESSES(&device_node);
static struct etimer et;

PROCESS_THREAD(device_node, ev, data)
{
    PROCESS_BEGIN();

    id_d  = (uint8_t)node_id;
    id_as = (uint8_t)AS_NODE_ID;

    discover_endpoints();

    etimer_set(&et, CLOCK_SECOND * (5 + node_id));

    while (1) {
        PROCESS_YIELD();

        if (etimer_expired(&et)) {

            /* ============================================================
             * ENROLLMENT (auth_round == 0, reg == 0)
             * ============================================================ */
            if (reg == 0) {
                printf("DESYNC_LOG|Node %u|=== ENROLLMENT START ===\n", id_d);

                print_energest_stats(&cpu_before, &energy_before);

                /* --- enrollment step 0 --- */
                {
                    struct AES_ctx _ctx;
                    memset(enroll_payload, 0, 16);
                    enroll_payload[0] = id_d;
                    AES_init_ctx(&_ctx, k_as_d);
                    AES_ECB_encrypt(&_ctx, enroll_payload);
                    coap_init_message(request, COAP_TYPE_CON, COAP_GET, coap_get_mid());
                    coap_set_header_uri_path(request, "test/reg");
                    coap_set_payload(request, enroll_payload, 16);
                    COAP_BLOCKING_REQUEST(&ep_as, request, client_reg_handler);
                }
                /* --- enrollment step 1 --- */
                {
                    struct AES_ctx _ctx;
                    uint8_t _R_d = simulate_puf_response(c_d);
                    uint8_t _secret;
                    generate_helper(_R_d, &h_d, &_secret);
                    memset(enroll_payload, 0, 16);
                    enroll_payload[0] = id_d;
                    enroll_payload[1] = y_d;
                    enroll_payload[2] = _R_d;
                    enroll_payload[3] = c_as_d;
                    AES_init_ctx(&_ctx, k_as_d);
                    AES_ECB_encrypt(&_ctx, enroll_payload);
                    coap_init_message(request, COAP_TYPE_CON, COAP_GET, coap_get_mid());
                    coap_set_header_uri_path(request, "test/reg1");
                    coap_set_payload(request, enroll_payload, 16);
                    COAP_BLOCKING_REQUEST(&ep_as, request, client_reg1_handler);
                }

                reg = 1;
                print_energest_stats(&cpu_after, &energy_after);
                printf("\nDESYNC_ENROLL_ENERGY|%u|cpu_s=%f|energy_j=%f\n",
                       id_d, cpu_after - cpu_before, energy_after - energy_before);
                printf("DESYNC_LOG|Node %u|=== ENROLLMENT COMPLETE ===|M_d[0]=%u\n",
                       id_d, M_d[0]);

            /* ============================================================
             * ROUND 1: Normal authentication (establishes sync)
             * ============================================================ */
            } else if (auth_round == 0) {
                auth_round = 1;
                printf("\nDESYNC_LOG|Node %u|========================================\n", id_d);
                printf("DESYNC_LOG|Node %u|Round 1|NORMAL AUTH (establishing sync)\n", id_d);
                printf("DESYNC_LOG|Node %u|========================================\n", id_d);

                print_energest_stats(&cpu_before, &energy_before);
                prepare_auth();
                coap_init_message(request, COAP_TYPE_CON, COAP_POST, coap_get_mid());
                coap_set_header_uri_path(request, "test/auth");
                coap_set_payload(request, auth_payload, 34);
                COAP_BLOCKING_REQUEST(&ep_as, request, client_auth_handler);

                if (last_auth_ok) {
                    prepare_keyupdate();
                    coap_init_message(request, COAP_TYPE_CON, COAP_POST, coap_get_mid());
                    coap_set_header_uri_path(request, "test/keyupdate");
                    coap_set_payload(request, ku_payload, 17);
                    COAP_BLOCKING_REQUEST(&ep_gw, request, client_keyupdate_handler);

                    prepare_data();
                    coap_init_message(request, COAP_TYPE_CON, COAP_POST, coap_get_mid());
                    coap_set_header_uri_path(request, "test/data");
                    coap_set_payload(request, data_payload, 17);
                    COAP_BLOCKING_REQUEST(&ep_gw, request, client_data_handler);
                    printf("DESYNC_LOG|Node %u|Round 1|RESULT: SUCCESS — both sides synced\n", id_d);
                    print_energest_stats(&cpu_after, &energy_after);
                    printf("\nDESYNC_ROUND1_ENERGY|%u|cpu_s=%f|energy_j=%f\n",
                           id_d, cpu_after - cpu_before, energy_after - energy_before);
                }

            /* ============================================================
             * ROUND 2: Auth succeeds on AS side, but device DROPS reply
             * → Causes desynchronization (base scheme: AS advances M_d,
             *   device keeps old M_d)
             * ============================================================ */
            } else if (auth_round == 1) {
                auth_round = 2;
                printf("\nDESYNC_LOG|Node %u|========================================\n", id_d);
                printf("DESYNC_LOG|Node %u|Round 2|DESYNC TRIGGER — will drop AS reply\n", id_d);
                printf("DESYNC_LOG|Node %u|========================================\n", id_d);

                print_energest_stats(&cpu_before, &energy_before);
                simulate_drop = 1;
                prepare_auth();
                coap_init_message(request, COAP_TYPE_CON, COAP_POST, coap_get_mid());
                coap_set_header_uri_path(request, "test/auth");
                coap_set_payload(request, auth_payload, 34);
                COAP_BLOCKING_REQUEST(&ep_as, request, client_auth_handler);

                printf("DESYNC_LOG|Node %u|Round 2|RESULT: DESYNCHRONIZED\n", id_d);
                print_energest_stats(&cpu_after, &energy_after);
                printf("\nDESYNC_ROUND2_ENERGY|%u|cpu_s=%f|energy_j=%f\n",
                       id_d, cpu_after - cpu_before, energy_after - energy_before);
                printf("DESYNC_LOG|Node %u|Round 2|Device state: OLD M_d[0]=%u\n",
                       id_d, M_d[0]);

            /* ============================================================
             * ROUND 3: Device retries with OLD M_d → AS hash mismatch → FAIL
             * Base scheme has NO dual-state, so AS rejects the request.
             * Device detects failure → RE-ENROLLS → retries auth.
             * TOTAL energy = re-enroll + re-auth costs (measured together).
             * ============================================================ */
            } else if (auth_round == 2) {
                auth_round = 3;
                printf("\nDESYNC_LOG|Node %u|========================================\n", id_d);
                printf("DESYNC_LOG|Node %u|Round 3|RETRY WITH OLD M_d (expect failure in base scheme)\n", id_d);
                printf("DESYNC_LOG|Node %u|========================================\n", id_d);

                /* Start energy measurement for entire Round 3 block */
                print_energest_stats(&cpu_before, &energy_before);

                /* First attempt: auth with old M_d — will fail */
                prepare_auth();
                coap_init_message(request, COAP_TYPE_CON, COAP_POST, coap_get_mid());
                coap_set_header_uri_path(request, "test/auth");
                coap_set_payload(request, auth_payload, 34);
                COAP_BLOCKING_REQUEST(&ep_as, request, client_auth_handler);

                if (!last_auth_ok) {
                    printf("DESYNC_LOG|Node %u|Round 3|Auth FAILED as expected (no dual-state at AS)\n", id_d);
                    printf("DESYNC_LOG|Node %u|Round 3|Base scheme: device must RE-ENROLL to recover\n", id_d);

                    /* RE-ENROLLMENT: get new c_d and M_d from AS */
                    printf("DESYNC_LOG|Node %u|Round 3|RE-ENROLLING...\n", id_d);
                    reg = 0;
                    /* re-enrol step 0 */
                    {
                        struct AES_ctx _ctx;
                        memset(enroll_payload, 0, 16);
                        enroll_payload[0] = id_d;
                        AES_init_ctx(&_ctx, k_as_d);
                        AES_ECB_encrypt(&_ctx, enroll_payload);
                        coap_init_message(request, COAP_TYPE_CON, COAP_GET, coap_get_mid());
                        coap_set_header_uri_path(request, "test/reg");
                        coap_set_payload(request, enroll_payload, 16);
                        COAP_BLOCKING_REQUEST(&ep_as, request, client_reg_handler);
                    }
                    /* re-enrol step 1 */
                    {
                        struct AES_ctx _ctx;
                        uint8_t _R_d = simulate_puf_response(c_d);
                        uint8_t _secret;
                        generate_helper(_R_d, &h_d, &_secret);
                        memset(enroll_payload, 0, 16);
                        enroll_payload[0] = id_d;
                        enroll_payload[1] = y_d;
                        enroll_payload[2] = _R_d;
                        enroll_payload[3] = c_as_d;
                        AES_init_ctx(&_ctx, k_as_d);
                        AES_ECB_encrypt(&_ctx, enroll_payload);
                        coap_init_message(request, COAP_TYPE_CON, COAP_GET, coap_get_mid());
                        coap_set_header_uri_path(request, "test/reg1");
                        coap_set_payload(request, enroll_payload, 16);
                        COAP_BLOCKING_REQUEST(&ep_as, request, client_reg1_handler);
                    }
                    reg = 1;
                    printf("DESYNC_LOG|Node %u|Round 3|Re-enrollment complete|New M_d[0]=%u\n",
                           id_d, M_d[0]);

                    /* Reset ts counters after re-enrollment */
                    ts_1    = 0;
                    last_ts2 = 0;

                    /* Retry auth with new M_d */
                    printf("DESYNC_LOG|Node %u|Round 3|Retrying auth after re-enrollment...\n", id_d);
                    prepare_auth();
                    coap_init_message(request, COAP_TYPE_CON, COAP_POST, coap_get_mid());
                    coap_set_header_uri_path(request, "test/auth");
                    coap_set_payload(request, auth_payload, 34);
                    COAP_BLOCKING_REQUEST(&ep_as, request, client_auth_handler);

                    if (last_auth_ok) {
                        prepare_keyupdate();
                        coap_init_message(request, COAP_TYPE_CON, COAP_POST, coap_get_mid());
                        coap_set_header_uri_path(request, "test/keyupdate");
                        coap_set_payload(request, ku_payload, 17);
                        COAP_BLOCKING_REQUEST(&ep_gw, request, client_keyupdate_handler);

                        prepare_data();
                        coap_init_message(request, COAP_TYPE_CON, COAP_POST, coap_get_mid());
                        coap_set_header_uri_path(request, "test/data");
                        coap_set_payload(request, data_payload, 17);
                        COAP_BLOCKING_REQUEST(&ep_gw, request, client_data_handler);
                        printf("DESYNC_LOG|Node %u|Round 3|RESULT: RECOVERY via RE-ENROLL — high cost\n", id_d);
                        print_energest_stats(&cpu_after, &energy_after);
                        printf("\nDESYNC_ROUND3_ENERGY|%u|cpu_s=%f|energy_j=%f\n",
                               id_d, cpu_after - cpu_before, energy_after - energy_before);
                    } else {
                        printf("DESYNC_LOG|Node %u|Round 3|RESULT: Recovery failed even after re-enroll\n", id_d);
                        print_energest_stats(&cpu_after, &energy_after);
                        printf("\nDESYNC_ROUND3_ENERGY|%u|cpu_s=%f|energy_j=%f\n",
                               id_d, cpu_after - cpu_before, energy_after - energy_before);
                    }
                } else {
                    /* Unexpected: auth succeeded even with old M_d (should not happen) */
                    printf("DESYNC_LOG|Node %u|Round 3|Unexpected auth success with old M_d\n", id_d);
                    print_energest_stats(&cpu_after, &energy_after);
                    printf("\nDESYNC_ROUND3_ENERGY|%u|cpu_s=%f|energy_j=%f\n",
                           id_d, cpu_after - cpu_before, energy_after - energy_before);
                }

            /* ============================================================
             * ROUND 4: Confirm normal operation post-recovery
             * ============================================================ */
            } else if (auth_round == 3) {
                auth_round = 4;
                printf("\nDESYNC_LOG|Node %u|========================================\n", id_d);
                printf("DESYNC_LOG|Node %u|Round 4|POST-RECOVERY NORMAL AUTH\n", id_d);
                printf("DESYNC_LOG|Node %u|========================================\n", id_d);

                print_energest_stats(&cpu_before, &energy_before);
                prepare_auth();
                coap_init_message(request, COAP_TYPE_CON, COAP_POST, coap_get_mid());
                coap_set_header_uri_path(request, "test/auth");
                coap_set_payload(request, auth_payload, 34);
                COAP_BLOCKING_REQUEST(&ep_as, request, client_auth_handler);

                if (last_auth_ok) {
                    prepare_keyupdate();
                    coap_init_message(request, COAP_TYPE_CON, COAP_POST, coap_get_mid());
                    coap_set_header_uri_path(request, "test/keyupdate");
                    coap_set_payload(request, ku_payload, 17);
                    COAP_BLOCKING_REQUEST(&ep_gw, request, client_keyupdate_handler);

                    prepare_data();
                    coap_init_message(request, COAP_TYPE_CON, COAP_POST, coap_get_mid());
                    coap_set_header_uri_path(request, "test/data");
                    coap_set_payload(request, data_payload, 17);
                    COAP_BLOCKING_REQUEST(&ep_gw, request, client_data_handler);
                    printf("DESYNC_LOG|Node %u|Round 4|RESULT: SUCCESS — system fully recovered\n", id_d);
                    print_energest_stats(&cpu_after, &energy_after);
                    printf("\nDESYNC_ROUND4_ENERGY|%u|cpu_s=%f|energy_j=%f\n",
                           id_d, cpu_after - cpu_before, energy_after - energy_before);
                }

                printf("\nDESYNC_LOG|Node %u|=== DESYNC DEMONSTRATION COMPLETE (BASE SCHEME) ===\n", id_d);
            }

            etimer_reset(&et);
        }
    }

    PROCESS_END();
}
