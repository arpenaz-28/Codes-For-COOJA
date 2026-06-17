#ifndef PROJECT_CONF_H_
#define PROJECT_CONF_H_

/* --------------------------------------------------------------------------
 * Li-Scheme (Li, Huang & Yu, Computer Networks 2024) — COOJA mapping.
 *
 * Same 100-node topology as the other schemes so results are comparable:
 *   Node 1        = GW  -> Management Server (MS): registration only
 *   Nodes 2-80    = AS  -> Service Nodes (SN): end-to-end verifier
 *   Nodes 81-100  = IoT terminal devices (TD): 20 newly-joined devices (20%)
 *   Devices 81-90 use SN node 2, devices 91-100 use SN node 3
 *
 * Li is end-to-end TD<->SN; the MS (node 1) only issues parameters at
 * registration (the "secure channel" phase), mirroring how the RA/MS is used
 * in the other schemes. This keeps the network identical for a fair compare.
 * -------------------------------------------------------------------------- */
#define GW_NODE_ID       1     /* RPL root + Management Server (MS) */
#define FOG1_NODE_ID     2     /* Service Node 1 (devices 81-90) */
#define FOG2_NODE_ID     3     /* Service Node 2 (devices 91-100) */
#define FOG_SPLIT_ID     91    /* devices < 91 -> SN1, >= 91 -> SN2 */
#define FOG_IDENTITY_ID  1

/* Enable energest for energy measurements */
#define ENERGEST_CONF_ON 1

/* CoAP payload ceiling — Li messages carry 64-byte ECC points (uncompressed),
 * so the largest message (registration blob, ~208 B) needs a bigger chunk. */
#define COAP_MAX_CHUNK_SIZE   256
#define REST_MAX_CHUNK_SIZE   256

/* RPL */
#define RPL_ENABLED           1
#define LOG_CONF_LEVEL_RPL    LOG_LEVEL_NONE

/* MAC back-off tuning (identical to other schemes) */
#define CSMA_CONF_MAX_BACKOFF        5
#define CSMA_CONF_MIN_BACKOFF        3
#define CSMA_CONF_CCA_THRESHOLD      -80
#define CSMA_CONF_MAX_FRAME_RETRIES  5

/* Freshness window (seconds) for timestamp-based checks */
#define FRESHNESS_WINDOW  120

#endif /* PROJECT_CONF_H_ */
