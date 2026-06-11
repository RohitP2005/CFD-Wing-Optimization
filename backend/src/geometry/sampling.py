"""Design-of-experiments sampling for wing design variables."""

from __future__ import annotations

from typing import Sequence

import numpy as np

from .generator import WingParameters
from .validation import Bounds

# Continuous design variables sampled within bounds.
_CONTINUOUS_VARS: tuple[str, ...] = (
    "span_m",
    "root_chord_m",
    "tip_chord_m",
    "sweep_deg",
    "twist_deg",
)


def _latin_hypercube(n: int, dims: int, rng: np.random.Generator) -> np.ndarray:
    """Return an (n, dims) Latin Hypercube sample in the unit hypercube."""
    cut = np.linspace(0.0, 1.0, n + 1)
    samples = np.empty((n, dims))
    for d in range(dims):
        points = rng.uniform(cut[:-1], cut[1:])
        rng.shuffle(points)
        samples[:, d] = points
    return samples


def sample_designs(
    bounds: Bounds,
    method: str,
    num_designs: int,
    seed: int,
) -> list[WingParameters]:
    """Sample feasible wing designs within bounds.

    Designs that violate ``tip_chord_m <= root_chord_m`` are repaired by
    swapping the two chord values so the sample remains feasible.
    """
    rng = np.random.default_rng(seed)
    airfoils: Sequence[str] = bounds.airfoils or ("NACA2412",)
    dims = len(_CONTINUOUS_VARS)

    if method == "lhs":
        unit = _latin_hypercube(num_designs, dims, rng)
    elif method == "fixed":
        unit = np.full((num_designs, dims), 0.5)
    else:
        # Uniform random fallback for unspecified methods.
        unit = rng.uniform(size=(num_designs, dims))

    designs: list[WingParameters] = []
    for i in range(num_designs):
        values: dict[str, float] = {}
        for d, name in enumerate(_CONTINUOUS_VARS):
            low, high = bounds.ranges[name]
            values[name] = float(low + unit[i, d] * (high - low))

        # Repair chord ordering to satisfy the feasibility constraint.
        if values["tip_chord_m"] > values["root_chord_m"]:
            values["root_chord_m"], values["tip_chord_m"] = (
                values["tip_chord_m"],
                values["root_chord_m"],
            )

        airfoil = airfoils[int(rng.integers(len(airfoils)))]
        designs.append(
            WingParameters(
                span_m=values["span_m"],
                root_chord_m=values["root_chord_m"],
                tip_chord_m=values["tip_chord_m"],
                sweep_deg=values["sweep_deg"],
                twist_deg=values["twist_deg"],
                airfoil_id=airfoil,
            )
        )
    return designs
