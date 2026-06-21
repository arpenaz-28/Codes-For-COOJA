/* ==========================================================================
 * gw-node.c  —  Zhou Desync Demo: Combined Medical Gateway + Sensor Node
 *
 * Simulates the GW and SN as a single combined node to demonstrate the
 * M3-loss desynchronisation vulnerability in Zhou et al. (IEEE IoT J., 2024).
 *
 * Per-user state tracks gw_SIDn (GW's view) and sn_SIDn (SN's actual state)
 * separately.  When auth_count == 2, the "M3 drop" is triggered:
 *   - SN commits SIDn_new  (sn_SIDn advances)
 *   - GW drops M3          (gw_SIDn stays old)
 *   - No M4 sent to User   (User keeps old SIDn too)
 * Result: sn_SIDn ≠ gw_SIDn  → beta mismatch in every subsequent round.
 *
 * Protocol messages:
 *   POST /zhou/reg   {uid(1)}               → {DIDi(32), SIDn(32)}          = 64 B
 *   POST /zhou/auth  {uid(1),DIDi(32),      → {DIDi_new(32), SIDn_new(32),
 *                     Ni(16), alpha(32)}=81B    lambda(32)}=96 B  or  0 B (fail)
 *   POST /zhou/data  {DIDi(32), enc(16)}=48B → {0x00}=1 B
 * ========================================================================== */

#include <stdio.h>
#include <string.h>
#include <stdint.h>
#include "contiki.h"
#include "coap-engine.h"
#include "aes.h"
#include "sha256.h"
#include "net/routing/routing.h"
#include "net/netstack.h"
#include "sys/node-id.h"
#include "project-conf.h"

/* --------------------------------------------------------------------------
 * Per-user state
 * -------------------------------------------------------------------------- */
#define MAX_USERS   25
#define HASH_LEN    32
#define KI_LEN      16

typedef struct {
    uint8_t  user_id;
    uint8_t  ki[KI_LEN];          /* shared key derived from biometrics     */
    uint8_t  gw_DIDi[HASH_LEN];   /* GW's stored user pseudonym             */
    uint8_t  gw_SIDn[HASH_LEN];   /* GW's view of SN's current SIDn         */
    uint8_t  sn_SIDn[HASH_LEN];   /* SN's actual committed SIDn (can differ!)*/
    uint8_t  SK[HASH_LEN];        /* session key for data decryption         */
    uint8_t  Rn[HASH_LEN];        /* simulated SN PUF response               */
    uint8_t  auth_count;          /* number of auth rounds completed         */
    uint8_t  enroll_count;        /* number of enrollments done (for SIDn nonce) */
    uint8_t  drop_armed;          /* 1 = trigger M3 drop on next auth_count==2 */
    uint8_t  registered;
} user_rec_t;

static user_rec_t users[MAX_USERS];

static user_rec_t *find_user(uint8_t uid)
{
    for (int i = 0; i < MAX_USERS; i++) {
        if (users[i].registered && users[i].user_id == uid)
            return &users[i];
    }
    return NULL;
}

static user_rec_t *alloc_user(uint8_t uid)
{
    /* Reuse existing slot if this user already has one */
    for (int i = 0; i < MAX_USERS; i++) {
        if (users[i].registered && users[i].user_id == uid)
            return &users[i];
    }
    for (int i = 0; i < MAX_USERS; i++) {
        if (!users[i].registered)
            return &users[i];
    }
    /* table full — reuse slot 0 */
    return &users[0];
}

/* --------------------------------------------------------------------------
 * Crypto helpers
 * ki = H("ZHOU_KI" || uid)[0:16]  — same derivation as in user-node.c
 * -------------------------------------------------------------------------- */
