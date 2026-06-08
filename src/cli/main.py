"""CLI entry point: generate geometries and run batch simulations.

Usage:
    python -m src.cli.main generate --config configs/experiment.default.yaml
    python -m src.cli.main simulate --config configs/experiment.default.yaml
    python -m src.cli.main optimize --config configs/experiment.default.yaml
"""

from __future__ import annotations

import argparse
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
from ..geometry.generator import export_geometry, generate_wing
from ..geometry.sampling import sample_designs
from ..geometry.validation import Bounds
from ..optimization.constraints import ConstraintSet
from ..optimization.ga import GeneticAlgorithm
from ..optimization.grid_search import GridSearch
from ..optimization.nsga2 import NSGA2
from ..optimization.objective import Evaluator, build_mission
from ..optimization.results import save_results
from ..optimization.space import DesignSpace
from ..simulation.runner import build_conditions, get_adapter, run_batch

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

    conditions = build_conditions(experiment["conditions"])
    adapter = get_adapter(str(experiment["solver"]["name"]))
    outcome = run_batch(geometries, conditions, adapter)

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


def build_parser() -> argparse.ArgumentParser:
    """Construct the CLI argument parser."""
    parser = argparse.ArgumentParser(prog="wing-cfd", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    for name, handler in (
        ("generate", cmd_generate),
        ("simulate", cmd_simulate),
        ("optimize", cmd_optimize),
    ):
        sp = sub.add_parser(name, help=f"{name} pipeline stage")
        sp.add_argument("--config", required=True, help="Experiment config YAML")
        sp.add_argument("--bounds", default=None, help="Bounds config YAML")
        sp.set_defaults(handler=handler)

    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
