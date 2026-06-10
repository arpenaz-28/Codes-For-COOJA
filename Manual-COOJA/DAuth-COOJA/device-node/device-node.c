/* ==========================================================================
 * device-node.c  —  IoT Device Node  (DAuth / Das[1] Base Scheme)
 *
 * Implements the base DAuth protocol WITHOUT anonymity extensions:
 *   - Real ID_D sent in every auth message (no pseudonym)
 *   - Single nonce state (m_curr only, no m_old / desync recovery)
 *   - Auth + Key Exchange in ONE combined CoAP round (like Proposed)
 *
 * Measurement methodology: DELTA-SNAPSHOT Energest
 *   ENROLL:   snapshot BEFORE Reg-0 → snapshot AFTER Reg-1   → delta
 *   AUTH+KEx: snapshot BEFORE auth  → snapshot AFTER key deriv → delta
 *
 * Output format matches Proposed / LAAKA so scripts can parse all three:
 *   ENROLL_ENERGY|<id>|cpu_s=<X>|energy_j=<X>
 *   AUTH_ENERGY|<id>|cpu_ticks=0|energy_ticks=0|cpu_s=<X>|energy_j=<X>
 *
 * Packet sizes:
 *   /test/reg   send 16 B   AES_enc(K_AS_D, [id_d | pad])
 *   /test/reg   recv 48 B   AES_enc(K_AS_D, [c_d | m_d(32) | pad])
 *   /test/reg1  send 48 B   AES_enc(K_AS_D, [id_d | Y_dH(32) | R_d | c_as_d | pad])
 *   /test/auth  send 34 B   id_d(1) | y_asd(32) | ts_1(1)
 *   /test/auth  recv 33 B   ts_2(1) | m_H(32)
 *   /test/data  send 17 B   id_d(1) | AES_enc(K_GW_D[0:15], data(16))
 *
 * Topology (100-mote):
 *   Node  1        = GW  (RPL root)
 *   Nodes 2-80     = AS  (2 active: nodes 2 and 3)
 *   Nodes 81-100   = Device nodes
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
 * Shared long-term key (identical to Proposed / base scheme)
 * -------------------------------------------------------------------------- */
static const uint8_t k_as_d[16] = {
    0x67,0x61,0x74,0x73,0x20,0x6D,0x79,0x20,
    0x4B,0x75,0x6F,0x67,0x20,0x46,0x75,0x00
};

/* --------------------------------------------------------------------------
 * Device state
 * -------------------------------------------------------------------------- */
static uint8_t id_d;           /* = node_id */
static uint8_t id_as;          /* assigned AS */

static uint8_t c_d;            /* PUF challenge received from AS */
static uint8_t c_as_d = 3;     /* challenge this device sends to AS */
static uint8_t y_d    = 2;     /* group membership secret */
static uint8_t h_d;            /* PUF helper */
static uint8_t ts_1 = 1;       /* sequential nonce / timestamp */

static uint8_t m_d[32];        /* 32-byte session nonce (single state, no m_old) */
static uint8_t k_gw_d[32];     /* derived session key with GW */

/* Staging: auth handler deposits ts_2 and m_H; process thread derives key */
static uint8_t auth_ts2;
static uint8_t auth_mH[32];

/* State flags */
static uint8_t reg   = 0;   /* 0 = not enrolled */
static uint8_t auth  = 0;   /* 0 = auth not done */
static int     count = 0;   /* one-shot guard: only 1 auth round measured */

/* --------------------------------------------------------------------------
 * Energest — delta-snapshot methodology
 *   Before phase → snapshot A
 *   After  phase → snapshot B
 *   Report: B - A  (only the phase cost, not RPL boot time)
 * -------------------------------------------------------------------------- */
#define CURRENT_CPU    1.8e-3
#define CURRENT_LPM    0.0545e-3
#define CURRENT_TX     17.4e-3
#define CURRENT_RX     18.8e-3
#define SUPPLY_VOLTAGE 3.0

