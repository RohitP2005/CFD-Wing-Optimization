"""Objective evaluation: mission aggregation, caching, and budget tracking."""

from __future__ import annotations

from dataclasses import dataclass, field
from statistics import fmean
from typing import Sequence

import numpy as np

from ..geometry.generator import WingParameters, generate_wing
from ..simulation.base_adapter import BaseSolverAdapter, FlightCondition
from .constraints import ConstraintSet
from .space import DesignSpace

# Supported single-objective targets and their optimization direction.
# direction = +1 means the raw metric is minimized, -1 means it is maximized.
_OBJECTIVES: dict[str, tuple[str, int]] = {
    "maximize_ld": ("LD", -1),
    "maximize_cl": ("CL", -1),
    "minimize_cd": ("CD", +1),
}


class BudgetExhausted(RuntimeError):
    """Raised internally when the evaluation budget is fully consumed."""


@dataclass
class EvalRecord:
    """Result of evaluating one design over the mission profile."""

    eval_index: int
    params: WingParameters
    metrics: dict[str, float]
    feasible: bool
    penalty: float
    cost: float
    objectives: tuple[float, float]

    def to_row(self) -> dict[str, object]:
        row: dict[str, object] = {
            "eval_index": self.eval_index,
            "span_m": self.params.span_m,
            "root_chord_m": self.params.root_chord_m,
            "tip_chord_m": self.params.tip_chord_m,
            "sweep_deg": self.params.sweep_deg,
            "twist_deg": self.params.twist_deg,
            "airfoil_id": self.params.airfoil_id,
            "feasible": self.feasible,
            "penalty": self.penalty,
            "cost": self.cost,
            "obj_cl": self.objectives[0],
            "obj_cd": self.objectives[1],
        }
        row.update(self.metrics)
        return row


def build_mission(conditions_cfg: dict) -> list[FlightCondition]:
    """Expand a mission config block into flight conditions for aggregation."""
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


class Evaluator:
    """Evaluates designs by aggregating solver outputs over a mission profile."""

    def __init__(
        self,
        space: DesignSpace,
        adapter: BaseSolverAdapter,
        mission: Sequence[FlightCondition],
        objective: str,
        constraints: ConstraintSet,
        max_evaluations: int,
    ) -> None:
        if objective not in _OBJECTIVES:
            raise ValueError(
                f"Unknown objective {objective!r}. Options: {sorted(_OBJECTIVES)}"
            )
        self.space = space
        self.adapter = adapter
        self.mission = list(mission)
        self.objective = objective
        self.constraints = constraints
        self.max_evaluations = int(max_evaluations)
        self._count = 0
        self._cache: dict[tuple, EvalRecord] = {}

    @property
    def num_evaluations(self) -> int:
        return self._count

    @property
    def budget_exhausted(self) -> bool:
        return self._count >= self.max_evaluations

    def _key(self, params: WingParameters) -> tuple:
        return (
            round(params.span_m, 6),
            round(params.root_chord_m, 6),
            round(params.tip_chord_m, 6),
            round(params.sweep_deg, 6),
            round(params.twist_deg, 6),
            params.airfoil_id,
        )

    def evaluate(self, params: WingParameters) -> EvalRecord:
        """Evaluate a design, using a cache and respecting the budget."""
        key = self._key(params)
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        if self.budget_exhausted:
            raise BudgetExhausted

        geometry = generate_wing(params, design_id=f"opt_{self._count:06d}")
        cls: list[float] = []
        cds: list[float] = []
        lds: list[float] = []
        for condition in self.mission:
            result = self.adapter.evaluate(geometry, condition)
            if result.status in ("converged", "stall_limited"):
                cls.append(result.CL)
                cds.append(result.CD)
                lds.append(result.LD)

        if cls:
            metrics = {
                "CL": fmean(cls),
                "CD": fmean(cds),
                "LD": fmean(lds),
                "wing_area_m2": geometry.wing_area_m2,
                "aspect_ratio": geometry.aspect_ratio,
            }
        else:
            metrics = {
                "CL": 0.0,
                "CD": 1.0,
                "LD": 0.0,
                "wing_area_m2": geometry.wing_area_m2,
                "aspect_ratio": geometry.aspect_ratio,
            }

        penalty = self.constraints.penalty(geometry.wing_area_m2)
        feasible = self.constraints.is_feasible(geometry.wing_area_m2)

        metric_name, direction = _OBJECTIVES[self.objective]
        cost = direction * metrics[metric_name] + penalty

        # Multi-objective vector (both minimized): maximize CL, minimize CD.
        objectives = (-metrics["CL"] + penalty, metrics["CD"] + penalty)

        record = EvalRecord(
            eval_index=self._count,
            params=params,
            metrics=metrics,
            feasible=feasible,
            penalty=penalty,
            cost=cost,
            objectives=objectives,
        )
        self._count += 1
        self._cache[key] = record
        return record
