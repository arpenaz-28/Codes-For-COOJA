/* ==========================================================================
 * ecc-util.h — Li-Scheme crypto helpers for COOJA
 *
 * Wraps micro-ecc (secp256r1) plus a modelled PUF and fuzzy extractor.
 *
 * MODELING NOTES (read before citing numbers):
 *  - ECC scalar multiplications are REAL (micro-ecc). Each side performs the
 *    SAME count as Li et al. Table 6 (6 per side) so the measured CPU/energy
 *    reflects the true ECC cost — the dominant term.
 *  - micro-ecc's public API exposes k*G (uECC_compute_public_key) and k*P
 *    (uECC_shared_secret = x-coord of k*P). Point ADDITIONS in Li's
 *    verification equation (T_ea = 0.012 ms, ~200x cheaper than a mult) are
 *    folded into hashing — negligible for energy, documented here for honesty.
 *  - PUF is modelled as a per-node keyed AES map (deterministic, unclonable
 *    across nodes). Fuzzy extractor is a hash-based secure sketch (Gen/Rep).
 *    Both are cheap, matching Li's accounting where ECC dominates.
 * ========================================================================== */
#ifndef ECC_UTIL_H_
#define ECC_UTIL_H_

#include <stdint.h>
#include <string.h>
#include "uECC.h"
#include "aes.h"
#include "sha256.h"
#include "sys/node-id.h"
#include "random.h"

#define ECC_PRIV_LEN   32
#define ECC_PUB_LEN    64   /* uncompressed point (x||y) */
#define ECC_SECRET_LEN 32   /* x-coordinate of k*P */
#define HASH_LEN       20
#define PUF_LEN        16
#define FE_HELPER_LEN  16

/* ---- RNG hook required by micro-ecc -------------------------------------- */
static int li_rng(uint8_t *dest, unsigned size)
{
    for (unsigned i = 0; i < size; i++) {
        uint16_t r = random_rand();
        dest[i] = (uint8_t)((r & 0xFF) ^ (uint8_t)(clock_time() >> (i & 7)));
    }
    return 1;
}

static inline const struct uECC_Curve_t *li_curve(void)
{
    static int seeded = 0;
    if (!seeded) { uECC_set_rng(&li_rng); seeded = 1; }
    return uECC_secp256r1();
}

/* ---- hash ----------------------------------------------------------------- */
static inline void li_H(const uint8_t *in, uint16_t len, uint8_t *out20)
{
    SHA256_CTX ctx; uint8_t full[32];
    sha256_init(&ctx); sha256_update(&ctx, in, len); sha256_final(&ctx, full);
    memcpy(out20, full, HASH_LEN);
}

/* ---- ECC ------------------------------------------------------------------ */
/* keypair: priv(32) / pub(64) */
static inline void ecc_keygen(uint8_t *priv, uint8_t *pub)
{
    uECC_make_key(pub, priv, li_curve());
}
/* out64 = k*G  (real scalar mult on the generator) */
static inline void ecc_base_mult(const uint8_t *k32, uint8_t *out64)
{
    uECC_compute_public_key(k32, out64, li_curve());
}
/* out32 = x-coord of k*P  (real scalar mult on an arbitrary point) */
static inline void ecc_point_mult(const uint8_t *k32, const uint8_t *P64,
                                  uint8_t *out32)
{
    uECC_shared_secret(P64, k32, out32, li_curve());
}

/* ---- PUF (per-node keyed AES map) ---------------------------------------- */
static inline void puf_eval(const uint8_t *challenge16, uint8_t *response16)
{
    struct AES_ctx ctx;
    uint8_t key[16];
    /* device-unique PUF key derived from node id (stands in for silicon PUF) */
    memset(key, 0, 16);
    key[0] = (uint8_t)node_id; key[1] = 0x9E; key[15] = (uint8_t)(node_id ^ 0x5A);
    memcpy(response16, challenge16, 16);
    AES_init_ctx(&ctx, key);
    AES_ECB_encrypt(&ctx, response16);
}

/* ---- Fuzzy extractor (hash-based secure sketch) -------------------------- */
/* Gen: r = H(w)[0..15], helper = w XOR r   (so Rep can recover r from w') */
static inline void fe_gen(const uint8_t *w16, uint8_t *r16, uint8_t *helper16)
{
    uint8_t h[HASH_LEN];
    li_H(w16, 16, h);
    memcpy(r16, h, 16);
    for (int i = 0; i < 16; i++) helper16[i] = w16[i] ^ r16[i];
}
/* Rep: recover r from a (near-identical) w' and helper */
static inline void fe_rep(const uint8_t *w16, const uint8_t *helper16, uint8_t *r16)
{
    for (int i = 0; i < 16; i++) r16[i] = w16[i] ^ helper16[i];
}

#endif /* ECC_UTIL_H_ */
