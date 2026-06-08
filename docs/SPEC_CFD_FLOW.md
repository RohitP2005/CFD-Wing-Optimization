# Specification: CFD Field Simulation and Flow Visualization

Version: 1.0  
Date: 2026-06-08  
Status: Proposed (not yet implemented)  
Parent: `SPEC.md` (extends FR-02 and FR-06)

This document specifies two capabilities that the current system has interface slots for but does not yet implement:

1. CFD Simulation — a higher-fidelity solver adapter that computes spatial flow fields (pressure, velocity), not just aggregate coefficients.
2. Generate Flow Visualizations — rendering of those fields (pressure contours, velocity/streamlines) and surface distributions.

## 1. Background and Gap

The shipped solver, `AnalyticAdapter` ([src/simulation/analytic_adapter.py](../src/simulation/analytic_adapter.py)), uses lifting-line and thin-airfoil approximations. It returns only `CL`, `CD`, and `LD` — no spatial field data. Consequently:

- `SimulationResult` ([src/simulation/base_adapter.py](../src/simulation/base_adapter.py)) carries coefficients plus a free-form `meta` dict, but no field artifact references.
- The performance plots in [src/visualization/plots_cfd.py](../src/visualization/plots_cfd.py) summarize coefficients only; the module docstring already notes that contour plots can be added "when a higher-fidelity adapter provides pressure/velocity fields."

The parent `SPEC.md` anticipates this: FR-02 lists "optional pressure and velocity field artifacts" and FR-06 lists "CFD fields/contours (when available)." This document turns those optional clauses into a concrete spec.

## 2. Objectives

- Add at least one field-producing solver adapter behind the existing `BaseSolverAdapter` interface.
- Extend the result contract to reference persisted field artifacts without breaking existing low-fidelity flows.
- Provide flow-field visualizations (surface pressure, pressure/velocity contours, streamlines) driven from those artifacts.
- Keep the analytic path fully working so the pipeline still runs with no external CFD dependency.

## 3. Scope

### In Scope
- A 2D airfoil-section field solver as the first field-producing adapter (fast, dependency-light, runs locally). Options: a panel method with a viscous boundary-layer coupling (XFoil-class), or a wrapper around an external solver (XFLR5/SU2) when available.
- Field artifact schema and storage (per design-condition).
- Surface `Cp` distribution plot, pressure contour, velocity-magnitude contour, and streamline plot.
- Dashboard integration: a flow-field viewer on the Performance page (or a new "Flow Fields" page).
- Graceful degradation: adapters that produce no fields simply omit field artifacts; visualizations show a clear "no field data" message.

### Out of Scope (v1 of this extension)
- Full 3D RANS/LES wing simulation as the default path (kept optional, heavy).
- Mesh generation UI and interactive 3D field manipulation.
- Transient/unsteady field animation.
- Structural/aeroelastic coupling.

## 4. Functional Requirements

### FR-CFD-01 Field-Producing Solver Adapter
The system shall provide a solver adapter that, in addition to `CL`/`CD`/`LD`, computes spatial flow fields for a design-condition and persists them as artifacts.

- Implements `BaseSolverAdapter.evaluate(geometry, condition) -> SimulationResult`.
- Populates `SimulationResult.meta` with references to written field artifacts (see FR-CFD-03).
- Reports real solver metadata: `iterations`, `residual_final`, `runtime_sec`, `status` (`converged`, `diverged`, `max_iter`, `failed`).

### FR-CFD-02 Solver Selection and Fallback
The adapter shall be selectable by name via the existing `solver.name` config key and `get_adapter` factory ([src/simulation/runner.py](../src/simulation/runner.py)).

- If an external dependency is missing, selection shall fail with a clear, actionable error, or fall back to analytic when `solver.allow_fallback: true`.
- The analytic adapter remains the default.

### FR-CFD-03 Field Artifact Contract
For each design-condition that produces fields, the system shall write:

- A surface distribution table (`x/c`, `Cp`, optional `Cf`) as CSV/Parquet.
- A field grid (coordinates plus pressure and velocity components) as a compact binary (`.npz`) or VTK file.
- A small JSON sidecar describing the artifact (paths, grid shape, units, solver, condition).

