"""Feature engineering for the aerodynamic surrogate model.

Encodes wing parameters and operating conditions into a numeric feature matrix.
Airfoil identity is handled as a categorical via stable one-hot encoding so the
feature layout is reproducible across train and inference.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np
import pandas as pd

# Continuous input features (in fixed order) used by the surrogate.
CONTINUOUS_FEATURES: tuple[str, ...] = (
    "span_m",
    "root_chord_m",
    "tip_chord_m",
    "sweep_deg",
    "twist_deg",
    "aoa_deg",
    "velocity_mps",
)

# Default prediction targets.
TARGETS: tuple[str, ...] = ("CL", "CD", "LD")


@dataclass(frozen=True)
class FeatureSpec:
    """Immutable description of the encoded feature layout.

    Persisting this with a model guarantees inference uses the same column
    order and airfoil vocabulary as training.
    """

    continuous: tuple[str, ...]
    airfoils: tuple[str, ...]

    @property
    def columns(self) -> list[str]:
        return list(self.continuous) + [f"airfoil_{a}" for a in self.airfoils]

    @property
    def n_features(self) -> int:
        return len(self.continuous) + len(self.airfoils)


def build_feature_spec(
    airfoils: Sequence[str],
    continuous: Sequence[str] = CONTINUOUS_FEATURES,
) -> FeatureSpec:
    """Create a feature spec from a sorted, de-duplicated airfoil vocabulary."""
    vocab = tuple(sorted(dict.fromkeys(airfoils)))
    return FeatureSpec(continuous=tuple(continuous), airfoils=vocab)


def encode_frame(frame: pd.DataFrame, spec: FeatureSpec) -> np.ndarray:
    """Encode a DataFrame of raw rows into a numeric feature matrix."""
    missing = [c for c in spec.continuous if c not in frame.columns]
    if missing:
        raise ValueError(f"Missing required feature columns: {missing}")

    cont = frame[list(spec.continuous)].to_numpy(dtype=float)

    # Stable one-hot for the known airfoil vocabulary; unknown airfoils -> zeros.
    onehot = np.zeros((len(frame), len(spec.airfoils)), dtype=float)
    index = {a: i for i, a in enumerate(spec.airfoils)}
    if "airfoil_id" in frame.columns:
        for row, airfoil in enumerate(frame["airfoil_id"].astype(str)):
            col = index.get(airfoil)
            if col is not None:
                onehot[row, col] = 1.0

    return np.hstack([cont, onehot])


def encode_row(row: dict[str, object], spec: FeatureSpec) -> np.ndarray:
    """Encode a single raw row dict into a 1 x n_features matrix."""
    return encode_frame(pd.DataFrame([row]), spec)
