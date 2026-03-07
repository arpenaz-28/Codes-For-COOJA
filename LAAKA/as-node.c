/* ==========================================================================
 * as-node.c  —  Fog Authentication Server  (LAAKA scheme)
 *
 * Nodes 2-80: Fog authentication server.
 * Receives device credentials from RA (GW node 1) and handles
 * authentication, key agreement, and encrypted data from IoT devices.
 *
 * Resources:
 *   POST /test/dev_info — receive device credentials from RA
 *     Recv: AES(K_RA_GW, [IDd(1)|TIDd(20)|Ad(20)|Bk(20)|pad(3)]) = 64 B
 *
 *   POST /test/auth — handle AuthReq from device (LAAKA Steps 2-5)
 *     Recv:  TIDd(20)+Td(1)+Cd(20)+Ed(20)+Gd(20) = 81 B
 *     Reply: TIDf(20)+Tf(1)+Ts(1)+Cf(20)+Ef(20)+Gf(20) = 82 B
 *
 *   POST /test/ack — handle Ack from device (Step 9)
 *     Recv: TIDd_new(20)+Ack(20) = 40 B
 *
 *   POST /test/data — receive encrypted sensor data
 *     Recv: TIDd_new(20)+enc_data(16) = 36 B
 * ========================================================================== */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include "contiki.h"
#include "coap-engine.h"
#include "aes.h"
#include "sha256.h"
#include "sys/node-id.h"
#include "random.h"
#include "project-conf.h"

/* --------------------------------------------------------------------------
 * Protocol constants
 * -------------------------------------------------------------------------- */
#define HASH_LEN      20
#define RAND_LEN      20
#define DEV_INFO_LEN  64
#define AUTH_REQ_LEN  81
#define AUTH_REP_LEN  82
#define ACK_MSG_LEN   40
#define DATA_MSG_LEN  36
#define MAX_DEVICES   110

/* --------------------------------------------------------------------------
 * Key for secure channel with RA
 * -------------------------------------------------------------------------- */
static const uint8_t K_RA_GW[16] = {
    0x67,0x62,0x74,0x73,0x20,0x6D,0x79,0x20,
    0x4B,0x75,0x6F,0x67,0x20,0x46,0x75,0x00
};

/* --------------------------------------------------------------------------
 * Pre-configured fog server identity (shared across all fog nodes)
 * -------------------------------------------------------------------------- */
static const uint8_t r1_fog[HASH_LEN] = {
    0x11,0x22,0x33,0x44,0x55,0x66,0x77,0x88,
    0x99,0xAA,0xBB,0xCC,0xDD,0xEE,0xFF,0x01,
    0x02,0x03,0x04,0x05
};
static const uint8_t TIDf_const[HASH_LEN] = {
    0xA1,0xB2,0xC3,0xD4,0xE5,0xF6,0x07,0x18,
    0x29,0x3A,0x4B,0x5C,0x6D,0x7E,0x8F,0x90,
    0x01,0x12,0x23,0x34
};
static uint8_t Af[HASH_LEN];

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

static int ts_fresh(uint8_t recv_ts)
{
    uint8_t now  = (uint8_t)(clock_time() / CLOCK_SECOND);
    int     diff = ((int)now - (int)recv_ts + 256) % 256;
    return (diff < FRESHNESS_WINDOW);
}

/* --------------------------------------------------------------------------
 * Per-device state table
 * -------------------------------------------------------------------------- */
typedef struct {
    uint8_t  IDd;
    uint8_t  TIDd[HASH_LEN];
    uint8_t  Ad[HASH_LEN];
    uint8_t  Bk[HASH_LEN];
    uint8_t  rf[RAND_LEN];
    uint8_t  SK[HASH_LEN];
    uint8_t  TIDd_new[HASH_LEN];
    uint8_t  registered;
    uint8_t  authenticated;
} fog_device_t;

