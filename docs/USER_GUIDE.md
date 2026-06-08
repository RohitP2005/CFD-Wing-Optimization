# User Guide: AI-Assisted Wing CFD and Optimization

This guide explains what the project is, how it is put together, and how to run it end to end. It is the practical companion to the formal `SPEC.md` and the phase-by-phase notes in `docs/PHASE1.md` through `docs/PHASE4.md`.

## 1. What This Project Is

This is an end-to-end system for exploring and optimizing small-UAV wing designs. Instead of hand-tuning a wing in a CAD tool and testing one shape at a time, you describe a *design space* (ranges of span, chord, sweep, twist, and a set of airfoils), and the system:

1. Generates many candidate wing geometries.
2. Evaluates each one aerodynamically over a flight mission.
3. Stores the results as a structured dataset.
4. Searches the design space for the best-performing wing.
5. Optionally trains a machine-learning surrogate to make that search far cheaper.
6. Visualizes geometry, performance, and optimization results, and verifies that runs are reproducible.

The aerodynamic "solver" is pluggable. The shipped default is a fast analytic lifting-line model, so the whole pipeline runs in seconds on a laptop with no external CFD software. Higher-fidelity solvers (XFLR5, OpenFOAM, SU2) can be added behind the same adapter interface without changing the rest of the system.

## 2. Core Concepts

| Concept | Meaning |
|---|---|
| Design variables | The numbers that define a wing: `span_m`, `root_chord_m`, `tip_chord_m`, `sweep_deg`, `twist_deg`, plus a categorical `airfoil_id`. |
| Bounds | The allowed range for each design variable, defined in `configs/bounds.default.yaml`. |
| Mission / conditions | The flight conditions a design is evaluated at: air density, a set of velocities, and a range of angles of attack. |
| Metrics | The aerodynamic outputs: lift coefficient `CL`, drag coefficient `CD`, and lift-to-drag ratio `LD`. |
| Solver adapter | A swappable component that turns a geometry + condition into metrics. The default is `analytic`. |
| Surrogate | An ML model that approximates the solver so optimization needs far fewer expensive evaluations. |
| Experiment | One full configured run, identified by a config hash and seed for reproducibility. |

## 3. How It Works (Architecture)

```text
configs/ ──► geometry ──► simulation ──► dataset ──► optimization ──► results
   │            │             │            │              │              │
 bounds     WingParameters  solver     Parquet/CSV    GA / NSGA-II    best.json
experiment   + metrics      adapter                   grid search     pareto.csv
                               │                          ▲
                               └──── ML surrogate ────────┘   (optional, cheaper)
                                          │
                                   visualization ──► figures, comparison report,
                                                     reproducibility check, dashboard
```

The codebase is organized as one package per stage:

- `src/geometry/` — parametric wing construction (`WingParameters`, NACA-4 airfoils), validation against bounds, metric computation, and Latin-Hypercube design sampling.
- `src/simulation/` — the solver adapter interface (`BaseSolverAdapter`), the analytic solver, post-processing/quality flags, and a batch runner.
- `src/dataio/` — dataset schema, Parquet/CSV storage, and run metadata/tracking (config hash, seeds, failure logs).
- `src/optimization/` — the design space, constraints, the objective `Evaluator`, and three optimizers: grid search, a genetic algorithm (single-objective), and NSGA-II (multi-objective Pareto).
- `src/ml/` — feature encoding, leakage-free design-wise splitting, a model factory (Random Forest, Gradient Boosting, MLP, optional XGBoost), training/evaluation, and a `SurrogateAdapter` that drops into the optimizer.
- `src/visualization/` — plotting, the baseline-vs-optimized report, the reproducibility verifier, and the Streamlit dashboard.
- `src/cli/main.py` — the single command-line entry point that wires every stage together.

### Why these design choices

- Adapter pattern for solvers means you can start with the fast analytic model and swap in real CFD later with no changes upstream or downstream.
- Pure-NumPy optimizers (no PyMOO/DEAP) keep dependencies light and make the GA/NSGA-II fully seed-reproducible.
- Design-wise dataset splitting prevents the surrogate from "cheating" by seeing other flight conditions of the same wing in both train and test.
- Config hash + seeds on every run make experiments reproducible and verifiable (see the `verify` command).

## 4. Installation

Requires Python 3.11+ (developed on 3.13).

```powershell
pip install -r requirements.txt
```

This installs NumPy, SciPy, Pandas, PyArrow, PyYAML, scikit-learn, joblib, Matplotlib, and Streamlit. XGBoost is optional; the ML stage falls back to scikit-learn models if it is absent.

## 5. Configuration

Two YAML files drive everything:

- `configs/bounds.default.yaml` — the design space: per-variable ranges, the airfoil list (`NACA0012`, `NACA2412`, `NACA4412`), and geometric constraints (e.g., wing area limits, tip ≤ root chord).
- `configs/experiment.default.yaml` — the experiment: solver name, sampling count, output paths, the optimization block (objective, budget, mission, constraints, GA/NSGA-II/grid settings, optional surrogate), and the ML block.

