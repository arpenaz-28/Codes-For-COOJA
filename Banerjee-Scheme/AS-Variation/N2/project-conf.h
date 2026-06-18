#ifndef PROJECT_CONF_H_
#define PROJECT_CONF_H_

/* Banerjee AS-Variation: 2 active SD nodes
 * Fixed topology: 1 GWN + 79 SD nodes (IDs 2-80) + 20 U nodes (IDs 81-100)
 * Active SDs: IDs 2 through 3 (round-robin assigned)
 */
#define N_SD_ACTIVE    2
#define SD_BASE_ID     2
#define FIRST_DEV_ID   81
#define GWN_NODE_ID    1

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
