/* ==========================================================================
 * as-node.c  —  Authentication Server (Base Scheme, unified build)
 *
 * Nodes 2-80.  Handles device registration (2-step) and authentication.
 * After auth, forwards auth token to GW (node 1) via CoAP POST.
 * ========================================================================== */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "contiki.h"
#include "coap-engine.h"
#include "coap-blocking-api.h"
#include "aes.h"
#include "sha256.h"
#include "net/ipv6/uip-ds6.h"
#include "net/routing/routing.h"
#include "sys/node-id.h"
#include "random.h"
#include "project-conf.h"
#include "sys/energest.h"

/* --------------------------------------------------------------------------
 * Shared keys
 * -------------------------------------------------------------------------- */
static const uint8_t k_as_d[16] = {
    0x67,0x61,0x74,0x73,0x20,0x6D,0x79,0x20,
    0x4B,0x75,0x6F,0x67,0x20,0x46,0x75,0x00
};
static const uint8_t k_gw_as[16] = {
    0x67,0x62,0x74,0x73,0x20,0x6D,0x79,0x20,
    0x4B,0x75,0x6F,0x67,0x20,0x46,0x75,0x00
};

/* --------------------------------------------------------------------------
 * Per-device state at AS
 * -------------------------------------------------------------------------- */
#define MAX_CLIENTS 12

typedef struct {
    uint8_t ID_d;
    uint8_t y_d;
    uint8_t M_d[32];
    uint8_t c_as_d;
    uint8_t PHI_d;
    uint8_t h_as_d;
} as_client_t;

static as_client_t cl[MAX_CLIENTS];
static int reg_count = 0;

/* Accumulator */
static uint8_t T_Acc[32];

/* Auth token queue */
#define TOKEN_LEN     48
#define MAX_TOKENS    12
static uint8_t auth_tokens[MAX_TOKENS][TOKEN_LEN];
static uint8_t token_count = 0;
static uint8_t sent_index  = 0;

static uint8_t c_d = 6;
static uint8_t n_d = 2;

/* --------------------------------------------------------------------------
 * GW endpoint for forwarding auth tokens
 * -------------------------------------------------------------------------- */
static coap_endpoint_t ep_gw;
static coap_message_t  request_fwd[1];
process_event_t event_send_token;

/* Forward declaration */
PROCESS_NAME(as_node);

/* --------------------------------------------------------------------------
 * Utility
 * -------------------------------------------------------------------------- */
static void H(const uint8_t *in, uint16_t len, uint8_t *out)
{
    SHA256_CTX ctx;
    uint8_t full[32];
    sha256_init(&ctx);
    sha256_update(&ctx, in, len);
    sha256_final(&ctx, full);
    memcpy(out, full, 32);
}

static uint8_t simulate_puf_response(uint8_t c)
{
    uint8_t response;
    uint8_t path1 = random_rand() ^ c;
    uint8_t path2 = random_rand() ^ c;
    response = (path1 > path2) ? 1 : 0;
    return response;
}

static void generate_helper(uint8_t response, uint8_t *helper, uint8_t *secret)
{
    *secret = 1;
    *helper = *secret & response;
}

static uint8_t regenerate_response(uint8_t challenge, uint8_t helper)
{
    uint8_t response;
    response = (helper == 0) ? (helper & challenge) : (helper || challenge);
    return response;
}

/* --------------------------------------------------------------------------
 * CoAP resource: /test/reg  —  Registration step 0  (GET)
 * Device sends AES(k_as_d, [ID_d, pad...]) → AS replies AES(k_as_d, [c_d, M_d])
 * -------------------------------------------------------------------------- */
static void res_reg_handler(coap_message_t *request, coap_message_t *response,
                            uint8_t *buffer, uint16_t preferred_size,
                            int32_t *offset)
{
    const uint8_t *chunk;
    int len = coap_get_payload(request, &chunk);
    if (len != 16) return;

    uint8_t payload[16];
    memcpy(payload, chunk, 16);
    struct AES_ctx ctx;
    AES_init_ctx(&ctx, k_as_d);
    AES_ECB_decrypt(&ctx, payload);

    uint8_t id_d = payload[0];
    uint8_t idx  = id_d % MAX_CLIENTS;

    if (cl[idx].ID_d == id_d || reg_count >= MAX_CLIENTS) {
        printf("AS %u: Device %u already registered or full\n", node_id, id_d);
        return;
    }

    reg_count++;
    cl[idx].ID_d   = id_d;
    cl[idx].M_d[0] = 5;

    /* Reply: [c_d, M_d[0]] encrypted */
    memset(payload, 0, 16);
    payload[0] = c_d;
    payload[1] = cl[idx].M_d[0];
    AES_init_ctx(&ctx, k_as_d);
    AES_ECB_encrypt(&ctx, payload);

    coap_set_payload(response, payload, 16);
    printf("AS %u: Reg step-0 for device %u done\n", node_id, id_d);
}

