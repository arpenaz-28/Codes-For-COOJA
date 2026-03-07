CONTIKI_PROJECT = coap-server
all: $(CONTIKI_PROJECT)

# Do not try to build on Sky because of code size limitation
#PLATFORMS_EXCLUDE = sky z1
#TARGET = cc26x0-cc13x0
#BOARD = launchpad/cc2650
# Include CoAP resources
#MODULES_REL += ./resources

CONTIKI=../../..
#PLATFORMS_ONLY = cc26x0-cc13x0
#BOARD = launchpad/cc2650
# Include the CoAP implementation
include $(CONTIKI)/Makefile.dir-variables
MODULES += $(CONTIKI_NG_APP_LAYER_DIR)/coap
CFLAGS += -fstack-usage

include $(CONTIKI)/Makefile.include
