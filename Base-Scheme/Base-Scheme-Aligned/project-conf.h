#ifndef PROJECT_CONF_H_
#define PROJECT_CONF_H_

/* --------------------------------------------------------------------------
 * Topology (COOJA):
 *   Node 1         = GW (RPL root)
 *   Nodes 2-80     = AS  (Authentication Servers)
 *   Nodes 81-100   = IoT Devices (20 nodes)
 *   Devices 81-90  use AS node 2,  Devices 91-100 use AS node 3
 * -------------------------------------------------------------------------- */
#define GW_NODE_ID       1
#define AS_NODE_ID       2
#define AS2_NODE_ID      3
#define AS_SPLIT_ID      91    /* devices < 91 -> AS2, >= 91 -> AS3 */

/* Enable energest for energy measurements */
#define ENERGEST_CONF_ON 1

/* CoAP payload ceiling */
#define COAP_MAX_CHUNK_SIZE   128
#define REST_MAX_CHUNK_SIZE   128

/* RPL */
#define LOG_CONF_LEVEL_RPL    LOG_LEVEL_NONE
#define LOG_CONF_LEVEL_TCPIP  LOG_LEVEL_WARN
#define LOG_CONF_LEVEL_MAC    LOG_LEVEL_WARN

/* MAC back-off tuning */
#define CSMA_CONF_MAX_BACKOFF        5
#define CSMA_CONF_MIN_BACKOFF        3
#define CSMA_CONF_CCA_THRESHOLD      -80
#define CSMA_CONF_MAX_FRAME_RETRIES  5

/* Freshness window (seconds) */
#define FRESHNESS_WINDOW  120

#endif /* PROJECT_CONF_H_ */
