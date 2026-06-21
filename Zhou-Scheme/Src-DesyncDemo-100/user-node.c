/* ==========================================================================
 * user-node.c  —  Zhou Desync Demo User (Doctor Device)
 *
 * Demonstrates the M3-loss desynchronisation vulnerability in Zhou et al.
 * (IEEE IoT Journal, Vol. 11, No. 6, 2024).  Recovery requires full
 * re-enrollment because Zhou has no dual-state mechanism.
 *
 * Protocol rounds (mirroring Base-Scheme/Src-DesyncDemo-100/device-node.c):
 *   Enrollment : POST /zhou/reg  → {DIDi(32), SIDn(32)}
 *   Round 1    : POST /zhou/auth → M4 success (both sides in sync)
 *                POST /zhou/data → ACK
 *   Round 2    : POST /zhou/auth → GW triggers M3-drop internally → FAIL
 *                (User gets no M4 → User keeps old DIDi and SIDn)
 *                (GW: gw_SIDn stays old; sn_SIDn advanced → DESYNC)
 *   Round 3    : POST /zhou/auth → GW detects beta mismatch → FAIL
 *                → User detects failure → RE-ENROLLS (/zhou/reg)
 *                → Retries auth → SUCCESS (gw_SIDn = sn_SIDn = SIDn_fresh)
 *                POST /zhou/data → ACK
 *   Round 4    : POST /zhou/auth → M4 success (post-recovery)
 *                POST /zhou/data → ACK
 *
 * Energy printed as:
 *   DESYNC_ENROLL_ENERGY|uid|cpu_s=...|energy_j=...
 *   DESYNC_ROUND1_ENERGY|uid|cpu_s=...|energy_j=...
 *   DESYNC_ROUND2_ENERGY|uid|cpu_s=...|energy_j=...
 *   DESYNC_ROUND3_ENERGY|uid|cpu_s=...|energy_j=...
 *   DESYNC_ROUND4_ENERGY|uid|cpu_s=...|energy_j=...
 * ========================================================================== */

#include <stdio.h>
#include <string.h>
#include <stdint.h>
#include "contiki.h"
#include "coap-engine.h"
#include "coap-blocking-api.h"
#include "aes.h"
#include "sha256.h"
#include "net/ipv6/uip-ds6.h"
#include "sys/node-id.h"
#include "sys/energest.h"
#include "project-conf.h"

/* --------------------------------------------------------------------------
 * User state
 * -------------------------------------------------------------------------- */
#define HASH_LEN  32
#define KI_LEN    16

static uint8_t user_id;
static uint8_t ki[KI_LEN];
static uint8_t DIDi[HASH_LEN];
static uint8_t SIDn[HASH_LEN];
static uint8_t Ni[16];
static uint8_t SK[HASH_LEN];       /* session key from last M4 */

static uint8_t ts_auth   = 0;      /* Ni counter — increments each auth attempt */
static uint8_t auth_round = 0;     /* 0=enroll, 1=R1, 2=R2, 3=R3, 4=R4 */
static uint8_t reg        = 0;
static uint8_t last_auth_ok = 0;

/* --------------------------------------------------------------------------
 * ENERGEST energy measurement (same constants as device-node.c)
 * -------------------------------------------------------------------------- */
#define CURRENT_CPU    1.8e-3
#define CURRENT_LPM    0.0545e-3
#define CURRENT_TX     17.4e-3
#define CURRENT_RX     18.8e-3
#define SUPPLY_VOLTAGE 3.0

static double cpu_before, energy_before;
static double cpu_after,  energy_after;

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
 * ki = H("ZHOU_KI" || uid)[0:16]  — same derivation as gw-node.c
 * -------------------------------------------------------------------------- */
static void derive_ki_local(void)
{
    uint8_t tmp[HASH_LEN];
    SHA256_CTX ctx;
    sha256_init(&ctx);
    const uint8_t prefix[] = {'Z','H','O','U','_','K','I'};
    sha256_update(&ctx, prefix, 7);
    sha256_update(&ctx, &user_id, 1);
    sha256_final(&ctx, tmp);
    memcpy(ki, tmp, KI_LEN);
}

