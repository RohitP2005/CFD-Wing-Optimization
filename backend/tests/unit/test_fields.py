"""Unit tests for Phase 5 field simulation and flow visualization."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from src.geometry.generator import generate_wing
from src.simulation.base_adapter import FlightCondition
from src.simulation.fields import load_fields, write_fields
from src.simulation.panel2d_adapter import Panel2DAdapter
from src.simulation.runner import get_adapter, run_batch
from src.visualization import plots_fields


def _geometry(bounds):
    params = {
        "span_m": 1.5,
        "root_chord_m": 0.30,
        "tip_chord_m": 0.15,
        "sweep_deg": 8.0,
        "twist_deg": 2.0,
        "airfoil_id": "NACA2412",
    }
    return generate_wing(params, design_id="wing_000001", bounds=bounds)


def test_get_adapter_registers_panel2d():
    adapter = get_adapter("panel2d")
    assert adapter.name == "panel2d"
    assert adapter.supports_fields is True


def test_get_adapter_fallback_to_analytic():
    adapter = get_adapter("nonexistent_solver", allow_fallback=True)
    assert adapter.name == "analytic"


def test_panel2d_matches_analytic_coefficients(bounds):
    geometry = _geometry(bounds)
    condition = FlightCondition(velocity_mps=20, aoa_deg=5)
    analytic = get_adapter("analytic").evaluate(geometry, condition)
    panel = get_adapter("panel2d").evaluate(geometry, condition)
    assert panel.CL == analytic.CL
    assert panel.CD == analytic.CD
    assert panel.solver == "panel2d"


def test_panel2d_field_is_well_formed(bounds):
    geometry = _geometry(bounds)
    condition = FlightCondition(velocity_mps=20, aoa_deg=5)
    data = Panel2DAdapter().compute_field(geometry, condition)

    assert data.x_grid.shape == data.pressure.shape
    assert data.velocity_x.shape == data.velocity_y.shape
    # Outside-the-body values must be finite (NaN only inside the airfoil).
    assert np.isfinite(data.pressure[0, 0])
    assert data.surface_cp.shape == data.surface_x.shape
    # Some part of the surface should see suction (Cp < 0) at positive lift.
    assert np.nanmin(data.surface_cp) < 0.0


def test_field_artifact_roundtrip(tmp_path, bounds):
    geometry = _geometry(bounds)
    condition = FlightCondition(velocity_mps=20, aoa_deg=5)
    data = Panel2DAdapter().compute_field(geometry, condition)

    sidecar = write_fields(data, tmp_path)
    assert sidecar.exists()

    restored = load_fields(sidecar)
    assert restored.design_id == data.design_id
    assert restored.condition_id == data.condition_id
    np.testing.assert_allclose(restored.pressure, data.pressure, equal_nan=True)
    np.testing.assert_allclose(restored.surface_cp, data.surface_cp)


def test_run_batch_writes_fields(tmp_path, bounds):
    geometry = _geometry(bounds)
    conditions = [FlightCondition(velocity_mps=20, aoa_deg=a) for a in (0, 4)]
    adapter = get_adapter("panel2d")
    outcome = run_batch(
        [geometry], conditions, adapter, save_fields=True, fields_dir=tmp_path
    )
    assert len(outcome.results) == 2
    assert len(outcome.field_artifacts) == 2
    assert all(Path(p).exists() for p in outcome.field_artifacts)


def test_run_batch_skips_fields_for_analytic(tmp_path, bounds):
    geometry = _geometry(bounds)
    conditions = [FlightCondition(velocity_mps=20, aoa_deg=0)]
    adapter = get_adapter("analytic")
    outcome = run_batch(
        [geometry], conditions, adapter, save_fields=True, fields_dir=tmp_path
    )
    assert outcome.field_artifacts == []


def test_flow_plots_save_files(tmp_path, bounds):
    geometry = _geometry(bounds)
    condition = FlightCondition(velocity_mps=20, aoa_deg=5)
    data = Panel2DAdapter().compute_field(geometry, condition)

    assert Path(plots_fields.plot_surface_cp(data, tmp_path / "cp.png")).exists()
    assert Path(
        plots_fields.plot_pressure_contour(data, tmp_path / "p.png")
    ).exists()
    assert Path(
        plots_fields.plot_velocity_contour(data, tmp_path / "v.png")
    ).exists()
    assert Path(
        plots_fields.plot_streamlines(data, tmp_path / "s.png")
    ).exists()
