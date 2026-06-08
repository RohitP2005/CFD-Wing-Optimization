# Phase 2 Implementation: Optimization Engine

Status: Complete  
Commits: 79e1b7c (engine), 093d0d6 (ignore generated artifacts)  
Date: 2026-06-08

This document describes the Phase 2 optimization engine: the design space, objective evaluation, constraints, the three algorithms (grid search, genetic algorithm, NSGA-II), result persistence, and CLI usage. It maps the work to the implementation plan's Phase 2 exit criteria.

## 1. Summary

Phase 2 adds an optimization layer on top of the Phase 1 pipeline. It searches the wing design space to improve aerodynamic performance, aggregating solver outputs over a mission profile, enforcing constraints via penalties, and persisting history, best design, convergence, and Pareto outputs.

Key capabilities:

1. Encode/decode/repair designs in a bounded continuous + discrete space.
2. Aggregate CL, CD, and L/D over a mission of flight conditions.
3. Enforce wing-area constraints with penalty handling.
4. Optimize using grid search, a genetic algorithm, or NSGA-II.
5. Respect a hard evaluation budget (default 1000) with result caching.
6. Persist artifacts and render convergence / Pareto plots.

## 2. Module Layout (Phase 2)

```text
src/optimization/
  __init__.py
  space.py          # DesignSpace: bounds, encode/decode, repair, sampling
  constraints.py    # ConstraintSet: area band, penalty, feasibility
  objective.py      # Evaluator: mission aggregation, caching, budget, EvalRecord
  base.py           # Optimizer ABC, OptimizationResult, better_feasible
  grid_search.py    # GridSearch (baseline reference)
  ga.py             # GeneticAlgorithm (single-objective)
  nsga2.py          # NSGA2 (multi-objective) + sorting/crowding helpers
  results.py        # save_results + convergence/Pareto plots
```

## 3. Design Space

`space.py` defines `DesignSpace`, derived from the configured bounds.

- Continuous variables (ordered): `span_m`, `root_chord_m`, `tip_chord_m`, `sweep_deg`, `twist_deg`.
- Discrete variable: airfoil index into the allowed airfoil list.
- `repair`: clips to bounds and enforces `tip_chord_m <= root_chord_m` by swapping chords, guaranteeing feasibility by construction.
- `to_parameters`: decodes a vector + airfoil index into `WingParameters`.
- Helpers for random sampling and per-dimension grid coordinates.

## 4. Objective Evaluation

`objective.py` defines the `Evaluator`.

- `build_mission`: expands a mission config block (velocities x AoA sweep) into `FlightCondition` points.
- For each design, the evaluator runs the solver across the mission and aggregates the mean CL, CD, and L/D over converged/stall-limited points.
- Single-objective cost:
  - `maximize_ld`, `maximize_cl`: cost = -metric + penalty
  - `minimize_cd`: cost = +metric + penalty
- Multi-objective vector (both minimized): `(-CL + penalty, CD + penalty)`.
- Caching: identical designs are evaluated once (keyed on rounded parameters).
- Budget: a hard `max_evaluations` cap raises `BudgetExhausted` internally, which algorithms catch to stop cleanly.

`EvalRecord` stores the design, metrics, feasibility, penalty, cost, and the multi-objective vector, and can flatten to a row for CSV export.

## 5. Constraints

`constraints.py` defines `ConstraintSet`.

- Wing-area band `[min, max]` with a configurable `penalty_weight`.
- `area_violation`: magnitude outside the band (0 if feasible).
- `penalty`: weighted violation added to objective cost.
- `is_feasible`: True when no violation.

Feasibility is treated lexicographically in single-objective comparison: feasible designs always beat infeasible ones; ties break on lower cost (`better_feasible` in `base.py`).

## 6. Algorithms

### 6.1 Grid Search (`grid`)

Exhaustive search over a per-dimension discretization (`points_per_dim`) crossed with all airfoils. Serves as a deterministic baseline reference. Stops when the budget is exhausted.

### 6.2 Genetic Algorithm (`ga`)

Real-coded GA for single-objective optimization:

- Tournament selection.
- Blend crossover (BLX-0.5) on continuous genes; uniform choice on airfoil.
- Gaussian mutation scaled to each variable's range; random airfoil reset.
- Elitism: the best individuals carry over each generation.
- Records a convergence trace (best cost per generation).
- Deterministic for a fixed seed.

