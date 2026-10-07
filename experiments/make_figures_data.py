#!/usr/bin/env python3
"""Convert results/*.csv into the pgfplots-ready tables under paper/data/.

Every number that appears in the paper is produced here, so the figures and
tables cannot drift from the simulation output.  Also writes
paper/data/macros.tex with the scalar values quoted in the text.
"""
from __future__ import annotations

import csv
import os
import re
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(HERE, "..", "results")
OUT = os.path.join(HERE, "..", "paper", "data")
sys.path.insert(0, os.path.join(HERE, "..", "src"))
from vlckem import handshake as hs, link as lnk  # noqa: E402


def ptbr(text: str) -> str:
    """Brazilian number formatting for LaTeX: decimal comma instead of point.

    "3.10" becomes "3{,}10"; the braces stop TeX from adding a space after the
    comma in math mode, and are harmless in text mode.  Only a point between
    two digits is touched, so "10^{-3}" and file names are left alone.
    """
    return re.sub(r"(?<=\d)\.(?=\d)", "{,}", text)


def read(name):
    with open(os.path.join(RES, name)) as f:
        return list(csv.DictReader(f))


def write_table(name, rows, cols, fmt="%.6g"):
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, name)
    with open(path, "w") as f:
        f.write(" ".join(cols) + "\n")
        for r in rows:
            f.write(" ".join(
                (fmt % float(r[c])) if not isinstance(r[c], str) or _isnum(r[c])
                else str(r[c]) for c in cols) + "\n")
    print("wrote", path)


def _isnum(s):
    try:
        float(s); return True
    except (TypeError, ValueError):
        return False


