/* ==========================================================================
 * gw-node.c  —  Gateway Node  (DAuth / Das[1] Base Scheme)
 *
 * RPL root + CoAP server.
 *
 * In the base DAuth scheme devices are identified by their real ID_D
 * (no pseudonym), so the session table is keyed by ID_D rather than PID.
 *
 * TOKEN from AS (POST /test/auth_token): 50 bytes
 *   id_d(1) | id_as(1) | enc_A(16) | enc_B(16) | enc_C(16)
 *   enc_A = AES(K_GW_AS, [id_d(1) | id_as(1) | ts_auth(1) | pad(13)])
 *   enc_B = AES(K_GW_AS, K_GW_D[0:15])
 *   enc_C = AES(K_GW_AS, K_GW_D[16:31])
 *
 *   GW actions:
 *     Decrypt A, B, C.
 *     Verify id_d / id_as match cleartext header.
 *     Freshness-check ts_auth.
 *     Store session keyed by id_d: { K_GW_D[32], ts_auth }.
 *
 * DATA from device (GET /test/data): 17 bytes
 *   id_d(1) | AES_enc(K_GW_D[0:15], sensor_data(16))
 *
 *   GW actions:
 *     Look up session by id_d.
 *     Decrypt sensor data.
 *     Print plaintext value.
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

/* --------------------------------------------------------------------------
 * Shared key with AS
 * -------------------------------------------------------------------------- */
static const uint8_t K_GW_AS[16] = {
    0x67,0x62,0x74,0x73,0x20,0x6D,0x79,0x20,
    0x4B,0x75,0x6F,0x67,0x20,0x46,0x75,0x00
};

/* --------------------------------------------------------------------------
 * Session table  — keyed by id_d (plain device ID, no pseudonym)
 * -------------------------------------------------------------------------- */
#define MAX_SESSIONS  110

typedef struct {
    uint8_t  id_d;          /* real device ID — the lookup key */
    uint8_t  id_as;         /* which AS authenticated this device */
    uint8_t  K_GW_D[32];   /* 32-byte session key */
    uint8_t  ts_auth;       /* token freshness timestamp */
    uint8_t  valid;
} gw_session_t;

static gw_session_t sessions[MAX_SESSIONS];

