#ifndef PROJECT_CONF_H_
#define PROJECT_CONF_H_

/* --------------------------------------------------------------------------
 * Topology — 100-mote COOJA simulation (Zhou et al. scheme)
 *
 *   Node 1        = GW  (RPL root, data receiver)
 *   Node 2        = GW-Server (the single ACTIVE authentication/registration server)
 *   Node 3        = GW-Server (firmware loaded but IDLE — no devices routed here)
 *   Nodes 4-23   = Sensor Nodes (20 SNs, all registered with node 2)
 *   Nodes 24-80  = Filler motes (inactive)
 *   Nodes 81-100 = User/Doctor devices (20 users, all registered with node 2)
 *
 *   GW_USER_SPLIT = 100 → all user IDs (81-100) ≤ 100 → GW_SERVER_ID = 2
 *   GW_SN_SPLIT   = 23  → all SN IDs  (4-23)   ≤ 23  → GW_SERVER_ID = 2
 *   Binding: user_id - SN_USER_OFFSET = bound SN  (e.g. user 81 → SN 4)
 * -------------------------------------------------------------------------- */
#define GW_NODE_ID       1
#define GW_SERVER_ID     2
#define GW_SERVER_ID2    3
#define FIRST_SN_ID      4
#define LAST_SN_ID       23
#define FIRST_USER_ID    81

#define SN_USER_OFFSET   77
#define GW_USER_SPLIT   100   /* all users (81-100) → GW_SERVER_ID = 2 */
#define GW_SN_SPLIT      23   /* all SNs   (4-23)  → GW_SERVER_ID = 2 */

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
