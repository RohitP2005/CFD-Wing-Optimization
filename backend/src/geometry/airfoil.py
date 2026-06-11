"""Airfoil definitions and lightweight NACA 4-digit geometry helpers."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class Airfoil:
    """Parsed NACA 4-digit airfoil parameters.

    Attributes:
        name: Airfoil identifier, e.g. ``"NACA2412"``.
        max_camber: Maximum camber as a fraction of chord (m).
        camber_position: Position of max camber as a fraction of chord (p).
        thickness: Maximum thickness as a fraction of chord (t).
    """

    name: str
    max_camber: float
    camber_position: float
    thickness: float

    @classmethod
    def from_naca4(cls, name: str) -> "Airfoil":
        """Parse a NACA 4-digit designation such as ``"NACA2412"``."""
        digits = name.upper().replace("NACA", "").strip()
        if len(digits) != 4 or not digits.isdigit():
            raise ValueError(f"Unsupported airfoil designation: {name!r}")
        m = int(digits[0]) / 100.0
        p = int(digits[1]) / 10.0
        t = int(digits[2:]) / 100.0
        return cls(name=name, max_camber=m, camber_position=p, thickness=t)

    def camber_line(self, x: np.ndarray) -> np.ndarray:
        """Return the mean camber line y-coordinates for chordwise stations x in [0, 1]."""
        x = np.asarray(x, dtype=float)
        yc = np.zeros_like(x)
        m, p = self.max_camber, self.camber_position
        if m == 0.0 or p == 0.0:
            return yc
        fore = x < p
        aft = ~fore
        yc[fore] = (m / p**2) * (2 * p * x[fore] - x[fore] ** 2)
        yc[aft] = (m / (1 - p) ** 2) * ((1 - 2 * p) + 2 * p * x[aft] - x[aft] ** 2)
        return yc

    def thickness_distribution(self, x: np.ndarray) -> np.ndarray:
        """Return the half-thickness distribution for chordwise stations x in [0, 1]."""
        x = np.asarray(x, dtype=float)
        t = self.thickness
        return (t / 0.2) * (
            0.2969 * np.sqrt(x)
            - 0.1260 * x
            - 0.3516 * x**2
            + 0.2843 * x**3
            - 0.1015 * x**4
        )
