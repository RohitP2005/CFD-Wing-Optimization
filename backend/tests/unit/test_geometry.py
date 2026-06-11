"""Unit tests for geometry generation, metrics, and validation."""

from __future__ import annotations

import math

import pytest

from src.geometry.generator import WingParameters, compute_metrics, generate_wing
from src.geometry.validation import ValidationError, validate_parameters


def _params(**overrides) -> dict:
    base = {
        "span_m": 1.5,
        "root_chord_m": 0.30,
        "tip_chord_m": 0.15,
        "sweep_deg": 10.0,
        "twist_deg": 2.0,
        "airfoil_id": "NACA2412",
    }
    base.update(overrides)
    return base


def test_compute_metrics_matches_spec_example():
    params = WingParameters.from_mapping(_params())
    metrics = compute_metrics(params)
    assert metrics["wing_area_m2"] == pytest.approx(0.3375, abs=1e-4)
    assert metrics["aspect_ratio"] == pytest.approx(6.667, abs=1e-2)
    assert metrics["taper_ratio"] == pytest.approx(0.5, abs=1e-9)
    assert math.isfinite(metrics["mean_aerodynamic_chord_m"])


def test_generate_wing_with_bounds(bounds):
    wing = generate_wing(_params(), design_id="wing_000001", bounds=bounds)
    assert wing.design_id == "wing_000001"
    assert wing.wing_area_m2 > 0
    record = wing.to_record()
    assert record["airfoil_id"] == "NACA2412"
    assert "aspect_ratio" in record


def test_validate_rejects_out_of_range_span(bounds):
    with pytest.raises(ValidationError):
        validate_parameters(_params(span_m=5.0), bounds)


def test_validate_rejects_tip_gt_root(bounds):
    with pytest.raises(ValidationError):
        validate_parameters(_params(tip_chord_m=0.40, root_chord_m=0.20), bounds)


def test_validate_rejects_unknown_airfoil(bounds):
    with pytest.raises(ValidationError):
        validate_parameters(_params(airfoil_id="NACA9999X"), bounds)
