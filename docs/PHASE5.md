# Phase 5 Implementation: CFD Field Simulation and Flow Visualization

Status: Complete  
Commit: 4419ef8  
Date: 2026-06-08  
Spec: `docs/SPEC_CFD_FLOW.md`  
Plan: `docs/IMPLEMENTATION_PLAN_CFD_FLOW.md`

This document describes the Phase 5 deliverables: a field-producing solver adapter, a field artifact layer, flow-field visualizations, and their integration into the CLI and dashboard. It maps the work to the Phase 5 exit criteria.

## 1. Summary

Phases 1-4 produced only aggregate aerodynamic coefficients (CL, CD, LD). Phase 5 adds *spatial* flow data: a solver adapter that computes a pressure and velocity field around the wing's section, persists it as artifacts, and renders it as flow visualizations (surface pressure, pressure/velocity contours, streamlines).

The work is additive and opt-in. The analytic solver remains the default, the existing result contract is unchanged, and field generation only happens when explicitly enabled in config. This satisfies the parent spec's previously-optional clauses FR-02 ("optional pressure and velocity field artifacts") and FR-06 ("CFD fields/contours when available").

Key capabilities:

1. A `panel2d` adapter that returns the same CL/CD/LD as the analytic baseline plus a 2D flow field.
2. A field artifact layer: surface distribution CSV, compressed `.npz` field grid, and a JSON sidecar.
3. Four flow visualizations rendered from a stored artifact.
4. CLI wiring: `simulate` writes fields; `report` emits flow figures.
5. A dashboard Flow Fields page.
6. Graceful fallback and no regression to the analytic path.

## 2. Module Layout (Phase 5)

```text
src/simulation/
  fields.py            # FieldData, write_fields, load_fields (artifact contract)
  panel2d_adapter.py   # Panel2DAdapter (field-producing default)
  base_adapter.py      # TOUCH: supports_fields / compute_field defaults
  runner.py            # TOUCH: register panel2d, allow_fallback, save fields in batch
src/visualization/
  plots_fields.py      # plot_surface_cp, plot_pressure_contour,
                       # plot_velocity_contour, plot_streamlines
  dashboard.py         # TOUCH: Flow Fields page
src/cli/main.py        # TOUCH: simulate writes fields; report emits flow figures
configs/experiment.default.yaml  # TOUCH: solver field options
tests/unit/test_fields.py        # Phase 5 tests
```

## 3. Field Artifact Layer

`fields.py` defines the in-memory container and the on-disk contract.

- `FieldData`: holds the design/condition identity, the field grid (`x_grid`, `y_grid`, `pressure`, `velocity_x`, `velocity_y`), the surface distribution (`surface_x`, `surface_cp`), and solver metadata (status, iterations, residual, runtime).
- `write_fields(data, fields_dir)`: writes `surface.csv`, a compressed `field.npz`, and a `field.json` sidecar under `<fields_dir>/<design_id>/<condition_id>/`, and returns the sidecar path.
- `load_fields(sidecar_path)`: reconstructs a `FieldData` from the sidecar and its referenced files.

Coordinates are chord-normalized (x/c, y/c) and the freestream speed is normalized to 1, so pressure is stored directly as a coefficient (Cp) and velocity magnitude is relative to freestream.

## 4. Panel2D Adapter

`panel2d_adapter.py` is the default field producer. It is deliberately low fidelity and depends only on NumPy, preserving the project's "runs anywhere" property.

- Coefficients: it delegates to `AnalyticAdapter` so the reported CL/CD/LD are identical to the baseline; only the `solver` name and `meta.model` change. This keeps datasets and optimization results consistent regardless of which adapter is selected.
- Field construction (`compute_field`): the 2D potential flow around the root section is a superposition of
  - a uniform freestream at the angle of attack,
  - a bound vortex at the quarter chord sized to the section circulation via Kutta-Joukowski (`Gamma = 0.5 * CL`), giving upper-surface suction, and
  - a source near the leading edge and a sink near the trailing edge to represent thickness displacement.
- Pressure follows from the incompressible relation `Cp = 1 - |V|^2`. Grid points inside the airfoil body are masked to NaN.
- Surface Cp is sampled on a closed loop just outside the upper and lower surfaces.

`supports_fields` returns `True`, and `compute_field` accepts an optional precomputed result to avoid re-evaluating coefficients.

## 5. Adapter Registration and Fallback

`runner.py` changes:

- `panel2d` is registered alongside `analytic` in the adapter registry.
- `_load_optional_adapters()` attempts to register optional external wrappers (`xflr5`, `su2`) if their modules exist; their absence is silently ignored so the default pipeline never breaks.
- `get_adapter(name, allow_fallback=False)`: when `allow_fallback` is true and the requested adapter is unavailable, it returns the analytic baseline instead of raising (FR-CFD-02).
- `run_batch(..., save_fields=False, fields_dir=None)`: when `save_fields` is true and the adapter supports fields, it writes one artifact per case and records the sidecar paths in `BatchOutcome.field_artifacts`.

`base_adapter.py` gains a `supports_fields` property (default `False`) and a `compute_field` method (default returns `None`), so every existing adapter keeps working with no changes.

## 6. Flow Visualizations

`plots_fields.py` renders a `FieldData`, each function following the shared save-or-return contract (`path=None` returns a figure for the dashboard; a path saves a PNG for the CLI):