static void derive_ki(uint8_t uid, uint8_t ki_out[KI_LEN])
{
    uint8_t tmp[HASH_LEN];
    SHA256_CTX ctx;
    sha256_init(&ctx);
    const uint8_t prefix[] = {'Z','H','O','U','_','K','I'};
    sha256_update(&ctx, prefix, 7);
    sha256_update(&ctx, &uid, 1);
    sha256_final(&ctx, tmp);
    memcpy(ki_out, tmp, KI_LEN);
}

/* ==========================================================================
 * POST /zhou/reg  —  User enrollment (and re-enrollment)
 *
 * Payload: {uid(1)} = 1 byte
 * Response: {DIDi(32), SIDn(32)} = 64 bytes
 *
 * On re-enrollment: GW resets both gw_SIDn and sn_SIDn to a fresh SIDn,
 * auth_count resets to 0, and drop_armed is cleared (no second drop).
 * ========================================================================== */
static void res_reg_handler(coap_message_t *req, coap_message_t *resp,
                             uint8_t *buf, uint16_t ps, int32_t *off)
{
    const uint8_t *chunk;
    if (coap_get_payload(req, &chunk) < 1) return;

    uint8_t uid = chunk[0];
    user_rec_t *u = alloc_user(uid);

    u->user_id = uid;
    u->enroll_count++;
    derive_ki(uid, u->ki);

    /* DIDi_init = H(ki || uid || enroll_count || "DID_INIT") */
    {
        SHA256_CTX ctx;
        sha256_init(&ctx);
        sha256_update(&ctx, u->ki, KI_LEN);
        sha256_update(&ctx, &uid, 1);
        sha256_update(&ctx, &u->enroll_count, 1);
        const uint8_t sep[] = {'D','I','D','_','I','N','I','T'};
        sha256_update(&ctx, sep, 8);
        sha256_final(&ctx, u->gw_DIDi);
    }

    /* SIDn_init = H(uid || enroll_count || "SID_INIT") */
    {
        SHA256_CTX ctx;
        sha256_init(&ctx);
        sha256_update(&ctx, &uid, 1);
        sha256_update(&ctx, &u->enroll_count, 1);
        const uint8_t sep[] = {'S','I','D','_','I','N','I','T'};
        sha256_update(&ctx, sep, 8);
        sha256_final(&ctx, u->gw_SIDn);
    }
    memcpy(u->sn_SIDn, u->gw_SIDn, HASH_LEN);   /* SN in sync at enrollment */

    /* Rn = H(SIDn_init || uid || "PUF") — simulated SN PUF response */
    {
        SHA256_CTX ctx;
        sha256_init(&ctx);
        sha256_update(&ctx, u->gw_SIDn, HASH_LEN);
        sha256_update(&ctx, &uid, 1);
        const uint8_t sep[] = {'P','U','F'};
        sha256_update(&ctx, sep, 3);
        sha256_final(&ctx, u->Rn);
    }

    u->auth_count  = 0;
    u->drop_armed  = 1;   /* arm M3-drop trigger for Round 2 */
    u->registered  = 1;

    /* Build response: {DIDi(32), SIDn(32)} */
    static uint8_t reg_resp[64];
    memcpy(reg_resp,      u->gw_DIDi, 32);
    memcpy(reg_resp + 32, u->gw_SIDn, 32);
    coap_set_payload(resp, reg_resp, 64);

    printf("GW: Enrolled user %u (enroll #%u) DIDi=%02x%02x SIDn=%02x%02x\n",
           uid, u->enroll_count,
           u->gw_DIDi[0], u->gw_DIDi[1],
           u->gw_SIDn[0], u->gw_SIDn[1]);
}

/* ==========================================================================
 * POST /zhou/auth  —  M1→M4 authentication (M2/M3 simulated internally)
 *
 * M1 payload: {uid(1), DIDi(32), Ni(16), alpha(32)} = 81 bytes
 *   alpha = H(Ni || ki || DIDi || gw_SIDn)
 *
 * M4 success response: {DIDi_new(32), SIDn_new(32), lambda(32)} = 96 bytes
 * M4 fail response:    0 bytes
 *
 * Desync simulation (Round 2, auth_count == 2 when drop_armed):
 *   SN commits sn_SIDn ← SIDn_new, GW drops M3 → gw_SIDn stays old.
 *   No M4 sent.  Subsequent rounds detect sn_SIDn ≠ gw_SIDn → FAIL.
 * ========================================================================== */
