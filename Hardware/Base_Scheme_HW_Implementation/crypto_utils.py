import hashlib
import random
from Crypto.Hash import SHA256
from Crypto.Random import get_random_bytes

def H(x):
    if isinstance(x, str):
        x = x.encode()
    elif isinstance(x, bytes):
        pass
    else:
        x = str(x).encode()
    return SHA256.new(x).hexdigest()

def xor_strings(s1, s2):
    return hex(int(s1, 16) ^ int(s2, 16))[2:].zfill(len(s1))

def generate_random(length=16):
    return get_random_bytes(length).hex()

class APUF:
    def __init__(self, name, noise_prob=0.0):
        self.name = name
        self.noise_prob = noise_prob
        self.response_map = {}

    def _true_response(self, challenge_hex):
        if challenge_hex not in self.response_map:
            h = hashlib.sha256((challenge_hex + self.name).encode()).hexdigest()
            self.response_map[challenge_hex] = h[:16]
        return self.response_map[challenge_hex]

    def get_response(self, challenge_hex):
        true_resp = self._true_response(challenge_hex)
        if self.noise_prob == 0:
            return true_resp
        resp_int = int(true_resp, 16)
        mask = 0
        for bit in range(64):
            if random.random() < self.noise_prob:
                mask |= (1 << bit)
        noisy_int = resp_int ^ mask
        return hex(noisy_int)[2:].zfill(16)

_apuf1 = APUF("APUF1", noise_prob=0.0)
_apuf2 = APUF("APUF2", noise_prob=0.0)
_as_apuf1 = APUF("AS_APUF1", noise_prob=0.05)
_as_apuf2 = APUF("AS_APUF2", noise_prob=0.05)

def bapuf(challenge_hex, sel, for_as=False):
    if for_as:
        apuf = _as_apuf1 if sel == 0 else _as_apuf2
    else:
        apuf = _apuf1 if sel == 0 else _apuf2
    return apuf.get_response(challenge_hex)