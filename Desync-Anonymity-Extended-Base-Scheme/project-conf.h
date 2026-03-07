#ifndef PROJECT_CONF_H_
#define PROJECT_CONF_H_

/* --------------------------------------------------------------------------
 * Desync Demonstration Topology (small):
 *   Node 1   = Gateway (RPL root)
 *   Node 2   = Authentication Server
 *   Nodes 3–5 = Device nodes (3 devices to demonstrate desync)
 * -------------------------------------------------------------------------- */
#define GW_NODE_ID       1
#define AS_NODE_ID       2
#define FIRST_DEVICE_ID  3

/* Enable energest for energy measurements */
#define ENERGEST_CONF_ON 1

/* CoAP payload ceiling */
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

/* Freshness window */
#define FRESHNESS_WINDOW  120

#endif /* PROJECT_CONF_H_ */
