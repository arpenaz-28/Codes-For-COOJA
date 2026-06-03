#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "contiki.h"
#include "coap-engine.h"
#include "aes.h"
#include "sys/energest.h"
#include "net/routing/routing.h"
#include "net/netstack.h"
#include "net/ipv6/simple-udp.h"
#include "net/ipv6/uip-ds6.h"
#include "net/routing/rpl-lite/rpl.h"
#include "net/mac/tsch/tsch.h"
#include "sys/node-id.h"
#define LOG_MODULE "coap-hello-gateway"
#define LOG_LEVEL LOG_LEVEL_INFO
#define CURRENT_CPU     1.8e-3     // in Amps
#define CURRENT_LPM     0.0545e-3
#define CURRENT_TX      17.4e-3
#define CURRENT_RX      18.8e-3
#define SUPPLY_VOLTAGE  3.0  
#include "sys/log.h"

//nt8_t nkey_gw_d[16] = {0x67, 0x61, 0x74, 0x73, 0x20, 0x6D, 0x79, 0x20, 0x4B, 0x75, 0x6F, 0x67, 0x20, 0x46, 0x75};

uint8_t k_gw_as[16] = {0x67, 0x62, 0x74, 0x73, 0x20, 0x6D, 0x79, 0x20, 0x4B, 0x75, 0x6F, 0x67, 0x20, 0x46, 0x75};
uint8_t auth_id_ts[16], key1[16],key2[16],payload[16];
typedef struct clients{
		uint8_t id_d;
		uint8_t id_as;
		uint8_t k_gw_d[32];
		uint8_t ts_auth;
	}clients;
	
clients c[20];
static uint8_t g=5,p=23,b=6; 

/*double cpu_reg,cpu_auth=0;
  double energy_reg,energy_auth=0;
static void print_energest_stats(double *seconds_cpu,double *total_energy) {
  energest_flush(); // Always flush before reading

  unsigned long cpu_ticks = energest_type_time(ENERGEST_TYPE_CPU);
  unsigned long lpm_ticks = energest_type_time(ENERGEST_TYPE_LPM);
  unsigned long tx_ticks  = energest_type_time(ENERGEST_TYPE_TRANSMIT);
  unsigned long rx_ticks  = energest_type_time(ENERGEST_TYPE_LISTEN);

  *seconds_cpu = cpu_ticks / (double)ENERGEST_SECOND;
  double seconds_lpm = lpm_ticks / (double)ENERGEST_SECOND;
  double seconds_tx  = tx_ticks  / (double)ENERGEST_SECOND;
  double seconds_rx  = rx_ticks  / (double)ENERGEST_SECOND;

  double energy_cpu = (*seconds_cpu) * CURRENT_CPU * SUPPLY_VOLTAGE;
  double energy_lpm = seconds_lpm * CURRENT_LPM * SUPPLY_VOLTAGE;
  double energy_tx  = seconds_tx  * CURRENT_TX  * SUPPLY_VOLTAGE;
  double energy_rx  = seconds_rx  * CURRENT_RX  * SUPPLY_VOLTAGE;

  *total_energy = energy_cpu + energy_lpm + energy_tx + energy_rx;

 // printf("\n--- Energest Statistics ---\n");
  //printf("CPU Active Time   : %lu ticks (%.3f s)\n", cpu_ticks, seconds_cpu);
 // printf("LPM Time          : %lu ticks (%.3f s)\n", lpm_ticks, seconds_lpm);
 // printf("Transmit Time     : %lu ticks (%.3f s)\n", tx_ticks, seconds_tx);
  //printf("Listen Time       : %lu ticks (%.3f s)\n", rx_ticks, seconds_rx);
 // printf("Estimated Energy  : %.6f J\n", total_energy);
//  return (cpu_ticks,total_energy);
//  printf("---------------------------\n");
}*/

static void res_authtoken_handler(coap_message_t *request, coap_message_t *response,
                                uint8_t *buffer, uint16_t preferred_size, int32_t *offset);

