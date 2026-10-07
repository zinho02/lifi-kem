#!/usr/bin/env python3
"""Experiment 2 - the handshake on an imperfect link.

Three sweeps:

  (a) expected fragment transmissions and completion time against the raw BER;
  (b) the fragment size that minimises completion time at each BER;
  (c) completion time against the receiver's position in the room, where the
      BER at each position comes from the DCO-OFDM model of Sec. III.

The handshake is carried before the session key exists, so it is transmitted
unencrypted: the relevant error rate is the Gray-labelled BER of the link.

Outputs results/arq_ber.csv, results/arq_fragment.csv, results/handshake_position.csv.
"""
from __future__ import annotations

import argparse
import csv
import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from vlckem import handshake as hs, link as lnk, optics  # noqa: E402

RES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "results")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rate", type=float, default=400e3,
                    help="link rate (default: the 400 kbit/s of OpenVLC1.3)")
    ap.add_argument("--snr-center", type=float, default=25.0)
    args = ap.parse_args()

    kems = ["ML-KEM-512", "ML-KEM-768", "HQC-128"]
    bers = np.logspace(-7, -2.5, 40)

    # (a) transmissions and time against BER
    rows = []
    for kem in kems:
        b = hs.handshake_bytes(kem)
        for ber in bers:
            link = hs.LinkBudget(args.rate, float(ber), 128)
            d = hs.handshake_time(kem, link)
            n_ideal = math.ceil(b["uplink"] / 128) + math.ceil(b["downlink"] / 128)
            tx = (hs.expected_transmissions(b["uplink"], 128, float(ber))
                  + hs.expected_transmissions(b["downlink"], 128, float(ber)))
            rows.append({"kem": kem, "ber": float(ber), "frags_ideal": n_ideal,
                         "frags_expected": tx, "overhead": tx / n_ideal,
                         "t_total_ms": 1e3 * d["t_total"]})
    with open(os.path.join(RES, "arq_ber.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)

    # (b) best fragment size
    frag_sizes = [16, 32, 64, 128, 256, 512, 1024]
    frows = []
    for ber in (1e-6, 1e-5, 1e-4, 1e-3):
        best, best_t = None, float("inf")
        for fb in frag_sizes:
            link = hs.LinkBudget(args.rate, ber, fb)
            t = hs.handshake_time("ML-KEM-512", link)["t_total"]
            frows.append({"ber": ber, "fragment_bytes": fb, "t_total_ms": 1e3 * t})
            if t < best_t:
                best, best_t = fb, t
        print(f"BER {ber:.0e}: best fragment = {best} B, {1e3 * best_t:.1f} ms")
    with open(os.path.join(RES, "arq_fragment.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(frows[0])); w.writeheader(); w.writerows(frows)

    # (c) completion time against position
    room = optics.Room()
    cfg = lnk.OFDMConfig()
    xs, _ = optics.grid(room, 41)
    prows = []
    for x in xs:
        snr = float(optics.snr_db(room, x, 0.0, args.snr_center))
        ber = float(lnk.ber_at_snr(snr, cfg))
        row = {"x": float(x), "snr_db": snr, "ber": ber}
        for kem in ("ML-KEM-512", "ML-KEM-768"):
            d = hs.handshake_time(kem, hs.LinkBudget(args.rate, ber, 128))
            row[f"t_total_ms_{kem}"] = 1e3 * d["t_total"]
        prows.append(row)
    with open(os.path.join(RES, "handshake_position.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(prows[0])); w.writeheader(); w.writerows(prows)

    centre = prows[len(prows) // 2]
    edge = prows[0]
    print(f"\nML-KEM-512 at {args.rate / 1e3:.0f} kbit/s: "
          f"{centre['t_total_ms_ML-KEM-512']:.1f} ms at the room centre "
          f"(BER {centre['ber']:.1e}) vs {edge['t_total_ms_ML-KEM-512']:.1f} ms at "
          f"x = {edge['x']:.2f} m (BER {edge['ber']:.1e})")
    print(f"wrote {RES}/arq_*.csv and {RES}/handshake_position.csv")


if __name__ == "__main__":
    main()
