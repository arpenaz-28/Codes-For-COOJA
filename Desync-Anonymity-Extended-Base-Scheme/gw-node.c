/* ==========================================================================
 * gw-node.c  —  Gateway Node (Desync Demonstration)
 *
 * RPL root + CoAP server. Receives auth tokens from AS and data from devices.
 * Minimal changes from the main scheme — GW is not directly involved in
 * desync recovery; it just stores/looks up sessions by PID.
 * ========================================================================== */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include "contiki.h"
#include "coap-engine.h"
#include "aes.h"
#include "net/routing/routing.h"
#include "net/netstack.h"
#include "sys/node-id.h"
#include "project-conf.h"

/* Shared key with AS */
static const uint8_t K_GW_AS[16] = {
    0x67,0x62,0x74,0x73,0x20,0x6D,0x79,0x20,
    0x4B,0x75,0x6F,0x67,0x20,0x46,0x75,0x00
};

/* Session table */
#define MAX_SESSIONS 10

typedef struct {
    uint8_t PID[32];
    uint8_t ID_d;
    uint8_t ID_as;
    uint8_t K_GW_D[32];
    uint8_t ts_auth;
    uint8_t valid;
} gw_session_t;

static gw_session_t sessions[MAX_SESSIONS];

static gw_session_t *find_by_pid(const uint8_t *pid)
{
    for (int i = 0; i < MAX_SESSIONS; i++) {
        if (sessions[i].valid && memcmp(sessions[i].PID, pid, 32) == 0)
            return &sessions[i];
    }
    return NULL;
}

static gw_session_t *alloc_session(void)
{
    for (int i = 0; i < MAX_SESSIONS; i++) {
        if (!sessions[i].valid) return &sessions[i];
    }
    return &sessions[0];
}

static void aes_dec(const uint8_t *key, uint8_t *buf, uint8_t n)
{
    struct AES_ctx ctx;
    for (uint8_t i = 0; i < n; i++) {
        AES_init_ctx(&ctx, key);
        AES_ECB_decrypt(&ctx, buf + i * 16);
    }
}

static int ts_fresh(uint8_t recv_ts)
{
    uint8_t now  = (uint8_t)(clock_time() / CLOCK_SECOND);
    int     diff = ((int)now - (int)recv_ts + 256) % 256;
    return (diff < FRESHNESS_WINDOW);
}

/* ==========================================================================
 * POST /test/auth_token  —  81 B from AS
 * ========================================================================== */
static void res_authtoken_handler(coap_message_t *req, coap_message_t *resp,
                                  uint8_t *buf, uint16_t ps, int32_t *off)
{
    const uint8_t *chunk;
    if (coap_get_payload(req, &chunk) != 81) return;

    uint8_t new_PID[32];
    uint8_t id_as_plain;
    uint8_t enc_tok[48];

    memcpy(new_PID, chunk, 32);
    id_as_plain = chunk[32];
    memcpy(enc_tok, chunk + 33, 48);

    aes_dec(K_GW_AS, enc_tok, 3);

    uint8_t id_d    = enc_tok[0];
    uint8_t id_as   = enc_tok[1];
    uint8_t ts_auth = enc_tok[2];
    uint8_t K_GW_D[32];
    memcpy(K_GW_D,      enc_tok + 16, 16);
    memcpy(K_GW_D + 16, enc_tok + 32, 16);

    if (id_as != id_as_plain) {
        printf("DESYNC_LOG|GW|Token rejected — ID_AS mismatch\n");
        return;
    }

    if (!ts_fresh(ts_auth)) {
        printf("DESYNC_LOG|GW|Token rejected — stale for device %u\n", id_d);
        return;
    }

    gw_session_t *sess = find_by_pid(new_PID);
    if (!sess) sess = alloc_session();

    memcpy(sess->PID, new_PID, 32);
    sess->ID_d    = id_d;
    sess->ID_as   = id_as;
    sess->ts_auth = ts_auth;
    sess->valid   = 1;
    memcpy(sess->K_GW_D, K_GW_D, 32);

    printf("DESYNC_LOG|GW|Token stored for device %u|PID=%02x%02x%02x\n",
           id_d, new_PID[0], new_PID[1], new_PID[2]);

    const char *msg = "OK";
    coap_set_payload(resp, (const uint8_t *)msg, strlen(msg));
}

/* ==========================================================================
 * POST /test/data  —  48 B from device
 * ========================================================================== */
static void res_data_handler(coap_message_t *req, coap_message_t *resp,
                             uint8_t *buf, uint16_t ps, int32_t *off)
{
    const uint8_t *chunk;
    if (coap_get_payload(req, &chunk) < 48) return;

    uint8_t recv_PID[32], enc_data[16];
    memcpy(recv_PID, chunk,      32);
    memcpy(enc_data, chunk + 32, 16);

    gw_session_t *sess = find_by_pid(recv_PID);
    if (!sess) {
        printf("DESYNC_LOG|GW|Data rejected — PID %02x%02x%02x not found\n",
               recv_PID[0], recv_PID[1], recv_PID[2]);
        return;
    }

    struct AES_ctx ctx;
    uint8_t K_AES[16];
    memcpy(K_AES, sess->K_GW_D, 16);
    AES_init_ctx(&ctx, K_AES);
    AES_ECB_decrypt(&ctx, enc_data);

    printf("DESYNC_LOG|GW|Data OK|device %u|val=%u|PID=%02x%02x%02x\n",
           sess->ID_d, enc_data[0], recv_PID[0], recv_PID[1], recv_PID[2]);

    uint8_t reply[1] = {0};
    coap_set_payload(resp, reply, 1);
}

RESOURCE(res_authtoken, "title=\"AuthToken\"",
         NULL, res_authtoken_handler, NULL, NULL);
RESOURCE(res_data, "title=\"Data\"",
         NULL, res_data_handler, NULL, NULL);

/* ==========================================================================
 * Main process
 * ========================================================================== */
PROCESS(gw_node, "Gateway Node");
AUTOSTART_PROCESSES(&gw_node);

PROCESS_THREAD(gw_node, ev, data)
{
    PROCESS_BEGIN();

    memset(sessions, 0, sizeof(sessions));
    NETSTACK_ROUTING.root_start();
    coap_engine_init();

    coap_activate_resource(&res_authtoken, "test/auth_token");
    coap_activate_resource(&res_data,      "test/data");

    printf("DESYNC_LOG|GW %u|Started (RPL root + CoAP server)\n", node_id);

    while (1) {
        PROCESS_WAIT_EVENT();
    }

    PROCESS_END();
}
