CONTIKI_PROJECT =  coap-gateway
all: $(CONTIKI_PROJECT)

# Do not try to build on Sky because of code size limitation
PLATFORMS_EXCLUDE = sky z1
#PROJECT_SOURCEFILES += lib/tiny-AES/aes.h
# Include CoAP resources
#MODULES_REL += ./resources
#TARGET = cc26x0-cc13x0
#BOARD = launchpad/cc2650
CONTIKI=../../..

# Include the CoAP implementation
include $(CONTIKI)/Makefile.dir-variables
MODULES += $(CONTIKI_NG_APP_LAYER_DIR)/coap
#In project makefile
#MODULES += os/sys/simple-energest

#CONTIKI_MODULES += tiny-AES

#PROJECT_SOURCEFILES += tiny-AES/aes.h
#CFLAGS += -Os
MAKE_ROUTING = MAKE_ROUTING_RPL_LITE
MAKE_ROUTER = 1
MAKE_NET = MAKE_NET_IPV6
#CFLAGS += -DAES128=1
include $(CONTIKI)/Makefile.include
