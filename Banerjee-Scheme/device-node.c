/* ============================================================================
 * device-node.c  —  U (User)   [Banerjee et al., IEEE Access 2019]
 *
 * Maps to entity U_i in the Banerjee 2019 PUF+anonymity scheme.
 * Node IDs 81–100 in the 100-node COOJA topology.
 *
 * Crypto cost per round (paper Table II):
 *   U: 17T_h + T_fe  (T_fe simulated as 8 chained SHA-256 calls)
 *
 * State machine:
 *   reg == 0            → Registration with GWN  [ENROLL_ENERGY]
 *   reg == 1, count < 1 → Auth + Key-exchange with SD  [AUTH + KEYEX_ENERGY]
 *   count >= 1          → Data loop
 *
 * Registration:
 *   U computes H1 = H(PW || r_U), H2 = H(ID_U || H1), sends to GWN.
 *   GWN replies with {PID_0, A_U, B_U} — initial pseudonym + auth keys.
 *   GWN forwards U credentials to the assigned SD.
 *
 * Authentication (Banerjee §IV-C, simplified for COOJA):
 *   U generates n_U, simulates PUF + FE, builds {M1..M6}, sends auth req.
 *   SD verifies, uses FE, computes SK, replies {N1, N2, T3}.
 *   U verifies N1, derives SK, updates pseudonym PID_new, sends ACK.
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
#include "net/ipv6/uip-ds6.h"
#include "sys/node-id.h"
#include "random.h"
#include "project-conf.h"
#include "sys/energest.h"

/* --------------------------------------------------------------------------
 * Protocol constants
 * -------------------------------------------------------------------------- */
#define HASH_LEN       20
#define RAND_LEN       20
#define FE_LOOPS        8   /* SHA-256 iterations to simulate T_fe cost */

/* SD selection — two modes depending on project-conf.h:
 *   N_SD_ACTIVE defined  → AS-variation: round-robin across N_SD_ACTIVE SDs
 *                          (SDs have IDs SD_BASE_ID … SD_BASE_ID+N_SD_ACTIVE-1)
 *   SD_SPLIT_ID defined  → network-variation: binary split by node_id
 */
static inline uint8_t get_my_sd(void)
{
#ifdef N_SD_ACTIVE
    return (uint8_t)(SD_BASE_ID + ((node_id - FIRST_DEV_ID) % N_SD_ACTIVE));
#else
    return (node_id < SD_SPLIT_ID) ? (uint8_t)SD1_NODE_ID : (uint8_t)SD2_NODE_ID;
#endif
}

/* Message sizes */
#define REG_REQ_LEN    48   /* AES: ID(1)+H1(20)+r_U(20)+T1(1)+pad(6) = 3 blocks */
#define REG_REP_LEN    64   /* AES: PID_0(20)+A_U(20)+B_U(20)+pad(4) = 4 blocks  */
#define AUTH_REQ_LEN  101   /* PID_0(20)+M1(20)+M2(20)+M3(20)+M4(20)+T2(1)       */
#define AUTH_REP_LEN   41   /* N1(20)+N2(20)+T3(1)                                */
#define ACK_MSG_LEN    40   /* ACK_val(20)+PID_new(20)                            */
#define DATA_MSG_LEN   36   /* PID_new(20)+enc_data(16)                           */

/* --------------------------------------------------------------------------
 * AES key for secure registration channel with GWN
 * -------------------------------------------------------------------------- */
static const uint8_t K_GWN_U[16] = {
    0x42,0x61,0x6E,0x65,0x72,0x6A,0x65,0x65,
    0x55,0x73,0x65,0x72,0x4B,0x65,0x79,0x00
};

/* --------------------------------------------------------------------------
 * U state
 * -------------------------------------------------------------------------- */
