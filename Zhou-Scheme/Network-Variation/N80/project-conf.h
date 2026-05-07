#ifndef PROJECT_CONF_H_
#define PROJECT_CONF_H_

/* --------------------------------------------------------------------------
 * Network Variation — N=80 total nodes
 *   Node 1          = RPL root / data sink (GW)
 *   Nodes 2–3       = Active GW servers (2 active)
 *   Nodes 4–72      = Sensor nodes (69 SN; only 8 active per user binding)
 *   Nodes 73–80     = User/Doctor devices (8 users)
 *
 *   User → SN binding:   SN_id = user_id - SN_USER_OFFSET  (user 73→SN4 … 80→SN11)
 *   User → GW_server:    user_id <= GW_USER_SPLIT → GW_SERVER_ID, else GW_SERVER_ID2
 *   SN   → GW_server:    sn_id  <= GW_SN_SPLIT   → GW_SERVER_ID, else GW_SERVER_ID2
 * -------------------------------------------------------------------------- */
#define GW_NODE_ID        1
#define GW_SERVER_ID      2
#define GW_SERVER_ID2     3
#define FIRST_SN_ID       4
#define LAST_SN_ID        72
#define FIRST_USER_ID     73

#define SN_USER_OFFSET    69   /* user_id - 69 = bound SN id */
#define GW_USER_SPLIT     76   /* users <= 76 → GW2, > 76 → GW3 */
#define GW_SN_SPLIT        7   /* SN  <=   7  → GW2, >  7 → GW3 — aligned with GW_USER_SPLIT */

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
