"""Unit tests for the Phase 2 optimization engine."""

from __future__ import annotations

import numpy as np

from src.optimization.constraints import ConstraintSet
from src.optimization.ga import GeneticAlgorithm
from src.optimization.grid_search import GridSearch
from src.optimization.nsga2 import NSGA2, fast_non_dominated_sort
from src.optimization.objective import Evaluator, build_mission
from src.optimization.space import DesignSpace
from src.simulation.analytic_adapter import AnalyticAdapter


MISSION_CFG = {
    "air_density": 1.225,
    "velocities_mps": [20],
    "aoa_deg_start": 0,
    "aoa_deg_stop": 8,
    "aoa_deg_step": 4,
}


def _evaluator(bounds, objective="maximize_ld", max_evaluations=300):
    return Evaluator(
        space=DesignSpace.from_bounds(bounds),
        adapter=AnalyticAdapter(),
        mission=build_mission(MISSION_CFG),
        objective=objective,
        constraints=ConstraintSet(wing_area_m2=(0.10, 0.90), penalty_weight=100.0),
        max_evaluations=max_evaluations,
    )


def test_design_space_repair_orders_chords(bounds):
    space = DesignSpace.from_bounds(bounds)
    # Force tip > root and check repair swaps them.
    vector = np.array([1.5, 0.20, 0.45, 10.0, 2.0])
    repaired = space.repair(vector)
    root_idx = 1
    tip_idx = 2
    assert repaired[tip_idx] <= repaired[root_idx]


def test_constraint_penalty_outside_band():
    cs = ConstraintSet(wing_area_m2=(0.10, 0.50), penalty_weight=10.0)
    assert cs.penalty(0.60) > 0
    assert cs.is_feasible(0.30)
    assert not cs.is_feasible(0.05)


def test_grid_search_returns_feasible_best(bounds):
    evaluator = _evaluator(bounds, max_evaluations=400)
    optimizer = GridSearch(evaluator, seed=0, points_per_dim=3)
    result = optimizer.optimize()
    assert result.best is not None
    assert result.best.feasible
    assert result.num_evaluations > 0


def test_ga_improves_best_cost(bounds):
    evaluator = _evaluator(bounds, max_evaluations=400)
    optimizer = GeneticAlgorithm(
        evaluator, seed=1, population_size=20, generations=10, elite=2
    )
    result = optimizer.optimize()
    assert result.best is not None
    first = result.convergence[0]["best_cost"]
    last = result.convergence[-1]["best_cost"]
    # Best cost is non-increasing across generations.
    assert last <= first


def test_ga_is_deterministic(bounds):
    a = GeneticAlgorithm(
        _evaluator(bounds), seed=7, population_size=16, generations=5
    ).optimize()
    b = GeneticAlgorithm(
        _evaluator(bounds), seed=7, population_size=16, generations=5
    ).optimize()
    assert a.best is not None and b.best is not None
    assert a.best.cost == b.best.cost


def test_budget_is_respected(bounds):
    evaluator = _evaluator(bounds, max_evaluations=50)
    GeneticAlgorithm(
        evaluator, seed=0, population_size=20, generations=50
    ).optimize()
    assert evaluator.num_evaluations <= 50


def test_non_dominated_sort_basic():
    objs = [(0.0, 1.0), (1.0, 0.0), (0.5, 0.5), (2.0, 2.0)]
    fronts = fast_non_dominated_sort(objs)
    # The dominated point (2,2) must not be in the first front.
    assert 3 not in fronts[0]


def test_nsga2_returns_pareto_front(bounds):
    evaluator = _evaluator(bounds, objective="maximize_cl", max_evaluations=400)
    optimizer = NSGA2(evaluator, seed=2, population_size=20, generations=8)
    result = optimizer.optimize()
    assert result.pareto
    assert result.best is not None
