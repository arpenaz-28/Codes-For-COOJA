#ifndef PROJECT_CONF_H_
#define PROJECT_CONF_H_

/* --------------------------------------------------------------------------
 * Network Variation — N=120 total nodes (20% devices)
 *   Node 1          = GW (RPL root + Registration Authority)
 *   Nodes 2–3       = Active Fog AS (FOG1=2, FOG2=3)
 *   Nodes 4–96      = Filler Fog motes (inactive, affect RF medium only)
 *   Nodes 97–120    = IoT Devices (24 newly joined; 20% of N=120)
 *
 *   Devices 97–108  → FOG1 (node_id < FOG_SPLIT_ID=109)
 *   Devices 109–120 → FOG2 (node_id >= FOG_SPLIT_ID=109)
 * -------------------------------------------------------------------------- */
#define GW_NODE_ID       1
#define FOG1_NODE_ID     2
#define FOG2_NODE_ID     3
#define FOG_SPLIT_ID     109   /* devices [97,108] → FOG1, [109,120] → FOG2 */
#define FOG_IDENTITY_ID  1

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
