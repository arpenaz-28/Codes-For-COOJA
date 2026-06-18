/* ============================================================================
 * as-node.c  —  SD (Sensing Device)   [Banerjee et al., IEEE Access 2019]
 *
 * Maps to entity SD_j in the Banerjee 2019 PUF+anonymity scheme.
 * Node IDs 2–80 in the 100-node COOJA topology.
 *
 * Crypto cost per round (paper Table II):
 *   SD: 6T_h + T_fe  (T_fe simulated as FE_LOOPS chained SHA-256 calls)
 *
 * Resources:
 *   POST /test/dev_info — receive U credentials from GWN
 *     Recv: AES(K_GWN_SD, [ID_U(1)|PID_0(20)|A_U(20)|B_U(20)|pad(3)]) = 64B
 *
 *   POST /test/auth — handle AuthReq from U
 *     Recv: PID_0(20)+M1(20)+M2(20)+M3(20)+M4(20)+T2(1) = 101B
 *     Reply: N1(20)+N2(20)+T3(1) = 41B
 *
 *   POST /test/ack — handle ACK from U
 *     Recv: ACK_val(20)+PID_new(20) = 40B
 *
 *   POST /test/data — receive encrypted sensor data
 *     Recv: PID_new(20)+enc_data(16) = 36B
 * ============================================================================ */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include "contiki.h"
#include "coap-engine.h"
#include "aes.h"
#include "sha256.h"
#include "sys/node-id.h"
#include "random.h"
#include "project-conf.h"

/* --------------------------------------------------------------------------
 * Protocol constants
 * -------------------------------------------------------------------------- */
#define HASH_LEN       20
#define RAND_LEN       20
#define FE_LOOPS        8   /* iterations for T_fe simulation */

#define DEV_INFO_LEN   64   /* AES-padded credential bundle from GWN */
#define AUTH_REQ_LEN  101
#define AUTH_REP_LEN   41
#define ACK_MSG_LEN    40
#define DATA_MSG_LEN   36
#define MAX_DEVICES   130

/* --------------------------------------------------------------------------
 * AES key for secure channel with GWN
 * -------------------------------------------------------------------------- */
static const uint8_t K_GWN_SD[16] = {
    0x42,0x61,0x6E,0x65,0x72,0x6A,0x65,0x65,
    0x53,0x44,0x4B,0x65,0x79,0x00,0x00,0x00
};

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

