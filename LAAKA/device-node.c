/* ==========================================================================
 * device-node.c  —  IoT Device  (LAAKA scheme)
 *
 * Maps to IoT device D_j in the LAAKA paper.
 *
 * State machine (mirrors base scheme measurement methodology):
 *   reg == 0   → Registration with RA (AS node)
 *   reg == 1,
 *   count < 1  → Auth with fog server (GW) + Ack + Data
 *                [BEFORE] energest snapshot
 *                Auth CoAP → Ack CoAP → Data CoAP
 *                [AFTER] energest snapshot, print AUTH_ENERGY
 *   count >= 1 → keep sending data every tick
 *
 * Registration (LAAKA §4.2.2):
 *   Device computes Ad = H(IDd || r2), sends to RA.
 *   RA replies with (TIDd, TIDf, Af, Bk).
 *
 * Authentication (LAAKA §4.3):
 *   Step 1:   Device → GW:  AuthReq = {TIDd, Td, Cd, Ed, Gd}
 *   Step 6-7: Device verifies AuthRep = {TIDf, Tf, Ts, Cf, Ef, Gf}
 *   Step 8:   Device → GW:  Ack = h(rf || Bk || SK)
 *   Data:     Device → GW:  encrypted sensor data
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
#define HASH_LEN    20
#define RAND_LEN    20

/* Message sizes */
#define REG_REQ_LEN    32   /* AES: IDd(1)+Ad(20)+pad(11) = 2 blocks */
#define REG_REP_LEN    80   /* AES: TIDd(20)+TIDf(20)+Af(20)+Bk(20) = 5 blocks */
#define AUTH_REQ_LEN   81   /* TIDd(20)+Td(1)+Cd(20)+Ed(20)+Gd(20) */
#define AUTH_REP_LEN   82   /* TIDf(20)+Tf(1)+Ts(1)+Cf(20)+Ef(20)+Gf(20) */
#define ACK_MSG_LEN    40   /* TIDd_new(20)+Ack(20) */
#define DATA_MSG_LEN   36   /* TIDd_new(20)+enc_data(16) */

/* --------------------------------------------------------------------------
 * Shared key for secure channel with RA
 * -------------------------------------------------------------------------- */
static const uint8_t K_RA_D[16] = {
    0x67,0x61,0x74,0x73,0x20,0x6D,0x79,0x20,
    0x4B,0x75,0x6F,0x67,0x20,0x46,0x75,0x00
};

/* --------------------------------------------------------------------------
 * Device state
 * -------------------------------------------------------------------------- */
static uint8_t IDd;               /* node_id */
static uint8_t r2[RAND_LEN];     /* registration random */
static uint8_t Ad[HASH_LEN];     /* H(IDd || r2) */

/* Received from RA during registration */
static uint8_t TIDd[HASH_LEN];
static uint8_t TIDf[HASH_LEN];
static uint8_t Af[HASH_LEN];
static uint8_t Bk[HASH_LEN];

/* Authentication session state */
static uint8_t rd[RAND_LEN];     /* random for current auth */
static uint8_t stored_rf[RAND_LEN]; /* rf recovered from AuthRep */
static uint8_t SK[HASH_LEN];     /* session key */
static uint8_t TIDd_new[HASH_LEN]; /* TIDd XOR rd */
static uint8_t auth_ok = 0;      /* 1 if auth verified successfully */

/* State machine flags */
static uint8_t reg   = 0;
static uint8_t count = 0;

/* --------------------------------------------------------------------------
 * Energest — identical variable naming to base scheme
 * -------------------------------------------------------------------------- */
#define CURRENT_CPU    1.8e-3
#define CURRENT_LPM    0.0545e-3
#define CURRENT_TX     17.4e-3
#define CURRENT_RX     18.8e-3
#define SUPPLY_VOLTAGE 3.0

double cpu_reg_snap, energy_reg_snap;
double cpu_auth_snap, energy_auth_snap;

/* Enrollment energy measurement */
double cpu_enroll_before, energy_enroll_before;
double cpu_enroll_after, energy_enroll_after;static uint8_t enroll_pending = 0;  /* deferred ENROLL_ENERGY print flag */
static uint8_t keyex_pending = 0;  /* deferred KEYEX_ENERGY print flag */
static uint8_t auth_pending = 0;   /* deferred AUTH_ENERGY print flag */
/* Key-exchange energy measurement */
double cpu_keyex_before, energy_keyex_before;
double cpu_keyex_after, energy_keyex_after;

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
 * Utility functions
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
 * Endpoints
 * -------------------------------------------------------------------------- */
