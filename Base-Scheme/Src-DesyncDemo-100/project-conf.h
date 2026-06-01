#ifndef PROJECT_CONF_H_
#define PROJECT_CONF_H_

/* Desync Demo — Base Scheme, 100-node topology
 *   Node 1        = Gateway (RPL root)
 *   Node 2        = Authentication Server
 *   Nodes 3–80    = RPL router nodes (78 routers, multi-hop mesh)
 *   Nodes 81–100  = Device nodes (20 devices)
 */
#define GW_NODE_ID       1
#define AS_NODE_ID       2
#define FIRST_DEVICE_ID  81
#define NUM_DEVICES      20

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
