"""Unit tests for the analytic adapter, conditions, and batch runner."""

from __future__ import annotations

from src.geometry.generator import generate_wing
from src.simulation.analytic_adapter import AnalyticAdapter
from src.simulation.base_adapter import FlightCondition
from src.simulation.postprocess import is_acceptable
from src.simulation.runner import build_conditions, get_adapter, run_batch


def _wing(bounds, design_id="wing_000000"):
    params = {
        "span_m": 1.5,
        "root_chord_m": 0.30,
        "tip_chord_m": 0.15,
        "sweep_deg": 10.0,
        "twist_deg": 2.0,
        "airfoil_id": "NACA2412",
    }
    return generate_wing(params, design_id=design_id, bounds=bounds)


def test_analytic_adapter_produces_physical_values(bounds):
    wing = _wing(bounds)
    adapter = AnalyticAdapter()
    result = adapter.evaluate(wing, FlightCondition(velocity_mps=20, aoa_deg=5))
    assert result.CD > 0
    assert result.LD == result.CL / result.CD
    assert is_acceptable(result)


def test_lift_increases_with_aoa(bounds):
    wing = _wing(bounds)
    adapter = AnalyticAdapter()
    low = adapter.evaluate(wing, FlightCondition(velocity_mps=20, aoa_deg=0))
    high = adapter.evaluate(wing, FlightCondition(velocity_mps=20, aoa_deg=8))
    assert high.CL > low.CL


def test_build_conditions_expands_grid():
    cfg = {
        "air_density": 1.225,
        "velocities_mps": [15, 20],
        "aoa_deg_start": -5,
        "aoa_deg_stop": 5,
        "aoa_deg_step": 5,
    }
    conditions = build_conditions(cfg)
    # 2 velocities x 3 AoA points (-5, 0, 5)
    assert len(conditions) == 6


def test_run_batch_collects_results(bounds):
    wings = [_wing(bounds, f"wing_{i:06d}") for i in range(3)]
    conditions = [FlightCondition(velocity_mps=20, aoa_deg=a) for a in (0, 5)]
    outcome = run_batch(wings, conditions, get_adapter("analytic"))
    assert len(outcome.results) == 6
    assert not outcome.failures
