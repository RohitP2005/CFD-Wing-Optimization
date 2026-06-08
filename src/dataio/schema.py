"""Dataset schema definition and record assembly."""

from __future__ import annotations

from datetime import datetime, timezone

from ..geometry.generator import WingGeometry
from ..simulation.base_adapter import SimulationResult

# Ordered columns for the primary sim_results dataset (FR-03 / Section 11).
DATASET_COLUMNS: tuple[str, ...] = (
    "experiment_id",
    "design_id",
    "condition_id",
    "timestamp",
    "span_m",
    "root_chord_m",
    "tip_chord_m",
    "taper_ratio",
    "sweep_deg",
    "twist_deg",
    "airfoil_id",
    "wing_area_m2",
    "aspect_ratio",
    "mean_aerodynamic_chord_m",
    "velocity_mps",
    "aoa_deg",
    "air_density",
    "CL",
    "CD",
    "LD",
    "solver_name",
    "solver_status",
    "iterations",
    "residual_final",
    "runtime_sec",
    "config_hash",
    "seed",
    "experiment_tag",
)


def build_record(
    geometry: WingGeometry,
    result: SimulationResult,
    *,
    experiment_id: str,
    config_hash: str,
    seed: int,
    experiment_tag: str,
) -> dict[str, object]:
    """Assemble a single dataset row from geometry and simulation result."""
    condition = result.condition
    return {
        "experiment_id": experiment_id,
        "design_id": geometry.design_id,
        "condition_id": condition.condition_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "span_m": geometry.params.span_m,
        "root_chord_m": geometry.params.root_chord_m,
        "tip_chord_m": geometry.params.tip_chord_m,
        "taper_ratio": geometry.taper_ratio,
        "sweep_deg": geometry.params.sweep_deg,
        "twist_deg": geometry.params.twist_deg,
        "airfoil_id": geometry.params.airfoil_id,
        "wing_area_m2": geometry.wing_area_m2,
        "aspect_ratio": geometry.aspect_ratio,
        "mean_aerodynamic_chord_m": geometry.mean_aerodynamic_chord_m,
        "velocity_mps": condition.velocity_mps,
        "aoa_deg": condition.aoa_deg,
        "air_density": condition.air_density,
        "CL": result.CL,
        "CD": result.CD,
        "LD": result.LD,
        "solver_name": result.solver,
        "solver_status": result.status,
        "iterations": result.iterations,
        "residual_final": result.residual_final,
        "runtime_sec": result.runtime_sec,
        "config_hash": config_hash,
        "seed": seed,
        "experiment_tag": experiment_tag,
    }
