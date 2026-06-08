# Phase 4 Implementation: Visualization, Reporting, and Hardening

Status: Complete  
Commit: 601b2b2  
Date: 2026-06-08

This document describes the Phase 4 deliverables: static plotting utilities, a baseline-versus-optimized comparison report, a reproducibility verifier, an interactive Streamlit dashboard, and the CLI commands that tie them together. It maps the work to the implementation plan's Phase 4 exit criteria.

## 1. Summary

Phase 4 makes the system's outputs visible and verifiable. It turns the raw artifacts produced by Phases 1-3 (datasets, optimization runs, surrogate models) into figures, a comparison report, and an interactive dashboard, and it adds an automated reproducibility check that re-runs an optimization with a fixed seed and confirms identical results.

Key capabilities:

1. Render geometry figures (airfoil profile, wing planform).
2. Render performance figures (drag polar, angle-of-attack sweeps).
3. Render optimization figures (convergence curve, Pareto front).
4. Compare a baseline design to the optimized design and write a JSON/HTML report plus a bar chart.
5. Verify reproducibility by running the configured optimizer twice with the same seed and comparing the best cost within a tolerance.
6. Explore the full workflow interactively in a Streamlit dashboard.
7. Drive all of the above headlessly through `report` and `verify` CLI commands.

## 2. Module Layout (Phase 4)

```text
src/visualization/
  __init__.py
  common.py             # _figure() Agg helper, save_or_return()
  plots_geometry.py     # plot_airfoil, plot_planform
  plots_cfd.py          # plot_polar, plot_aoa_sweep
  plots_optimization.py # plot_convergence, plot_pareto
  report.py             # ComparisonRow, evaluate_design, build_comparison,
                        # comparison_to_dict, write_comparison_report, plot_comparison
  reproducibility.py    # ReproResult, verify_reproducibility
  dashboard.py          # Streamlit app (Geometry / Performance / Optimization / Experiments)
```

CLI additions live in `src/cli/main.py` (`cmd_report`, `cmd_verify`, `_baseline_params`).

## 3. Plotting Foundation

`common.py` standardizes figure creation so the rest of the package stays simple and headless-safe.

- Matplotlib uses the non-interactive `Agg` backend, so plots render without a display (CI, servers, headless shells).
- `_figure(figsize)` returns a fresh `(fig, ax)` pair.
- `save_or_return(fig, path)` writes the figure to disk when a path is given, or returns the figure object when no path is given. The "return" path is what the Streamlit dashboard consumes via `st.pyplot(...)`.

This dual behavior lets every plotting function serve both the file-producing CLI and the interactive dashboard without branching logic at every call site.

## 4. Geometry, Performance, and Optimization Plots

`plots_geometry.py`:

- `plot_airfoil(airfoil_id, path=None)`: builds the airfoil from its NACA-4 code and draws the upper/lower surfaces.
- `plot_planform(params, path=None)`: draws the top-down wing planform from `WingParameters` (span, chords, sweep).

`plots_cfd.py`:

- `plot_polar(frame, path=None)`: drag polar (CL versus CD) from a results dataframe.
- `plot_aoa_sweep(frame, velocity_mps=None, path=None)`: a 1x3 panel of CL, CD, and L/D versus angle of attack, optionally filtered to a single velocity.

`plots_optimization.py`:

- `plot_convergence(convergence_df, path=None)`: best cost per generation/iteration.
- `plot_pareto(pareto_df, path=None)`: the multi-objective Pareto front (e.g., CL versus CD).

Every function follows the same `(..., path=None)` contract and returns either a path (saved) or a figure (in-memory).

## 5. Baseline-versus-Optimized Report

`report.py` quantifies the improvement the optimizer found.

- `ComparisonRow`: a dataclass holding `metric`, `baseline`, and `optimized`, with derived `delta` and `pct_change` properties.
- `evaluate_design(params, space, adapter, mission_cfg, constraints_cfg)`: evaluates a single design over the mission using the same `Evaluator` the optimizer uses, so the comparison numbers are consistent with optimization.
- `build_comparison(baseline_metrics, optimized_metrics, keys)`: assembles `ComparisonRow`s for the requested metrics (default CL, CD, LD).
- `comparison_to_dict(rows)`: serializes rows to a plain dict.
- `write_comparison_report(rows, output_dir, name)`: writes `<name>.comparison.json` and a small `<name>.comparison.html` table.
- `plot_comparison(rows, path=None)`: grouped bar chart of baseline versus optimized.

The baseline design is the midpoint of every design-variable range (`_baseline_params` in the CLI), giving a neutral reference point that does not depend on any single hand-picked design.

## 6. Reproducibility Verification

`reproducibility.py` provides the automated determinism check required by the exit criteria.

- `_build_optimizer(opt_cfg, evaluator, seed)`: constructs the configured optimizer (`grid`, `ga`, or `nsga2`) with the given seed.
- `_run_once(experiment, bounds, seed)`: builds the design space, solver adapter, and `Evaluator`, runs the optimizer once, and returns the best cost.
- `verify_reproducibility(experiment, bounds, seed, tolerance=1e-9)`: runs the optimization twice and returns a `ReproResult` whose `matched` flag is true when both runs land within `tolerance`.