/* Ni = H(uid || ts_auth)[0:16] — deterministic nonce for each auth round */
static void derive_Ni(void)
{
    uint8_t tmp[HASH_LEN];
    SHA256_CTX ctx;
    sha256_init(&ctx);
    sha256_update(&ctx, &user_id, 1);
    sha256_update(&ctx, &ts_auth,  1);
    sha256_final(&ctx, tmp);
    memcpy(Ni, tmp, 16);
}

/* --------------------------------------------------------------------------
 * Endpoints and CoAP buffers
 * -------------------------------------------------------------------------- */
static coap_endpoint_t ep_gw;
static coap_message_t  request[1];

static void discover_gw(void)
{
    uip_ipaddr_t a;
    uint8_t g = (uint8_t)GW_NODE_ID;
    uip_ip6addr_u8(&a, 0xfd,0,0,0,0,0,0,0,
                   0x02,g,0,g,0,g,0,g);
    uip_ipaddr_copy(&ep_gw.ipaddr, &a);
    ep_gw.port = UIP_HTONS(COAP_DEFAULT_PORT);
}

/* ==========================================================================
 * CoAP response handlers
 * ========================================================================== */

/* reg handler: receive {DIDi(32), SIDn(32)} = 64 bytes */
static void client_reg_handler(coap_message_t *resp)
{
    const uint8_t *chunk;
    if (!resp || coap_get_payload(resp, &chunk) < 64) {
        printf("DESYNC_LOG|Node %u|Reg dropped\n", user_id);
        return;
    }
    memcpy(DIDi, chunk,      32);
    memcpy(SIDn, chunk + 32, 32);
    printf("DESYNC_LOG|Node %u|Reg OK|DIDi=%02x%02x|SIDn=%02x%02x\n",
           user_id, DIDi[0], DIDi[1], SIDn[0], SIDn[1]);
}

/* auth handler: receive M4 {DIDi_new(32), SIDn_new(32), lambda(32)} = 96 bytes
 * or empty (0 bytes) = FAIL */
static void client_auth_handler(coap_message_t *resp)
{
    const uint8_t *chunk;
    int len = 0;
    if (resp) len = coap_get_payload(resp, &chunk);

    if (len < 96) {
        printf("DESYNC_LOG|Node %u|Round %u|Auth FAILED (no M4 — %u bytes)\n",
               user_id, auth_round, len);
        last_auth_ok = 0;
        return;
    }

    uint8_t DIDi_new[HASH_LEN], SIDn_new[HASH_LEN], lambda_recv[HASH_LEN];
    memcpy(DIDi_new,    chunk,      32);
    memcpy(SIDn_new,    chunk + 32, 32);
    memcpy(lambda_recv, chunk + 64, 32);

    /* Compute SK_u = H(ki || Ni || SIDn) — using User's stored SIDn */
    uint8_t SK_u[HASH_LEN];
    {
        SHA256_CTX ctx;
        sha256_init(&ctx);
        sha256_update(&ctx, ki,   KI_LEN);
        sha256_update(&ctx, Ni,   16);
        sha256_update(&ctx, SIDn, HASH_LEN);
        sha256_final(&ctx, SK_u);
    }

    /* Verify lambda = H(SK_u || DIDi_old || ki || DIDi_new || SIDn_new) */
    uint8_t lambda_check[HASH_LEN];
    {
        SHA256_CTX ctx;
        sha256_init(&ctx);
        sha256_update(&ctx, SK_u,     HASH_LEN);
        sha256_update(&ctx, DIDi,     HASH_LEN);   /* old DIDi — before update */
        sha256_update(&ctx, ki,       KI_LEN);
        sha256_update(&ctx, DIDi_new, HASH_LEN);
        sha256_update(&ctx, SIDn_new, HASH_LEN);
        sha256_final(&ctx, lambda_check);
    }

    if (memcmp(lambda_check, lambda_recv, HASH_LEN) != 0) {
        printf("DESYNC_LOG|Node %u|Round %u|Lambda verify FAILED\n", user_id, auth_round);
        last_auth_ok = 0;
        return;
    }

    /* Accept M4: update User state */
    memcpy(DIDi, DIDi_new, HASH_LEN);
    memcpy(SIDn, SIDn_new, HASH_LEN);
    memcpy(SK,   SK_u,     HASH_LEN);   /* store session key for data phase */

    printf("DESYNC_LOG|Node %u|Round %u|Auth OK|DIDi=%02x%02x|SIDn=%02x%02x\n",
           user_id, auth_round, DIDi[0], DIDi[1], SIDn[0], SIDn[1]);
    last_auth_ok = 1;
}

