#ifndef PROJECT_CONF_H_
#define PROJECT_CONF_H_

/* --------------------------------------------------------------------------
 * Network Variation — N=20 total nodes
 *   Node 1          = Gateway (RPL root)
 *   Nodes 2–3       = Active Authentication Servers (2 active)
 *   Nodes 4–18      = Filler AS motes (inactive, affect RF medium only)
 *   Nodes 19–20     = Device nodes (2 newly joined devices)
 *
 *   Device → AS assignment: AS_NODE_ID + ((node_id - FIRST_DEVICE_ID) % NUM_AS)
 *   → device 19 → AS 2,  device 20 → AS 3
 * -------------------------------------------------------------------------- */
#define GW_NODE_ID       1
#define AS_NODE_ID       2     /* base (lowest) active AS node ID */
#define NUM_AS           2     /* only 2 active AS regardless of total count */
#define FIRST_DEVICE_ID  19    /* first device node ID */

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
