/* ==========================================================================
 * device-node.c  —  IoT Device (Base Scheme, ALIGNED build)
 *
 * MODIFIED VERSION: Auth + KeyEx + Data all happen in ONE timer tick,
 * matching the measurement methodology of Proposed and LAAKA schemes.
 *
 * Nodes 81-100.  Protocol:
 *   reg == 0   → Enrollment: /test/reg + /test/reg1 to AS
 *   count < 1  → Auth + KeyEx + Data (all in one tick)
 *   count >= 1 → Ongoing data to GW
 *
 * Energy measurements (3 levels, all in same tick):
 *   ENROLL_ENERGY    — around enrollment block
 *   AUTH_ONLY_ENERGY — auth CoAP + session key only (crypto-only)
 *   PROTOCOL_ENERGY  — auth + keyex, excludes data CoAP
 *   AUTH_TOTAL_ENERGY — auth + keyex + data (matches Proposed/LAAKA Auth)
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
 * Protocol constants
 * -------------------------------------------------------------------------- */
static uint8_t id_d, id_as = 2;
static uint8_t y_d = 2, c_as_d = 3, c_d, m_d, h_d;
static uint8_t g = 5, p = 23, a_dh = 5;

static const uint8_t k_as_d[16] = {
    0x67,0x61,0x74,0x73,0x20,0x6D,0x79,0x20,
    0x4B,0x75,0x6F,0x67,0x20,0x46,0x75,0x00
};

static uint8_t reg = 0, auth = 0;
static uint8_t M_d[32], k_gw_d[32], K_GW_D[16];
static uint8_t count = 0;

/* --------------------------------------------------------------------------
 * Energest
 * -------------------------------------------------------------------------- */
#define CURRENT_CPU    1.8e-3
#define CURRENT_LPM    0.0545e-3
#define CURRENT_TX     17.4e-3
#define CURRENT_RX     18.8e-3
#define SUPPLY_VOLTAGE 3.0

double cpu_enroll_before, energy_enroll_before;
double cpu_enroll_after,  energy_enroll_after;
double cpu_auth_before,   energy_auth_before;
double cpu_auth_after,    energy_auth_after;
double cpu_keyex_after,   energy_keyex_after;
double cpu_total_after,   energy_total_after;

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
 * Crypto helpers
 * -------------------------------------------------------------------------- */
static void H(const uint8_t *in, uint16_t len, uint8_t *out)
{
    SHA256_CTX ctx;
    uint8_t full[32];
    sha256_init(&ctx);
    sha256_update(&ctx, in, len);
    sha256_final(&ctx, full);
    memcpy(out, full, 32);
}

static uint8_t simulate_puf_response(uint8_t c)
{
    uint8_t path1 = random_rand() ^ c;
    uint8_t path2 = random_rand() ^ c;
    return (path1 > path2) ? 1 : 0;
}

static void generate_helper(uint8_t response, uint8_t *helper, uint8_t *secret)
{
    *secret = 1;
    *helper = *secret & response;
}

static uint8_t regenerate_response(uint8_t challenge, uint8_t helper)
{
    return (helper == 0) ? (helper & challenge) : (helper || challenge);
}

/* --------------------------------------------------------------------------
 * Endpoints
 * -------------------------------------------------------------------------- */
static coap_endpoint_t ep_as, ep_gw;
static coap_message_t  request[1];

static void discover_endpoints(void)
{
    uip_ipaddr_t addr;

    /* AS: devices < AS_SPLIT_ID → AS node 2, else AS node 3 */
    uint8_t as_id = (node_id < AS_SPLIT_ID) ?
                    (uint8_t)AS_NODE_ID : (uint8_t)AS2_NODE_ID;
    uip_ip6addr_u8(&addr, 0xfd,0,0,0,0,0,0,0,
                   0x02,as_id,0,as_id,0,as_id,0,as_id);
    uip_ipaddr_copy(&ep_as.ipaddr, &addr);
    ep_as.port = UIP_HTONS(COAP_DEFAULT_PORT);

    /* GW: always node 1 */
    uint8_t gw_id = (uint8_t)GW_NODE_ID;
    uip_ip6addr_u8(&addr, 0xfd,0,0,0,0,0,0,0,
                   0x02,gw_id,0,gw_id,0,gw_id,0,gw_id);
    uip_ipaddr_copy(&ep_gw.ipaddr, &addr);
    ep_gw.port = UIP_HTONS(COAP_DEFAULT_PORT);
}

