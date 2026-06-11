"""Performance visualizations: polar curves and CL/CD/LD vs angle of attack.

Phase 1 ships a low-fidelity analytic solver without spatial fields, so these
plots summarize the aggregated aerodynamic coefficients. When a higher-fidelity
adapter provides pressure/velocity fields, contour plots can be added here.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from .common import _figure, save_or_return


def plot_polar(frame: pd.DataFrame, path: str | Path | None = None):
    """Plot the drag polar (CL vs CD) from a results frame."""
    fig, ax = _figure(figsize=(5, 4))
    ax.scatter(frame["CD"], frame["CL"], c="tab:blue", s=12, alpha=0.6)
    ax.set_xlabel("CD")
    ax.set_ylabel("CL")
    ax.set_title("Drag polar")
    ax.grid(True, alpha=0.3)
    return save_or_return(fig, path)


def plot_aoa_sweep(
    frame: pd.DataFrame,
    velocity_mps: float | None = None,
    path: str | Path | None = None,
):
    """Plot CL, CD, and L/D versus angle of attack.

    If a velocity is provided, only rows at that velocity are shown.
    """
    data = frame
    if velocity_mps is not None and "velocity_mps" in frame.columns:
        data = frame[frame["velocity_mps"] == velocity_mps]
    data = data.sort_values("aoa_deg")

    fig, axes = _figure(figsize=(8, 3.5))
    # _figure returns (fig, ax); build a 1x3 layout instead.
    import matplotlib.pyplot as plt

    plt.close(fig)
    fig, axs = plt.subplots(1, 3, figsize=(11, 3.2))

    grouped = data.groupby("aoa_deg", as_index=False).mean(numeric_only=True)
    axs[0].plot(grouped["aoa_deg"], grouped["CL"], marker="o", color="tab:blue")
    axs[0].set_title("CL vs AoA")
    axs[0].set_xlabel("AoA (deg)")
    axs[0].set_ylabel("CL")

    axs[1].plot(grouped["aoa_deg"], grouped["CD"], marker="o", color="tab:red")
    axs[1].set_title("CD vs AoA")
    axs[1].set_xlabel("AoA (deg)")
    axs[1].set_ylabel("CD")

    axs[2].plot(grouped["aoa_deg"], grouped["LD"], marker="o", color="tab:green")
    axs[2].set_title("L/D vs AoA")
    axs[2].set_xlabel("AoA (deg)")
    axs[2].set_ylabel("L/D")

    for ax in axs:
        ax.grid(True, alpha=0.3)
    fig.tight_layout()
    return save_or_return(fig, path)
