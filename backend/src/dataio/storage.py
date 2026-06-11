"""Dataset persistence in Parquet (primary) and CSV (interoperability)."""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

import pandas as pd

from .schema import DATASET_COLUMNS


def build_dataframe(records: Sequence[dict[str, object]]) -> pd.DataFrame:
    """Build an ordered DataFrame from dataset records."""
    frame = pd.DataFrame(list(records))
    if frame.empty:
        return pd.DataFrame(columns=list(DATASET_COLUMNS))
    # Guarantee a stable, complete column order.
    for column in DATASET_COLUMNS:
        if column not in frame.columns:
            frame[column] = None
    return frame[list(DATASET_COLUMNS)]


def write_dataset(
    records: Sequence[dict[str, object]],
    dataset_dir: str | Path,
    name: str,
) -> dict[str, Path]:
    """Write records to Parquet and CSV; return the written paths.

    Parquet is the primary typed format; CSV is exported for interoperability.
    Falls back gracefully if a Parquet engine is unavailable.
    """
    out_dir = Path(dataset_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    frame = build_dataframe(records)

    paths: dict[str, Path] = {}

    csv_path = out_dir / f"{name}.csv"
    frame.to_csv(csv_path, index=False)
    paths["csv"] = csv_path

    parquet_path = out_dir / f"{name}.parquet"
    try:
        frame.to_parquet(parquet_path, index=False)
        paths["parquet"] = parquet_path
    except (ImportError, ValueError):
        # Parquet engine missing; CSV already written as the fallback.
        pass

    return paths
