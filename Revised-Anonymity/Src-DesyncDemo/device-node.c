/* ==========================================================================
 * device-node.c  —  Desync Demonstration Device Node
 *
 * Demonstrates the dual-state storage (PID_curr/PID_old, m_curr/m_old)
 * desynchronization recovery mechanism in the Anonymity-Extended scheme.
 *
 * Protocol rounds:
 *   Round 1: Normal auth → success (both sides in sync)
 *   Round 2: Auth sent, AS processes & rotates → device DROPS the reply
 *            → AS advanced to new state, device stuck on old = DESYNC
 *   Round 3: Device retries with OLD PID/mask → AS matches PID_old
 *            → Desync recovery succeeds → both sides re-synced
 *   Round 4: Normal auth with new synced state → confirms recovery
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

/* --------------------------------------------------------------------------
 * Shared long-term key
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
static uint8_t last_ts2 = 0;

static uint8_t m_d[32];
static uint8_t k_gw_d[32];
static uint8_t PID[32];
static uint8_t auth_PID[32];
static uint8_t auth_Y_dH[32];

static uint8_t reg   = 0;
static uint8_t auth_round = 0;  /* counts auth rounds: 0, 1, 2, 3 */

/* Flag: when 1, device intentionally ignores the AS reply to trigger desync */
static uint8_t simulate_drop = 0;

/* Store whether last auth succeeded or was dropped */
static uint8_t last_auth_ok = 0;

/* --------------------------------------------------------------------------
 * Endpoints
 * -------------------------------------------------------------------------- */
static coap_endpoint_t ep_as, ep_gw;
static coap_message_t  request[1];

/* --------------------------------------------------------------------------
 * Helpers
 * -------------------------------------------------------------------------- */
static uint8_t puf_response(uint8_t challenge)
{
    uint32_t s = ((uint32_t)node_id   * 2246822519UL)
               ^ ((uint32_t)challenge * 2654435761UL);
    s = ((s >> 16) ^ s) * 0x45d9f3bUL;
    s = ((s >> 16) ^ s) * 0x45d9f3bUL;
    s ^= (s >> 16);
    return (uint8_t)(s & 0xFF);
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
        printf("DESYNC_LOG|Node %u|Reg-0 dropped\n", id_d);
        return;
    }
    uint8_t plain[48];
    memcpy(plain, chunk, 48);
    aes_dec(K_AS_D, plain, 3);
    c_d = plain[0];
    memcpy(m_d, plain + 1, 32);
    printf("DESYNC_LOG|Node %u|Reg-0 OK|c_d=%u\n", id_d, c_d);
}

static void client_reg1_handler(coap_message_t *resp)
{
    if (!resp) {
        printf("DESYNC_LOG|Node %u|Reg-1 dropped\n", id_d);
        return;
    }
    printf("DESYNC_LOG|Node %u|Reg-1 OK|Enrolled\n", id_d);
}

