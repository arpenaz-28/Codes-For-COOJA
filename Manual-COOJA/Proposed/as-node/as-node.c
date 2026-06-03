/* ==========================================================================
 * as-node.c  —  Authentication Server  (Revised Anonymity — SINGLE ROUND)
 *
 * Auth and Key Exchange combined into one CoAP round:
 *
 *   /test/auth  (POST) — Verify membership, compute m_new/m_H/K_GW_D/token,
 *                        rotate PID and m_curr immediately, forward token to GW.
 *                        Reply: ts_2(1) | m_H(32) = 33 B
 *
 * Packet sizes:
 *   REG0_REQ = 16 B    REG0_REP = 48 B
 *   REG1_REQ = 48 B    REG1_REP = "Registered"
 *   AUTH_REQ = 65 B    AUTH_REP = 33 B  (ts_2 | m_H)
 *   GW_TOKEN = 81 B    (forwarded immediately after auth)
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
 * Long-term symmetric keys
 * -------------------------------------------------------------------------- */
static const uint8_t K_AS_D[16]  = {
    0x67,0x61,0x74,0x73,0x20,0x6D,0x79,0x20,
    0x4B,0x75,0x6F,0x67,0x20,0x46,0x75,0x00
};
static const uint8_t K_GW_AS[16] = {
    0x67,0x62,0x74,0x73,0x20,0x6D,0x79,0x20,
    0x4B,0x75,0x6F,0x67,0x20,0x46,0x75,0x00
};

/* --------------------------------------------------------------------------
 * Packet size constants
 * -------------------------------------------------------------------------- */
#define REG0_REQ_LEN    16
#define REG0_REP_LEN    48
#define REG1_REQ_LEN    48
#define AUTH_REQ_LEN    65   /* PID(32) | y_asd(32) | ts_1(1)   */
#define AUTH_REP_LEN    33   /* ts_2(1) | m_H(32)               */
#define GW_TOKEN_LEN    81   /* new_PID(32) | ID_AS(1) | enc_tok(48) */

#define MAX_CLIENTS     110

/* --------------------------------------------------------------------------
 * Energest
 * -------------------------------------------------------------------------- */
#define CURRENT_CPU     1.8e-3
#define CURRENT_LPM     0.0545e-3
#define CURRENT_TX      17.4e-3
#define CURRENT_RX      18.8e-3
#define SUPPLY_VOLTAGE  3.0

static double cpu_auth_as, energy_auth_as;

static void print_energest_stats(double *seconds_cpu, double *total_energy)
{
    energest_flush();
    unsigned long cpu_ticks = energest_type_time(ENERGEST_TYPE_CPU);
    unsigned long lpm_ticks = energest_type_time(ENERGEST_TYPE_LPM);
    unsigned long tx_ticks  = energest_type_time(ENERGEST_TYPE_TRANSMIT);
    unsigned long rx_ticks  = energest_type_time(ENERGEST_TYPE_LISTEN);
    *seconds_cpu = cpu_ticks / (double)ENERGEST_SECOND;
    double sl = lpm_ticks / (double)ENERGEST_SECOND;
    double st = tx_ticks  / (double)ENERGEST_SECOND;
    double sr = rx_ticks  / (double)ENERGEST_SECOND;
    *total_energy = (*seconds_cpu * CURRENT_CPU + sl * CURRENT_LPM +
                     st * CURRENT_TX  + sr * CURRENT_RX) * SUPPLY_VOLTAGE;
}

/* --------------------------------------------------------------------------
 * AND accumulator for membership test (T_acc & y_dH == T_acc)
 * -------------------------------------------------------------------------- */
static uint8_t T_acc[32];
static uint8_t session_ctr = 0;

/* --------------------------------------------------------------------------
 * Per-client enrolled state
 * -------------------------------------------------------------------------- */
