# AI-Assisted Wing CFD and Parametric Optimization for Small UAVs

Version: 1.0  
Date: 2026-06-08  
Owner: Project Lead

## 1. Purpose
Build an end-to-end system that automates wing design exploration for small UAVs by combining parametric geometry generation, aerodynamic simulation, optimization, and machine learning surrogate modeling.

## 2. Objectives
- Generate parameterized wing geometries.
- Run aerodynamic simulations automatically for each design.
- Compute and store CL, CD, and L/D.
- Optimize wing parameters for aerodynamic efficiency.
- Train ML surrogates to reduce expensive simulation calls.
- Visualize geometry, performance, and optimization behavior.

## 3. Scope
### In Scope (v1)
- Wing planform parameterization: span, root chord, tip chord, sweep, twist, airfoil.
- Batch simulation orchestration for velocity and AoA sweeps.
- Dataset generation with run metadata and reproducibility logs.
- Single-objective and multi-objective optimization workflows.
- Surrogate model training and validation.
- Dashboard/report visualizations.

### Out of Scope (v1)
- Full aircraft optimization (fuselage, tail, propulsion coupling).
- High-fidelity transient CFD only workflows (LES/DES) as default path.
- Structural coupling (FSI) and aeroelasticity.

## 4. Functional Requirements
### FR-01 Wing Generation
The system shall generate wing geometry from user-defined parameters:
- span_m
- root_chord_m
- tip_chord_m
- taper_ratio (optional derived)
- sweep_deg
- twist_deg
- airfoil_id

Outputs:
- wing_area_m2
- aspect_ratio
- geometry artifact path (stl/step)

### FR-02 Aerodynamic Simulation
The system shall evaluate generated wings using a solver adapter (XFLR5, OpenFOAM, or SU2).

Outputs per condition:
- CL
- CD
- LD
- solver status and convergence metadata
- optional pressure and velocity field artifacts

### FR-03 Dataset Generation
The system shall store all evaluated cases in a structured dataset with one record per design-condition pair.

### FR-04 Optimization
The system shall optimize selected objectives:
- maximize CL
- minimize CD
- maximize LD

Under constraints:
- wing area bounds
- geometric variable bounds

### FR-05 ML Surrogate
The system shall train predictive models for:
- CL
- CD
- LD

Using generated simulation data and report RMSE, MAE, and R2.

### FR-06 Visualization
The system shall provide visualizations for:
- airfoil and wing geometry
- CFD fields/contours (when available)
- optimization convergence and Pareto fronts
- baseline versus optimized comparisons

## 5. Non-Functional Requirements
### Performance
- Batch execution support for large sweeps.
- Optimization support for at least 1000 design evaluations.

### Scalability
- New airfoils can be added without core code changes.
- New optimization algorithms can be integrated through adapters.

### Reproducibility
- Every run must persist configuration, seed, and metadata.
- Every optimization run must be reproducible from stored config.

### Reliability
- Simulation failures are logged with explicit reason.
- Pipeline continues for remaining queued designs after isolated failures.

## 6. System Architecture
1. Input Parameters and Experiment Config
2. Wing Generator
3. Geometry Export
4. Solver Adapter and CFD Execution
5. Performance Metrics Extraction
6. Dataset Storage
7. Optimization Engine
8. Best Design Selection
9. Visualization
10. ML Surrogate Training and Inference

## 7. Data Contracts
### 7.1 Geometry Input Schema
```json
{
  "span_m": 1.5,
  "root_chord_m": 0.30,
  "tip_chord_m": 0.15,
  "sweep_deg": 10,
  "twist_deg": 2,
  "airfoil_id": "NACA2412"
}
```

### 7.2 Geometry Output Schema
```json
{
  "design_id": "wing_000123",
  "wing_area_m2": 0.3375,
  "aspect_ratio": 6.67,
  "geometry_file": "artifacts/geometry/wing_000123.stl"
}
```

### 7.3 CFD Output Schema
```json
{
  "design_id": "wing_000123",
  "velocity_mps": 20,
  "aoa_deg": 5,
  "CL": 1.12,
  "CD": 0.07,
  "LD": 16.0,
  "solver": "SU2",
  "status": "converged",
  "iterations": 420,
  "runtime_sec": 193
}
```

## 8. Simulation Settings
### Baseline Conditions
- Velocity: 15, 20, 25 m/s
- AoA: -5 to 15 deg
- Air density: 1.225 kg/m3

### Supported Solvers
- XFLR5 (fast/early stage)
- OpenFOAM (higher fidelity)
- SU2 (higher fidelity)

## 9. Optimization Specification
### Design Variable Bounds
- span_m: 1.0 to 2.0
- sweep_deg: 0 to 30
- twist_deg: -5 to 5
- root_chord_m: 0.15 to 0.50
- tip_chord_m: 0.05 to 0.30

### Objectives
- Primary: maximize LD
- Secondary options: maximize CL, minimize CD

### Constraints
- Wing area within configured bounds.
- tip_chord_m less than or equal to root_chord_m unless explicitly overridden.

### Algorithms
- Baseline: grid search
- Intermediate: genetic algorithm
- Advanced: NSGA-II, Bayesian optimization

## 10. ML Surrogate Specification
### Features
- span_m
- root_chord_m
- tip_chord_m
- sweep_deg
- twist_deg
- airfoil encoding
- aoa_deg
- velocity_mps

### Targets
- CL
- CD
- LD

### Candidate Models
- Random Forest
- XGBoost
- Neural Network
- Gaussian Process Regression

### Metrics
- RMSE
- MAE
- R2

Acceptance target:
- At least 0.90 R2 on held-out test data for key targets (configurable).

## 11. Storage and Logging
### Dataset Columns
span_m, root_chord_m, tip_chord_m, sweep_deg, twist_deg, airfoil_id, velocity_mps, aoa_deg, CL, CD, LD

### Required Metadata
- experiment_id
- design_id
- condition_id
- config hash
- random seed
- solver metadata
- runtime
- timestamp

Preferred storage:
- Parquet as primary
- CSV export for interoperability

## 12. Validation and Testing
### Unit
- geometry calculations
- bounds and constraints validation
- parser correctness

### Integration
- design to simulation to storage path
- batch execution with mixed pass/fail cases

### System
- optimization smoke test
- surrogate train and inference test

### Acceptance
- 1000 evaluation optimization run supported
- reproducible rerun from same config and seed
- baseline versus optimized comparison report generated

## 13. Deliverables
- Source code modules:
  - wing generation
  - simulation automation
  - optimization
  - surrogate modeling
  - visualization dashboard
- CFD dataset
- Documentation
- Demonstration workflow

## 14. Risks and Mitigations
- High CFD compute cost: use multi-fidelity and surrogate-assisted loops.
- Non-convergence: retries, QC filters, and robust failure logging.
- ML leakage: split by design_id and strict train/test boundaries.
- Overfitting: cross-validation and region-wise error analysis.

## 15. Definition of Done
- End-to-end pipeline executes from config to optimized design.
- At least one solver adapter operational.
- Measurable L/D improvement over baseline.
- Surrogate model meets acceptance threshold.
- Visual report/dashboard ready for demonstration.
