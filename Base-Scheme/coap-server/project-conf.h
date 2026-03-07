#ifndef PROJECT_CONF_H_
#define PROJECT_CONF_H_

/* Enable RPL */
#define ROUTING_CONF_RPL_LITE 1
#define UIP_CONF_ROUTER 1
#define RPL_CONF_ROUTER 1

/* Enable UDP forwarding */
#define UIP_CONF_FORWARDER 1
#define UIP_CONF_UDP 1

/* Set CSMA backoff parameters */
#define CSMA_CONF_MAX_BACKOFF 5    // max backoff exponent (2^5 = 32 units)
#define CSMA_CONF_MIN_BACKOFF 3    // min backoff exponent (2^3 = 8 units)

/* Adjust CCA threshold (default usually -75 dBm) */
#define CSMA_CONF_CCA_THRESHOLD -80  // more sensitive; lower value means more sensitive

/* Optionally, increase max number of transmissions before dropping */
#define CSMA_CONF_MAX_FRAME_RETRIES 5

/* Enable logs */
#define LOG_CONF_LEVEL_RPL LOG_LEVEL_NONE


#endif /* PROJECT_CONF_H_ */
