/* ==========================================================================
 * device-node.c  —  IoT Device Node  (Revised Anonymity Scheme)
 *
 * State machine MIRRORS base scheme (coap-client1.c) exactly:
 *   reg  == 0                    → Enrollment  : /test/reg + /test/reg1
 *   auth == 0 && count < 1       → Auth+KeyEx  : /test/auth  (one combined round)
 *   auth == 1                    → Data         : /test/data  (one-shot, then idle)
 *
 * Measurement positions MIRROR base scheme (coap-client1.c):
 *   (1) End of registration       — cumulative snapshot before auth send
 *   (2) End of authentication 1   — delta (cpu_auth - cpu_reg)  after reply
 *   (3) End of session key sharing 1 — delta (same snapshot; key already
 *                                     derived in client_auth_handler, no
 *                                     extra network round)
 *
 * Packet sizes:
 *   /test/reg   send  16 B   AES_enc(K_AS_D, [id_d | pad])
 *   /test/reg   recv  48 B   AES_enc(K_AS_D, [c_d | m_d(32) | pad])
 *   /test/reg1  send  48 B   AES_enc(K_AS_D, [id_d | Y_dH(32) | R_d | c_as_d | pad])
 *   /test/auth  send  65 B   PID(32) | y_asd(32) | ts_1(1)
 *   /test/auth  recv  33 B   ts_2(1) | m_H(32)
 *   /test/data  send  48 B   PID(32) | AES_enc(K_GW_D[0..15], data(16))
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
#include "net/ipv6/uip-ds6.h"
#include "sys/node-id.h"
#include "random.h"
#include "project-conf.h"
#include "sys/energest.h"

/* --------------------------------------------------------------------------
 * Shared long-term key  — EXACTLY 16 bytes (same as base scheme)
 * -------------------------------------------------------------------------- */
uint8_t k_as_d[16] = {
    0x67,0x61,0x74,0x73,0x20,0x6D,0x79,0x20,
    0x4B,0x75,0x6F,0x67,0x20,0x46,0x75,0x00
};

/* --------------------------------------------------------------------------
 * Device state  — variable names MIRROR base scheme (coap-client1.c)
 * -------------------------------------------------------------------------- */
static uint8_t id_d;
static uint8_t id_as;

static uint8_t c_d;
static uint8_t c_as_d = 3;
static uint8_t y_d    = 2;
static uint8_t h_d;
static uint8_t ts_1 = 1;

static uint8_t m_d[32];
static uint8_t k_gw_d[32];
static uint8_t PID[32];

/* Staging area: auth handler deposits raw reply; process thread derives key */
static uint8_t auth_ts2;
static uint8_t auth_mH[32];

/* State flags  — IDENTICAL names to base scheme */
uint8_t reg   = 0;   /* 0 = not enrolled   */
uint8_t auth  = 0;   /* 0 = auth not done  */
int     count = 0;   /* one-shot guard     */

/* --------------------------------------------------------------------------
 * Energest  — IDENTICAL constants, variable names, and function signature
 *             to base scheme (coap-client1.c)
 * -------------------------------------------------------------------------- */
#define CURRENT_CPU    1.8e-3
#define CURRENT_LPM    0.0545e-3
#define CURRENT_TX     17.4e-3
#define CURRENT_RX     18.8e-3
#define SUPPLY_VOLTAGE 3.0

double cpu_reg,  energy_reg;
double cpu_auth, energy_auth;

static void print_energest_stats(double *seconds_cpu, double *total_energy)
{
    energest_flush();
    unsigned long cpu_ticks = energest_type_time(ENERGEST_TYPE_CPU);
    unsigned long lpm_ticks = energest_type_time(ENERGEST_TYPE_LPM);
    unsigned long tx_ticks  = energest_type_time(ENERGEST_TYPE_TRANSMIT);
    unsigned long rx_ticks  = energest_type_time(ENERGEST_TYPE_LISTEN);

    *seconds_cpu       = cpu_ticks / (double)ENERGEST_SECOND;
    double seconds_lpm = lpm_ticks / (double)ENERGEST_SECOND;
    double seconds_tx  = tx_ticks  / (double)ENERGEST_SECOND;
    double seconds_rx  = rx_ticks  / (double)ENERGEST_SECOND;

    double energy_cpu = *seconds_cpu * CURRENT_CPU * SUPPLY_VOLTAGE;
    double energy_lpm = seconds_lpm  * CURRENT_LPM * SUPPLY_VOLTAGE;
    double energy_tx  = seconds_tx   * CURRENT_TX  * SUPPLY_VOLTAGE;
    double energy_rx  = seconds_rx   * CURRENT_RX  * SUPPLY_VOLTAGE;

    *total_energy = energy_cpu + energy_lpm + energy_tx + energy_rx;
}

