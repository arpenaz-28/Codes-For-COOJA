#ifndef PROJECT_CONF_H_
#define PROJECT_CONF_H_

/* --------------------------------------------------------------------------
 * Topology — 100-mote COOJA simulation (DAuth / Das[1] Base Scheme)
 *
 *   Node 1        = GW  (RPL root + data sink)
 *   Nodes 2-80    = AS  (Authentication Server nodes; only 2 & 3 active)
 *   Nodes 81-100  = IoT Device nodes (20 devices)
 *
 *   Device-to-AS assignment (same as Proposed for apples-to-apples comparison):
 *     id_as = AS_NODE_ID + ((node_id - FIRST_DEVICE_ID) % NUM_AS)
 *     Devices 81-90  → AS node 2
 *     Devices 91-100 → AS node 3
 *
 * Packet size summary (DAuth — smaller than Proposed due to no PID):
 *   Auth send  : 34 B  (id_d(1) | y_asd(32) | ts_1(1))
 *   Auth recv  : 33 B  (ts_2(1) | m_H(32))
 *   GW token   : 50 B  (id_d(1) | id_as(1) | enc_tok(48))
 *   Data send  : 17 B  (id_d(1) | enc_data(16))
 *
 * For comparison — Proposed packet sizes:
 *   Auth send  : 65 B  (PID(32) | y_asd(32) | ts_1(1))
 *   Auth recv  : 33 B  (ts_2(1) | m_H(32))
 *   GW token   : 81 B  (new_PID(32) | id_as(1) | enc_tok(48))
 *   Data send  : 48 B  (PID(32) | enc_data(16))
 * -------------------------------------------------------------------------- */
#define GW_NODE_ID       1
#define AS_NODE_ID       2
#define NUM_AS           2
#define FIRST_DEVICE_ID  81

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
