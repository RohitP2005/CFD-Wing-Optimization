"""CLI entry point: generate geometries and run batch simulations.

Usage:
    python -m src.cli.main generate --config configs/experiment.default.yaml
    python -m src.cli.main simulate --config configs/experiment.default.yaml
    python -m src.cli.main optimize --config configs/experiment.default.yaml
    python -m src.cli.main train-surrogate --config configs/experiment.default.yaml
    python -m src.cli.main report --config configs/experiment.default.yaml
    python -m src.cli.main verify --config configs/experiment.default.yaml
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import yaml

from ..dataio.schema import build_record
from ..dataio.storage import write_dataset
from ..dataio.tracking import (
    config_hash,
    make_experiment_id,
    write_failure_log,
    write_run_metadata,
)
from ..geometry.generator import export_geometry, generate_wing, WingParameters
from ..geometry.sampling import sample_designs
from ..geometry.validation import Bounds
from ..ml.dataset import build_dataset, load_frame
from ..ml.infer import SurrogateAdapter
from ..ml.train import save_bundle, train_surrogate
from ..optimization.constraints import ConstraintSet
from ..optimization.ga import GeneticAlgorithm
from ..optimization.grid_search import GridSearch
from ..optimization.nsga2 import NSGA2
from ..optimization.objective import Evaluator, build_mission
from ..optimization.results import save_results
from ..optimization.space import DesignSpace
from ..simulation.runner import build_conditions, get_adapter, run_batch
from ..visualization import (
    plots_cfd,
    plots_fields,
    plots_geometry,
    plots_optimization,
)
from ..visualization.report import (
    build_comparison,
    evaluate_design,
    plot_comparison,
    write_comparison_report,
)
from ..visualization.reproducibility import verify_reproducibility

DEFAULT_BOUNDS = "configs/bounds.default.yaml"


def load_yaml(path: str | Path) -> dict[str, Any]:
    """Load a YAML file into a dictionary."""
    with open(path, "r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def _resolve(args: argparse.Namespace) -> tuple[dict, dict, Bounds]:
    experiment = load_yaml(args.config)
    bounds_path = args.bounds or DEFAULT_BOUNDS
    bounds_cfg = load_yaml(bounds_path)
    bounds = Bounds.from_config(bounds_cfg)
    return experiment, bounds_cfg, bounds


def _sample_geometries(experiment: dict, bounds: Bounds):
    sampling = experiment["sampling"]
    seed = int(experiment["experiment"]["seed"])
    designs = sample_designs(
        bounds=bounds,
        method=str(sampling.get("method", "lhs")),
        num_designs=int(sampling["num_designs"]),
        seed=seed,
    )
    geometries = []
    for index, design in enumerate(designs):
        design_id = f"wing_{index:06d}"
        geometries.append(generate_wing(design, design_id=design_id, bounds=bounds))
    return geometries


def cmd_generate(args: argparse.Namespace) -> int:
    """Sample designs, validate, and export geometry artifacts."""
    experiment, _, bounds = _resolve(args)
    geometry_dir = experiment["paths"]["geometry_dir"]
    geometries = _sample_geometries(experiment, bounds)

    for geometry in geometries:
        export_geometry(geometry, geometry_dir)

    print(f"Generated {len(geometries)} wing geometries in {geometry_dir}")
    return 0


def cmd_simulate(args: argparse.Namespace) -> int:
    """Sample designs, run the batch solver, and persist the dataset."""
    experiment, _, bounds = _resolve(args)
    exp_meta = experiment["experiment"]
    paths = experiment["paths"]
    seed = int(exp_meta["seed"])
    tag = str(exp_meta.get("tag", ""))

    cfg_hash = config_hash(experiment)
    experiment_id = make_experiment_id(str(exp_meta["name"]), cfg_hash)

    geometries = _sample_geometries(experiment, bounds)
    for geometry in geometries:
        export_geometry(geometry, paths["geometry_dir"])

    solver_cfg = experiment["solver"]
    conditions = build_conditions(experiment["conditions"])
    adapter = get_adapter(
        str(solver_cfg["name"]),
        allow_fallback=bool(solver_cfg.get("allow_fallback", False)),
    )
    save_fields = bool(solver_cfg.get("save_fields", False))
    fields_dir = solver_cfg.get("fields_dir", "artifacts/solver/fields")
    outcome = run_batch(
        geometries,
        conditions,
        adapter,
        save_fields=save_fields,
        fields_dir=fields_dir,
    )

    geometry_by_id = {g.design_id: g for g in geometries}
    records = [
        build_record(
            geometry_by_id[result.design_id],
            result,
            experiment_id=experiment_id,
            config_hash=cfg_hash,
            seed=seed,
            experiment_tag=tag,
        )
        for result in outcome.results
    ]

    dataset_paths = write_dataset(records, paths["dataset_dir"], experiment_id)
    if outcome.field_artifacts:
        print(f"  field artifacts: {len(outcome.field_artifacts)} written")
    write_failure_log(paths["log_dir"], experiment_id, outcome.failures)
    write_run_metadata(
        paths["log_dir"],
        experiment_id=experiment_id,
        config=experiment,
        cfg_hash=cfg_hash,
        seed=seed,
        num_designs=len(geometries),
        num_results=len(records),
        num_failures=len(outcome.failures),
        dataset_paths=dataset_paths,
    )

    print(
        f"Experiment {experiment_id}: {len(records)} results, "
        f"{len(outcome.failures)} failures"
    )
    for kind, path in dataset_paths.items():
        print(f"  dataset[{kind}]: {path}")
    return 0


def _build_optimizer(opt_cfg: dict, evaluator: Evaluator, seed: int):
    """Instantiate the configured optimizer."""
    algorithm = str(opt_cfg.get("algorithm", "ga"))
    if algorithm == "grid":
        grid_cfg = opt_cfg.get("grid", {})
        return GridSearch(
            evaluator, seed=seed, points_per_dim=int(grid_cfg.get("points_per_dim", 3))
        )
    if algorithm == "ga":
        ga_cfg = opt_cfg.get("ga", {})
        return GeneticAlgorithm(
            evaluator,
            seed=seed,
            population_size=int(ga_cfg.get("population_size", 40)),
            generations=int(ga_cfg.get("generations", 30)),
            crossover_rate=float(ga_cfg.get("crossover_rate", 0.9)),
            mutation_rate=float(ga_cfg.get("mutation_rate", 0.2)),
            elite=int(ga_cfg.get("elite", 2)),
        )
    if algorithm == "nsga2":
        nsga_cfg = opt_cfg.get("nsga2", {})
        return NSGA2(
            evaluator,
            seed=seed,
            population_size=int(nsga_cfg.get("population_size", 40)),
            generations=int(nsga_cfg.get("generations", 30)),
            crossover_rate=float(nsga_cfg.get("crossover_rate", 0.9)),
            mutation_rate=float(nsga_cfg.get("mutation_rate", 0.2)),
        )
    raise ValueError(f"Unknown optimization algorithm: {algorithm!r}")


def cmd_optimize(args: argparse.Namespace) -> int:
    """Run the configured optimizer and persist results."""
    experiment, _, bounds = _resolve(args)
    exp_meta = experiment["experiment"]
    seed = int(exp_meta["seed"])
    opt_cfg = experiment["optimization"]

    cfg_hash = config_hash(experiment)
    experiment_id = make_experiment_id(str(exp_meta["name"]) + "_opt", cfg_hash)

    space = DesignSpace.from_bounds(bounds)
    surrogate_cfg = opt_cfg.get("surrogate", {})
    if surrogate_cfg.get("enabled"):
        # Surrogate-in-the-loop: replace the CFD solver with a trained model.
        adapter = SurrogateAdapter.from_path(str(surrogate_cfg["model_path"]))
    else:
        adapter = get_adapter(str(experiment["solver"]["name"]))
    mission = build_mission(opt_cfg["mission"])
    constraints = ConstraintSet.from_config(opt_cfg.get("constraints", {}))
    evaluator = Evaluator(
        space=space,
        adapter=adapter,
        mission=mission,
        objective=str(opt_cfg.get("objective", "maximize_ld")),
        constraints=constraints,
        max_evaluations=int(opt_cfg.get("max_evaluations", 1000)),
    )

    optimizer = _build_optimizer(opt_cfg, evaluator, seed)
    result = optimizer.optimize()

    output_dir = opt_cfg.get("output_dir", "artifacts/optimization")
    paths = save_results(result, output_dir, experiment_id)

    print(
        f"Optimization {experiment_id} [{result.algorithm}]: "
        f"{result.num_evaluations} evaluations"
    )
    if result.best is not None:
        b = result.best
        print(
            f"  best: CL={b.metrics['CL']:.3f} CD={b.metrics['CD']:.4f} "
            f"LD={b.metrics['LD']:.2f} area={b.metrics['wing_area_m2']:.3f} "
            f"feasible={b.feasible}"
        )
    if result.pareto:
        print(f"  pareto front size: {len(result.pareto)}")
    for kind, path in paths.items():
        print(f"  {kind}: {path}")
    return 0


def cmd_train_surrogate(args: argparse.Namespace) -> int:
    """Train and evaluate an ML surrogate from a CFD dataset."""
    experiment, bounds_cfg, _ = _resolve(args)
    exp_meta = experiment["experiment"]
    seed = int(exp_meta["seed"])
    ml_cfg = experiment["ml"]

    dataset_path = args.dataset or ml_cfg["dataset_path"]
    frame = load_frame(dataset_path)

    targets = tuple(ml_cfg.get("targets", ("CL", "CD", "LD")))
    airfoils = bounds_cfg.get("airfoils")
    dataset = build_dataset(
        frame,
        airfoils=airfoils,
        targets=targets,
        test_fraction=float(ml_cfg.get("test_fraction", 0.2)),
        seed=seed,
    )

    model_name = str(ml_cfg.get("model", "random_forest"))
    threshold = float(ml_cfg.get("r2_threshold", 0.90))
    bundle, report = train_surrogate(
        dataset,
        model_name,
        seed=seed,
        threshold=threshold,
        model_params=ml_cfg.get("model_params", {}),
    )

    cfg_hash = config_hash(experiment)
    name = make_experiment_id(str(exp_meta["name"]) + "_surrogate", cfg_hash)
    model_dir = ml_cfg.get("model_dir", "artifacts/models")
    paths = save_bundle(bundle, report, model_dir, name)

    print(
        f"Surrogate {name} [{model_name}]: "
        f"train={report.n_train} test={report.n_test} passed={report.passed}"
    )
    for target in dataset.targets:
        m = report.metrics[target]
        print(
            f"  {target}: R2={m['r2']:.3f} RMSE={m['rmse']:.4f} MAE={m['mae']:.4f}"
        )
    for kind, path in paths.items():
        print(f"  {kind}: {path}")
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    """Generate static figures and a baseline-vs-optimized comparison."""
    import pandas as pd

    experiment, _, bounds = _resolve(args)
    exp_meta = experiment["experiment"]
    opt_cfg = experiment["optimization"]
    figures_dir = Path(experiment.get("paths", {}).get("figures_dir", "artifacts/figures"))
    figures_dir.mkdir(parents=True, exist_ok=True)
    cfg_hash = config_hash(experiment)
    name = make_experiment_id(str(exp_meta["name"]) + "_report", cfg_hash)

    written: list[Path] = []

    # Performance plots from the most recent dataset, if any.
    dataset_dir = Path(experiment["paths"]["dataset_dir"])
    datasets = sorted(dataset_dir.glob("*.csv"))
    if datasets:
        frame = pd.read_csv(datasets[-1])
        written.append(plots_cfd.plot_polar(frame, figures_dir / f"{name}.polar.png"))
        written.append(
            plots_cfd.plot_aoa_sweep(frame, path=figures_dir / f"{name}.aoa.png")
        )

    # Baseline vs optimized comparison using the best design, if available.
    opt_dir = Path(opt_cfg.get("output_dir", "artifacts/optimization"))
    best_files = sorted(opt_dir.glob("*.best.json"))
    if best_files:
        best_payload = json.loads(best_files[-1].read_text(encoding="utf-8"))
        if best_payload and best_payload.get("params"):
            space = DesignSpace.from_bounds(bounds)
            adapter = get_adapter(str(experiment["solver"]["name"]))
            mission_cfg = opt_cfg["mission"]
            constraints_cfg = opt_cfg.get("constraints", {})

            baseline_params = WingParameters.from_mapping(
                _baseline_params(bounds)
            )
            optimized_params = WingParameters.from_mapping(best_payload["params"])

            baseline_metrics = evaluate_design(
                baseline_params, space, adapter, mission_cfg, constraints_cfg
            )
            optimized_metrics = evaluate_design(
                optimized_params, space, adapter, mission_cfg, constraints_cfg
            )
            rows = build_comparison(baseline_metrics, optimized_metrics)
            paths = write_comparison_report(rows, figures_dir, name)
            written.extend(paths.values())
            written.append(
                plot_comparison(rows, figures_dir / f"{name}.comparison.png")
            )
            for r in rows:
                print(
                    f"  {r.metric}: baseline={r.baseline:.4f} "
                    f"optimized={r.optimized:.4f} ({r.pct_change:+.1f}%)"
                )

    # Flow-field figures from the most recent field artifact, if any.
    fields_dir = Path(
        experiment["solver"].get("fields_dir", "artifacts/solver/fields")
    )
    sidecars = sorted(fields_dir.glob("**/field.json"))
    if sidecars:
        from ..simulation.fields import load_fields

        field_data = load_fields(sidecars[-1])
        written.append(
            plots_fields.plot_surface_cp(field_data, figures_dir / f"{name}.cp.png")
        )
        written.append(
            plots_fields.plot_pressure_contour(
                field_data, figures_dir / f"{name}.pressure.png"
            )
        )
        written.append(
            plots_fields.plot_velocity_contour(
                field_data, figures_dir / f"{name}.velocity.png"
            )
        )
        written.append(
            plots_fields.plot_streamlines(
                field_data, figures_dir / f"{name}.streamlines.png"
            )
        )

    print(f"Report {name}: {len(written)} artifacts")
    for path in written:
        print(f"  {path}")
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    """Verify optimization reproducibility for a fixed seed."""
    experiment, _, bounds = _resolve(args)
    seed = int(experiment["experiment"]["seed"])
    result = verify_reproducibility(experiment, bounds, seed)
    status = "MATCH" if result.matched else "MISMATCH"
    print(f"Reproducibility: {status}")
    print(f"  run A cost: {result.run_a_cost}")
    print(f"  run B cost: {result.run_b_cost}")
    print(f"  difference: {result.difference:.3e} (tol {result.tolerance:.0e})")
    return 0 if result.matched else 1


def _baseline_params(bounds) -> dict:
    """Return a baseline design at the midpoint of each design-variable range."""
    ranges = bounds.ranges
    mid = {k: (lo + hi) / 2.0 for k, (lo, hi) in ranges.items()}
    if mid["tip_chord_m"] > mid["root_chord_m"]:
        mid["tip_chord_m"] = mid["root_chord_m"]
    airfoil = bounds.airfoils[0] if bounds.airfoils else "NACA2412"
    return {**mid, "airfoil_id": airfoil}


def build_parser() -> argparse.ArgumentParser:
    """Construct the CLI argument parser."""
    parser = argparse.ArgumentParser(prog="wing-cfd", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    for name, handler in (
        ("generate", cmd_generate),
        ("simulate", cmd_simulate),
        ("optimize", cmd_optimize),
        ("train-surrogate", cmd_train_surrogate),
        ("report", cmd_report),
        ("verify", cmd_verify),
    ):
        sp = sub.add_parser(name, help=f"{name} pipeline stage")
        sp.add_argument("--config", required=True, help="Experiment config YAML")
        sp.add_argument("--bounds", default=None, help="Bounds config YAML")
        if name == "train-surrogate":
            sp.add_argument(
                "--dataset", default=None, help="Override dataset path"
            )
        sp.set_defaults(handler=handler)

    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