static void client_auth_handler(coap_message_t *resp)
{
    const uint8_t *chunk;
    if (!resp || coap_get_payload(resp, &chunk) < 34) {
        printf("DESYNC_LOG|Node %u|Round %u|Auth reply not received\n",
               id_d, auth_round);
        last_auth_ok = 0;
        return;
    }

    /* ---- DESYNC TRIGGER: On round 2, device ignores the reply ---- */
    if (simulate_drop) {
        printf("DESYNC_LOG|Node %u|Round %u|SIMULATED DROP — ignoring valid AS reply\n",
               id_d, auth_round);
        printf("DESYNC_LOG|Node %u|Round %u|Device keeps OLD PID=%02x%02x%02x and OLD m_d\n",
               id_d, auth_round, PID[0], PID[1], PID[2]);
        printf("DESYNC_LOG|Node %u|Round %u|AS has ALREADY ROTATED to new PID/m → STATE IS DESYNCHRONIZED\n",
               id_d, auth_round);
        simulate_drop = 0;  /* only drop once */
        last_auth_ok = 0;
        /* Do NOT update m_d, PID, ts_1, last_ts2 — device stays on old state */
        return;
    }

    uint8_t ack  = chunk[0];
    uint8_t m_H[32];
    uint8_t ts_2 = chunk[33];
    memcpy(m_H, chunk + 1, 32);

    if (ack != 0xAC) {
        printf("DESYNC_LOG|Node %u|Round %u|Bad ACK 0x%02x\n", id_d, auth_round, ack);
        last_auth_ok = 0;
        return;
    }
    if (!ts2_seq_fresh(ts_2, last_ts2)) {
        printf("DESYNC_LOG|Node %u|Round %u|Stale ts_2\n", id_d, auth_round);
        last_auth_ok = 0;
        return;
    }

    /* Key exchange — device side */
    uint8_t R_d = h_d;
    uint8_t Y_dH[32];
    memcpy(Y_dH, auth_Y_dH, 32);

    uint8_t mh_in[99], mh_mask[32], m_new[32];
    memcpy(mh_in,      Y_dH,     32);
    memcpy(mh_in + 32, m_d,      32);
    mh_in[64] = R_d;
    mh_in[65] = id_as;
    memcpy(mh_in + 66, auth_PID, 32);
    mh_in[98] = ts_2;
    H(mh_in, 99, mh_mask);
    for (int i = 0; i < 32; i++) m_new[i] = m_H[i] ^ mh_mask[i];

    uint8_t kd_in[33];
    kd_in[0] = R_d;
    memcpy(kd_in + 1, m_new, 32);
    H(kd_in, 33, k_gw_d);

    /* Commit new state */
    memcpy(m_d, m_new, 32);
    uint8_t pid_buf[33];
    pid_buf[0] = id_d;
    memcpy(pid_buf + 1, m_new, 32);
    H(pid_buf, 33, PID);

    last_ts2 = ts_2;
    ts_1++;
    last_auth_ok = 1;

    printf("DESYNC_LOG|Node %u|Round %u|Auth OK|New PID=%02x%02x%02x|SYNCED\n",
           id_d, auth_round, PID[0], PID[1], PID[2]);
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
 * Inline macros: prepare auth payload and data payload
 * (COAP_BLOCKING_REQUEST must be called directly inside PROCESS_THREAD)
 * ========================================================================== */
static uint8_t auth_payload[65];
static uint8_t data_payload[48];

static void prepare_auth(void)
{
    uint8_t R_d = h_d;
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

    memcpy(auth_payload,      auth_PID, 32);
    memcpy(auth_payload + 32, y_asd,   32);
    auth_payload[64] = ts_1;

    printf("DESYNC_LOG|Node %u|Round %u|Sending auth|PID=%02x%02x%02x|ts_1=%u\n",
           id_d, auth_round, auth_PID[0], auth_PID[1], auth_PID[2], ts_1);
}

static void prepare_data(void)
{
    uint8_t sensor[16];
    memset(sensor, 0, 16);
    sensor[0] = 9;
    uint8_t K_AES[16];
    memcpy(K_AES, k_gw_d, 16);
    aes_enc(K_AES, sensor, 1);
    memcpy(data_payload,      PID,    32);
    memcpy(data_payload + 32, sensor, 16);
}

/* ==========================================================================
 * Main process
 * ========================================================================== */
PROCESS(device_node, "Device Node");
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
             * ENROLLMENT
             * ============================================================ */
            if (reg == 0) {
                printf("DESYNC_LOG|Node %u|=== ENROLLMENT START ===\n", id_d);

                /* Reg-0 */
                {
                    uint8_t p0[16];
                    memset(p0, 0, 16);
                    p0[0] = id_d;
                    aes_enc(K_AS_D, p0, 1);

                    coap_init_message(request, COAP_TYPE_CON, COAP_GET, 0);
                    coap_set_header_uri_path(request, "test/reg");
                    coap_set_payload(request, p0, 16);
                    COAP_BLOCKING_REQUEST(&ep_as, request, client_reg_handler);
                }

                /* Reg-1 */
                {
                    uint8_t R_d = puf_response(c_d);
                    h_d = R_d;

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
                    COAP_BLOCKING_REQUEST(&ep_as, request, client_reg1_handler);
                }

                /* Compute initial PID */
                {
                    uint8_t pid_buf[33];
                    pid_buf[0] = id_d;
                    memcpy(pid_buf + 1, m_d, 32);
                    H(pid_buf, 33, PID);
                }

                reg = 1;
                printf("DESYNC_LOG|Node %u|=== ENROLLMENT COMPLETE ===|Initial PID=%02x%02x%02x\n",
                       id_d, PID[0], PID[1], PID[2]);

            /* ============================================================
             * ROUND 1: Normal authentication (establishes sync)
             * ============================================================ */
            } else if (auth_round == 0) {
                auth_round = 1;
                printf("\nDESYNC_LOG|Node %u|========================================\n", id_d);
                printf("DESYNC_LOG|Node %u|Round 1|NORMAL AUTH (establishing sync)\n", id_d);
                printf("DESYNC_LOG|Node %u|========================================\n", id_d);

                prepare_auth();
                coap_init_message(request, COAP_TYPE_CON, COAP_POST, 2);
                coap_set_header_uri_path(request, "test/auth");
                coap_set_payload(request, auth_payload, 65);
                COAP_BLOCKING_REQUEST(&ep_as, request, client_auth_handler);

                if (last_auth_ok) {
                    prepare_data();
                    coap_init_message(request, COAP_TYPE_CON, COAP_POST, 3);
                    coap_set_header_uri_path(request, "test/data");
                    coap_set_payload(request, data_payload, 48);
                    COAP_BLOCKING_REQUEST(&ep_gw, request, client_data_handler);
                    printf("DESYNC_LOG|Node %u|Round 1|RESULT: SUCCESS — both sides synced\n", id_d);
                }

            /* ============================================================
             * ROUND 2: Auth succeeds on AS side, but device DROPS reply
             * → Causes desynchronization
             * ============================================================ */
            } else if (auth_round == 1) {
                auth_round = 2;
                printf("\nDESYNC_LOG|Node %u|========================================\n", id_d);
                printf("DESYNC_LOG|Node %u|Round 2|DESYNC TRIGGER — will drop AS reply\n", id_d);
                printf("DESYNC_LOG|Node %u|========================================\n", id_d);

                simulate_drop = 1;
                prepare_auth();
                coap_init_message(request, COAP_TYPE_CON, COAP_POST, 2);
                coap_set_header_uri_path(request, "test/auth");
                coap_set_payload(request, auth_payload, 65);
                COAP_BLOCKING_REQUEST(&ep_as, request, client_auth_handler);

                printf("DESYNC_LOG|Node %u|Round 2|RESULT: DESYNCHRONIZED\n", id_d);
                printf("DESYNC_LOG|Node %u|Round 2|Device state: PID=%02x%02x%02x (OLD), ts_1=%u\n",
                       id_d, PID[0], PID[1], PID[2], ts_1);

            /* ============================================================
             * ROUND 3: Device retries with OLD PID → AS uses PID_old
             * → Desync recovery via dual-state storage
             * ============================================================ */
            } else if (auth_round == 2) {
                auth_round = 3;
                printf("\nDESYNC_LOG|Node %u|========================================\n", id_d);
                printf("DESYNC_LOG|Node %u|Round 3|DESYNC RECOVERY — retrying with old PID\n", id_d);
                printf("DESYNC_LOG|Node %u|Round 3|Device using PID=%02x%02x%02x (same as before drop)\n",
                       id_d, PID[0], PID[1], PID[2]);
                printf("DESYNC_LOG|Node %u|========================================\n", id_d);

                prepare_auth();
                coap_init_message(request, COAP_TYPE_CON, COAP_POST, 2);
                coap_set_header_uri_path(request, "test/auth");
                coap_set_payload(request, auth_payload, 65);
                COAP_BLOCKING_REQUEST(&ep_as, request, client_auth_handler);

                if (last_auth_ok) {
                    prepare_data();
                    coap_init_message(request, COAP_TYPE_CON, COAP_POST, 3);
                    coap_set_header_uri_path(request, "test/data");
                    coap_set_payload(request, data_payload, 48);
                    COAP_BLOCKING_REQUEST(&ep_gw, request, client_data_handler);
                    printf("DESYNC_LOG|Node %u|Round 3|RESULT: RECOVERY SUCCESSFUL — re-synced via dual-state\n", id_d);
                } else {
                    printf("DESYNC_LOG|Node %u|Round 3|RESULT: Recovery failed\n", id_d);
                }

            /* ============================================================
             * ROUND 4: Confirm normal operation post-recovery
             * ============================================================ */
            } else if (auth_round == 3) {
                auth_round = 4;
                printf("\nDESYNC_LOG|Node %u|========================================\n", id_d);
                printf("DESYNC_LOG|Node %u|Round 4|POST-RECOVERY NORMAL AUTH\n", id_d);
                printf("DESYNC_LOG|Node %u|========================================\n", id_d);

                prepare_auth();
                coap_init_message(request, COAP_TYPE_CON, COAP_POST, 2);
                coap_set_header_uri_path(request, "test/auth");
                coap_set_payload(request, auth_payload, 65);
                COAP_BLOCKING_REQUEST(&ep_as, request, client_auth_handler);

                if (last_auth_ok) {
                    prepare_data();
                    coap_init_message(request, COAP_TYPE_CON, COAP_POST, 3);
                    coap_set_header_uri_path(request, "test/data");
                    coap_set_payload(request, data_payload, 48);
                    COAP_BLOCKING_REQUEST(&ep_gw, request, client_data_handler);
                    printf("DESYNC_LOG|Node %u|Round 4|RESULT: SUCCESS — system fully recovered\n", id_d);
                }

                printf("\nDESYNC_LOG|Node %u|=== DESYNC DEMONSTRATION COMPLETE ===\n", id_d);
            }

            etimer_reset(&et);
        }
    }

    PROCESS_END();
}
