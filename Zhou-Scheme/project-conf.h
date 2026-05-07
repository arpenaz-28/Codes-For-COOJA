#ifndef PROJECT_CONF_H_
#define PROJECT_CONF_H_

/* --------------------------------------------------------------------------
 * Topology (COOJA) — Zhou et al. scheme
 *   Node 1         = RPL root (network gateway, receives data)
 *   Nodes 2–3      = Medical Gateway servers (active)
 *   Nodes 4–23     = Sensor Nodes (20 sensors with PUF)
 *   Nodes 24–80    = Filler GW-server motes (inactive)
 *   Nodes 81–100   = User/Doctor devices (20 users)
 *
 *   Binding: User i (81–100) → Sensor (i-77) (4–23)
 *            Users 81–90 → GW 2,  Users 91–100 → GW 3
 * -------------------------------------------------------------------------- */
#define GW_NODE_ID       1
#define GW_SERVER_ID     2
#define GW_SERVER_ID2    3
#define FIRST_SN_ID      4
#define LAST_SN_ID       23
#define FIRST_USER_ID    81

/* Parameterised binding constants — keeps existing 100-node topology intact */
#define SN_USER_OFFSET    77   /* user_id - 77 = bound SN id (81→4 … 100→23) */
#define GW_USER_SPLIT     90   /* users 81-90 → GW2, 91-100 → GW3 */
#define GW_SN_SPLIT       13   /* SN 4-13 → GW2, 14-23 → GW3 */

/* Enable energest for energy measurements */
#define ENERGEST_CONF_ON 1

/* CoAP payload ceiling — must hold largest packet.
 * M4: SKi(96B) + lambda(32B) = 128B                                       */
#define COAP_MAX_CHUNK_SIZE   160
#define REST_MAX_CHUNK_SIZE   160

/* RPL */
#define RPL_ENABLED           1
#define LOG_CONF_LEVEL_RPL    LOG_LEVEL_NONE

/* MAC back-off tuning */
#define CSMA_CONF_MAX_BACKOFF        5
#define CSMA_CONF_MIN_BACKOFF        3
#define CSMA_CONF_CCA_THRESHOLD      -80
#define CSMA_CONF_MAX_FRAME_RETRIES  5

/* Freshness window (seconds) */
#define FRESHNESS_WINDOW  120

#endif /* PROJECT_CONF_H_ */
