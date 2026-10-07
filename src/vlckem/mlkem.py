"""ML-KEM (FIPS 203) in Python/NumPy, written for simulation and teaching.

This module follows the algorithm numbering of FIPS 203 (August 2024):
KeyGen_internal (Alg. 16), Encaps_internal (Alg. 17), Decaps_internal (Alg. 18)
and the K-PKE component (Algs. 13-15).  It is validated against the C2SP/CCTV
"accumulated" ML-KEM-768 vector (see tests/test_mlkem.py).

WARNING: this code is NOT constant time and must never be used to protect real
data.  It exists so that the simulator can move real encapsulation keys and
ciphertexts over a simulated optical link and check that both ends derive the
same shared secret.
"""
from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass

import numpy as np

Q = 3329
N = 256


@dataclass(frozen=True)
class MLKEMParams:
    name: str
    k: int
    eta1: int
    eta2: int
    du: int
    dv: int

    @property
    def ek_bytes(self) -> int:
        return 384 * self.k + 32

    @property
    def dk_bytes(self) -> int:
        return 768 * self.k + 96

    @property
    def ct_bytes(self) -> int:
        return 32 * (self.du * self.k + self.dv)


ML_KEM_512 = MLKEMParams("ML-KEM-512", 2, 3, 2, 10, 4)
ML_KEM_768 = MLKEMParams("ML-KEM-768", 3, 2, 2, 10, 4)
ML_KEM_1024 = MLKEMParams("ML-KEM-1024", 4, 2, 2, 11, 5)
PARAMS = {p.name: p for p in (ML_KEM_512, ML_KEM_768, ML_KEM_1024)}


def _bitrev7(x: int) -> int:
    return int(f"{x:07b}"[::-1], 2)


ZETAS = np.array([pow(17, _bitrev7(i), Q) for i in range(128)], dtype=np.int64)
GAMMAS = np.array([pow(17, 2 * _bitrev7(i) + 1, Q) for i in range(128)], dtype=np.int64)

# --------------------------------------------------------------- hash functions
def H(s: bytes) -> bytes:
    return hashlib.sha3_256(s).digest()


def J(s: bytes) -> bytes:
    return hashlib.shake_256(s).digest(32)


def G(c: bytes) -> tuple[bytes, bytes]:
    d = hashlib.sha3_512(c).digest()
    return d[:32], d[32:]


def PRF(eta: int, s: bytes, b: int) -> bytes:
    return hashlib.shake_256(s + bytes([b])).digest(64 * eta)


# ------------------------------------------------------------ number theoretic
def ntt(f: np.ndarray) -> np.ndarray:
    """Algorithm 9, vectorised over any leading dimensions."""
    f = np.array(f, dtype=np.int64, copy=True)
    lead = f.shape[:-1]
    i, length = 1, 128
    while length >= 2:
        nb = N // (2 * length)
        z = ZETAS[i:i + nb][:, None]
        i += nb
        v = f.reshape(lead + (nb, 2, length))
        a, b = v[..., 0, :], v[..., 1, :]
        t = (z * b) % Q
        f = np.stack(((a + t) % Q, (a - t) % Q), axis=-2).reshape(lead + (N,))
        length //= 2
    return f


def intt(f: np.ndarray) -> np.ndarray:
    """Algorithm 10."""
    f = np.array(f, dtype=np.int64, copy=True)
    lead = f.shape[:-1]
    i, length = 127, 2
    while length <= 128:
        nb = N // (2 * length)
        z = ZETAS[i - nb + 1:i + 1][::-1][:, None]
        i -= nb
        v = f.reshape(lead + (nb, 2, length))
        a, b = v[..., 0, :], v[..., 1, :]
        f = np.stack(((a + b) % Q, (z * (b - a)) % Q), axis=-2).reshape(lead + (N,))
        length *= 2
    return (f * 3303) % Q


