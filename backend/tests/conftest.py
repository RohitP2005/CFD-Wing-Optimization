"""Shared pytest fixtures."""

from __future__ import annotations

import pytest

from src.geometry.validation import Bounds


@pytest.fixture
def bounds() -> Bounds:
    config = {
        "bounds": {
            "span_m": [1.0, 2.0],
            "root_chord_m": [0.15, 0.50],
            "tip_chord_m": [0.05, 0.30],
            "sweep_deg": [0.0, 30.0],
            "twist_deg": [-5.0, 5.0],
        },
        "airfoils": ["NACA0012", "NACA2412", "NACA4412"],
        "constraints": {
            "enforce_tip_le_root": True,
            "wing_area_m2": [0.10, 0.90],
        },
    }
    return Bounds.from_config(config)
