"""Model factory for surrogate regressors.

Provides scikit-learn estimators by name and an optional XGBoost backend when
the package is installed. Each target is modeled by an independent regressor.
"""

from __future__ import annotations

from typing import Any

from sklearn.ensemble import (
    GradientBoostingRegressor,
    RandomForestRegressor,
)
from sklearn.neural_network import MLPRegressor


def available_models() -> tuple[str, ...]:
    """Return the model names supported in this environment."""
    names = ["random_forest", "gradient_boosting", "mlp"]
    if _has_xgboost():
        names.append("xgboost")
    return tuple(names)


def _has_xgboost() -> bool:
    try:
        import xgboost  # noqa: F401
    except ImportError:
        return False
    return True


def make_model(name: str, seed: int = 42, params: dict[str, Any] | None = None):
    """Instantiate a single-target regressor by name."""
    params = dict(params or {})

    if name == "random_forest":
        return RandomForestRegressor(
            n_estimators=int(params.get("n_estimators", 200)),
            max_depth=params.get("max_depth"),
            min_samples_leaf=int(params.get("min_samples_leaf", 1)),
            random_state=seed,
            n_jobs=-1,
        )

    if name == "gradient_boosting":
        return GradientBoostingRegressor(
            n_estimators=int(params.get("n_estimators", 200)),
            learning_rate=float(params.get("learning_rate", 0.05)),
            max_depth=int(params.get("max_depth", 3)),
            random_state=seed,
        )

    if name == "mlp":
        return MLPRegressor(
            hidden_layer_sizes=tuple(params.get("hidden_layer_sizes", (64, 64))),
            activation=str(params.get("activation", "relu")),
            max_iter=int(params.get("max_iter", 500)),
            random_state=seed,
        )

    if name == "xgboost":
        if not _has_xgboost():
            raise ValueError("xgboost is not installed")
        from xgboost import XGBRegressor

        return XGBRegressor(
            n_estimators=int(params.get("n_estimators", 300)),
            learning_rate=float(params.get("learning_rate", 0.05)),
            max_depth=int(params.get("max_depth", 4)),
            subsample=float(params.get("subsample", 0.9)),
            random_state=seed,
            n_jobs=-1,
        )

    raise ValueError(
        f"Unknown model {name!r}. Available: {available_models()}"
    )