static fog_device_t devices[MAX_DEVICES];

static fog_device_t *find_by_tid(const uint8_t *tid)
{
    for (int i = 1; i < MAX_DEVICES; i++) {
        if (devices[i].registered &&
            memcmp(devices[i].TIDd, tid, HASH_LEN) == 0)
            return &devices[i];
    }
    return NULL;
}

static fog_device_t *find_by_tid_new(const uint8_t *tid_new)
{
    for (int i = 1; i < MAX_DEVICES; i++) {
        if (devices[i].registered &&
            memcmp(devices[i].TIDd_new, tid_new, HASH_LEN) == 0)
            return &devices[i];
    }
    return NULL;
}

/* ==========================================================================
 * Resource: POST /test/dev_info — receive device credentials from RA
 * Payload: AES(K_RA_GW, [IDd(1)|TIDd(20)|Ad(20)|Bk(20)|pad(3)]) = 64 B
 * ========================================================================== */
static void res_devinfo_handler(coap_message_t *req, coap_message_t *resp,
                                uint8_t *buf, uint16_t ps, int32_t *off)
{
    const uint8_t *chunk;
    if (coap_get_payload(req, &chunk) != DEV_INFO_LEN) return;

    uint8_t plain[DEV_INFO_LEN];
    memcpy(plain, chunk, DEV_INFO_LEN);
    aes_dec(K_RA_GW, plain, 4);

    uint8_t id_d = plain[0];
    if (id_d == 0 || id_d >= MAX_DEVICES) return;

    devices[id_d].IDd = id_d;
    memcpy(devices[id_d].TIDd, plain + 1, HASH_LEN);
    memcpy(devices[id_d].Ad, plain + 1 + HASH_LEN, HASH_LEN);
    memcpy(devices[id_d].Bk, plain + 1 + 2 * HASH_LEN, HASH_LEN);
    devices[id_d].registered    = 1;
    devices[id_d].authenticated = 0;

    printf("Fog %u: Stored credentials for device %u. TIDd=%02x%02x%02x\n",
           node_id, id_d,
           devices[id_d].TIDd[0], devices[id_d].TIDd[1], devices[id_d].TIDd[2]);

    const char *msg = "OK";
    coap_set_payload(resp, (const uint8_t *)msg, strlen(msg));
}

/* ==========================================================================
 * Resource: POST /test/auth — handle AuthReq from device
 *
 * LAAKA Steps 2-5:
 *   2. Verify TIDd, check timestamp freshness
 *   3. Extract rd* = Ed XOR h(Bk||Af), verify Cd, verify Gd
 *   4. Generate Tf, rf, Ts, compute SK = h(rd||rf||Ts)
 *   5. Compute Ef, Gf, send AuthRep
 *
 * Recv:  TIDd(20)+Td(1)+Cd(20)+Ed(20)+Gd(20) = 81 B
 * Reply: TIDf(20)+Tf(1)+Ts(1)+Cf(20)+Ef(20)+Gf(20) = 82 B
 * ========================================================================== */
