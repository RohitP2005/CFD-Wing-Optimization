"""Streamlit dashboard for the wing CFD and optimization workflow.

Run with:
    streamlit run src/visualization/dashboard.py

Pages:
    - Geometry: airfoil profile and wing planform.
    - Performance: drag polar and AoA sweeps from a dataset.
    - Optimization: convergence and Pareto front from a run.
    - Experiments: browse generated runs and datasets.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

# Allow running directly via `streamlit run` by adding the repo root to sys.path.
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from src.geometry.generator import WingParameters  # noqa: E402
from src.simulation.fields import load_fields  # noqa: E402
from src.visualization import (  # noqa: E402
    plots_cfd,
    plots_fields,
    plots_geometry,
    plots_optimization,
)

DATASET_DIR = _REPO_ROOT / "data" / "processed"
OPT_DIR = _REPO_ROOT / "artifacts" / "optimization"
MODEL_DIR = _REPO_ROOT / "artifacts" / "models"
FIELDS_DIR = _REPO_ROOT / "artifacts" / "solver" / "fields"
AIRFOILS = ["NACA0012", "NACA2412", "NACA4412"]


def _list_files(directory: Path, pattern: str) -> list[Path]:
    return sorted(directory.glob(pattern)) if directory.exists() else []


def page_geometry() -> None:
    st.header("Geometry")
    col1, col2 = st.columns(2)
    with col1:
        airfoil = st.selectbox("Airfoil", AIRFOILS, index=1)
        span = st.slider("Span (m)", 1.0, 2.0, 1.5, 0.05)
        root = st.slider("Root chord (m)", 0.15, 0.50, 0.30, 0.01)
        tip = st.slider("Tip chord (m)", 0.05, 0.30, 0.15, 0.01)
        sweep = st.slider("Sweep (deg)", 0.0, 30.0, 10.0, 1.0)
        twist = st.slider("Twist (deg)", -5.0, 5.0, 2.0, 0.5)

    tip = min(tip, root)
    params = WingParameters(
        span_m=span, root_chord_m=root, tip_chord_m=tip,
        sweep_deg=sweep, twist_deg=twist, airfoil_id=airfoil,
    )
    with col2:
        st.pyplot(plots_geometry.plot_airfoil(airfoil))
    st.pyplot(plots_geometry.plot_planform(params))


def _load_selected_dataset() -> pd.DataFrame | None:
    files = _list_files(DATASET_DIR, "*.csv")
    if not files:
        st.info("No datasets found. Run `simulate` first.")
        return None
    choice = st.selectbox("Dataset", [f.name for f in files])
    return pd.read_csv(DATASET_DIR / choice)


def page_performance() -> None:
    st.header("Performance")
    frame = _load_selected_dataset()
    if frame is None:
        return
    st.pyplot(plots_cfd.plot_polar(frame))
    velocities = sorted(frame["velocity_mps"].unique()) if "velocity_mps" in frame else []
    velocity = st.selectbox("Velocity (m/s)", velocities) if velocities else None
    st.pyplot(plots_cfd.plot_aoa_sweep(frame, velocity_mps=velocity))


def page_optimization() -> None:
    st.header("Optimization")
    conv_files = _list_files(OPT_DIR, "*.convergence.csv")
    pareto_files = _list_files(OPT_DIR, "*.pareto.csv")

    if conv_files:
        choice = st.selectbox("Convergence run", [f.name for f in conv_files])
        conv = pd.read_csv(OPT_DIR / choice)
        st.pyplot(plots_optimization.plot_convergence(conv))
    else:
        st.info("No convergence files found. Run `optimize` with grid or ga.")

    if pareto_files:
        choice = st.selectbox("Pareto run", [f.name for f in pareto_files])
        pareto = pd.read_csv(OPT_DIR / choice)
        st.pyplot(plots_optimization.plot_pareto(pareto))
        st.dataframe(pareto)


def page_flow_fields() -> None:
    st.header("Flow Fields")
    sidecars = sorted(FIELDS_DIR.glob("**/field.json")) if FIELDS_DIR.exists() else []
    if not sidecars:
        st.info(
            "No field artifacts found. Run `simulate` with a field solver "
            "(set `solver.name: panel2d` and `solver.save_fields: true`)."
        )
        return
    labels = [f"{p.parent.parent.name}/{p.parent.name}" for p in sidecars]
    choice = st.selectbox("Field case", labels)
    data = load_fields(sidecars[labels.index(choice)])
    col1, col2 = st.columns(2)
    with col1:
        st.pyplot(plots_fields.plot_surface_cp(data))
        st.pyplot(plots_fields.plot_velocity_contour(data))
    with col2:
        st.pyplot(plots_fields.plot_pressure_contour(data))
        st.pyplot(plots_fields.plot_streamlines(data))


def page_experiments() -> None:
    st.header("Experiments")
    st.subheader("Datasets")
    st.write([f.name for f in _list_files(DATASET_DIR, "*.csv")] or "None")
    st.subheader("Optimization runs")
    st.write([f.name for f in _list_files(OPT_DIR, "*.best.json")] or "None")
    st.subheader("Surrogate models")
    st.write([f.name for f in _list_files(MODEL_DIR, "*.report.json")] or "None")


def main() -> None:
    st.set_page_config(page_title="UAV Wing CFD Dashboard", layout="wide")
    st.title("AI-Assisted Wing CFD and Optimization")
    page = st.sidebar.radio(
        "Page",
        ("Geometry", "Performance", "Flow Fields", "Optimization", "Experiments"),
    )
    if page == "Geometry":
        page_geometry()
    elif page == "Performance":
        page_performance()
    elif page == "Flow Fields":
        page_flow_fields()
    elif page == "Optimization":
        page_optimization()
    else:
        page_experiments()


if __name__ == "__main__":
    main()