static double cpu_enroll_before, energy_enroll_before;
static double cpu_enroll_after,  energy_enroll_after;
static double cpu_auth_before,   energy_auth_before;
static double cpu_auth_after,    energy_auth_after;

static void read_energest(double *seconds_cpu, double *total_energy)
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

static void discover_endpoints(void)
{
    uip_ipaddr_t a;

    /* AS: round-robin among NUM_AS servers starting at AS_NODE_ID */
    uint8_t a_id = (uint8_t)(AS_NODE_ID + ((node_id - FIRST_DEVICE_ID) % NUM_AS));
    id_as = a_id;
    uip_ip6addr_u8(&a, 0xfd,0,0,0,0,0,0,0,
                   0x02,a_id,0,a_id,0,a_id,0,a_id);
    uip_ipaddr_copy(&ep_as.ipaddr, &a);
    ep_as.port   = UIP_HTONS(COAP_DEFAULT_PORT);
    ep_as.secure = 0;

    /* GW: always node 1 */
    uint8_t g_id = (uint8_t)GW_NODE_ID;
    uip_ip6addr_u8(&a, 0xfd,0,0,0,0,0,0,0,
                   0x02,g_id,0,g_id,0,g_id,0,g_id);
    uip_ipaddr_copy(&ep_gw.ipaddr, &a);
    ep_gw.port   = UIP_HTONS(COAP_DEFAULT_PORT);
    ep_gw.secure = 0;
}

/* --------------------------------------------------------------------------
 * Crypto helpers
 * -------------------------------------------------------------------------- */
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

/* ==========================================================================
 * CoAP response handlers
 * ========================================================================== */

/* Reg-0 reply: AES(K_AS_D, [c_d | m_d(32) | pad]) = 48 B */
static void client_reg_handler(coap_message_t *response)
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
    printf("Node %u: Reg-0 OK. c_d=%u m_d[0]=%02x\n", id_d, c_d, m_d[0]);
}

/* Reg-1 reply: "Registered" */
static void client_reg1_handler(coap_message_t *response)
{
    const uint8_t *chunk;
    if (response && coap_get_payload(response, &chunk)) {
        reg = 1;
        printf("Node %u: Reg-1 OK\n", id_d);
    }
}

/* Auth reply: ts_2(1) | m_H(32) = 33 B
 * Only copies raw bytes; key derivation happens in the process thread
 * so the AUTH snapshot captures BOTH the network cost AND the crypto cost. */
static void client_auth_handler(coap_message_t *response)
{
    const uint8_t *chunk;
    if (!response || coap_get_payload(response, &chunk) < 33) {
        printf("Node %u: Auth reply dropped\n", id_d);
        return;
    }
    auth_ts2 = chunk[0];
    memcpy(auth_mH, chunk + 1, 32);
    printf("Node %u: Auth reply OK. ts_2=%u\n", id_d, auth_ts2);
}

/* Data ACK from GW */
static void client_data_handler(coap_message_t *response)
{
    if (!response)
        printf("Node %u: Data ACK missing\n", id_d);
    else
        printf("Node %u: Data confirmed\n", id_d);
}

/* ==========================================================================
 * Main process
 * ========================================================================== */
PROCESS(dauth_device, "DAuth IoT Device");
AUTOSTART_PROCESSES(&dauth_device);

static struct etimer et;

