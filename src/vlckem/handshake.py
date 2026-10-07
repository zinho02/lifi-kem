"""Post-quantum handshake carried over the simulated optical link.

Protocol (two round trips, cf. NIST SP 800-227 Sec. 5 for the KEM usage):

    node -> AP:  ID_N, nonce Nc, encapsulation key ek        (ek_bytes)
    AP   -> node: ciphertext ct, nonce Ns                    (ct_bytes)
    both:        SK = KDF(K_KEM || Nc || Ns || transcript)

``role="node-keygen"`` places KeyGen and Decaps on the sensor node (the
arrangement of Nurmurodov et al.); ``role="ap-keygen"`` reverses it so that the
node only encapsulates.  Both cost the same on air; they differ in node compute
and in where the long-term decapsulation key lives.

Timings are taken from published measurements (see ``MCU_CYCLES``), not from
this machine: the simulator moves real bytes, but the microcontroller cost is a
literature-based model, and the paper says so.
"""
from __future__ import annotations

import hashlib
import math
import os
from dataclasses import dataclass

from . import mlkem

# ---------------------------------------------------------------- KEM catalogue
# Sizes: ML-KEM from FIPS 203 Table 3; code-based KEMs from the liboqs 0.15.0
# datasheets (BIKE spec 5.1, HQC spec 2023-04-30, Classic McEliece
# SUPERCOP-20221025).  HQC sizes differ between specification versions: the
# 2025-08-22 revision (HQC-1) uses a 2241-byte key and the same 4433-byte
# ciphertext.  The values here are the liboqs 0.15.0 ones.
KEM_SIZES = {
    "X25519":                  {"ek": 32, "ct": 32, "level": "classical"},
    "ML-KEM-512":              {"ek": 800, "ct": 768, "level": 1},
    "ML-KEM-768":              {"ek": 1184, "ct": 1088, "level": 3},
    "ML-KEM-1024":             {"ek": 1568, "ct": 1568, "level": 5},
    "HQC-128":                 {"ek": 2249, "ct": 4433, "level": 1},
    "BIKE-L1":                 {"ek": 1541, "ct": 1573, "level": 1},
    "Classic McEliece-348864": {"ek": 261120, "ct": 96, "level": 1},
}

# Cortex-M4 cycle counts.  ML-KEM: pqm4 benchmarks.csv (m4fspeed, mean of 10
# runs).  Classic McEliece: Chen & Chou, TCHES 2021(3), at 168 MHz.  X25519:
# Emill/X25519-Cortex-M4 (548 873 cycles per scalar multiplication, so key
# generation and shared-secret computation cost one each).
MCU_CYCLES = {
    "ML-KEM-512":  {"keygen": 392423, "encaps": 390881, "decaps": 428167},
    "ML-KEM-768":  {"keygen": 642096, "encaps": 658754, "decaps": 707827},
    "ML-KEM-1024": {"keygen": 1018976, "encaps": 1031565, "decaps": 1094008},
    "HQC-128":     {"keygen": 52705201, "encaps": 105650897, "decaps": 159569179},
    "BIKE-L1":     {"keygen": 24943740, "encaps": 3253983, "decaps": 65539093},
    "Classic McEliece-348864": {"keygen": 2146932033, "encaps": 582199, "decaps": 2706681},
    "X25519":      {"keygen": 548873, "encaps": 548873, "decaps": 548873},
}

MCU_CLOCK_HZ = 168e6     # STM32F4 at its maximum frequency, as in pqm4/TCHES
MCU_ACTIVE_W = 0.132     # ESP32 at 160 MHz, dual core: 44 mA at 3.0 V (datasheet)


@dataclass(frozen=True)
class LinkBudget:
    rate_bps: float
    ber: float = 0.0
    fragment_bytes: int = 128
    header_bytes: int = 8          # per-fragment framing
    ack_bytes: int = 8


