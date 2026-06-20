/* miracl_shim.c — thin C shim over MIRACL Core (NIST P-256), built as a shared
 * library for use from Python via ctypes. Provides exactly the primitives the
 * end-to-end hardware protocols need:
 *   - SHA-256                (interop-identical to hashlib.sha256)
 *   - AES-128-ECB enc/dec    (interop-identical to pycryptodome AES ECB)
 *   - ECC P-256 fuzzy extractor (SHA-256 -> scalar -> k.G, x-coord out) for Zhou
 *
 * Build (on RPi, against the configured MIRACL Core):
 *   gcc -O2 -fPIC -shared miracl_shim.c miracl_core/core.a -lm -o libmiraclshim.so
 */
#include <stdint.h>
#include <string.h>
#include "miracl_core/core.h"
#include "miracl_core/big_256_56.h"
#include "miracl_core/ecp_NIST256.h"

/* SHA-256 over `len` input bytes -> 32-byte digest */
void m_sha256(const uint8_t *in, int len, uint8_t *out32){
    hash256 sh; HASH256_init(&sh);
    for(int i=0;i<len;i++) HASH256_process(&sh,(int)in[i]);
    char d[32]; HASH256_hash(&sh,d);
    memcpy(out32,d,32);
}

/* AES-128-ECB encrypt `nblocks` 16-byte blocks (out may equal in) */
void m_aes128_ecb_enc(const uint8_t *key16, const uint8_t *in, int nblocks, uint8_t *out){
    core_aes a; char key[16]; memcpy(key,key16,16);
    AES_init(&a,ECB,16,key,NULL);
    for(int b=0;b<nblocks;b++){
        char blk[16]; memcpy(blk,in+16*b,16);
        AES_encrypt(&a,blk);
        memcpy(out+16*b,blk,16);
    }
    AES_end(&a);
}

/* AES-128-ECB decrypt `nblocks` 16-byte blocks (out may equal in) */
void m_aes128_ecb_dec(const uint8_t *key16, const uint8_t *in, int nblocks, uint8_t *out){
    core_aes a; char key[16]; memcpy(key,key16,16);
    AES_init(&a,ECB,16,key,NULL);
    for(int b=0;b<nblocks;b++){
        char blk[16]; memcpy(blk,in+16*b,16);
        AES_decrypt(&a,blk);
        memcpy(out+16*b,blk,16);
    }
    AES_end(&a);
}

/* ECC-based fuzzy extractor: SHA-256(in) -> scalar k, R = k.G, output R.x (32B).
 * Deterministic in `in`, so both parties derive the same value. Cost = one
 * P-256 scalar multiplication (= T_fe = T_M, Dodis/Kim convention). */
void m_fe_p256(const uint8_t *in, int len, uint8_t *out32){
    hash256 sh; HASH256_init(&sh);
    for(int i=0;i<len;i++) HASH256_process(&sh,(int)in[i]);
    char d[32]; HASH256_hash(&sh,d);
    BIG_256_56 k; BIG_256_56_fromBytes(k,d);
    ECP_NIST256 R; ECP_NIST256_generator(&R); ECP_NIST256_mul(&R,k);
    BIG_256_56 x,y; ECP_NIST256_get(x,y,&R);   /* affine x,y */
    char xb[32]; BIG_256_56_toBytes(xb,x);
    memcpy(out32,xb,32);
}