typedef struct {
    uint8_t  ID_d;
    uint8_t  c_d;
    uint8_t  c_as_d;
    uint8_t  phi_as_d;        /* R_as XOR R_d                            */
    uint8_t  h_as_d;          /* PUF helper for AS-side regeneration     */
    uint8_t  PID_curr[32];    /* H(ID || m_curr) — current pseudonym     */
    uint8_t  PID_old[32];     /* H(ID || m_old)  — previous pseudonym    */
    uint8_t  m_curr[32];      /* current session random                  */
    uint8_t  m_old[32];       /* previous session random (desync)        */
    uint8_t  last_ts1;
    uint8_t  enrolled;
    uint8_t  pid_old_valid;
} client_t;

static client_t clients[MAX_CLIENTS];

/* --------------------------------------------------------------------------
 * Token ring-buffer to GW
 * -------------------------------------------------------------------------- */
static uint8_t  tok_buf[MAX_CLIENTS][GW_TOKEN_LEN];
static uint8_t  tok_head = 0;
static uint8_t  tok_tail = 0;
#define TOK_EMPTY()  (tok_head == tok_tail)
#define TOK_FULL()   (((tok_tail + 1) % MAX_CLIENTS) == tok_head)

static coap_endpoint_t  ep_gw;
static coap_message_t   req_gw[1];
process_event_t         ev_send_tok;
PROCESS_NAME(as_proc);

/* ==========================================================================
 * Utility helpers (identical to original scheme)
 * ========================================================================== */
static uint8_t simulate_puf_response(uint8_t c)
{
    uint8_t p1 = random_rand() ^ c, p2 = random_rand() ^ c;
    return (p1 > p2) ? 1 : 0;
}
static void generate_helper(uint8_t r, uint8_t *h, uint8_t *s)
{ *s = 1; *h = *s & r; }
static uint8_t regenerate_response(uint8_t c, uint8_t h)
{ return (h == 0) ? (h & c) : (h || c); }
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
        AES_init_ctx(&ctx, key); AES_ECB_encrypt(&ctx, buf + i * 16);
    }
}
static void aes_dec(const uint8_t *key, uint8_t *buf, uint8_t n)
{
    struct AES_ctx ctx;
    for (uint8_t i = 0; i < n; i++) {
        AES_init_ctx(&ctx, key); AES_ECB_decrypt(&ctx, buf + i * 16);
    }
}
static int seq_ts_fresh(uint8_t nw, uint8_t last)
{
    int d = ((int)nw - (int)last + 256) % 256;
    return (d > 0 && d <= 200);
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
 * PHASE 1a — /test/reg  (Reg-0)
 * Recv: AES_enc(K_AS_D, [id_d|pad]) = 16 B
 * Send: AES_enc(K_AS_D, [c_d|m_d[32]|pad]) = 48 B
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

    printf("AS %u: Reg-0 for device %u (c_d=%u)\n",
           node_id, id_d, clients[id_d].c_d);
}

/* ==========================================================================
 * PHASE 1b — /test/reg1  (Reg-1)
 * Recv: AES_enc(K_AS_D, [id_d|y_dH(32)|R_d|c_as_d|pad]) = 48 B
 * ========================================================================== */
static void res_reg1_handler(coap_message_t *req, coap_message_t *resp,
                             uint8_t *buf, uint16_t ps, int32_t *off)
{
    const uint8_t *chunk;
    if (coap_get_payload(req, &chunk) != REG1_REQ_LEN) return;

    uint8_t plain[REG1_REQ_LEN];
    memcpy(plain, chunk, REG1_REQ_LEN);
    aes_dec(K_AS_D, plain, 3);

    uint8_t id_d = plain[0];
    if (id_d == 0 || id_d >= MAX_CLIENTS || clients[id_d].ID_d != id_d) return;

    uint8_t Y_dH[32];
    memcpy(Y_dH, plain + 1, 32);
    uint8_t R_d    = plain[33];
    uint8_t c_as_d = plain[34];
    clients[id_d].c_as_d = c_as_d;

    for (int i = 0; i < 32; i++) T_acc[i] &= Y_dH[i];

    uint8_t R_as = simulate_puf_response(c_as_d);
    uint8_t secret;
    generate_helper(R_as, &clients[id_d].h_as_d, &secret);
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
    printf("AS %u: Reg-1 complete for device %u\n", node_id, id_d);
}

