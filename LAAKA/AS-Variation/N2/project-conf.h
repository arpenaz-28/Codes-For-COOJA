#ifndef PROJECT_CONF_H_
#define PROJECT_CONF_H_

/* --------------------------------------------------------------------------
 * AS-Variation study — N=100 nodes, 2 active Fog AS
 *   Node 1          = GW (RPL root + Registration Authority)
 *   Nodes 2–80      = Fog AS nodes (79 total; only 2 & 3 active)
 *   Nodes 81–100    = IoT Devices (20 total)
 * -------------------------------------------------------------------------- */
#define GW_NODE_ID       1
#define FOG_BASE_ID      2      /* first active fog node ID */
#define NUM_ACTIVE_FOG   2      /* active fog count for this variant */
#define FIRST_DEVICE_ID  81     /* first device node ID */
#define FOG_IDENTITY_ID  1      /* shared fog IDf for Af = H(IDf||r1) */

#define ENERGEST_CONF_ON 1

#define COAP_MAX_CHUNK_SIZE   128
#define REST_MAX_CHUNK_SIZE   128

#define RPL_ENABLED           1
#define LOG_CONF_LEVEL_RPL    LOG_LEVEL_NONE

#define CSMA_CONF_MAX_BACKOFF        5
#define CSMA_CONF_MIN_BACKOFF        3
#define CSMA_CONF_CCA_THRESHOLD      -80
#define CSMA_CONF_MAX_FRAME_RETRIES  5

#define FRESHNESS_WINDOW  120

#endif /* PROJECT_CONF_H_ */
