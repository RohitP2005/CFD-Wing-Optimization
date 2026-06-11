"""SQLAlchemy database models for wing design persistence."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, relationship

Base = declarative_base()


class Project(Base):
    """A project containing multiple wing designs and optimization runs."""

    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    designs = relationship("Design", back_populates="project", cascade="all, delete-orphan")
    optimization_runs = relationship("OptimizationRun", back_populates="project", cascade="all, delete-orphan")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


class Design(Base):
    """A wing design (baseline or optimized)."""

    __tablename__ = "designs"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)

    # Wing parameters
    span_m = Column(Float, nullable=False)
    root_chord_m = Column(Float, nullable=False)
    tip_chord_m = Column(Float, nullable=False)
    sweep_deg = Column(Float, nullable=False)
    twist_deg = Column(Float, nullable=False)
    airfoil_id = Column(String(32), nullable=False)

    # Design type
    design_type = Column(String(32), nullable=False)  # 'baseline', 'optimized', 'preliminary'

    # Metrics (mission-averaged)
    wing_area_m2 = Column(Float, nullable=True)
    aspect_ratio = Column(Float, nullable=True)
    taper_ratio = Column(Float, nullable=True)
    mean_cl = Column(Float, nullable=True)
    mean_cd = Column(Float, nullable=True)
    mean_ld = Column(Float, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    project = relationship("Project", back_populates="designs")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "project_id": self.project_id,
            "name": self.name,
            "description": self.description,
            "span_m": self.span_m,
            "root_chord_m": self.root_chord_m,
            "tip_chord_m": self.tip_chord_m,
            "sweep_deg": self.sweep_deg,
            "twist_deg": self.twist_deg,
            "airfoil_id": self.airfoil_id,
            "design_type": self.design_type,
            "wing_area_m2": self.wing_area_m2,
            "aspect_ratio": self.aspect_ratio,
            "taper_ratio": self.taper_ratio,
            "mean_cl": self.mean_cl,
            "mean_cd": self.mean_cd,
            "mean_ld": self.mean_ld,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


class OptimizationRun(Base):
    """An optimization run comparing baseline and optimized designs."""

    __tablename__ = "optimization_runs"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    baseline_design_id = Column(Integer, ForeignKey("designs.id"), nullable=False)
    optimized_design_id = Column(Integer, ForeignKey("designs.id"), nullable=True)

    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)

    # Optimization settings
    algorithm = Column(String(32), nullable=False)  # 'grid', 'ga', 'nsga2'
    objective = Column(String(64), nullable=False)  # 'maximize_ld', 'maximize_cl', 'minimize_cd'
    max_evaluations = Column(Integer, nullable=False)

    # Results
    num_evaluations = Column(Integer, nullable=True)
    best_cost = Column(Float, nullable=True)
    improvement_pct = Column(Float, nullable=True)

    # Comparison metrics (stored as JSON strings for flexibility)
    comparison_json = Column(Text, nullable=True)  # Serialized comparison data
    convergence_json = Column(Text, nullable=True)  # Serialized convergence data
    pareto_json = Column(Text, nullable=True)  # Serialized Pareto front

    status = Column(String(32), nullable=False, default="pending")  # 'pending', 'running', 'completed', 'failed'
    error_message = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)

    project = relationship("Project", back_populates="optimization_runs")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "project_id": self.project_id,
            "baseline_design_id": self.baseline_design_id,
            "optimized_design_id": self.optimized_design_id,
            "name": self.name,
            "description": self.description,
            "algorithm": self.algorithm,
            "objective": self.objective,
            "max_evaluations": self.max_evaluations,
            "num_evaluations": self.num_evaluations,
            "best_cost": self.best_cost,
            "improvement_pct": self.improvement_pct,
            "status": self.status,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


def get_or_create_db_session(db_url: str = "") -> Session:
    import os
    if not db_url:
        db_path = "/tmp/wing_design.db" if os.environ.get("VERCEL") else "./wing_design.db"
        db_url = f"sqlite:///{db_path}"
    """Create database engine and return session."""
    engine = create_engine(db_url, connect_args={"check_same_thread": False} if "sqlite" in db_url else {})
    Base.metadata.create_all(bind=engine)
    from sqlalchemy.orm import sessionmaker
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return SessionLocal()
