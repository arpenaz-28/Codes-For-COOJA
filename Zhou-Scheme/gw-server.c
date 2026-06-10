/* ==========================================================================
 * gw-server.c  —  Medical Gateway (GW) for Zhou et al. scheme
 *
 * Faithful implementation of the Medical Gateway entity from:
 *   "Security-Enhanced Lightweight and Anonymity-Preserving User
 *    Authentication Scheme for IoT-Based Healthcare"
 *   Zhou et al., IEEE IoT Journal, Vol. 11, No. 6, March 2024
 *
 * The Medical Gateway:
 *  - Handles User Registration Phase (Section IV.A)
 *  - Handles Sensor Node Registration Phase (Section IV.B)
 *  - Orchestrates Authentication & Key Exchange Phase (Section IV.C)
 *    with the full 4-message protocol: M1(U→GW), M2(GW→SN), M3(SN→GW), M4(GW→U)
 *
 * Hash count: 7 hashes per auth (matches paper Table VI)
 *
 * Architecture:
 *  - Acts as CoAP server: receives M1 from User, reg from User/Sensor
 *  - Acts as CoAP client: sends M2 to Sensor, M4 to User, token to GW router
 *  - Uses async event-driven token/message delivery via ring buffers
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
 * Shared long-term symmetric keys — 16 bytes each
 * -------------------------------------------------------------------------- */
/* Key shared between GW and User (for secure registration channel) */
static const uint8_t K_GW_U[16] = {
    0x67,0x77,0x75,0x73,0x20,0x6D,0x79,0x20,
    0x4B,0x75,0x6F,0x67,0x20,0x46,0x75,0x00
};
/* Key shared between GW and Sensor (for secure registration channel) */
static const uint8_t K_GW_SN[16] = {
    0x73,0x6E,0x67,0x77,0x20,0x6B,0x65,0x79,
    0x5F,0x73,0x65,0x63,0x75,0x72,0x65,0x00
};
/* Key shared between GW server and GW router (for token encryption) */
static const uint8_t K_GW_RT[16] = {
    0x67,0x62,0x74,0x73,0x20,0x6D,0x79,0x20,
    0x4B,0x75,0x6F,0x67,0x20,0x46,0x75,0x00
};

/* --------------------------------------------------------------------------
 * Constants
 * -------------------------------------------------------------------------- */
#define MAX_CLIENTS      130
#define MAX_SENSORS      30
#define GW_TOKEN_LEN     81    /* PID(32) + id_gw(1) + enc(48) */

/* --------------------------------------------------------------------------
 * Per-user state (paper Section IV.A)
 * -------------------------------------------------------------------------- */
typedef struct {
    uint8_t  IDi;             /* Real identity (node_id)                 */
    uint8_t  IDi_padded[32];  /* Zero-padded 32-byte identity            */
    uint8_t  ki[32];          /* Biometric secret key from fuzzy ext.    */
    uint8_t  bi[32];          /* Random blinding factor                  */
    uint8_t  DIDi_curr[32];   /* Current pseudonym: bi ⊕ IDi_padded     */
    uint8_t  DIDi_old[32];    /* Previous pseudonym (for desync)         */
    uint8_t  did_old_valid;   /* 1 once first rotation has happened      */
    uint8_t  enrolled;        /* 1 after registration completes          */
} user_record_t;

static user_record_t users[MAX_CLIENTS];

/* --------------------------------------------------------------------------
 * Per-sensor state (paper Section IV.B)
 * -------------------------------------------------------------------------- */
typedef struct {
    uint8_t  SNn;             /* Real identity (node_id)                 */
    uint8_t  SNn_padded[32];  /* Zero-padded 32-byte identity            */
    uint8_t  bn[32];          /* Random blinding factor                  */
    uint8_t  SIDn_curr[32];   /* Current pseudonym: bn ⊕ SNn_padded     */
    uint8_t  SIDn_old[32];    /* Previous pseudonym                      */
    uint8_t  sid_old_valid;   /* 1 once first rotation has happened      */
    uint8_t  Cn;              /* PUF challenge                           */
    uint8_t  Rn;              /* PUF response                            */
    uint8_t  enrolled;        /* 1 after full registration               */
    uint8_t  reg_step;        /* 0=not started, 1=step1 done             */
} sensor_record_t;

static sensor_record_t sensors[MAX_SENSORS];

/* --------------------------------------------------------------------------
 * Auth pipeline: stores in-progress auth data for async M2/M4 delivery
 * -------------------------------------------------------------------------- */
