/* ==========================================================================
 * as-node.c  —  Authentication Server (Desync Demonstration)
 *
 * Enhanced with DESYNC_LOG output to clearly show:
 * - PID_curr vs PID_old search
 * - Dual-state storage usage during desync recovery
 * - Pseudonym rotation steps
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
#include "random.h"
#include "sys/node-id.h"
#include "net/ipv6/uip-ds6.h"
#include "project-conf.h"
#include "sys/energest.h"

/* --------------------------------------------------------------------------
 * Shared long-term symmetric keys
 * -------------------------------------------------------------------------- */
static const uint8_t K_AS_D[16] = {
    0x67,0x61,0x74,0x73,0x20,0x6D,0x79,0x20,
    0x4B,0x75,0x6F,0x67,0x20,0x46,0x75,0x00
};
static const uint8_t K_GW_AS[16] = {
    0x67,0x62,0x74,0x73,0x20,0x6D,0x79,0x20,
    0x4B,0x75,0x6F,0x67,0x20,0x46,0x75,0x00
};

/* --------------------------------------------------------------------------
 * Packet sizes
 * -------------------------------------------------------------------------- */
#define REG0_REQ_LEN   16
#define REG0_REP_LEN   48
#define REG1_REQ_LEN   48
#define AUTH_REQ_LEN   65
#define AUTH_REP_LEN   34
#define GW_TOKEN_LEN   81
#define ACK_BYTE       0xAC
#define MAX_CLIENTS    10

/* --------------------------------------------------------------------------
 * AND-accumulator
 * -------------------------------------------------------------------------- */
static uint8_t T_acc[32];
static uint8_t session_ctr = 0;

/* --------------------------------------------------------------------------
 * Per-client state — DUAL-STATE storage for desync resistance
 * -------------------------------------------------------------------------- */
typedef struct {
    uint8_t  ID_d;
    uint8_t  c_d;
    uint8_t  c_as_d;
    uint8_t  phi_as_d;
    uint8_t  PID_curr[32];    /* Current pseudonym                     */
    uint8_t  PID_old[32];     /* Previous pseudonym (for desync)       */
    uint8_t  m_curr[32];      /* Current mask                          */
    uint8_t  m_old[32];       /* Previous mask (for desync)            */
    uint8_t  last_ts1;
    uint8_t  enrolled;
    uint8_t  pid_old_valid;   /* 1 once first rotation happened        */
} client_t;

static client_t clients[MAX_CLIENTS];

/* --------------------------------------------------------------------------
 * Token ring-buffer
 * -------------------------------------------------------------------------- */
static uint8_t  tok_buf[MAX_CLIENTS][GW_TOKEN_LEN];
static uint8_t  tok_head = 0, tok_tail = 0;
#define TOK_EMPTY()  (tok_head == tok_tail)
#define TOK_FULL()   (((tok_tail + 1) % MAX_CLIENTS) == tok_head)

/* --------------------------------------------------------------------------
 * Energest
 * -------------------------------------------------------------------------- */
#define CURRENT_CPU     1.8e-3
#define CURRENT_LPM     0.0545e-3
#define CURRENT_TX      17.4e-3
#define CURRENT_RX      18.8e-3
#define SUPPLY_VOLTAGE  3.0

static void print_energest_stats(void)
{
    energest_flush();
    unsigned long cpu  = energest_type_time(ENERGEST_TYPE_CPU);
    unsigned long lpm  = energest_type_time(ENERGEST_TYPE_LPM);
    unsigned long tx   = energest_type_time(ENERGEST_TYPE_TRANSMIT);
    unsigned long rx   = energest_type_time(ENERGEST_TYPE_LISTEN);

    double s_cpu = cpu / (double)ENERGEST_SECOND;
    double e = s_cpu * CURRENT_CPU * SUPPLY_VOLTAGE
             + (lpm / (double)ENERGEST_SECOND) * CURRENT_LPM * SUPPLY_VOLTAGE
             + (tx  / (double)ENERGEST_SECOND) * CURRENT_TX  * SUPPLY_VOLTAGE
             + (rx  / (double)ENERGEST_SECOND) * CURRENT_RX  * SUPPLY_VOLTAGE;
    printf("DESYNC_LOG|AS %u|Energest|cpu_s=%.6f|energy_j=%.6f\n",
           node_id, s_cpu, e);
}

