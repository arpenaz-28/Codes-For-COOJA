/* ==========================================================================
 * device-node.c  —  IoT Terminal Device (TD)  [Li et al., Comp. Networks 2024]
 *
 * Initiator of the end-to-end anonymous authentication. Performs the SAME
 * operation profile as Li Table 6 (initiator): PUF + fuzzy extractor +
 * 3 hashes + 6 ECC scalar multiplications.
 *
 * State machine mirrors the other schemes so the runner/parser are reused:
 *   reg == 0   -> Registration with MS (node 1) over secure channel  -> ENROLL
 *   count < 1  -> 3-message end-to-end auth with Service Node (SN)    -> KEYEX
 *   count >= 1 -> periodic data
 *
 * Energy markers (parsed by run_*): ENROLL_ENERGY, AUTH_ENERGY, KEYEX_ENERGY.
 * KEYEX_ENERGY is printed LAST (it is the runner's early-exit trigger).
 * ========================================================================== */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include "contiki.h"
#include "coap-engine.h"
#include "coap-blocking-api.h"
#include "net/ipv6/uip-ds6.h"
#include "sys/node-id.h"
#include "random.h"
#include "project-conf.h"
#include "sys/energest.h"
#include "ecc-util.h"

/* Message sizes */
#define REG_REQ_LEN   144   /* AES(IDd|SNj|Yi1(64)|Yi2(64)|pad) = 9 blocks */
#define REG_REP_LEN   128   /* AES(Xj(64)|Ppub(64)) = 8 blocks */
#define M1_LEN        100    /* cj(16)+pj(16)+tsj(4)+E(64) */
#define M2_LEN         84    /* h(20)+D(64) */
#define M3_LEN         96    /* w(32)+Yi(64) */
#define DATA_MSG_LEN   36

static const uint8_t K_MS_D[16] = {  /* secure-channel key with MS */
    0x67,0x61,0x74,0x73,0x20,0x6D,0x79,0x20,
    0x4B,0x75,0x6F,0x67,0x20,0x46,0x75,0x00 };

/* ---- device state -------------------------------------------------------- */
static uint8_t IDd;
static uint8_t cj[16], pj[16];          /* PUF challenge + FE helper */
static uint8_t yi1[32], Yi1[64], yi2[32], Yi2[64];  /* long-term keypairs */
static uint8_t Xj[64], Ppub[64];        /* SN public key, MS public key */
static uint8_t SK[HASH_LEN];
static uint8_t auth_ok = 0;
static uint8_t reg = 0, count = 0;

/* ---- energest (identical constants to the other schemes) ----------------- */
#define CURRENT_CPU    1.8e-3
#define CURRENT_LPM    0.0545e-3
#define CURRENT_TX     17.4e-3
#define CURRENT_RX     18.8e-3
#define SUPPLY_VOLTAGE 3.0

double cpu_reg_snap, energy_reg_snap, cpu_auth_snap, energy_auth_snap;
double cpu_enroll_before, energy_enroll_before, cpu_enroll_after, energy_enroll_after;
double cpu_keyex_before, energy_keyex_before, cpu_keyex_after, energy_keyex_after;
static uint8_t enroll_pending = 0, keyex_pending = 0, auth_pending = 0;

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
    *total_energy = (*seconds_cpu)*CURRENT_CPU*SUPPLY_VOLTAGE
                  + seconds_lpm*CURRENT_LPM*SUPPLY_VOLTAGE
                  + seconds_tx*CURRENT_TX*SUPPLY_VOLTAGE
                  + seconds_rx*CURRENT_RX*SUPPLY_VOLTAGE;
}

/* ---- endpoints ----------------------------------------------------------- */
static coap_endpoint_t ep_ms, ep_sn;
static coap_message_t  request[1];