def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    macros = {}

    # ------------------------------------------------------- Fig. handshake rate
    hr = read("handshake_rate.csv")
    kems = ["X25519", "ML-KEM-512", "ML-KEM-768", "ML-KEM-1024", "HQC-128",
            "BIKE-L1"]
    rates = sorted({float(r["rate_bps"]) for r in hr})
    rows = []
    for rate in rates:
        row = {"rate_kbps": rate / 1e3}
        for k in kems:
            rec = next(r for r in hr if r["kem"] == k and float(r["rate_bps"]) == rate)
            row[k.replace("-", "")] = 1e3 * float(rec["t_total"])
            row[k.replace("-", "") + "air"] = 1e3 * float(rec["t_air"])
        rows.append(row)
    cols = ["rate_kbps"] + [k.replace("-", "") for k in kems] + \
           [k.replace("-", "") + "air" for k in kems]
    write_table("handshake_rate.dat", rows, cols)

    summ = read("handshake_summary.csv")
    write_table("handshake_summary.dat", summ,
                ["ek_bytes", "ct_bytes", "total_bytes", "ofdm_symbols", "t_cpu_ms",
                 "energy_mJ", "crossover_kbps", "t_air_ms_100k", "t_total_ms_100k",
                 "t_total_ms_400k"])
    for r in summ:
        tag = r["kem"].replace("-", "").replace(" ", "")
        macros[tag + "Bytes"] = r["total_bytes"]
        macros[tag + "Cpu"] = f"{float(r['t_cpu_ms']):.1f}"
        macros[tag + "Cross"] = f"{float(r['crossover_kbps']) / 1e3:.2f}"
        macros[tag + "Air100k"] = f"{float(r['t_air_ms_100k']):.0f}"
        macros[tag + "Symbols"] = r["ofdm_symbols"]
        # Unformatted copies, for use as plot coordinates (names end in "Raw").
        macros[tag + "CrossKbpsRaw"] = f"{float(r['crossover_kbps']):.0f}"
        macros[tag + "CpuRaw"] = f"{float(r['t_cpu_ms']):.3f}"
        # English-format copy, for the abstract in English (names end in "En").
        macros[tag + "CrossEn"] = macros[tag + "Cross"]

    # ------------------------------------------------------------- Fig. ARQ / xy
    arq = read("arq_ber.csv")
    bers = sorted({float(r["ber"]) for r in arq})
    rows = []
    for b in bers:
        row = {"ber": b}
        for k in ("ML-KEM-512", "ML-KEM-768", "HQC-128"):
            rec = next(r for r in arq if r["kem"] == k and float(r["ber"]) == b)
            row[k.replace("-", "")] = float(rec["t_total_ms"])
            row[k.replace("-", "") + "ovh"] = float(rec["overhead"])
        rows.append(row)
    write_table("arq_ber.dat", rows, ["ber"] + [k.replace("-", "") for k in
                ("ML-KEM-512", "ML-KEM-768", "HQC-128")] +
                [k.replace("-", "") + "ovh" for k in ("ML-KEM-512", "ML-KEM-768", "HQC-128")])

    pos = read("handshake_position.csv")
    write_table("handshake_position.dat", pos,
                ["x", "snr_db", "ber", "t_total_ms_ML-KEM-512", "t_total_ms_ML-KEM-768"])
    centre = min(pos, key=lambda r: abs(float(r["x"])))
    edge = min(pos, key=lambda r: float(r["x"]))
    macros["PosCentreMs"] = f"{float(centre['t_total_ms_ML-KEM-512']):.0f}"
    macros["PosEdgeMs"] = f"{float(edge['t_total_ms_ML-KEM-512']):.0f}"
    macros["PosEdgeS"] = f"{float(edge['t_total_ms_ML-KEM-512']) / 1e3:.1f}"
    macros["PosCentreBerExp"] = f"{round(np.log10(float(centre['ber']))):d}"
    macros["PosRatio"] = f"{float(edge['t_total_ms_ML-KEM-512']) / float(centre['t_total_ms_ML-KEM-512']):.0f}"
    m, e = f"{float(edge['ber']):.1e}".split("e")
    macros["PosCentreSnr"] = f"{float(centre['snr_db']):.0f}"
    macros["PosEdgeSnr"] = f"{float(edge['snr_db']):.1f}"
    macros["PosSnrDrop"] = f"{float(centre['snr_db']) - float(edge['snr_db']):.1f}"
    macros["PosEdgeBer"] = f"{m}\\times 10^{{{int(e)}}}"

    frag = read("arq_fragment.csv")
    fb = sorted({int(r["fragment_bytes"]) for r in frag})
    rows = []
    for f_ in fb:
        row = {"fragment_bytes": f_}
        for b in (1e-6, 1e-5, 1e-4, 1e-3):
            rec = next(r for r in frag if int(r["fragment_bytes"]) == f_
                       and abs(float(r["ber"]) - b) < 1e-12)
            row[f"b{int(-np.log10(b))}"] = float(rec["t_total_ms"])
        rows.append(row)
    write_table("arq_fragment.dat", rows, ["fragment_bytes", "b6", "b5", "b4", "b3"])

    # LaTeX table for the fragment sweep, generated so it cannot drift.
    bers = ["b6", "b5", "b4", "b3"]
    best = {b: min(rows, key=lambda r: r[b])["fragment_bytes"] for b in bers}
    lines = ["% Generated by experiments/make_figures_data.py - do not edit.",
             "\\begin{tabular}{lrrrr}", "\\toprule",
             "fragmento & \\multicolumn{4}{c}{BER do enlace}\\\\",
             "\\cmidrule(l){2-5}",
             "(bytes) & $10^{-6}$ & $10^{-5}$ & $10^{-4}$ & $10^{-3}$\\\\",
             "\\midrule"]
    for r in rows:
        cells = []
        for b in bers:
            v = r[b]
            txt = f"{v:.1f}" if v < 1e4 else f"{v/1e3:.1f}\\,s"
            cells.append(f"\\textbf{{{txt}}}" if best[b] == r["fragment_bytes"] else txt)
        lines.append(f"${r['fragment_bytes']}$ & " + " & ".join(cells) + " \\\\")
    lines += ["\\bottomrule", "\\end{tabular}"]
    with open(os.path.join(OUT, "table_frag.tex"), "w") as f:
        f.write(ptbr("\n".join(lines)) + "\n")
    print("wrote", os.path.join(OUT, "table_frag.tex"))
    macros["FragBestClean"] = str(best["b6"])
    macros["FragBestNoisy"] = str(best["b3"])
    b3 = {r["fragment_bytes"]: r["b3"] for r in rows}
    macros["FragFixedPenalty"] = f"{100 * (b3[128] / min(b3.values()) - 1):.0f}"
    macros["FragKiloPenalty"] = f"{b3[1024] / min(b3.values()):.0f}"

    # -------------------------------------------------------------- misc. macros
    cfg = lnk.OFDMConfig()
    macros["BitsPerSymbol"] = str(cfg.bits_per_symbol)
    macros["DataSubcarriers"] = str(cfg.n_data)
    roles = read("handshake_roles.csv")
    r_node = next(r for r in roles if r["kem"] == "ML-KEM-512"
                  and r["role"] == "node-keygen" and float(r["rate_bps"]) == 400e3)
    r_ap = next(r for r in roles if r["kem"] == "ML-KEM-512"
                and r["role"] == "ap-keygen" and float(r["rate_bps"]) == 400e3)
    macros["RoleNodeCpu"] = f"{float(r_node['t_cpu_ms']):.1f}"
    macros["RoleApCpu"] = f"{float(r_ap['t_cpu_ms']):.1f}"
    macros["RoleNodeUp"] = r_node["uplink_bytes"]
    macros["RoleApUp"] = r_ap["uplink_bytes"]
    macros["RoleSaving"] = f"{100 * (1 - float(r_ap['t_cpu_ms']) / float(r_node['t_cpu_ms'])):.0f}"

    # ------------------------------------------------- worked example (Table)
    # One ML-KEM-512 exchange at 100 kbit/s and BER 1e-5, step by step, so the
    # hand calculation in the paper is produced by the same code as the plots.
    kem, rate, ber = "ML-KEM-512", 100e3, 1e-5
    ex = hs.LinkBudget(rate, ber)
    size, cyc = hs.KEM_SIZES[kem], hs.MCU_CYCLES[kem]
    n_ek = -(-size["ek"] // ex.fragment_bytes)
    n_ct = -(-size["ct"] // ex.fragment_bytes)
    bits_frag = 8 * (ex.fragment_bytes + ex.header_bytes)
    bits_air = bits_frag + 8 * ex.ack_bytes
    p_ok = (1 - ber) ** bits_frag
    n_tx = (hs.expected_transmissions(size["ek"], ex.fragment_bytes, ber)
            + hs.expected_transmissions(size["ct"], ex.fragment_bytes, ber))
    d = hs.handshake_time(kem, ex)
    cross = hs.crossover_rate(kem, ex)
    thousands = lambda n: f"{n:,}".replace(",", "\\,")
    macros.update({
        "ExFragsEk": str(n_ek), "ExFragsCt": str(n_ct), "ExFrags": str(n_ek + n_ct),
        "ExBitsFrag": str(bits_frag), "ExBitsAir": str(bits_air),
        "ExFrameMs": f"{1e3 * bits_air / rate:.2f}",
        "ExSurvival": f"{p_ok:.3f}",
        "ExTx": f"{n_tx:.2f}",
        "ExRetxPct": f"{100 * (n_tx / (n_ek + n_ct) - 1):.0f}",
        "ExAirMs": f"{1e3 * d['t_air']:.1f}",
        "ExCycKeygen": thousands(cyc["keygen"]),
        "ExCycDecaps": thousands(cyc["decaps"]),
        "ExCyc": thousands(cyc["keygen"] + cyc["decaps"]),
        "ExTotalMs": f"{1e3 * d['t_total']:.1f}",
        "ExAirPct": f"{100 * d['air_fraction']:.0f}",
        "ExCpuPct": f"{100 * (1 - d['air_fraction']):.0f}",
        "ExSpeedup": f"{cross / rate:.0f}",
    })
    mc = next(r for r in summ if r["kem"].startswith("Classic"))
    macros["McElieceAirS"] = f"{float(mc['t_air_ms_100k']) / 1e3:.0f}"
    macros["McElieceEkKiB"] = f"{int(mc['ek_bytes']) // 1024}"
    macros["McElieceCt"] = mc["ct_bytes"]
    macros["BytesRatio"] = f"{int(next(r for r in summ if r['kem'] == 'ML-KEM-512')['total_bytes']) / int(next(r for r in summ if r['kem'] == 'X25519')['total_bytes']):.1f}"

    # LaTeX control sequences cannot contain digits, so the values are stored
    # under \csname and retrieved in the text with \val{Name}.
    with open(os.path.join(OUT, "macros.tex"), "w") as f:
        f.write("% Generated by experiments/make_figures_data.py - do not edit.\n")
        f.write("\\makeatletter\n")
        f.write("\\providecommand{\\val}[1]{%\n"
                "  \\ifcsname vlc@#1\\endcsname\\csname vlc@#1\\endcsname\n"
                "  \\else\\textbf{??#1??}\\fi}\n")
        for k, v in sorted(macros.items()):
            v = str(v) if k.endswith(("Raw", "En")) else ptbr(str(v))
            f.write(f"\\expandafter\\gdef\\csname vlc@{k}\\endcsname{{{v}}}\n")
        f.write("\\makeatother\n")
    print("wrote", os.path.join(OUT, "macros.tex"), f"({len(macros)} macros)")


if __name__ == "__main__":
    main()
