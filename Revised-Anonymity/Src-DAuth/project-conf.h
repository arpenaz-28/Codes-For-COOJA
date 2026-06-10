#ifndef PROJECT_CONF_H_
#define PROJECT_CONF_H_

/* --------------------------------------------------------------------------
 * DAuth / Das[1] base scheme — default 100-mote layout (overridden by the
 * sweep runner per config):
 *   Node 1        = Gateway (RPL root)
 *   Nodes 2–80    = Authentication Servers (only NUM_AS active)
 *   Nodes 81–100  = Device nodes (20 total)
 *   Assignment: id_as = AS_NODE_ID + ((node_id - FIRST_DEVICE_ID) % NUM_AS)
 * -------------------------------------------------------------------------- */
#define GW_NODE_ID       1
#define AS_NODE_ID       2
#define NUM_AS           2
#define FIRST_DEVICE_ID  81

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
