"""DCO-OFDM link: how many bits a symbol carries and what BER a position sees.

This is the part of the physical layer the handshake actually needs.  The
handshake runs before any session key exists, so it travels unprotected and is
exposed to the raw bit-error rate of the link.

Parameters follow Al-Moliki et al., IEEE IoT-J 9(6):4661-4676, 2022.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from . import modulation as mod


@dataclass(frozen=True)
class OFDMConfig:
    N: int = 512               # IFFT size
    M: int = 32                # QAM order
    cp_total: int = 64         # cyclic prefix, samples
    clip_lambda: float = 3.2   # symmetric clipping level, in sigma

    @property
    def n_data(self) -> int:
        """Data-bearing subcarriers after Hermitian symmetry (DC and Nyquist null)."""
        return self.N // 2 - 1

    @property
    def bits_per_symbol(self) -> int:
        return self.n_data * int(np.log2(self.M))


def ber_at_snr(snr_db, cfg: OFDMConfig = OFDMConfig()):
    """Uncoded BER of the Gray-labelled constellation at a given electrical SNR."""
    eff = mod.effective_snr(10 ** (np.asarray(snr_db, dtype=float) / 10))
    return mod.ber_gray(eff, cfg.M)


def symbols_for(n_bytes: int, cfg: OFDMConfig = OFDMConfig()) -> int:
    """How many OFDM symbols a message of n_bytes occupies."""
    return int(np.ceil(8 * n_bytes / cfg.bits_per_symbol))
