#ifndef PROJECT_CONF_H_
#define PROJECT_CONF_H_

/* --------------------------------------------------------------------------
 * Network Variation — N=120 total nodes (20% users)
 *   Node 1          = RPL root / data sink (GW)
 *   Nodes 2–3       = Active GW servers (2 active)
 *   Nodes 4–96      = Sensor nodes (93 SN; 24 active per user binding)
 *   Nodes 97–120    = User/Doctor devices (24 users; 20% of N=120)
 *
 *   User → SN binding:   SN_id = user_id - SN_USER_OFFSET  (user 97→SN4 … 120→SN27)
 *   User → GW_server:    user_id <= GW_USER_SPLIT → GW_SERVER_ID, else GW_SERVER_ID2
 *   SN   → GW_server:    sn_id  <= GW_SN_SPLIT   → GW_SERVER_ID, else GW_SERVER_ID2
 * -------------------------------------------------------------------------- */
#define GW_NODE_ID        1
#define GW_SERVER_ID      2
#define GW_SERVER_ID2     3
#define FIRST_SN_ID       4
#define LAST_SN_ID        96
#define FIRST_USER_ID     97

#define SN_USER_OFFSET    93   /* user_id - 93 = bound SN id (97→4, 98→5, …, 120→27) */
#define GW_USER_SPLIT     108  /* users 97-108 → GW2; users 109-120 → GW3 */
#define GW_SN_SPLIT       15   /* SN 4-15 → GW2; SN 16-27 → GW3 */

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
