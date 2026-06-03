CONTIKI_PROJECT = coap-client
all: $(CONTIKI_PROJECT)

CONTIKI = ../../..
#TARGET = cc26x0-cc13x0
#BOARD = launchpad/cc2650

include $(CONTIKI)/Makefile.dir-variables
MODULES += $(CONTIKI_NG_APP_LAYER_DIR)/coap
CFLAGS += -Wno-error -Wno-error=unused-result -Wno-error=maybe-uninitialized

include $(CONTIKI)/Makefile.include


