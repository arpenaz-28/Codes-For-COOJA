/* ==========================================================================
 * gw-node.c  —  Registration Authority (RA) + RPL Root  (LAAKA scheme)
 *
 * Node 1: RPL root + Registration Authority.
 * Handles device registration (LAAKA §4.2.2) and forwards credentials
 * to the assigned fog server via POST /test/dev_info.
 *
 * Resources:
 *   POST /test/reg — device registration
 *     Recv:  AES(K_RA_D, [IDd(1)|Ad(20)|pad(11)]) = 32 B
 *     Reply: AES(K_RA_D, [TIDd(20)|TIDf(20)|Af(20)|Bk(20)]) = 80 B
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
#include "net/routing/routing.h"
#include "net/netstack.h"
#include "net/ipv6/uip-ds6.h"
#include "sys/node-id.h"
#include "random.h"
#include "project-conf.h"

/* --------------------------------------------------------------------------
 * Protocol constants
 * -------------------------------------------------------------------------- */
#define HASH_LEN      20
#define RAND_LEN      20
#define REG_REQ_LEN   32
#define REG_REP_LEN   80
#define DEV_INFO_LEN  64
#define MAX_CLIENTS   110

/* --------------------------------------------------------------------------
 * Shared keys
 * -------------------------------------------------------------------------- */
static const uint8_t K_RA_D[16] = {
    0x67,0x61,0x74,0x73,0x20,0x6D,0x79,0x20,
    0x4B,0x75,0x6F,0x67,0x20,0x46,0x75,0x00
};
static const uint8_t K_RA_GW[16] = {
    0x67,0x62,0x74,0x73,0x20,0x6D,0x79,0x20,
    0x4B,0x75,0x6F,0x67,0x20,0x46,0x75,0x00
};
static const uint8_t K_MASTER[HASH_LEN] = {
    0xDE,0xAD,0xBE,0xEF,0xCA,0xFE,0xBA,0xBE,
    0x01,0x23,0x45,0x67,0x89,0xAB,0xCD,0xEF,
    0xFE,0xDC,0xBA,0x98
};

/* --------------------------------------------------------------------------
 * Pre-configured fog server identity
 * -------------------------------------------------------------------------- */
static const uint8_t r1_fog[HASH_LEN] = {
    0x11,0x22,0x33,0x44,0x55,0x66,0x77,0x88,
    0x99,0xAA,0xBB,0xCC,0xDD,0xEE,0xFF,0x01,
    0x02,0x03,0x04,0x05
};
static const uint8_t TIDf_const[HASH_LEN] = {
    0xA1,0xB2,0xC3,0xD4,0xE5,0xF6,0x07,0x18,
    0x29,0x3A,0x4B,0x5C,0x6D,0x7E,0x8F,0x90,
    0x01,0x12,0x23,0x34
};
static uint8_t Af[HASH_LEN];

/* --------------------------------------------------------------------------
 * Per-client state
 * -------------------------------------------------------------------------- */
typedef struct {
    uint8_t  IDd;
    uint8_t  TIDd[HASH_LEN];
    uint8_t  Ad[HASH_LEN];
    uint8_t  Bk[HASH_LEN];
    uint8_t  registered;
} ra_client_t;

static ra_client_t clients[MAX_CLIENTS];

/* --------------------------------------------------------------------------
 * Forward queue — stores dev_info + target fog node ID
 * -------------------------------------------------------------------------- */
typedef struct {
    uint8_t payload[DEV_INFO_LEN];
    uint8_t fog_id;
} fwd_entry_t;

static fwd_entry_t fwd_queue[MAX_CLIENTS];
static uint8_t fwd_head = 0, fwd_tail = 0;
#define FWD_EMPTY() (fwd_head == fwd_tail)
#define FWD_FULL()  (((fwd_tail + 1) % MAX_CLIENTS) == fwd_head)

/* --------------------------------------------------------------------------
 * Utility functions
 * -------------------------------------------------------------------------- */
