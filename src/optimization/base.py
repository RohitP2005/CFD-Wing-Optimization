"""Optimizer base interface and shared result containers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from .objective import EvalRecord, Evaluator


@dataclass
class OptimizationResult:
    """Outcome of an optimization run."""

    algorithm: str
    best: EvalRecord | None
    history: list[EvalRecord] = field(default_factory=list)
    convergence: list[dict[str, float]] = field(default_factory=list)
    pareto: list[EvalRecord] = field(default_factory=list)
    num_evaluations: int = 0


class Optimizer(ABC):
    """Base class for all optimization algorithms."""

    name: str = "base"

    def __init__(self, evaluator: Evaluator, seed: int = 0) -> None:
        self.evaluator = evaluator
        self.seed = seed

    @abstractmethod
    def optimize(self) -> OptimizationResult:
        """Run the optimization and return the result."""
        raise NotImplementedError


def better_feasible(candidate: EvalRecord, incumbent: EvalRecord | None) -> bool:
    """Return True if candidate should replace incumbent for single-objective.

    Feasible designs always dominate infeasible ones; ties break on lower cost.
    """
    if incumbent is None:
        return True
    if candidate.feasible and not incumbent.feasible:
        return True
    if not candidate.feasible and incumbent.feasible:
        return False
    return candidate.cost < incumbent.cost
