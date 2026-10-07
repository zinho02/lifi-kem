"""QAM constellations, hard detection and closed-form error-rate expressions.

Symbols are integers s in [0, M); ``const[s]`` is the complex point carrying
the log2(M) label bits of s.  Square constellations use per-axis Gray coding;
32-QAM uses the classic cross constellation obtained by folding the outer
columns of a Gray-coded 8x4 rectangle, with the fold chosen to minimise the
average Hamming distance between nearest neighbours.
"""
from __future__ import annotations

from functools import lru_cache
from itertools import permutations

import numpy as np
from scipy.special import erfc
from scipy.stats import norm


def _gray(i: int) -> int:
    return i ^ (i >> 1)


def _pam(levels: int):
    """Gray-coded PAM: returns amplitude for each label value."""
    amp = np.empty(levels)
    for idx in range(levels):
        amp[_gray(idx)] = 2 * idx - (levels - 1)
    return amp


@lru_cache(maxsize=None)
def constellation(M: int) -> np.ndarray:
    """Unit-average-energy constellation indexed by symbol label."""
    if M == 32:
        pts = _cross32()
    else:
        L = int(round(np.sqrt(M)))
        if L * L != M:
            raise ValueError("M must be a square or 32")
        b = int(np.log2(L))
        amp = _pam(L)
        s = np.arange(M)
        pts = amp[s >> b] + 1j * amp[s & (L - 1)]
    return pts / np.sqrt(np.mean(np.abs(pts) ** 2))


_HAM32 = None


def _nn_hamming(pts: np.ndarray, ham: np.ndarray) -> float:
    d = np.abs(pts[:, None] - pts[None, :])
    dmin = np.min(d[d > 1e-9])
    nn = np.isclose(d, dmin)
    return float(ham[nn].mean())


def _cross32() -> np.ndarray:
    """Fold the |x| = 7 columns of a Gray 8x4 rectangle into the y = +-5 rows.

    Points with y > 0 move to the top row and points with y < 0 to the bottom
    row; among the 4! x 4! assignments we keep the one with the smallest mean
    nearest-neighbour Hamming distance (quasi-Gray labelling).
    """
    ampx, ampy = _pam(8), _pam(4)
    s = np.arange(32)
    base = ampx[s >> 2] + 1j * ampy[s & 3]
    lab = np.arange(32, dtype=np.uint32)
    x = lab[:, None] ^ lab[None, :]
    ham = np.array([[bin(int(v)).count("1") for v in row] for row in x])
    up = [i for i in range(32) if abs(base[i].real) == 7 and base[i].imag > 0]
    dn = [i for i in range(32) if abs(base[i].real) == 7 and base[i].imag < 0]
    top = [complex(v, 5) for v in (-3, -1, 1, 3)]
    bot = [complex(v, -5) for v in (-3, -1, 1, 3)]
    best, best_pts = None, None
    for pu in permutations(range(4)):
        for pd in permutations(range(4)):
            pts = base.copy()
            for mv, sl in zip(up, pu):
                pts[mv] = top[sl]
            for mv, sl in zip(dn, pd):
                pts[mv] = bot[sl]
            score = _nn_hamming(pts, ham)
            if best is None or score < best - 1e-12:
                best, best_pts = score, pts
    return best_pts


def detect(y: np.ndarray, M: int) -> np.ndarray:
    c = constellation(M)
    return np.argmin(np.abs(y[..., None] - c) ** 2, axis=-1)


def popcount(x: np.ndarray) -> np.ndarray:
    x = np.asarray(x, dtype=np.uint32)
    return np.unpackbits(x.view(np.uint8)).reshape(x.shape + (32,)).sum(-1)


@lru_cache(maxsize=None)
def neighbour_stats(M: int) -> tuple[float, float, float]:
    """(d_min, mean number of nearest neighbours, mean NN Hamming distance)."""
    c = constellation(M)
    d = np.abs(c[:, None] - c[None, :])
    dmin = np.min(d[d > 1e-9])
    nn = np.isclose(d, dmin)
    lab = np.arange(M)
    ham = popcount(lab[:, None] ^ lab[None, :])
    return float(dmin), float(nn.sum(1).mean()), float(ham[nn].mean())


def Qf(x):
    return 0.5 * erfc(np.asarray(x) / np.sqrt(2))


def ser_nn(snr_lin, M: int):
    """Nearest-neighbour approximation of the symbol error rate (Es/N0)."""
    dmin, nbar, _ = neighbour_stats(M)
    return np.minimum(1.0, nbar * Qf(dmin * np.sqrt(np.asarray(snr_lin) / 2)))


def ber_gray(snr_lin, M: int):
    """BER of the Gray-labelled constellation (each SE flips h_nn bits)."""
    _, _, hnn = neighbour_stats(M)
    return ser_nn(snr_lin, M) * hnn / np.log2(M)


def ber_random_label(snr_lin, M: int):
    """BER when a key-dependent S-box re-labels the points.

    A symbol error lands on a neighbour whose label is, after inverse
    substitution, uniformly distributed over the M-1 wrong labels, so on
    average M/(2(M-1)) of the bits are wrong.
    """
    return ser_nn(snr_lin, M) * M / (2 * (M - 1))


def bussgang_clip(lam: float) -> tuple[float, float]:
    """Gain alpha and clipping-noise variance for symmetric clipping at +-lam*sigma
    of a unit-variance Gaussian (cf. Dimitrov & Haas 2013; Al-Moliki 2022, Eq. 18)."""
    alpha = 1 - 2 * norm.sf(lam)
    ex2 = (1 - 2 * norm.sf(lam)) - 2 * lam * norm.pdf(lam) + 2 * lam ** 2 * norm.sf(lam)
    return float(alpha), float(ex2 - alpha ** 2)


def effective_snr(snr_lin, lam: float = 3.2, sig2: float = 510 / 512):
    alpha, var_c = bussgang_clip(lam)
    snr_lin = np.asarray(snr_lin, dtype=float)
    n0 = 1.0 / snr_lin
    return alpha ** 2 / (n0 + var_c * sig2)


def kmr_theory(snr_lin, sig2: float = 510 / 512):
    """Per-bit key mismatch rate of the cyclic-prefix key.

    The secret CP samples are replaced by +-A with A = E|s| = sigma sqrt(2/pi)
    (Al-Moliki 2022, Eq. 21), so a polarity error occurs with probability
    Q(A / sigma_n) (Eq. 25 with the explicit value of A)."""
    snr_lin = np.asarray(snr_lin, dtype=float)
    A = np.sqrt(sig2 * 2 / np.pi)
    return Qf(A * np.sqrt(snr_lin))
