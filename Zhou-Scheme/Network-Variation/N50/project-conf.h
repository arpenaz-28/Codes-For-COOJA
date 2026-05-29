#ifndef PROJECT_CONF_H_
#define PROJECT_CONF_H_

/* --------------------------------------------------------------------------
 * Network Variation — N=50 total nodes (20% users)
 *   Node 1          = RPL root / data sink (GW)
 *   Nodes 2–3       = Active GW servers (2 active)
 *   Nodes 4–40      = Sensor nodes (37 SN; 5 active per user binding)
 *   Nodes 41–50     = User/Doctor devices (10 users; 20% of N=50)
 *
 *   User → SN binding:   SN_id = user_id - SN_USER_OFFSET  (user 41→SN4 … 50→SN13)
 *   User → GW_server:    user_id <= GW_USER_SPLIT → GW_SERVER_ID, else GW_SERVER_ID2
 *   SN   → GW_server:    sn_id  <= GW_SN_SPLIT   → GW_SERVER_ID, else GW_SERVER_ID2
 * -------------------------------------------------------------------------- */
#define GW_NODE_ID        1
#define GW_SERVER_ID      2
#define GW_SERVER_ID2     3
#define FIRST_SN_ID       4
#define LAST_SN_ID        40
#define FIRST_USER_ID     41

#define SN_USER_OFFSET    37   /* user_id - 37 = bound SN id (41→4, 42→5, …, 50→13) */
#define GW_USER_SPLIT     45   /* users <= 45 → GW2 (41-45); users 46-50 → GW3 */
#define GW_SN_SPLIT        8   /* SN  <=   8  → GW2 (SN4-8); SN > 8 → GW3 */

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