/* --------------------------------------------------------------------------
 * CoAP response handlers
 * -------------------------------------------------------------------------- */
static uint8_t reg_payload[16];
static uint8_t hpayload[34];
static uint8_t hash[32];

static void client_reg_handler(coap_message_t *resp)
{
    const uint8_t *chunk;
    if (!resp || coap_get_payload(resp, &chunk) < 16) {
        printf("Node %u: Reg dropped\n", id_d);
        return;
    }
    memcpy(reg_payload, chunk, 16);
    printf("Node %u: Received reg payload\n", id_d);
}

static void client_reg1_handler(coap_message_t *resp)
{
    const uint8_t *chunk;
    if (resp && coap_get_payload(resp, &chunk)) {
        reg = 1;
        printf("Node %u: %s\n", id_d, (char *)chunk);
    }
}

static void client_auth_handler(coap_message_t *resp)
{
    const uint8_t *chunk;
    if (!resp || coap_get_payload(resp, &chunk) < 34) {
        printf("Node %u: Auth reply dropped\n", id_d);
        return;
    }
    memcpy(hpayload, chunk, 34);
    printf("Node %u: Auth reply received\n", id_d);
}

static void client_key_update_handler(coap_message_t *resp)
{
    const uint8_t *chunk;
    if (!resp || coap_get_payload(resp, &chunk) < 16) {
        printf("Node %u: Keyupdate reply dropped\n", id_d);
        return;
    }
    uint8_t payload[16];
    memcpy(payload, chunk, 16);
    struct AES_ctx ctx;
    AES_init_ctx(&ctx, K_GW_D);
    AES_ECB_decrypt(&ctx, payload);

    uint8_t beta = payload[0];
    k_gw_d[0] = (beta ^ a_dh) % p;
    printf("Node %u: Key update done, k_gw_d[0]=%u\n", id_d, k_gw_d[0]);
}

static void client_data_handler(coap_message_t *resp)
{
    const uint8_t *chunk;
    int len = 0;
    if (resp) len = coap_get_payload(resp, &chunk);
    if (!resp || len == 0) {
        printf("Node %u: Data ACK missing\n", id_d);
    } else {
        auth = chunk[0];
        printf("Node %u: Data confirmed\n", id_d);
    }
}

/* ==========================================================================
 * Main process
 * ========================================================================== */
PROCESS(device_node, "IoT Device");
AUTOSTART_PROCESSES(&device_node);
static struct etimer et;