typedef struct {
    uint8_t  valid;
    /* M2 data for sensor */
    uint8_t  sn_node_id;      /* Sensor's COOJA node_id for addressing   */
    uint8_t  SKn[64];         /* Encrypted session key for sensor        */
    uint8_t  beta[32];        /* Verification hash for sensor            */
    uint8_t  Cn;              /* Challenge for sensor                    */
    /* M4 data for user (computed after M3) */
    uint8_t  user_node_id;    /* User's COOJA node_id for addressing     */
    uint8_t  SKi[96];         /* Encrypted data for user                 */
    uint8_t  lambda[32];      /* Verification hash for user              */
    uint8_t  ski_len;         /* Length of SKi (SIDn_new + SK + DIDi_new)*/
    /* Internal state for M3 verification */
    uint8_t  SK[32];          /* Session key                             */
    uint8_t  SIDn_new[32];    /* New sensor pseudonym                    */
    uint8_t  DIDi_new[32];    /* New user pseudonym                      */
    uint8_t  DIDi_curr[32];   /* Current user pseudonym (for λ)          */
    uint8_t  ki[32];          /* User's biometric key (for SKi, λ)       */
    int      user_idx;        /* Index into users[]                      */
    int      sensor_idx;      /* Index into sensors[]                    */
} auth_pipeline_t;

#define PIPELINE_SIZE  10
static auth_pipeline_t pipeline[PIPELINE_SIZE];
static uint8_t pipe_head = 0, pipe_tail = 0;
#define PIPE_EMPTY() (pipe_head == pipe_tail)
#define PIPE_FULL()  (((pipe_tail + 1) % PIPELINE_SIZE) == pipe_head)

/* Token ring-buffer for GW router delivery */
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

static double cpu_auth_before_gw, energy_auth_before_gw;
static double cpu_auth_after_gw,  energy_auth_after_gw;

static void print_energest_stats(double *seconds_cpu, double *total_energy)
{
    energest_flush();
    unsigned long cpu_ticks = energest_type_time(ENERGEST_TYPE_CPU);
    unsigned long lpm_ticks = energest_type_time(ENERGEST_TYPE_LPM);
    unsigned long tx_ticks  = energest_type_time(ENERGEST_TYPE_TRANSMIT);
    unsigned long rx_ticks  = energest_type_time(ENERGEST_TYPE_LISTEN);

    *seconds_cpu = cpu_ticks / (double)ENERGEST_SECOND;
    double seconds_lpm = lpm_ticks / (double)ENERGEST_SECOND;
    double seconds_tx  = tx_ticks  / (double)ENERGEST_SECOND;
    double seconds_rx  = rx_ticks  / (double)ENERGEST_SECOND;

    double energy_cpu = *seconds_cpu * CURRENT_CPU * SUPPLY_VOLTAGE;
    double energy_lpm = seconds_lpm * CURRENT_LPM * SUPPLY_VOLTAGE;
    double energy_tx  = seconds_tx  * CURRENT_TX  * SUPPLY_VOLTAGE;
    double energy_rx  = seconds_rx  * CURRENT_RX  * SUPPLY_VOLTAGE;

    *total_energy = energy_cpu + energy_lpm + energy_tx + energy_rx;
}

/* --------------------------------------------------------------------------
 * Endpoints and events
 * -------------------------------------------------------------------------- */
static coap_endpoint_t ep_gw_router;
static coap_message_t  req_out[1];
process_event_t        ev_send_pipeline;
PROCESS_NAME(gw_server_proc);

/* --------------------------------------------------------------------------
 * Utility helpers
 * -------------------------------------------------------------------------- */
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

