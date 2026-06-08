# Phase 3 Implementation: ML Surrogate Modeling

Status: Complete  
Commit: 103a84a  
Date: 2026-06-08

This document describes the Phase 3 machine learning surrogate: feature engineering, leakage-free dataset splitting, model factory, training and evaluation, inference, and the surrogate-in-the-loop optimization mode. It maps the work to the implementation plan's Phase 3 exit criteria.

## 1. Summary

Phase 3 trains predictive models that approximate the aerodynamic solver, reducing the number of expensive evaluations needed during optimization. Models are trained on the CFD dataset produced in Phase 1, evaluated on a held-out split, and can be plugged directly into the Phase 2 optimizer.

Key capabilities:

1. Encode wing parameters and operating conditions into a numeric feature matrix.
2. Split data by design to prevent train/test leakage.
3. Train one regressor per target (CL, CD, L/D).
4. Evaluate with RMSE, MAE, and R2, with a configurable acceptance threshold.
5. Persist a model bundle and an evaluation report.
6. Use a trained surrogate as a drop-in solver adapter (surrogate-in-the-loop).

## 2. Module Layout (Phase 3)

```text
src/ml/
  __init__.py
  features.py     # FeatureSpec, continuous + one-hot airfoil encoding
  dataset.py      # load, design-wise split, build encoded Dataset
  models.py       # model factory (RF, GBR, MLP, optional XGBoost)
  evaluate.py     # RMSE / MAE / R2 metrics and threshold check
  train.py        # SurrogateBundle, training, save/load, report
  infer.py        # single-row prediction + SurrogateAdapter
```

## 3. Feature Engineering

`features.py` defines the encoded feature layout.

- Continuous features (fixed order): `span_m`, `root_chord_m`, `tip_chord_m`, `sweep_deg`, `twist_deg`, `aoa_deg`, `velocity_mps`.
- Airfoil identity is encoded as a stable one-hot block over a sorted, de-duplicated vocabulary.
- `FeatureSpec` captures both the continuous column order and the airfoil vocabulary; persisting it with the model guarantees inference uses the exact same layout as training.
- Unknown airfoils at inference map to an all-zero one-hot block rather than erroring.

Targets default to `CL`, `CD`, and `LD`.

## 4. Dataset and Leakage-Free Split

`dataset.py` builds the training matrices.

- `load_frame`: loads the dataset from Parquet or CSV.
- `design_wise_split`: groups rows by `design_id` so all condition rows for a given wing stay together in either train or test. This prevents leakage, which would otherwise inflate scores because rows from the same design are highly correlated.
- `build_dataset`: encodes features and targets and returns a `Dataset` with `X_train`, `X_test`, and per-target `y_train` / `y_test`.

If the group column is missing, the split falls back to a shuffled row-wise split.

## 5. Model Factory

`models.py` provides estimators by name:

- `random_forest`: `RandomForestRegressor`.
- `gradient_boosting`: `GradientBoostingRegressor`.
- `mlp`: `MLPRegressor`.
- `xgboost`: `XGBRegressor`, available only when the optional `xgboost` package is installed (`available_models` reports what is usable).

Each target is modeled by an independent regressor, which keeps the design simple and lets each output be tuned or swapped separately.

## 6. Training and Evaluation

`train.py` orchestrates fitting and persistence.

- `train_surrogate`: fits one model per target on the training split, predicts on the test split, and computes metrics.
- `SurrogateBundle`: holds the per-target models plus the `FeatureSpec`; `predict` returns a dict of target arrays.
- `TrainingReport`: stores per-target metrics, sample counts, the threshold, and a pass/fail flag.
- `save_bundle`: serializes the bundle with joblib and writes the report as JSON.
- `load_bundle`: restores a saved bundle.

`evaluate.py` computes RMSE, MAE, and R2 per target and checks whether every named target meets the configured R2 threshold.

## 7. Inference and Surrogate-in-the-Loop

`infer.py` exposes the trained model to the rest of the system.