/* data handler: receive ACK {0x00} = 1 byte */
static void client_data_handler(coap_message_t *resp)
{
    if (!resp) {
        printf("DESYNC_LOG|Node %u|Round %u|Data ACK missing\n", user_id, auth_round);
        return;
    }
    printf("DESYNC_LOG|Node %u|Round %u|Data confirmed by GW\n", user_id, auth_round);
}

/* ==========================================================================
 * Auth payload preparation
 * M1: {uid(1), DIDi(32), Ni(16), alpha(32)} = 81 bytes
 * alpha = H(Ni || ki || DIDi || SIDn)
 * ========================================================================== */
static uint8_t auth_payload[81];
static uint8_t data_payload[48];

static void prepare_auth(void)
{
    ts_auth++;
    derive_Ni();

    /* alpha = H(Ni || ki || DIDi || SIDn) */
    uint8_t alpha[HASH_LEN];
    {
        SHA256_CTX ctx;
        sha256_init(&ctx);
        sha256_update(&ctx, Ni,   16);
        sha256_update(&ctx, ki,   KI_LEN);
        sha256_update(&ctx, DIDi, HASH_LEN);
        sha256_update(&ctx, SIDn, HASH_LEN);
        sha256_final(&ctx, alpha);
    }

    auth_payload[0] = user_id;
    memcpy(auth_payload + 1,  DIDi,  32);
    memcpy(auth_payload + 33, Ni,    16);
    memcpy(auth_payload + 49, alpha, 32);

    printf("DESYNC_LOG|Node %u|Round %u|Sending M1|ts_auth=%u|DIDi=%02x%02x|SIDn=%02x%02x\n",
           user_id, auth_round, ts_auth, DIDi[0], DIDi[1], SIDn[0], SIDn[1]);
}

static void prepare_data(void)
{
    uint8_t sensor = 9;
    uint8_t K[16];
    memcpy(K, SK, 16);
    uint8_t plaintext[16];
    memset(plaintext, 0, 16);
    plaintext[0] = sensor;
    struct AES_ctx ctx;
    AES_init_ctx(&ctx, K);
    AES_ECB_encrypt(&ctx, plaintext);
    memcpy(data_payload,      DIDi,      32);   /* current DIDi for GW lookup */
    memcpy(data_payload + 32, plaintext,  16);
}

/* reg payload buffer (reused for both initial enroll and re-enroll) */
static uint8_t enroll_payload[1];

/* ==========================================================================
 * Main process
 * ========================================================================== */
PROCESS(user_node, "User Node (Zhou Desync Demo)");
AUTOSTART_PROCESSES(&user_node);
static struct etimer et;

