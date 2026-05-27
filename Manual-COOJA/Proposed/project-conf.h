#ifndef PROJECT_CONF_H_
#define PROJECT_CONF_H_

/* --------------------------------------------------------------------------
 * Topology — 100-mote COOJA simulation (Proposed / Revised-Anonymity scheme)
 *
 *   Node 1        = GW  (RPL root + Registration Authority)
 *   Nodes 2-80   = AS motes (79 total; only nodes 2 & 3 are ACTIVE)
 *                   Nodes 4-80 run as-node firmware but have no devices assigned
 *   Nodes 81-100 = IoT Device nodes (20 devices)
 *
 *   Device-to-AS assignment:
 *     AS = AS_NODE_ID + ((node_id - FIRST_DEVICE_ID) % NUM_AS)
 *     Devices 81-90  → AS node 2
 *     Devices 91-100 → AS node 3
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
