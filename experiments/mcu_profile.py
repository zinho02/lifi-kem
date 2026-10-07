#!/usr/bin/env python3
"""Recompute the paper's cost analysis from *measured* MCU timings.

The paper's compute floor uses published Cortex-M4 cycle counts.  If you have
a board, measure your own and rerun everything through this script:

    python3 experiments/mcu_profile.py --profile bench/my_esp32.csv \
            --clock 240e6 --power 0.132 --out results/handshake_summary_measured.csv

The profile CSV needs one row per KEM and operation:

    kem,operation,cycles            # or: kem,operation,time_ms
    ML-KEM-512,keygen,2436000
    ML-KEM-512,encaps,2301000
    ML-KEM-512,decaps,2570000

Either `cycles` (converted with --clock) or `time_ms` may be given; if both are
present, `time_ms` wins because it needs no clock assumption.

WHAT IS AND IS NOT COMPARABLE
  * Comparable: crossover rate, airtime, ARQ overhead, position dependence and
    the bytes-on-air columns.  These depend only on KEM sizes and the link, so
    measured compute slots straight in.
  * NOT comparable without care: cycle counts across architectures.  The paper
    uses Cortex-M4 (32-bit, DSP extensions).  An ESP32 is Xtensa LX6/LX7 with a
    different compiler back end, so do not present measured ESP32 numbers as an
    update of the paper's table -- add them as a separate column and say which
    chip, clock, toolchain, optimisation level and implementation produced them.
  * Especially not comparable: FIPS 203 ML-KEM against Kyber "90s".  ML-KEM
    uses SHAKE/SHA-3, which the ESP32 hardware accelerator does not implement;
    the 90s variant uses AES and SHA-2, which it does.  Published ESP32 Kyber
    speed-ups generally refer to the 90s variant.
"""
from __future__ import annotations

import argparse
import csv
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from vlckem import handshake as hs  # noqa: E402


def load_profile(path: str, clock_hz: float) -> dict[str, dict[str, float]]:
    """Return {kem: {op: seconds}} from a measurement CSV."""
    prof: dict[str, dict[str, float]] = {}
    with open(path) as f:
        for row in csv.DictReader(f):
            kem, op = row["kem"].strip(), row["operation"].strip().lower()
            if row.get("time_ms"):
                sec = float(row["time_ms"]) / 1e3
            elif row.get("cycles"):
                sec = float(row["cycles"]) / clock_hz
            else:
                raise ValueError(f"row for {kem}/{op} has neither cycles nor time_ms")
            prof.setdefault(kem, {})[op] = sec
    for kem, ops in prof.items():
        missing = {"keygen", "encaps", "decaps"} - set(ops)
        if missing:
            print(f"warning: {kem} is missing {sorted(missing)}; "
                  f"roles needing them will be skipped")
    return prof


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", required=True, help="measurement CSV")
    ap.add_argument("--clock", type=float, default=240e6,
                    help="MCU clock in Hz, used only for rows given in cycles")
    ap.add_argument("--power", type=float, default=hs.MCU_ACTIVE_W,
                    help="active power in W for the energy column")
    ap.add_argument("--ber", type=float, default=1e-5)
    ap.add_argument("--fragment", type=int, default=128)
    ap.add_argument("--rate", type=float, default=400e3)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    prof = load_profile(args.profile, args.clock)
    hs.MCU_ACTIVE_W = args.power

    rows = []
    print(f"{'KEM':<22}{'compute':>10}{'airtime':>10}{'total':>10}"
          f"{'crossover':>12}{'vs paper':>10}")
    print(f"{'':<22}{'(ms)':>10}{'(ms)':>10}{'(ms)':>10}{'(Mbit/s)':>12}{'':>10}")
    for kem, ops in sorted(prof.items()):
        if kem not in hs.KEM_SIZES:
            print(f"skipping unknown KEM {kem!r}")
            continue
        if not {"keygen", "decaps"} <= set(ops):
            continue
        t_cpu = ops["keygen"] + ops["decaps"]          # node-keygen role
        link = hs.LinkBudget(args.rate, args.ber, args.fragment)
        b = hs.handshake_bytes(kem)
        t_air = hs.airtime(b["uplink"], link) + hs.airtime(b["downlink"], link)
        cross = args.rate * t_air / t_cpu
        paper = hs.mcu_time(kem)
        rows.append({"kem": kem, "t_cpu_ms": 1e3 * t_cpu, "t_air_ms": 1e3 * t_air,
                     "t_total_ms": 1e3 * (t_cpu + t_air),
                     "crossover_kbps": cross / 1e3,
                     "energy_mJ": 1e3 * t_cpu * args.power,
                     "paper_t_cpu_ms": 1e3 * paper,
                     "ratio_measured_over_paper": t_cpu / paper})
        print(f"{kem:<22}{1e3*t_cpu:>10.1f}{1e3*t_air:>10.1f}"
              f"{1e3*(t_cpu+t_air):>10.1f}{cross/1e3:>12.2f}"
              f"{t_cpu/paper:>9.2f}x")

    if rows:
        out = args.out or os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                       "..", "results", "handshake_summary_measured.csv")
        os.makedirs(os.path.dirname(out), exist_ok=True)
        with open(out, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]))
            w.writeheader(); w.writerows(rows)
        print(f"\nwrote {out}")
        print("The 'vs paper' column is the ratio of your measurement to the "
              "Cortex-M4 figure used in the paper.\nReport it as a separate "
              "column, not as a replacement: the architectures differ.")


if __name__ == "__main__":
    main()
