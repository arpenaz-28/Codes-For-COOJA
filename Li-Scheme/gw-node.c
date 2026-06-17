/* ==========================================================================
 * gw-node.c  —  Management Server (MS) + RPL root  [Li et al., 2024]
 *
 * Node 1. Handles device registration over the secure channel: receives the
 * device long-term public keys, returns the target Service Node public key Xj
 * (derived deterministically, identical to as-node) and the MS public key Ppub.
 *
 *   POST test/reg
 *     Recv : AES(K_MS_D, [IDd|SNj|Yi1(64)|Yi2(64)|pad]) = 144 B
 *     Reply: AES(K_MS_D, [Xj(64)|Ppub(64)])             = 128 B
 * ========================================================================== */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include "contiki.h"
#include "coap-engine.h"
#include "net/routing/routing.h"
#include "net/netstack.h"
#include "net/ipv6/uip-ds6.h"
#include "sys/node-id.h"
#include "random.h"
#include "project-conf.h"
#include "ecc-util.h"

#define REG_REQ_LEN 144
#define REG_REP_LEN 128
#define MAX_CLIENTS 130

static const uint8_t K_MS_D[16] = {
    0x67,0x61,0x74,0x73,0x20,0x6D,0x79,0x20,
    0x4B,0x75,0x6F,0x67,0x20,0x46,0x75,0x00 };

static uint8_t kM[32], Ppub[64];   /* MS keypair */

/* derive the deterministic Xj for a given SN node id (matches as-node) */
static void derive_sn_pub(uint8_t sn_id, uint8_t *Xj_out)
{
    uint8_t seed[8];
    seed[0]='L';seed[1]='I';seed[2]='S';seed[3]='N';
    seed[4]=sn_id;seed[5]=0x5A;seed[6]=0xA5;seed[7]=(uint8_t)(sn_id^0x3C);
    uint8_t h1[HASH_LEN],h2[HASH_LEN],xj[32];
    li_H(seed,8,h1); li_H(h1,HASH_LEN,h2);
    memcpy(xj,h1,20); memcpy(xj+20,h2,12);
    ecc_base_mult(xj, Xj_out);
}

static void res_reg_handler(coap_message_t *req, coap_message_t *resp,
                            uint8_t *buf, uint16_t ps, int32_t *off)
{
    const uint8_t *chunk;
    if (coap_get_payload(req,&chunk) != REG_REQ_LEN) return;
    uint8_t plain[REG_REQ_LEN]; memcpy(plain,chunk,REG_REQ_LEN);
    struct AES_ctx ctx;
    for(int i=0;i<REG_REQ_LEN/16;i++){AES_init_ctx(&ctx,K_MS_D);AES_ECB_decrypt(&ctx,plain+i*16);}

    uint8_t id_d=plain[0], sn_id=plain[1];
    if(id_d==0||id_d>=MAX_CLIENTS) return;

    uint8_t Xj[64]; derive_sn_pub(sn_id, Xj);

    memset(buf,0,REG_REP_LEN);
    memcpy(buf, Xj, 64);
    memcpy(buf+64, Ppub, 64);
    for(int i=0;i<REG_REP_LEN/16;i++){AES_init_ctx(&ctx,K_MS_D);AES_ECB_encrypt(&ctx,buf+i*16);}
    coap_set_payload(resp, buf, REG_REP_LEN);
    printf("MS %u: Registered device %u -> SN %u\n", node_id, id_d, sn_id);
}

RESOURCE(res_reg,"title=\"Reg\"",NULL,res_reg_handler,NULL,NULL);

PROCESS(gw_proc, "GW / Management Server");
AUTOSTART_PROCESSES(&gw_proc);

PROCESS_THREAD(gw_proc, ev, data)
{
    PROCESS_BEGIN();
    ecc_keygen(kM, Ppub);              /* MS keypair */
    NETSTACK_ROUTING.root_start();
    coap_engine_init();
    coap_activate_resource(&res_reg,"test/reg");
    printf("MS %u: started (Li management server). Ppub=%02x%02x\n",
           node_id, Ppub[0],Ppub[1]);
    while (1) { PROCESS_WAIT_EVENT(); }
    PROCESS_END();
}
