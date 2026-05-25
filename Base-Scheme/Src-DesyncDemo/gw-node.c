/* ==========================================================================
 * gw-node.c  —  Gateway (Base Scheme, unified build)
 *
 * Node 1 = RPL root, receives auth tokens from AS, handles key-update
 * and data reception from devices.
 * ========================================================================== */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "contiki.h"
#include "coap-engine.h"
#include "aes.h"
#include "sha256.h"
#include "sys/energest.h"
#include "net/routing/routing.h"
#include "net/netstack.h"
#include "net/ipv6/uip-ds6.h"
#include "sys/node-id.h"
#include "project-conf.h"

/* --------------------------------------------------------------------------
 * Shared key between AS and GW
 * -------------------------------------------------------------------------- */
static const uint8_t k_gw_as[16] = {
    0x67,0x62,0x74,0x73,0x20,0x6D,0x79,0x20,
    0x4B,0x75,0x6F,0x67,0x20,0x46,0x75,0x00
};

/* --------------------------------------------------------------------------
 * Per-device state at gateway
 * -------------------------------------------------------------------------- */
#define MAX_CLIENTS 25

typedef struct {
    uint8_t id_d;
    uint8_t id_as;
    uint8_t k_gw_d[32];
    uint8_t ts_auth;
} gw_client_t;

static gw_client_t clients[MAX_CLIENTS];

static uint8_t g = 5, p = 23, b = 6;

/* --------------------------------------------------------------------------
 * CoAP resource: /test/auth_token  — receive auth token from AS
 * -------------------------------------------------------------------------- */
static void res_authtoken_handler(coap_message_t *request, coap_message_t *response,
                                  uint8_t *buffer, uint16_t preferred_size,
                                  int32_t *offset)
{
    const uint8_t *chunk;
    int len = coap_get_payload(request, &chunk);
    if (len != 48) {
        printf("GW: stale auth_token packet (len=%d)\n", len);
        return;
    }

    /* Decrypt auth_id_ts block */
    uint8_t auth_id_ts[16];
    memcpy(auth_id_ts, chunk, 16);
    struct AES_ctx ctx;
    AES_init_ctx(&ctx, k_gw_as);
    AES_ECB_decrypt(&ctx, auth_id_ts);

    uint8_t id_d = auth_id_ts[0];
    uint8_t idx  = id_d % MAX_CLIENTS;
    clients[idx].id_d     = id_d;
    clients[idx].id_as    = auth_id_ts[1];
    clients[idx].ts_auth  = auth_id_ts[2];

    /* Decrypt key1 and key2 */
    uint8_t key1[16], key2[16];
    memcpy(key1, chunk + 16, 16);
    memcpy(key2, chunk + 32, 16);
    AES_init_ctx(&ctx, k_gw_as);
    AES_ECB_decrypt(&ctx, key1);
    AES_init_ctx(&ctx, k_gw_as);
    AES_ECB_decrypt(&ctx, key2);

    memcpy(clients[idx].k_gw_d,      key1, 16);
    memcpy(clients[idx].k_gw_d + 16, key2, 16);

    printf("GW: Auth token received for device %u\n", id_d);

    char *msg = "Received";
    coap_set_payload(response, (uint8_t *)msg, strlen(msg));
}

RESOURCE(res_authtoken,
         "title=\"auth_token\";rt=\"Text\"",
         res_authtoken_handler, NULL, NULL, NULL);

/* --------------------------------------------------------------------------
 * CoAP resource: /test/keyupdate — DH key exchange with device
 * -------------------------------------------------------------------------- */
static void res_keyupdate_handler(coap_message_t *request, coap_message_t *response,
                                  uint8_t *buffer, uint16_t preferred_size,
                                  int32_t *offset)
{
    const uint8_t *chunk;
    int len = coap_get_payload(request, &chunk);
    if (len != 17) {
        printf("GW: Invalid keyupdate payload (len=%d)\n", len);
        return;
    }

    uint8_t id_d = chunk[0];
    uint8_t idx  = id_d % MAX_CLIENTS;

    uint8_t payload[16];
    memcpy(payload, chunk + 1, 16);

    /* Decrypt with first 16 bytes of k_gw_d */
    uint8_t K[16];
    memcpy(K, clients[idx].k_gw_d, 16);
    struct AES_ctx ctx;
    AES_init_ctx(&ctx, K);
    AES_ECB_decrypt(&ctx, payload);

    uint8_t alpha = payload[0];
    /* Update session key: k_gw_d[0] = (alpha XOR b) mod p */
    clients[idx].k_gw_d[0] = (alpha ^ b) % p;
    for (int i = 1; i < 32; i++)
        clients[idx].k_gw_d[i] = 0;

    /* Reply with beta = (g XOR b) mod p, encrypted */
    uint8_t beta = (g ^ b) % p;
    memset(payload, 0, 16);
    payload[0] = beta;
    AES_init_ctx(&ctx, K);
    AES_ECB_encrypt(&ctx, payload);

    coap_set_payload(response, payload, 16);
    printf("GW: Key update done for device %u\n", id_d);
}

RESOURCE(res_keyupdate,
         "title=\"keyupdate\";rt=\"Text\"",
         res_keyupdate_handler, NULL, NULL, NULL);

/* --------------------------------------------------------------------------
 * CoAP resource: /test/data — receive encrypted data from device
 * -------------------------------------------------------------------------- */
static void res_data_handler(coap_message_t *request, coap_message_t *response,
                             uint8_t *buffer, uint16_t preferred_size,
                             int32_t *offset)
{
    const uint8_t *chunk;
    int len = coap_get_payload(request, &chunk);
    if (len < 17) {
        printf("GW: Invalid data payload\n");
        return;
    }

    uint8_t id_d = chunk[0];
    uint8_t idx  = id_d % MAX_CLIENTS;

    uint8_t payload[16];
    memcpy(payload, chunk + 1, 16);

    uint8_t K[16];
    memcpy(K, clients[idx].k_gw_d, 16);
    struct AES_ctx ctx;
    AES_init_ctx(&ctx, K);
    AES_ECB_decrypt(&ctx, payload);

    printf("GW: Data from device %u = %d\n", id_d, payload[0]);

    uint8_t ack = 0;
    coap_set_payload(response, &ack, 1);
}

RESOURCE(res_data,
         "title=\"data\";rt=\"Text\"",
         res_data_handler, NULL, NULL, NULL);

/* --------------------------------------------------------------------------
 * Main process
 * -------------------------------------------------------------------------- */
PROCESS(gw_node, "Gateway Node");
AUTOSTART_PROCESSES(&gw_node);

PROCESS_THREAD(gw_node, ev, data)
{
    PROCESS_BEGIN();

    NETSTACK_ROUTING.root_start();

    PROCESS_PAUSE();

    coap_engine_init();
    coap_activate_resource(&res_authtoken, "test/auth_token");
    coap_activate_resource(&res_keyupdate, "test/keyupdate");
    coap_activate_resource(&res_data,      "test/data");

    printf("GW node %u started (RPL root)\n", node_id);

    while (1) {
        PROCESS_WAIT_EVENT();
    }

    PROCESS_END();
}
