/*
 * Copyright (c) 2013, Institute for Pervasive Computing, ETH Zurich
 * All rights reserved.
 *
 * Redistribution and use in source and binary forms, with or without
 * modification, are permitted provided that the following conditions
 * are met:
 * 1. Redistributions of source code must retain the above copyright
 *    notice, this list of conditions and the following disclaimer.
 * 2. Redistributions in binary form must reproduce the above copyright
 *    notice, this list of conditions and the following disclaimer in the
 *    documentation and/or other materials provided with the distribution.
 * 3. Neither the name of the Institute nor the names of its contributors
 *    may be used to endorse or promote products derived from this software
 *    without specific prior written permission.
 *
 * THIS SOFTWARE IS PROVIDED BY THE INSTITUTE AND CONTRIBUTORS ``AS IS'' AND
 * ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
 * IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
 * ARE DISCLAIMED.  IN NO EVENT SHALL THE INSTITUTE OR CONTRIBUTORS BE LIABLE
 * FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
 * DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS
 * OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
 * HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
 * LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY
 * OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF
 * SUCH DAMAGE.
 *
 * This file is part of the Contiki operating system.
 */

/**
 * \file
 *      Erbium (Er) example project configuration.
 * \author
 *      Matthias Kovatsch <kovatsch@inf.ethz.ch>
 */

#ifndef PROJECT_CONF_H_
#define PROJECT_CONF_H_

#define RPL_ENABLED            1
#define RPL_DEBUG              1

/* Set CSMA backoff parameters */
#define CSMA_CONF_MAX_BACKOFF 5    // max backoff exponent (2^5 = 32 units)
#define CSMA_CONF_MIN_BACKOFF 3    // min backoff exponent (2^3 = 8 units)

/* Adjust CCA threshold (default usually -75 dBm) */
#define CSMA_CONF_CCA_THRESHOLD -80  // more sensitive; lower value means more sensitive

/* Optionally, increase max number of transmissions before dropping */
#define CSMA_CONF_MAX_FRAME_RETRIES 5
#define LOG_CONF_LEVEL_RPL     LOG_LEVEL_NONE

/* Logging */
//#define LOG_LEVEL_APP          LOG_LEVEL_DBG
//#define LOG_LEVEL LOG_LEVEL_NONE
//#define LOG_CONF_LEVEL_RPL     LOG_LEVEL_DBG  // Enable RPL-level logs

/* Enable client-side support for CoAP Observe */
#define COAP_OBSERVE_CLIENT    1

#endif /* PROJECT_CONF_H_ */