/* Fuzzy-extractor simulation: FE_LOOPS chained SHA-256 calls ≈ T_fe cost */
static void fe_sim(const uint8_t *seed, uint16_t slen, uint8_t *out)
{
    uint8_t buf[HASH_LEN];
    H(seed, slen, buf);
    for (int i = 1; i < FE_LOOPS; i++)
        H(buf, HASH_LEN, buf);
    memcpy(out, buf, HASH_LEN);
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

static int ts_fresh(uint8_t recv_ts)
{
    uint8_t now  = (uint8_t)(clock_time() / CLOCK_SECOND);
    int     diff = ((int)now - (int)recv_ts + 256) % 256;
    return (diff < FRESHNESS_WINDOW) || (diff > 256 - FRESHNESS_WINDOW);
}

/* --------------------------------------------------------------------------
 * Per-user credential store
 * -------------------------------------------------------------------------- */
typedef struct {
    uint8_t  ID_U;
    uint8_t  PID_0[HASH_LEN];   /* initial pseudonym */
    uint8_t  A_U[HASH_LEN];     /* auth key          */
    uint8_t  B_U[HASH_LEN];     /* binding key       */
    uint8_t  SK[HASH_LEN];      /* session key       */
    uint8_t  PID_new[HASH_LEN]; /* updated pseudonym */
    uint8_t  ACK_expected[HASH_LEN];
    uint8_t  DID[HASH_LEN];     /* H(PID_0 || A_U)  */
    uint8_t  registered;
    uint8_t  authenticated;
} sd_user_t;

static sd_user_t users[MAX_DEVICES];

static sd_user_t *find_by_pid0(const uint8_t *pid0)
{
    for (int i = 1; i < MAX_DEVICES; i++)
        if (users[i].registered &&
            memcmp(users[i].PID_0, pid0, HASH_LEN) == 0)
            return &users[i];
    return NULL;
}

static sd_user_t *find_by_pid_new(const uint8_t *pid_new)
{
    for (int i = 1; i < MAX_DEVICES; i++)
        if (users[i].registered &&
            memcmp(users[i].PID_new, pid_new, HASH_LEN) == 0)
            return &users[i];
    return NULL;
}

/* ==========================================================================
 * Resource: POST /test/dev_info — receive U credentials from GWN
 * Payload: AES(K_GWN_SD, [ID_U(1)|PID_0(20)|A_U(20)|B_U(20)|pad(3)]) = 64B
 * ========================================================================== */
static void res_devinfo_handler(coap_message_t *req, coap_message_t *resp,
                                uint8_t *buf, uint16_t ps, int32_t *off)
{
    const uint8_t *chunk;
    if (coap_get_payload(req, &chunk) != DEV_INFO_LEN) return;

    uint8_t plain[DEV_INFO_LEN];
    memcpy(plain, chunk, DEV_INFO_LEN);
    aes_dec(K_GWN_SD, plain, 4);

    uint8_t id_u = plain[0];
    if (id_u == 0 || id_u >= MAX_DEVICES) return;

    users[id_u].ID_U = id_u;
    memcpy(users[id_u].PID_0, plain + 1,              HASH_LEN);
    memcpy(users[id_u].A_U,   plain + 1 + HASH_LEN,   HASH_LEN);
    memcpy(users[id_u].B_U,   plain + 1 + 2*HASH_LEN, HASH_LEN);
    users[id_u].registered    = 1;
    users[id_u].authenticated = 0;

    printf("SD %u: Stored credentials for U %u. PID_0=%02x%02x%02x\n",
           node_id, id_u,
           users[id_u].PID_0[0], users[id_u].PID_0[1], users[id_u].PID_0[2]);

    const char *ok = "OK";
    coap_set_payload(resp, (const uint8_t *)ok, 2);
}

/* ==========================================================================
 * Resource: POST /test/auth — handle AuthReq from U
 *
 * SD's crypto load: 6T_h + T_fe (paper Table II).
 *
 * Recv:  PID_0(20)+M1(20)+M2(20)+M3(20)+M4(20)+T2(1) = 101B
 * Reply: N1(20)+N2(20)+T3(1) = 41B
 *
 * Steps:
 *   T_fe: fe_sim(R_SD || B_U)         — fuzzy-extractor simulation
 *   hash 1: R_SD = H(node_id || A_U)  — simulated PUF
 *   hash 2: DID* = H(PID_0 || A_U)
 *   hash 3: verify M2* = H(DID*||n_U*) == M2
 *   hash 4: SK = H(n_U* || n_S || DID*)
 *   hash 5: N1 = H(n_S || SK)
 *   hash 6: PID_new = H(PID_0 || SK)
 * ========================================================================== */
static void res_auth_handler(coap_message_t *req, coap_message_t *resp,
                             uint8_t *buf, uint16_t ps, int32_t *off)
{
    const uint8_t *chunk;
    int len = coap_get_payload(req, &chunk);
    if (len < AUTH_REQ_LEN) return;

    uint8_t recv_PID_0[HASH_LEN], recv_M1[HASH_LEN];
    uint8_t recv_M2[HASH_LEN],    recv_M3[RAND_LEN];
    uint8_t recv_M4[HASH_LEN];
    uint8_t T2;

    memcpy(recv_PID_0, chunk,              HASH_LEN);
    memcpy(recv_M1,    chunk + HASH_LEN,   HASH_LEN);
    memcpy(recv_M2,    chunk + 2*HASH_LEN, HASH_LEN);
    memcpy(recv_M3,    chunk + 3*HASH_LEN, RAND_LEN);
    memcpy(recv_M4,    chunk + 4*HASH_LEN, HASH_LEN);
    T2 = chunk[5*HASH_LEN];

    /* Timestamp check */
    if (!ts_fresh(T2)) {
        printf("SD %u: Auth — stale timestamp\n", node_id);
        return;
    }

    /* Lookup user by PID_0 */
    sd_user_t *usr = find_by_pid0(recv_PID_0);
    if (!usr) {
        printf("SD %u: Auth — PID_0 not found\n", node_id);
        return;
    }

    /* hash 1: R_SD = H(node_id || A_U)  — simulated PUF response */
    uint8_t puf_in[1 + HASH_LEN];
    puf_in[0] = (uint8_t)node_id;
    memcpy(puf_in + 1, usr->A_U, HASH_LEN);
    uint8_t R_SD[HASH_LEN];
    H(puf_in, 1 + HASH_LEN, R_SD);

    /* T_fe: fe_sim(R_SD || B_U)  — fuzzy-extractor simulation */
    uint8_t fe_in[HASH_LEN + HASH_LEN];
    memcpy(fe_in,          R_SD,    HASH_LEN);
    memcpy(fe_in + HASH_LEN, usr->B_U, HASH_LEN);
    uint8_t fe_out[HASH_LEN];
    fe_sim(fe_in, 2*HASH_LEN, fe_out);
    (void)fe_out; /* binds SD's PUF into session; not sent */

    /* hash 2: DID* = H(PID_0 || A_U) */
    uint8_t did_in[HASH_LEN + HASH_LEN];
    memcpy(did_in,          recv_PID_0, HASH_LEN);
    memcpy(did_in + HASH_LEN, usr->A_U,   HASH_LEN);
    uint8_t DID[HASH_LEN];
    H(did_in, 2*HASH_LEN, DID);
    memcpy(usr->DID, DID, HASH_LEN);

    /* Recover n_U*: M3 = n_U ⊕ DID  →  n_U* = M3 ⊕ DID* */
    uint8_t n_U_star[RAND_LEN];
    for (int i = 0; i < RAND_LEN; i++)
        n_U_star[i] = recv_M3[i] ^ DID[i];

    /* hash 3: verify M2* = H(DID* || n_U*) */
    uint8_t m2_in[HASH_LEN + RAND_LEN];
    memcpy(m2_in,           DID,      HASH_LEN);
    memcpy(m2_in + HASH_LEN, n_U_star, RAND_LEN);
    uint8_t M2_star[HASH_LEN];
    H(m2_in, HASH_LEN + RAND_LEN, M2_star);

    if (memcmp(M2_star, recv_M2, HASH_LEN) != 0) {
        printf("SD %u: Auth failed — M2 mismatch for U %u\n", node_id, usr->ID_U);
        return;
    }

    /* Verify M4: H(A_U || n_U*) == recv_M4 */
    uint8_t m4_in[HASH_LEN + RAND_LEN];
    memcpy(m4_in,           usr->A_U, HASH_LEN);
    memcpy(m4_in + RAND_LEN, n_U_star, RAND_LEN);
    uint8_t M4_star[HASH_LEN];
    H(m4_in, HASH_LEN + RAND_LEN, M4_star);

    if (memcmp(M4_star, recv_M4, HASH_LEN) != 0) {
        printf("SD %u: Auth failed — M4 mismatch for U %u\n", node_id, usr->ID_U);
        return;
    }

    /* Generate n_S */
    uint8_t n_S[RAND_LEN];
    gen_random(n_S, RAND_LEN);

    /* hash 4: SK = H(n_U* || n_S || DID*) */
    uint8_t sk_in[RAND_LEN + RAND_LEN + HASH_LEN];
    memcpy(sk_in,               n_U_star, RAND_LEN);
    memcpy(sk_in + RAND_LEN,    n_S,      RAND_LEN);
    memcpy(sk_in + 2*RAND_LEN,  DID,      HASH_LEN);
    H(sk_in, 2*RAND_LEN + HASH_LEN, usr->SK);

    /* hash 5: N1 = H(n_S || SK) */
    uint8_t n1_in[RAND_LEN + HASH_LEN];
    memcpy(n1_in,          n_S,     RAND_LEN);
    memcpy(n1_in + RAND_LEN, usr->SK, HASH_LEN);
    uint8_t N1[HASH_LEN];
    H(n1_in, RAND_LEN + HASH_LEN, N1);

    /* hash 6: PID_new = H(PID_0 || SK) — update pseudonym */
    uint8_t pid_in[HASH_LEN + HASH_LEN];
    memcpy(pid_in,          recv_PID_0, HASH_LEN);
    memcpy(pid_in + HASH_LEN, usr->SK,    HASH_LEN);
    H(pid_in, 2*HASH_LEN, usr->PID_new);

    /* Precompute expected ACK_val = H(SK || PID_new) for ack handler */
    uint8_t ack_in[HASH_LEN + HASH_LEN];
    memcpy(ack_in,          usr->SK,      HASH_LEN);
    memcpy(ack_in + HASH_LEN, usr->PID_new, HASH_LEN);
    H(ack_in, 2*HASH_LEN, usr->ACK_expected);

    /* N2 = n_S ⊕ DID  (U recovers n_S as N2 ⊕ DID) */
    uint8_t N2[RAND_LEN];
    for (int i = 0; i < RAND_LEN; i++)
        N2[i] = n_S[i] ^ DID[i];

    uint8_t T3 = (uint8_t)(clock_time() / CLOCK_SECOND);

    /* Build reply: N1(20)+N2(20)+T3(1) = 41B */
    uint8_t reply[AUTH_REP_LEN];
    memcpy(reply,              N1, HASH_LEN);
    memcpy(reply + HASH_LEN,   N2, RAND_LEN);
    reply[2*HASH_LEN] = T3;
    coap_set_payload(resp, reply, AUTH_REP_LEN);

    printf("SD %u: AuthRep sent to U %u. SK=%02x%02x%02x\n",
           node_id, usr->ID_U, usr->SK[0], usr->SK[1], usr->SK[2]);
}

/* ==========================================================================
 * Resource: POST /test/ack — handle ACK from U
 * Recv: ACK_val(20)+PID_new(20) = 40B
 * ========================================================================== */
static void res_ack_handler(coap_message_t *req, coap_message_t *resp,
                            uint8_t *buf, uint16_t ps, int32_t *off)
{
    const uint8_t *chunk;
    if (coap_get_payload(req, &chunk) < ACK_MSG_LEN) return;

    uint8_t recv_ack[HASH_LEN], recv_pid_new[HASH_LEN];
    memcpy(recv_ack,     chunk,          HASH_LEN);
    memcpy(recv_pid_new, chunk + HASH_LEN, HASH_LEN);

    sd_user_t *usr = find_by_pid_new(recv_pid_new);
    if (!usr) {
        printf("SD %u: ACK rejected — PID_new not found\n", node_id);
        return;
    }

    if (memcmp(recv_ack, usr->ACK_expected, HASH_LEN) != 0) {
        printf("SD %u: ACK verification failed for U %u\n", node_id, usr->ID_U);
        return;
    }

    usr->authenticated = 1;
    printf("SD %u: Mutual auth complete for U %u. SK established.\n",
           node_id, usr->ID_U);

    const char *ok = "OK";
    coap_set_payload(resp, (const uint8_t *)ok, 2);
}

/* ==========================================================================
 * Resource: POST /test/data — receive AES-encrypted sensor data
 * Recv: PID_new(20) + AES_SK(data(16)) = 36B
 * ========================================================================== */
static void res_data_handler(coap_message_t *req, coap_message_t *resp,
                             uint8_t *buf, uint16_t ps, int32_t *off)
{
    const uint8_t *chunk;
    if (coap_get_payload(req, &chunk) < DATA_MSG_LEN) return;

    uint8_t recv_pid_new[HASH_LEN], enc_data[16];
    memcpy(recv_pid_new, chunk,          HASH_LEN);
    memcpy(enc_data,     chunk + HASH_LEN, 16);

    sd_user_t *usr = find_by_pid_new(recv_pid_new);
    if (!usr || !usr->authenticated) {
        printf("SD %u: Data rejected — not authenticated\n", node_id);
        return;
    }

    struct AES_ctx actx;
    AES_init_ctx(&actx, usr->SK);
    AES_ECB_decrypt(&actx, enc_data);

    printf("SD %u: Data from U %u received.\n", node_id, usr->ID_U);

    uint8_t reply[1] = {0};
    coap_set_payload(resp, reply, 1);
}

/* --------------------------------------------------------------------------
 * CoAP resource declarations
 * -------------------------------------------------------------------------- */
RESOURCE(res_devinfo, "title=\"DevInfo\"", NULL, res_devinfo_handler, NULL, NULL);
RESOURCE(res_auth,    "title=\"Auth\"",    NULL, res_auth_handler,    NULL, NULL);
RESOURCE(res_ack,     "title=\"Ack\"",     NULL, res_ack_handler,     NULL, NULL);
RESOURCE(res_data,    "title=\"Data\"",    NULL, res_data_handler,    NULL, NULL);

/* ==========================================================================
 * Main process
 * ========================================================================== */
PROCESS(sd_proc, "SD (Sensing Device) — Banerjee 2019");
AUTOSTART_PROCESSES(&sd_proc);

PROCESS_THREAD(sd_proc, ev, data)
{
    PROCESS_BEGIN();

    memset(users, 0, sizeof(users));

    coap_engine_init();
    coap_activate_resource(&res_devinfo, "test/dev_info");
    coap_activate_resource(&res_auth,    "test/auth");
    coap_activate_resource(&res_ack,     "test/ack");
    coap_activate_resource(&res_data,    "test/data");

    printf("SD %u: Started (Sensing Device, Banerjee 2019).\n", node_id);

    while (1) {
        PROCESS_WAIT_EVENT();
    }

    PROCESS_END();
}
