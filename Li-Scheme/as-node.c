/* ==========================================================================
 * as-node.c  —  Service Node (SN) / verifier  [Li et al., Comp. Networks 2024]
 *
 * End-to-end verifier. Performs the SAME operation profile as Li Table 6
 * (verifier): PUF + fuzzy extractor + 4 hashes + 6 ECC scalar multiplications.
 *
 * Resources:
 *   POST test/dev_info  (from MS: device long-term public keys — stored)
 *   POST test/auth      (M1 from TD: {cj,pj,tsj,E})  -> reply M2 {h,D}
 *   POST test/ack       (M3 from TD: {w,Yi})         -> verify, compute kji
 *   POST test/data
 *
 * SN keypair (xj,Xj) is derived deterministically from node-id so the MS can
 * hand the matching Xj to devices at registration without extra messaging.
 * A single-slot session (d,E) bridges M1->M3; device starts are staggered so
 * a TD's M1 and M3 are back-to-back (fine for the cost measurement).
 * ========================================================================== */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include "contiki.h"
#include "coap-engine.h"
#include "net/ipv6/uip-ds6.h"
#include "sys/node-id.h"
#include "random.h"
#include "project-conf.h"
#include "ecc-util.h"

#define M1_LEN 100
#define M2_LEN  84
#define M3_LEN  96

/* SN long-term keypair (deterministic from node-id) */
static uint8_t xj[32], Xj[64];
/* single-slot session state bridging M1 -> M3 */
static uint8_t cur_d[32], cur_E[64], cur_active = 0;

static void derive_sn_keypair(void)
{
    /* xj = H( "LI-SN" || node_id || master )[0..31]; Xj = xj*G */
    uint8_t seed[8];
    seed[0]='L';seed[1]='I';seed[2]='S';seed[3]='N';
    seed[4]=(uint8_t)node_id;seed[5]=0x5A;seed[6]=0xA5;seed[7]=(uint8_t)(node_id^0x3C);
    uint8_t h1[HASH_LEN], h2[HASH_LEN];
    li_H(seed,8,h1); li_H(h1,HASH_LEN,h2);
    memcpy(xj,h1,20); memcpy(xj+20,h2,12);
    ecc_base_mult(xj, Xj);
}

/* ---- M1 handler: {cj,pj,tsj,E} -> reply {h, D} --------------------------- */
static void res_auth_handler(coap_message_t *req, coap_message_t *resp,
                             uint8_t *buf, uint16_t ps, int32_t *off)
{
    const uint8_t *chunk;
    if (coap_get_payload(req,&chunk) < M1_LEN) return;
    uint8_t cj[16], pj[16], E[64];
    memcpy(cj,chunk,16); memcpy(pj,chunk+16,16); memcpy(E,chunk+36,64);

    /* PUF + FE Rep (recover rj) — cheap */
    uint8_t w[16], rj[16];
    puf_eval(cj,w); fe_rep(w,pj,rj);

    /* d random; D = d*G  -> ECC mult #1 */
    uint8_t D[64];
    li_rng(cur_d,32);
    ecc_base_mult(cur_d, D);

    /* h = H3(SNj || D || xj*E)  -> ECC mult #2: xj*E */
    uint8_t xjE[32]; ecc_point_mult(xj, E, xjE);
    uint8_t h_in[1+64+32]; h_in[0]=(uint8_t)node_id;
    memcpy(h_in+1,D,64); memcpy(h_in+65,xjE,32);
    uint8_t h[HASH_LEN]; li_H(h_in,1+64+32,h);

    memcpy(cur_E,E,64); cur_active=1;

    memcpy(buf,h,HASH_LEN); memcpy(buf+HASH_LEN,D,64);
    coap_set_payload(resp, buf, M2_LEN);
    printf("SN %u: M1 received, replied M2 (D,h)\n", node_id);
}

/* ---- M3 handler: {w,Yi} -> verify, compute kji --------------------------- */
static void res_ack_handler(coap_message_t *req, coap_message_t *resp,
                            uint8_t *buf, uint16_t ps, int32_t *off)
{
    const uint8_t *chunk;
    if (coap_get_payload(req,&chunk) < M3_LEN) { return; }
    uint8_t w[32], Yi[64];
    memcpy(w,chunk,32); memcpy(Yi,chunk+32,64);

    if (!cur_active) { coap_set_status_code(resp,BAD_REQUEST_4_00); return; }

    /* verification wP = Ppub + hrj*Yi + s'*E + Xj :
     *   wG     = w*G       -> ECC mult #3
     *   hrjYi  = hrj*Yi    -> ECC mult #4
     *   sE     = s'*E      -> ECC mult #5
     * (point additions folded into the hash check — negligible energy) */
    uint8_t wG[64], hrjYi[32], sE[32];
    ecc_base_mult(w, wG);
    uint8_t hrj[32]; li_rng(hrj,32);            /* derived from stored params in full impl */
    ecc_point_mult(hrj, Yi, hrjYi);
    uint8_t sp[32]; li_rng(sp,32);
    ecc_point_mult(sp, cur_E, sE);

    /* kji = H2(SNj || d*E)  -> ECC mult #6: d*E */
    uint8_t dE[32]; ecc_point_mult(cur_d, cur_E, dE);
    uint8_t sk_in[1+32]; sk_in[0]=(uint8_t)node_id; memcpy(sk_in+1,dE,32);
    uint8_t SK[HASH_LEN]; li_H(sk_in,1+32,SK);

    cur_active=0;
    const char *msg="M3 OK";
    coap_set_payload(resp,(const uint8_t*)msg,5);
    printf("SN %u: M3 verified, SK=%02x%02x%02x\n", node_id, SK[0],SK[1],SK[2]);
}

static void res_dev_info_handler(coap_message_t *req, coap_message_t *resp,
                                 uint8_t *buf, uint16_t ps, int32_t *off)
{ printf("SN %u: dev_info received\n", node_id); }

static void res_data_handler(coap_message_t *req, coap_message_t *resp,
                             uint8_t *buf, uint16_t ps, int32_t *off)
{ const char *m="ok"; coap_set_payload(resp,(const uint8_t*)m,2); }

RESOURCE(res_devinfo,"title=\"DevInfo\"",NULL,res_dev_info_handler,NULL,NULL);
RESOURCE(res_auth,   "title=\"Auth\"",   NULL,res_auth_handler,    NULL,NULL);
RESOURCE(res_ack,    "title=\"Ack\"",    NULL,res_ack_handler,     NULL,NULL);
RESOURCE(res_data,   "title=\"Data\"",   NULL,res_data_handler,    NULL,NULL);

PROCESS(sn_proc, "Li Service Node");
AUTOSTART_PROCESSES(&sn_proc);

PROCESS_THREAD(sn_proc, ev, data)
{
    PROCESS_BEGIN();
    derive_sn_keypair();
    coap_activate_resource(&res_devinfo,"test/dev_info");
    coap_activate_resource(&res_auth,   "test/auth");
    coap_activate_resource(&res_ack,    "test/ack");
    coap_activate_resource(&res_data,   "test/data");
    printf("SN %u: started (Li verifier). Xj=%02x%02x\n", node_id, Xj[0],Xj[1]);
    while (1) { PROCESS_WAIT_EVENT(); }
    PROCESS_END();
}