RESOURCE(res_reg,
         "title=\"reg\";rt=\"Text\"",
         res_reg_handler, NULL, NULL, NULL);

/* --------------------------------------------------------------------------
 * CoAP resource: /test/reg1  —  Registration step 1  (GET)
 * Device sends AES(k_as_d, [ID_d, y_d, R_d, c_as_d]) → AS replies "Registered"
 * -------------------------------------------------------------------------- */
static void res_reg1_handler(coap_message_t *request, coap_message_t *response,
                             uint8_t *buffer, uint16_t preferred_size,
                             int32_t *offset)
{
    const uint8_t *chunk;
    int len = coap_get_payload(request, &chunk);
    if (len != 16) return;

    uint8_t payload[16];
    memcpy(payload, chunk, 16);
    struct AES_ctx ctx;
    AES_init_ctx(&ctx, k_as_d);
    AES_ECB_decrypt(&ctx, payload);

    uint8_t id_d = payload[0];
    uint8_t idx  = id_d % MAX_CLIENTS;
    cl[idx].y_d    = payload[1];
    uint8_t R_d    = payload[2];
    cl[idx].c_as_d = payload[3];

    /* PUF on AS side */
    uint8_t R_as_d = simulate_puf_response(cl[idx].c_as_d);
    uint8_t secret;
    generate_helper(R_as_d, &cl[idx].h_as_d, &secret);
    cl[idx].PHI_d = R_d ^ R_as_d;

    /* Accumulator: T_Acc = T_Acc AND H(y_d) */
    uint8_t Y_d_H[32];
    H(&cl[idx].y_d, 1, Y_d_H);
    for (int i = 0; i < 32; i++)
        T_Acc[i] = T_Acc[i] & Y_d_H[i];

    char *msg = "Registered";
    coap_set_payload(response, (uint8_t *)msg, strlen(msg));
    printf("AS %u: Reg step-1 for device %u done\n", node_id, id_d);
}

RESOURCE(res_reg1,
         "title=\"reg1\";rt=\"Text\"",
         res_reg1_handler, NULL, NULL, NULL);

/* --------------------------------------------------------------------------
 * CoAP resource: /test/auth  —  Authentication + session key  (POST)
 * Device sends [ID_d, Y_d_H(32), ts_1] = 34B
 * AS verifies, computes session key, replies [AS_id, masked_key(32), ts_2] = 34B
 * Then forwards auth token to GW.
 * -------------------------------------------------------------------------- */
static void res_auth_handler(coap_message_t *request, coap_message_t *response,
                             uint8_t *buffer, uint16_t preferred_size,
                             int32_t *offset)
{
    const uint8_t *chunk;
    int len = coap_get_payload(request, &chunk);
    if (len < 34) return;

    uint8_t hpayload[34];
    memcpy(hpayload, chunk, 34);

    uint8_t id_d = hpayload[0];
    uint8_t ts_1 = hpayload[33];
    uint8_t idx  = id_d % MAX_CLIENTS;

    if (cl[idx].ID_d != id_d) {
        printf("AS %u: Device %u not registered\n", node_id, id_d);
        return;
    }

    uint8_t Y_d_H[32];
    memcpy(Y_d_H, hpayload + 1, 32);

    /* Regenerate R_d from PHI_d */
    uint8_t R_as_d = regenerate_response(cl[idx].c_as_d, cl[idx].h_as_d);
    uint8_t R_d = cl[idx].PHI_d ^ R_as_d;

    /* Compute hash: SHA256([R_d, M_d(32), id_d, ts_1]) */
    uint8_t data_c[35];
    memset(data_c, 0, 35);
    data_c[0] = R_d;
    memcpy(data_c + 1, cl[idx].M_d, 32);
    data_c[33] = id_d;
    data_c[34] = ts_1;

    uint8_t hash_dash[32];
    H(data_c, 35, hash_dash);

    /* Unmask Y_d_H */
    for (int i = 0; i < 32; i++)
        Y_d_H[i] = Y_d_H[i] ^ hash_dash[i];

    /* Verify accumulator */
    for (int i = 0; i < 32; i++) {
        if (T_Acc[i] != (T_Acc[i] & Y_d_H[i])) {
            printf("AS %u: Auth failed for device %u (accumulator)\n", node_id, id_d);
            return;
        }
    }

    /* Compute session key mask */
    uint8_t ts_2 = 1;
    uint8_t data[68];
    memset(data, 0, 68);
    memcpy(data, Y_d_H, 32);
    memcpy(data + 32, cl[idx].M_d, 32);
    data[64] = R_d;
    data[65] = node_id;
    data[66] = id_d;
    data[67] = ts_2;

    H(data, 68, hash_dash);

    /* n = SHA256(n_d) */
    uint8_t n[32];
    H(&n_d, 1, n);

    /* XOR mask with n → session key response */
    for (int i = 0; i < 32; i++)
        hash_dash[i] = hash_dash[i] ^ n[i];

    /* Build response: [AS_id, masked_key(32), ts_2] = 34B */
    hpayload[0] = node_id;
    memcpy(hpayload + 1, hash_dash, 32);
    hpayload[33] = ts_2;
    coap_set_payload(response, hpayload, 34);

    printf("AS %u: Auth OK for device %u\n", node_id, id_d);

    /* Update M_d for future rounds */
    for (int i = 0; i < 32; i++)
        cl[idx].M_d[i] = n[i];

    /* Derive k_gw_d = SHA256([R_d, updated_M_d]) */
    uint8_t k_gw_d[33];
    k_gw_d[0] = R_d;
    memcpy(k_gw_d + 1, cl[idx].M_d, 32);
    uint8_t sk_hash[32];
    H(k_gw_d, 33, sk_hash);

    /* Build auth token: auth_id_ts(16) + key1(16) + key2(16) = 48B */
    uint8_t auth_id_ts[16];
    memset(auth_id_ts, 0, 16);
    auth_id_ts[0] = id_d;
    auth_id_ts[1] = node_id;
    auth_id_ts[2] = (uint8_t)(clock_time() / CLOCK_SECOND);

    struct AES_ctx ctx;
    AES_init_ctx(&ctx, k_gw_as);
    AES_ECB_encrypt(&ctx, auth_id_ts);

    uint8_t key1[16], key2[16];
    memcpy(key1, sk_hash, 16);
    memcpy(key2, sk_hash + 16, 16);
    AES_init_ctx(&ctx, k_gw_as);
    AES_ECB_encrypt(&ctx, key1);
    AES_init_ctx(&ctx, k_gw_as);
    AES_ECB_encrypt(&ctx, key2);

    uint8_t token[TOKEN_LEN];
    memcpy(token,      auth_id_ts, 16);
    memcpy(token + 16, key1,       16);
    memcpy(token + 32, key2,       16);

    /* Queue token for forwarding */
    if (token_count < MAX_TOKENS) {
        if (token_count == sent_index) {
            sent_index = 0;
            token_count = 0;
        }
        memcpy(auth_tokens[token_count], token, TOKEN_LEN);
        token_count = (token_count + 1) % MAX_TOKENS;
        process_post(&as_node, event_send_token, NULL);
    }
}