/* --------------------------------------------------------------------------
 * Forward declarations
 * -------------------------------------------------------------------------- */
static coap_endpoint_t ep_gw;
static coap_message_t  req_gw[1];
process_event_t        ev_send_tok;
PROCESS_NAME(as_proc);

/* --------------------------------------------------------------------------
 * Helpers
 * -------------------------------------------------------------------------- */
static uint8_t puf_response(uint8_t challenge)
{
    uint32_t s = ((uint32_t)node_id  * 2246822519UL)
               ^ ((uint32_t)challenge * 2654435761UL);
    s = ((s >> 16) ^ s) * 0x45d9f3bUL;
    s = ((s >> 16) ^ s) * 0x45d9f3bUL;
    s ^= (s >> 16);
    return (uint8_t)(s & 0xFF);
}

static void gen_random(uint8_t *buf, uint8_t len)
{
    for (uint8_t i = 0; i < len; i++) {
        uint16_t r = random_rand();
        buf[i] = (uint8_t)((r & 0xFF) ^ (uint8_t)(clock_time() >> (i & 7)));
    }
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

static int seq_ts_fresh(uint8_t new_ts, uint8_t last_ts)
{
    int diff = ((int)new_ts - (int)last_ts + 256) % 256;
    return (diff > 0 && diff <= 200);
}

static void discover_gw(void)
{
    uip_ipaddr_t a;
    uint8_t g = GW_NODE_ID;
    uip_ip6addr_u8(&a, 0xfd,0,0,0,0,0,0,0, 0x02,g,0,g,0,g,0,g);
    uip_ipaddr_copy(&ep_gw.ipaddr, &a);
    ep_gw.port = UIP_HTONS(COAP_DEFAULT_PORT);
}

/* ==========================================================================
 * Enrollment Step 0 (GET /test/reg)
 * ========================================================================== */
static void res_reg_handler(coap_message_t *req, coap_message_t *resp,
                            uint8_t *buf, uint16_t ps, int32_t *off)
{
    const uint8_t *chunk;
    if (coap_get_payload(req, &chunk) != REG0_REQ_LEN) return;

    uint8_t plain[16];
    memcpy(plain, chunk, 16);
    aes_dec(K_AS_D, plain, 1);
    uint8_t id_d = plain[0];
    if (id_d == 0 || id_d >= MAX_CLIENTS) return;

    clients[id_d].ID_d          = id_d;
    clients[id_d].enrolled      = 0;
    clients[id_d].pid_old_valid = 0;
    clients[id_d].last_ts1      = 0;

    clients[id_d].c_d = (uint8_t)(random_rand() & 0xFF);
    gen_random(clients[id_d].m_curr, 32);
    memcpy(clients[id_d].m_old, clients[id_d].m_curr, 32);

    uint8_t reply[REG0_REP_LEN];
    memset(reply, 0, REG0_REP_LEN);
    reply[0] = clients[id_d].c_d;
    memcpy(reply + 1, clients[id_d].m_curr, 32);
    aes_enc(K_AS_D, reply, 3);

    coap_set_payload(resp, reply, REG0_REP_LEN);
    printf("DESYNC_LOG|AS %u|Reg-0 for device %u|c_d=%u\n",
           node_id, id_d, clients[id_d].c_d);
}

/* ==========================================================================
 * Enrollment Step 1 (POST /test/reg1)
 * ========================================================================== */
static void res_reg1_handler(coap_message_t *req, coap_message_t *resp,
                             uint8_t *buf, uint16_t ps, int32_t *off)
{
    const uint8_t *chunk;
    if (coap_get_payload(req, &chunk) != REG1_REQ_LEN) return;

    uint8_t plain[REG1_REQ_LEN];
    memcpy(plain, chunk, REG1_REQ_LEN);
    aes_dec(K_AS_D, plain, 3);

    uint8_t id_d   = plain[0];
    if (id_d == 0 || id_d >= MAX_CLIENTS || clients[id_d].ID_d != id_d) return;

    uint8_t Y_dH[32];
    memcpy(Y_dH, plain + 1, 32);
    uint8_t R_d    = plain[33];
    uint8_t c_as_d = plain[34];

    clients[id_d].c_as_d = c_as_d;

    for (int i = 0; i < 32; i++) T_acc[i] &= Y_dH[i];

    uint8_t R_as = puf_response(c_as_d);
    clients[id_d].phi_as_d = R_as ^ R_d;

    uint8_t pid_in[33];
    pid_in[0] = id_d;
    memcpy(pid_in + 1, clients[id_d].m_curr, 32);
    H(pid_in, 33, clients[id_d].PID_curr);

    memset(clients[id_d].PID_old, 0, 32);
    clients[id_d].pid_old_valid = 0;
    clients[id_d].enrolled = 1;

    const char *msg = "Registered";
    coap_set_payload(resp, (const uint8_t *)msg, strlen(msg));

    printf("DESYNC_LOG|AS %u|Reg-1 complete for device %u|PID_curr=%02x%02x%02x|pid_old_valid=0\n",
           node_id, id_d,
           clients[id_d].PID_curr[0], clients[id_d].PID_curr[1], clients[id_d].PID_curr[2]);
}

/* ==========================================================================
 * Authentication & Key Exchange (POST /test/auth)
 * ========================================================================== */
static void res_auth_handler(coap_message_t *req, coap_message_t *resp,
                             uint8_t *buf, uint16_t ps, int32_t *off)
{
    const uint8_t *chunk;
    int len = coap_get_payload(req, &chunk);
    if (len < AUTH_REQ_LEN) return;

    uint8_t recv_PID[32], y_asd[32], ts_1;
    memcpy(recv_PID, chunk,      32);
    memcpy(y_asd,    chunk + 32, 32);
    ts_1 = chunk[64];

    printf("DESYNC_LOG|AS %u|Auth request received|recv_PID=%02x%02x%02x|ts_1=%u\n",
           node_id, recv_PID[0], recv_PID[1], recv_PID[2], ts_1);

    /* ---- Phase 2a: Search PID_curr first, then PID_old (dual-state) ---- */
    int     found   = -1;
    uint8_t use_old = 0;
    for (int i = 1; i < MAX_CLIENTS; i++) {
        if (!clients[i].enrolled) continue;
        if (memcmp(clients[i].PID_curr, recv_PID, 32) == 0) {
            found = i; use_old = 0;
            printf("DESYNC_LOG|AS %u|PID MATCH on PID_curr for device %u|NORMAL PATH\n",
                   node_id, i);
            break;
        }
        if (clients[i].pid_old_valid &&
            memcmp(clients[i].PID_old, recv_PID, 32) == 0) {
            found = i; use_old = 1;
            printf("DESYNC_LOG|AS %u|PID MATCH on PID_old for device %u|DESYNC RECOVERY PATH\n",
                   node_id, i);
            printf("DESYNC_LOG|AS %u|RECOVERY|Device stuck on OLD state — AS using m_old to verify\n",
                   node_id);
            break;
        }
    }
    if (found == -1) {
        printf("DESYNC_LOG|AS %u|Auth FAILED|PID not found in curr or old\n", node_id);
        return;
    }

    client_t *cl       = &clients[found];
    uint8_t  *m_active = use_old ? cl->m_old : cl->m_curr;

    if (use_old) {
        printf("DESYNC_LOG|AS %u|RECOVERY|Using m_old=%02x%02x%02x... for device %u\n",
               node_id, cl->m_old[0], cl->m_old[1], cl->m_old[2], found);
    } else {
        printf("DESYNC_LOG|AS %u|Using m_curr=%02x%02x%02x... for device %u\n",
               node_id, cl->m_curr[0], cl->m_curr[1], cl->m_curr[2], found);
    }

    /* ---- Phase 2b: Freshness check ---- */
    if (use_old) {
        int diff = ((int)ts_1 - (int)cl->last_ts1 + 256) % 256;
        if (diff > 200) {
            printf("DESYNC_LOG|AS %u|Auth FAILED|ts_1 wrapped badly in desync recovery\n",
                   node_id);
            return;
        }
    } else {
        if (!seq_ts_fresh(ts_1, cl->last_ts1)) {
            printf("DESYNC_LOG|AS %u|Auth FAILED|stale ts_1 for device %u\n",
                   node_id, found);
            return;
        }
    }

    /* ---- Phase 2c: Recover R_d ---- */
    uint8_t R_as = puf_response(cl->c_as_d);
    uint8_t R_d  = cl->phi_as_d ^ R_as;

    /* ---- Phase 2d: Recover y_dH ---- */
    uint8_t mask_in[66], mask[32], Y_dH[32];
    mask_in[0] = R_d;
    memcpy(mask_in + 1,  m_active, 32);
    memcpy(mask_in + 33, recv_PID, 32);
    mask_in[65] = ts_1;
    H(mask_in, 66, mask);
    for (int i = 0; i < 32; i++) Y_dH[i] = y_asd[i] ^ mask[i];

    /* ---- Phase 2e: Membership test ---- */
    uint8_t T_new[32];
    for (int i = 0; i < 32; i++) T_new[i] = T_acc[i] & Y_dH[i];
    if (memcmp(T_new, T_acc, 32) != 0) {
        printf("DESYNC_LOG|AS %u|Auth FAILED|membership check failed for device %u\n",
               node_id, found);
        return;
    }

    cl->last_ts1 = ts_1;
    printf("DESYNC_LOG|AS %u|Device %u AUTHENTICATED|membership OK|use_old=%u\n",
           node_id, found, use_old);

    /* ==== Phase 3 — Key Exchange ==== */
    uint8_t n1[32], m_new[32];
    gen_random(n1, 32);
    H(n1, 32, m_new);
    uint8_t ts_2 = ++session_ctr;

    uint8_t mh_in[99], mh_mask[32], m_H[32];
    memcpy(mh_in,      Y_dH,      32);
    memcpy(mh_in + 32, m_active,  32);
    mh_in[64] = R_d;
    mh_in[65] = (uint8_t)node_id;
    memcpy(mh_in + 66, recv_PID,  32);
    mh_in[98] = ts_2;
    H(mh_in, 99, mh_mask);
    for (int i = 0; i < 32; i++) m_H[i] = m_new[i] ^ mh_mask[i];

    uint8_t kd_in[33], K_GW_D[32];
    kd_in[0] = R_d;
    memcpy(kd_in + 1, m_new, 32);
    H(kd_in, 33, K_GW_D);

    uint8_t ts_auth = (uint8_t)(clock_time() / CLOCK_SECOND);
    uint8_t enc_tok[48];
    memset(enc_tok, 0, 48);
    enc_tok[0] = (uint8_t)found;
    enc_tok[1] = (uint8_t)node_id;
    enc_tok[2] = ts_auth;
    memcpy(enc_tok + 16, K_GW_D,      16);
    memcpy(enc_tok + 32, K_GW_D + 16, 16);
    aes_enc(K_GW_AS, enc_tok, 3);

    /* ---- Pseudonym rotation (with desync logging) ---- */
    printf("DESYNC_LOG|AS %u|ROTATING state for device %u\n", node_id, found);
    printf("DESYNC_LOG|AS %u|  Before: PID_curr=%02x%02x%02x, PID_old=%02x%02x%02x, pid_old_valid=%u\n",
           node_id,
           cl->PID_curr[0], cl->PID_curr[1], cl->PID_curr[2],
           cl->PID_old[0],  cl->PID_old[1],  cl->PID_old[2],
           cl->pid_old_valid);

    memcpy(cl->PID_old, cl->PID_curr, 32);
    memcpy(cl->m_old,   cl->m_curr,   32);
    cl->pid_old_valid = 1;

    uint8_t new_pid_in[33];
    new_pid_in[0] = (uint8_t)found;
    memcpy(new_pid_in + 1, m_new, 32);
    H(new_pid_in, 33, cl->PID_curr);
    memcpy(cl->m_curr, m_new, 32);

    printf("DESYNC_LOG|AS %u|  After:  PID_curr=%02x%02x%02x (NEW), PID_old=%02x%02x%02x (BACKUP), pid_old_valid=1\n",
           node_id,
           cl->PID_curr[0], cl->PID_curr[1], cl->PID_curr[2],
           cl->PID_old[0],  cl->PID_old[1],  cl->PID_old[2]);

    /* Reply to device */
    uint8_t reply[AUTH_REP_LEN];
    reply[0] = ACK_BYTE;
    memcpy(reply + 1, m_H, 32);
    reply[33] = ts_2;
    coap_set_payload(resp, reply, AUTH_REP_LEN);

    /* Enqueue token for GW */
    if (!TOK_FULL()) {
        uint8_t *slot = tok_buf[tok_tail];
        memcpy(slot,      cl->PID_curr, 32);
        slot[32] = (uint8_t)node_id;
        memcpy(slot + 33, enc_tok,      48);
        tok_tail = (tok_tail + 1) % MAX_CLIENTS;
        process_post(&as_proc, ev_send_tok, NULL);
    }

    print_energest_stats();
}

/* --------------------------------------------------------------------------
 * CoAP resource declarations
 * -------------------------------------------------------------------------- */
RESOURCE(res_reg,  "title=\"Reg\"",  res_reg_handler,  NULL, NULL, NULL);
RESOURCE(res_reg1, "title=\"Reg1\"", NULL, res_reg1_handler, NULL, NULL);
RESOURCE(res_auth, "title=\"Auth\"", NULL, res_auth_handler, NULL, NULL);

static void gw_tok_ack(coap_message_t *resp)
{
    if (!resp)
        printf("DESYNC_LOG|AS %u|Token delivery to GW timed out\n", node_id);
    tok_head = (tok_head + 1) % MAX_CLIENTS;
}

/* ==========================================================================
 * Main process
 * ========================================================================== */
PROCESS(as_proc, "AS");
AUTOSTART_PROCESSES(&as_proc);

PROCESS_THREAD(as_proc, ev, data)
{
    PROCESS_BEGIN();

    memset(clients, 0, sizeof(clients));
    memset(T_acc, 0xFF, 32);
    tok_head = tok_tail = 0;
    session_ctr = 0;

    coap_engine_init();
    discover_gw();

    coap_activate_resource(&res_reg,  "test/reg");
    coap_activate_resource(&res_reg1, "test/reg1");
    coap_activate_resource(&res_auth, "test/auth");

    ev_send_tok = process_alloc_event();
    printf("DESYNC_LOG|AS %u|Started\n", node_id);

    while (1) {
        PROCESS_WAIT_EVENT_UNTIL(ev == ev_send_tok);
        while (!TOK_EMPTY()) {
            uint8_t payload[GW_TOKEN_LEN];
            memcpy(payload, tok_buf[tok_head], GW_TOKEN_LEN);
            coap_init_message(req_gw, COAP_TYPE_CON, COAP_POST, coap_get_mid());
            coap_set_header_uri_path(req_gw, "test/auth_token");
            coap_set_payload(req_gw, payload, GW_TOKEN_LEN);
            COAP_BLOCKING_REQUEST(&ep_gw, req_gw, gw_tok_ack);
        }
    }

    PROCESS_END();
}
