"""Dataset loading and leakage-free train/test splitting for the surrogate."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from .features import TARGETS, FeatureSpec, build_feature_spec, encode_frame


@dataclass
class Dataset:
    """Encoded train/test matrices plus the originating frames and spec."""

    spec: FeatureSpec
    targets: tuple[str, ...]
    X_train: np.ndarray
    X_test: np.ndarray
    y_train: dict[str, np.ndarray]
    y_test: dict[str, np.ndarray]
    train_frame: pd.DataFrame
    test_frame: pd.DataFrame


def load_frame(dataset_path: str | Path) -> pd.DataFrame:
    """Load a dataset from Parquet or CSV based on file extension."""
    path = Path(dataset_path)
    if path.suffix == ".parquet":
        return pd.read_parquet(path)
    if path.suffix == ".csv":
        return pd.read_csv(path)
    raise ValueError(f"Unsupported dataset format: {path.suffix!r}")


def design_wise_split(
    frame: pd.DataFrame,
    test_fraction: float,
    seed: int,
    group_column: str = "design_id",
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Split rows by design group so no design appears in both partitions.

    This prevents leakage: all condition rows for a given wing stay together.
    Falls back to a row-wise split when the group column is absent.
    """
    rng = np.random.default_rng(seed)
    if group_column not in frame.columns:
        shuffled = frame.sample(frac=1.0, random_state=seed).reset_index(drop=True)
        cut = int(round(len(shuffled) * (1.0 - test_fraction)))
        return shuffled.iloc[:cut].copy(), shuffled.iloc[cut:].copy()

    groups = np.asarray(frame[group_column].dropna().unique())
    rng.shuffle(groups)
    cut = int(round(len(groups) * (1.0 - test_fraction)))
    train_groups = set(groups[:cut])

    train_mask = frame[group_column].isin(train_groups)
    return frame[train_mask].copy(), frame[~train_mask].copy()


def build_dataset(
    frame: pd.DataFrame,
    *,
    airfoils: list[str] | None = None,
    targets: tuple[str, ...] = TARGETS,
    test_fraction: float = 0.2,
    seed: int = 42,
) -> Dataset:
    """Encode features/targets and produce a leakage-free train/test split."""
    if airfoils is None:
        airfoils = sorted(frame.get("airfoil_id", pd.Series(dtype=str)).astype(str).unique())
    spec = build_feature_spec(airfoils)

    train_frame, test_frame = design_wise_split(frame, test_fraction, seed)

    X_train = encode_frame(train_frame, spec)
    X_test = encode_frame(test_frame, spec)
    y_train = {t: train_frame[t].to_numpy(dtype=float) for t in targets}
    y_test = {t: test_frame[t].to_numpy(dtype=float) for t in targets}

    return Dataset(
        spec=spec,
        targets=tuple(targets),
        X_train=X_train,
        X_test=X_test,
        y_train=y_train,
        y_test=y_test,
        train_frame=train_frame,
        test_frame=test_frame,
    )
