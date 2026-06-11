const BASE = (import.meta as any).env?.VITE_API_BASE_URL || "http://localhost:8000";

export const API_BASE_URL = BASE;

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers || {}),
    },
  });
  if (!res.ok) {
    let detail = "";
    try {
      const j = await res.json();
      detail = j?.detail || j?.message || JSON.stringify(j);
    } catch {
      detail = await res.text();
    }
    throw new Error(`${res.status} ${res.statusText}: ${detail || "request failed"}`);
  }
  return res.json() as Promise<T>;
}

// ===== Types =====
export interface WingParams {
  span_m: number;
  root_chord_m: number;
  tip_chord_m: number;
  sweep_deg: number;
  twist_deg: number;
  airfoil_id: string;
}

export interface AirfoilPlot {
  x: number[];
  camber_y: number[];
  upper_y: number[];
  lower_y: number[];
}

export interface PlanformPlot {
  outline_span_y: number[];
  outline_chord_x: number[];
}

export interface WingMetrics {
  wing_area_m2: number;
  aspect_ratio: number;
  taper_ratio: number;
  mean_chord: number;
  quarter_chord_sweep_deg?: number;
}

export interface PreviewResponse {
  params: WingParams;
  metrics: WingMetrics;
  airfoil_plot: AirfoilPlot;
  planform_plot: PlanformPlot;
}

export interface Project {
  id: number;
  name: string;
  description?: string | null;
  created_at: string;
  updated_at: string;
}

export interface Design extends WingParams {
  id: number;
  project_id: number;
  name: string;
  description?: string | null;
  design_type: "baseline" | "optimized" | "preliminary" | string;
  wing_area_m2?: number;
  aspect_ratio?: number;
  taper_ratio?: number;
  mean_cl?: number;
  mean_cd?: number;
  mean_ld?: number;
  created_at: string;
  updated_at: string;
}

export interface OptimizationRun {
  id: number;
  project_id: number;
  baseline_design_id: number;
  optimized_design_id?: number | null;
  name: string;
  description?: string | null;
  algorithm: string;
  objective: string;
  max_evaluations: number;
  num_evaluations?: number;
  best_cost?: number;
  improvement_pct?: number;
  status: string;
  created_at: string;
  updated_at: string;
  completed_at?: string | null;
}

export interface DesignBundle {
  params: WingParams;
  metrics: WingMetrics;
  airfoil_plot: AirfoilPlot;
  planform_plot: PlanformPlot;
  mission_metrics?: { mean_CL: number; mean_CD: number; mean_LD: number };
  selected_condition?: {
    condition: { velocity_mps: number; aoa_deg: number; air_density: number };
    coefficients: { CL: number; CD: number; LD: number };
    forces: { lift_n: number; drag_n: number };
  };
  flow_field?: {
    condition_id?: string;
    solver?: string;
    grid?: {
      x: number[][];
      y: number[][];
      pressure: number[][];
      velocity_x: number[][];
      velocity_y: number[][];
    };
    surface?: { x: number[]; cp: number[] };
  };
}

export interface OptimizeResponse {
  baseline: DesignBundle;
  optimized: DesignBundle;
  comparison: Array<{
    metric: string;
    baseline: number;
    optimized: number;
    delta: number;
    pct_change: number;
  }>;
  optimization: {
    algorithm: string;
    num_evaluations: number;
    best_cost: number;
    convergence: number[];
    best: { params: WingParams; metrics: WingMetrics; cost: number };
    pareto?: Array<{ cl: number; cd: number }>;
  };
}

export interface ConfigDefaults {
  bounds: Record<string, { min: number; max: number; default?: number }>;
  airfoils: string[];
  optimization: {
    algorithms: string[];
    objectives: string[];
    defaults: Record<string, any>;
  };
  conditions?: {
    velocity_mps: { min: number; max: number; default: number };
    aoa_deg: { min: number; max: number; default: number };
  };
}

// ===== Endpoints =====
export const api = {
  health: () => request<{ status: string }>("/api/health"),
  defaults: () => request<ConfigDefaults>("/api/config/defaults"),

  previewWing: (params: WingParams) =>
    request<PreviewResponse>("/api/wings/preview", {
      method: "POST",
      body: JSON.stringify(params),
    }),

  optimize: (body: {
    baseline: WingParams;
    compare_condition?: { velocity_mps: number; aoa_deg: number };
    optimization: {
      algorithm: string;
      objective: string;
      max_evaluations: number;
      population_size?: number;
      generations?: number;
      crossover_rate?: number;
      mutation_rate?: number;
      grid_points_per_dim?: number;
      seed?: number;
    };
    include_flow_fields?: boolean;
    solver?: string;
  }) =>
    request<OptimizeResponse>("/api/workflows/optimize", {
      method: "POST",
      body: JSON.stringify(body),
    }),

  listProjects: () => request<{ projects: Project[] }>("/api/projects"),
  createProject: (body: { name: string; description?: string }) =>
    request<{ project: Project }>("/api/projects", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  getProject: (id: number) => request<{ project: Project }>(`/api/projects/${id}`),
  updateProject: (id: number, body: Partial<Project>) =>
    request<{ project: Project }>(`/api/projects/${id}`, {
      method: "PUT",
      body: JSON.stringify(body),
    }),
  deleteProject: (id: number) =>
    request<{ success: boolean }>(`/api/projects/${id}`, { method: "DELETE" }),

  listDesigns: (projectId: number) =>
    request<{ designs: Design[] }>(`/api/projects/${projectId}/designs`),
  createDesign: (
    projectId: number,
    body: { name: string; description?: string; params: WingParams; design_type?: string },
  ) =>
    request<{ design: Design }>(`/api/projects/${projectId}/designs`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  getDesign: (id: number) => request<{ design: Design }>(`/api/designs/${id}`),
  deleteDesign: (id: number) =>
    request<{ success: boolean }>(`/api/designs/${id}`, { method: "DELETE" }),

  listRuns: (projectId: number) =>
    request<{ runs: OptimizationRun[] }>(`/api/projects/${projectId}/optimization-runs`),
  createRun: (
    projectId: number,
    body: {
      baseline_design_id: number;
      optimized_design_id?: number;
      name: string;
      description?: string;
      algorithm: string;
      objective: string;
      max_evaluations: number;
      num_evaluations?: number;
      best_cost?: number;
      improvement_pct?: number;
    },
  ) =>
    request<{ run: OptimizationRun }>(`/api/projects/${projectId}/optimization-runs`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  getRun: (id: number) => request<{ run: OptimizationRun }>(`/api/optimization-runs/${id}`),
  deleteRun: (id: number) =>
    request<{ success: boolean }>(`/api/optimization-runs/${id}`, { method: "DELETE" }),
};

export const DEFAULT_PARAMS: WingParams = {
  span_m: 1.5,        // Within range: 1.0-2.0 m
  root_chord_m: 0.30, // Within range: 0.15-0.50 m
  tip_chord_m: 0.15,  // Within range: 0.05-0.30 m, and < root_chord
  sweep_deg: 15.0,    // Within range: 0.0-30.0°
  twist_deg: 2.0,     // Within range: -5.0 to 5.0°
  airfoil_id: "NACA4412",
};