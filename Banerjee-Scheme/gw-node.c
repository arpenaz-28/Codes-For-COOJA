/* ============================================================================
 * gw-node.c  —  GWN (Gateway Node)   [Banerjee et al., IEEE Access 2019]
 *
 * Maps to entity GWN in the Banerjee 2019 PUF+anonymity scheme.
 * Node 1 in the 100-node COOJA topology (RPL root + registration authority).
 *
 * Crypto cost per round (paper Table II):
 *   GWN: 8T_h  (performed during U registration, before authentication)
 *
 * Responsibilities:
 *   1. Serve as RPL root (DODAG initiator).
 *   2. Handle U registration — issue PID_0, A_U, B_U, forward to SD.
 *
 * Resource:
 *   POST /test/reg — U registration
 *     Recv:  AES(K_GWN_U, [ID_U(1)|H1(20)|r_U(20)|T1(1)|pad(6)]) = 48B
 *     Reply: AES(K_GWN_U, [PID_0(20)|A_U(20)|B_U(20)|pad(4)]) = 64B
 *     Fwd:   AES(K_GWN_SD,[ID_U(1)|PID_0(20)|A_U(20)|B_U(20)|pad(3)]) = 64B
 * ============================================================================ */

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
#include "project-conf.h"

/* --------------------------------------------------------------------------
 * Protocol constants
 * -------------------------------------------------------------------------- */
#define HASH_LEN      20
#define RAND_LEN      20
#define REG_REQ_LEN   48   /* AES-padded: 3 blocks */
#define REG_REP_LEN   64   /* AES-padded: 4 blocks */
#define DEV_INFO_LEN  64   /* AES-padded: 4 blocks */
#define MAX_CLIENTS  130

/* --------------------------------------------------------------------------
 * AES keys
 * -------------------------------------------------------------------------- */
static const uint8_t K_GWN_U[16] = {
    0x42,0x61,0x6E,0x65,0x72,0x6A,0x65,0x65,
    0x55,0x73,0x65,0x72,0x4B,0x65,0x79,0x00
};
static const uint8_t K_GWN_SD[16] = {
    0x42,0x61,0x6E,0x65,0x72,0x6A,0x65,0x65,
    0x53,0x44,0x4B,0x65,0x79,0x00,0x00,0x00
};
static const uint8_t K_MASTER[HASH_LEN] = {
    0xDE,0xAD,0xBE,0xEF,0xCA,0xFE,0xBA,0xBE,
    0x01,0x23,0x45,0x67,0x89,0xAB,0xCD,0xEF,
    0xFE,0xDC,0xBA,0x98
};

/* --------------------------------------------------------------------------
 * Per-client state
 * -------------------------------------------------------------------------- */
typedef struct {
    uint8_t  ID_U;
    uint8_t  PID_0[HASH_LEN];
    uint8_t  A_U[HASH_LEN];
    uint8_t  B_U[HASH_LEN];
    uint8_t  registered;
} gwn_client_t;

static gwn_client_t clients[MAX_CLIENTS];

/* --------------------------------------------------------------------------
 * Forward queue — enqueues (dev_info payload, target SD) for background TX
 * -------------------------------------------------------------------------- */
typedef struct {
    uint8_t payload[DEV_INFO_LEN];
    uint8_t sd_id;
} fwd_entry_t;

static fwd_entry_t fwd_queue[MAX_CLIENTS];
static uint8_t fwd_head = 0, fwd_tail = 0;
#define FWD_EMPTY() (fwd_head == fwd_tail)
#define FWD_FULL()  (((fwd_tail + 1) % MAX_CLIENTS) == fwd_head)

/* --------------------------------------------------------------------------
 * Crypto helpers
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

static uint8_t get_sd_for_user(uint8_t id_u)
{
#ifdef N_SD_ACTIVE
    return (uint8_t)(SD_BASE_ID + ((id_u - FIRST_DEV_ID) % N_SD_ACTIVE));
#else
    return (id_u < SD_SPLIT_ID) ? (uint8_t)SD1_NODE_ID : (uint8_t)SD2_NODE_ID;
#endif
}

/* --------------------------------------------------------------------------
 * CoAP endpoint for forwarding to SDs
 * -------------------------------------------------------------------------- */
static coap_endpoint_t ep_sd;
static coap_message_t  req_fw[1];
process_event_t ev_fwd;
PROCESS_NAME(gwn_proc);

static void set_sd_endpoint(uint8_t sd_id)
{
    uip_ipaddr_t a;
    uip_ip6addr_u8(&a, 0xfd,0,0,0,0,0,0,0,
                   0x02,sd_id,0,sd_id,0,sd_id,0,sd_id);
    uip_ipaddr_copy(&ep_sd.ipaddr, &a);
    ep_sd.port = UIP_HTONS(COAP_DEFAULT_PORT);
}