RESOURCE(res_authtoken,
         "title=\"Hello reg2: ?len=0..\";rt=\"Text\"",
         res_authtoken_handler,
         NULL,
         NULL,
         NULL);

static void res_authtoken_handler(coap_message_t *request, coap_message_t *response,
       
       
                                uint8_t *buffer, uint16_t preferred_size, int32_t *offset) {
        
        
   // print_energest_stats(&cpu_reg,&energy_reg);      
         uint8_t id_d;                        
  
  const uint8_t *chunk;
  char *message="Received";
  printf("\nReceived auth token");
  int len = coap_get_payload(request, &chunk);
  if (len != 48) {
  	printf("\n stale packet");
  	return;
  }
  memset(auth_id_ts,0,16);
  memcpy(auth_id_ts,chunk,16);
  struct AES_ctx aes_ctx_ch_d;
  AES_init_ctx(&aes_ctx_ch_d,k_gw_as);
  AES_ECB_decrypt(&aes_ctx_ch_d,auth_id_ts);
 id_d=auth_id_ts[0];
  
  //uint8_t current_time = (uint8_t)(clock_time() / CLOCK_SECOND);
  
     printf("Authentication token for Node %u\n", id_d);
  
 
  c[id_d % 20].id_d=id_d;
  printf("\n Obtained auth_token is %u",id_d);
  c[id_d % 20].id_as=auth_id_ts[1];
  c[id_d % 20].ts_auth=auth_id_ts[2];
  memset(key1,0,16);
  memcpy(key1,chunk+16,16);
  memset(key2,0,16);
  memcpy(key2,chunk+32,16);
  
  AES_init_ctx(&aes_ctx_ch_d,k_gw_as);
  AES_ECB_decrypt(&aes_ctx_ch_d,key1);
  
   AES_init_ctx(&aes_ctx_ch_d,k_gw_as);
  AES_ECB_decrypt(&aes_ctx_ch_d,key2);
  
  memcpy(c[id_d % 20].k_gw_d,key1,16);
  memcpy(c[id_d % 20].k_gw_d + 16, key2,16);
  
  printf("\n The value of session key is k_gw_d");
  for(int i=0;i<32;i++)
  {
  	printf("%u",c[id_d % 20].k_gw_d[i]);
  }
    

 coap_set_payload(response,(uint8_t *)message,strlen(message));  
 // print_energest_stats(&cpu_auth,&energy_auth);
 
 // printf("\n The CPU time and energy at the end of authenticatication for client %u by server %u and gateway %u are %f and %f",id_d,c[id_d % 20].id_as,node_id,(cpu_auth-cpu_reg),(energy_auth-energy_reg));
//cpu_reg=cpu_auth;
//energy_reg=energy_auth;

  
  
}

static void res_key_update_handler(coap_message_t *request, coap_message_t *response, uint8_t *buffer, uint16_t preferred_size, int32_t *offset);

RESOURCE(res_key_update,
         "title=\"Hello challenge: ?len=0..\";rt=\"Text\"",
         res_key_update_handler,
         NULL,
         NULL,
         NULL);
         

