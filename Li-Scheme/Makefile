CONTIKI_PROJECT = device-node as-node gw-node
all: $(CONTIKI_PROJECT)

CONTIKI = /opt/contiki-ng

# Real ECC (micro-ecc, secp256r1) + shared hash/AES primitives.
# Run ./setup.sh first to vendor uECC.c/uECC.h and copy sha256.c/aes.c.
PROJECT_SOURCEFILES += aes.c sha256.c uECC.c
MODULES += os/net/app-layer/coap

# micro-ecc configuration: enable secp256r1, fixed word size for the
# native (ContikiMoteType) target which compiles to host x86.
CFLAGS += -DuECC_SUPPORTS_secp256r1=1
CFLAGS += -DuECC_SUPPORT_COMPRESSED_POINT=0
CFLAGS += -DuECC_OPTIMIZATION_LEVEL=2

# Suppress non-fatal warnings (same as the other schemes)
CFLAGS += -Wno-error=unused-function
CFLAGS += -Wno-error=unused-variable
CFLAGS += -Wno-error=unused-result
CFLAGS += -Wno-error=unused-but-set-variable

include $(CONTIKI)/Makefile.include
