import type { WingMetrics } from "@/lib/api";

export function MetricsPanel({ metrics }: { metrics: WingMetrics }) {
  const rows: Array<[string, string]> = [
    ["Wing area", `${metrics.wing_area_m2?.toFixed(3)} m²`],
    ["Aspect ratio", metrics.aspect_ratio?.toFixed(3) ?? "—"],
    ["Taper ratio", metrics.taper_ratio?.toFixed(3) ?? "—"],
    ["Mean chord", `${metrics.mean_chord?.toFixed(3)} m`],
  ];
  if (metrics.quarter_chord_sweep_deg != null) {
    rows.push(["c/4 sweep", `${metrics.quarter_chord_sweep_deg.toFixed(2)}°`]);
  }
  return (
    <div className="grid grid-cols-2 gap-px bg-border rounded-md overflow-hidden">
      {rows.map(([k, v]) => (
        <div key={k} className="bg-card p-3">
          <div className="text-[10px] uppercase tracking-wider text-muted-foreground font-mono">{k}</div>
          <div className="font-mono text-base text-foreground tabular-nums mt-0.5">{v}</div>
        </div>
      ))}
    </div>
  );
}