static uint8_t ID_U;
static uint8_t r_U[RAND_LEN];
static uint8_t PID_0[HASH_LEN];   /* initial pseudonym from GWN */
static uint8_t A_U[HASH_LEN];     /* auth key from GWN          */
static uint8_t B_U[HASH_LEN];     /* binding key from GWN       */
static uint8_t n_U[RAND_LEN];     /* per-auth nonce             */
static uint8_t SK[HASH_LEN];      /* established session key    */
static uint8_t PID_new[HASH_LEN]; /* updated pseudonym          */
static uint8_t ACK_val[HASH_LEN]; /* ACK payload                */
static uint8_t auth_ok = 0;

static uint8_t reg   = 0;
static uint8_t count = 0;

/* --------------------------------------------------------------------------
 * Energest helpers  (identical methodology to other schemes)
 * -------------------------------------------------------------------------- */
#define CURRENT_CPU    1.8e-3
#define CURRENT_LPM    0.0545e-3
#define CURRENT_TX     17.4e-3
#define CURRENT_RX     18.8e-3
#define SUPPLY_VOLTAGE 3.0

double cpu_reg_snap, energy_reg_snap;
double cpu_auth_snap, energy_auth_snap;
double cpu_enroll_before, energy_enroll_before;
double cpu_enroll_after,  energy_enroll_after;
double cpu_keyex_before,  energy_keyex_before;
double cpu_keyex_after,   energy_keyex_after;

static uint8_t enroll_pending = 0;
static uint8_t auth_pending   = 0;
static uint8_t keyex_pending  = 0;

static void print_energest_stats(double *seconds_cpu, double *total_energy)
{
    energest_flush();
    unsigned long cpu_ticks = energest_type_time(ENERGEST_TYPE_CPU);
    unsigned long lpm_ticks = energest_type_time(ENERGEST_TYPE_LPM);
    unsigned long tx_ticks  = energest_type_time(ENERGEST_TYPE_TRANSMIT);
    unsigned long rx_ticks  = energest_type_time(ENERGEST_TYPE_LISTEN);

    *seconds_cpu        = cpu_ticks / (double)ENERGEST_SECOND;
    double seconds_lpm  = lpm_ticks / (double)ENERGEST_SECOND;
    double seconds_tx   = tx_ticks  / (double)ENERGEST_SECOND;
    double seconds_rx   = rx_ticks  / (double)ENERGEST_SECOND;

    double energy_cpu = *seconds_cpu * CURRENT_CPU * SUPPLY_VOLTAGE;
    double energy_lpm = seconds_lpm  * CURRENT_LPM * SUPPLY_VOLTAGE;
    double energy_tx  = seconds_tx   * CURRENT_TX  * SUPPLY_VOLTAGE;
    double energy_rx  = seconds_rx   * CURRENT_RX  * SUPPLY_VOLTAGE;

    *total_energy = energy_cpu + energy_lpm + energy_tx + energy_rx;
}

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

/* --------------------------------------------------------------------------
 * CoAP endpoints
 * -------------------------------------------------------------------------- */
static coap_endpoint_t ep_gwn, ep_sd;
static coap_message_t  request[1];

static void discover_endpoints(void)
{
    uip_ipaddr_t a;
    /* Registration → GWN (node 1) */
    uint8_t gwn_id = (uint8_t)GWN_NODE_ID;
    uip_ip6addr_u8(&a, 0xfd,0,0,0,0,0,0,0,
                   0x02,gwn_id,0,gwn_id,0,gwn_id,0,gwn_id);
    uip_ipaddr_copy(&ep_gwn.ipaddr, &a);
    ep_gwn.port = UIP_HTONS(COAP_DEFAULT_PORT);

    /* Authentication → assigned SD (Sensing Device) */
    uint8_t sd_id = get_my_sd();
    uip_ip6addr_u8(&a, 0xfd,0,0,0,0,0,0,0,
                   0x02,sd_id,0,sd_id,0,sd_id,0,sd_id);
    uip_ipaddr_copy(&ep_sd.ipaddr, &a);
    ep_sd.port = UIP_HTONS(COAP_DEFAULT_PORT);
}

/* ==========================================================================
 * CoAP response handlers
 * ========================================================================== */

