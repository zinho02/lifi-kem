"""Indoor VLC geometry (Lambertian line-of-sight model).

The DC gain of a LOS link is (Kahn & Barry 1997; Komine & Nakagawa 2004)

    h = (m+1) A_pd / (2 pi d^2) cos^m(phi) cos(psi),   0 <= psi <= FOV,

with Lambertian order m = -ln 2 / ln cos(Phi_1/2).  Following common practice
in VLC physical-layer security papers, the electrical SNR at any position is
referenced to the SNR at the centre of the receiving plane, so that

    SNR(x, y) [dB] = SNR_c [dB] + 20 log10( h(x, y) / h(0, 0) ).

The ceiling-bounce delay spread for a 3.5 m ceiling (a = 2H/c = 23 ns,
D_rms ~ 2 ns) is far below the 50 ns sample period used here, so after
zero-forcing equalisation the channel is flat (Al-Moliki et al. 2022, Eq. 11).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class Room:
    Lx: float = 5.0          # m
    Ly: float = 5.0          # m
    height: float = 3.5      # LED (access point) height above receiving plane, m
    semi_angle_deg: float = 70.0   # LED half-power semi-angle
    fov_deg: float = 85.0          # receiver field of view
    a_pd: float = 1e-4             # detector area, m^2

    @property
    def m(self) -> float:
        return -np.log(2) / np.log(np.cos(np.deg2rad(self.semi_angle_deg)))


def los_gain(room: Room, x, y, semi_angle_deg: float | None = None,
             fov_deg: float | None = None) -> np.ndarray:
    """LOS DC gain between a ceiling-centre device and a floor device at (x, y).

    The same expression serves the downlink (LED at ceiling, detector on the
    floor) and the uplink (node LED facing up, detector at the ceiling)
    because both devices face each other along the vertical.
    """
    sa = room.semi_angle_deg if semi_angle_deg is None else semi_angle_deg
    fov = room.fov_deg if fov_deg is None else fov_deg
    m = -np.log(2) / np.log(np.cos(np.deg2rad(sa)))
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    d2 = room.height ** 2 + x ** 2 + y ** 2
    c = room.height / np.sqrt(d2)           # cos(phi) = cos(psi)
    psi = np.degrees(np.arccos(c))
    h = (m + 1) * room.a_pd / (2 * np.pi * d2) * c ** m * c
    return np.where(psi <= fov, h, 0.0)


def snr_db(room: Room, x, y, snr_center_db: float, **kw) -> np.ndarray:
    h = los_gain(room, x, y, **kw)
    h0 = los_gain(room, 0.0, 0.0, **kw)
    with np.errstate(divide="ignore"):
        return snr_center_db + 20 * np.log10(h / h0)


def grid(room: Room, n: int = 41):
    xs = np.linspace(-room.Lx / 2, room.Lx / 2, n)
    ys = np.linspace(-room.Ly / 2, room.Ly / 2, n)
    return xs, ys