static void res_auth_handler(coap_message_t *req, coap_message_t *resp,
                              uint8_t *buf, uint16_t ps, int32_t *off)
{
    const uint8_t *chunk;
    if (coap_get_payload(req, &chunk) < 81) return;

    uint8_t uid         = chunk[0];
    const uint8_t *DIDi = chunk + 1;
    const uint8_t *Ni   = chunk + 33;
    const uint8_t *alpha_recv = chunk + 49;

    user_rec_t *u = find_user(uid);
    if (!u) {
        printf("GW: Auth rejected — user %u not registered\n", uid);
        return;
    }

    /* Verify DIDi matches GW's stored record */
    if (memcmp(DIDi, u->gw_DIDi, HASH_LEN) != 0) {
        printf("GW: Auth rejected — DIDi mismatch for user %u\n", uid);
        return;
    }

    /* Verify alpha = H(Ni || ki || DIDi || gw_SIDn) */
    {
        uint8_t alpha_check[HASH_LEN];
        SHA256_CTX ctx;
        sha256_init(&ctx);
        sha256_update(&ctx, Ni,         16);
        sha256_update(&ctx, u->ki,      KI_LEN);
        sha256_update(&ctx, DIDi,       HASH_LEN);
        sha256_update(&ctx, u->gw_SIDn, HASH_LEN);
        sha256_final(&ctx, alpha_check);
        if (memcmp(alpha_check, alpha_recv, HASH_LEN) != 0) {
            printf("GW: Auth rejected — alpha mismatch for user %u\n", uid);
            return;
        }
    }

    u->auth_count++;

    /* Compute derived values for M2/M3/M4 */
    uint8_t SIDn_new[HASH_LEN];
    uint8_t SK[HASH_LEN];
    uint8_t beta[HASH_LEN];

    /* SIDn_new = H(gw_SIDn || Ni || uid) */
    {
        SHA256_CTX ctx;
        sha256_init(&ctx);
        sha256_update(&ctx, u->gw_SIDn, HASH_LEN);
        sha256_update(&ctx, Ni,         16);
        sha256_update(&ctx, &uid,       1);
        sha256_final(&ctx, SIDn_new);
    }

    /* SK = H(ki || Ni || gw_SIDn) */
    {
        SHA256_CTX ctx;
        sha256_init(&ctx);
        sha256_update(&ctx, u->ki,      KI_LEN);
        sha256_update(&ctx, Ni,         16);
        sha256_update(&ctx, u->gw_SIDn, HASH_LEN);
        sha256_final(&ctx, SK);
    }

    /* beta = H(SK || Rn || gw_SIDn || SIDn_new) — GW sends to SN in M2 */
    {
        SHA256_CTX ctx;
        sha256_init(&ctx);
        sha256_update(&ctx, SK,         HASH_LEN);
        sha256_update(&ctx, u->Rn,      HASH_LEN);
        sha256_update(&ctx, u->gw_SIDn, HASH_LEN);
        sha256_update(&ctx, SIDn_new,   HASH_LEN);
        sha256_final(&ctx, beta);
    }

    /* -----------------------------------------------------------------------
     * DESYNC TRIGGER (Round 2):
     * SN receives M2, commits SIDn_new, then attempts to send M3.
     * GW "drops" M3 — gw_SIDn stays on old value, sn_SIDn advances.
     * No M4 is sent: User keeps old DIDi and SIDn.
     * ----------------------------------------------------------------------- */
    if (u->drop_armed && u->auth_count == 2) {
        memcpy(u->sn_SIDn, SIDn_new, HASH_LEN);   /* SN committed */
        u->drop_armed = 0;
        printf("GW: [Round 2] M3-DROP for user %u — sn_SIDn advanced, gw_SIDn=%02x%02x stays old\n",
               uid, u->gw_SIDn[0], u->gw_SIDn[1]);
        printf("GW: [Round 2] DESYNC: sn_SIDn=%02x%02x, gw_SIDn=%02x%02x\n",
               u->sn_SIDn[0], u->sn_SIDn[1], u->gw_SIDn[0], u->gw_SIDn[1]);
        /* No M4 — respond with empty payload (FAIL) */
        return;
    }

    /* -----------------------------------------------------------------------
     * DESYNC STATE DETECTION:
     * SN has sn_SIDn ≠ gw_SIDn → SN computes beta' using sn_SIDn → beta mismatch.
     * GW detects this by checking sn_SIDn against gw_SIDn.
     * ----------------------------------------------------------------------- */
    if (memcmp(u->sn_SIDn, u->gw_SIDn, HASH_LEN) != 0) {
        /* Verify: compute what SN would compute (beta') — it will differ */
        uint8_t sn_SK[HASH_LEN], beta_sn[HASH_LEN];
        {
            SHA256_CTX ctx;
            sha256_init(&ctx);
            sha256_update(&ctx, u->ki,      KI_LEN);
            sha256_update(&ctx, Ni,         16);
            sha256_update(&ctx, u->sn_SIDn, HASH_LEN);   /* SN uses its own SIDn */
            sha256_final(&ctx, sn_SK);
        }
        {
            SHA256_CTX ctx;
            sha256_init(&ctx);
            sha256_update(&ctx, sn_SK,      HASH_LEN);
            sha256_update(&ctx, u->Rn,      HASH_LEN);
            sha256_update(&ctx, u->sn_SIDn, HASH_LEN);
            sha256_update(&ctx, SIDn_new,   HASH_LEN);
            sha256_final(&ctx, beta_sn);
        }
        if (memcmp(beta_sn, beta, HASH_LEN) != 0) {
            printf("GW: [Round %u] Beta mismatch for user %u — SN rejects (DESYNC STATE)\n",
                   u->auth_count, uid);
            printf("GW: [Round %u] gw_SIDn=%02x%02x, sn_SIDn=%02x%02x\n",
                   u->auth_count, u->gw_SIDn[0], u->gw_SIDn[1],
                   u->sn_SIDn[0], u->sn_SIDn[1]);
            return;  /* No M4 — FAIL */
        }
    }

    /* -----------------------------------------------------------------------
     * NORMAL / RECOVERY PATH:
     * SN verifies beta OK, commits SIDn_new, sends gamma via M3.
     * GW verifies gamma (not shown — accepted here), computes M4.
     * ----------------------------------------------------------------------- */
    memcpy(u->sn_SIDn, SIDn_new, HASH_LEN);   /* SN committed */
    memcpy(u->gw_SIDn, SIDn_new, HASH_LEN);   /* GW received M3, updated */

    /* DIDi_new = H(gw_DIDi || Ni || uid || 0xDD) */
    uint8_t DIDi_new[HASH_LEN];
    {
        uint8_t sep = 0xDD;
        SHA256_CTX ctx;
        sha256_init(&ctx);
        sha256_update(&ctx, u->gw_DIDi, HASH_LEN);
        sha256_update(&ctx, Ni,         16);
        sha256_update(&ctx, &uid,       1);
        sha256_update(&ctx, &sep,       1);
        sha256_final(&ctx, DIDi_new);
    }

    /* lambda = H(SK || gw_DIDi_old || ki || DIDi_new || SIDn_new) */
    uint8_t lambda[HASH_LEN];
    {
        SHA256_CTX ctx;
        sha256_init(&ctx);
        sha256_update(&ctx, SK,          HASH_LEN);
        sha256_update(&ctx, u->gw_DIDi,  HASH_LEN);   /* old DIDi — before update */
        sha256_update(&ctx, u->ki,       KI_LEN);
        sha256_update(&ctx, DIDi_new,    HASH_LEN);
        sha256_update(&ctx, SIDn_new,    HASH_LEN);
        sha256_final(&ctx, lambda);
    }

    /* Commit GW state updates */
    memcpy(u->gw_DIDi, DIDi_new, HASH_LEN);
    memcpy(u->SK,      SK,       HASH_LEN);

    /* M4 response: {DIDi_new(32), SIDn_new(32), lambda(32)} */
    static uint8_t m4[96];
    memcpy(m4,      DIDi_new, 32);
    memcpy(m4 + 32, SIDn_new, 32);
    memcpy(m4 + 64, lambda,   32);
    coap_set_payload(resp, m4, 96);

    printf("GW: [Round %u] M4 sent to user %u — DIDi=%02x%02x SIDn=%02x%02x\n",
           u->auth_count, uid, DIDi_new[0], DIDi_new[1], SIDn_new[0], SIDn_new[1]);
}