- `predict_one`: predicts CL, CD, and L/D for a single design-condition row.
- `SurrogateAdapter`: implements the same `BaseSolverAdapter` interface as a real solver, so the optimizer can call it transparently. When enabled, it replaces CFD calls during optimization, dramatically reducing evaluation cost.
- Inference forces single-threaded prediction on the underlying models, which is faster for the single-row calls made during optimization and avoids noisy parallel-backend warnings.

## 8. Configuration

The `ml` block in `configs/experiment.default.yaml`:

```yaml
ml:
  dataset_path: data/processed/surrogate_dataset.csv
  model: random_forest          # random_forest, gradient_boosting, mlp, xgboost
  targets: [CL, CD, LD]
  test_fraction: 0.2
  r2_threshold: 0.90
  model_dir: artifacts/models
  model_params:
    n_estimators: 200
```

To enable surrogate-in-the-loop optimization, add to the `optimization` block:

```yaml
optimization:
  surrogate:
    enabled: true
    model_path: artifacts/models/<bundle>.joblib
```

## 9. How to Run

Train and evaluate a surrogate:

```powershell
python -m src.cli.main train-surrogate --config configs/experiment.default.yaml
```

Override the dataset path on the command line:

```powershell
python -m src.cli.main train-surrogate --config configs/experiment.default.yaml --dataset data/processed/surrogate_dataset.csv
```

Run surrogate-assisted optimization (after enabling it in config):

```powershell
python -m src.cli.main optimize --config configs/experiment.default.yaml
```

Outputs:

- Model bundle: `artifacts/models/<name>.joblib`
- Evaluation report: `artifacts/models/<name>.report.json`

## 10. Validation Results

Trained on 1800 rows (120 designs, 1440 train / 360 test) with Random Forest:

| Target | R2 | RMSE | MAE |
|---|---|---|---|
| CL | 0.989 | 0.0574 | 0.0416 |
| CD | 0.973 | 0.0072 | 0.0042 |
| LD | 0.969 | 2.5055 | 1.6503 |

- Acceptance threshold (R2 >= 0.90): passed for all targets.
- Surrogate-in-the-loop optimization ran end-to-end using `SurrogateAdapter` instead of the solver.
- Unit tests: 24 passed (4 new ML tests).

## 11. Exit Criteria Mapping

| Plan exit criterion | Status | Where |
|---|---|---|
| Feature encoder including airfoil handling | Met | `features.py` |
| Train baseline regressors (RF and others) | Met | `models.py`, `train.py` |
| Evaluate with RMSE, MAE, R2 on design-wise split | Met | `dataset.py`, `evaluate.py` |
| Save model artifacts and evaluation reports | Met | `train.py` save_bundle |
| Surrogate-in-the-loop optimization option | Met | `infer.py`, CLI optimize surrogate block |
| Surrogate reaches target accuracy threshold | Met | report passed=True, all targets R2 >= 0.90 |

## 12. Tests

`tests/unit/test_ml.py` covers:

- Feature encoding shape and one-hot correctness.
- Design-wise split has no shared designs between train and test.
- Surrogate trains and reaches strong R2 on a synthetic, learnable dataset.
- `SurrogateAdapter` conforms to the solver interface and returns finite predictions.

## 13. Design Notes and Deviations

- One independent regressor per target instead of a single multi-output model. This keeps each output independently tunable and simplifies metric reporting; a multi-output model can be added behind the same `SurrogateBundle` interface later.
- XGBoost is optional. The factory detects availability and falls back to scikit-learn models so the pipeline runs without it.
- Gaussian Process Regression (listed as a candidate in the spec) is not included by default but can be added as another factory entry; it is most useful when paired with Bayesian optimization in a later iteration.
- Single-threaded inference is enforced in the adapter for fast per-row prediction during optimization.

## 14. Next Steps (Phase 4 Preview)

- Build the Streamlit dashboard for geometry, CFD, optimization, and ML views.
- Add an experiment browser and run comparison (baseline versus optimized).
- Add reproducibility checks using config hash and seeds.
- Finalize documentation and usage guides.
