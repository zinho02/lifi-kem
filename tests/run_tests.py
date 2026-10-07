"""Self-contained test suite (run: python3 tests/run_tests.py [--full]).

--full also runs the 10 000-iteration C2SP accumulated ML-KEM-768 vector,
which takes about a minute.
"""
from __future__ import annotations

import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from vlckem import handshake, link as lnk, mlkem, modulation as mod, optics  # noqa: E402

FAILURES: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    print(f"  {'PASS' if cond else 'FAIL'}  {name}{'  -- ' + detail if detail else ''}")
    if not cond:
        FAILURES.append(name)


# ------------------------------------------------------------------ primitives
def test_mlkem() -> None:
    print("ML-KEM (FIPS 203)")
    for name, p in mlkem.PARAMS.items():
        k = mlkem.MLKEM(name)
        ek, dk = k.keygen()
        ss, ct = k.encaps(ek)
        check(f"{name} sizes",
              len(ek) == p.ek_bytes and len(dk) == p.dk_bytes and len(ct) == p.ct_bytes,
              f"ek={len(ek)} ct={len(ct)}")
        check(f"{name} round-trip", k.decaps(dk, ct) == ss)
        bad = bytearray(ct); bad[0] ^= 1
        check(f"{name} implicit rejection", k.decaps(dk, bytes(bad)) != ss)
    # A ciphertext of the wrong length must be rejected outright.
    k = mlkem.MLKEM("ML-KEM-512")
    ek, dk = k.keygen()
    try:
        k.decaps(dk, b"\x00" * 10)
        ok = False
    except ValueError:
        ok = True
    check("short ciphertext raises", ok)
    # Modulus check of FIPS 203 Sec. 7.2.
    bad_ek = bytearray(ek); bad_ek[0] = 0xFF; bad_ek[1] = 0xFF
    check("malformed encapsulation key rejected", not mlkem.ek_check(k.p, bytes(bad_ek)))
    print("  (run with --full for the 10 000-iteration C2SP accumulated vector)")


def test_mlkem_accumulated() -> None:
    print("ML-KEM accumulated vector (C2SP/CCTV)")
    from accumulated_mlkem768 import EXPECTED_10000, run
    check("ML-KEM-768, 10 000 iterations", run(10000) == EXPECTED_10000)


# ----------------------------------------------------------------- phy helpers
def test_constellations() -> None:
    print("Constellations")
    for M in (16, 32, 64, 256):
        c = mod.constellation(M)
        check(f"{M}-QAM unit energy", abs(np.mean(np.abs(c) ** 2) - 1) < 1e-12)
        check(f"{M}-QAM points distinct", len(np.unique(np.round(c, 9))) == M)
        sym = np.arange(M)
        check(f"{M}-QAM noiseless detection", np.array_equal(mod.detect(c[sym], M), sym))
    d, nbar, h = mod.neighbour_stats(32)
    check("32-cross has 3.25 mean nearest neighbours", abs(nbar - 3.25) < 1e-9)
    check("32-cross labelling is near-Gray", h < 1.2, f"mean NN Hamming = {h:.3f}")


def test_optics() -> None:
    print("Optics")
    room = optics.Room()
    # m = -ln2 / ln cos(Phi_1/2): 0.65 at 70 deg, 1.0 at 60 deg
    check("Lambertian order for a 70 deg semi-angle",
          abs(room.m - 0.6461) < 1e-3, f"m = {room.m:.3f}")
    check("Lambertian order for a 60 deg semi-angle",
          abs(optics.Room(semi_angle_deg=60.0).m - 1.0) < 1e-9)
    h0 = optics.los_gain(room, 0, 0)
    hc = optics.los_gain(room, 2.5, 2.5)
    check("gain decreases away from the centre", hc < h0)
    check("SNR at the centre equals the reference",
          abs(optics.snr_db(room, 0, 0, 25.0) - 25.0) < 1e-9)
    check("a narrow FOV blanks distant receivers",
          optics.los_gain(room, 2.5, 2.5, fov_deg=20.0) == 0.0)


def test_link() -> None:
    print("Link")
    cfg = lnk.OFDMConfig()
    check("1275 bits per OFDM symbol", cfg.bits_per_symbol == 1275)
    check("255 data subcarriers", cfg.n_data == 255)
    check("ML-KEM-512 fits in 10 OFDM symbols", lnk.symbols_for(1568) == 10)
    check("BER falls as SNR rises",
          lnk.ber_at_snr(25.0) < lnk.ber_at_snr(15.0) < lnk.ber_at_snr(5.0))
    check("BER at 15 dB matches the closed form",
          abs(float(lnk.ber_at_snr(15.0)) - 2.87e-2) < 1e-3,
          f"{float(lnk.ber_at_snr(15.0)):.3e}")


def test_handshake() -> None:
    print("Handshake over the optical link")
    res = handshake.run_handshake("ML-KEM-512", link_rate=100e3, ber=1e-5,
                                  fragment_bytes=128, seed=5)
    check("shared secrets agree", res["agreed"])
    check("handshake bytes match FIPS 203", res["bytes_total"] == 800 + 768)
    check("airtime is positive and finite", 0 < res["t_air"] < 10)
    slow = handshake.run_handshake("ML-KEM-512", link_rate=10e3, ber=1e-5, seed=5)
    check("airtime scales inversely with rate",
          abs(slow["t_air"] / res["t_air"] - 10) < 0.5)
    noisy = handshake.expected_transmissions(1568, 128, 1e-3)
    clean = handshake.expected_transmissions(1568, 128, 0.0)
    check("a noisy link needs more fragment transmissions", noisy > clean * 1.5,
          f"{noisy:.1f} vs {clean:.0f}")


def main() -> None:
    full = "--full" in sys.argv
    test_mlkem()
    if full:
        test_mlkem_accumulated()
    test_constellations()
    test_optics()
    test_link()
    test_handshake()
    print()
    if FAILURES:
        print(f"{len(FAILURES)} FAILED: {', '.join(FAILURES)}")
        sys.exit(1)
    print("all tests passed")


if __name__ == "__main__":
    main()