def mul_ntt(f: np.ndarray, g: np.ndarray) -> np.ndarray:
    """Algorithms 11-12 (MultiplyNTTs / BaseCaseMultiply), broadcasting."""
    a0, a1 = f[..., 0::2], f[..., 1::2]
    b0, b1 = g[..., 0::2], g[..., 1::2]
    c0 = (a0 * b0 + ((a1 * b1) % Q) * GAMMAS) % Q
    c1 = (a0 * b1 + a1 * b0) % Q
    out = np.empty(np.broadcast_shapes(f.shape, g.shape), dtype=np.int64)
    out[..., 0::2], out[..., 1::2] = c0, c1
    return out


# ------------------------------------------------------------- encode / decode
def byte_encode(F: np.ndarray, d: int) -> bytes:
    """Algorithm 5 for one or more polynomials (concatenated)."""
    F = np.asarray(F, dtype=np.int64).reshape(-1, N)
    bits = ((F[..., None] >> np.arange(d)) & 1).astype(np.uint8).reshape(-1)
    return np.packbits(bits, bitorder="little").tobytes()


def byte_decode(B: bytes, d: int, count: int = 1) -> np.ndarray:
    """Algorithm 6; returns shape (count, 256)."""
    bits = np.unpackbits(np.frombuffer(B, dtype=np.uint8), bitorder="little")
    bits = bits.reshape(count, N, d).astype(np.int64)
    F = (bits << np.arange(d)).sum(axis=-1)
    return F % Q if d == 12 else F


def compress(x: np.ndarray, d: int) -> np.ndarray:
    return ((x.astype(np.int64) << (d + 1)) + Q) // (2 * Q) % (1 << d)


def decompress(y: np.ndarray, d: int) -> np.ndarray:
    return (y.astype(np.int64) * Q + (1 << (d - 1))) >> d


