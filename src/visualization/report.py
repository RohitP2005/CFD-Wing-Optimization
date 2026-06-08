"""Baseline-versus-optimized comparison reporting."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from ..geometry.generator import WingParameters
from ..optimization.constraints import ConstraintSet
from ..optimization.objective import Evaluator, build_mission
from ..optimization.space import DesignSpace
from ..simulation.base_adapter import BaseSolverAdapter


@dataclass
class ComparisonRow:
    """One metric compared between baseline and optimized designs."""

    metric: str
    baseline: float
    optimized: float

    @property
    def delta(self) -> float:
        return self.optimized - self.baseline

    @property
    def pct_change(self) -> float:
        if self.baseline == 0:
            return 0.0
        return 100.0 * self.delta / abs(self.baseline)


def evaluate_design(
    params: WingParameters,
    space: DesignSpace,
    adapter: BaseSolverAdapter,
    mission_cfg: dict,
    constraints_cfg: dict,
) -> dict[str, float]:
    """Evaluate a single design over the mission and return its metrics."""
    evaluator = Evaluator(
        space=space,
        adapter=adapter,
        mission=build_mission(mission_cfg),
        objective="maximize_ld",
        constraints=ConstraintSet.from_config(constraints_cfg),
        max_evaluations=10,
    )
    record = evaluator.evaluate(params)
    return record.metrics


def build_comparison(
    baseline_metrics: dict[str, float],
    optimized_metrics: dict[str, float],
    keys: tuple[str, ...] = ("CL", "CD", "LD"),
) -> list[ComparisonRow]:
    """Build comparison rows for the requested metric keys."""
    return [
        ComparisonRow(
            metric=key,
            baseline=float(baseline_metrics.get(key, 0.0)),
            optimized=float(optimized_metrics.get(key, 0.0)),
        )
        for key in keys
    ]


def comparison_to_dict(rows: list[ComparisonRow]) -> dict[str, object]:
    """Serialize comparison rows into a plain dict structure."""
    return {
        "comparison": [
            {
                "metric": r.metric,
                "baseline": r.baseline,
                "optimized": r.optimized,
                "delta": r.delta,
                "pct_change": r.pct_change,
            }
            for r in rows
        ]
    }


def write_comparison_report(
    rows: list[ComparisonRow],
    output_dir: str | Path,
    name: str,
) -> dict[str, Path]:
    """Write the comparison as JSON and a small HTML table."""
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = comparison_to_dict(rows)

    json_path = out_dir / f"{name}.comparison.json"
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    html_rows = "\n".join(
        f"<tr><td>{r.metric}</td><td>{r.baseline:.4f}</td>"
        f"<td>{r.optimized:.4f}</td><td>{r.delta:+.4f}</td>"
        f"<td>{r.pct_change:+.1f}%</td></tr>"
        for r in rows
    )
    html = (
        "<html><head><meta charset='utf-8'>"
        "<title>Baseline vs Optimized</title></head><body>"
        "<h2>Baseline vs Optimized</h2>"
        "<table border='1' cellpadding='6' cellspacing='0'>"
        "<tr><th>Metric</th><th>Baseline</th><th>Optimized</th>"
        "<th>Delta</th><th>% Change</th></tr>"
        f"{html_rows}</table></body></html>"
    )
    html_path = out_dir / f"{name}.comparison.html"
    html_path.write_text(html, encoding="utf-8")

    return {"json": json_path, "html": html_path}


def plot_comparison(rows: list[ComparisonRow], path: str | Path | None = None):
    """Render a grouped bar chart comparing baseline and optimized metrics."""
    from .common import _figure, save_or_return

    metrics = [r.metric for r in rows]
    baseline = [r.baseline for r in rows]
    optimized = [r.optimized for r in rows]

    fig, ax = _figure(figsize=(6, 4))
    import numpy as np

    x = np.arange(len(metrics))
    width = 0.35
    ax.bar(x - width / 2, baseline, width, label="baseline", color="tab:gray")
    ax.bar(x + width / 2, optimized, width, label="optimized", color="tab:green")
    ax.set_xticks(x)
    ax.set_xticklabels(metrics)
    ax.set_title("Baseline vs Optimized")
    ax.legend()
    ax.grid(True, axis="y", alpha=0.3)
    return save_or_return(fig, path)