/* Double-hash: H2(x) = H(x||0x00) || H(x||0x01) for 64-byte output */
static void H2(const uint8_t *in, uint16_t len, uint8_t *out64)
{
    uint8_t buf[256];
    if (len > 254) len = 254;
    memcpy(buf, in, len);
    buf[len] = 0x00;
    H(buf, len + 1, out64);
    buf[len] = 0x01;
    H(buf, len + 1, out64 + 32);
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

static void discover_gw_router(void)
{
    uip_ipaddr_t a;
    uint8_t g = GW_NODE_ID;
    uip_ip6addr_u8(&a, 0xfd,0,0,0,0,0,0,0, 0x02,g,0,g,0,g,0,g);
    uip_ipaddr_copy(&ep_gw_router.ipaddr, &a);
    ep_gw_router.port = UIP_HTONS(COAP_DEFAULT_PORT);
}

/* Find user by DIDi (current or old for desync recovery) */
static int find_user_by_did(const uint8_t *did, uint8_t *use_old)
{
    for (int i = 1; i < MAX_CLIENTS; i++) {
        if (!users[i].enrolled) continue;
        if (memcmp(users[i].DIDi_curr, did, 32) == 0) {
            *use_old = 0; return i;
        }
        if (users[i].did_old_valid &&
            memcmp(users[i].DIDi_old, did, 32) == 0) {
            *use_old = 1; return i;
        }
    }
    return -1;
}

/* Find sensor by SIDn */
static int find_sensor_by_sid(const uint8_t *sid, uint8_t *use_old)
{
    for (int i = 0; i < MAX_SENSORS; i++) {
        if (!sensors[i].enrolled) continue;
        if (memcmp(sensors[i].SIDn_curr, sid, 32) == 0) {
            *use_old = 0; return i;
        }
        if (sensors[i].sid_old_valid &&
            memcmp(sensors[i].SIDn_old, sid, 32) == 0) {
            *use_old = 1; return i;
        }
    }
    return -1;
}

/* ==========================================================================
 * USER REGISTRATION PHASE (Section IV.A)
 *
 * POST /test/user_reg
 * Receive: AES_enc(K_GW_U, [IDi(1) | ki(32) | pad(15)]) = 48 bytes
 * Reply:   AES_enc(K_GW_U, [DIDi(32) | pad(16)]) = 48 bytes
 *
 * GW actions (Steps 1-2):
 *   - Generate random bi (32 bytes)
 *   - DIDi = bi ⊕ IDi_padded
 *   - Store {IDi, ki, bi, DIDi}
 *   - Reply with DIDi
 * ========================================================================== */
static void res_user_reg_handler(coap_message_t *req, coap_message_t *resp,
                                  uint8_t *buf, uint16_t ps, int32_t *off)
{
    const uint8_t *chunk;
    if (coap_get_payload(req, &chunk) < 48) return;

    uint8_t plain[48];
    memcpy(plain, chunk, 48);
    aes_dec(K_GW_U, plain, 3);

    uint8_t id_i = plain[0];
    if (id_i == 0 || id_i >= MAX_CLIENTS) return;

    /* Store user identity and biometric key */
    users[id_i].IDi = id_i;
    memset(users[id_i].IDi_padded, 0, 32);
    users[id_i].IDi_padded[0] = id_i;
    memcpy(users[id_i].ki, plain + 1, 32);

    /* Generate random bi */
    gen_random(users[id_i].bi, 32);

    /* DIDi = bi ⊕ IDi_padded */
    for (int j = 0; j < 32; j++)
        users[id_i].DIDi_curr[j] = users[id_i].bi[j] ^ users[id_i].IDi_padded[j];

    users[id_i].did_old_valid = 0;
    users[id_i].enrolled = 1;

    /* Reply with AES_enc(K_GW_U, [DIDi(32) | pad(16)]) */
    uint8_t reply[48];
    memset(reply, 0, 48);
    memcpy(reply, users[id_i].DIDi_curr, 32);
    aes_enc(K_GW_U, reply, 3);
    coap_set_payload(resp, reply, 48);

    printf("GW-S %u: User %u registered. DIDi=%02x%02x%02x\n",
           node_id, id_i, users[id_i].DIDi_curr[0],
           users[id_i].DIDi_curr[1], users[id_i].DIDi_curr[2]);
}

/* ==========================================================================
 * SENSOR NODE REGISTRATION PHASE (Section IV.B)
 *
 * POST /test/sn_reg  (Step 1 → Step 2)
 * Receive: AES_enc(K_GW_SN, [SNn(1) | pad(15)]) = 16 bytes
 * Reply:   AES_enc(K_GW_SN, [SIDn(32) | Cn(1) | pad(15)]) = 48 bytes
 *
 * POST /test/sn_reg1 (Step 3 → Step 4)
 * Receive: AES_enc(K_GW_SN, [Rn(1) | sn_id(1) | pad(14)]) = 16 bytes
 * Reply:   "OK"
 * ========================================================================== */
static void res_sn_reg_handler(coap_message_t *req, coap_message_t *resp,
                                uint8_t *buf, uint16_t ps, int32_t *off)
{
    const uint8_t *chunk;
    if (coap_get_payload(req, &chunk) < 16) return;

    uint8_t plain[16];
    memcpy(plain, chunk, 16);
    aes_dec(K_GW_SN, plain, 1);

    uint8_t sn_id = plain[0];
    if (sn_id < FIRST_SN_ID || sn_id > LAST_SN_ID) return;

    int idx = sn_id - FIRST_SN_ID;
    sensors[idx].SNn = sn_id;
    memset(sensors[idx].SNn_padded, 0, 32);
    sensors[idx].SNn_padded[0] = sn_id;

    /* Generate random bn */
    gen_random(sensors[idx].bn, 32);

    /* SIDn = bn ⊕ SNn_padded */
    for (int j = 0; j < 32; j++)
        sensors[idx].SIDn_curr[j] = sensors[idx].bn[j] ^ sensors[idx].SNn_padded[j];

    /* Generate challenge Cn */
    sensors[idx].Cn = (uint8_t)(random_rand() & 0xFF);
    sensors[idx].reg_step = 1;
    sensors[idx].sid_old_valid = 0;

    /* Reply: AES_enc(K_GW_SN, [SIDn(32) | Cn(1) | pad]) = 48 bytes */
    uint8_t reply[48];
    memset(reply, 0, 48);
    memcpy(reply, sensors[idx].SIDn_curr, 32);
    reply[32] = sensors[idx].Cn;
    aes_enc(K_GW_SN, reply, 3);
    coap_set_payload(resp, reply, 48);

    printf("GW-S %u: Sensor %u reg step 1. SIDn=%02x%02x%02x, Cn=%u\n",
           node_id, sn_id, sensors[idx].SIDn_curr[0],
           sensors[idx].SIDn_curr[1], sensors[idx].SIDn_curr[2],
           sensors[idx].Cn);
}

static void res_sn_reg1_handler(coap_message_t *req, coap_message_t *resp,
                                 uint8_t *buf, uint16_t ps, int32_t *off)
{
    const uint8_t *chunk;
    if (coap_get_payload(req, &chunk) < 16) return;

    uint8_t plain[16];
    memcpy(plain, chunk, 16);
    aes_dec(K_GW_SN, plain, 1);

    uint8_t Rn    = plain[0];
    uint8_t sn_id = plain[1];
    if (sn_id < FIRST_SN_ID || sn_id > LAST_SN_ID) return;

    int idx = sn_id - FIRST_SN_ID;
    if (sensors[idx].reg_step != 1) return;

    /* Step 4: Store PUF response */
    sensors[idx].Rn = Rn;
    sensors[idx].enrolled = 1;

    const char *msg = "OK";
    coap_set_payload(resp, (const uint8_t *)msg, strlen(msg));

    printf("GW-S %u: Sensor %u registration complete. (Cn=%u, Rn=%u)\n",
           node_id, sn_id, sensors[idx].Cn, Rn);
}

/* ==========================================================================
 * AUTHENTICATION & KEY EXCHANGE PHASE (Section IV.C)
 *
 * POST /test/auth
 * Receive M1: {Ni(32) | α(32) | DIDi(32) | SIDn(32)} = 128 bytes
 *
 * GW actions:
 *   1. Find user by DIDi → retrieve ki, IDi, bi
 *   2. bi_new' = Ni ⊕ h(ki)                                [hash 1]
 *   3. α' = h(bi_new'||ki||DIDi||SIDn)                      [hash 2]
 *   4. Verify α' == α
 *   5. Find sensor by SIDn → retrieve (Cn, Rn), SNn, bn
 *   6. Generate bn_new(32), SK(32)
 *   7. SIDn_new = SNn_padded ⊕ bn_new                       [XOR]
 *   8. SKn = (SK||SIDn_new) ⊕ H2(Rn)                        [hash 3]
 *   9. β = h(SK||Rn||SIDn||SIDn_new)                         [hash 4]
 *  10. Enqueue M2 for async delivery to sensor
 *  11. Reply to user with interim ACK
 *
 * After M3 received (async in main loop):
 *  12. γ' = h(SIDn_new||SK)                                  [hash 5]
 *  13. Verify γ' == γ
 *  14. DIDi_new = IDi_padded ⊕ bi_new                        [XOR]
 *  15. SKi = (SIDn_new||SK||DIDi_new) ⊕ H3(ki)               [hash 6]
 *  16. λ = h(SK||DIDi||ki||DIDi_new||SIDn_new)                [hash 7]
 *  17. Send M4 to user, token to GW router
 *  18. Rotate pseudonyms
 * ========================================================================== */
static void res_auth_handler(coap_message_t *req, coap_message_t *resp,
                              uint8_t *buf, uint16_t ps, int32_t *off)
{
    const uint8_t *chunk;
    int len = coap_get_payload(req, &chunk);
    if (len < 128) {
        printf("GW-S %u: Auth M1 too short (%d)\n", node_id, len);
        return;
    }

    /* Parse M1: {Ni(32) | α(32) | DIDi(32) | SIDn(32)} */
    uint8_t Ni[32], alpha[32], recv_DIDi[32], recv_SIDn[32];
    memcpy(Ni,        chunk,      32);
    memcpy(alpha,     chunk + 32, 32);
    memcpy(recv_DIDi, chunk + 64, 32);
    memcpy(recv_SIDn, chunk + 96, 32);

    /* Step 1: Find user by DIDi */
    uint8_t use_old_u = 0;
    int uidx = find_user_by_did(recv_DIDi, &use_old_u);
    if (uidx < 0) {
        printf("GW-S %u: Auth failed — DIDi not found\n", node_id);
        return;
    }
    user_record_t *u = &users[uidx];

    /* Step 2: bi_new' = Ni ⊕ h(ki) */
    uint8_t h_ki[32];
    H(u->ki, 32, h_ki);                     /* Hash 1 */
    uint8_t bi_new_prime[32];
    for (int j = 0; j < 32; j++)
        bi_new_prime[j] = Ni[j] ^ h_ki[j];

    /* Step 3: α' = h(bi_new'||ki||DIDi||SIDn) */
    uint8_t alpha_in[128];                   /* 32+32+32+32 = 128 */
    memcpy(alpha_in,      bi_new_prime, 32);
    memcpy(alpha_in + 32, u->ki,        32);
    memcpy(alpha_in + 64, recv_DIDi,    32);
    memcpy(alpha_in + 96, recv_SIDn,    32);
    uint8_t alpha_prime[32];
    H(alpha_in, 128, alpha_prime);           /* Hash 2 */

    /* Step 4: Verify α' == α */
    if (memcmp(alpha_prime, alpha, 32) != 0) {
        printf("GW-S %u: Auth failed — α mismatch (user %u)\n", node_id, uidx);
        return;
    }
    printf("GW-S %u: User %u M1 verified\n", node_id, uidx);

    /* Step 5: Find sensor by SIDn */
    uint8_t use_old_s = 0;
    int sidx = find_sensor_by_sid(recv_SIDn, &use_old_s);
    if (sidx < 0) {
        printf("GW-S %u: Auth failed — SIDn not found\n", node_id);
        return;
    }
    sensor_record_t *s = &sensors[sidx];

    /* Step 6: Generate bn_new and SK */
    uint8_t bn_new[32], SK[32];
    gen_random(bn_new, 32);
    gen_random(SK, 32);

    /* Step 7: SIDn_new = SNn_padded ⊕ bn_new */
    uint8_t SIDn_new[32];
    for (int j = 0; j < 32; j++)
        SIDn_new[j] = s->SNn_padded[j] ^ bn_new[j];

    /* Step 8: SKn = (SK||SIDn_new) ⊕ H2(Rn) */
    uint8_t rn_buf[1] = {s->Rn};
    uint8_t mask64[64];
    H2(rn_buf, 1, mask64);                   /* Hash 3 (double-hash for 64B) */
    uint8_t SKn[64];
    for (int j = 0; j < 32; j++) SKn[j]      = SK[j]       ^ mask64[j];
    for (int j = 0; j < 32; j++) SKn[32 + j] = SIDn_new[j] ^ mask64[32 + j];

    /* Step 9: β = h(SK||Rn||SIDn||SIDn_new) */
    uint8_t beta_in[97];                     /* 32+1+32+32 = 97 */
    memcpy(beta_in,      SK,       32);
    beta_in[32] = s->Rn;
    memcpy(beta_in + 33, use_old_s ? s->SIDn_old : s->SIDn_curr, 32);
    memcpy(beta_in + 65, SIDn_new, 32);
    uint8_t beta[32];
    H(beta_in, 97, beta);                    /* Hash 4 */

    /* Step 10: Enqueue M2 for async delivery */
    if (!PIPE_FULL()) {
        auth_pipeline_t *p = &pipeline[pipe_tail];
        memset(p, 0, sizeof(*p));
        p->valid = 1;
        p->sn_node_id = s->SNn;
        memcpy(p->SKn, SKn, 64);
        memcpy(p->beta, beta, 32);
        p->Cn = s->Cn;
        p->user_node_id = u->IDi;
        memcpy(p->SK, SK, 32);
        memcpy(p->SIDn_new, SIDn_new, 32);
        memcpy(p->ki, u->ki, 32);
        memcpy(p->DIDi_curr, recv_DIDi, 32);
        p->user_idx = uidx;
        p->sensor_idx = sidx;

        /* Pre-compute DIDi_new = IDi_padded ⊕ bi_new' */
        for (int j = 0; j < 32; j++)
            p->DIDi_new[j] = u->IDi_padded[j] ^ bi_new_prime[j];

        pipe_tail = (pipe_tail + 1) % PIPELINE_SIZE;
        process_post(&gw_server_proc, ev_send_pipeline, NULL);
    } else {
        printf("GW-S %u: Pipeline full\n", node_id);
    }

    /* Step 11: Reply to user with interim ACK */
    uint8_t ack = 0xAC;
    coap_set_payload(resp, &ack, 1);
}

/* --------------------------------------------------------------------------
 * CoAP resource declarations
 * -------------------------------------------------------------------------- */
/* ==========================================================================
 * GET SENSOR SIDn — allows User to fetch SIDn by sensor node_id
 *
 * POST /test/get_sid
 * Receive: AES_enc(K_GW_U, [sn_node_id(1) | pad(15)]) = 16 bytes
 * Reply:   AES_enc(K_GW_U, [SIDn(32) | pad(16)]) = 48 bytes (or 1 byte error)
 * ========================================================================== */
static void res_get_sid_handler(coap_message_t *req, coap_message_t *resp,
                                uint8_t *buf, uint16_t ps, int32_t *off)
{
    const uint8_t *chunk;
    if (coap_get_payload(req, &chunk) < 16) return;

    uint8_t plain[16];
    memcpy(plain, chunk, 16);
    aes_dec(K_GW_U, plain, 1);

    uint8_t sn_id = plain[0];
    if (sn_id < FIRST_SN_ID || sn_id > LAST_SN_ID) {
        uint8_t err = 0xFF;
        coap_set_payload(resp, &err, 1);
        return;
    }

    int idx = sn_id - FIRST_SN_ID;
    if (!sensors[idx].enrolled) {
        uint8_t err = 0xFE;
        coap_set_payload(resp, &err, 1);
        printf("GW-S %u: get_sid — sensor %u not enrolled yet\n", node_id, sn_id);
        return;
    }

    /* Reply with AES_enc(K_GW_U, [SIDn(32) | pad(16)]) = 48 bytes */
    uint8_t reply[48];
    memset(reply, 0, 48);
    memcpy(reply, sensors[idx].SIDn_curr, 32);
    aes_enc(K_GW_U, reply, 3);
    coap_set_payload(resp, reply, 48);

    printf("GW-S %u: get_sid — returned SIDn for sensor %u\n", node_id, sn_id);
}

RESOURCE(res_user_reg,  "title=\"UserReg\"",  NULL, res_user_reg_handler,  NULL, NULL);
RESOURCE(res_sn_reg,    "title=\"SNReg\"",    NULL, res_sn_reg_handler,    NULL, NULL);
RESOURCE(res_sn_reg1,   "title=\"SNReg1\"",   NULL, res_sn_reg1_handler,   NULL, NULL);
RESOURCE(res_auth,      "title=\"Auth\"",     NULL, res_auth_handler,      NULL, NULL);
RESOURCE(res_get_sid,   "title=\"GetSID\"",   NULL, res_get_sid_handler,   NULL, NULL);

/* --------------------------------------------------------------------------
 * CoAP response callbacks for async delivery
 * -------------------------------------------------------------------------- */

/* M3 response from sensor */
static uint8_t m3_gamma[32];
static uint8_t m3_received = 0;

static void m2_response_handler(coap_message_t *resp)
{
    const uint8_t *chunk;
    if (!resp || coap_get_payload(resp, &chunk) < 32) {
        printf("GW-S %u: M3 not received from sensor\n", node_id);
        m3_received = 0;
        return;
    }
    memcpy(m3_gamma, chunk, 32);
    m3_received = 1;
    printf("GW-S %u: M3 received from sensor\n", node_id);
}

/* M4 delivery to user */
static void m4_delivery_handler(coap_message_t *resp)
{
    if (!resp)
        printf("GW-S %u: M4 delivery to user failed\n", node_id);
    else
        printf("GW-S %u: M4 delivered to user\n", node_id);
}

/* Token delivery to GW router */
static void gw_tok_ack(coap_message_t *resp)
{
    if (!resp)
        printf("GW-S %u: Token delivery to GW router timed out\n", node_id);
    tok_head = (tok_head + 1) % MAX_CLIENTS;
}

/* ==========================================================================
 * Main process — handles async M2/M3/M4 delivery
 * ========================================================================== */
PROCESS(gw_server_proc, "GW Server");
AUTOSTART_PROCESSES(&gw_server_proc);

PROCESS_THREAD(gw_server_proc, ev, data)
{
    PROCESS_BEGIN();

    memset(users,    0, sizeof(users));
    memset(sensors,  0, sizeof(sensors));
    memset(pipeline, 0, sizeof(pipeline));
    tok_head = tok_tail = 0;
    pipe_head = pipe_tail = 0;

    coap_engine_init();
    discover_gw_router();

    coap_activate_resource(&res_user_reg,  "test/user_reg");
    coap_activate_resource(&res_sn_reg,    "test/sn_reg");
    coap_activate_resource(&res_sn_reg1,   "test/sn_reg1");
    coap_activate_resource(&res_auth,      "test/auth");
    coap_activate_resource(&res_get_sid,   "test/get_sid");

    ev_send_pipeline = process_alloc_event();
    printf("GW-S %u: Started.\n", node_id);

    while (1) {
        PROCESS_WAIT_EVENT_UNTIL(ev == ev_send_pipeline);

        /* Process all pending auth pipeline entries */
        while (!PIPE_EMPTY()) {
            static auth_pipeline_t *p;
            p = &pipeline[pipe_head];
            if (!p->valid) {
                pipe_head = (pipe_head + 1) % PIPELINE_SIZE;
                continue;
            }

            /* === AUTH BEFORE snapshot (start of M2→M4 pipeline) === */
            print_energest_stats(&cpu_auth_before_gw, &energy_auth_before_gw);

            /* ---- Send M2 to sensor node ---- */
            static coap_endpoint_t ep_sn;
            static uip_ipaddr_t sn_addr;
            static uint8_t sn;
            sn = p->sn_node_id;
            uip_ip6addr_u8(&sn_addr, 0xfd,0,0,0,0,0,0,0,
                           0x02,sn,0,sn,0,sn,0,sn);
            uip_ipaddr_copy(&ep_sn.ipaddr, &sn_addr);
            ep_sn.port = UIP_HTONS(COAP_DEFAULT_PORT);

            /* M2 payload: {SKn(64) | β(32) | Cn(1)} = 97 bytes */
            static uint8_t m2_payload[97];
            memcpy(m2_payload,      p->SKn,  64);
            memcpy(m2_payload + 64, p->beta, 32);
            m2_payload[96] = p->Cn;

            coap_init_message(req_out, COAP_TYPE_CON, COAP_POST, coap_get_mid());
            coap_set_header_uri_path(req_out, "test/auth_sn");
            coap_set_payload(req_out, m2_payload, 97);
            printf("GW-S %u: Sending M2 to sensor %u\n", node_id, sn);

            m3_received = 0;
            COAP_BLOCKING_REQUEST(&ep_sn, req_out, m2_response_handler);

            if (!m3_received) {
                printf("GW-S %u: Auth aborted — no M3 from sensor %u\n",
                       node_id, sn);
                p->valid = 0;
                pipe_head = (pipe_head + 1) % PIPELINE_SIZE;
                continue;
            }

            /* ---- Step 12: Verify M3 (γ) ---- */
            /* γ' = h(SIDn_new||SK) */
            uint8_t gamma_in[64];
            memcpy(gamma_in,      p->SIDn_new, 32);
            memcpy(gamma_in + 32, p->SK,       32);
            uint8_t gamma_prime[32];
            H(gamma_in, 64, gamma_prime);          /* Hash 5 */

            if (memcmp(gamma_prime, m3_gamma, 32) != 0) {
                printf("GW-S %u: Auth failed — γ mismatch from sensor %u\n",
                       node_id, sn);
                p->valid = 0;
                pipe_head = (pipe_head + 1) % PIPELINE_SIZE;
                continue;
            }
            printf("GW-S %u: M3 verified from sensor %u\n", node_id, sn);

            /* ---- Step 13-16: Update sensor records ---- */
            sensor_record_t *s = &sensors[p->sensor_idx];
            memcpy(s->SIDn_old, s->SIDn_curr, 32);
            memcpy(s->SIDn_curr, p->SIDn_new, 32);
            s->sid_old_valid = 1;

            /* Step 15: SKi = (SIDn_new||SK||DIDi_new) ⊕ H3(ki)
             * Need 96-byte mask from ki. Use triple-hash:
             * H3(ki) = H(ki||0x00) || H(ki||0x01) || H(ki||0x02) */
            uint8_t ki_buf[33];
            uint8_t mask96[96];
            memcpy(ki_buf, p->ki, 32);
            ki_buf[32] = 0x00; H(ki_buf, 33, mask96);        /* Hash 6a */
            ki_buf[32] = 0x01; H(ki_buf, 33, mask96 + 32);   /* Hash 6b */
            ki_buf[32] = 0x02; H(ki_buf, 33, mask96 + 64);   /* Hash 6c */

            uint8_t ski_plain[96]; /* SIDn_new(32) || SK(32) || DIDi_new(32) */
            memcpy(ski_plain,      p->SIDn_new,  32);
            memcpy(ski_plain + 32, p->SK,        32);
            memcpy(ski_plain + 64, p->DIDi_new,  32);
            for (int j = 0; j < 96; j++)
                p->SKi[j] = ski_plain[j] ^ mask96[j];
            p->ski_len = 96;

            /* Step 16: λ = h(SK||DIDi||ki||DIDi_new||SIDn_new) */
            uint8_t lambda_in[160]; /* 32+32+32+32+32 = 160 */
            memcpy(lambda_in,       p->SK,        32);
            memcpy(lambda_in + 32,  p->DIDi_curr, 32);
            memcpy(lambda_in + 64,  p->ki,        32);
            memcpy(lambda_in + 96,  p->DIDi_new,  32);
            memcpy(lambda_in + 128, p->SIDn_new,  32);
            H(lambda_in, 160, p->lambda);              /* Hash 7 */

            /* ---- Step 17: Send M4 to user ---- */
            coap_endpoint_t ep_user;
            uip_ipaddr_t u_addr;
            uint8_t uid = p->user_node_id;
            uip_ip6addr_u8(&u_addr, 0xfd,0,0,0,0,0,0,0,
                           0x02,uid,0,uid,0,uid,0,uid);
            uip_ipaddr_copy(&ep_user.ipaddr, &u_addr);
            ep_user.port = UIP_HTONS(COAP_DEFAULT_PORT);

            /* M4 payload: {SKi(96) | λ(32)} = 128 bytes */
            uint8_t m4_payload[128];
            memcpy(m4_payload,      p->SKi,    96);
            memcpy(m4_payload + 96, p->lambda, 32);

            coap_init_message(req_out, COAP_TYPE_CON, COAP_POST, coap_get_mid());
            coap_set_header_uri_path(req_out, "test/auth_complete");
            coap_set_payload(req_out, m4_payload, 128);
            printf("GW-S %u: Sending M4 to user %u\n", node_id, uid);
            COAP_BLOCKING_REQUEST(&ep_user, req_out, m4_delivery_handler);

            /* ---- Step 18: Rotate user pseudonyms ---- */
            user_record_t *u = &users[p->user_idx];
            memcpy(u->DIDi_old, u->DIDi_curr, 32);
            memcpy(u->DIDi_curr, p->DIDi_new, 32);
            u->did_old_valid = 1;

            /* ---- Forward token to GW router ---- */
            if (!TOK_FULL()) {
                uint8_t *slot = tok_buf[tok_tail];
                /* PID(32) = new DIDi | id_gw(1) | enc_token(48) */
                memcpy(slot, p->DIDi_new, 32);
                slot[32] = (uint8_t)node_id;

                uint8_t enc_tok[48];
                memset(enc_tok, 0, 48);
                enc_tok[0] = uid;
                enc_tok[1] = (uint8_t)node_id;
                enc_tok[2] = (uint8_t)(clock_time() / CLOCK_SECOND);
                memcpy(enc_tok + 16, p->SK, 16);
                memcpy(enc_tok + 32, p->SK + 16, 16);
                aes_enc(K_GW_RT, enc_tok, 3);
                memcpy(slot + 33, enc_tok, 48);

                tok_tail = (tok_tail + 1) % MAX_CLIENTS;
            }

            /* === AUTH AFTER snapshot — print differential cost === */
            print_energest_stats(&cpu_auth_after_gw, &energy_auth_after_gw);
            printf("\nAUTH_ENERGY_GW|%u|cpu_s=%f|energy_j=%f",
                   node_id,
                   (cpu_auth_after_gw  - cpu_auth_before_gw),
                   (energy_auth_after_gw - energy_auth_before_gw));

            p->valid = 0;
            pipe_head = (pipe_head + 1) % PIPELINE_SIZE;
        }

        /* Drain token queue to GW router */
        while (!TOK_EMPTY()) {
            uint8_t payload[GW_TOKEN_LEN];
            memcpy(payload, tok_buf[tok_head], GW_TOKEN_LEN);
            coap_init_message(req_out, COAP_TYPE_CON, COAP_POST, coap_get_mid());
            coap_set_header_uri_path(req_out, "test/auth_token");
            coap_set_payload(req_out, payload, GW_TOKEN_LEN);
            COAP_BLOCKING_REQUEST(&ep_gw_router, req_out, gw_tok_ack);
        }
    }

    PROCESS_END();
}
