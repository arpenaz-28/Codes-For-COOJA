#ifndef PROJECT_CONF_H_
#define PROJECT_CONF_H_

/* --------------------------------------------------------------------------
 * Network Variation — N=80 total nodes (20% devices)
 *   Node 1          = Gateway (RPL root)
 *   Nodes 2–3       = Active Authentication Servers (2 active)
 *   Nodes 4–64      = Filler AS motes (inactive, affect RF medium only)
 *   Nodes 65–80     = Device nodes (16 newly joined devices; 20% of N=80)
 *
 *   Device → AS assignment: AS_NODE_ID + ((node_id - FIRST_DEVICE_ID) % NUM_AS)
 *   → devices 65,67,69,71,73,75,77,79 → AS 2;  devices 66,68,70,72,74,76,78,80 → AS 3
 * -------------------------------------------------------------------------- */
#define GW_NODE_ID       1
#define AS_NODE_ID       2
#define NUM_AS           2
#define FIRST_DEVICE_ID  65

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
