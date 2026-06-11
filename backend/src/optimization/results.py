"""Persistence of optimization history, best design, convergence, and Pareto."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import pandas as pd

from .base import OptimizationResult


def _best_payload(result: OptimizationResult) -> dict | None:
    if result.best is None:
        return None
    best = result.best
    return {
        "algorithm": result.algorithm,
        "params": asdict(best.params),
        "metrics": best.metrics,
        "feasible": best.feasible,
        "penalty": best.penalty,
        "cost": best.cost,
    }


def save_results(
    result: OptimizationResult,
    output_dir: str | Path,
    experiment_id: str,
) -> dict[str, Path]:
    """Persist all optimization artifacts and return written paths."""
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    paths: dict[str, Path] = {}

    # Full evaluation history.
    history_rows = [record.to_row() for record in result.history]
    history_df = pd.DataFrame(history_rows)
    history_path = out_dir / f"{experiment_id}.history.csv"
    history_df.to_csv(history_path, index=False)
    paths["history"] = history_path

    # Best design summary.
    best_payload = _best_payload(result)
    best_path = out_dir / f"{experiment_id}.best.json"
    best_path.write_text(json.dumps(best_payload, indent=2), encoding="utf-8")
    paths["best"] = best_path

    # Convergence trace (single-objective algorithms).
    if result.convergence:
        conv_path = out_dir / f"{experiment_id}.convergence.csv"
        pd.DataFrame(result.convergence).to_csv(conv_path, index=False)
        paths["convergence"] = conv_path
        _maybe_plot_convergence(result, out_dir / f"{experiment_id}.convergence.png", paths)

    # Pareto front (multi-objective algorithms).
    if result.pareto:
        pareto_rows = [record.to_row() for record in result.pareto]
        pareto_path = out_dir / f"{experiment_id}.pareto.csv"
        pd.DataFrame(pareto_rows).to_csv(pareto_path, index=False)
        paths["pareto"] = pareto_path
        _maybe_plot_pareto(result, out_dir / f"{experiment_id}.pareto.png", paths)

    return paths


def _maybe_plot_convergence(
    result: OptimizationResult, path: Path, paths: dict[str, Path]
) -> None:
    """Render a convergence curve if matplotlib is available."""
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return

    xs = [row.get("generation", row.get("evaluation", i)) for i, row in enumerate(result.convergence)]
    ys = [row["best_cost"] for row in result.convergence]
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.plot(xs, ys, marker="o", markersize=3)
    ax.set_xlabel("Generation / Evaluation")
    ax.set_ylabel("Best cost (lower is better)")
    ax.set_title(f"Convergence: {result.algorithm}")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)
    paths["convergence_plot"] = path


def _maybe_plot_pareto(
    result: OptimizationResult, path: Path, paths: dict[str, Path]
) -> None:
    """Render a Pareto front scatter if matplotlib is available."""
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return

    cls = [r.metrics["CL"] for r in result.pareto]
    cds = [r.metrics["CD"] for r in result.pareto]
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.scatter(cds, cls, c="tab:blue")
    ax.set_xlabel("CD (minimize)")
    ax.set_ylabel("CL (maximize)")
    ax.set_title("Pareto front")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)
    paths["pareto_plot"] = path