static coap_endpoint_t ep_as, ep_gw;
static coap_message_t  request[1];

static void discover_endpoints(void)
{
    uip_ipaddr_t a;
    /* Registration -> GW (node 1, Registration Authority) */
    uint8_t ra_id = (uint8_t)GW_NODE_ID;
    uip_ip6addr_u8(&a, 0xfd,0,0,0,0,0,0,0,
                   0x02,ra_id,0,ra_id,0,ra_id,0,ra_id);
    uip_ipaddr_copy(&ep_as.ipaddr, &a);
    ep_as.port = UIP_HTONS(COAP_DEFAULT_PORT);

    /* Auth/data -> assigned fog server (fixed IP based on node_id) */
    uint8_t fog_id = (node_id < FOG_SPLIT_ID) ?
                     (uint8_t)FOG1_NODE_ID : (uint8_t)FOG2_NODE_ID;
    uip_ip6addr_u8(&a, 0xfd,0,0,0,0,0,0,0,
                   0x02,fog_id,0,fog_id,0,fog_id,0,fog_id);
    uip_ipaddr_copy(&ep_gw.ipaddr, &a);
    ep_gw.port = UIP_HTONS(COAP_DEFAULT_PORT);
}

/* ==========================================================================
 * CoAP response handlers
 * ========================================================================== */

/* Registration reply from RA */
static void client_reg_handler(coap_message_t *resp)
{
    const uint8_t *chunk;
    if (!resp || coap_get_payload(resp, &chunk) < REG_REP_LEN) {
        printf("Node %u: Reg dropped\n", IDd);
        return;
    }

    uint8_t plain[REG_REP_LEN];
    memcpy(plain, chunk, REG_REP_LEN);
    aes_dec(K_RA_D, plain, 5);

    memcpy(TIDd, plain, HASH_LEN);
    memcpy(TIDf, plain + HASH_LEN, HASH_LEN);
    memcpy(Af,   plain + 2 * HASH_LEN, HASH_LEN);
    memcpy(Bk,   plain + 3 * HASH_LEN, HASH_LEN);

    printf("Node %u: Registered. TIDd=%02x%02x%02x TIDf=%02x%02x%02x\n",
           IDd, TIDd[0], TIDd[1], TIDd[2], TIDf[0], TIDf[1], TIDf[2]);
}