You can point any command at alternative files with `--config` and `--bounds`.

## 6. End-to-End Workflow

Run the stages in order. Each one writes artifacts the next stage (or the dashboard) can consume.

### Step 1 — Generate geometries

```powershell
python -m src.cli.main generate --config configs/experiment.default.yaml
```

Samples wing designs across the bounds and writes geometry artifacts.

### Step 2 — Simulate (build the dataset)

```powershell
python -m src.cli.main simulate --config configs/experiment.default.yaml
```

Evaluates every sampled design over the mission and writes the dataset to `data/processed/`.

### Step 3 — Optimize

```powershell
python -m src.cli.main optimize --config configs/experiment.default.yaml
```

Searches the design space with the configured optimizer. Writes the best design (`*.best.json`), a convergence curve (`*.convergence.csv`), and, for NSGA-II, a Pareto front (`*.pareto.csv`) to `artifacts/optimization/`.

### Step 4 — Train a surrogate (optional)

```powershell
python -m src.cli.main train-surrogate --config configs/experiment.default.yaml
```

Trains one regressor per metric on the dataset, evaluates on a held-out design-wise split, and writes a model bundle + report to `artifacts/models/`. To use it during optimization, enable the `surrogate` block in the config and re-run `optimize`.

### Step 5 — Report

```powershell
python -m src.cli.main report --config configs/experiment.default.yaml
```

Produces performance plots (drag polar, AoA sweep) from the latest dataset and a baseline-vs-optimized comparison (JSON, HTML, and a bar chart) in `artifacts/figures/`. The baseline is the midpoint of every design-variable range.

### Step 6 — Verify reproducibility

```powershell
python -m src.cli.main verify --config configs/experiment.default.yaml
```

Runs the configured optimization twice with the same seed and confirms the best cost matches within tolerance. Exit code 0 means reproducible, 1 means not.

### Step 7 — Explore interactively

```powershell
streamlit run src/visualization/dashboard.py
```

Opens a dashboard with four pages:

- Geometry — adjust sliders to see airfoil and planform update live.
- Performance — pick a dataset and view its polar and AoA sweeps.
- Optimization — pick a run and view convergence and the Pareto front.
- Experiments — browse all datasets, optimization runs, and surrogate reports.

## 7. Where Outputs Go

| Directory | Contents | Git-tracked? |
|---|---|---|
| `data/processed/` | Simulation datasets (CSV/Parquet) | No (generated) |
| `artifacts/geometry/` | Geometry artifacts | No |
| `artifacts/solver/` | Solver logs / metadata | No |
| `artifacts/optimization/` | `*.best.json`, `*.convergence.csv`, `*.pareto.csv` | No |
| `artifacts/models/` | Surrogate bundles + reports | No |
| `artifacts/figures/` | Report plots, comparison JSON/HTML/PNG | No |

All generated outputs are git-ignored; only source, configs, tests, and docs are versioned.

## 8. Reproducibility

Every run records a config hash and the random seed. Because geometry sampling, the optimizers, and the analytic solver are all seeded, re-running the same configuration produces identical results. The `verify` command automates this check, and the optimization stage is deterministic across machines for the analytic solver.

## 9. Example Results

Using the shipped defaults (analytic solver, GA, 1000-evaluation budget), the optimizer improved lift-to-drag substantially over the neutral baseline:

| Metric | Baseline | Optimized | Change |
|---|---|---|---|
| CL | 0.3073 | 0.7827 | +154.7% |
| CD | 0.0170 | 0.0245 | +44.0% |
| LD | 14.4797 | 33.4350 | +130.9% |

The surrogate (Random Forest) reproduced the solver closely on held-out designs (CL R² 0.989, CD R² 0.973, LD R² 0.969), making surrogate-assisted optimization viable.

## 10. Testing

Run the full unit suite:

```powershell
python -m pytest -q
```

The suite (30 tests) covers geometry, simulation, data I/O, optimization, ML, and visualization.

## 11. Extending the System

- New solver: subclass `BaseSolverAdapter` in `src/simulation/` and register it with `get_adapter`. The CLI selects it via `solver.name` in the config.
- New optimizer: subclass `Optimizer` in `src/optimization/` and wire it into the runner/`_build_optimizer` factory.
- New surrogate model: add an entry to the model factory in `src/ml/models.py`; it is picked up by `model:` in the ML config.
- New airfoil: add its NACA-4 code to the `airfoils` list in `configs/bounds.default.yaml`.

## 12. Where to Read More

- `SPEC.md` — formal requirements, architecture, and acceptance criteria.
- `IMPLEMENTATION_PLAN.md` — the phased delivery plan and quality gates.
- `docs/PHASE1.md` … `docs/PHASE4.md` — detailed notes for each implemented phase.
