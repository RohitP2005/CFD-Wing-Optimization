# Implementation Plan

Version: 1.0  
Date: 2026-06-08

## 1. Delivery Strategy
Use a phased approach that delivers a usable system quickly and increases fidelity over time.

- Phase 1: Core pipeline with simplified or low-fidelity solver.
- Phase 2: Optimization and data scaling.
- Phase 3: Surrogate-assisted optimization and dashboard hardening.

## 2. Proposed Repository Structure
```text
cfd-uav-wing/
  configs/
    experiment.default.yaml
    bounds.default.yaml
  data/
    raw/
    processed/
  artifacts/
    geometry/
    solver/
    figures/
    models/
  src/
    geometry/
      generator.py
      airfoil.py
      validation.py
    simulation/
      base_adapter.py
      xflr5_adapter.py
      openfoam_adapter.py
      su2_adapter.py
      runner.py
      postprocess.py
    optimization/
      objective.py
      constraints.py
      grid_search.py
      ga.py
      nsga2.py
      bayes_opt.py
    ml/
      features.py
      train.py
      evaluate.py
      infer.py
    visualization/
      plots_geometry.py
      plots_cfd.py
      plots_optimization.py
      dashboard.py
    dataio/
      schema.py
      storage.py
      tracking.py
    cli/
      main.py
  tests/
    unit/
    integration/
    system/
  requirements.txt
  README.md
```

## 3. Phase Plan
## Phase 1: Foundation and Baseline (Week 1 to Week 2)
Goals:
- Build geometry module and validation.
- Define data schemas and storage paths.
- Add baseline simulation adapter.
- Implement CLI pipeline for single and batch runs.

Tasks:
1. Create parameter schema and bounds checks.
2. Implement geometry generator and derived metrics.
3. Implement simulation adapter interface and one concrete adapter.
4. Implement parser for CL, CD, LD extraction.
5. Write records to Parquet and CSV.
6. Add experiment config loading and run metadata logging.

Exit Criteria:
- One command executes batch simulation and produces dataset rows.
- Failed runs are logged and do not crash entire batch.

## Phase 2: Optimization Engine (Week 3 to Week 5)
Goals:
- Introduce objective and constraints framework.
- Implement grid search and GA.
- Add NSGA-II option for multi-objective mode.

Tasks:
1. Build objective functions for CL/CD/LD over mission profile.
2. Implement constraints (area and geometry bounds).
3. Add optimization loop with checkpointing.
4. Persist history, best-so-far, and convergence plots.
5. Support at least 1000 evaluations.

Exit Criteria:
- Optimization run completes and returns best design set.
- Baseline versus optimized comparison report generated.

## Phase 3: Surrogate Modeling (Week 6 to Week 8)
Goals:
- Train surrogate models and validate performance.
- Integrate surrogate-assisted optimization mode.

Tasks:
1. Build feature encoder (including airfoil categorical handling).
2. Train baseline regressors (RF and XGBoost).
3. Evaluate with RMSE, MAE, R2 on design-wise split.
4. Save model artifacts and evaluation reports.
5. Add surrogate-in-the-loop optimization option.

Exit Criteria:
- Surrogate reaches target accuracy threshold in config.
- Surrogate-assisted mode reduces expensive solver calls.

## Phase 4: Visualization and Hardening (Week 9 to Week 10)
Goals:
- Deliver dashboard and final reproducibility checks.
- Stabilize pipeline for demo and report.

Tasks:
1. Build Streamlit dashboard pages for geometry, CFD, optimization, and ML.
2. Add experiment browser and run comparison views.
3. Add reproducibility checks using config hash and seeds.
4. Finalize documentation and usage guides.

Exit Criteria:
- Dashboard demonstrates full workflow.
- Re-run of same config/seed gives comparable outputs.

## 4. Work Packages
### WP-01 Configuration and Validation
Deliverables:
- Experiment config schema
- Bounds config
- Validation utilities

### WP-02 Geometry Engine
Deliverables:
- Parametric geometry generator
- Metric calculator (area, AR, taper)
- Geometry artifact exporter

### WP-03 Simulation Orchestration
Deliverables:
- Adapter interface
- At least one working adapter
- Batch runner and postprocessing

### WP-04 Data Layer and Tracking
Deliverables:
- Structured dataset writer
- Metadata logger
- Failure log with reasons

### WP-05 Optimization
Deliverables:
- Objective and constraints package
- Grid and GA implementation
- NSGA-II integration

### WP-06 ML Surrogate
Deliverables:
- Feature engineering pipeline
- Training and evaluation scripts
- Model registry folder structure

### WP-07 Visualization
Deliverables:
- Static plots
- Dashboard with run comparison
- Baseline versus optimized report view

### WP-08 QA and Testing
Deliverables:
- Unit, integration, and smoke test suites
- Acceptance checklist execution report

## 5. Recommended Tooling
- Python
- NumPy, SciPy, Pandas
- PyMOO, DEAP, SciPy Optimize
- Scikit-learn, XGBoost
- Matplotlib, Plotly, Streamlit
- PyArrow for Parquet
- Hydra or pydantic for config management (optional but recommended)

## 6. Execution Commands (Target CLI)
Example command set to implement:
- python -m src.cli.main generate --config configs/experiment.default.yaml
- python -m src.cli.main simulate --config configs/experiment.default.yaml
- python -m src.cli.main optimize --config configs/experiment.default.yaml
- python -m src.cli.main train-surrogate --config configs/experiment.default.yaml
- python -m src.cli.main report --config configs/experiment.default.yaml

## 7. Quality Gates
Before advancing phase:
1. Tests for current phase pass.
2. Artifacts are generated in expected directories.
3. Run metadata complete (config hash, seed, status, runtime).
4. Documentation updated.

## 8. Acceptance Checklist
- Functional requirements FR-01 through FR-06 implemented.
- 1000 evaluation optimization path demonstrated.
- Reproducible run confirmed using same config and seed.
- Surrogate performance meets configured threshold.
- End-to-end demo and comparison outputs produced.

## 9. Immediate Next Actions
1. Initialize repository structure and base package layout.
2. Create config schemas and sample experiment config.
3. Implement geometry module plus unit tests.
4. Implement one simulation adapter and batch runner.
5. Produce first dataset and verify logging format.