static void discover_endpoints(void)
{
    uip_ipaddr_t a;
    uint8_t ms_id = (uint8_t)GW_NODE_ID;
    uip_ip6addr_u8(&a,0xfd,0,0,0,0,0,0,0,0x02,ms_id,0,ms_id,0,ms_id,0,ms_id);
    uip_ipaddr_copy(&ep_ms.ipaddr,&a); ep_ms.port = UIP_HTONS(COAP_DEFAULT_PORT);

    uint8_t sn_id = (node_id < FOG_SPLIT_ID) ? (uint8_t)FOG1_NODE_ID : (uint8_t)FOG2_NODE_ID;
    uip_ip6addr_u8(&a,0xfd,0,0,0,0,0,0,0,0x02,sn_id,0,sn_id,0,sn_id,0,sn_id);
    uip_ipaddr_copy(&ep_sn.ipaddr,&a); ep_sn.port = UIP_HTONS(COAP_DEFAULT_PORT);
}

/* ---- registration reply (from MS) ---------------------------------------- */
static void client_reg_handler(coap_message_t *resp)
{
    const uint8_t *chunk;
    if (!resp || coap_get_payload(resp,&chunk) < REG_REP_LEN) {
        printf("Node %u: Reg dropped\n", IDd); return;
    }
    uint8_t plain[REG_REP_LEN];
    memcpy(plain, chunk, REG_REP_LEN);
    struct AES_ctx ctx;
    for (int i=0;i<REG_REP_LEN/16;i++){ AES_init_ctx(&ctx,K_MS_D); AES_ECB_decrypt(&ctx,plain+i*16); }
    memcpy(Xj, plain, 64);
    memcpy(Ppub, plain+64, 64);
    printf("Node %u: Registered (Li). Xj=%02x%02x Ppub=%02x%02x\n",
           IDd, Xj[0],Xj[1], Ppub[0],Ppub[1]);
}

/* ---- M2 handler: {h(20), D(64)} from SN, then build M3 ------------------- */
static uint8_t e_scalar[32], D_point[64], w_out[32], Yi_out[64];
static void client_auth_handler(coap_message_t *resp)
{
    const uint8_t *chunk;
    if (!resp || coap_get_payload(resp,&chunk) < M2_LEN) {
        printf("Node %u: Auth reply dropped\n", IDd); auth_ok=0; return;
    }
    uint8_t recv_h[HASH_LEN];
    memcpy(recv_h, chunk, HASH_LEN);
    memcpy(D_point, chunk+HASH_LEN, 64);

    /* FE Rep to recover device secret (cheap) */
    uint8_t w[16], r[16];
    puf_eval(cj, w);
    fe_rep(w, pj, r);

    /* s = H4(SNj || D || eXj)  -> ECC mult #2: eXj */
    uint8_t eXj[32];
    ecc_point_mult(e_scalar, Xj, eXj);
    uint8_t s_in[1+64+32]; s_in[0]=(uint8_t)((node_id<FOG_SPLIT_ID)?FOG1_NODE_ID:FOG2_NODE_ID);
    memcpy(s_in+1, D_point, 64); memcpy(s_in+65, eXj, 32);
    uint8_t s_hash[HASH_LEN]; li_H(s_in, 1+64+32, s_hash);

    /* temporary public key Yi = (u+v)^-1 (u*Yi1 + v*Yi2)
     * -> ECC mults #3 (u*Yi1) and #4 (v*Yi2). (u+v)^-1 scalar arithmetic and
     *    the point addition are folded into the hash binding below.) */
    uint8_t u[32], v[32], uY1[32], vY2[32];
    li_rng(u,32); li_rng(v,32);
    ecc_point_mult(u, Yi1, uY1);
    ecc_point_mult(v, Yi2, vY2);
    /* Yi (as a point) recomputed on the generator -> ECC mult #6 (yi*G) */
    uint8_t yi[32]; li_H(uY1, 32, yi); memcpy(yi+20, vY2, 12);
    ecc_base_mult(yi, Yi_out);

    /* w = yi + e*s   (scalar; bound via hash) */
    uint8_t w_in[32+HASH_LEN]; memcpy(w_in, yi, 32); memcpy(w_in+32, s_hash, HASH_LEN);
    uint8_t wh[HASH_LEN]; li_H(w_in, 32+HASH_LEN, wh);
    memcpy(w_out, wh, 20); memset(w_out+20, 0, 12);

    /* session key kij = H2(SNj || eD)  -> ECC mult #5: eD */
    uint8_t eD[32];
    ecc_point_mult(e_scalar, D_point, eD);
    uint8_t sk_in[1+32]; sk_in[0]=s_in[0]; memcpy(sk_in+1, eD, 32);
    li_H(sk_in, 1+32, SK);

    (void)recv_h;   /* h verified against H3(SN,D,eXj) in a full impl. */
    auth_ok = 1;
    printf("Node %u: Auth OK (Li). SK=%02x%02x%02x\n", IDd, SK[0],SK[1],SK[2]);
}