/* Registration reply from GWN — receives {PID_0, A_U, B_U} */
static void client_reg_handler(coap_message_t *resp)
{
    const uint8_t *chunk;
    if (!resp || coap_get_payload(resp, &chunk) < REG_REP_LEN) {
        printf("U %u: Reg reply dropped\n", ID_U);
        return;
    }
    uint8_t plain[REG_REP_LEN];
    memcpy(plain, chunk, REG_REP_LEN);
    aes_dec(K_GWN_U, plain, 4);

    memcpy(PID_0, plain,              HASH_LEN);
    memcpy(A_U,   plain + HASH_LEN,   HASH_LEN);
    memcpy(B_U,   plain + 2*HASH_LEN, HASH_LEN);
    printf("U %u: Registered. PID_0=%02x%02x%02x A_U=%02x%02x%02x\n",
           ID_U, PID_0[0],PID_0[1],PID_0[2], A_U[0],A_U[1],A_U[2]);
}

/* Auth reply from SD: {N1(20) | N2(20) | T3(1)}  (41 bytes)
 *
 * Post-reply computation (hashes 7–11 of U's 17T_h):
 *   n_S  = N2 ⊕ DID          [XOR]           hash  7: SK = H(n_U||n_S||DID)
 *   hash  8: verify_N1 = H(n_S||SK)
 *   hash  9: PID_new = H(PID_0||SK)
 *   hash 10: ACK_val = H(SK||PID_new)
 *   hash 11: M_ack   = H(ACK_val||A_U)
 */
static uint8_t DID_cached[HASH_LEN];   /* set before request, read in handler */

static void client_auth_handler(coap_message_t *resp)
{
    const uint8_t *chunk;
    if (!resp || coap_get_payload(resp, &chunk) < AUTH_REP_LEN) {
        printf("U %u: Auth reply dropped\n", ID_U);
        auth_ok = 0;
        return;
    }

    uint8_t N1[HASH_LEN], N2[HASH_LEN];
    uint8_t T3;
    memcpy(N1, chunk,            HASH_LEN);
    memcpy(N2, chunk + HASH_LEN, HASH_LEN);
    T3 = chunk[2 * HASH_LEN];

    /* Check timestamp freshness */
    uint8_t now = (uint8_t)(clock_time() / CLOCK_SECOND);
    int diff = ((int)now - (int)T3 + 256) % 256;
    if (!((diff < FRESHNESS_WINDOW) || (diff > 256 - FRESHNESS_WINDOW))) {
        printf("U %u: Auth reply stale (diff=%d)\n", ID_U, diff);
        auth_ok = 0;
        return;
    }

    /* Recover n_S: N2 = n_S ⊕ DID  →  n_S = N2 ⊕ DID */
    uint8_t n_S[RAND_LEN];
    for (int i = 0; i < RAND_LEN; i++)
        n_S[i] = N2[i] ^ DID_cached[i];

    /* hash 7: SK = H(n_U || n_S || DID) */
    uint8_t sk_in[RAND_LEN + RAND_LEN + HASH_LEN];
    memcpy(sk_in,                      n_U,        RAND_LEN);
    memcpy(sk_in + RAND_LEN,           n_S,        RAND_LEN);
    memcpy(sk_in + 2*RAND_LEN,         DID_cached, HASH_LEN);
    H(sk_in, 2*RAND_LEN + HASH_LEN, SK);

    /* hash 8: verify_N1 = H(n_S || SK) */
    uint8_t n1_in[RAND_LEN + HASH_LEN];
    memcpy(n1_in,          n_S, RAND_LEN);
    memcpy(n1_in + RAND_LEN, SK,  HASH_LEN);
    uint8_t verify_N1[HASH_LEN];
    H(n1_in, RAND_LEN + HASH_LEN, verify_N1);

    if (memcmp(verify_N1, N1, HASH_LEN) != 0) {
        printf("U %u: Auth failed — N1 mismatch\n", ID_U);
        auth_ok = 0;
        return;
    }

    /* hash 9: PID_new = H(PID_0 || SK) */
    uint8_t pid_in[HASH_LEN + HASH_LEN];
    memcpy(pid_in,          PID_0, HASH_LEN);
    memcpy(pid_in + HASH_LEN, SK,    HASH_LEN);
    H(pid_in, 2*HASH_LEN, PID_new);

    /* hash 10: ACK_val = H(SK || PID_new) */
    uint8_t ack_in[HASH_LEN + HASH_LEN];
    memcpy(ack_in,          SK,      HASH_LEN);
    memcpy(ack_in + HASH_LEN, PID_new, HASH_LEN);
    H(ack_in, 2*HASH_LEN, ACK_val);

    /* hash 11: M_ack = H(ACK_val || A_U) (integrity tag, not sent) */
    uint8_t mack_in[HASH_LEN + HASH_LEN];
    memcpy(mack_in,          ACK_val, HASH_LEN);
    memcpy(mack_in + HASH_LEN, A_U,    HASH_LEN);
    uint8_t M_ack[HASH_LEN];
    H(mack_in, 2*HASH_LEN, M_ack);
    (void)M_ack; /* used in post-ack hashes below */

    auth_ok = 1;
    printf("U %u: Auth OK. SK=%02x%02x%02x PID_new=%02x%02x%02x\n",
           ID_U, SK[0],SK[1],SK[2], PID_new[0],PID_new[1],PID_new[2]);
}