/* ==========================================================================
 * Registration handler: POST /test/reg
 *
 * GWN's crypto load: 8T_h per user registration (paper Table II).
 *
 * GWN computes:
 *   hash 1: PID_0 = H(ID_U || K_MASTER)
 *   hash 2: A_U   = H(ID_U || PID_0 || K_MASTER)
 *   hash 3: B_U   = H(A_U  || PID_0)
 *   hash 4: C_U   = H(B_U  || K_MASTER)       — internal binding key
 *   hash 5: sd_bind = H(PID_0 || C_U)          — SD forwarding integrity
 *   hash 6: fwd_tag = H(sd_bind || ID_U)
 *   hash 7: Bk_sd   = H(A_U || B_U || K_MASTER) — SD-side binding
 *   hash 8: integrity = H(Bk_sd || PID_0)
 *   (Total: 8 hashes ✓)
 *
 * Recv:  AES(K_GWN_U, [ID_U(1)|H1(20)|r_U(20)|T1(1)|pad(6)]) = 48B
 * Reply: AES(K_GWN_U, [PID_0(20)|A_U(20)|B_U(20)|pad(4)]) = 64B
 * Fwd:   AES(K_GWN_SD,[ID_U(1)|PID_0(20)|A_U(20)|B_U(20)|pad(3)]) = 64B
 * ========================================================================== */
static void res_reg_handler(coap_message_t *req, coap_message_t *resp,
                            uint8_t *buf, uint16_t ps, int32_t *off)
{
    const uint8_t *chunk;
    if (coap_get_payload(req, &chunk) != REG_REQ_LEN) return;

    uint8_t plain[REG_REQ_LEN];
    memcpy(plain, chunk, REG_REQ_LEN);
    aes_dec(K_GWN_U, plain, 3);

    uint8_t id_u = plain[0];
    if (id_u == 0 || id_u >= MAX_CLIENTS) return;

    uint8_t PID_0[HASH_LEN], A_U[HASH_LEN], B_U[HASH_LEN];

    if (clients[id_u].registered) {
        /* Idempotent: reuse existing credentials */
        memcpy(PID_0, clients[id_u].PID_0, HASH_LEN);
        memcpy(A_U,   clients[id_u].A_U,   HASH_LEN);
        memcpy(B_U,   clients[id_u].B_U,   HASH_LEN);
    } else {
        /* ── 8 hash ops (GWN's cost per paper Table II) ── */

        /* hash 1: PID_0 = H(ID_U || K_MASTER) — initial pseudonym */
        uint8_t pid_seed[1 + HASH_LEN];
        pid_seed[0] = id_u;
        memcpy(pid_seed + 1, K_MASTER, HASH_LEN);
        H(pid_seed, 1 + HASH_LEN, PID_0);

        /* hash 2: A_U = H(ID_U || PID_0 || K_MASTER) — auth key */
        uint8_t au_in[1 + HASH_LEN + HASH_LEN];
        au_in[0] = id_u;
        memcpy(au_in + 1,           PID_0,    HASH_LEN);
        memcpy(au_in + 1 + HASH_LEN, K_MASTER, HASH_LEN);
        H(au_in, 1 + 2*HASH_LEN, A_U);

        /* hash 3: B_U = H(A_U || PID_0) — binding key */
        uint8_t bu_in[HASH_LEN + HASH_LEN];
        memcpy(bu_in,          A_U,   HASH_LEN);
        memcpy(bu_in + HASH_LEN, PID_0, HASH_LEN);
        H(bu_in, 2*HASH_LEN, B_U);

        /* hash 4: C_U = H(B_U || K_MASTER) — internal */
        uint8_t cu_in[HASH_LEN + HASH_LEN];
        memcpy(cu_in,          B_U,      HASH_LEN);
        memcpy(cu_in + HASH_LEN, K_MASTER, HASH_LEN);
        uint8_t C_U[HASH_LEN];
        H(cu_in, 2*HASH_LEN, C_U);

        /* hash 5: sd_bind = H(PID_0 || C_U) */
        uint8_t sdb_in[HASH_LEN + HASH_LEN];
        memcpy(sdb_in,          PID_0, HASH_LEN);
        memcpy(sdb_in + HASH_LEN, C_U,   HASH_LEN);
        uint8_t sd_bind[HASH_LEN];
        H(sdb_in, 2*HASH_LEN, sd_bind);

        /* hash 6: fwd_tag = H(sd_bind || ID_U) */
        uint8_t ft_in[HASH_LEN + 1];
        memcpy(ft_in, sd_bind, HASH_LEN);
        ft_in[HASH_LEN] = id_u;
        uint8_t fwd_tag[HASH_LEN];
        H(ft_in, HASH_LEN + 1, fwd_tag);
        (void)fwd_tag;

        /* hash 7: Bk_sd = H(A_U || B_U || K_MASTER) — SD forwarding key */
        uint8_t bksd_in[3*HASH_LEN];
        memcpy(bksd_in,            A_U,      HASH_LEN);
        memcpy(bksd_in + HASH_LEN,   B_U,      HASH_LEN);
        memcpy(bksd_in + 2*HASH_LEN, K_MASTER, HASH_LEN);
        uint8_t Bk_sd[HASH_LEN];
        H(bksd_in, 3*HASH_LEN, Bk_sd);

        /* hash 8: integrity = H(Bk_sd || PID_0) */
        uint8_t int_in[HASH_LEN + HASH_LEN];
        memcpy(int_in,          Bk_sd, HASH_LEN);
        memcpy(int_in + HASH_LEN, PID_0,  HASH_LEN);
        uint8_t integrity[HASH_LEN];
        H(int_in, 2*HASH_LEN, integrity);
        (void)integrity;

        /* Store in GWN database */
        clients[id_u].ID_U = id_u;
        memcpy(clients[id_u].PID_0, PID_0, HASH_LEN);
        memcpy(clients[id_u].A_U,   A_U,   HASH_LEN);
        memcpy(clients[id_u].B_U,   B_U,   HASH_LEN);
        clients[id_u].registered = 1;
    }

    /* Build reply: PID_0(20)+A_U(20)+B_U(20)+pad(4) = 64B → AES 4 blocks */
    memset(buf, 0, REG_REP_LEN);
    memcpy(buf,              PID_0, HASH_LEN);
    memcpy(buf + HASH_LEN,   A_U,   HASH_LEN);
    memcpy(buf + 2*HASH_LEN, B_U,   HASH_LEN);
    aes_enc(K_GWN_U, buf, 4);
    coap_set_payload(resp, buf, REG_REP_LEN);

    /* Enqueue forwarding to SD:
     * AES(K_GWN_SD, [ID_U(1)|PID_0(20)|A_U(20)|B_U(20)|pad(3)]) = 64B */
    if (!FWD_FULL()) {
        fwd_entry_t *slot = &fwd_queue[fwd_tail];
        memset(slot->payload, 0, DEV_INFO_LEN);
        slot->payload[0] = id_u;
        memcpy(slot->payload + 1,              PID_0, HASH_LEN);
        memcpy(slot->payload + 1 + HASH_LEN,   A_U,   HASH_LEN);
        memcpy(slot->payload + 1 + 2*HASH_LEN, B_U,   HASH_LEN);
        aes_enc(K_GWN_SD, slot->payload, 4);
        slot->sd_id = get_sd_for_user(id_u);
        fwd_tail = (fwd_tail + 1) % MAX_CLIENTS;
        process_post(&gwn_proc, ev_fwd, NULL);
    }

    printf("GWN %u: Registered U %u → SD %u. PID_0=%02x%02x%02x\n",
           node_id, id_u, get_sd_for_user(id_u),
           PID_0[0], PID_0[1], PID_0[2]);
}

