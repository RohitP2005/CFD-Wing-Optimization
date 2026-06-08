# Implementation Plan: CFD Field Simulation and Flow Visualization

Version: 1.0  
Date: 2026-06-08  
Status: Proposed (not yet implemented)  
Parent: `IMPLEMENTATION_PLAN.md` (adds Phase 5)  
Spec: `docs/SPEC_CFD_FLOW.md`

This plan delivers the two capabilities specified in `docs/SPEC_CFD_FLOW.md` — a field-producing CFD solver adapter and flow-field visualizations — as an additive Phase 5 on top of the existing four phases. The guiding principle is the same adapter pattern already in the codebase: add fidelity behind a stable interface without disturbing the analytic path.

## 1. Delivery Strategy

- Keep the analytic solver as the default; field generation is opt-in and config-gated.
- Introduce field artifacts as additive metadata so `SimulationResult` and existing tests are untouched.
- Ship one self-contained field adapter (`panel2d`) first so the feature works with no external CFD software; treat XFLR5/SU2 wrappers as optional follow-ons.
- Reuse the existing `(..., path=None)` plotting contract so new flow visualizations serve both the CLI and the dashboard.

## 2. New and Touched Modules

```text
src/simulation/
  fields.py            # NEW: FieldData dataclass, write_fields(), load_fields(), sidecar I/O
  panel2d_adapter.py   # NEW: default field-producing adapter (vortex-panel + thin BL)
  xflr5_adapter.py     # NEW (optional): external XFLR5 wrapper
  su2_adapter.py       # NEW (optional): external SU2 wrapper
  base_adapter.py      # TOUCH: optional field reference on SimulationResult (default None)
  runner.py            # TOUCH: register new adapters in get_adapter; honor save_fields
src/visualization/
  plots_fields.py      # NEW: plot_surface_cp, plot_pressure_contour,
                       #      plot_velocity_contour, plot_streamlines
  dashboard.py         # TOUCH: Flow Fields view / panel
src/cli/main.py        # TOUCH: simulate writes fields when enabled; report emits field plots
configs/
  experiment.default.yaml  # TOUCH: solver.save_fields, fields_dir, panel2d block
tests/unit/
  test_fields.py       # NEW: adapter + artifact + field-plot tests
```

## 3. Phase 5 Plan

### Phase 5: CFD Fields and Flow Visualization

Goals:
- Add a field-producing solver adapter and a field artifact layer.
- Render flow-field visualizations from stored artifacts.
- Integrate both into the CLI and dashboard without regressing Phases 1–4.

Tasks:
1. Define the field artifact layer (`fields.py`): `FieldData` dataclass, `.npz` field writer/loader, surface CSV writer, and JSON sidecar per `docs/SPEC_CFD_FLOW.md` section 6.
2. Implement `panel2d_adapter.py`: a vortex/source-panel section solver with a simple boundary-layer drag correction; returns `CL`/`CD`/`LD` plus a `FieldData` and real solver metadata.
3. Extend `base_adapter.py` with an optional, defaulted field reference and have `runner.run_batch` write fields when `solver.save_fields` is true.
4. Register `panel2d` (and optional `xflr5`/`su2`) in `get_adapter`, with `allow_fallback` to analytic on missing dependencies.
5. Implement `plots_fields.py`: surface `Cp`, pressure contour, velocity-magnitude contour, and streamlines, each following the save-or-return contract.
6. Wire the CLI: `simulate` persists fields when enabled; `report` emits flow-field figures for a representative design-condition when artifacts exist.
7. Add a dashboard Flow Fields view that lists available field artifacts and renders the four plot types, with a clear empty-state message.
8. Add `configs` keys (`save_fields`, `fields_dir`, `panel2d` settings) and document them.
9. Write `tests/unit/test_fields.py`.

Exit Criteria:
- `panel2d` returns coefficients plus field artifacts that match the schema and are git-ignored.
- Flow visualizations render surface `Cp`, pressure contour, velocity contour, and streamlines from a stored artifact, to file and in the dashboard.
- Analytic path and all prior tests remain green; field behavior is additive and opt-in.
- Field outputs are reproducible for a fixed solver configuration.

## 4. Work Packages

### WP-09 Field Artifact Layer
Deliverables:
- `FieldData` dataclass and serialization (`.npz` + surface table + JSON sidecar).
- Loader utilities for visualization and the dashboard.

### WP-10 Field-Producing Adapter
Deliverables:
- `panel2d_adapter.py` (default, dependency-light).
- Optional `xflr5_adapter.py` / `su2_adapter.py` stubs with availability detection.
- `get_adapter` registration and `allow_fallback` behavior.

### WP-11 Flow Visualization
Deliverables:
- `plots_fields.py` with the four renderers.
- Dashboard Flow Fields view.

### WP-12 Integration and QA
Deliverables:
- CLI `simulate`/`report` field wiring.
- Config additions and docs.
- `tests/unit/test_fields.py` and an integration smoke test through `simulate` with `save_fields: true`.

## 5. Testing Strategy

- Unit: `FieldData` round-trips through `.npz`/sidecar; `panel2d` returns finite coefficients and a well-formed field grid; each field plot saves a file; closed-surface `Cp` integrates to a lift consistent in sign with `CL`.
- Integration: `simulate --save-fields` produces artifacts for a small sample and the batch survives a forced solver failure.
- System: `report` emits flow-field figures when artifacts exist and skips cleanly when they do not.
- Regression: full existing suite stays green; analytic remains the default.

## 6. Sequencing and Dependencies

1. WP-09 (artifact layer) first — everything else consumes it.
2. WP-10 (adapter) depends on WP-09.
3. WP-11 (visualization) depends on the artifact schema (WP-09); can be built in parallel with WP-10 using a synthetic field fixture.
4. WP-12 (integration/QA) last, once adapter and plots exist.

## 7. Tooling Notes

- Default adapter uses NumPy only, keeping the "runs anywhere" property of the project.
- External solvers (XFLR5, SU2, OpenFOAM) are optional wrappers; their absence must never break the default pipeline.
- Visualization stays on the Matplotlib Agg backend, consistent with `src/visualization/common.py`.
- Field artifacts remain git-ignored under `artifacts/solver/fields/`.

## 8. Target CLI Additions

```text
python -m src.cli.main simulate --config configs/experiment.default.yaml   # with solver.save_fields: true
python -m src.cli.main report   --config configs/experiment.default.yaml   # emits flow-field figures when fields exist
streamlit run src/visualization/dashboard.py                                # Flow Fields view
```

## 9. Definition of Done (Phase 5)

- At least one field-producing adapter operational and selectable by config.
- Field artifacts written per schema and git-ignored.
- Four flow visualizations available from file and in the dashboard.
- Opt-in, additive, and non-regressive with respect to Phases 1–4.
- Documentation updated (`docs/SPEC_CFD_FLOW.md`, this plan, and a future `docs/PHASE5.md` on completion).