Artifacts live under `artifacts/solver/fields/<design_id>/<condition_id>/` and are git-ignored.

### FR-CFD-04 Flow Visualization
The system shall render, from a field artifact:

- Surface pressure coefficient (`Cp` vs `x/c`).
- Pressure contour over the section.
- Velocity-magnitude contour.
- Streamlines around the section.

Each renderer follows the existing `(..., path=None)` contract: save to disk when given a path, return a Matplotlib figure otherwise (for the dashboard).

### FR-CFD-05 CLI and Dashboard Integration
- The `simulate` command shall write field artifacts when the active adapter produces them, controlled by `solver.save_fields: true`.
- The `report` command shall emit flow-field figures for a selected representative design-condition when field artifacts exist.
- The dashboard shall display flow-field plots and a clear message when no field data is available.

## 5. Non-Functional Requirements

- Performance: the default field adapter should evaluate a single 2D section in seconds; field artifacts for one design-condition should stay within a few MB.
- Reproducibility: solver settings (panels, iterations, tolerances, seed if any) are recorded in run metadata and the artifact sidecar.
- Reliability: non-convergence is logged with reason and does not abort the batch (consistent with existing failure handling).
- Compatibility: no breaking change to `SimulationResult`; field references go in `meta` or a new optional field with a default, so existing tests and the analytic path are unaffected.
- Portability: visualization stays headless (Matplotlib Agg), like the rest of `src/visualization/`.

## 6. Data Contracts

### 6.1 Surface Distribution (CSV/Parquet)
```text
x_over_c, Cp, Cf(optional)
```

### 6.2 Field Sidecar (JSON)
```json
{
  "design_id": "wing_000123",
  "condition_id": "v20_a5",
  "solver": "panel2d",
  "grid_shape": [128, 96],
  "fields": ["pressure", "velocity_x", "velocity_y"],
  "units": {"pressure": "Pa", "velocity": "m/s"},
  "surface_file": "artifacts/solver/fields/wing_000123/v20_a5/surface.csv",
  "field_file": "artifacts/solver/fields/wing_000123/v20_a5/field.npz",
  "status": "converged",
  "iterations": 320,
  "residual_final": 1.0e-6,
  "runtime_sec": 4.2
}
```

### 6.3 Result Linkage
`SimulationResult.meta` gains, when fields are produced:
```json
{ "field_sidecar": "artifacts/solver/fields/wing_000123/v20_a5/field.json" }
```

## 7. Configuration Additions
`configs/experiment.default.yaml`:
```yaml
solver:
  name: analytic        # or: panel2d, xflr5, su2
  allow_fallback: true  # fall back to analytic if a field solver is unavailable
  save_fields: false    # write pressure/velocity field artifacts when supported
  fields_dir: artifacts/solver/fields
  panel2d:              # settings for the default field adapter
    n_panels: 160
    max_iter: 400
    tolerance: 1.0e-6
```

## 8. Acceptance Criteria
- A field-producing adapter is selectable and returns coefficients plus field artifacts for at least one solver.
- Field artifacts conform to the schema in section 6 and are git-ignored.
- Flow visualizations render surface `Cp`, pressure contour, velocity contour, and streamlines from a stored artifact, both to file and in the dashboard.
- The analytic path and all existing tests remain green; new behavior is additive and config-gated.
- Reproducible field outputs for a fixed config and solver settings.

## 9. Risks and Mitigations
- External solver availability/licensing → ship a self-contained `panel2d` adapter as the default field producer; treat XFLR5/SU2 as optional wrappers.
- Artifact size growth → store compact `.npz`, cap grid resolution via config, keep artifacts git-ignored.
- Performance regression in batch sweeps → field saving is opt-in (`save_fields`), defaulting off; surrogate-assisted loops bypass field generation.
- Interface drift → field references are additive (`meta`/optional field with default), preserving the existing contract and tests.

## 10. Relationship to Existing Phases
This extension is delivered as Phase 5 in `docs/IMPLEMENTATION_PLAN_CFD_FLOW.md`, building directly on the Phase 1 simulation layer and the Phase 4 visualization layer without altering Phases 1–4 behavior.