/* AuthRep from fog server (GW) — LAAKA Steps 6-7 */
static void client_auth_handler(coap_message_t *resp)
{
    const uint8_t *chunk;
    if (!resp || coap_get_payload(resp, &chunk) < AUTH_REP_LEN) {
        printf("Node %u: Auth reply dropped\n", IDd);
        auth_ok = 0;
        return;
    }

    /* Parse: TIDf(20)+Tf(1)+Ts(1)+Cf(20)+Ef(20)+Gf(20) = 82 B */
    uint8_t recv_TIDf[HASH_LEN];
    memcpy(recv_TIDf, chunk, HASH_LEN);
    uint8_t Tf = chunk[HASH_LEN];
    uint8_t Ts = chunk[HASH_LEN + 1];
    uint8_t recv_Cf[HASH_LEN], recv_Ef[HASH_LEN], recv_Gf[HASH_LEN];
    memcpy(recv_Cf, chunk + HASH_LEN + 2, HASH_LEN);
    memcpy(recv_Ef, chunk + 2 * HASH_LEN + 2, HASH_LEN);
    memcpy(recv_Gf, chunk + 3 * HASH_LEN + 2, HASH_LEN);

    /* Step 6: Verify TIDf matches stored value */
    if (memcmp(recv_TIDf, TIDf, HASH_LEN) != 0) {
        printf("Node %u: Auth failed — TIDf mismatch\n", IDd);
        auth_ok = 0;
        return;
    }

    /* Step 7: Compute TIDd_new = TIDd XOR rd */
    for (int i = 0; i < HASH_LEN; i++)
        TIDd_new[i] = TIDd[i] ^ rd[i];

    /* Extract rf*: rf* = Ef XOR h(TIDd_new) */
    uint8_t h_tid_new[HASH_LEN];
    H(TIDd_new, HASH_LEN, h_tid_new);
    uint8_t rf[RAND_LEN];
    for (int i = 0; i < RAND_LEN; i++)
        rf[i] = recv_Ef[i] ^ h_tid_new[i];

    /* Verify Cf*: Cf* = h(Tf || rf*) */
    uint8_t cf_in[1 + RAND_LEN];
    cf_in[0] = Tf;
    memcpy(cf_in + 1, rf, RAND_LEN);
    uint8_t Cf_star[HASH_LEN];
    H(cf_in, 1 + RAND_LEN, Cf_star);

    if (memcmp(Cf_star, recv_Cf, HASH_LEN) != 0) {
        printf("Node %u: Auth failed — Cf mismatch\n", IDd);
        auth_ok = 0;
        return;
    }

    /* Compute SK* = h(rd || rf* || Ts) */
    uint8_t sk_in[RAND_LEN + RAND_LEN + 1];
    memcpy(sk_in, rd, RAND_LEN);
    memcpy(sk_in + RAND_LEN, rf, RAND_LEN);
    sk_in[2 * RAND_LEN] = Ts;
    H(sk_in, 2 * RAND_LEN + 1, SK);

    /* Compute TIDf_new* = TIDf XOR rf* */
    uint8_t TIDf_new[HASH_LEN];
    for (int i = 0; i < HASH_LEN; i++)
        TIDf_new[i] = TIDf[i] ^ rf[i];

    /* Verify Gf*: Gf* = h(TIDf_new* || Bk || rf* || SK* || Ts)
     * Input: 20 + 20 + 20 + 20 + 1 = 81 bytes */
    uint8_t gf_in[3 * HASH_LEN + RAND_LEN + 1];
    memcpy(gf_in, TIDf_new, HASH_LEN);
    memcpy(gf_in + HASH_LEN, Bk, HASH_LEN);
    memcpy(gf_in + 2 * HASH_LEN, rf, RAND_LEN);
    memcpy(gf_in + 2 * HASH_LEN + RAND_LEN, SK, HASH_LEN);
    gf_in[3 * HASH_LEN + RAND_LEN] = Ts;
    uint8_t Gf_star[HASH_LEN];
    H(gf_in, 3 * HASH_LEN + RAND_LEN + 1, Gf_star);

    if (memcmp(Gf_star, recv_Gf, HASH_LEN) != 0) {
        printf("Node %u: Auth failed — Gf mismatch\n", IDd);
        auth_ok = 0;
        return;
    }

    /* Store rf for Ack computation */
    memcpy(stored_rf, rf, RAND_LEN);
    auth_ok = 1;

    printf("Node %u: Auth OK. SK=%02x%02x%02x\n", IDd, SK[0], SK[1], SK[2]);
}

/* Ack response from GW */
static void client_ack_handler(coap_message_t *resp)
{
    if (!resp) {
        printf("Node %u: Ack delivery failed\n", IDd);
        return;
    }
    printf("Node %u: Ack confirmed — mutual auth complete\n", IDd);
}

