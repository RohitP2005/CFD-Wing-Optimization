"""Surrogate training: fit per-target models, evaluate, and persist a bundle."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import joblib
import numpy as np

from .dataset import Dataset
from .evaluate import meets_threshold, regression_metrics
from .features import FeatureSpec
from .models import make_model


@dataclass
class SurrogateBundle:
    """A trained surrogate: per-target models plus the feature spec."""

    model_name: str
    spec: FeatureSpec
    targets: tuple[str, ...]
    models: dict[str, object] = field(default_factory=dict)

    def predict(self, X: np.ndarray) -> dict[str, np.ndarray]:
        """Predict every target for an encoded feature matrix."""
        return {t: self.models[t].predict(X) for t in self.targets}


@dataclass
class TrainingReport:
    """Evaluation report for a trained surrogate."""

    model_name: str
    seed: int
    n_train: int
    n_test: int
    metrics: dict[str, dict[str, float]]
    passed: bool
    threshold: float

    def to_dict(self) -> dict[str, object]:
        return {
            "model_name": self.model_name,
            "seed": self.seed,
            "n_train": self.n_train,
            "n_test": self.n_test,
            "metrics": self.metrics,
            "passed": self.passed,
            "threshold": self.threshold,
        }


def train_surrogate(
    dataset: Dataset,
    model_name: str,
    *,
    seed: int = 42,
    threshold: float = 0.90,
    model_params: dict | None = None,
) -> tuple[SurrogateBundle, TrainingReport]:
    """Fit one regressor per target and evaluate on the held-out test set."""
    bundle = SurrogateBundle(
        model_name=model_name,
        spec=dataset.spec,
        targets=dataset.targets,
    )
    metrics: dict[str, dict[str, float]] = {}

    for target in dataset.targets:
        model = make_model(model_name, seed=seed, params=model_params)
        model.fit(dataset.X_train, dataset.y_train[target])
        bundle.models[target] = model

        y_pred = model.predict(dataset.X_test)
        metrics[target] = regression_metrics(dataset.y_test[target], y_pred)

    passed = meets_threshold(metrics, threshold, dataset.targets)
    report = TrainingReport(
        model_name=model_name,
        seed=seed,
        n_train=len(dataset.X_train),
        n_test=len(dataset.X_test),
        metrics=metrics,
        passed=passed,
        threshold=threshold,
    )
    return bundle, report


def save_bundle(
    bundle: SurrogateBundle,
    report: TrainingReport,
    model_dir: str | Path,
    name: str,
) -> dict[str, Path]:
    """Persist the model bundle (joblib) and the evaluation report (JSON)."""
    out_dir = Path(model_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    model_path = out_dir / f"{name}.joblib"
    joblib.dump(bundle, model_path)

    report_path = out_dir / f"{name}.report.json"
    report_path.write_text(json.dumps(report.to_dict(), indent=2), encoding="utf-8")

    return {"model": model_path, "report": report_path}


def load_bundle(model_path: str | Path) -> SurrogateBundle:
    """Load a persisted surrogate bundle."""
    return joblib.load(model_path)
