#ifndef PROJECT_CONF_H_
#define PROJECT_CONF_H_

/* Banerjee N=120 topology:
 *   Node 1          = GWN
 *   Nodes 2–96 = SD (Sensing Devices)
 *   Nodes 97–120 = U  (Users, 20% newly-joined)
 *   U 97–108 → SD1 (node 2)
 *   U 109–120  → SD2 (node 3)
 */
#define GWN_NODE_ID    1
#define SD1_NODE_ID    2
#define SD2_NODE_ID    3
#define SD_SPLIT_ID   109

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
