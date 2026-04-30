#ifndef PROJECT_CONF_H_
#define PROJECT_CONF_H_

/* --------------------------------------------------------------------------
 * Topology (COOJA) — 20 AS + 79 Devices:
 *   Node 1        = Gateway (RPL root)
 *   Nodes 2–21    = Authentication Servers (20 nodes, all active)
 *   Nodes 22–100  = Device nodes (79 total)
 *   Assignment: AS = AS_NODE_ID + ((node_id - FIRST_DEVICE_ID) % NUM_AS)
 *   → ~4 devices per AS (19 AS get 4 devices, 1 AS gets 3 devices)
 * -------------------------------------------------------------------------- */
#define GW_NODE_ID       1
#define AS_NODE_ID       2    /* base AS node ID */
#define NUM_AS           20   /* total AS nodes */
#define FIRST_DEVICE_ID  22

/* Enable energest for energy measurements */
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