RESOURCE(res_auth,
         "title=\"auth\";rt=\"Text\"",
         NULL, res_auth_handler, NULL, NULL);

/* --------------------------------------------------------------------------
 * Token-forwarding callback
 * -------------------------------------------------------------------------- */
static void gw_token_callback(coap_message_t *resp)
{
    if (!resp) {
        printf("AS %u: Token delivery to GW failed\n", node_id);
        return;
    }
    printf("AS %u: Token delivered to GW\n", node_id);
    sent_index = (sent_index + 1) % MAX_TOKENS;
}

/* --------------------------------------------------------------------------
 * Main process
 * -------------------------------------------------------------------------- */
PROCESS(as_node, "AS Node");
AUTOSTART_PROCESSES(&as_node);

PROCESS_THREAD(as_node, ev, data)
{
    PROCESS_BEGIN();

    /* Initialize accumulator to all-ones */
    memset(T_Acc, 0xFF, 32);

    coap_engine_init();
    coap_activate_resource(&res_reg,  "test/reg");
    coap_activate_resource(&res_reg1, "test/reg1");
    coap_activate_resource(&res_auth, "test/auth");

    /* Set up GW endpoint (node 1) */
    uip_ipaddr_t gw_addr;
    uint8_t gw_id = (uint8_t)GW_NODE_ID;
    uip_ip6addr_u8(&gw_addr, 0xfd,0,0,0,0,0,0,0,
                   0x02,gw_id,0,gw_id,0,gw_id,0,gw_id);
    uip_ipaddr_copy(&ep_gw.ipaddr, &gw_addr);
    ep_gw.port = UIP_HTONS(COAP_DEFAULT_PORT);

    event_send_token = process_alloc_event();

    printf("AS node %u started\n", node_id);

    while (1) {
        PROCESS_WAIT_EVENT_UNTIL(ev == event_send_token);

        if (sent_index < token_count) {
            uint8_t fwd_payload[TOKEN_LEN];
            memcpy(fwd_payload, auth_tokens[sent_index], TOKEN_LEN);

            coap_init_message(request_fwd, COAP_TYPE_CON, COAP_GET, coap_get_mid());
            coap_set_header_uri_path(request_fwd, "test/auth_token");
            coap_set_payload(request_fwd, fwd_payload, TOKEN_LEN);
            COAP_BLOCKING_REQUEST(&ep_gw, request_fwd, gw_token_callback);

            if (sent_index < token_count)
                process_post(&as_node, event_send_token, NULL);
        }
    }

    PROCESS_END();
}