PROCESS_THREAD(device_node, ev, data)
{
    PROCESS_BEGIN();

    id_d = (uint8_t)node_id;
    discover_endpoints();

    etimer_set(&et, CLOCK_SECOND * (5 + node_id));

    while (1) {
        PROCESS_YIELD();

        if (etimer_expired(&et)) {

            /* ============================================================
             * ENROLLMENT — reg == 0
             * Two-step registration with AS: /test/reg then /test/reg1
             * ============================================================ */
            if (reg == 0) {

                /* === ENROLL BEFORE snapshot === */
                print_energest_stats(&cpu_enroll_before, &energy_enroll_before);

                /* Step 0: send AES(k_as_d, [ID_d]) → get [c_d, M_d] */
                uint8_t payload[16];
                memset(payload, 0, 16);
                payload[0] = id_d;
                struct AES_ctx ctx;
                AES_init_ctx(&ctx, k_as_d);
                AES_ECB_encrypt(&ctx, payload);

                coap_init_message(request, COAP_TYPE_CON, COAP_GET, 0);
                coap_set_header_uri_path(request, "test/reg");
                coap_set_payload(request, payload, 16);
                printf("Node %u: Sending reg step-0\n", id_d);
                COAP_BLOCKING_REQUEST(&ep_as, request, client_reg_handler);

                /* Decrypt reg reply */
                AES_init_ctx(&ctx, k_as_d);
                AES_ECB_decrypt(&ctx, reg_payload);
                c_d = reg_payload[0];
                m_d = reg_payload[1];
                memset(M_d, 0, 32);
                M_d[0] = m_d;

                /* Step 1: send AES(k_as_d, [ID_d, y_d, R_d, c_as_d]) → "Registered" */
                memset(payload, 0, 16);
                payload[0] = id_d;
                payload[1] = y_d;
                uint8_t R_d = simulate_puf_response(c_d);
                uint8_t secret;
                generate_helper(R_d, &h_d, &secret);
                payload[2] = R_d;
                payload[3] = c_as_d;
                AES_init_ctx(&ctx, k_as_d);
                AES_ECB_encrypt(&ctx, payload);

                coap_init_message(request, COAP_TYPE_CON, COAP_GET, 1);
                coap_set_header_uri_path(request, "test/reg1");
                coap_set_payload(request, payload, 16);
                printf("Node %u: Sending reg step-1\n", id_d);
                COAP_BLOCKING_REQUEST(&ep_as, request, client_reg1_handler);

                /* === ENROLL AFTER snapshot === */
                print_energest_stats(&cpu_enroll_after, &energy_enroll_after);
                printf("ENROLL_ENERGY|%u|cpu_s=%f|energy_j=%f\n",
                       id_d,
                       cpu_enroll_after - cpu_enroll_before,
                       energy_enroll_after - energy_enroll_before);

            /* ============================================================
             * AUTH + KEY EXCHANGE + DATA — all in ONE timer tick
             * (Aligned with Proposed/LAAKA measurement methodology)
             *
             * Three measurement snapshots:
             *   BEFORE → auth CoAP + session key → AUTH_ONLY_ENERGY
             *          → keyex CoAP             → PROTOCOL_ENERGY
             *          → data CoAP              → AUTH_TOTAL_ENERGY
             * ============================================================ */
            } else if (count < 1) {

                /* === BEFORE snapshot (start of entire block) === */
                print_energest_stats(&cpu_auth_before, &energy_auth_before);

                /* ---- PART 1: Authentication (CoAP to AS + session key) ---- */
                uint8_t R_d = regenerate_response(c_d, h_d);

                uint8_t Y_d_H[32];
                H(&y_d, 1, Y_d_H);

                uint8_t data_c[35];
                memset(data_c, 0, 35);
                data_c[0] = R_d;
                memcpy(data_c + 1, M_d, 32);
                data_c[33] = id_d;
                data_c[34] = 0; /* ts_1 */

                H(data_c, 35, hash);

                for (int i = 0; i < 32; i++)
                    hash[i] = hash[i] ^ Y_d_H[i];

                hpayload[0] = id_d;
                memcpy(hpayload + 1, hash, 32);
                hpayload[33] = 0; /* ts_1 */

                coap_init_message(request, COAP_TYPE_CON, COAP_POST, 2);
                coap_set_header_uri_path(request, "test/auth");
                coap_set_payload(request, hpayload, 34);
                printf("Node %u: Sending auth request\n", id_d);
                COAP_BLOCKING_REQUEST(&ep_as, request, client_auth_handler);

                /* Compute session key from reply */
                R_d = regenerate_response(c_d, h_d);
                uint8_t ts_2 = hpayload[33];
                H(&y_d, 1, Y_d_H);

                uint8_t data_dash[68];
                memset(data_dash, 0, 68);
                memcpy(data_dash, Y_d_H, 32);
                memcpy(data_dash + 32, M_d, 32);
                data_dash[64] = R_d;
                data_dash[65] = id_as;
                data_dash[66] = id_d;
                data_dash[67] = ts_2;

                H(data_dash, 68, hash);

                memcpy(M_d, hpayload + 1, 32);
                for (int i = 0; i < 32; i++)
                    M_d[i] = M_d[i] ^ hash[i];

                uint8_t key_in[33];
                key_in[0] = R_d;
                memcpy(key_in + 1, M_d, 32);
                H(key_in, 33, k_gw_d);

                auth = 1;

                /* === AUTH ONLY snapshot (after auth, before keyex) === */
                print_energest_stats(&cpu_auth_after, &energy_auth_after);
                printf("AUTH_ONLY_ENERGY|%u|cpu_s=%f|energy_j=%f\n",
                       id_d,
                       cpu_auth_after - cpu_auth_before,
                       energy_auth_after - energy_auth_before);

                /* ---- PART 2: Key Exchange (DH CoAP to GW) ---- */
                memset(K_GW_D, 0, 16);
                for (int i = 0; i < 16; i++)
                    K_GW_D[i] = k_gw_d[i];

                uint8_t alpha = (g ^ a_dh) % p;
                uint8_t p1[17];
                memset(p1, 0, 17);
                p1[0] = (uint8_t)node_id;

                uint8_t payload[16];
                memset(payload, 0, 16);
                payload[0] = alpha;
                struct AES_ctx ctx;
                AES_init_ctx(&ctx, K_GW_D);
                AES_ECB_encrypt(&ctx, payload);
                memcpy(p1 + 1, payload, 16);

                coap_init_message(request, COAP_TYPE_CON, COAP_GET, 2);
                coap_set_header_uri_path(request, "test/keyupdate");
                coap_set_payload(request, p1, 17);
                printf("Node %u: Sending key update to GW\n", id_d);
                COAP_BLOCKING_REQUEST(&ep_gw, request, client_key_update_handler);

                for (int i = 1; i < 32; i++)
                    k_gw_d[i] = 0;

                /* === PROTOCOL ONLY snapshot (after keyex, before data) === */
                print_energest_stats(&cpu_keyex_after, &energy_keyex_after);
                printf("PROTOCOL_ENERGY|%u|cpu_s=%f|energy_j=%f\n",
                       id_d,
                       cpu_keyex_after - cpu_auth_before,
                       energy_keyex_after - energy_auth_before);

                /* ---- PART 3: First Data (CoAP to GW) ---- */
                uint8_t data_val = 9;
                uint8_t buffer[17];
                memset(buffer, 0, 17);
                buffer[0] = id_d;
                memset(payload, 0, 16);
                payload[0] = data_val;

                memset(K_GW_D, 0, 16);
                for (int i = 0; i < 16; i++)
                    K_GW_D[i] = k_gw_d[i];
                AES_init_ctx(&ctx, K_GW_D);
                AES_ECB_encrypt(&ctx, payload);
                memcpy(buffer + 1, payload, 16);

                coap_init_message(request, COAP_TYPE_CON, COAP_GET, 3);
                coap_set_header_uri_path(request, "test/data");
                coap_set_payload(request, buffer, 17);
                printf("Node %u: Sending data to GW\n", id_d);
                COAP_BLOCKING_REQUEST(&ep_gw, request, client_data_handler);

                count++;

                /* === TOTAL snapshot (after data = matches Proposed Auth) === */
                print_energest_stats(&cpu_total_after, &energy_total_after);
                printf("AUTH_TOTAL_ENERGY|%u|cpu_s=%f|energy_j=%f\n",
                       id_d,
                       cpu_total_after - cpu_auth_before,
                       energy_total_after - energy_auth_before);

                /* Legacy format for backward-compatible extraction */
                printf("\n The CPU time and energy at the end of authentication %u for client %u are %f and %f",
                       count, id_d,
                       cpu_total_after - cpu_auth_before,
                       energy_total_after - energy_auth_before);

            /* ============================================================
             * ONGOING DATA — count >= 1
             * ============================================================ */
            } else if (count >= 1) {
                uint8_t data_val = 9;
                uint8_t payload[16];
                uint8_t buffer[17];
                memset(buffer, 0, 17);
                buffer[0] = id_d;
                memset(payload, 0, 16);
                payload[0] = data_val;

                memset(K_GW_D, 0, 16);
                for (int i = 0; i < 16; i++)
                    K_GW_D[i] = k_gw_d[i];
                struct AES_ctx ctx;
                AES_init_ctx(&ctx, K_GW_D);
                AES_ECB_encrypt(&ctx, payload);
                memcpy(buffer + 1, payload, 16);

                coap_init_message(request, COAP_TYPE_CON, COAP_GET, 3);
                coap_set_header_uri_path(request, "test/data");
                coap_set_payload(request, buffer, 17);
                COAP_BLOCKING_REQUEST(&ep_gw, request, client_data_handler);
            }

            etimer_reset(&et);
        }
    }

    PROCESS_END();
}