PROCESS_THREAD(dauth_device, ev, data)
{
    PROCESS_BEGIN();

    id_d = (uint8_t)node_id;
    discover_endpoints();

    /* Staggered start (IDENTICAL to Proposed scheme): each device begins at
     * (5 + node_id) s.  This waits out RPL convergence and spreads devices in
     * time so each enrollment CoAP round-trip is fast — the BEFORE/AFTER delta
     * then captures crypto + a converged round-trip, NOT the RPL boot wait. */
    etimer_set(&et, CLOCK_SECOND * (5 + node_id));

    while (1) {
        PROCESS_YIELD();

        if (etimer_expired(&et)) {

            /* ================================================================
             * PHASE 1 — ENROLLMENT (reg == 0)
             *
             * Reg-0: device → AS: AES(K_AS_D, [id_d | pad]) = 16 B
             *        AS → device: AES(K_AS_D, [c_d | m_d(32) | pad]) = 48 B
             * Reg-1: device → AS: AES(K_AS_D, [id_d | Y_dH(32) | R_d | c_as_d | pad]) = 48 B
             *        AS → device: "Registered"
             *
             * Measurement: delta from BEFORE Reg-0 to AFTER Reg-1.
             * This captures ONLY enrollment crypto, NOT RPL boot time.
             * ================================================================ */
            if (reg == 0) {

                /* --- Snapshot A: before enrollment begins --- */
                read_energest(&cpu_enroll_before, &energy_enroll_before);

                /* Reg-0 */
                uint8_t payload[16];
                memset(payload, 0, 16);
                payload[0] = id_d;
                aes_enc(k_as_d, payload, 1);
                coap_init_message(request, COAP_TYPE_CON, COAP_GET, 0);
                coap_set_header_uri_path(request, "test/reg");
                coap_set_payload(request, payload, 16);
                printf("Node %u: Sending Reg-0 → AS %u\n", id_d, id_as);
                COAP_BLOCKING_REQUEST(&ep_as, request, client_reg_handler);

                /* Reg-1 */
                uint8_t R_d_enroll = simulate_puf_response(c_d);
                uint8_t secret;
                generate_helper(R_d_enroll, &h_d, &secret);

                uint8_t Y_dH_enroll[32];
                H(&y_d, 1, Y_dH_enroll);

                uint8_t p1[48];
                memset(p1, 0, 48);
                p1[0]  = id_d;
                memcpy(p1 + 1, Y_dH_enroll, 32);
                p1[33] = R_d_enroll;
                p1[34] = c_as_d;
                aes_enc(k_as_d, p1, 3);
                coap_init_message(request, COAP_TYPE_CON, COAP_POST, 1);
                coap_set_header_uri_path(request, "test/reg1");
                coap_set_payload(request, p1, sizeof(p1));
                printf("Node %u: Sending Reg-1 → AS %u\n", id_d, id_as);
                COAP_BLOCKING_REQUEST(&ep_as, request, client_reg1_handler);

                /* --- Snapshot B: after enrollment completes --- */
                read_energest(&cpu_enroll_after, &energy_enroll_after);
                printf("ENROLL_ENERGY|%u|cpu_s=%f|energy_j=%f\n",
                       id_d,
                       cpu_enroll_after  - cpu_enroll_before,
                       energy_enroll_after - energy_enroll_before);

            /* ================================================================
             * PHASE 2+3 — AUTH + KEY EXCHANGE (reg == 1, count < 1)
             *
             * One combined CoAP round to AS (same as Proposed):
             *   send: id_d(1) | y_asd(32) | ts_1(1) = 34 B
             *   recv: ts_2(1) | m_H(32)              = 33 B
             *
             * y_asd = Y_dH XOR H(R_d || m_d || id_d || ts_1)
             *                              ^-- ID_D not PID (no anonymity)
             *
             * Key derivation (in process thread after CoAP returns):
             *   mH_mask = H(Y_dH || m_d || R_d || id_as || id_d || ts_2)
             *   m_new   = auth_mH XOR mH_mask
             *   K_GW_D  = H(R_d || m_new)
             *   m_d     = m_new   (update; no rotation history kept)
             *
             * Measurement: delta from BEFORE auth send to AFTER key derivation.
             * ================================================================ */
            } else if (auth == 0 && count < 1) {

                /* --- Snapshot C: before auth begins --- */
                read_energest(&cpu_auth_before, &energy_auth_before);

                uint8_t R_d = regenerate_response(c_d, h_d);

                uint8_t Y_dH[32];
                H(&y_d, 1, Y_dH);

                /* mask = H(R_d(1) | m_d(32) | id_d(1) | ts_1(1)) = 35-byte input */
                uint8_t mask_in[35], mask[32];
                mask_in[0] = R_d;
                memcpy(mask_in + 1, m_d, 32);
                mask_in[33] = id_d;
                mask_in[34] = ts_1;
                H(mask_in, 35, mask);

                uint8_t y_asd[32];
                for (int i = 0; i < 32; i++) y_asd[i] = Y_dH[i] ^ mask[i];

                /* Auth packet: id_d(1) | y_asd(32) | ts_1(1) = 34 B */
                uint8_t pa[34];
                pa[0] = id_d;
                memcpy(pa + 1, y_asd, 32);
                pa[33] = ts_1;

                coap_init_message(request, COAP_TYPE_CON, COAP_POST, 2);
                coap_set_header_uri_path(request, "test/auth");
                coap_set_payload(request, pa, sizeof(pa));
                printf("Node %u: Sending Auth → AS %u\n", id_d, id_as);
                COAP_BLOCKING_REQUEST(&ep_as, request, client_auth_handler);

                count++;

                /* Key derivation (process thread — NOT in the CoAP handler):
                 * mH_mask = H(Y_dH(32) | m_d(32) | R_d(1) | id_as(1) | id_d(1) | ts_2(1))
                 *         = H[68-byte input]
                 * m_new   = auth_mH XOR mH_mask
                 * K_GW_D  = H(R_d(1) | m_new(32)) */
                {
                    uint8_t mh_in[68], mh_mask[32], m_new[32];
                    memcpy(mh_in,      Y_dH, 32);
                    memcpy(mh_in + 32, m_d,  32);
                    mh_in[64] = R_d;
                    mh_in[65] = id_as;
                    mh_in[66] = id_d;
                    mh_in[67] = auth_ts2;
                    H(mh_in, 68, mh_mask);
                    for (int i = 0; i < 32; i++) m_new[i] = auth_mH[i] ^ mh_mask[i];

                    uint8_t kd_in[33];
                    kd_in[0] = R_d;
                    memcpy(kd_in + 1, m_new, 32);
                    H(kd_in, 33, k_gw_d);

                    /* Update nonce (no old-state history in base scheme) */
                    memcpy(m_d, m_new, 32);
                    ts_1++;
                    auth = 1;

                    printf("Node %u: KeyEx OK. K_GW_D=%02x%02x%02x\n",
                           id_d, k_gw_d[0], k_gw_d[1], k_gw_d[2]);
                }

                /* --- Snapshot D: after auth + key derivation --- */
                read_energest(&cpu_auth_after, &energy_auth_after);
                printf("AUTH_ENERGY|%u|cpu_ticks=0|energy_ticks=0|cpu_s=%f|energy_j=%f\n",
                       id_d,
                       cpu_auth_after  - cpu_auth_before,
                       energy_auth_after - energy_auth_before);

            /* ================================================================
             * PHASE 4 — DATA (auth == 1)
             *
             * Data packet: id_d(1) | AES_enc(K_GW_D[0:15], sensor(16)) = 17 B
             * GW looks up the session by id_d.
             * ================================================================ */
            } else if (auth == 1) {

                uint8_t sensor[16];
                memset(sensor, 0, 16);
                sensor[0] = 9;   /* dummy sensor value */

                uint8_t K_AES[16];
                memcpy(K_AES, k_gw_d, 16);
                struct AES_ctx aes_ctx;
                AES_init_ctx(&aes_ctx, K_AES);
                AES_ECB_encrypt(&aes_ctx, sensor);

                uint8_t pd[17];
                pd[0] = id_d;
                memcpy(pd + 1, sensor, 16);

                printf("Node %u: Sending data → GW\n", id_d);
                coap_init_message(request, COAP_TYPE_CON, COAP_GET, 3);
                coap_set_header_uri_path(request, "test/data");
                coap_set_payload(request, pd, sizeof(pd));
                COAP_BLOCKING_REQUEST(&ep_gw, request, client_data_handler);

                auth = 0;   /* idle after first data; count >= 1 prevents re-auth */
            }

            etimer_reset(&et);
        }
    }

    PROCESS_END();
}
