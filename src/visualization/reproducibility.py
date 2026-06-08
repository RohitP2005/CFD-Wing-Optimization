"""Reproducibility verification by re-running an optimization with a fixed seed."""

from __future__ import annotations

from dataclasses import dataclass

from ..geometry.validation import Bounds
from ..optimization.constraints import ConstraintSet
from ..optimization.ga import GeneticAlgorithm
from ..optimization.grid_search import GridSearch
from ..optimization.nsga2 import NSGA2
from ..optimization.objective import Evaluator, build_mission
from ..optimization.space import DesignSpace
from ..simulation.runner import get_adapter


@dataclass
class ReproResult:
    """Outcome of a reproducibility check."""

    matched: bool
    run_a_cost: float | None
    run_b_cost: float | None
    tolerance: float

    @property
    def difference(self) -> float:
        if self.run_a_cost is None or self.run_b_cost is None:
            return float("inf")
        return abs(self.run_a_cost - self.run_b_cost)


def _build_optimizer(opt_cfg: dict, evaluator: Evaluator, seed: int):
    algorithm = str(opt_cfg.get("algorithm", "ga"))
    if algorithm == "grid":
        return GridSearch(
            evaluator, seed=seed,
            points_per_dim=int(opt_cfg.get("grid", {}).get("points_per_dim", 3)),
        )
    if algorithm == "nsga2":
        nsga_cfg = opt_cfg.get("nsga2", {})
        return NSGA2(
            evaluator, seed=seed,
            population_size=int(nsga_cfg.get("population_size", 40)),
            generations=int(nsga_cfg.get("generations", 30)),
        )
    ga_cfg = opt_cfg.get("ga", {})
    return GeneticAlgorithm(
        evaluator, seed=seed,
        population_size=int(ga_cfg.get("population_size", 40)),
        generations=int(ga_cfg.get("generations", 30)),
        crossover_rate=float(ga_cfg.get("crossover_rate", 0.9)),
        mutation_rate=float(ga_cfg.get("mutation_rate", 0.2)),
        elite=int(ga_cfg.get("elite", 2)),
    )


def _run_once(experiment: dict, bounds: Bounds, seed: int) -> float | None:
    opt_cfg = experiment["optimization"]
    space = DesignSpace.from_bounds(bounds)
    adapter = get_adapter(str(experiment["solver"]["name"]))
    evaluator = Evaluator(
        space=space,
        adapter=adapter,
        mission=build_mission(opt_cfg["mission"]),
        objective=str(opt_cfg.get("objective", "maximize_ld")),
        constraints=ConstraintSet.from_config(opt_cfg.get("constraints", {})),
        max_evaluations=int(opt_cfg.get("max_evaluations", 1000)),
    )
    result = _build_optimizer(opt_cfg, evaluator, seed).optimize()
    return result.best.cost if result.best else None


def verify_reproducibility(
    experiment: dict,
    bounds: Bounds,
    seed: int,
    tolerance: float = 1e-9,
) -> ReproResult:
    """Run the configured optimization twice and compare the best cost."""
    cost_a = _run_once(experiment, bounds, seed)
    cost_b = _run_once(experiment, bounds, seed)
    matched = (
        cost_a is not None
        and cost_b is not None
        and abs(cost_a - cost_b) <= tolerance
    )
    return ReproResult(
        matched=matched,
        run_a_cost=cost_a,
        run_b_cost=cost_b,
        tolerance=tolerance,
    )
