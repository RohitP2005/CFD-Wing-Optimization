"""Batch simulation orchestration with fault-tolerant execution."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Sequence

from ..geometry.generator import WingGeometry
from .analytic_adapter import AnalyticAdapter
from .base_adapter import (
    BaseSolverAdapter,
    FlightCondition,
    SimulationError,
    SimulationResult,
)
from .fields import write_fields
from .panel2d_adapter import Panel2DAdapter

# Registry of available solver adapters keyed by config name.
_ADAPTERS: dict[str, type[BaseSolverAdapter]] = {
    AnalyticAdapter.name: AnalyticAdapter,
    Panel2DAdapter.name: Panel2DAdapter,
}


def _load_optional_adapters() -> None:
    """Register optional external-solver adapters when their deps are present."""
    try:  # pragma: no cover - exercised only when the optional module exists
        from .xflr5_adapter import XFLR5Adapter

        _ADAPTERS.setdefault(XFLR5Adapter.name, XFLR5Adapter)
    except Exception:  # noqa: BLE001 - optional, missing deps are expected
        pass
    try:  # pragma: no cover - exercised only when the optional module exists
        from .su2_adapter import SU2Adapter

        _ADAPTERS.setdefault(SU2Adapter.name, SU2Adapter)
    except Exception:  # noqa: BLE001 - optional, missing deps are expected
        pass


def get_adapter(name: str, allow_fallback: bool = False) -> BaseSolverAdapter:
    """Instantiate a solver adapter by name.

    When ``allow_fallback`` is true and the requested adapter is unavailable,
    fall back to the analytic baseline instead of raising (FR-CFD-02).
    """
    _load_optional_adapters()
    try:
        return _ADAPTERS[name]()
    except KeyError as exc:
        if allow_fallback:
            return AnalyticAdapter()
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
    field_artifacts: list[str] = field(default_factory=list)


def run_batch(
    geometries: Sequence[WingGeometry],
    conditions: Iterable[FlightCondition],
    adapter: BaseSolverAdapter,
    save_fields: bool = False,
    fields_dir: str | Path | None = None,
) -> BatchOutcome:
    """Evaluate every geometry across all conditions.

    Isolated case failures are recorded and do not abort the batch, satisfying
    the Phase 1 fault-tolerance exit criterion. When ``save_fields`` is true and
    the adapter supports fields, a flow-field artifact is written per case
    (FR-CFD-01/03).
    """
    conditions = list(conditions)
    outcome = BatchOutcome()
    write_field_artifacts = (
        save_fields and adapter.supports_fields and fields_dir is not None
    )

    for geometry in geometries:
        for condition in conditions:
            try:
                result = adapter.evaluate(geometry, condition)
                outcome.results.append(result)
                if write_field_artifacts:
                    field_data = adapter.compute_field(geometry, condition, result)
                    if field_data is not None:
                        sidecar = write_fields(field_data, fields_dir)
                        outcome.field_artifacts.append(str(sidecar))
            except SimulationError as exc:
                outcome.failures.append(
                    {
                        "design_id": geometry.design_id,
                        "condition_id": condition.condition_id,
                        "reason": str(exc),
                    }
                )

    return outcome
