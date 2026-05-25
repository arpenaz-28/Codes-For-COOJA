CONTIKI_PROJECT = gw-node as-node device-node
all: $(CONTIKI_PROJECT)

PROJECT_SOURCEFILES += aes.c sha256.c
MODULES += os/net/app-layer/coap

CFLAGS += -Wno-error=unused-function
CFLAGS += -Wno-error=unused-variable
CFLAGS += -Wno-error=unused-result
CFLAGS += -Wno-error=unused-but-set-variable

CONTIKI = /home/apex/contiki-ng
include $(CONTIKI)/Makefile.include
