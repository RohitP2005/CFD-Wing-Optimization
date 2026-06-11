"""Unit tests for the Phase 4 visualization and reproducibility utilities."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.geometry.generator import WingParameters
from src.visualization import plots_cfd, plots_geometry, plots_optimization
from src.visualization.report import (
    build_comparison,
    comparison_to_dict,
    write_comparison_report,
)
from src.visualization.reproducibility import verify_reproducibility


def _results_frame() -> pd.DataFrame:
    rows = []
    for aoa in (-4, 0, 4, 8):
        for vel in (15, 20):
            cl = 0.1 * aoa + 0.4
            cd = 0.02 + 0.001 * abs(aoa)
            rows.append(
                {
                    "aoa_deg": aoa,
                    "velocity_mps": vel,
                    "CL": cl,
                    "CD": cd,
                    "LD": cl / cd,
                }
            )
    return pd.DataFrame(rows)


def test_plot_airfoil_saves_file(tmp_path):
    out = plots_geometry.plot_airfoil("NACA2412", tmp_path / "airfoil.png")
    assert Path(out).exists()


def test_plot_planform_saves_file(tmp_path):
    params = WingParameters(
        span_m=1.5, root_chord_m=0.30, tip_chord_m=0.15,
        sweep_deg=10.0, twist_deg=2.0, airfoil_id="NACA2412",
    )
    out = plots_geometry.plot_planform(params, tmp_path / "planform.png")
    assert Path(out).exists()


def test_performance_plots_save(tmp_path):
    frame = _results_frame()
    assert Path(plots_cfd.plot_polar(frame, tmp_path / "polar.png")).exists()
    assert Path(
        plots_cfd.plot_aoa_sweep(frame, velocity_mps=20, path=tmp_path / "aoa.png")
    ).exists()


def test_optimization_plots_save(tmp_path):
    conv = pd.DataFrame({"generation": [0, 1, 2], "best_cost": [-5.0, -8.0, -10.0]})
    assert Path(
        plots_optimization.plot_convergence(conv, tmp_path / "conv.png")
    ).exists()
    pareto = pd.DataFrame({"CL": [0.8, 1.0, 1.2], "CD": [0.02, 0.03, 0.05]})
    assert Path(
        plots_optimization.plot_pareto(pareto, tmp_path / "pareto.png")
    ).exists()


def test_comparison_report(tmp_path):
    rows = build_comparison(
        {"CL": 0.95, "CD": 0.08, "LD": 11.8},
        {"CL": 1.15, "CD": 0.06, "LD": 19.1},
    )
    payload = comparison_to_dict(rows)
    assert payload["comparison"][2]["metric"] == "LD"
    assert payload["comparison"][2]["delta"] > 0

    paths = write_comparison_report(rows, tmp_path, "cmp")
    assert paths["json"].exists()
    assert paths["html"].exists()


def test_reproducibility_matches_for_fixed_seed(bounds):
    experiment = {
        "experiment": {"seed": 3},
        "solver": {"name": "analytic"},
        "optimization": {
            "algorithm": "ga",
            "objective": "maximize_ld",
            "max_evaluations": 120,
            "mission": {
                "air_density": 1.225,
                "velocities_mps": [20],
                "aoa_deg_start": 0,
                "aoa_deg_stop": 8,
                "aoa_deg_step": 4,
            },
            "constraints": {"wing_area_m2": [0.10, 0.90], "penalty_weight": 100.0},
            "ga": {"population_size": 16, "generations": 5},
        },
    }
    result = verify_reproducibility(experiment, bounds, seed=3)
    assert result.matched