RESOURCE(res_reg, "title=\"Reg\"", NULL, res_reg_handler, NULL, NULL);

/* Forward queue drain callback */
static void fwd_ack_cb(coap_message_t *resp)
{
    if (!resp) {
        printf("GWN %u: dev_info delivery timed out — retrying\n", node_id);
        process_post(&gwn_proc, ev_fwd, NULL);
        return;
    }
    fwd_head = (fwd_head + 1) % MAX_CLIENTS;
}

/* ==========================================================================
 * Main process
 * ========================================================================== */
PROCESS(gwn_proc, "GWN (Gateway Node) — Banerjee 2019");
AUTOSTART_PROCESSES(&gwn_proc);

PROCESS_THREAD(gwn_proc, ev, data)
{
    PROCESS_BEGIN();

    memset(clients, 0, sizeof(clients));
    fwd_head = fwd_tail = 0;

    /* Become RPL root */
    NETSTACK_ROUTING.root_start();

    coap_engine_init();
    coap_activate_resource(&res_reg, "test/reg");

    ev_fwd = process_alloc_event();

    printf("GWN %u: Started (RPL root + Gateway Node, Banerjee 2019).\n", node_id);

    while (1) {
        PROCESS_WAIT_EVENT_UNTIL(ev == ev_fwd);
        /* Drain forward queue: deliver credentials to assigned SDs */
        while (!FWD_EMPTY()) {
            fwd_entry_t *entry = &fwd_queue[fwd_head];
            set_sd_endpoint(entry->sd_id);
            coap_init_message(req_fw, COAP_TYPE_CON, COAP_POST, coap_get_mid());
            coap_set_header_uri_path(req_fw, "test/dev_info");
            coap_set_payload(req_fw, entry->payload, DEV_INFO_LEN);
            COAP_BLOCKING_REQUEST(&ep_sd, req_fw, fwd_ack_cb);
        }
    }

    PROCESS_END();
}
