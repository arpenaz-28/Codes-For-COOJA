#ifndef PROJECT_CONF_H_
#define PROJECT_CONF_H_

/* Zhou Desync Demo — 100-node topology
 *   Node 1        = GW (Medical Gateway + SN simulation combined, RPL root)
 *   Nodes 2–80    = RPL router nodes (79 routers)
 *   Nodes 81–100  = User nodes (Doctor devices, 20 users)
 *
 * The GW internally maintains per-user SN state (sn_SIDn vs gw_SIDn) so
 * that M3-loss desynchronisation can be simulated without a separate SN node.
 */
#define GW_NODE_ID       1
#define FIRST_USER_ID    81
#define NUM_USERS        20

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
