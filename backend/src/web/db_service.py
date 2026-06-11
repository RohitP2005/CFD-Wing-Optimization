"""Database service layer for design persistence."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from ..geometry.generator import WingParameters
from .models import Design, OptimizationRun, Project


class ProjectService:
    """Service for project-related operations."""

    @staticmethod
    def create_project(db: Session, name: str, description: Optional[str] = None) -> Project:
        project = Project(name=name, description=description)
        db.add(project)
        db.commit()
        db.refresh(project)
        return project

    @staticmethod
    def get_project(db: Session, project_id: int) -> Optional[Project]:
        return db.query(Project).filter(Project.id == project_id).first()

    @staticmethod
    def list_projects(db: Session, skip: int = 0, limit: int = 50) -> list[Project]:
        return db.query(Project).offset(skip).limit(limit).all()

    @staticmethod
    def update_project(db: Session, project_id: int, name: Optional[str] = None, description: Optional[str] = None) -> Optional[Project]:
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            return None
        if name is not None:
            project.name = name
        if description is not None:
            project.description = description
        project.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(project)
        return project

    @staticmethod
    def delete_project(db: Session, project_id: int) -> bool:
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            return False
        db.delete(project)
        db.commit()
        return True


class DesignService:
    """Service for design-related operations."""

    @staticmethod
    def create_design(
        db: Session,
        project_id: int,
        name: str,
        params: WingParameters,
        design_type: str = "baseline",
        description: Optional[str] = None,
        metrics: Optional[dict] = None,
    ) -> Design:
        design = Design(
            project_id=project_id,
            name=name,
            description=description,
            span_m=params.span_m,
            root_chord_m=params.root_chord_m,
            tip_chord_m=params.tip_chord_m,
            sweep_deg=params.sweep_deg,
            twist_deg=params.twist_deg,
            airfoil_id=params.airfoil_id,
            design_type=design_type,
        )
        if metrics:
            design.wing_area_m2 = metrics.get("wing_area_m2")
            design.aspect_ratio = metrics.get("aspect_ratio")
            design.taper_ratio = metrics.get("taper_ratio")
            design.mean_cl = metrics.get("mean_cl")
            design.mean_cd = metrics.get("mean_cd")
            design.mean_ld = metrics.get("mean_ld")
        db.add(design)
        db.commit()
        db.refresh(design)
        return design

    @staticmethod
    def get_design(db: Session, design_id: int) -> Optional[Design]:
        return db.query(Design).filter(Design.id == design_id).first()

    @staticmethod
    def list_designs(db: Session, project_id: int, design_type: Optional[str] = None, skip: int = 0, limit: int = 50) -> list[Design]:
        query = db.query(Design).filter(Design.project_id == project_id)
        if design_type:
            query = query.filter(Design.design_type == design_type)
        return query.offset(skip).limit(limit).all()

    @staticmethod
    def update_design(db: Session, design_id: int, name: Optional[str] = None, description: Optional[str] = None) -> Optional[Design]:
        design = db.query(Design).filter(Design.id == design_id).first()
        if not design:
            return None
        if name is not None:
            design.name = name
        if description is not None:
            design.description = description
        design.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(design)
        return design

    @staticmethod
    def delete_design(db: Session, design_id: int) -> bool:
        design = db.query(Design).filter(Design.id == design_id).first()
        if not design:
            return False
        db.delete(design)
        db.commit()
        return True


class OptimizationService:
    """Service for optimization run operations."""

    @staticmethod
    def create_run(
        db: Session,
        project_id: int,
        baseline_design_id: int,
        algorithm: str,
        objective: str,
        max_evaluations: int,
        name: Optional[str] = None,
        description: Optional[str] = None,
    ) -> OptimizationRun:
        run = OptimizationRun(
            project_id=project_id,
            baseline_design_id=baseline_design_id,
            algorithm=algorithm,
            objective=objective,
            max_evaluations=max_evaluations,
            name=name or f"Opt_{baseline_design_id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
            description=description,
            status="pending",
        )
        db.add(run)
        db.commit()
        db.refresh(run)
        return run

    @staticmethod
    def get_run(db: Session, run_id: int) -> Optional[OptimizationRun]:
        return db.query(OptimizationRun).filter(OptimizationRun.id == run_id).first()

    @staticmethod
    def list_runs(db: Session, project_id: int, skip: int = 0, limit: int = 50) -> list[OptimizationRun]:
        return db.query(OptimizationRun).filter(OptimizationRun.project_id == project_id).offset(skip).limit(limit).all()

    @staticmethod
    def update_run_status(db: Session, run_id: int, status: str, error_message: Optional[str] = None) -> Optional[OptimizationRun]:
        run = db.query(OptimizationRun).filter(OptimizationRun.id == run_id).first()
        if not run:
            return None
        run.status = status
        run.error_message = error_message
        if status == "completed":
            run.completed_at = datetime.utcnow()
        db.commit()
        db.refresh(run)
        return run

    @staticmethod
    def update_run_results(
        db: Session,
        run_id: int,
        optimized_design_id: int,
        num_evaluations: int,
        best_cost: float,
        improvement_pct: float,
        comparison: Optional[list] = None,
        convergence: Optional[list] = None,
        pareto: Optional[list] = None,
    ) -> Optional[OptimizationRun]:
        run = db.query(OptimizationRun).filter(OptimizationRun.id == run_id).first()
        if not run:
            return None
        run.optimized_design_id = optimized_design_id
        run.num_evaluations = num_evaluations
        run.best_cost = best_cost
        run.improvement_pct = improvement_pct
        if comparison:
            run.comparison_json = json.dumps(comparison)
        if convergence:
            run.convergence_json = json.dumps(convergence)
        if pareto:
            run.pareto_json = json.dumps(pareto)
        run.status = "completed"
        run.completed_at = datetime.utcnow()
        db.commit()
        db.refresh(run)
        return run

    @staticmethod
    def delete_run(db: Session, run_id: int) -> bool:
        run = db.query(OptimizationRun).filter(OptimizationRun.id == run_id).first()
        if not run:
            return False
        db.delete(run)
        db.commit()
        return True
