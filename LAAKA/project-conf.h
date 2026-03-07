#ifndef PROJECT_CONF_H_
#define PROJECT_CONF_H_

/* --------------------------------------------------------------------------
 * Topology (COOJA):
 *   Node 1         = GW (RPL root + Registration Authority)
 *   Nodes 2-80     = Fog Authentication Servers (79 nodes)
 *   Nodes 81-100   = IoT Devices (20 nodes)
 *   Devices 81-90  use Fog node 2,  Devices 91-100 use Fog node 3
 * -------------------------------------------------------------------------- */
#define GW_NODE_ID       1     /* RPL root + Registration Authority */
#define FOG1_NODE_ID     2     /* Fog Auth Server 1 (devices 81-90) */
#define FOG2_NODE_ID     3     /* Fog Auth Server 2 (devices 91-100) */
#define FOG_SPLIT_ID     91    /* devices < 91 -> FOG1, >= 91 -> FOG2 */
#define FOG_IDENTITY_ID  1     /* shared fog IDf for Af = H(IDf||r1) */

/* Enable energest for energy measurements */
#define ENERGEST_CONF_ON 1

/* CoAP payload ceiling — largest message is AUTH_REP at 82 bytes */
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

/* Freshness window (seconds) for timestamp-based checks */
#define FRESHNESS_WINDOW  120

#endif /* PROJECT_CONF_H_ */
