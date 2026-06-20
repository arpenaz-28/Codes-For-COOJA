/* scheme_compute_bench.c — per-scheme CRYPTOGRAPHIC COMPUTE cost on RPi 4B via
 * MIRACL Core (NIST P-256). Executes each scheme's *actual* operation sequence
 * (op-counts identical to Paper tab:comp_total / plot_comparison_kim_rpi.py) and
 * times the whole per-round (Auth) and Enrollment sequences live on hardware.
 *
 * This is the "compute-only" companion to the network-bound end-to-end hardware
 * chart: it isolates pure computation (no TCP), so the ECC fuzzy extractor in
 * Zhou's scheme is faithfully exercised.
 *
 * Op-counts (all entities; T_rand excluded, per the paper):
 *   LAAKA     enrol 3h            ; auth 16h
 *   Zhou      enrol 1puf+2h+1fe   ; auth 1puf+15h+1fe
 *   DAuth     enrol 2puf+1h       ; auth 2puf+8h +2aes
 *   Proposed  enrol 2puf+2h       ; auth 2puf+11h+2aes
 *
 * FE = ECC-based fuzzy extractor = SHA-256 -> scalar, one P-256 scalar mult
 *      (Dodis et al. Eurocrypt 2004; Kim et al. convention T_fe = T_M).
 *
 * Build:  gcc -O2 scheme_compute_bench.c miracl_core/core.a -lm -o scheme_compute_bench
 * Run:    ./scheme_compute_bench
 * Output: CSV to stdout  ->  scheme,phase,mean_ms,sd_ms,iters
 */
#include <stdio.h>
#include <string.h>
#include <stdint.h>
#include <time.h>
#include <math.h>
#include "miracl_core/core.h"
#include "miracl_core/big_256_56.h"
#include "miracl_core/ecp_NIST256.h"

#define N_WARMUP   200
#define N_MEASURE  2000

static inline double now_ms(void){
    struct timespec ts; clock_gettime(CLOCK_MONOTONIC,&ts);
    return (double)ts.tv_sec*1000.0 + (double)ts.tv_nsec/1.0e6;
}

static csprng RNG;

/* ── primitive ops (identical API to bench_min.c) ─────────────────────────── */
static char H_IN[32]   = "hash_input_data";
static char AES_KEY[16]= "0123456789abcdef";
static uint8_t PUF_DELAY[128];
static char PUF_CHAL[16]="puf_challenge_16";
static char BIO[32]    = "biometric_sample";

static inline void op_hash(void){
    hash256 sh; char d[32];
    HASH256_init(&sh);
    for(int j=0;j<32;j++) HASH256_process(&sh,H_IN[j]);
    HASH256_hash(&sh,d);
    /* prevent the optimiser from discarding the result */
    H_IN[0] ^= d[0];
}
static inline void op_aes(void){
    core_aes a; char blk[16]="plaintext_block!";
    AES_init(&a,ECB,16,AES_KEY,NULL);
    AES_encrypt(&a,blk);
    AES_KEY[0] ^= blk[0];
}
static inline void op_puf(void){
    volatile uint8_t r=0;
    for(int j=0;j<128;j++) r ^= (PUF_DELAY[j] & (uint8_t)((PUF_CHAL[j>>3]>>(j&7))&1));
    PUF_CHAL[0] ^= r;
}
static inline void op_fe(void){
    ECP_NIST256 R; BIG_256_56 k; hash256 sh; char d[32];
    HASH256_init(&sh);
    for(int j=0;j<32;j++) HASH256_process(&sh,BIO[j]);
    HASH256_hash(&sh,d);
    BIG_256_56_fromBytes(k,d);
    ECP_NIST256_generator(&R);
    ECP_NIST256_mul(&R,k);
    BIO[0] ^= d[1];
}

/* run one scheme phase: given op counts, execute the full sequence once */
static inline void run_seq(int puf,int hash,int aes,int fe){
    for(int i=0;i<puf;i++)  op_puf();
    for(int i=0;i<hash;i++) op_hash();
    for(int i=0;i<aes;i++)  op_aes();
    for(int i=0;i<fe;i++)   op_fe();
}

static void bench(const char*scheme,const char*phase,int puf,int hash,int aes,int fe){
    double s[N_MEASURE];
    for(int i=0;i<N_WARMUP;i++) run_seq(puf,hash,aes,fe);
    for(int i=0;i<N_MEASURE;i++){
        double t=now_ms();
        run_seq(puf,hash,aes,fe);
        s[i]=now_ms()-t;
    }
    double sum=0,sq=0;
    for(int i=0;i<N_MEASURE;i++){sum+=s[i];sq+=s[i]*s[i];}
    double m=sum/N_MEASURE, v=sq/N_MEASURE-m*m, sd=v>0?sqrt(v):0;
    printf("%s,%s,%.6f,%.6f,%d\n",scheme,phase,m,sd,N_MEASURE);
}

int main(void){
    char seed[32]; for(int i=0;i<32;i++) seed[i]=(char)(i*7+1);
    RAND_seed(&RNG,32,seed);
    for(int j=0;j<128;j++) PUF_DELAY[j]=(uint8_t)(j*0x6B+1);

    fprintf(stderr,"# MIRACL Core per-scheme compute benchmark (RPi 4B, NIST P-256)\n");
    fprintf(stderr,"# %d warm-up + %d measured per phase\n",N_WARMUP,N_MEASURE);

    printf("scheme,phase,mean_ms,sd_ms,iters\n");
    /*        scheme        phase     puf hash aes fe */
    bench("Proposed","enroll", 2, 2, 0, 0);
    bench("Proposed","auth",   2,11, 2, 0);
    bench("DAuth",   "enroll", 2, 1, 0, 0);
    bench("DAuth",   "auth",   2, 8, 2, 0);
    bench("LAAKA",   "enroll", 0, 3, 0, 0);
    bench("LAAKA",   "auth",   0,16, 0, 0);
    bench("Zhou",    "enroll", 1, 2, 0, 1);
    bench("Zhou",    "auth",   1,15, 0, 1);
    return 0;
}
