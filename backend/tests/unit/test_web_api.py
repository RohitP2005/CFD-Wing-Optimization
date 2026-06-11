"""Unit tests for the web backend API."""

from __future__ import annotations

from fastapi.testclient import TestClient

from src.web.api import create_app


def _client() -> TestClient:
    return TestClient(create_app())


def test_health_endpoint():
    response = _client().get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_defaults_endpoint_exposes_bounds_and_options():
    response = _client().get("/api/config/defaults")
    assert response.status_code == 200
    payload = response.json()
    assert "bounds" in payload
    assert "optimization" in payload["defaults"]
    assert "span_m" in payload["bounds"]["ranges"]


def test_preview_endpoint_returns_geometry_plot_data():
    response = _client().post(
        "/api/wings/preview",
        json={
            "span_m": 1.5,
            "root_chord_m": 0.3,
            "tip_chord_m": 0.15,
            "sweep_deg": 10.0,
            "twist_deg": 2.0,
            "airfoil_id": "NACA2412",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["metrics"]["wing_area_m2"] > 0.0
    assert len(payload["airfoil_plot"]["x"]) == len(payload["airfoil_plot"]["upper_y"])
    assert len(payload["planform_plot"]["outline_span_y"]) == 7


def test_optimize_workflow_returns_overlay_compare_and_flow_fields():
    response = _client().post(
        "/api/workflows/optimize",
        json={
            "baseline": {
                "span_m": 1.4,
                "root_chord_m": 0.28,
                "tip_chord_m": 0.12,
                "sweep_deg": 8.0,
                "twist_deg": 1.0,
                "airfoil_id": "NACA2412",
            },
            "compare_condition": {
                "velocity_mps": 20.0,
                "aoa_deg": 5.0,
                "air_density": 1.225,
            },
            "optimization": {
                "algorithm": "ga",
                "objective": "maximize_ld",
                "max_evaluations": 120,
                "population_size": 16,
                "generations": 5,
                "solver_name": "analytic",
            },
            "include_flow_fields": True,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["optimization"]["num_evaluations"] > 0
    assert payload["comparison"]
    assert "flow_field" in payload["baseline"]
    assert "flow_field" in payload["optimized"]
    assert payload["baseline"]["selected_condition"]["forces"]["lift_n"] >= 0.0