#!/usr/bin/env python3
"""Experiment 1 - cost of the post-quantum handshake over the Li-Fi link.

Sweeps the link rate for each KEM and reports airtime, node computation,
total handshake time and the rate at which the two are equal.  Also compares
the two role assignments (node generates the key pair, or the access point
does) and verifies that ML-KEM handshakes really complete over the modelled
link by running the actual FIPS 203 algorithms.

Outputs results/handshake_rate.csv, results/handshake_summary.csv and
results/handshake_roles.csv.
"""
from __future__ import annotations

import argparse
import csv
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from vlckem import handshake as hs, link as lnk  # noqa: E402

RES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "results")
KEMS = ["X25519", "ML-KEM-512", "ML-KEM-768", "ML-KEM-1024",
        "BIKE-L1", "HQC-128", "Classic McEliece-348864"]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ber", type=float, default=1e-5)
    ap.add_argument("--fragment", type=int, default=128)
    args = ap.parse_args()

    rates = np.logspace(4, 7, 61)        # 10 kbit/s to 10 Mbit/s
    rows = []
    for kem in KEMS:
        for r in rates:
            link = hs.LinkBudget(float(r), args.ber, args.fragment)
            d = hs.handshake_time(kem, link)
            rows.append({"kem": kem, "rate_bps": float(r), **{
                k: d[k] for k in ("t_air", "t_cpu", "t_total", "air_fraction")}})
    with open(os.path.join(RES, "handshake_rate.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader(); w.writerows(rows)

    # Summary at three representative link rates, plus the crossover rate.
    cfg = lnk.OFDMConfig()
    ref = hs.LinkBudget(100e3, args.ber, args.fragment)
    summary = []
    for kem in KEMS:
        b = hs.handshake_bytes(kem)
        row = {"kem": kem, "level": hs.KEM_SIZES[kem]["level"],
               "ek_bytes": hs.KEM_SIZES[kem]["ek"], "ct_bytes": hs.KEM_SIZES[kem]["ct"],
               "total_bytes": b["total"],
               "ofdm_symbols": int(np.ceil(8 * b["total"] / cfg.bits_per_symbol)),
               "t_cpu_ms": 1e3 * hs.mcu_time(kem),
               "energy_mJ": 1e3 * hs.mcu_time(kem) * hs.MCU_ACTIVE_W,
               "crossover_kbps": hs.crossover_rate(kem, ref) / 1e3}
        for r, tag in ((10e3, "10k"), (100e3, "100k"), (400e3, "400k"), (10e6, "10M")):
            d = hs.handshake_time(kem, hs.LinkBudget(r, args.ber, args.fragment))
            row[f"t_air_ms_{tag}"] = 1e3 * d["t_air"]
            row[f"t_total_ms_{tag}"] = 1e3 * d["t_total"]
        summary.append(row)
        print(f"{kem:26s} {b['total']:>7d} B  cpu {row['t_cpu_ms']:8.1f} ms  "
              f"air@100k {row['t_air_ms_100k']:9.1f} ms  crossover "
              f"{row['crossover_kbps']:8.1f} kbit/s")
    with open(os.path.join(RES, "handshake_summary.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(summary[0]))
        w.writeheader(); w.writerows(summary)

    # Role comparison: who generates the ephemeral key pair?
    roles = []
    for kem in KEMS:
        for role in ("node-keygen", "ap-keygen"):
            for r in (100e3, 400e3):
                d = hs.handshake_time(kem, hs.LinkBudget(r, args.ber, args.fragment), role)
                roles.append({"kem": kem, "role": role, "rate_bps": r,
                              "uplink_bytes": hs.handshake_bytes(kem, role)["uplink"],
                              "t_cpu_ms": 1e3 * d["t_cpu"],
                              "t_total_ms": 1e3 * d["t_total"],
                              "energy_mJ": d["energy_mJ"]})
    with open(os.path.join(RES, "handshake_roles.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(roles[0]))
        w.writeheader(); w.writerows(roles)

    # End-to-end check with the real FIPS 203 algorithms.
    print()
    for kem in ("ML-KEM-512", "ML-KEM-768", "ML-KEM-1024"):
        out = hs.run_handshake(kem, 100e3, args.ber, args.fragment, seed=1)
        print(f"{kem}: shared secret agreed = {out['agreed']}, "
              f"{out['bytes_total']} B on air, session key "
              f"{out['session_key'][:8].hex()}...")
    print(f"wrote {RES}/handshake_*.csv")


if __name__ == "__main__":
    main()