static void
res_key_update_handler(coap_message_t *request, coap_message_t *response, uint8_t *buffer, uint16_t preferred_size, int32_t *offset)
{
	  const uint8_t *chunk;
          int len = coap_get_payload(request, &chunk);
          if (len != 17) {
             printf("Invalid payload length: %d\n", len);
             return;
            }
            
            uint8_t id_d=chunk[0];
          memset(payload,0,16);
          memcpy(payload,chunk+1,16);
         
          uint8_t K_GW_D[16];
          memset(K_GW_D,0,16);
         for(int i=0;i<16;i++)
        {
        	K_GW_D[i]=c[id_d % 20].k_gw_d[i];
        }
          struct AES_ctx aes_ctx_ch_d;
          AES_init_ctx(&aes_ctx_ch_d,K_GW_D);
	  AES_ECB_decrypt(&aes_ctx_ch_d,payload);
	  
	 // uint8_t id_d=datareq[0];
	  uint8_t alpha=payload[1];
	   printf("\n the value of alpha is %u",alpha);
	  c[id_d % 20].k_gw_d[0]=(alpha ^ b)% p;
	  
	  for(int i=1;i<32;i++)
	  	c[id_d % 20].k_gw_d[i]=0;
	  
	  uint8_t beta=(g ^ b)% p;
	  memset(payload,0,16);
	  payload[0]=beta;
	  printf("\n the value of beta is %u",beta);
	    AES_init_ctx(&aes_ctx_ch_d,K_GW_D);
	  AES_ECB_encrypt(&aes_ctx_ch_d,payload);
 

 
         coap_set_payload(response, payload, sizeof(payload));
 // printf("\n The energy requirement of gateway after data transfer");
  //  print_energest_stats();
}


static void res_data_handler(coap_message_t *request, coap_message_t *response,
                             uint8_t *buffer, uint16_t preferred_size, int32_t *offset);

RESOURCE(res_data,
         "title=\"Hello reg2: ?len=0..\";rt=\"Text\"",
         res_data_handler,
         NULL,
         NULL,
         NULL);

static void res_data_handler(coap_message_t *request, coap_message_t *response,
                             uint8_t *buffer, uint16_t preferred_size, int32_t *offset) {
  const uint8_t *chunk;
   uint8_t auth[1];
  if (coap_get_payload(request, &chunk)) {
  
    uint8_t id_d=chunk[0];
    memset(payload,0,16);
    memcpy(payload,chunk+1,16);
   

     uint8_t K_GW_D[16];
    memset(K_GW_D,0,16);
    for(int i=0;i<16;i++)
        {
        	K_GW_D[i]=c[id_d % 20].k_gw_d[i];
        }
    struct AES_ctx aes_ctx_ch_d;
    AES_init_ctx(&aes_ctx_ch_d,K_GW_D);
    AES_ECB_decrypt(&aes_ctx_ch_d,payload);  
    
    printf("\n The message obtained for node %u is %d",id_d,payload[0]);
    
       
  
    auth[0]=0;
    coap_set_payload(response, auth, 1);
    
    
    }
     
    
}    
    


extern coap_resource_t res_authtoken;
extern coap_resource_t res_data;

PROCESS(er_example_server, "Erbium Example Server");
AUTOSTART_PROCESSES(&er_example_server);

PROCESS_THREAD(er_example_server, ev, data) {
  PROCESS_BEGIN();
 //ETSTACK_MAC.on();
 //sch_set_coordinator(1);
  NETSTACK_ROUTING.root_start();

  uip_ipaddr_t ipaddr;
  if (NETSTACK_ROUTING.get_root_ipaddr(&ipaddr)) {
    LOG_DBG("RPL DAG Root IP: ");
    LOG_DBG_6ADDR(&ipaddr);
    LOG_DBG_("\n");
  }

  uip_ipaddr_t prefix;
  uip_ip6addr(&prefix, 0xfd00, 0, 0, 0, 0, 0, 0, 0);

  uint8_t flags = 0x40; // On-link + Autonomous address configuration
  if (rpl_set_prefix_from_addr(&prefix, 64, flags)) {
    LOG_DBG("Prefix set successfully\n");
  } else {
    LOG_WARN("Failed to set prefix\n");
  }

  PROCESS_PAUSE();

  LOG_INFO("Starting Erbium Example Server\n");

  coap_activate_resource(&res_authtoken, "test/auth_token");
   coap_activate_resource(&res_key_update, "test/keyupdate");
  coap_activate_resource(&res_data, "test/data");

  LOG_INFO("Server is listening for requests\n");

  while (1) {
    PROCESS_WAIT_EVENT();
      
    // No button handling in this simplified version
  }

  PROCESS_END();
}