Because the GA, NSGA-II, sampling, and solver are all seeded, two runs of the same config produce bit-identical costs (difference 0.0), which is the strongest possible form of the "comparable outputs" criterion.

## 7. Streamlit Dashboard

`dashboard.py` is the interactive front end. It inserts the repo root on `sys.path` so it can be launched directly with `streamlit run`.

Pages (sidebar radio):

- Geometry: interactive sliders for span, chords, sweep, twist, and airfoil; live airfoil and planform plots. Tip chord is clamped to root chord to keep designs valid.
- Performance: pick a generated dataset and view its drag polar and per-velocity AoA sweep.
- Optimization: pick a run and view its convergence curve and Pareto front (with the Pareto table).
- Experiments: a browser listing available datasets, optimization runs, and surrogate model reports.

The dashboard reads only from `data/processed/`, `artifacts/optimization/`, and `artifacts/models/`, so it reflects whatever the CLI pipeline has produced.

## 8. Configuration

Phase 4 adds one path to `configs/experiment.default.yaml`:

```yaml
paths:
  geometry_dir: artifacts/geometry
  dataset_dir: data/processed
  log_dir: artifacts/solver
  figures_dir: artifacts/figures   # report output location (new in Phase 4)
```

The `report` command reads the existing `optimization` and `solver` blocks to evaluate the baseline and optimized designs; the `verify` command reads `experiment.seed` plus the `optimization` block. No new required keys were introduced beyond `figures_dir` (which defaults to `artifacts/figures` if absent).

## 9. How to Run

Generate static figures and the comparison report:

```powershell
python -m src.cli.main report --config configs/experiment.default.yaml
```

Verify reproducibility (exit code 0 on match, 1 on mismatch):

```powershell
python -m src.cli.main verify --config configs/experiment.default.yaml
```

Launch the interactive dashboard:

```powershell
streamlit run src/visualization/dashboard.py
```

The `report` command consumes the latest `*.csv` dataset in `data/processed/` and the latest `*.best.json` in `artifacts/optimization/`; run `simulate` and `optimize` first if those are absent (both directories are git-ignored).

Outputs (under `artifacts/figures/`):

- `<name>.polar.png`, `<name>.aoa.png`
- `<name>.comparison.json`, `<name>.comparison.html`, `<name>.comparison.png`

## 10. Validation Results

`report` on the Phase 1 dataset and the latest GA optimum produced:

| Metric | Baseline | Optimized | Change |
|---|---|---|---|
| CL | 0.3073 | 0.7827 | +154.7% |
| CD | 0.0170 | 0.0245 | +44.0% |
| LD | 14.4797 | 33.4350 | +130.9% |

- `report` wrote 5 artifacts (2 performance plots, JSON, HTML, comparison chart).
- `verify` reported MATCH: run A cost = run B cost = -39.6154, difference 0.000e+00 (tol 1e-09), exit code 0.
- Unit tests: 30 passed (6 new visualization/reproducibility tests).
- Generated figures remain git-ignored (`artifacts/figures/`).

## 11. Exit Criteria Mapping

| Plan exit criterion | Status | Where |
|---|---|---|
| Dashboard pages for geometry, CFD, optimization, ML outputs | Met | `dashboard.py` (Geometry, Performance, Optimization, Experiments) |
| Experiment browser and run comparison | Met | Experiments page; `report.py` baseline vs optimized |
| Reproducibility check via config hash and seeds | Met | `reproducibility.py`, `verify` command |
| Dashboard demonstrates the full workflow end-to-end | Met | dashboard reads datasets, runs, and model reports |
| Re-run of same config/seed gives comparable outputs | Met | `verify` MATCH, difference 0.0 |
| Finalize documentation and usage guide | Met | this file and `docs/USER_GUIDE.md` |

## 12. Tests

`tests/unit/test_visualization.py` covers:

- `plot_airfoil` and `plot_planform` produce saved files.
- `plot_polar` and `plot_aoa_sweep` render from a small results dataframe.
- `plot_convergence` and `plot_pareto` render from convergence/Pareto frames.
- `build_comparison` / `ComparisonRow` math (delta and percent change) and `comparison_to_dict` ordering.
- `write_comparison_report` writes both JSON and HTML.
- `verify_reproducibility` returns `matched=True` for a fixed seed using a small evaluation budget.

## 13. Design Notes and Deviations

- The dashboard uses Streamlit plus Matplotlib only; Plotly (listed as a candidate in the spec) was kept optional to avoid an extra dependency, since the static figures already serve both the CLI and the dashboard.
- Plotting functions deliberately share one `(..., path=None)` contract so the same code serves file output and interactive rendering. This avoids a parallel set of "render" versus "save" functions.
- The reproducibility check compares the optimizer's best cost rather than the full population, which is the decision-relevant quantity and is exactly reproducible under seeding. A full-population hash could be added later if needed.
- The baseline design is the range midpoint rather than a stored "reference wing", keeping the comparison self-contained and independent of any prior run.
- All Phase 4 outputs are generated artifacts and remain git-ignored, consistent with Phases 1-3.

## 14. Project Status

With Phase 4 complete, all four implementation phases are delivered: Phase 1 (geometry, simulation, dataset), Phase 2 (optimization), Phase 3 (ML surrogate), and Phase 4 (visualization, reporting, reproducibility). See `docs/USER_GUIDE.md` for an end-to-end walkthrough of the whole system.
