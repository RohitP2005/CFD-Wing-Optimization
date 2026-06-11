"""FastAPI backend for the wing-design web application.

The frontend owns all plotting. This backend returns JSON payloads for:

- design preview (airfoil/planform coordinates and metrics)
- optimization + baseline/optimized comparison
- flow-field data for frontend contour/streamline rendering
- design persistence and project management
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Literal, Optional

import numpy as np
import yaml
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .db_service import DesignService, OptimizationService, ProjectService
from .models import get_or_create_db_session

from ..geometry.airfoil import Airfoil
from ..geometry.generator import WingParameters, generate_wing
from ..geometry.validation import Bounds, ValidationError
from ..optimization.constraints import ConstraintSet
from ..optimization.ga import GeneticAlgorithm
from ..optimization.grid_search import GridSearch
from ..optimization.nsga2 import NSGA2
from ..optimization.objective import EvalRecord, Evaluator, build_mission
from ..optimization.space import CONTINUOUS_VARS, DesignSpace
from ..simulation.base_adapter import FlightCondition, SimulationResult
from ..simulation.panel2d_adapter import Panel2DAdapter
from ..simulation.runner import get_adapter
from ..visualization.report import build_comparison

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_CONFIG = _REPO_ROOT / "configs" / "experiment.default.yaml"
_DEFAULT_BOUNDS = _REPO_ROOT / "configs" / "bounds.default.yaml"


class WingParametersModel(BaseModel):
    span_m: float
    root_chord_m: float
    tip_chord_m: float
    sweep_deg: float
    twist_deg: float
    airfoil_id: str

    def to_domain(self) -> WingParameters:
        return WingParameters(**self.model_dump())


class ConditionModel(BaseModel):
    velocity_mps: float = 20.0
    aoa_deg: float = 5.0
    air_density: float = 1.225

    def to_domain(self) -> FlightCondition:
        return FlightCondition(**self.model_dump())


class OptimizationOptionsModel(BaseModel):
    algorithm: Literal["grid", "ga", "nsga2"] = "ga"
    objective: Literal["maximize_ld", "maximize_cl", "minimize_cd"] = "maximize_ld"
    max_evaluations: int = Field(default=240, ge=10, le=5000)
    seed: int = 42
    grid_points_per_dim: int = Field(default=3, ge=2, le=8)
    population_size: int = Field(default=24, ge=4, le=200)
    generations: int = Field(default=8, ge=1, le=200)
    crossover_rate: float = Field(default=0.9, ge=0.0, le=1.0)
    mutation_rate: float = Field(default=0.2, ge=0.0, le=1.0)
    elite: int = Field(default=2, ge=0, le=20)
    solver_name: str = "analytic"
    allow_fallback: bool = True


class OptimizeWorkflowRequest(BaseModel):
    baseline: WingParametersModel
    compare_condition: ConditionModel = Field(default_factory=ConditionModel)
    optimization: OptimizationOptionsModel = Field(default_factory=OptimizationOptionsModel)
    include_flow_fields: bool = True


def _load_yaml(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def _load_defaults() -> tuple[dict, Bounds]:
    experiment = _load_yaml(_DEFAULT_CONFIG)
    bounds_cfg = _load_yaml(_DEFAULT_BOUNDS)
    return experiment, Bounds.from_config(bounds_cfg)


def _serialize_parameters(params: WingParameters) -> dict[str, object]:
    return asdict(params)


def _json_matrix(values: np.ndarray) -> list[list[float | None]]:
    matrix: list[list[float | None]] = []
    for row in np.asarray(values, dtype=float):
        matrix.append([
            None if not np.isfinite(value) else float(value)
            for value in row
        ])
    return matrix


def _serialize_geometry_payload(params: WingParameters) -> dict[str, object]:
    geometry = generate_wing(params, design_id="preview")
    airfoil = Airfoil.from_naca4(params.airfoil_id)
    x = np.linspace(0.0, 1.0, 120)
    yc = airfoil.camber_line(x)
    yt = airfoil.thickness_distribution(x)
    upper = yc + yt
    lower = yc - yt

    half = params.span_m / 2.0
    sweep = np.radians(params.sweep_deg)
    le_tip_x = half * np.tan(sweep)
    polygon_y = [0.0, half, half, 0.0, -half, -half, 0.0]
    polygon_x = [0.0, le_tip_x, le_tip_x - params.tip_chord_m, -params.root_chord_m,
                 le_tip_x - params.tip_chord_m, le_tip_x, 0.0]

    return {
        "params": _serialize_parameters(params),
        "metrics": geometry.to_record(),
        "airfoil_plot": {
            "x": x.tolist(),
            "camber_y": yc.tolist(),
            "upper_y": upper.tolist(),
            "lower_y": lower.tolist(),
        },
        "planform_plot": {
            "outline_span_y": polygon_y,
            "outline_chord_x": polygon_x,
        },
    }


def _serialize_condition_result(result: SimulationResult, wing_area_m2: float) -> dict[str, object]:
    q = 0.5 * result.condition.air_density * result.condition.velocity_mps ** 2
    return {
        "condition": {
            "velocity_mps": result.condition.velocity_mps,
            "aoa_deg": result.condition.aoa_deg,
            "air_density": result.condition.air_density,
        },
        "coefficients": {
            "CL": result.CL,
            "CD": result.CD,
            "LD": result.LD,
        },
        "forces": {
            "lift_n": q * wing_area_m2 * result.CL,
            "drag_n": q * wing_area_m2 * result.CD,
        },
        "status": result.status,
        "solver": result.solver,
    }


def _serialize_flow_field(params: WingParameters, condition: FlightCondition) -> dict[str, object]:
    geometry = generate_wing(params, design_id="flow")
    adapter = Panel2DAdapter()
    field = adapter.compute_field(geometry, condition)
    return {
        "condition_id": field.condition_id,
        "solver": field.solver,
        "grid": {
            "x": _json_matrix(field.x_grid),
            "y": _json_matrix(field.y_grid),
            "pressure": _json_matrix(field.pressure),
            "velocity_x": _json_matrix(field.velocity_x),
            "velocity_y": _json_matrix(field.velocity_y),
        },
        "surface": {
            "x": field.surface_x.tolist(),
            "cp": field.surface_cp.tolist(),
        },
        "meta": field.meta,
    }


def _build_optimizer(options: OptimizationOptionsModel, evaluator: Evaluator):
    if options.algorithm == "grid":
        return GridSearch(
            evaluator,
            seed=options.seed,
            points_per_dim=options.grid_points_per_dim,
        )
    if options.algorithm == "nsga2":
        return NSGA2(
            evaluator,
            seed=options.seed,
            population_size=options.population_size,
            generations=options.generations,
        )
    return GeneticAlgorithm(
        evaluator,
        seed=options.seed,
        population_size=options.population_size,
        generations=options.generations,
        crossover_rate=options.crossover_rate,
        mutation_rate=options.mutation_rate,
        elite=options.elite,
    )


def _serialize_eval_record(record) -> dict[str, object]:
    return {
        "params": _serialize_parameters(record.params),
        "metrics": record.metrics,
        "feasible": record.feasible,
        "penalty": record.penalty,
        "cost": record.cost,
        "objectives": {
            "obj_cl": record.objectives[0],
            "obj_cd": record.objectives[1],
        },
    }


class ProjectCreateModel(BaseModel):
    name: str
    description: Optional[str] = None


class ProjectUpdateModel(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


class DesignCreateModel(BaseModel):
    name: str
    params: WingParametersModel
    design_type: str = "baseline"
    description: Optional[str] = None


class OptimizationRunCreateModel(BaseModel):
    baseline_design_id: int
    algorithm: Literal["grid", "ga", "nsga2"] = "ga"
    objective: Literal["maximize_ld", "maximize_cl", "minimize_cd"] = "maximize_ld"
    max_evaluations: int = Field(default=240, ge=10, le=5000)
    name: Optional[str] = None
    description: Optional[str] = None


# Database dependency
def get_db() -> Session:
    db = get_or_create_db_session()
    try:
        yield db
    finally:
        db.close()


def create_app() -> FastAPI:
    app = FastAPI(
        title="Wing Design Backend",
        version="0.2.0",
        description=(
            "Backend API for wing design preview, optimization, comparison, and "
            "flow-field generation. The frontend is responsible for all plotting."
        ),
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    # Project endpoints
    @app.post("/api/projects")
    def create_project(payload: ProjectCreateModel, db: Session = Depends(get_db)) -> dict[str, object]:
        project = ProjectService.create_project(db, name=payload.name, description=payload.description)
        return {"success": True, "project": project.to_dict()}

    @app.get("/api/projects")
    def list_projects(skip: int = 0, limit: int = 50, db: Session = Depends(get_db)) -> dict[str, object]:
        projects = ProjectService.list_projects(db, skip=skip, limit=limit)
        return {"projects": [p.to_dict() for p in projects]}

    @app.get("/api/projects/{project_id}")
    def get_project(project_id: int, db: Session = Depends(get_db)) -> dict[str, object]:
        project = ProjectService.get_project(db, project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        return {"project": project.to_dict()}

    @app.put("/api/projects/{project_id}")
    def update_project(project_id: int, payload: ProjectUpdateModel, db: Session = Depends(get_db)) -> dict[str, object]:
        project = ProjectService.update_project(db, project_id, name=payload.name, description=payload.description)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        return {"success": True, "project": project.to_dict()}

    @app.delete("/api/projects/{project_id}")
    def delete_project(project_id: int, db: Session = Depends(get_db)) -> dict[str, object]:
        if not ProjectService.delete_project(db, project_id):
            raise HTTPException(status_code=404, detail="Project not found")
        return {"success": True}

    # Design endpoints
    @app.post("/api/projects/{project_id}/designs")
    def create_design(project_id: int, payload: DesignCreateModel, db: Session = Depends(get_db)) -> dict[str, object]:
        project = ProjectService.get_project(db, project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        params = payload.params.to_domain()
        geometry = generate_wing(params, design_id="design")
        design = DesignService.create_design(
            db,
            project_id,
            name=payload.name,
            params=params,
            design_type=payload.design_type,
            description=payload.description,
            metrics=geometry.to_record(),
        )
        return {"success": True, "design": design.to_dict()}

    @app.get("/api/projects/{project_id}/designs")
    def list_designs(
        project_id: int, design_type: Optional[str] = None, skip: int = 0, limit: int = 50, db: Session = Depends(get_db)
    ) -> dict[str, object]:
        project = ProjectService.get_project(db, project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        designs = DesignService.list_designs(db, project_id, design_type=design_type, skip=skip, limit=limit)
        return {"designs": [d.to_dict() for d in designs]}

    @app.get("/api/designs/{design_id}")
    def get_design(design_id: int, db: Session = Depends(get_db)) -> dict[str, object]:
        design = DesignService.get_design(db, design_id)
        if not design:
            raise HTTPException(status_code=404, detail="Design not found")
        return {"design": design.to_dict()}

    @app.put("/api/designs/{design_id}")
    def update_design(design_id: int, payload: ProjectUpdateModel, db: Session = Depends(get_db)) -> dict[str, object]:
        design = DesignService.update_design(db, design_id, name=payload.name, description=payload.description)
        if not design:
            raise HTTPException(status_code=404, detail="Design not found")
        return {"success": True, "design": design.to_dict()}

    @app.delete("/api/designs/{design_id}")
    def delete_design(design_id: int, db: Session = Depends(get_db)) -> dict[str, object]:
        if not DesignService.delete_design(db, design_id):
            raise HTTPException(status_code=404, detail="Design not found")
        return {"success": True}

    # Optimization run endpoints
    @app.post("/api/projects/{project_id}/optimization-runs")
    def create_optimization_run(project_id: int, payload: OptimizationRunCreateModel, db: Session = Depends(get_db)) -> dict[str, object]:
        project = ProjectService.get_project(db, project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        design = DesignService.get_design(db, payload.baseline_design_id)
        if not design or design.project_id != project_id:
            raise HTTPException(status_code=404, detail="Design not found in this project")
        run = OptimizationService.create_run(
            db,
            project_id=project_id,
            baseline_design_id=payload.baseline_design_id,
            algorithm=payload.algorithm,
            objective=payload.objective,
            max_evaluations=payload.max_evaluations,
            name=payload.name,
            description=payload.description,
        )
        return {"success": True, "run": run.to_dict()}

    @app.get("/api/projects/{project_id}/optimization-runs")
    def list_optimization_runs(project_id: int, skip: int = 0, limit: int = 50, db: Session = Depends(get_db)) -> dict[str, object]:
        project = ProjectService.get_project(db, project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        runs = OptimizationService.list_runs(db, project_id, skip=skip, limit=limit)
        return {"runs": [r.to_dict() for r in runs]}

    @app.get("/api/optimization-runs/{run_id}")
    def get_optimization_run(run_id: int, db: Session = Depends(get_db)) -> dict[str, object]:
        run = OptimizationService.get_run(db, run_id)
        if not run:
            raise HTTPException(status_code=404, detail="Optimization run not found")
        result = run.to_dict()
        if run.comparison_json:
            result["comparison"] = json.loads(run.comparison_json)
        if run.convergence_json:
            result["convergence"] = json.loads(run.convergence_json)
        if run.pareto_json:
            result["pareto"] = json.loads(run.pareto_json)
        return {"run": result}

    @app.delete("/api/optimization-runs/{run_id}")
    def delete_optimization_run(run_id: int, db: Session = Depends(get_db)) -> dict[str, object]:
        if not OptimizationService.delete_run(db, run_id):
            raise HTTPException(status_code=404, detail="Optimization run not found")
        return {"success": True}

    @app.get("/api/config/defaults")
    def defaults() -> dict[str, object]:
        experiment, bounds = _load_defaults()
        bounds_dict = {}
        for key, (min_val, max_val) in bounds.ranges.items():
            bounds_dict[key] = {"min": min_val, "max": max_val}

        opt_config = experiment.get("optimization", {})
        return {
            "bounds": bounds_dict,
            "airfoils": list(bounds.airfoils),
            "optimization": {
                "algorithms": ["grid", "ga", "nsga2"],
                "objectives": ["maximize_ld", "maximize_cl", "minimize_cd"],
                "defaults": {
                    "algorithm": opt_config.get("algorithm", "ga"),
                    "objective": opt_config.get("objective", "maximize_ld"),
                    "max_evaluations": opt_config.get("max_evaluations", 240),
                },
            },
        }

    @app.post("/api/wings/preview")
    def preview_wing(payload: WingParametersModel) -> dict[str, object]:
        _, bounds = _load_defaults()
        params = payload.to_domain()
        try:
            generate_wing(params, design_id="preview", bounds=bounds)
        except ValidationError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return _serialize_geometry_payload(params)

    @app.post("/api/workflows/optimize")
    def optimize_workflow(payload: OptimizeWorkflowRequest, db: Session = Depends(get_db)) -> dict[str, object]:
        experiment, bounds = _load_defaults()
        baseline = payload.baseline.to_domain()
        condition = payload.compare_condition.to_domain()

        try:
            baseline_geometry = generate_wing(baseline, design_id="baseline", bounds=bounds)
        except ValidationError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        options = payload.optimization
        space = DesignSpace.from_bounds(bounds)
        mission_cfg = experiment["optimization"]["mission"]
        constraints_cfg = experiment["optimization"].get("constraints", {})

        adapter = get_adapter(options.solver_name, allow_fallback=options.allow_fallback)
        evaluator = Evaluator(
            space=space,
            adapter=adapter,
            mission=build_mission(mission_cfg),
            objective=options.objective,
            constraints=ConstraintSet.from_config(constraints_cfg),
            max_evaluations=options.max_evaluations,
        )
        optimization_result = _build_optimizer(options, evaluator).optimize()
        if optimization_result.best is None:
            raise HTTPException(status_code=500, detail="Optimization did not produce a best design")

        optimized = optimization_result.best.params
        optimized_geometry = generate_wing(optimized, design_id="optimized", bounds=bounds)

        baseline_condition_result = adapter.evaluate(baseline_geometry, condition)
        optimized_condition_result = adapter.evaluate(optimized_geometry, condition)
        optimized_mission_record = optimization_result.best

        # Create baseline record from simulation result
        baseline_mission_record = EvalRecord(
            eval_index=0,
            params=baseline,
            metrics={"CL": baseline_condition_result.CL, "CD": baseline_condition_result.CD, "LD": baseline_condition_result.LD},
            feasible=True,
            penalty=0.0,
            cost=baseline_condition_result.LD,
            objectives=(baseline_condition_result.CL, baseline_condition_result.CD),
        )

        rows = build_comparison(
            baseline_mission_record.metrics,
            optimized_mission_record.metrics,
        )

        response: dict[str, object] = {
            "baseline": {
                **_serialize_geometry_payload(baseline),
                "mission_metrics": baseline_mission_record.metrics,
                "selected_condition": _serialize_condition_result(
                    baseline_condition_result,
                    baseline_geometry.wing_area_m2,
                ),
            },
            "optimized": {
                **_serialize_geometry_payload(optimized),
                "mission_metrics": optimized_mission_record.metrics,
                "selected_condition": _serialize_condition_result(
                    optimized_condition_result,
                    optimized_geometry.wing_area_m2,
                ),
            },
            "comparison": [
                {
                    "metric": row.metric,
                    "baseline": row.baseline,
                    "optimized": row.optimized,
                    "delta": row.delta,
                    "pct_change": row.pct_change,
                }
                for row in rows
            ],
            "optimization": {
                "algorithm": optimization_result.algorithm,
                "num_evaluations": optimization_result.num_evaluations,
                "best_cost": optimization_result.best.cost,
                "convergence": optimization_result.convergence,
                "best": _serialize_eval_record(optimization_result.best),
                "pareto": [_serialize_eval_record(record) for record in optimization_result.pareto],
            },
        }

        if payload.include_flow_fields:
            response["baseline"]["flow_field"] = _serialize_flow_field(baseline, condition)
            response["optimized"]["flow_field"] = _serialize_flow_field(optimized, condition)

        return response

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("src.web.api:app", host="0.0.0.0", port=8000, reload=False)