/* ACK confirmation from SD */
static void client_ack_handler(coap_message_t *resp)
{
    if (!resp)
        printf("U %u: ACK delivery failed\n", ID_U);
    else
        printf("U %u: Mutual auth + key exchange complete\n", ID_U);
}

/* Data acknowledgement from SD */
static void client_data_handler(coap_message_t *resp)
{
    if (!resp)
        printf("U %u: Data ACK missing\n", ID_U);
}

/* ==========================================================================
 * Main process
 * ========================================================================== */
PROCESS(user_proc, "U (User) — Banerjee 2019");
AUTOSTART_PROCESSES(&user_proc);
static struct etimer et;

PROCESS_THREAD(user_proc, ev, data)
{
    PROCESS_BEGIN();

    ID_U = (uint8_t)node_id;
    discover_endpoints();

    /* Staggered start — spread device activations to reduce MAC collisions */
    etimer_set(&et, CLOCK_SECOND * (5 + node_id));

    while (1) {
        PROCESS_YIELD();
        if (!etimer_expired(&et)) continue;

        /* ── deferred energy prints (same ordering as other schemes) ── */
        if (enroll_pending) {
            printf("ENROLL_ENERGY|%u|cpu_s=%f|energy_j=%f\n",
                   ID_U,
                   cpu_enroll_after - cpu_enroll_before,
                   energy_enroll_after - energy_enroll_before);
            enroll_pending = 0;
        }
        if (auth_pending) {
            printf("AUTH_ENERGY|%u|cpu_ticks=0|energy_ticks=0|cpu_s=%f|energy_j=%f\n",
                   ID_U,
                   cpu_auth_snap - cpu_reg_snap,
                   energy_auth_snap - energy_reg_snap);
            auth_pending = 0;
        }
        if (keyex_pending) {
            printf("KEYEX_ENERGY|%u|cpu_s=%f|energy_j=%f\n",
                   ID_U,
                   cpu_keyex_after - cpu_keyex_before,
                   energy_keyex_after - energy_keyex_before);
            keyex_pending = 0;
        }

        /* ================================================================
         * PHASE 1 — REGISTRATION  (reg == 0)
         *
         * U computes H1 = H(PW||r_U), H2 = H(ID_U||H1) — 2 hashes.
         * Sends AES-encrypted {ID_U, H1, r_U, T1} to GWN.
         * Receives AES-encrypted {PID_0, A_U, B_U} from GWN.
         * ================================================================ */
        if (reg == 0) {
            print_energest_stats(&cpu_enroll_before, &energy_enroll_before);

            gen_random(r_U, RAND_LEN);

            /* Simulated password (fixed per device for reproducibility) */
            uint8_t PW[HASH_LEN];
            memset(PW, (uint8_t)(ID_U * 7), HASH_LEN);

            /* H1 = H(PW || r_U) */
            uint8_t h1_in[HASH_LEN + RAND_LEN];
            memcpy(h1_in,           PW,  HASH_LEN);
            memcpy(h1_in + HASH_LEN, r_U, RAND_LEN);
            uint8_t H1[HASH_LEN];
            H(h1_in, HASH_LEN + RAND_LEN, H1);

            /* H2 = H(ID_U || H1) — not sent, stored for binding */
            uint8_t h2_in[1 + HASH_LEN];
            h2_in[0] = ID_U;
            memcpy(h2_in + 1, H1, HASH_LEN);
            uint8_t H2[HASH_LEN];
            H(h2_in, 1 + HASH_LEN, H2);
            (void)H2;

            /* Build request: ID_U(1)+H1(20)+r_U(20)+T1(1)+pad(6) = 48B */
            uint8_t req[REG_REQ_LEN];
            memset(req, 0, REG_REQ_LEN);
            req[0] = ID_U;
            memcpy(req + 1,  H1,  HASH_LEN);
            memcpy(req + 21, r_U, RAND_LEN);
            req[41] = (uint8_t)(clock_time() / CLOCK_SECOND);
            aes_enc(K_GWN_U, req, 3);

            coap_init_message(request, COAP_TYPE_CON, COAP_POST, 0);
            coap_set_header_uri_path(request, "test/reg");
            coap_set_payload(request, req, REG_REQ_LEN);
            printf("U %u: Sending registration to GWN\n", ID_U);
            COAP_BLOCKING_REQUEST(&ep_gwn, request, client_reg_handler);

            print_energest_stats(&cpu_enroll_after, &energy_enroll_after);
            enroll_pending = 1;
            reg = 1;

        /* ================================================================
         * PHASE 2 — AUTHENTICATION + KEY EXCHANGE  (reg == 1, count < 1)
         *
         * U's crypto load: 17T_h + T_fe (paper Table II).
         *   Hashes 1–6  : pre-request computation
         *   T_fe        : fe_sim() = FE_LOOPS SHA-256 calls
         *   Hashes 7–11 : post-reply, pre-ACK  (in client_auth_handler)
         *   Hashes 12–17: post-ACK binding
         * ================================================================ */
        } else if (count < 1) {

            print_energest_stats(&cpu_reg_snap, &energy_reg_snap);

            auth_ok = 0;
            gen_random(n_U, RAND_LEN);
            uint8_t T2 = (uint8_t)(clock_time() / CLOCK_SECOND);

            /* hash 1: R_U = H(ID_U || B_U)  — simulated PUF response */
            uint8_t puf_in[1 + HASH_LEN];
            puf_in[0] = ID_U;
            memcpy(puf_in + 1, B_U, HASH_LEN);
            uint8_t R_U[HASH_LEN];
            H(puf_in, 1 + HASH_LEN, R_U);

            /* T_fe: fe_sim(R_U || B_U)  — fuzzy-extractor simulation */
            uint8_t fe_in[HASH_LEN + HASH_LEN];
            memcpy(fe_in,          R_U, HASH_LEN);
            memcpy(fe_in + HASH_LEN, B_U, HASH_LEN);
            uint8_t fe_out[HASH_LEN];
            fe_sim(fe_in, 2 * HASH_LEN, fe_out);

            /* hash 2: DID = H(PID_0 || A_U) */
            uint8_t did_in[HASH_LEN + HASH_LEN];
            memcpy(did_in,          PID_0, HASH_LEN);
            memcpy(did_in + HASH_LEN, A_U,   HASH_LEN);
            H(did_in, 2*HASH_LEN, DID_cached);

            /* hash 3: M2 = H(DID || n_U) */
            uint8_t m2_in[HASH_LEN + RAND_LEN];
            memcpy(m2_in,           DID_cached, HASH_LEN);
            memcpy(m2_in + HASH_LEN, n_U,        RAND_LEN);
            uint8_t M2[HASH_LEN];
            H(m2_in, HASH_LEN + RAND_LEN, M2);

            /* hash 4: M4 = H(A_U || n_U) */
            uint8_t m4_in[HASH_LEN + RAND_LEN];
            memcpy(m4_in,           A_U, HASH_LEN);
            memcpy(m4_in + RAND_LEN, n_U, RAND_LEN);
            uint8_t M4[HASH_LEN];
            H(m4_in, HASH_LEN + RAND_LEN, M4);

            /* hash 5: M5 = H(fe_out || DID) */
            uint8_t m5_in[HASH_LEN + HASH_LEN];
            memcpy(m5_in,          fe_out,     HASH_LEN);
            memcpy(m5_in + HASH_LEN, DID_cached, HASH_LEN);
            uint8_t M5[HASH_LEN];
            H(m5_in, 2*HASH_LEN, M5);

            /* hash 6: M6 = H(M2 || M5) */
            uint8_t m6_in[HASH_LEN + HASH_LEN];
            memcpy(m6_in,          M2, HASH_LEN);
            memcpy(m6_in + HASH_LEN, M5, HASH_LEN);
            uint8_t M6[HASH_LEN];
            H(m6_in, 2*HASH_LEN, M6);
            (void)M6;

            /* M1 = PID_0 ⊕ ID_SD  (pseudonym masking) */
            uint8_t sd_id = get_my_sd();
            uint8_t M1[HASH_LEN];
            memcpy(M1, PID_0, HASH_LEN);
            M1[0] ^= sd_id;   /* XOR ID_SD into first byte */

            /* M3 = n_U ⊕ DID */
            uint8_t M3[RAND_LEN];
            for (int i = 0; i < RAND_LEN; i++)
                M3[i] = n_U[i] ^ DID_cached[i];

            /* Build auth request:
             * PID_0(20)+M1(20)+M2(20)+M3(20)+M4(20)+T2(1) = 101B */
            uint8_t auth_req[AUTH_REQ_LEN];
            memcpy(auth_req,               PID_0, HASH_LEN);
            memcpy(auth_req + HASH_LEN,    M1,    HASH_LEN);
            memcpy(auth_req + 2*HASH_LEN,  M2,    HASH_LEN);
            memcpy(auth_req + 3*HASH_LEN,  M3,    RAND_LEN);
            memcpy(auth_req + 4*HASH_LEN,  M4,    HASH_LEN);
            auth_req[5*HASH_LEN] = T2;

            /* KEYEX_BEFORE — communication phase starts here */
            print_energest_stats(&cpu_keyex_before, &energy_keyex_before);

            coap_init_message(request, COAP_TYPE_CON, COAP_POST, 1);
            coap_set_header_uri_path(request, "test/auth");
            coap_set_payload(request, auth_req, AUTH_REQ_LEN);
            printf("U %u: Sending AuthReq to SD %u\n", ID_U, sd_id);
            COAP_BLOCKING_REQUEST(&ep_sd, request, client_auth_handler);

            if (auth_ok) {
                /* Send ACK: {ACK_val(20) | PID_new(20)} = 40B */
                uint8_t ack_msg[ACK_MSG_LEN];
                memcpy(ack_msg,          ACK_val,  HASH_LEN);
                memcpy(ack_msg + HASH_LEN, PID_new, HASH_LEN);

                coap_init_message(request, COAP_TYPE_CON, COAP_POST, 2);
                coap_set_header_uri_path(request, "test/ack");
                coap_set_payload(request, ack_msg, ACK_MSG_LEN);
                printf("U %u: Sending ACK\n", ID_U);
                COAP_BLOCKING_REQUEST(&ep_sd, request, client_ack_handler);

                /* KEYEX_AFTER — key establishment complete */
                print_energest_stats(&cpu_keyex_after, &energy_keyex_after);
                keyex_pending = 1;

                /* ── hashes 12–17: post-ACK session binding ── */
                /* hash 12: M9 = H(ACK_val || B_U) */
                uint8_t m9_in[HASH_LEN + HASH_LEN];
                memcpy(m9_in,          ACK_val, HASH_LEN);
                memcpy(m9_in + HASH_LEN, B_U,    HASH_LEN);
                uint8_t M9[HASH_LEN];
                H(m9_in, 2*HASH_LEN, M9);

                /* hash 13: final_tag = H(M9 || fe_out) */
                uint8_t ft_in[HASH_LEN + HASH_LEN];
                memcpy(ft_in,          M9,     HASH_LEN);
                memcpy(ft_in + HASH_LEN, fe_out, HASH_LEN);
                uint8_t final_tag[HASH_LEN];
                H(ft_in, 2*HASH_LEN, final_tag);

                /* hash 14: final_tag2 = H(final_tag || DID) */
                uint8_t ft2_in[HASH_LEN + HASH_LEN];
                memcpy(ft2_in,          final_tag,  HASH_LEN);
                memcpy(ft2_in + HASH_LEN, DID_cached, HASH_LEN);
                uint8_t final_tag2[HASH_LEN];
                H(ft2_in, 2*HASH_LEN, final_tag2);

                /* hash 15: sess1 = H(final_tag2 || n_U) */
                uint8_t s1_in[HASH_LEN + RAND_LEN];
                memcpy(s1_in,           final_tag2, HASH_LEN);
                memcpy(s1_in + HASH_LEN, n_U,        RAND_LEN);
                uint8_t sess1[HASH_LEN];
                H(s1_in, HASH_LEN + RAND_LEN, sess1);

                /* hash 16: bind1 = H(sess1 || A_U) */
                uint8_t b1_in[HASH_LEN + HASH_LEN];
                memcpy(b1_in,          sess1, HASH_LEN);
                memcpy(b1_in + HASH_LEN, A_U,   HASH_LEN);
                uint8_t bind1[HASH_LEN];
                H(b1_in, 2*HASH_LEN, bind1);

                /* hash 17: bind2 = H(bind1 || PID_0) — finalises session state */
                uint8_t b2_in[HASH_LEN + HASH_LEN];
                memcpy(b2_in,          bind1, HASH_LEN);
                memcpy(b2_in + HASH_LEN, PID_0,  HASH_LEN);
                uint8_t bind2[HASH_LEN];
                H(b2_in, 2*HASH_LEN, bind2);
                (void)bind2;

                /* Data transmission */
                uint8_t data_pkt[DATA_MSG_LEN];
                memcpy(data_pkt, PID_new, HASH_LEN);
                uint8_t sensor_data[16];
                memset(sensor_data, 0, 16);
                sensor_data[0] = ID_U;
                sensor_data[1] = (uint8_t)(clock_time() & 0xFF);
                struct AES_ctx actx;
                AES_init_ctx(&actx, SK);
                AES_ECB_encrypt(&actx, sensor_data);
                memcpy(data_pkt + HASH_LEN, sensor_data, 16);

                coap_init_message(request, COAP_TYPE_CON, COAP_POST, 3);
                coap_set_header_uri_path(request, "test/data");
                coap_set_payload(request, data_pkt, DATA_MSG_LEN);
                printf("U %u: Sending encrypted data\n", ID_U);
                COAP_BLOCKING_REQUEST(&ep_sd, request, client_data_handler);

                count++;
                print_energest_stats(&cpu_auth_snap, &energy_auth_snap);
                auth_pending = 1;
            }

        /* ================================================================
         * DATA LOOP  (count >= 1)
         * ================================================================ */
        } else {
            uint8_t data_pkt[DATA_MSG_LEN];
            memcpy(data_pkt, PID_new, HASH_LEN);
            uint8_t sensor_data[16];
            memset(sensor_data, 0, 16);
            sensor_data[0] = ID_U;
            sensor_data[1] = (uint8_t)(clock_time() & 0xFF);
            struct AES_ctx actx;
            AES_init_ctx(&actx, SK);
            AES_ECB_encrypt(&actx, sensor_data);
            memcpy(data_pkt + HASH_LEN, sensor_data, 16);
            coap_init_message(request, COAP_TYPE_CON, COAP_POST, 3);
            coap_set_header_uri_path(request, "test/data");
            coap_set_payload(request, data_pkt, DATA_MSG_LEN);
            COAP_BLOCKING_REQUEST(&ep_sd, request, client_data_handler);
        }

        etimer_reset(&et);
    }

    PROCESS_END();
}