- `plot_surface_cp`: surface Cp versus x/c, with the conventional inverted axis.
- `plot_pressure_contour`: filled Cp contour with the section masked out.
- `plot_velocity_contour`: filled velocity-magnitude contour.
- `plot_streamlines`: streamlines colored by speed.

All plots use the Matplotlib Agg backend via `common.py`, consistent with the rest of the visualization package.

## 7. CLI and Dashboard Integration

CLI (`src/cli/main.py`):

- `simulate`: reads `solver.allow_fallback`, `solver.save_fields`, and `solver.fields_dir`; passes them to `run_batch`; prints how many field artifacts were written.
- `report`: after the performance and comparison sections, loads the most recent field sidecar (if any) and writes four flow figures (`<name>.cp.png`, `.pressure.png`, `.velocity.png`, `.streamlines.png`).

Dashboard (`dashboard.py`):

- A new Flow Fields page lists available field cases and renders the four plots in a two-column layout. When no artifacts exist it shows a clear message explaining how to produce them (`solver.name: panel2d`, `solver.save_fields: true`).

## 8. Configuration

The `solver` block in `configs/experiment.default.yaml`:

```yaml
solver:
  name: analytic              # or: panel2d, xflr5, su2
  allow_fallback: true        # fall back to analytic if a field solver is unavailable
  save_fields: false          # write pressure/velocity field artifacts (panel2d)
  fields_dir: artifacts/solver/fields
  panel2d:
    n_panels: 160
    grid_nx: 140
    grid_ny: 110
```

To produce fields, set `name: panel2d` and `save_fields: true`, then run `simulate`. Defaults keep the analytic, field-free behavior unchanged.

## 9. How to Run

Run a field-producing simulation:

```powershell
# with solver.name: panel2d and solver.save_fields: true in the config
python -m src.cli.main simulate --config configs/experiment.default.yaml
```

Generate flow-field figures from the latest artifact:

```powershell
python -m src.cli.main report --config configs/experiment.default.yaml
```

Explore fields interactively:

```powershell
streamlit run src/visualization/dashboard.py   # Flow Fields page
```

Outputs:

- Field artifacts: `artifacts/solver/fields/<design_id>/<condition_id>/` (surface.csv, field.npz, field.json)
- Flow figures: `artifacts/figures/<name>.{cp,pressure,velocity,streamlines}.png`

All generated outputs are git-ignored.

## 10. Validation Results

End-to-end run with `panel2d` on a 2-design sample (30 design-conditions):

- `simulate` wrote 30 field artifacts, 0 failures; coefficients identical to the analytic baseline.
- `report` produced 9 figures total, including the four flow visualizations.
- The pressure field shows upper-surface suction and lower-surface pressure consistent with positive lift; streamlines accelerate over the top of the section.
- Unit tests: 38 passed (8 new field/visualization tests).

## 11. Exit Criteria Mapping

| Plan exit criterion | Status | Where |
|---|---|---|
| Field-producing adapter selectable by config | Met | `panel2d_adapter.py`, `get_adapter` |
| Field artifacts conform to schema and are git-ignored | Met | `fields.py`, `artifacts/solver/fields/` |
| Flow visualizations from a stored artifact (file + dashboard) | Met | `plots_fields.py`, dashboard Flow Fields page |
| Analytic path and prior tests remain green; field behavior additive/opt-in | Met | default `analytic`, 38 tests pass |
| Reproducible field outputs for a fixed solver config | Met | deterministic potential-flow construction |

## 12. Tests

`tests/unit/test_fields.py` covers:

- `get_adapter` registers `panel2d` and reports `supports_fields`.
- `get_adapter(..., allow_fallback=True)` falls back to analytic for an unknown solver.
- `panel2d` coefficients match the analytic adapter exactly.
- `compute_field` returns a well-formed grid with finite outside-body values and negative surface Cp (suction) at positive lift.
- Field artifacts round-trip through `write_fields` / `load_fields`.
- `run_batch` writes one artifact per case for `panel2d` and none for `analytic`.
- All four flow plots save files.

## 13. Design Notes and Deviations

- The `panel2d` adapter is a potential-flow superposition, not a true panel solver or RANS. It is a fast, dependency-light stand-in chosen to deliver the field/visualization feature without external CFD software, exactly as the plan specifies. Higher-fidelity wrappers (XFLR5, SU2, OpenFOAM) plug in behind the same interface.
- Coefficients are intentionally delegated to the analytic model so that switching adapters never changes dataset or optimization numbers; only the field artifacts are new.
- Field references are carried additively (adapter methods with safe defaults, `BatchOutcome.field_artifacts`), so `SimulationResult` and all prior tests are untouched.
- Field generation is opt-in (`save_fields`, default off) to keep batch sweeps and surrogate-assisted loops fast.
- The first field is built for the wing's root section; spanwise field stacking is a natural future extension.

## 14. Project Status

With Phase 5 complete, the system now spans geometry, low-fidelity aerodynamic simulation, optimization, ML surrogate modeling, visualization/reporting/reproducibility, and field-level CFD visualization. See `docs/USER_GUIDE.md` for the end-to-end workflow and `docs/SPEC_CFD_FLOW.md` for the full field-simulation specification.