/* ==========================================================================
 * POST /zhou/data  —  Receive AES-encrypted sensor data from authenticated user
 *
 * Payload: {DIDi(32), AES_enc(SK[0:16], data(16))} = 48 bytes
 * Response: {0x00} = 1 byte
 * ========================================================================== */
static void res_data_handler(coap_message_t *req, coap_message_t *resp,
                              uint8_t *buf, uint16_t ps, int32_t *off)
{
    const uint8_t *chunk;
    if (coap_get_payload(req, &chunk) < 48) return;

    const uint8_t *DIDi_recv = chunk;
    uint8_t enc_data[16];
    memcpy(enc_data, chunk + 32, 16);

    /* Find user by DIDi */
    user_rec_t *u = NULL;
    for (int i = 0; i < MAX_USERS; i++) {
        if (users[i].registered && memcmp(users[i].gw_DIDi, DIDi_recv, HASH_LEN) == 0) {
            u = &users[i];
            break;
        }
    }
    if (!u) {
        printf("GW: Data rejected — DIDi %02x%02x not found\n",
               DIDi_recv[0], DIDi_recv[1]);
        return;
    }

    /* Decrypt using first 16 bytes of SK */
    uint8_t K[16];
    memcpy(K, u->SK, 16);
    struct AES_ctx ctx;
    AES_init_ctx(&ctx, K);
    AES_ECB_decrypt(&ctx, enc_data);

    printf("GW: Data from user %u: val=%u\n", u->user_id, enc_data[0]);

    static const uint8_t ack[1] = {0};
    coap_set_payload(resp, ack, 1);
}

RESOURCE(res_reg,  "title=\"ZhouReg\"",  NULL, res_reg_handler,  NULL, NULL);
RESOURCE(res_auth, "title=\"ZhouAuth\"", NULL, res_auth_handler, NULL, NULL);
RESOURCE(res_data, "title=\"ZhouData\"", NULL, res_data_handler, NULL, NULL);

/* ==========================================================================
 * Main process
 * ========================================================================== */
PROCESS(gw_node, "GW+SN Node (Zhou Desync Demo)");
AUTOSTART_PROCESSES(&gw_node);

PROCESS_THREAD(gw_node, ev, data)
{
    PROCESS_BEGIN();

    memset(users, 0, sizeof(users));

    NETSTACK_ROUTING.root_start();
    coap_engine_init();

    coap_activate_resource(&res_reg,  "zhou/reg");
    coap_activate_resource(&res_auth, "zhou/auth");
    coap_activate_resource(&res_data, "zhou/data");

    printf("GW %u: Started (RPL root + CoAP, Zhou Desync Demo)\n", node_id);

    while (1) {
        PROCESS_WAIT_EVENT();
    }

    PROCESS_END();
}