static gw_session_t *find_by_id(uint8_t id_d)
{
    for (int i = 0; i < MAX_SESSIONS; i++) {
        if (sessions[i].valid && sessions[i].id_d == id_d)
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

/* --------------------------------------------------------------------------
 * AES-ECB decrypt n consecutive 16-byte blocks in-place
 * -------------------------------------------------------------------------- */
static void aes_dec(const uint8_t *key, uint8_t *buf, uint8_t n)
{
    struct AES_ctx ctx;
    for (uint8_t i = 0; i < n; i++) {
        AES_init_ctx(&ctx, key);
        AES_ECB_decrypt(&ctx, buf + i * 16);
    }
}

/* --------------------------------------------------------------------------
 * Clock-based freshness check (uint8 wraparound safe)
 * -------------------------------------------------------------------------- */
static int ts_fresh(uint8_t recv_ts)
{
    uint8_t now  = (uint8_t)(clock_time() / CLOCK_SECOND);
    int     diff = ((int)now - (int)recv_ts + 256) % 256;
    return (diff < FRESHNESS_WINDOW);
}

/* ==========================================================================
 * Resource: POST /test/auth_token
 * Payload: id_d(1) | id_as(1) | enc_A(16) | enc_B(16) | enc_C(16) = 50 B
 * ========================================================================== */
static void res_authtoken_handler(coap_message_t *req, coap_message_t *resp,
                                  uint8_t *buf, uint16_t ps, int32_t *off)
{
    const uint8_t *chunk;
    int plen = coap_get_payload(req, &chunk);
    if (plen < 50) {
        printf("GW: Token too short (%d B)\n", plen);
        return;
    }

    /* Header (cleartext) */
    uint8_t hdr_id_d  = chunk[0];
    uint8_t hdr_id_as = chunk[1];

    /* Decrypt three blocks */
    uint8_t enc_tok[48];
    memcpy(enc_tok, chunk + 2, 48);
    aes_dec(K_GW_AS, enc_tok, 3);

    /* Block A: id_d(1) | id_as(1) | ts_auth(1) | pad(13) */
    uint8_t dec_id_d  = enc_tok[0];
    uint8_t dec_id_as = enc_tok[1];
    uint8_t ts_auth   = enc_tok[2];

    /* Sanity: cleartext header must match decrypted interior */
    if (dec_id_d != hdr_id_d || dec_id_as != hdr_id_as) {
        printf("GW: Token rejected — ID mismatch\n");
        return;
    }

    /* Freshness check */
    if (!ts_fresh(ts_auth)) {
        printf("GW: Token rejected — stale ts_auth for device %u\n", dec_id_d);
        return;
    }

    /* K_GW_D: Block B (first 16 B) + Block C (next 16 B) */
    uint8_t K_GW_D[32];
    memcpy(K_GW_D,      enc_tok + 16, 16);
    memcpy(K_GW_D + 16, enc_tok + 32, 16);

    /* Store or refresh session keyed by id_d */
    gw_session_t *sess = find_by_id(dec_id_d);
    if (!sess) sess = alloc_session();

    sess->id_d    = dec_id_d;
    sess->id_as   = dec_id_as;
    sess->ts_auth = ts_auth;
    sess->valid   = 1;
    memcpy(sess->K_GW_D, K_GW_D, 32);

    printf("GW: Token stored for device %u (via AS %u).\n",
           dec_id_d, dec_id_as);

    const char *msg = "OK";
    coap_set_payload(resp, (const uint8_t *)msg, strlen(msg));
}

/* ==========================================================================
 * Resource: GET /test/data
 * Payload: id_d(1) | AES_enc(K_GW_D[0:15], sensor_data(16)) = 17 B
 * ========================================================================== */
static void res_data_handler(coap_message_t *req, coap_message_t *resp,
                             uint8_t *buf, uint16_t ps, int32_t *off)
{
    const uint8_t *chunk;
    int plen = coap_get_payload(req, &chunk);
    if (plen < 17) {
        printf("GW: Data packet too short (%d B)\n", plen);
        return;
    }

    uint8_t id_d     = chunk[0];
    uint8_t enc_data[16];
    memcpy(enc_data, chunk + 1, 16);

    /* Look up session by plain ID_D */
    gw_session_t *sess = find_by_id(id_d);
    if (!sess) {
        printf("GW: Rejected data — device %u not in session table\n", id_d);
        return;
    }

    /* Decrypt using first 16 bytes of K_GW_D */
    struct AES_ctx ctx;
    uint8_t K_AES[16];
    memcpy(K_AES, sess->K_GW_D, 16);
    AES_init_ctx(&ctx, K_AES);
    AES_ECB_decrypt(&ctx, enc_data);

    printf("GW: Data [%u] from device %u (via AS %u).\n",
           enc_data[0], id_d, sess->id_as);

    uint8_t reply[1] = {0};
    coap_set_payload(resp, reply, 1);
}

/* --------------------------------------------------------------------------
 * CoAP resource declarations
 * -------------------------------------------------------------------------- */
RESOURCE(res_authtoken, "title=\"AuthToken\"",
         NULL, res_authtoken_handler, NULL, NULL);
RESOURCE(res_data,      "title=\"Data\"",
         res_data_handler, NULL, NULL, NULL);

/* ==========================================================================
 * Main process
 * ========================================================================== */
PROCESS(gw_node, "DAuth Gateway Node");
AUTOSTART_PROCESSES(&gw_node);

PROCESS_THREAD(gw_node, ev, data)
{
    PROCESS_BEGIN();

    memset(sessions, 0, sizeof(sessions));

    /* Become the RPL root */
    NETSTACK_ROUTING.root_start();

    coap_engine_init();
    coap_activate_resource(&res_authtoken, "test/auth_token");
    coap_activate_resource(&res_data,      "test/data");

    printf("GW %u (DAuth Base Scheme): Started (RPL root + CoAP server).\n",
           node_id);
    printf("GW %u: Session table: %d slots × %u B each = %u B total\n",
           node_id, MAX_SESSIONS,
           (unsigned)sizeof(gw_session_t),
           (unsigned)sizeof(sessions));

    while (1) {
        PROCESS_WAIT_EVENT();
    }

    PROCESS_END();
}
