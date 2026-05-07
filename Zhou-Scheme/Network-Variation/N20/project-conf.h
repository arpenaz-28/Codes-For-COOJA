#ifndef PROJECT_CONF_H_
#define PROJECT_CONF_H_

/* --------------------------------------------------------------------------
 * Network Variation — N=20 total nodes
 *   Node 1          = RPL root / data sink (GW)
 *   Nodes 2–3       = Active GW servers (2 active)
 *   Nodes 4–18      = Sensor nodes (15 SN; only 2 active per user binding)
 *   Nodes 19–20     = User/Doctor devices (2 users)
 *
 *   User → SN binding:   SN_id = user_id - SN_USER_OFFSET  (user 19→SN4, 20→SN5)
 *   User → GW_server:    user_id <= GW_USER_SPLIT → GW_SERVER_ID, else GW_SERVER_ID2
 *   SN   → GW_server:    sn_id  <= GW_SN_SPLIT   → GW_SERVER_ID, else GW_SERVER_ID2
 * -------------------------------------------------------------------------- */
#define GW_NODE_ID        1
#define GW_SERVER_ID      2
#define GW_SERVER_ID2     3
#define FIRST_SN_ID       4
#define LAST_SN_ID        18
#define FIRST_USER_ID     19

/* Parameterised binding constants (replaces hardcoded magic numbers) */
#define SN_USER_OFFSET    15   /* user_id - SN_USER_OFFSET = bound SN id */
#define GW_USER_SPLIT     19   /* users <= 19 → GW2, > 19 → GW3 */
#define GW_SN_SPLIT        4   /* SN  <=   4  → GW2, >  4 → GW3 — aligned with GW_USER_SPLIT */

#define ENERGEST_CONF_ON 1

#define COAP_MAX_CHUNK_SIZE   160
#define REST_MAX_CHUNK_SIZE   160

#define RPL_ENABLED           1
#define LOG_CONF_LEVEL_RPL    LOG_LEVEL_NONE

#define CSMA_CONF_MAX_BACKOFF        5
#define CSMA_CONF_MIN_BACKOFF        3
#define CSMA_CONF_CCA_THRESHOLD      -80
#define CSMA_CONF_MAX_FRAME_RETRIES  5

#define FRESHNESS_WINDOW  120

#endif /* PROJECT_CONF_H_ */
