#ifndef PROJECT_CONF_H_
#define PROJECT_CONF_H_

/* --------------------------------------------------------------------------
 * Topology (COOJA) — 50 AS + 50 Devices:
 *   Node 1        = Gateway (RPL root)
 *   Nodes 2–51    = Authentication Servers (50 nodes, all active)
 *   Nodes 52–101  = Device nodes (50 total)
 *   Assignment: device picks AS = AS_NODE_ID + ((node_id - FIRST_DEVICE_ID) % NUM_AS)
 *   → Device 52 → AS 2, Device 53 → AS 3, …, Device 101 → AS 51 (1 device per AS)
 * -------------------------------------------------------------------------- */
#define GW_NODE_ID       1
#define AS_NODE_ID       2    /* base AS node ID */
#define NUM_AS           50   /* total AS nodes (nodes AS_NODE_ID .. AS_NODE_ID+NUM_AS-1) */
#define FIRST_DEVICE_ID  52

/* Enable energest for energy measurements */
#define ENERGEST_CONF_ON 1

/* CoAP payload ceiling — must hold the largest packet (81 bytes for the
 * GW token message).  128 is sufficient.                                   */
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

/* Freshness window (seconds, uint8 counter wraps every 256 s).
 * Used for ts_1 sequence guard and clock-based ts_2/ts_auth checks.       */
#define FRESHNESS_WINDOW  120

#endif /* PROJECT_CONF_H_ */