/* Data response from GW */
static void client_data_handler(coap_message_t *resp)
{
    if (!resp) {
        printf("Node %u: Data ACK missing\n", IDd);
        return;
    }
    printf("Node %u: Data confirmed\n", IDd);
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

    IDd = (uint8_t)node_id;

    /* Generate r2 and compute Ad = H(IDd || r2) */
    gen_random(r2, RAND_LEN);
    {
        uint8_t ad_in[1 + RAND_LEN];
        ad_in[0] = IDd;
        memcpy(ad_in + 1, r2, RAND_LEN);
        H(ad_in, 1 + RAND_LEN, Ad);
    }

    discover_endpoints();

    /* Staggered start — identical to base scheme */
    etimer_set(&et, CLOCK_SECOND * (5 + node_id));

    while (1) {
        PROCESS_YIELD();

        if (etimer_expired(&et)) {

            /* Deferred energy metric prints */
            if (enroll_pending) {
                printf("ENROLL_ENERGY|%u|cpu_s=%f|energy_j=%f\n",
                       IDd,
                       cpu_enroll_after - cpu_enroll_before,
                       energy_enroll_after - energy_enroll_before);
                enroll_pending = 0;
            }
            if (keyex_pending) {
                printf("KEYEX_ENERGY|%u|cpu_s=%f|energy_j=%f\n",
                       IDd,
                       cpu_keyex_after - cpu_keyex_before,
                       energy_keyex_after - energy_keyex_before);
                keyex_pending = 0;
            }
            if (auth_pending) {
                printf("AUTH_ENERGY|%u|cpu_ticks=0|energy_ticks=0|cpu_s=%f|energy_j=%f\n",
                       IDd,
                       cpu_auth_snap - cpu_reg_snap,
                       energy_auth_snap - energy_reg_snap);
                auth_pending = 0;
            }

            /* ============================================================
             * REGISTRATION — reg == 0
             * Send Ad to RA, receive (TIDd, TIDf, Af, Bk)
             * ============================================================ */
            if (reg == 0) {
                /* === ENROLL BEFORE snapshot === */
                print_energest_stats(&cpu_enroll_before, &energy_enroll_before);

                uint8_t req_payload[REG_REQ_LEN];
                memset(req_payload, 0, REG_REQ_LEN);
                req_payload[0] = IDd;
                memcpy(req_payload + 1, Ad, HASH_LEN);
                aes_enc(K_RA_D, req_payload, 2);

                coap_init_message(request, COAP_TYPE_CON, COAP_POST, 0);
                coap_set_header_uri_path(request, "test/reg");
                coap_set_payload(request, req_payload, REG_REQ_LEN);
                printf("Node %u: Sending registration to RA\n", IDd);
                COAP_BLOCKING_REQUEST(&ep_as, request, client_reg_handler);

                /* === ENROLL AFTER snapshot === */
                print_energest_stats(&cpu_enroll_after, &energy_enroll_after);
                enroll_pending = 1;

                reg = 1;

            /* ============================================================
             * AUTH + ACK + DATA — reg == 1, count < 1
             *
             * LAAKA Steps 1 → 8, plus data transmission.
             *
             * BEFORE snapshot taken at start of block.
             * AFTER  snapshot taken after data confirmed.
             * Reported: (cpu_auth - cpu_reg) and (energy_auth - energy_reg)
             * ============================================================ */
            } else if (count < 1) {

                /* === BEFORE snapshot === */
                print_energest_stats(&cpu_reg_snap, &energy_reg_snap);

                auth_ok = 0;

                /* Step 1: Generate rd, Td, compute AuthReq components */
                gen_random(rd, RAND_LEN);
                uint8_t Td = (uint8_t)(clock_time() / CLOCK_SECOND);

                /* Cd = h(Td || rd) */
                uint8_t cd_in[1 + RAND_LEN];
                cd_in[0] = Td;
                memcpy(cd_in + 1, rd, RAND_LEN);
                uint8_t Cd[HASH_LEN];
                H(cd_in, 1 + RAND_LEN, Cd);

                /* Ed = rd XOR h(Bk || Af) */
                uint8_t bk_af[2 * HASH_LEN];
                memcpy(bk_af, Bk, HASH_LEN);
                memcpy(bk_af + HASH_LEN, Af, HASH_LEN);
                uint8_t h_bk_af[HASH_LEN];
                H(bk_af, 2 * HASH_LEN, h_bk_af);
                uint8_t Ed[HASH_LEN];
                for (int i = 0; i < HASH_LEN; i++)
                    Ed[i] = rd[i] ^ h_bk_af[i];

                /* TIDd_new = TIDd XOR rd (used internally, not sent) */
                uint8_t tmp_tid_new[HASH_LEN];
                for (int i = 0; i < HASH_LEN; i++)
                    tmp_tid_new[i] = TIDd[i] ^ rd[i];

                /* Gd = h(Ad || TIDd_new || Bk || rd) */
                uint8_t gd_in[4 * HASH_LEN];
                memcpy(gd_in, Ad, HASH_LEN);
                memcpy(gd_in + HASH_LEN, tmp_tid_new, HASH_LEN);
                memcpy(gd_in + 2 * HASH_LEN, Bk, HASH_LEN);
                memcpy(gd_in + 3 * HASH_LEN, rd, RAND_LEN);
                uint8_t Gd[HASH_LEN];
                H(gd_in, 4 * HASH_LEN, Gd);

                /* Build AuthReq: TIDd(20)+Td(1)+Cd(20)+Ed(20)+Gd(20) = 81 */
                uint8_t auth_req[AUTH_REQ_LEN];
                memcpy(auth_req, TIDd, HASH_LEN);
                auth_req[HASH_LEN] = Td;
                memcpy(auth_req + HASH_LEN + 1, Cd, HASH_LEN);
                memcpy(auth_req + 2 * HASH_LEN + 1, Ed, HASH_LEN);
                memcpy(auth_req + 3 * HASH_LEN + 1, Gd, HASH_LEN);

                coap_init_message(request, COAP_TYPE_CON, COAP_POST, 1);
                coap_set_header_uri_path(request, "test/auth");
                coap_set_payload(request, auth_req, AUTH_REQ_LEN);
                printf("Node %u: Sending AuthReq to fog server\n", IDd);
                /* === KEYEX BEFORE snapshot (auth+ack = key exchange) === */
                print_energest_stats(&cpu_keyex_before, &energy_keyex_before);

                COAP_BLOCKING_REQUEST(&ep_gw, request, client_auth_handler);

                if (auth_ok) {
                    /* Step 8: Send Ack = h(rf* || Bk || SK*)
                     * Message: TIDd_new(20) + Ack(20) = 40 B */
                    uint8_t ack_in[RAND_LEN + 2 * HASH_LEN];
                    memcpy(ack_in, stored_rf, RAND_LEN);
                    memcpy(ack_in + RAND_LEN, Bk, HASH_LEN);
                    memcpy(ack_in + RAND_LEN + HASH_LEN, SK, HASH_LEN);
                    uint8_t ack_val[HASH_LEN];
                    H(ack_in, RAND_LEN + 2 * HASH_LEN, ack_val);

                    uint8_t ack_msg[ACK_MSG_LEN];
                    memcpy(ack_msg, TIDd_new, HASH_LEN);
                    memcpy(ack_msg + HASH_LEN, ack_val, HASH_LEN);

                    coap_init_message(request, COAP_TYPE_CON, COAP_POST, 2);
                    coap_set_header_uri_path(request, "test/ack");
                    coap_set_payload(request, ack_msg, ACK_MSG_LEN);
                    printf("Node %u: Sending Ack\n", IDd);
                    COAP_BLOCKING_REQUEST(&ep_gw, request, client_ack_handler);

                    /* === KEYEX AFTER snapshot === */
                    print_energest_stats(&cpu_keyex_after, &energy_keyex_after);
                    keyex_pending = 1;

                    /* Data transmission: TIDd_new(20) + enc_data(16) = 36 B */
                    uint8_t data_pkt[DATA_MSG_LEN];
                    memcpy(data_pkt, TIDd_new, HASH_LEN);

                    uint8_t sensor_data[16];
                    memset(sensor_data, 0, 16);
                    sensor_data[0] = IDd;
                    sensor_data[1] = (uint8_t)(clock_time() & 0xFF);

                    struct AES_ctx actx;
                    AES_init_ctx(&actx, SK); /* first 16 bytes of SK */
                    AES_ECB_encrypt(&actx, sensor_data);
                    memcpy(data_pkt + HASH_LEN, sensor_data, 16);

                    coap_init_message(request, COAP_TYPE_CON, COAP_POST, 3);
                    coap_set_header_uri_path(request, "test/data");
                    coap_set_payload(request, data_pkt, DATA_MSG_LEN);
                    printf("Node %u: Sending encrypted data\n", IDd);
                    COAP_BLOCKING_REQUEST(&ep_gw, request, client_data_handler);

                    count++;

                    /* === AFTER snapshot === */
                    print_energest_stats(&cpu_auth_snap, &energy_auth_snap);
                    auth_pending = 1;
                }

            /* ============================================================
             * DATA LOOP — count >= 1
             * ============================================================ */
            } else {
                uint8_t data_pkt[DATA_MSG_LEN];
                memcpy(data_pkt, TIDd_new, HASH_LEN);

                uint8_t sensor_data[16];
                memset(sensor_data, 0, 16);
                sensor_data[0] = IDd;
                sensor_data[1] = (uint8_t)(clock_time() & 0xFF);

                struct AES_ctx actx;
                AES_init_ctx(&actx, SK);
                AES_ECB_encrypt(&actx, sensor_data);
                memcpy(data_pkt + HASH_LEN, sensor_data, 16);

                coap_init_message(request, COAP_TYPE_CON, COAP_POST, 3);
                coap_set_header_uri_path(request, "test/data");
                coap_set_payload(request, data_pkt, DATA_MSG_LEN);
                COAP_BLOCKING_REQUEST(&ep_gw, request, client_data_handler);
            }

            etimer_reset(&et);
        }
    }

    PROCESS_END();
}
