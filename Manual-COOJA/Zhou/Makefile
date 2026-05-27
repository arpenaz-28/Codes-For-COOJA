CONTIKI_PROJECT = user-node gw-server sn-node gw-node
all: $(CONTIKI_PROJECT)

CONTIKI = /home/apex/contiki-ng
PROJECT_SOURCEFILES += aes.c sha256.c
MODULES += os/net/app-layer/coap

CFLAGS += -Wno-error=unused-function
CFLAGS += -Wno-error=unused-variable
CFLAGS += -Wno-error=unused-result
CFLAGS += -Wno-error=unused-but-set-variable

include $(CONTIKI)/Makefile.include