static void res_auth_handler(coap_message_t *req, coap_message_t *resp,
                             uint8_t *buf, uint16_t ps, int32_t *off)
{
    const uint8_t *chunk;
    int len = coap_get_payload(req, &chunk);
    if (len < AUTH_REQ_LEN) return;

    /* Parse AuthReq */
    uint8_t recv_TIDd[HASH_LEN];
    uint8_t Td;
    uint8_t recv_Cd[HASH_LEN], recv_Ed[HASH_LEN], recv_Gd[HASH_LEN];

    memcpy(recv_TIDd, chunk, HASH_LEN);
    Td = chunk[HASH_LEN];
    memcpy(recv_Cd, chunk + HASH_LEN + 1, HASH_LEN);
    memcpy(recv_Ed, chunk + 2 * HASH_LEN + 1, HASH_LEN);
    memcpy(recv_Gd, chunk + 3 * HASH_LEN + 1, HASH_LEN);

    /* Step 2: Find device by TIDd */
    fog_device_t *dev = find_by_tid(recv_TIDd);
    if (!dev) {
        printf("Fog %u: Auth failed - TIDd not found\n", node_id);
        return;
    }

    /* Step 2: Timestamp freshness check */
    if (!ts_fresh(Td)) {
        printf("Fog %u: Auth failed - stale timestamp for device %u\n",
               node_id, dev->IDd);
        return;
    }

    /* Step 3: Extract rd* = Ed XOR h(Bk || Af) */
    uint8_t bk_af_in[2 * HASH_LEN];
    uint8_t h_bk_af[HASH_LEN];
    memcpy(bk_af_in, dev->Bk, HASH_LEN);
    memcpy(bk_af_in + HASH_LEN, Af, HASH_LEN);
    H(bk_af_in, 2 * HASH_LEN, h_bk_af);

    uint8_t rd_star[RAND_LEN];
    for (int i = 0; i < RAND_LEN; i++)
        rd_star[i] = recv_Ed[i] ^ h_bk_af[i];

    /* Step 3: Verify Cd* = h(Td || rd*) */
    uint8_t cd_in[1 + RAND_LEN];
    cd_in[0] = Td;
    memcpy(cd_in + 1, rd_star, RAND_LEN);
    uint8_t Cd_star[HASH_LEN];
    H(cd_in, 1 + RAND_LEN, Cd_star);

    if (memcmp(Cd_star, recv_Cd, HASH_LEN) != 0) {
        printf("Fog %u: Auth failed - Cd mismatch for device %u\n",
               node_id, dev->IDd);
        return;
    }

    /* Step 3: Compute TIDd_new* = TIDd XOR rd* */
    uint8_t TIDd_new_star[HASH_LEN];
    for (int i = 0; i < HASH_LEN; i++)
        TIDd_new_star[i] = recv_TIDd[i] ^ rd_star[i];

    /* Step 3: Verify Gd* = h(Ad || TIDd_new* || Bk || rd*) */
    uint8_t gd_in[4 * HASH_LEN];
    memcpy(gd_in, dev->Ad, HASH_LEN);
    memcpy(gd_in + HASH_LEN, TIDd_new_star, HASH_LEN);
    memcpy(gd_in + 2 * HASH_LEN, dev->Bk, HASH_LEN);
    memcpy(gd_in + 3 * HASH_LEN, rd_star, RAND_LEN);
    uint8_t Gd_star[HASH_LEN];
    H(gd_in, 4 * HASH_LEN, Gd_star);

    if (memcmp(Gd_star, recv_Gd, HASH_LEN) != 0) {
        printf("Fog %u: Auth failed - Gd mismatch for device %u\n",
               node_id, dev->IDd);
        return;
    }

    /* Step 4: Generate Tf, rf, Ts */
    uint8_t Tf = (uint8_t)(clock_time() / CLOCK_SECOND);
    uint8_t rf[RAND_LEN];
    gen_random(rf, RAND_LEN);
    uint8_t Ts = Tf + 1;

    /* Step 4: Compute Cf = h(Tf || rf) */
    uint8_t cf_in[1 + RAND_LEN];
    cf_in[0] = Tf;
    memcpy(cf_in + 1, rf, RAND_LEN);
    uint8_t Cf[HASH_LEN];
    H(cf_in, 1 + RAND_LEN, Cf);

    /* Step 4: Compute SK = h(rd || rf || Ts) */
    uint8_t sk_in[RAND_LEN + RAND_LEN + 1];
    memcpy(sk_in, rd_star, RAND_LEN);
    memcpy(sk_in + RAND_LEN, rf, RAND_LEN);
    sk_in[2 * RAND_LEN] = Ts;
    uint8_t SK[HASH_LEN];
    H(sk_in, 2 * RAND_LEN + 1, SK);

    /* Step 5: Compute Ef = rf XOR h(TIDd_new*) */
    uint8_t h_tid_new[HASH_LEN];
    H(TIDd_new_star, HASH_LEN, h_tid_new);
    uint8_t Ef[HASH_LEN];
    for (int i = 0; i < HASH_LEN; i++)
        Ef[i] = rf[i] ^ h_tid_new[i];

    /* Step 5: Compute TIDf_new = TIDf XOR rf */
    uint8_t TIDf_new[HASH_LEN];
    for (int i = 0; i < HASH_LEN; i++)
        TIDf_new[i] = TIDf_const[i] ^ rf[i];

    /* Step 5: Compute Gf = h(TIDf_new || Bk || rf || SK || Ts) */
    uint8_t gf_in[3 * HASH_LEN + RAND_LEN + 1];
    memcpy(gf_in, TIDf_new, HASH_LEN);
    memcpy(gf_in + HASH_LEN, dev->Bk, HASH_LEN);
    memcpy(gf_in + 2 * HASH_LEN, rf, RAND_LEN);
    memcpy(gf_in + 2 * HASH_LEN + RAND_LEN, SK, HASH_LEN);
    gf_in[3 * HASH_LEN + RAND_LEN] = Ts;
    uint8_t Gf[HASH_LEN];
    H(gf_in, 3 * HASH_LEN + RAND_LEN + 1, Gf);

    /* Store auth session state */
    memcpy(dev->rf, rf, RAND_LEN);
    memcpy(dev->SK, SK, HASH_LEN);
    memcpy(dev->TIDd_new, TIDd_new_star, HASH_LEN);

    /* Build AuthRep: TIDf(20)+Tf(1)+Ts(1)+Cf(20)+Ef(20)+Gf(20) = 82 */
    uint8_t reply[AUTH_REP_LEN];
    memcpy(reply, TIDf_const, HASH_LEN);
    reply[HASH_LEN] = Tf;
    reply[HASH_LEN + 1] = Ts;
    memcpy(reply + HASH_LEN + 2, Cf, HASH_LEN);
    memcpy(reply + 2 * HASH_LEN + 2, Ef, HASH_LEN);
    memcpy(reply + 3 * HASH_LEN + 2, Gf, HASH_LEN);
    coap_set_payload(resp, reply, AUTH_REP_LEN);

    printf("Fog %u: AuthRep sent to device %u. SK=%02x%02x%02x\n",
           node_id, dev->IDd, SK[0], SK[1], SK[2]);
}

