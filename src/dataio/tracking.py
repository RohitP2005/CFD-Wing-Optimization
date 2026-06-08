"""Experiment tracking: config hashing, run metadata, and failure logs."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence


def config_hash(config: Mapping[str, Any]) -> str:
    """Return a stable short hash for a configuration mapping."""
    payload = json.dumps(config, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:12]


def make_experiment_id(name: str, cfg_hash: str) -> str:
    """Construct a unique experiment identifier from name and config hash."""
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{name}_{stamp}_{cfg_hash}"


def write_run_metadata(
    log_dir: str | Path,
    *,
    experiment_id: str,
    config: Mapping[str, Any],
    cfg_hash: str,
    seed: int,
    num_designs: int,
    num_results: int,
    num_failures: int,
    dataset_paths: Mapping[str, Any],
) -> Path:
    """Persist a run metadata record for reproducibility (Section 7)."""
    out_dir = Path(log_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    metadata = {
        "experiment_id": experiment_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "config_hash": cfg_hash,
        "seed": seed,
        "num_designs": num_designs,
        "num_results": num_results,
        "num_failures": num_failures,
        "dataset_paths": {k: str(v) for k, v in dataset_paths.items()},
        "config": config,
    }
    path = out_dir / f"{experiment_id}.run.json"
    path.write_text(json.dumps(metadata, indent=2, default=str), encoding="utf-8")
    return path


def write_failure_log(
    log_dir: str | Path,
    experiment_id: str,
    failures: Sequence[Mapping[str, Any]],
) -> Path | None:
    """Persist a failure log when any case failed; return its path or None."""
    if not failures:
        return None
    out_dir = Path(log_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{experiment_id}.failures.json"
    path.write_text(json.dumps(list(failures), indent=2, default=str), encoding="utf-8")
    return path
