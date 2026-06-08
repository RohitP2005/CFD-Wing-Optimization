"""Design-variable space: encoding, decoding, sampling, and repair."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np

from ..geometry.generator import WingParameters
from ..geometry.validation import Bounds

# Ordered continuous design variables optimized by the engine.
CONTINUOUS_VARS: tuple[str, ...] = (
    "span_m",
    "root_chord_m",
    "tip_chord_m",
    "sweep_deg",
    "twist_deg",
)


@dataclass(frozen=True)
class DesignSpace:
    """Continuous + discrete design space derived from configured bounds."""

    lower: np.ndarray
    upper: np.ndarray
    airfoils: tuple[str, ...]

    @classmethod
    def from_bounds(cls, bounds: Bounds) -> "DesignSpace":
        lower = np.array([bounds.ranges[name][0] for name in CONTINUOUS_VARS], dtype=float)
        upper = np.array([bounds.ranges[name][1] for name in CONTINUOUS_VARS], dtype=float)
        airfoils = tuple(bounds.airfoils) or ("NACA2412",)
        return cls(lower=lower, upper=upper, airfoils=airfoils)

    @property
    def n_continuous(self) -> int:
        return len(CONTINUOUS_VARS)

    @property
    def n_airfoils(self) -> int:
        return len(self.airfoils)

    def clip(self, vector: np.ndarray) -> np.ndarray:
        """Clip a continuous vector into the design bounds."""
        return np.clip(vector, self.lower, self.upper)

    def repair(self, vector: np.ndarray) -> np.ndarray:
        """Repair a continuous vector so it is feasible by construction.

        Ensures bounds compliance and enforces tip_chord <= root_chord by
        swapping the two chord values when needed.
        """
        out = self.clip(np.asarray(vector, dtype=float)).copy()
        root_idx = CONTINUOUS_VARS.index("root_chord_m")
        tip_idx = CONTINUOUS_VARS.index("tip_chord_m")
        if out[tip_idx] > out[root_idx]:
            out[root_idx], out[tip_idx] = out[tip_idx], out[root_idx]
        return out

    def to_parameters(self, vector: np.ndarray, airfoil_index: int) -> WingParameters:
        """Decode a continuous vector + airfoil index into wing parameters."""
        vec = self.repair(vector)
        airfoil = self.airfoils[int(airfoil_index) % self.n_airfoils]
        values = dict(zip(CONTINUOUS_VARS, vec))
        return WingParameters(
            span_m=values["span_m"],
            root_chord_m=values["root_chord_m"],
            tip_chord_m=values["tip_chord_m"],
            sweep_deg=values["sweep_deg"],
            twist_deg=values["twist_deg"],
            airfoil_id=airfoil,
        )

    def random_vector(self, rng: np.random.Generator) -> np.ndarray:
        """Sample a uniform random continuous vector within bounds."""
        return rng.uniform(self.lower, self.upper)

    def random_airfoil_index(self, rng: np.random.Generator) -> int:
        """Sample a random airfoil index."""
        return int(rng.integers(self.n_airfoils))

    def linspace_grid(self, points_per_dim: int) -> list[np.ndarray]:
        """Return per-dimension grid coordinates for grid search."""
        return [
            np.linspace(self.lower[d], self.upper[d], points_per_dim)
            for d in range(self.n_continuous)
        ]