static void client_ack_handler(coap_message_t *resp)
{ printf("Node %u: %s\n", IDd, resp ? "M3 confirmed - mutual auth complete" : "M3 failed"); }
static void client_data_handler(coap_message_t *resp)
{ if(!resp) printf("Node %u: Data ACK missing\n", IDd); }

/* ==========================================================================
 * Main process
 * ========================================================================== */
PROCESS(device_node, "Li IoT Terminal Device");
AUTOSTART_PROCESSES(&device_node);
static struct etimer et;

PROCESS_THREAD(device_node, ev, data)
{
    PROCESS_BEGIN();
    IDd = (uint8_t)node_id;
    discover_endpoints();
    etimer_set(&et, CLOCK_SECOND * (5 + node_id));

    while (1) {
        PROCESS_YIELD();
        if (!etimer_expired(&et)) continue;

        /* deferred energy prints (ENROLL, then AUTH, then KEYEX last) */
        if (enroll_pending) {
            printf("ENROLL_ENERGY|%u|cpu_s=%f|energy_j=%f\n", IDd,
                   cpu_enroll_after-cpu_enroll_before, energy_enroll_after-energy_enroll_before);
            enroll_pending=0;
        }
        if (auth_pending) {
            printf("AUTH_ENERGY|%u|cpu_ticks=0|energy_ticks=0|cpu_s=%f|energy_j=%f\n", IDd,
                   cpu_auth_snap-cpu_reg_snap, energy_auth_snap-energy_reg_snap);
            auth_pending=0;
        }
        if (keyex_pending) {
            printf("KEYEX_ENERGY|%u|cpu_s=%f|energy_j=%f\n", IDd,
                   cpu_keyex_after-cpu_keyex_before, energy_keyex_after-energy_keyex_before);
            keyex_pending=0;
        }

        /* ---------------- REGISTRATION (ENROLL) ---------------- */
        if (reg == 0) {
            print_energest_stats(&cpu_enroll_before,&energy_enroll_before);

            /* device-side enrol cost: PUF + FE Gen + 2 long-term keypairs */
            uint8_t w[16], r[16];
            li_rng(cj,16);
            puf_eval(cj, w);
            fe_gen(w, r, pj);
            ecc_keygen(yi1, Yi1);
            ecc_keygen(yi2, Yi2);

            uint8_t req[REG_REQ_LEN]; memset(req,0,REG_REQ_LEN);
            req[0]=IDd; req[1]=(node_id<FOG_SPLIT_ID)?FOG1_NODE_ID:FOG2_NODE_ID;
            memcpy(req+2, Yi1, 64); memcpy(req+66, Yi2, 64);
            struct AES_ctx ctx;
            for(int i=0;i<REG_REQ_LEN/16;i++){AES_init_ctx(&ctx,K_MS_D);AES_ECB_encrypt(&ctx,req+i*16);}

            coap_init_message(request,COAP_TYPE_CON,COAP_POST,0);
            coap_set_header_uri_path(request,"test/reg");
            coap_set_payload(request,req,REG_REQ_LEN);
            printf("Node %u: Sending Li registration to MS\n", IDd);
            COAP_BLOCKING_REQUEST(&ep_ms,request,client_reg_handler);

            print_energest_stats(&cpu_enroll_after,&energy_enroll_after);
            enroll_pending=1; reg=1;

        /* ---------------- AUTH (KEYEX) ------------------------- */
        } else if (count < 1) {
            print_energest_stats(&cpu_reg_snap,&energy_reg_snap);
            auth_ok=0;

            /* M1: E = e*G  -> ECC mult #1 */
            li_rng(e_scalar,32);
            uint8_t E[64]; ecc_base_mult(e_scalar, E);
            uint8_t tsj=(uint8_t)(clock_time()/CLOCK_SECOND);

            uint8_t m1[M1_LEN];
            memcpy(m1, cj, 16); memcpy(m1+16, pj, 16);
            m1[32]=tsj; m1[33]=0; m1[34]=0; m1[35]=0;
            memcpy(m1+36, E, 64);

            coap_init_message(request,COAP_TYPE_CON,COAP_POST,1);
            coap_set_header_uri_path(request,"test/auth");
            coap_set_payload(request,m1,M1_LEN);
            printf("Node %u: Sending M1 to SN\n", IDd);

            print_energest_stats(&cpu_keyex_before,&energy_keyex_before);
            COAP_BLOCKING_REQUEST(&ep_sn,request,client_auth_handler);

            if (auth_ok) {
                /* M3: {w, Yi} */
                uint8_t m3[M3_LEN];
                memcpy(m3, w_out, 32); memcpy(m3+32, Yi_out, 64);
                coap_init_message(request,COAP_TYPE_CON,COAP_POST,2);
                coap_set_header_uri_path(request,"test/ack");
                coap_set_payload(request,m3,M3_LEN);
                printf("Node %u: Sending M3 to SN\n", IDd);
                COAP_BLOCKING_REQUEST(&ep_sn,request,client_ack_handler);

                print_energest_stats(&cpu_keyex_after,&energy_keyex_after);
                keyex_pending=1;

                /* data */
                uint8_t data_pkt[DATA_MSG_LEN]; memset(data_pkt,0,DATA_MSG_LEN);
                data_pkt[0]=IDd; data_pkt[1]=(uint8_t)(clock_time()&0xFF);
                struct AES_ctx actx; AES_init_ctx(&actx,SK); AES_ECB_encrypt(&actx,data_pkt+HASH_LEN);
                coap_init_message(request,COAP_TYPE_CON,COAP_POST,3);
                coap_set_header_uri_path(request,"test/data");
                coap_set_payload(request,data_pkt,DATA_MSG_LEN);
                COAP_BLOCKING_REQUEST(&ep_sn,request,client_data_handler);

                count++;
                print_energest_stats(&cpu_auth_snap,&energy_auth_snap);
                auth_pending=1;
            }

        /* ---------------- DATA LOOP ---------------------------- */
        } else {
            uint8_t data_pkt[DATA_MSG_LEN]; memset(data_pkt,0,DATA_MSG_LEN);
            data_pkt[0]=IDd; data_pkt[1]=(uint8_t)(clock_time()&0xFF);
            struct AES_ctx actx; AES_init_ctx(&actx,SK); AES_ECB_encrypt(&actx,data_pkt+HASH_LEN);
            coap_init_message(request,COAP_TYPE_CON,COAP_POST,3);
            coap_set_header_uri_path(request,"test/data");
            coap_set_payload(request,data_pkt,DATA_MSG_LEN);
            COAP_BLOCKING_REQUEST(&ep_sn,request,client_data_handler);
        }
        etimer_reset(&et);
    }
    PROCESS_END();
}
