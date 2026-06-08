"""CLI entry point: generate geometries and run batch simulations.

Usage:
    python -m src.cli.main generate --config configs/experiment.default.yaml
    python -m src.cli.main simulate --config configs/experiment.default.yaml
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


def build_parser() -> argparse.ArgumentParser:
    """Construct the CLI argument parser."""
    parser = argparse.ArgumentParser(prog="wing-cfd", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    for name, handler in (("generate", cmd_generate), ("simulate", cmd_simulate)):
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
