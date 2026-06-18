#ifndef PROJECT_CONF_H_
#define PROJECT_CONF_H_

/* --------------------------------------------------------------------------
 * Topology (COOJA — 100-node network):
 *   Node 1        = GWN (RPL root + Gateway Node)
 *   Nodes 2–80    = SD  (Sensing Devices, 79 nodes)
 *   Nodes 81–100  = U   (Users, 20 nodes — 20% newly-joined)
 *   U 81–90  →  SD1 (node 2)
 *   U 91–100 →  SD2 (node 3)
 * -------------------------------------------------------------------------- */
#define GWN_NODE_ID    1     /* RPL root + Gateway Node                    */
#define SD1_NODE_ID    2     /* Sensing Device 1 (serves U nodes 81–90)    */
#define SD2_NODE_ID    3     /* Sensing Device 2 (serves U nodes 91–100)   */
#define SD_SPLIT_ID   91     /* U < 91 → SD1, U >= 91 → SD2               */

/* Enable energest for energy measurements */
#define ENERGEST_CONF_ON 1

/* CoAP payload ceiling — largest message is AUTH_REQ at 101 bytes */
#define COAP_MAX_CHUNK_SIZE   128
#define REST_MAX_CHUNK_SIZE   128

/* RPL */
#define RPL_ENABLED           1
#define LOG_CONF_LEVEL_RPL    LOG_LEVEL_NONE

/* MAC back-off tuning */
#define CSMA_CONF_MAX_BACKOFF        5
#define CSMA_CONF_MIN_BACKOFF        3
#define CSMA_CONF_CCA_THRESHOLD      -80
#define CSMA_CONF_MAX_FRAME_RETRIES  5

/* Freshness window (seconds) for timestamp-based replay checks */
#define FRESHNESS_WINDOW  120

#endif /* PROJECT_CONF_H_ */