def expected_transmissions(payload_bytes: int, fragment_bytes: int, ber: float,
                           header_bytes: int = 8) -> float:
    """Mean number of fragment transmissions under stop-and-wait ARQ.

    Each fragment carries ``fragment_bytes`` of payload plus a header and is
    retransmitted until it arrives intact, so with independent bit errors the
    number of attempts is geometric with success probability (1-BER)^bits.
    """
    n = math.ceil(payload_bytes / fragment_bytes)
    bits = 8 * (fragment_bytes + header_bytes)
    per = 1 - (1 - ber) ** bits
    if per >= 1:
        return float("inf")
    return n / (1 - per)


def airtime(payload_bytes: int, link: LinkBudget) -> float:
    """Seconds on air for a payload, including framing and ARQ."""
    tx = expected_transmissions(payload_bytes, link.fragment_bytes, link.ber,
                                link.header_bytes)
    per_frag_bits = 8 * (link.fragment_bytes + link.header_bytes + link.ack_bytes)
    return tx * per_frag_bits / link.rate_bps


def mcu_time(kem: str, role: str = "node-keygen") -> float:
    """Seconds of node computation for one handshake."""
    c = MCU_CYCLES[kem]
    ops = ("keygen", "decaps") if role == "node-keygen" else ("encaps",)
    return sum(c[o] for o in ops) / MCU_CLOCK_HZ


def handshake_bytes(kem: str, role: str = "node-keygen") -> dict:
    s = KEM_SIZES[kem]
    return {"uplink": s["ek"] if role == "node-keygen" else s["ct"],
            "downlink": s["ct"] if role == "node-keygen" else s["ek"],
            "total": s["ek"] + s["ct"]}


def handshake_time(kem: str, link: LinkBudget, role: str = "node-keygen") -> dict:
    b = handshake_bytes(kem, role)
    t_air = airtime(b["uplink"], link) + airtime(b["downlink"], link)
    t_cpu = mcu_time(kem, role)
    return {"kem": kem, "role": role, "bytes_total": b["total"],
            "t_air": t_air, "t_cpu": t_cpu, "t_total": t_air + t_cpu,
            "energy_mJ": 1e3 * t_cpu * MCU_ACTIVE_W,
            "air_fraction": t_air / (t_air + t_cpu)}


def crossover_rate(kem: str, link: LinkBudget, role: str = "node-keygen") -> float:
    """Link rate at which airtime equals node computation."""
    b = handshake_bytes(kem, role)
    t_air_at_ref = airtime(b["uplink"], link) + airtime(b["downlink"], link)
    return link.rate_bps * t_air_at_ref / mcu_time(kem, role)


def run_handshake(kem: str = "ML-KEM-512", link_rate: float = 100e3, ber: float = 0.0,
                  fragment_bytes: int = 128, role: str = "node-keygen",
                  seed: int | None = None) -> dict:
    """Execute a real ML-KEM handshake and account for its cost on the link."""
    rng = (lambda n: hashlib.shake_256(f"{seed}".encode()).digest(n)) if seed is not None else os.urandom
    link = LinkBudget(link_rate, ber, fragment_bytes)
    out = handshake_time(kem, link, role)
    if kem.startswith("ML-KEM"):
        k = mlkem.MLKEM(kem)
        ek, dk = k.keygen(rng)
        nc, ns = rng(16), rng(16)
        ss_ap, ct = k.encaps(ek, rng)
        ss_node = k.decaps(dk, ct)
        out["agreed"] = ss_ap == ss_node
        out["session_key"] = derive_session_key(ss_node, nc, ns, ek, ct)
        out["bytes_total"] = len(ek) + len(ct)
    else:
        out["agreed"] = None
    return out


def derive_session_key(shared_secret: bytes, nc: bytes, ns: bytes,
                       ek: bytes, ct: bytes, length: int = 32) -> bytes:
    """SK = SHAKE256(K || Nc || Ns || H(transcript)).

    Binding the transcript follows SP 800-227 Sec. 5.2: the KEM shared secret
    alone does not authenticate the exchange.
    """
    transcript = hashlib.sha3_256(ek + ct).digest()
    return hashlib.shake_256(shared_secret + nc + ns + transcript).digest(length)
