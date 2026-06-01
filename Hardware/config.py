"""
Network config for hardware experiments.
GW_IP is set via environment variable GW_IP (set on the RPis before running).

Usage (on RPi before running any script):
    export GW_IP=192.168.1.XXX   # PC's IP on the shared network
    export AS_IP=192.168.1.113
    export DEV_IP=192.168.1.132
"""
import os

GW_IP  = os.environ.get("GW_IP",  "192.168.1.100")   # PC — update when known
AS_IP  = os.environ.get("AS_IP",  "192.168.1.113")   # RPi 1 (Pi)
DEV_IP = os.environ.get("DEV_IP", "192.168.1.132")   # RPi 2 (Apex)

# TCP ports (one service per port per role)
PORT_GW_TOKEN  = 5001   # AS → GW: auth token delivery
PORT_GW_KEYEX  = 5002   # Device → GW: key exchange
PORT_GW_DATA   = 5003   # Device → GW: data
PORT_AS_ENROLL = 5004   # Device → AS: enrollment
PORT_AS_AUTH   = 5005   # Device → AS: auth + key-exchange reply

# Node IDs (match COOJA simulation)
NODE_GW  = 1
NODE_AS  = 2
NODE_DEV = 3

# Protocol constants (Base scheme DH)
DH_G = 5
DH_P = 23
DH_A = 5   # device exponent
DH_B = 6   # GW exponent

# Zhou scheme ports (GW-centric; SN=RPi1, User=RPi2)
PORT_ZHOU_USER_REG = 5011   # User → GW: user registration
PORT_ZHOU_SN_REG   = 5012   # SN → GW: sensor registration (two-step)
PORT_ZHOU_AUTH     = 5013   # User → GW: M1 (GW replies with M4 after M2/M3)
PORT_ZHOU_M2       = 5014   # GW → SN: M2 delivery (SN replies with M3)

NODE_SN  = NODE_AS   # RPi 1 is SN in Zhou scheme