/* ==========================================================================
 * PHASE 2+3 — /test/auth  (Single round: Auth + Key Exchange combined)
 *
 * Recv: PID(32) | y_asd(32) | ts_1(1) = 65 B
 * Send: ts_2(1) | m_H(32)             = 33 B
 *
 * Verifies membership, computes m_new/m_H/K_GW_D/enc_token,
 * rotates PID and m_curr immediately, forwards token to GW.
 * ========================================================================== */
static void res_auth_handler(coap_message_t *req, coap_message_t *resp,
                             uint8_t *buf, uint16_t ps, int32_t *off)
{
    const uint8_t *chunk;
    int len = coap_get_payload(req, &chunk);
    if (len < AUTH_REQ_LEN) {
        printf("AS %u: Auth pkt too short (%d B)\n", node_id, len);
        return;
    }

    uint8_t recv_PID[32], y_asd[32], ts_1;
    memcpy(recv_PID, chunk,      32);
    memcpy(y_asd,    chunk + 32, 32);
    ts_1 = chunk[64];

    /* --- Find client by PID --- */
    int     found   = -1;
    uint8_t use_old = 0;
    for (int i = 1; i < MAX_CLIENTS; i++) {
        if (!clients[i].enrolled) continue;
        if (memcmp(clients[i].PID_curr, recv_PID, 32) == 0) {
            found = i; use_old = 0; break;
        }
        if (clients[i].pid_old_valid &&
            memcmp(clients[i].PID_old, recv_PID, 32) == 0) {
            found = i; use_old = 1; break;
        }
    }
    if (found == -1) {
        printf("AS %u: Auth failed — PID not found\n", node_id);
        return;
    }
    if (use_old)
        printf("AS %u: Desync recovery for device %u (matched PID_old)\n",
               node_id, found);

    client_t *cl       = &clients[found];
    uint8_t  *m_active = use_old ? cl->m_old : cl->m_curr;

    /* --- Freshness check --- */
    if (use_old) {
        int diff = ((int)ts_1 - (int)cl->last_ts1 + 256) % 256;
        if (diff > 200) {
            printf("AS %u: Bad ts_1 in desync for device %u\n", node_id, found);
            return;
        }
    } else {
        if (!seq_ts_fresh(ts_1, cl->last_ts1)) {
            printf("AS %u: Stale ts_1 for device %u\n", node_id, found);
            return;
        }
    }

    /* --- Recover R_d and y_dH --- */
    uint8_t R_as = regenerate_response(cl->c_as_d, cl->h_as_d);
    uint8_t R_d  = cl->phi_as_d ^ R_as;

    uint8_t mask_in[66], mask[32], Y_dH[32];
    mask_in[0] = R_d;
    memcpy(mask_in + 1,  m_active, 32);
    memcpy(mask_in + 33, recv_PID, 32);
    mask_in[65] = ts_1;
    H(mask_in, 66, mask);
    for (int i = 0; i < 32; i++) Y_dH[i] = y_asd[i] ^ mask[i];

    /* --- Membership test: T_acc & y_dH == T_acc --- */
    uint8_t T_new[32];
    for (int i = 0; i < 32; i++) T_new[i] = T_acc[i] & Y_dH[i];
    if (memcmp(T_new, T_acc, 32) != 0) {
        printf("AS %u: Membership failed for device %u\n", node_id, found);
        return;
    }

    cl->last_ts1 = ts_1;
    printf("AS %u: Device %u authenticated\n", node_id, found);

    /* ------------------------------------------------------------------
     * Compute key exchange material
     * ------------------------------------------------------------------ */

    /* m_new = H(n1),  ts_2 = sequential counter */
    uint8_t n1[32], m_new[32];
    gen_random(n1, 32);
    H(n1, 32, m_new);
    uint8_t ts_2 = ++session_ctr;

    /* m_H = m_new XOR H(Y_dH || m_active || R_d || ID_AS || PID || ts_2) */
    uint8_t mh_in[99], mh_mask[32], m_H[32];
    memcpy(mh_in,      Y_dH,     32);
    memcpy(mh_in + 32, m_active, 32);
    mh_in[64] = R_d;
    mh_in[65] = (uint8_t)node_id;
    memcpy(mh_in + 66, recv_PID, 32);
    mh_in[98] = ts_2;
    H(mh_in, 99, mh_mask);
    for (int i = 0; i < 32; i++) m_H[i] = m_new[i] ^ mh_mask[i];

    /* K_GW_D = H(R_d || m_new) */
    uint8_t kd_in[33], K_GW_D[32];
    kd_in[0] = R_d;
    memcpy(kd_in + 1, m_new, 32);
    H(kd_in, 33, K_GW_D);

    /* new_PID = H(ID || m_new) */
    uint8_t new_pid_in[33], new_PID[32];
    new_pid_in[0] = (uint8_t)found;
    memcpy(new_pid_in + 1, m_new, 32);
    H(new_pid_in, 33, new_PID);

    /* enc_token = AES_enc(K_GW_AS, [ID_d|ID_AS|ts_auth|pad] | K[0..15] | K[16..31]) */
    uint8_t ts_auth = (uint8_t)(clock_time() / CLOCK_SECOND);
    uint8_t enc_tok[48];
    memset(enc_tok, 0, 48);
    enc_tok[0] = (uint8_t)found;
    enc_tok[1] = (uint8_t)node_id;
    enc_tok[2] = ts_auth;
    memcpy(enc_tok + 16, K_GW_D,      16);
    memcpy(enc_tok + 32, K_GW_D + 16, 16);
    aes_enc(K_GW_AS, enc_tok, 3);

    /* --- Rotate PID and m_curr immediately (no deferral) --- */
    memcpy(cl->PID_old,  cl->PID_curr, 32);
    memcpy(cl->PID_curr, new_PID,      32);
    cl->pid_old_valid = 1;
    memcpy(cl->m_old,  cl->m_curr, 32);
    memcpy(cl->m_curr, m_new,      32);

    /* --- Enqueue token for GW: new_PID(32) | ID_AS(1) | enc_tok(48) --- */
    if (!TOK_FULL()) {
        uint8_t *slot = tok_buf[tok_tail];
        memcpy(slot,      new_PID,  32);
        slot[32] = (uint8_t)node_id;
        memcpy(slot + 33, enc_tok,  48);
        tok_tail = (tok_tail + 1) % MAX_CLIENTS;
        process_post(&as_proc, ev_send_tok, NULL);
    } else {
        printf("AS %u: Token queue full — dropping token for device %u\n",
               node_id, found);
    }

    /* Reply: ts_2(1) | m_H(32) = 33 B */
    uint8_t reply[AUTH_REP_LEN];
    reply[0] = ts_2;
    memcpy(reply + 1, m_H, 32);
    coap_set_payload(resp, reply, AUTH_REP_LEN);

    printf("AS %u: Auth+KeyEx reply to device %u (ts_2=%u). Token queued for GW.\n",
           node_id, found, ts_2);

    print_energest_stats(&cpu_auth_as, &energy_auth_as);
    printf("\n The CPU time and energy at end of authentication for server %u are %f and %f",
           node_id, cpu_auth_as, energy_auth_as);
}

/* --------------------------------------------------------------------------
 * CoAP resource declarations
 * -------------------------------------------------------------------------- */
RESOURCE(res_reg,  "title=\"Reg\"",  res_reg_handler,  NULL, NULL, NULL);
RESOURCE(res_reg1, "title=\"Reg1\"", NULL, res_reg1_handler, NULL, NULL);
RESOURCE(res_auth, "title=\"Auth\"", NULL, res_auth_handler, NULL, NULL);

/* GW token-delivery ACK callback */
static void gw_tok_ack(coap_message_t *resp)
{
    if (!resp)
        printf("AS %u: Token delivery to GW timed out\n", node_id);
    tok_head = (tok_head + 1) % MAX_CLIENTS;
}

/* ==========================================================================
 * Main process
 * ========================================================================== */
PROCESS(as_proc, "AS Revised Anonymity");
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
    printf("AS %u (Revised Anonymity — Single Round): Started.\n", node_id);

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
