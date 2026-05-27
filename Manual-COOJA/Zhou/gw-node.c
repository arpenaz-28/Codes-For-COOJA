/* ==========================================================================
 * gw-node.c  —  RPL Root / Gateway Router for Zhou et al. scheme
 *
 * Same role as in existing schemes: RPL root + CoAP server for receiving
 * auth tokens from the Medical Gateway server and encrypted data from Users.
 *
 * TOKEN from GW-server (POST /test/auth_token): 81 bytes
 *   DIDi_new(32) | id_gw(1) | enc_A(16) | enc_B(16) | enc_C(16)
 *
 * DATA from User (POST /test/data): 48 bytes
 *   DIDi(32) | AES_enc(SK[0..15], data(16))
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

/* Shared key with GW server (same as K_GW_RT in gw-server.c) */
static const uint8_t K_GW_RT[16] = {
    0x67,0x62,0x74,0x73,0x20,0x6D,0x79,0x20,
    0x4B,0x75,0x6F,0x67,0x20,0x46,0x75,0x00
};

/* Session table (indexed by slot, looked up by DIDi) */
#define MAX_SESSIONS  110

typedef struct {
    uint8_t  DIDi[32];     /* User pseudonym — external lookup key      */
    uint8_t  ID_d;         /* Real user ID (from decrypted token)       */
    uint8_t  ID_gw;        /* Which GW server authenticated this user   */
    uint8_t  K_GW_D[32];   /* 32-byte session key                       */
    uint8_t  ts_auth;      /* Token freshness timestamp                  */
    uint8_t  valid;        /* 1 = slot in use                           */
} gw_session_t;

static gw_session_t sessions[MAX_SESSIONS];

static gw_session_t *find_by_did(const uint8_t *did)
{
    for (int i = 0; i < MAX_SESSIONS; i++) {
        if (sessions[i].valid && memcmp(sessions[i].DIDi, did, 32) == 0)
            return &sessions[i];
    }
    return NULL;
}

static gw_session_t *alloc_session(void)
{
    for (int i = 0; i < MAX_SESSIONS; i++) {
        if (!sessions[i].valid) return &sessions[i];
    }
    printf("GW: Session table full — overwriting slot 0\n");
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
 * Receive auth token from GW server
 * POST /test/auth_token
 * Payload: DIDi_new(32) | ID_GW(1) | enc_A(16) | enc_B(16) | enc_C(16) = 81B
 * ========================================================================== */
static void res_authtoken_handler(coap_message_t *req, coap_message_t *resp,
                                   uint8_t *buf, uint16_t ps, int32_t *off)
{
    const uint8_t *chunk;
    if (coap_get_payload(req, &chunk) != 81) {
        printf("GW: Token wrong length\n");
        return;
    }

    uint8_t new_DIDi[32];
    uint8_t id_gw_plain;
    uint8_t enc_tok[48];

    memcpy(new_DIDi,  chunk,      32);
    id_gw_plain = chunk[32];
    memcpy(enc_tok,   chunk + 33, 48);

    aes_dec(K_GW_RT, enc_tok, 3);

    uint8_t id_d    = enc_tok[0];
    uint8_t id_gw   = enc_tok[1];
    uint8_t ts_auth = enc_tok[2];

    uint8_t K_GW_D[32];
    memcpy(K_GW_D,      enc_tok + 16, 16);
    memcpy(K_GW_D + 16, enc_tok + 32, 16);

    if (id_gw != id_gw_plain) {
        printf("GW: Token rejected — ID_GW mismatch\n");
        return;
    }

    if (!ts_fresh(ts_auth)) {
        printf("GW: Token rejected — stale ts_auth for user %u\n", id_d);
        return;
    }

    gw_session_t *sess = find_by_did(new_DIDi);
    if (!sess) sess = alloc_session();

    memcpy(sess->DIDi,   new_DIDi, 32);
    sess->ID_d    = id_d;
    sess->ID_gw   = id_gw;
    sess->ts_auth = ts_auth;
    sess->valid   = 1;
    memcpy(sess->K_GW_D, K_GW_D, 32);

    printf("GW: Auth token for user %u (via GW-S %u). DIDi: %02x%02x%02x\n",
           id_d, id_gw, new_DIDi[0], new_DIDi[1], new_DIDi[2]);

    const char *msg = "OK";
    coap_set_payload(resp, (const uint8_t *)msg, strlen(msg));
}

/* ==========================================================================
 * Receive encrypted sensor data from authenticated user
 * POST /test/data
 * Payload: DIDi(32) | AES_enc(SK[0..15], data(16)) = 48B
 * ========================================================================== */
static void res_data_handler(coap_message_t *req, coap_message_t *resp,
                              uint8_t *buf, uint16_t ps, int32_t *off)
{
    const uint8_t *chunk;
    if (coap_get_payload(req, &chunk) < 48) return;

    uint8_t recv_DIDi[32], enc_data[16];
    memcpy(recv_DIDi, chunk,      32);
    memcpy(enc_data,  chunk + 32, 16);

    gw_session_t *sess = find_by_did(recv_DIDi);
    if (!sess) {
        printf("GW: Rejected data — DIDi %02x%02x%02x not found\n",
               recv_DIDi[0], recv_DIDi[1], recv_DIDi[2]);
        return;
    }

    struct AES_ctx ctx;
    uint8_t K_AES[16];
    memcpy(K_AES, sess->K_GW_D, 16);
    AES_init_ctx(&ctx, K_AES);
    AES_ECB_decrypt(&ctx, enc_data);

    printf("GW: Decrypted data [%u] from DIDi %02x%02x%02x (user %u)\n",
           enc_data[0], recv_DIDi[0], recv_DIDi[1], recv_DIDi[2], sess->ID_d);

    uint8_t reply[1] = {0};
    coap_set_payload(resp, reply, 1);
}

RESOURCE(res_authtoken, "title=\"AuthToken\"",
         NULL, res_authtoken_handler, NULL, NULL);
RESOURCE(res_data,      "title=\"Data\"",
         NULL, res_data_handler,      NULL, NULL);

/* ==========================================================================
 * Main process
 * ========================================================================== */
PROCESS(gw_node, "Gateway Router");
AUTOSTART_PROCESSES(&gw_node);

PROCESS_THREAD(gw_node, ev, data)
{
    PROCESS_BEGIN();

    memset(sessions, 0, sizeof(sessions));

    NETSTACK_ROUTING.root_start();
    coap_engine_init();

    coap_activate_resource(&res_authtoken, "test/auth_token");
    coap_activate_resource(&res_data,      "test/data");

    printf("GW %u: Started (RPL root + CoAP server).\n", node_id);

    while (1) {
        PROCESS_WAIT_EVENT();
    }

    PROCESS_END();
}
