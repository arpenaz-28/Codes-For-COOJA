#ifndef PROJECT_CONF_H_
#define PROJECT_CONF_H_

/* --------------------------------------------------------------------------
 * Network Variation — N=30 total nodes (20% users)
 *   Node 1          = RPL root / data sink (GW)
 *   Nodes 2–3       = Active GW servers (2 active)
 *   Nodes 4–24      = Sensor nodes (21 SN; 3 active per user binding)
 *   Nodes 25–30     = User/Doctor devices (6 users; 20% of N=30)
 *
 *   User → SN binding:   SN_id = user_id - SN_USER_OFFSET  (user 25→SN4 … 30→SN9)
 *   User → GW_server:    user_id <= GW_USER_SPLIT → GW_SERVER_ID, else GW_SERVER_ID2
 *   SN   → GW_server:    sn_id  <= GW_SN_SPLIT   → GW_SERVER_ID, else GW_SERVER_ID2
 * -------------------------------------------------------------------------- */
#define GW_NODE_ID        1
#define GW_SERVER_ID      2
#define GW_SERVER_ID2     3
#define FIRST_SN_ID       4
#define LAST_SN_ID        24
#define FIRST_USER_ID     25

#define SN_USER_OFFSET    21   /* user_id - 21 = bound SN id (25→4, 26→5, …, 30→9) */
#define GW_USER_SPLIT     27   /* users <= 27 → GW2 (25,26,27); users 28-30 → GW3 */
#define GW_SN_SPLIT        6   /* SN  <=   6  → GW2 (SN4,5,6); SN > 6 → GW3 */

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
