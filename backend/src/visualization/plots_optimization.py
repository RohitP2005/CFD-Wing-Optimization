"""Optimization visualizations: convergence curve and Pareto front."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from .common import _figure, save_or_return


def plot_convergence(convergence: pd.DataFrame, path: str | Path | None = None):
    """Plot best cost versus generation or evaluation."""
    x_col = "generation" if "generation" in convergence.columns else "evaluation"
    fig, ax = _figure(figsize=(6, 4))
    ax.plot(convergence[x_col], convergence["best_cost"], marker="o", markersize=3)
    ax.set_xlabel(x_col.capitalize())
    ax.set_ylabel("Best cost (lower is better)")
    ax.set_title("Optimization convergence")
    ax.grid(True, alpha=0.3)
    return save_or_return(fig, path)


def plot_pareto(pareto: pd.DataFrame, path: str | Path | None = None):
    """Plot the Pareto front in CL-CD space."""
    fig, ax = _figure(figsize=(6, 4))
    ordered = pareto.sort_values("CD")
    ax.plot(ordered["CD"], ordered["CL"], marker="o", color="tab:blue")
    ax.set_xlabel("CD (minimize)")
    ax.set_ylabel("CL (maximize)")
    ax.set_title("Pareto front")
    ax.grid(True, alpha=0.3)
    return save_or_return(fig, path)
