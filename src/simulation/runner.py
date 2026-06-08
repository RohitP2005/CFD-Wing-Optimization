"""Batch simulation orchestration with fault-tolerant execution."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Sequence

from ..geometry.generator import WingGeometry
from .analytic_adapter import AnalyticAdapter
from .base_adapter import (
    BaseSolverAdapter,
    FlightCondition,
    SimulationError,
    SimulationResult,
)

# Registry of available solver adapters keyed by config name.
_ADAPTERS: dict[str, type[BaseSolverAdapter]] = {
    AnalyticAdapter.name: AnalyticAdapter,
}


def get_adapter(name: str) -> BaseSolverAdapter:
    """Instantiate a solver adapter by name."""
    try:
        return _ADAPTERS[name]()
    except KeyError as exc:
        raise ValueError(
            f"Unknown solver adapter {name!r}. Available: {sorted(_ADAPTERS)}"
        ) from exc


def build_conditions(conditions_cfg: dict) -> list[FlightCondition]:
    """Expand a conditions config block into a flat list of flight points."""
    density = float(conditions_cfg.get("air_density", 1.225))
    velocities = [float(v) for v in conditions_cfg["velocities_mps"]]
    start = float(conditions_cfg["aoa_deg_start"])
    stop = float(conditions_cfg["aoa_deg_stop"])
    step = float(conditions_cfg["aoa_deg_step"])

    aoas: list[float] = []
    value = start
    while value <= stop + 1e-9:
        aoas.append(round(value, 6))
        value += step

    return [
        FlightCondition(velocity_mps=v, aoa_deg=a, air_density=density)
        for v in velocities
        for a in aoas
    ]


@dataclass
class BatchOutcome:
    """Collected results and failures from a batch run."""

    results: list[SimulationResult] = field(default_factory=list)
    failures: list[dict[str, object]] = field(default_factory=list)


def run_batch(
    geometries: Sequence[WingGeometry],
    conditions: Iterable[FlightCondition],
    adapter: BaseSolverAdapter,
) -> BatchOutcome:
    """Evaluate every geometry across all conditions.

    Isolated case failures are recorded and do not abort the batch, satisfying
    the Phase 1 fault-tolerance exit criterion.
    """
    conditions = list(conditions)
    outcome = BatchOutcome()

    for geometry in geometries:
        for condition in conditions:
            try:
                result = adapter.evaluate(geometry, condition)
                outcome.results.append(result)
            except SimulationError as exc:
                outcome.failures.append(
                    {
                        "design_id": geometry.design_id,
                        "condition_id": condition.condition_id,
                        "reason": str(exc),
                    }
                )

    return outcome