### 6.3 NSGA-II (`nsga2`)

Elitist multi-objective optimizer (maximize CL, minimize CD):

- Fast non-dominated sorting into Pareto fronts.
- Crowding-distance selection to preserve diversity.
- Offspring via crossover + mutation, then environmental selection from the combined parent + offspring pool.
- Returns the final Pareto front (sorted) plus a representative best (lowest CD on the front).

## 7. Result Persistence

`results.py` `save_results` writes, per run:

- `<id>.history.csv`: every evaluation.
- `<id>.best.json`: best design parameters and metrics.
- `<id>.convergence.csv` and `.png`: single-objective convergence (GA / grid).
- `<id>.pareto.csv` and `.png`: Pareto front (NSGA-II).

Plots use a non-interactive matplotlib backend and are skipped gracefully if matplotlib is unavailable. Generated artifacts are git-ignored under `artifacts/optimization/`.

## 8. Configuration

The `optimization` block in `configs/experiment.default.yaml`:

```yaml
optimization:
  algorithm: ga                 # grid, ga, nsga2
  objective: maximize_ld        # maximize_ld, maximize_cl, minimize_cd
  max_evaluations: 1000
  output_dir: artifacts/optimization
  mission:
    air_density: 1.225
    velocities_mps: [20]
    aoa_deg_start: 0
    aoa_deg_stop: 8
    aoa_deg_step: 4
  constraints:
    wing_area_m2: [0.10, 0.90]
    penalty_weight: 100.0
  grid:
    points_per_dim: 4
  ga:
    population_size: 40
    generations: 30
    crossover_rate: 0.9
    mutation_rate: 0.2
    elite: 2
  nsga2:
    population_size: 40
    generations: 30
    crossover_rate: 0.9
    mutation_rate: 0.2
```

## 9. How to Run

```powershell
python -m src.cli.main optimize --config configs/experiment.default.yaml
```

Select the algorithm by setting `optimization.algorithm` to `grid`, `ga`, or `nsga2`.

Outputs are written to `artifacts/optimization/<experiment_id>.*`.

## 10. Validation Results

- Unit tests: 20 passed (8 new optimization tests).
- GA run: 1000 evaluations, feasible best CL=0.791, CD=0.0204, L/D=39.62, area=0.200.
- NSGA-II run: 1000 evaluations, Pareto front of 40 designs.
- Convergence and Pareto plots generated.

## 11. Exit Criteria Mapping

| Plan exit criterion | Status | Where |
|---|---|---|
| Objective functions for CL/CD/LD over mission | Met | `objective.py` |
| Constraints (area and geometry bounds) | Met | `constraints.py`, `space.repair` |
| Optimization loop with checkpointing/history | Met | algorithm modules, `results.save_results` |
| Persist history, best-so-far, convergence plots | Met | `results.py` |
| Support at least 1000 evaluations | Met | `Evaluator` budget; GA and NSGA-II runs |
| Run completes and returns best design set | Met | `OptimizationResult.best` / `.pareto` |

## 12. Tests

`tests/unit/test_optimization.py` covers:

- Design-space chord-order repair.
- Constraint penalty and feasibility.
- Grid search returns a feasible best.
- GA best cost is non-increasing across generations.
- GA determinism for a fixed seed.
- Evaluation budget is respected.
- Non-dominated sorting correctness.
- NSGA-II returns a Pareto front.

## 13. Design Notes and Deviations

- GA and NSGA-II are implemented in pure NumPy rather than PyMOO/DEAP to keep dependencies light. They share the same `Evaluator` and `DesignSpace`, so a library-backed optimizer can be swapped in later without changing the interface.
- Bayesian optimization (listed as advanced in the spec) is not included in Phase 2; it can be added as another `Optimizer` subclass.
- The standalone baseline-versus-optimized comparison report is deferred to the Phase 4 visualization work, where it fits naturally with the dashboard.

## 14. Next Steps (Phase 3 Preview)

- Build the ML feature encoder (including airfoil categorical handling).
- Train baseline surrogate regressors (Random Forest, XGBoost).
- Evaluate with RMSE, MAE, and R2 on a design-wise split.
- Add a surrogate-in-the-loop optimization mode to reduce solver calls.