static void H(const uint8_t *in, uint16_t len, uint8_t *out)
{
    SHA256_CTX ctx;
    uint8_t full[32];
    sha256_init(&ctx);
    sha256_update(&ctx, in, len);
    sha256_final(&ctx, full);
    memcpy(out, full, HASH_LEN);
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

/* Determine which fog server handles a given device */
static uint8_t get_fog_for_device(uint8_t id_d)
{
    return (id_d < FOG_SPLIT_ID) ? (uint8_t)FOG1_NODE_ID : (uint8_t)FOG2_NODE_ID;
}

/* --------------------------------------------------------------------------
 * CoAP forwarding to fog servers
 * -------------------------------------------------------------------------- */
static coap_endpoint_t ep_fog;
static coap_message_t  req_fw[1];
process_event_t ev_fwd;
PROCESS_NAME(gw_proc);

static void set_fog_endpoint(uint8_t fog_id)
{
    uip_ipaddr_t a;
    uip_ip6addr_u8(&a, 0xfd,0,0,0,0,0,0,0,
                   0x02,fog_id,0,fog_id,0,fog_id,0,fog_id);
    uip_ipaddr_copy(&ep_fog.ipaddr, &a);
    ep_fog.port = UIP_HTONS(COAP_DEFAULT_PORT);
}

/* ==========================================================================
 * Registration handler: POST /test/reg
 *
 * LAAKA Registration Phase (§4.2.2):
 *   - Device sends Ad = h(IDd || r2)
 *   - RA generates TIDd, computes Bk = h(Ad || Af || K)
 *   - RA sends (TIDd, TIDf, Af, Bk) to device
 *   - RA forwards (IDd, TIDd, Ad, Bk) to assigned fog server
 *
 * Recv:  AES(K_RA_D, [IDd(1)|Ad(20)|pad(11)]) = 32 B
 * Reply: AES(K_RA_D, [TIDd(20)|TIDf(20)|Af(20)|Bk(20)]) = 80 B
 * ========================================================================== */
static void res_reg_handler(coap_message_t *req, coap_message_t *resp,
                            uint8_t *buf, uint16_t ps, int32_t *off)
{
    const uint8_t *chunk;
    if (coap_get_payload(req, &chunk) != REG_REQ_LEN) return;

    uint8_t plain[REG_REQ_LEN];
    memcpy(plain, chunk, REG_REQ_LEN);
    aes_dec(K_RA_D, plain, 2);

    uint8_t id_d = plain[0];
    if (id_d == 0 || id_d >= MAX_CLIENTS) return;

    uint8_t Ad[HASH_LEN];
    memcpy(Ad, plain + 1, HASH_LEN);

    /* Generate TIDd = H(random_seed || IDd || K_MASTER) */
    uint8_t tid_seed[HASH_LEN + 1 + HASH_LEN];
    gen_random(tid_seed, HASH_LEN);
    tid_seed[HASH_LEN] = id_d;
    memcpy(tid_seed + HASH_LEN + 1, K_MASTER, HASH_LEN);
    uint8_t TIDd[HASH_LEN];
    H(tid_seed, HASH_LEN + 1 + HASH_LEN, TIDd);

    /* Compute Bk = H(Ad || Af || K) */
    uint8_t bk_in[3 * HASH_LEN];
    memcpy(bk_in, Ad, HASH_LEN);
    memcpy(bk_in + HASH_LEN, Af, HASH_LEN);
    memcpy(bk_in + 2 * HASH_LEN, K_MASTER, HASH_LEN);
    uint8_t Bk[HASH_LEN];
    H(bk_in, 3 * HASH_LEN, Bk);

    /* Store in RA database */
    clients[id_d].IDd = id_d;
    memcpy(clients[id_d].TIDd, TIDd, HASH_LEN);
    memcpy(clients[id_d].Ad, Ad, HASH_LEN);
    memcpy(clients[id_d].Bk, Bk, HASH_LEN);
    clients[id_d].registered = 1;

    /* Build reply: TIDd(20)+TIDf(20)+Af(20)+Bk(20) = 80 B, encrypt 5 blocks */
    uint8_t reply[REG_REP_LEN];
    memset(reply, 0, REG_REP_LEN);
    memcpy(reply, TIDd, HASH_LEN);
    memcpy(reply + HASH_LEN, TIDf_const, HASH_LEN);
    memcpy(reply + 2 * HASH_LEN, Af, HASH_LEN);
    memcpy(reply + 3 * HASH_LEN, Bk, HASH_LEN);
    aes_enc(K_RA_D, reply, 5);
    coap_set_payload(resp, reply, REG_REP_LEN);

    /* Enqueue device info for forwarding to correct fog server:
     * AES(K_RA_GW, [IDd(1)|TIDd(20)|Ad(20)|Bk(20)|pad(3)]) = 64 B */
    if (!FWD_FULL()) {
        fwd_entry_t *slot = &fwd_queue[fwd_tail];
        memset(slot->payload, 0, DEV_INFO_LEN);
        slot->payload[0] = id_d;
        memcpy(slot->payload + 1, TIDd, HASH_LEN);
        memcpy(slot->payload + 1 + HASH_LEN, Ad, HASH_LEN);
        memcpy(slot->payload + 1 + 2 * HASH_LEN, Bk, HASH_LEN);
        aes_enc(K_RA_GW, slot->payload, 4);
        slot->fog_id = get_fog_for_device(id_d);
        fwd_tail = (fwd_tail + 1) % MAX_CLIENTS;
        process_post(&gw_proc, ev_fwd, NULL);
    }

    printf("RA %u: Registered device %u -> Fog %u. TIDd=%02x%02x%02x\n",
           node_id, id_d, get_fog_for_device(id_d),
           TIDd[0], TIDd[1], TIDd[2]);
}

RESOURCE(res_reg, "title=\"Reg\"", NULL, res_reg_handler, NULL, NULL);

/* Forward queue drain callback */
static void fwd_ack(coap_message_t *resp)
{
    if (!resp)
        printf("RA %u: dev_info delivery to fog timed out\n", node_id);
    fwd_head = (fwd_head + 1) % MAX_CLIENTS;
}

/* ==========================================================================
 * Main process
 * ========================================================================== */
PROCESS(gw_proc, "GW / Registration Authority");
AUTOSTART_PROCESSES(&gw_proc);

PROCESS_THREAD(gw_proc, ev, data)
{
    PROCESS_BEGIN();

    memset(clients, 0, sizeof(clients));
    fwd_head = fwd_tail = 0;

    /* Compute Af = H(FOG_IDENTITY_ID || r1_fog) */
    {
        uint8_t af_in[1 + HASH_LEN];
        af_in[0] = (uint8_t)FOG_IDENTITY_ID;
        memcpy(af_in + 1, r1_fog, HASH_LEN);
        H(af_in, 1 + HASH_LEN, Af);
    }

    /* Become RPL root */
    NETSTACK_ROUTING.root_start();

    /* Initialise CoAP engine and activate registration resource */
    coap_engine_init();
    coap_activate_resource(&res_reg, "test/reg");

    ev_fwd = process_alloc_event();

    printf("RA %u: Started (RPL root + Registration Authority). Af=%02x%02x%02x\n",
           node_id, Af[0], Af[1], Af[2]);

    while (1) {
        PROCESS_WAIT_EVENT_UNTIL(ev == ev_fwd);
        /* Drain forward queue: deliver device info to assigned fog servers */
        while (!FWD_EMPTY()) {
            fwd_entry_t *entry = &fwd_queue[fwd_head];
            set_fog_endpoint(entry->fog_id);
            coap_init_message(req_fw, COAP_TYPE_CON, COAP_POST, coap_get_mid());
            coap_set_header_uri_path(req_fw, "test/dev_info");
            coap_set_payload(req_fw, entry->payload, DEV_INFO_LEN);
            COAP_BLOCKING_REQUEST(&ep_fog, req_fw, fwd_ack);
        }
    }

    PROCESS_END();
}