/* --------------------------------------------------------------------------
 * Endpoints
 * -------------------------------------------------------------------------- */
static coap_endpoint_t ep_as, ep_gw;
static coap_message_t  request[1];

/* --------------------------------------------------------------------------
 * Helpers  — IDENTICAL implementations to base scheme (coap-client1.c)
 * -------------------------------------------------------------------------- */
uint8_t simulate_puf_response(uint8_t c)
{
    uint8_t path1 = random_rand() ^ c;
    uint8_t path2 = random_rand() ^ c;
    printf("Simulate PUF response: challenge=%u response=%u\n", c,
           (path1 > path2) ? 1 : 0);
    return (path1 > path2) ? 1 : 0;
}

void generate_helper(uint8_t response, uint8_t *helper, uint8_t *secret)
{
    *secret = 1;
    *helper = *secret & response;
}

uint8_t regenerate_response(uint8_t challenge, uint8_t helper)
{
    uint8_t response;
    (helper == 0) ? (response = helper & challenge) : (response = helper || challenge);
    return response;
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

static bool discover_peer_to_authenticate_with(void)
{
    uip_ipaddr_t a;
    uint8_t a_id = id_as;
    uip_ip6addr_u8(&a, 0xfd,0,0,0,0,0,0,0,
                   0x02,a_id,0,a_id,0,a_id,0,a_id);
    uip_ipaddr_copy(&ep_as.ipaddr, &a);
    ep_as.port   = UIP_HTONS(COAP_DEFAULT_PORT);
    ep_as.secure = 0;
    return true;
}

static bool discover_peer_to_authenticate_with1(void)
{
    uip_ipaddr_t a;
    uint8_t g_id = (uint8_t)GW_NODE_ID;
    uip_ip6addr_u8(&a, 0xfd,0,0,0,0,0,0,0,
                   0x02,g_id,0,g_id,0,g_id,0,g_id);
    uip_ipaddr_copy(&ep_gw.ipaddr, &a);
    ep_gw.port   = UIP_HTONS(COAP_DEFAULT_PORT);
    ep_gw.secure = 0;
    return true;
}

/* ==========================================================================
 * CoAP response handlers
 * ========================================================================== */

void client_reg_handler(coap_message_t *response)
{
    const uint8_t *chunk;
    if (!response || coap_get_payload(response, &chunk) < 48) {
        printf("Node %u: Reg-0 dropped\n", id_d);
        return;
    }
    uint8_t plain[48];
    memcpy(plain, chunk, 48);
    aes_dec(k_as_d, plain, 3);
    c_d = plain[0];
    memcpy(m_d, plain + 1, 32);
    printf("Received reg payload\n");
}

void client_reg1_handler(coap_message_t *response)
{
    const uint8_t *chunk;
    if (coap_get_payload(response, &chunk)) {
        reg = 1;
        printf("%s", chunk);
    }
}

/* --------------------------------------------------------------------------
 * Auth reply handler: ts_2(1) | m_H(32) = 33 B
 *
 * Lightweight receiver — ONLY copies ts_2 and m_H into staging globals.
 * Key derivation (m_new, K_GW_D, PID rotation) is done in the process
 * thread AFTER this returns, so the "authentication" and "session key
 * sharing" energest snapshots capture different costs — mirroring the
 * base scheme (coap-client1.c) exactly.
 * -------------------------------------------------------------------------- */
void client_auth_handler(coap_message_t *response)
{
    const uint8_t *chunk;
    if (!response || coap_get_payload(response, &chunk) < 33) {
        printf("No auth payload");
        return;
    }
    auth_ts2 = chunk[0];
    memcpy(auth_mH, chunk + 1, 32);
    printf("\n The value of ts_2 is %u", auth_ts2);
}

void client_data_handler(coap_message_t *response)
{
    const uint8_t *chunk;
    int len = coap_get_payload(response, &chunk);
    printf("Data length: %u\n", len);
    if (!response || len == 0) {
        printf("No data payload");
    } else {
        printf("Data payload: %u\n", chunk[0]);
    }
}

/* ==========================================================================
 * Main process
 * ========================================================================== */
PROCESS(er_example_client, "Erbium Example Client");
AUTOSTART_PROCESSES(&er_example_client);

static struct etimer et;

PROCESS_THREAD(er_example_client, ev, data)
{
    PROCESS_BEGIN();

    id_d  = (uint8_t)node_id;
    id_as = (uint8_t)(AS_NODE_ID + ((node_id - FIRST_DEVICE_ID) % NUM_AS));

    discover_peer_to_authenticate_with();
    discover_peer_to_authenticate_with1();

    /* Staggered start — IDENTICAL to base scheme */
    etimer_set(&et, CLOCK_SECOND * 5);

    while (1) {
        PROCESS_YIELD();

        if (etimer_expired(&et)) {

            /* ================================================================
             * ENROLLMENT — reg == 0
             * Reg-0 + Reg-1 in same timer tick  (IDENTICAL to base scheme)
             * ================================================================ */
            if (reg == 0) {

                /* --- Reg-0 --- */
                uint8_t payload[16];
                memset(payload, 0, 16);
                payload[0] = id_d;
                aes_enc(k_as_d, payload, 1);
                coap_init_message(request, COAP_TYPE_CON, COAP_GET, 0);
                coap_set_header_uri_path(request, "test/reg");
                coap_set_payload(request, payload, 16);
                printf("Sending registration request to server...\n");
                COAP_BLOCKING_REQUEST(&ep_as, request, client_reg_handler);

                /* --- Reg-1 --- */
                uint8_t R_d_enroll = simulate_puf_response(c_d);
                uint8_t secret;
                generate_helper(R_d_enroll, &h_d, &secret);

                uint8_t Y_dH_enroll[32];
                H(&y_d, 1, Y_dH_enroll);

                uint8_t p1[48];
                memset(p1, 0, 48);
                p1[0] = id_d;
                memcpy(p1 + 1, Y_dH_enroll, 32);
                p1[33] = R_d_enroll;
                p1[34] = c_as_d;
                aes_enc(k_as_d, p1, 3);
                coap_init_message(request, COAP_TYPE_CON, COAP_POST, 1);
                coap_set_header_uri_path(request, "test/reg1");
                coap_set_payload(request, p1, sizeof(p1));
                printf("Sending reg1 request\n");
                reg = 1;
                COAP_BLOCKING_REQUEST(&ep_as, request, client_reg1_handler);

            /* ================================================================
             * AUTH + KEY EXCHANGE — auth == 0, count < 1
             *
             * Measurement positions MIRROR base scheme (coap-client1.c):
             *
             *   Before send → print_energest_stats (reg snapshot, twice)
             *   After  recv → print_energest_stats (auth delta)
             *   After  recv → print_energest_stats (session key sharing delta;
             *                 same snapshot — key derived in handler already)
             * ================================================================ */
            } else if (auth == 0 && count < 1) {

                /* --- Mirror base scheme lines 321-323 --- */
                print_energest_stats(&cpu_reg, &energy_reg);
                printf("\n The CPU time and energy at the end of registration for client %u are %f and %f",
                       id_d, cpu_reg, energy_reg);
                print_energest_stats(&cpu_reg, &energy_reg);

                /* Build auth payload: PID(32) | y_asd(32) | ts_1(1) = 65 B */
                uint8_t R_d = regenerate_response(c_d, h_d);

                uint8_t cur_PID[32], pid_buf[33];
                pid_buf[0] = id_d;
                memcpy(pid_buf + 1, m_d, 32);
                H(pid_buf, 33, cur_PID);

                uint8_t Y_dH[32];
                H(&y_d, 1, Y_dH);

                uint8_t mask_in[66], mask[32];
                mask_in[0] = R_d;
                memcpy(mask_in + 1,  m_d,     32);
                memcpy(mask_in + 33, cur_PID, 32);
                mask_in[65] = ts_1;
                H(mask_in, 66, mask);

                uint8_t y_asd[32];
                for (int i = 0; i < 32; i++) y_asd[i] = Y_dH[i] ^ mask[i];

                uint8_t pa[65];
                memcpy(pa,      cur_PID, 32);
                memcpy(pa + 32, y_asd,  32);
                pa[64] = ts_1;

                coap_init_message(request, COAP_TYPE_CON, COAP_POST, 2);
                coap_set_header_uri_path(request, "test/auth");
                coap_set_payload(request, pa, sizeof(pa));
                printf("\n Sending auth_request");
                COAP_BLOCKING_REQUEST(&ep_as, request, client_auth_handler);

                count++;

                if (count == 1) {
                    /* --- Mirror base scheme lines 371-372 ---
                     * Snapshot A: covers only the network round-trip cost.
                     * Key derivation has NOT happened yet.                    */
                    print_energest_stats(&cpu_auth, &energy_auth);
                    printf("\n The CPU time and energy at the end of authentication %u for client %u are %f and %f",
                           count, id_d,
                           (cpu_auth - cpu_reg),
                           (energy_auth - energy_reg));
                }

                /* --- Key derivation in process thread (mirrors base scheme lines 376-440) ---
                 * Recover m_new from auth_mH, derive K_GW_D, rotate m_d and PID. */
                {
                    uint8_t R_d = regenerate_response(c_d, h_d);

                    uint8_t Y_dH[32];
                    H(&y_d, 1, Y_dH);

                    uint8_t cur_PID[32], pid_buf[33];
                    pid_buf[0] = id_d;
                    memcpy(pid_buf + 1, m_d, 32);
                    H(pid_buf, 33, cur_PID);

                    /* mH_mask = H(Y_dH || m_d || R_d || ID_AS || cur_PID || ts_2) */
                    uint8_t mh_in[99], mh_mask[32], m_new[32];
                    memcpy(mh_in,      Y_dH,    32);
                    memcpy(mh_in + 32, m_d,     32);
                    mh_in[64] = R_d;
                    mh_in[65] = id_as;
                    memcpy(mh_in + 66, cur_PID, 32);
                    mh_in[98] = auth_ts2;
                    H(mh_in, 99, mh_mask);
                    for (int i = 0; i < 32; i++) m_new[i] = auth_mH[i] ^ mh_mask[i];

                    /* K_GW_D = H(R_d || m_new) */
                    uint8_t kd_in[33];
                    kd_in[0] = R_d;
                    memcpy(kd_in + 1, m_new, 32);
                    H(kd_in, 33, k_gw_d);

                    /* Rotate m_d and PID */
                    memcpy(m_d, m_new, 32);
                    pid_buf[0] = id_d;
                    memcpy(pid_buf + 1, m_new, 32);
                    H(pid_buf, 33, PID);

                    ts_1++;
                    auth = 1;
                    printf("\nNode %u: KeyEx OK. New PID=%02x%02x%02x\n",
                           id_d, PID[0], PID[1], PID[2]);
                }

                if (count == 1) {
                    /* --- Mirror base scheme lines 434-437 ---
                     * Snapshot B: covers network round-trip + local key
                     * derivation (3× SHA256 + XOR). B > A by that delta.     */
                    print_energest_stats(&cpu_auth, &energy_auth);
                    printf("\n The CPU time and energy at the end of session key sharing %u for client %u are %f and %f",
                           count, id_d,
                           (cpu_auth - cpu_reg),
                           (energy_auth - energy_reg));
                }

            /* ================================================================
             * DATA — auth == 1  (one-shot, mirrors base scheme)
             *
             * Send one PID-addressed encrypted data packet to GW then idle.
             * PID rotation already performed inside client_auth_handler.
             * ================================================================ */
            } else if (auth == 1) {

                print_energest_stats(&cpu_reg, &energy_reg);

                uint8_t sensor[16];
                memset(sensor, 0, 16);
                sensor[0] = 9;

                uint8_t K_AES[16];
                memcpy(K_AES, k_gw_d, 16);
                struct AES_ctx aes_ctx_ch_d;
                AES_init_ctx(&aes_ctx_ch_d, K_AES);
                AES_ECB_encrypt(&aes_ctx_ch_d, sensor);

                uint8_t pd[48];
                memcpy(pd,      PID,    32);
                memcpy(pd + 32, sensor, 16);

                printf("Authentication success, sending data request\n");
                coap_init_message(request, COAP_TYPE_CON, COAP_GET, 3);
                coap_set_header_uri_path(request, "test/data");
                coap_set_payload(request, pd, sizeof(pd));
                COAP_BLOCKING_REQUEST(&ep_gw, request, client_data_handler);

                auth = 0;
            }

            etimer_reset(&et);
        }
    }

    PROCESS_END();
}
