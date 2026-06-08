"""Shared matplotlib helpers using a non-interactive backend."""

from __future__ import annotations

from pathlib import Path


def _figure(figsize=(6, 4)):
    """Create a matplotlib figure/axes with the Agg backend configured."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    return plt.subplots(figsize=figsize)


def save_or_return(fig, path: str | Path | None):
    """Save the figure to path (returning the path) or return the figure.

    Returning the figure lets the Streamlit dashboard render it directly,
    while passing a path supports headless export from the CLI.
    """
    if path is None:
        return fig
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=120, bbox_inches="tight")
    import matplotlib.pyplot as plt

    plt.close(fig)
    return out