/* ==========================================================================
 * Resource: POST /test/ack — handle Ack from device (Step 9)
 *
 * Recv: TIDd_new(20) + Ack(20) = 40 B
 * Verify: Ack == h(rf || Bk || SK)
 * ========================================================================== */
static void res_ack_handler(coap_message_t *req, coap_message_t *resp,
                            uint8_t *buf, uint16_t ps, int32_t *off)
{
    const uint8_t *chunk;
    if (coap_get_payload(req, &chunk) < ACK_MSG_LEN) return;

    uint8_t recv_tid_new[HASH_LEN];
    uint8_t recv_ack[HASH_LEN];
    memcpy(recv_tid_new, chunk, HASH_LEN);
    memcpy(recv_ack, chunk + HASH_LEN, HASH_LEN);

    fog_device_t *dev = find_by_tid_new(recv_tid_new);
    if (!dev) {
        printf("Fog %u: Ack rejected - TIDd_new not found\n", node_id);
        return;
    }

    /* Compute expected: h(rf || Bk || SK) */
    uint8_t ack_in[RAND_LEN + 2 * HASH_LEN];
    memcpy(ack_in, dev->rf, RAND_LEN);
    memcpy(ack_in + RAND_LEN, dev->Bk, HASH_LEN);
    memcpy(ack_in + RAND_LEN + HASH_LEN, dev->SK, HASH_LEN);
    uint8_t expected_ack[HASH_LEN];
    H(ack_in, RAND_LEN + 2 * HASH_LEN, expected_ack);

    if (memcmp(expected_ack, recv_ack, HASH_LEN) != 0) {
        printf("Fog %u: Ack verification failed for device %u\n",
               node_id, dev->IDd);
        return;
    }

    dev->authenticated = 1;
    printf("Fog %u: Mutual auth complete for device %u. SK established.\n",
           node_id, dev->IDd);

    const char *msg = "OK";
    coap_set_payload(resp, (const uint8_t *)msg, strlen(msg));
}

