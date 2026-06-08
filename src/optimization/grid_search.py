"""Grid search optimizer (baseline reference algorithm)."""

from __future__ import annotations

import itertools

from .base import OptimizationResult, Optimizer, better_feasible
from .objective import BudgetExhausted, EvalRecord


class GridSearch(Optimizer):
    """Exhaustive search over a discretized design grid."""

    name = "grid"

    def __init__(self, evaluator, seed: int = 0, points_per_dim: int = 3) -> None:
        super().__init__(evaluator, seed)
        self.points_per_dim = int(points_per_dim)

    def optimize(self) -> OptimizationResult:
        space = self.evaluator.space
        axes = space.linspace_grid(self.points_per_dim)

        best: EvalRecord | None = None
        history: list[EvalRecord] = []
        convergence: list[dict[str, float]] = []

        try:
            for combo in itertools.product(*axes):
                vector = space.repair(list(combo))
                for airfoil_index in range(space.n_airfoils):
                    params = space.to_parameters(vector, airfoil_index)
                    record = self.evaluator.evaluate(params)
                    history.append(record)
                    if better_feasible(record, best):
                        best = record
                    convergence.append(
                        {
                            "evaluation": float(self.evaluator.num_evaluations),
                            "best_cost": best.cost if best else float("inf"),
                        }
                    )
        except BudgetExhausted:
            pass

        return OptimizationResult(
            algorithm=self.name,
            best=best,
            history=history,
            convergence=convergence,
            num_evaluations=self.evaluator.num_evaluations,
        )