PROCESS_THREAD(user_node, ev, data)
{
    PROCESS_BEGIN();

    user_id = (uint8_t)node_id;
    derive_ki_local();
    discover_gw();

    /* Stagger start: each user delays by its index (seconds) */
    etimer_set(&et, CLOCK_SECOND * (node_id - FIRST_USER_ID + 1));

    while (1) {
        PROCESS_YIELD();

        if (etimer_expired(&et)) {

            /* ================================================================
             * ENROLLMENT
             * ================================================================ */
            if (reg == 0) {
                printf("DESYNC_LOG|Node %u|=== ENROLLMENT START ===\n", user_id);
                print_energest_stats(&cpu_before, &energy_before);

                enroll_payload[0] = user_id;
                coap_init_message(request, COAP_TYPE_CON, COAP_POST, coap_get_mid());
                coap_set_header_uri_path(request, "zhou/reg");
                coap_set_payload(request, enroll_payload, 1);
                COAP_BLOCKING_REQUEST(&ep_gw, request, client_reg_handler);

                reg = 1;
                ts_auth = 0;  /* reset Ni counter after enrollment */

                print_energest_stats(&cpu_after, &energy_after);
                printf("\nDESYNC_ENROLL_ENERGY|%u|cpu_s=%f|energy_j=%f\n",
                       user_id, cpu_after - cpu_before, energy_after - energy_before);
                printf("DESYNC_LOG|Node %u|=== ENROLLMENT COMPLETE ===\n", user_id);

            /* ================================================================
             * ROUND 1: Normal authentication (sync established)
             * ================================================================ */
            } else if (auth_round == 0) {
                auth_round = 1;
                printf("\nDESYNC_LOG|Node %u|========================================\n", user_id);
                printf("DESYNC_LOG|Node %u|Round 1|NORMAL AUTH\n", user_id);
                printf("DESYNC_LOG|Node %u|========================================\n", user_id);

                print_energest_stats(&cpu_before, &energy_before);

                prepare_auth();
                coap_init_message(request, COAP_TYPE_CON, COAP_POST, coap_get_mid());
                coap_set_header_uri_path(request, "zhou/auth");
                coap_set_payload(request, auth_payload, 81);
                COAP_BLOCKING_REQUEST(&ep_gw, request, client_auth_handler);

                if (last_auth_ok) {
                    prepare_data();
                    coap_init_message(request, COAP_TYPE_CON, COAP_POST, coap_get_mid());
                    coap_set_header_uri_path(request, "zhou/data");
                    coap_set_payload(request, data_payload, 48);
                    COAP_BLOCKING_REQUEST(&ep_gw, request, client_data_handler);
                    printf("DESYNC_LOG|Node %u|Round 1|RESULT: SUCCESS\n", user_id);
                }

                print_energest_stats(&cpu_after, &energy_after);
                printf("\nDESYNC_ROUND1_ENERGY|%u|cpu_s=%f|energy_j=%f\n",
                       user_id, cpu_after - cpu_before, energy_after - energy_before);

            /* ================================================================
             * ROUND 2: Auth sent — GW internally triggers M3-drop → User gets
             * no M4.  User keeps old DIDi and SIDn.  Desync established at GW.
             * ================================================================ */
            } else if (auth_round == 1) {
                auth_round = 2;
                printf("\nDESYNC_LOG|Node %u|========================================\n", user_id);
                printf("DESYNC_LOG|Node %u|Round 2|DESYNC TRIGGER (GW will drop M3)\n", user_id);
                printf("DESYNC_LOG|Node %u|========================================\n", user_id);

                print_energest_stats(&cpu_before, &energy_before);

                prepare_auth();
                coap_init_message(request, COAP_TYPE_CON, COAP_POST, coap_get_mid());
                coap_set_header_uri_path(request, "zhou/auth");
                coap_set_payload(request, auth_payload, 81);
                COAP_BLOCKING_REQUEST(&ep_gw, request, client_auth_handler);
                /* last_auth_ok == 0: no M4 received — User stays on old state */

                printf("DESYNC_LOG|Node %u|Round 2|RESULT: DESYNCHRONIZED (no M4)\n", user_id);
                printf("DESYNC_LOG|Node %u|Round 2|User keeps old DIDi=%02x%02x SIDn=%02x%02x\n",
                       user_id, DIDi[0], DIDi[1], SIDn[0], SIDn[1]);

                print_energest_stats(&cpu_after, &energy_after);
                printf("\nDESYNC_ROUND2_ENERGY|%u|cpu_s=%f|energy_j=%f\n",
                       user_id, cpu_after - cpu_before, energy_after - energy_before);

            /* ================================================================
             * ROUND 3: User retries with old DIDi/SIDn → beta mismatch at GW
             * (sn_SIDn ≠ gw_SIDn) → FAIL.
             * Zhou has NO recovery mechanism → User must RE-ENROLL.
             * TOTAL energy = failed auth + re-enroll + recovery auth + data.
             * ================================================================ */
            } else if (auth_round == 2) {
                auth_round = 3;
                printf("\nDESYNC_LOG|Node %u|========================================\n", user_id);
                printf("DESYNC_LOG|Node %u|Round 3|RETRY (expect beta mismatch → FAIL)\n", user_id);
                printf("DESYNC_LOG|Node %u|========================================\n", user_id);

                /* Start Round 3 energy measurement — includes everything below */
                print_energest_stats(&cpu_before, &energy_before);

                /* First attempt: auth with old DIDi/SIDn → FAIL */
                prepare_auth();
                coap_init_message(request, COAP_TYPE_CON, COAP_POST, coap_get_mid());
                coap_set_header_uri_path(request, "zhou/auth");
                coap_set_payload(request, auth_payload, 81);
                COAP_BLOCKING_REQUEST(&ep_gw, request, client_auth_handler);

                if (!last_auth_ok) {
                    printf("DESYNC_LOG|Node %u|Round 3|Auth FAILED as expected (beta mismatch at GW-SN)\n", user_id);
                    printf("DESYNC_LOG|Node %u|Round 3|Zhou has no dual-state → must RE-ENROLL\n", user_id);

                    /* RE-ENROLLMENT: obtain fresh DIDi and SIDn from GW */
                    reg = 0;
                    enroll_payload[0] = user_id;
                    coap_init_message(request, COAP_TYPE_CON, COAP_POST, coap_get_mid());
                    coap_set_header_uri_path(request, "zhou/reg");
                    coap_set_payload(request, enroll_payload, 1);
                    COAP_BLOCKING_REQUEST(&ep_gw, request, client_reg_handler);
                    reg = 1;

                    /* Reset Ni counter post re-enrollment */
                    ts_auth = 0;

                    printf("DESYNC_LOG|Node %u|Round 3|Re-enrolled: DIDi=%02x%02x SIDn=%02x%02x\n",
                           user_id, DIDi[0], DIDi[1], SIDn[0], SIDn[1]);

                    /* Retry auth with fresh credentials → should succeed */
                    prepare_auth();
                    coap_init_message(request, COAP_TYPE_CON, COAP_POST, coap_get_mid());
                    coap_set_header_uri_path(request, "zhou/auth");
                    coap_set_payload(request, auth_payload, 81);
                    COAP_BLOCKING_REQUEST(&ep_gw, request, client_auth_handler);

                    if (last_auth_ok) {
                        prepare_data();
                        coap_init_message(request, COAP_TYPE_CON, COAP_POST, coap_get_mid());
                        coap_set_header_uri_path(request, "zhou/data");
                        coap_set_payload(request, data_payload, 48);
                        COAP_BLOCKING_REQUEST(&ep_gw, request, client_data_handler);
                        printf("DESYNC_LOG|Node %u|Round 3|RESULT: RECOVERY via RE-ENROLL (high cost)\n", user_id);
                    } else {
                        printf("DESYNC_LOG|Node %u|Round 3|RESULT: Recovery failed even after re-enroll\n", user_id);
                    }
                } else {
                    printf("DESYNC_LOG|Node %u|Round 3|Unexpected success with old DIDi/SIDn\n", user_id);
                }

                print_energest_stats(&cpu_after, &energy_after);
                printf("\nDESYNC_ROUND3_ENERGY|%u|cpu_s=%f|energy_j=%f\n",
                       user_id, cpu_after - cpu_before, energy_after - energy_before);

            /* ================================================================
             * ROUND 4: Normal auth post-recovery (confirms system re-synced)
             * ================================================================ */
            } else if (auth_round == 3) {
                auth_round = 4;
                printf("\nDESYNC_LOG|Node %u|========================================\n", user_id);
                printf("DESYNC_LOG|Node %u|Round 4|POST-RECOVERY NORMAL AUTH\n", user_id);
                printf("DESYNC_LOG|Node %u|========================================\n", user_id);

                print_energest_stats(&cpu_before, &energy_before);

                prepare_auth();
                coap_init_message(request, COAP_TYPE_CON, COAP_POST, coap_get_mid());
                coap_set_header_uri_path(request, "zhou/auth");
                coap_set_payload(request, auth_payload, 81);
                COAP_BLOCKING_REQUEST(&ep_gw, request, client_auth_handler);

                if (last_auth_ok) {
                    prepare_data();
                    coap_init_message(request, COAP_TYPE_CON, COAP_POST, coap_get_mid());
                    coap_set_header_uri_path(request, "zhou/data");
                    coap_set_payload(request, data_payload, 48);
                    COAP_BLOCKING_REQUEST(&ep_gw, request, client_data_handler);
                    printf("DESYNC_LOG|Node %u|Round 4|RESULT: SUCCESS — system fully recovered\n", user_id);
                }

                print_energest_stats(&cpu_after, &energy_after);
                printf("\nDESYNC_ROUND4_ENERGY|%u|cpu_s=%f|energy_j=%f\n",
                       user_id, cpu_after - cpu_before, energy_after - energy_before);

                printf("\nDESYNC_LOG|Node %u|=== ZHOU DESYNC DEMONSTRATION COMPLETE ===\n", user_id);
            }

            etimer_reset(&et);
        }
    }

    PROCESS_END();
}