/* ==========================================================================
 * Resource: POST /test/data — receive encrypted sensor data
 *
 * Recv: TIDd_new(20) + AES_enc(SK[0:16], data(16)) = 36 B
 * ========================================================================== */
static void res_data_handler(coap_message_t *req, coap_message_t *resp,
                             uint8_t *buf, uint16_t ps, int32_t *off)
{
    const uint8_t *chunk;
    if (coap_get_payload(req, &chunk) < DATA_MSG_LEN) return;

    uint8_t recv_tid_new[HASH_LEN], enc_data[16];
    memcpy(recv_tid_new, chunk, HASH_LEN);
    memcpy(enc_data, chunk + HASH_LEN, 16);

    fog_device_t *dev = find_by_tid_new(recv_tid_new);
    if (!dev || !dev->authenticated) {
        printf("Fog %u: Data rejected - not authenticated (TIDd_new=%02x%02x%02x)\n",
               node_id, recv_tid_new[0], recv_tid_new[1], recv_tid_new[2]);
        return;
    }

    struct AES_ctx actx;
    AES_init_ctx(&actx, dev->SK);
    AES_ECB_decrypt(&actx, enc_data);

    printf("Fog %u: Data [%u] from device %u\n",
           node_id, enc_data[0], dev->IDd);

    uint8_t reply[1] = {0};
    coap_set_payload(resp, reply, 1);
}

/* --------------------------------------------------------------------------
 * CoAP resource declarations
 * -------------------------------------------------------------------------- */
RESOURCE(res_devinfo,  "title=\"DevInfo\"",
         NULL, res_devinfo_handler,  NULL, NULL);
RESOURCE(res_auth,     "title=\"Auth\"",
         NULL, res_auth_handler,     NULL, NULL);
RESOURCE(res_ack,      "title=\"Ack\"",
         NULL, res_ack_handler,      NULL, NULL);
RESOURCE(res_data,     "title=\"Data\"",
         NULL, res_data_handler,     NULL, NULL);

/* ==========================================================================
 * Main process
 * ========================================================================== */
PROCESS(fog_proc, "Fog Authentication Server");
AUTOSTART_PROCESSES(&fog_proc);

PROCESS_THREAD(fog_proc, ev, data)
{
    PROCESS_BEGIN();

    memset(devices, 0, sizeof(devices));

    /* Compute Af = H(FOG_IDENTITY_ID || r1_fog) */
    {
        uint8_t af_in[1 + HASH_LEN];
        af_in[0] = (uint8_t)FOG_IDENTITY_ID;
        memcpy(af_in + 1, r1_fog, HASH_LEN);
        H(af_in, 1 + HASH_LEN, Af);
    }

    /* Initialise CoAP engine — no RPL root (only GW is root) */
    coap_engine_init();

    coap_activate_resource(&res_devinfo, "test/dev_info");
    coap_activate_resource(&res_auth,    "test/auth");
    coap_activate_resource(&res_ack,     "test/ack");
    coap_activate_resource(&res_data,    "test/data");

    printf("Fog %u: Started (Fog Authentication Server). Af=%02x%02x%02x\n",
           node_id, Af[0], Af[1], Af[2]);

    while (1) {
        PROCESS_WAIT_EVENT();
    }

    PROCESS_END();
}