# -------------------------------------------------------------------- sampling
def sample_ntt(seed34: bytes) -> np.ndarray:
    """Algorithm 7 (rejection sampling from SHAKE128)."""
    n = 840
    while True:
        buf = np.frombuffer(hashlib.shake_128(seed34).digest(n), dtype=np.uint8).astype(np.int64)
        c = buf[: (n // 3) * 3].reshape(-1, 3)
        d1 = c[:, 0] + 256 * (c[:, 1] & 15)
        d2 = (c[:, 1] >> 4) + 16 * c[:, 2]
        cand = np.stack((d1, d2), axis=1).reshape(-1)
        good = cand[cand < Q]
        if good.size >= N:
            return good[:N]
        n *= 2


def sample_cbd(B: bytes, eta: int) -> np.ndarray:
    """Algorithm 8."""
    bits = np.unpackbits(np.frombuffer(B, dtype=np.uint8), bitorder="little").reshape(N, 2 * eta)
    x = bits[:, :eta].sum(axis=1).astype(np.int64)
    y = bits[:, eta:].sum(axis=1).astype(np.int64)
    return (x - y) % Q


def _matrix_A(rho: bytes, k: int) -> np.ndarray:
    return np.array([[sample_ntt(rho + bytes([j, i])) for j in range(k)] for i in range(k)])


# ----------------------------------------------------------------------- K-PKE
def kpke_keygen(p: MLKEMParams, d: bytes) -> tuple[bytes, bytes]:
    rho, sigma = G(d + bytes([p.k]))
    A = _matrix_A(rho, p.k)
    s = np.array([sample_cbd(PRF(p.eta1, sigma, i), p.eta1) for i in range(p.k)])
    e = np.array([sample_cbd(PRF(p.eta1, sigma, p.k + i), p.eta1) for i in range(p.k)])
    s_hat, e_hat = ntt(s), ntt(e)
    t_hat = (mul_ntt(A, s_hat[None, :, :]).sum(axis=1) + e_hat) % Q
    return byte_encode(t_hat, 12) + rho, byte_encode(s_hat, 12)


def kpke_encrypt(p: MLKEMParams, ek: bytes, m: bytes, r: bytes) -> bytes:
    k = p.k
    t_hat = byte_decode(ek[:384 * k], 12, k)
    A = _matrix_A(ek[384 * k:384 * k + 32], k)
    y = np.array([sample_cbd(PRF(p.eta1, r, i), p.eta1) for i in range(k)])
    e1 = np.array([sample_cbd(PRF(p.eta2, r, k + i), p.eta2) for i in range(k)])
    e2 = sample_cbd(PRF(p.eta2, r, 2 * k), p.eta2)
    y_hat = ntt(y)
    u = (intt(mul_ntt(A.transpose(1, 0, 2), y_hat[None, :, :]).sum(axis=1) % Q) + e1) % Q
    mu = decompress(byte_decode(m, 1)[0], 1)
    v = (intt(mul_ntt(t_hat, y_hat).sum(axis=0) % Q) + e2 + mu) % Q
    return byte_encode(compress(u, p.du), p.du) + byte_encode(compress(v, p.dv), p.dv)


def kpke_decrypt(p: MLKEMParams, dk: bytes, c: bytes) -> bytes:
    k = p.k
    c1, c2 = c[:32 * p.du * k], c[32 * p.du * k:]
    u = decompress(byte_decode(c1, p.du, k), p.du)
    v = decompress(byte_decode(c2, p.dv)[0], p.dv)
    s_hat = byte_decode(dk, 12, k)
    w = (v - intt(mul_ntt(s_hat, ntt(u)).sum(axis=0) % Q)) % Q
    return byte_encode(compress(w, 1), 1)


# ---------------------------------------------------------------------- ML-KEM
def keygen_internal(p: MLKEMParams, d: bytes, z: bytes) -> tuple[bytes, bytes]:
    ek, dk_pke = kpke_keygen(p, d)
    return ek, dk_pke + ek + H(ek) + z


def encaps_internal(p: MLKEMParams, ek: bytes, m: bytes) -> tuple[bytes, bytes]:
    K, r = G(m + H(ek))
    return K, kpke_encrypt(p, ek, m, r)


def decaps_internal(p: MLKEMParams, dk: bytes, c: bytes) -> bytes:
    k = p.k
    dk_pke = dk[:384 * k]
    ek_pke = dk[384 * k:768 * k + 32]
    h = dk[768 * k + 32:768 * k + 64]
    z = dk[768 * k + 64:768 * k + 96]
    m_ = kpke_decrypt(p, dk_pke, c)
    K_, r_ = G(m_ + h)
    K_bar = J(z + c)
    c_ = kpke_encrypt(p, ek_pke, m_, r_)
    return K_ if c_ == c else K_bar


def ek_check(p: MLKEMParams, ek: bytes) -> bool:
    """Input check of FIPS 203 Sec. 7.2 (type and modulus check)."""
    if len(ek) != p.ek_bytes:
        return False
    t = byte_decode(ek[:384 * p.k], 12, p.k)
    return byte_encode(t, 12) == ek[:384 * p.k]


class MLKEM:
    """Convenience wrapper with the public API of FIPS 203 (Algs. 19-21)."""

    def __init__(self, name: str = "ML-KEM-768"):
        self.p = PARAMS[name]

    def keygen(self, rng=os.urandom) -> tuple[bytes, bytes]:
        return keygen_internal(self.p, rng(32), rng(32))

    def encaps(self, ek: bytes, rng=os.urandom) -> tuple[bytes, bytes]:
        if not ek_check(self.p, ek):
            raise ValueError("encapsulation key failed the FIPS 203 input check")
        return encaps_internal(self.p, ek, rng(32))

    def decaps(self, dk: bytes, c: bytes) -> bytes:
        if len(c) != self.p.ct_bytes or len(dk) != self.p.dk_bytes:
            raise ValueError("wrong ciphertext or decapsulation-key length")
        return decaps_internal(self.p, dk, c)
