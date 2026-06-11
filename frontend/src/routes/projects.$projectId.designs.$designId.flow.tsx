import { createFileRoute, useParams, Link } from "@tanstack/react-router";
import { useQuery, useMutation } from "@tanstack/react-query";
import { useState, useMemo } from "react";
import { api, type WingParams } from "@/lib/api";
import { Section } from "@/components/wing/section";
import { ContourCanvas } from "@/components/wing/contour-canvas";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Slider } from "@/components/ui/slider";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  Legend,
} from "recharts";
import { ChevronRight, Wind } from "lucide-react";
import { toast } from "sonner";

export const Route = createFileRoute("/projects/$projectId/designs/$designId/flow")({
  head: () => ({ meta: [{ title: "Flow visualization — Aerofoil.lab" }] }),
  component: FlowPage,
});

function FlowPage() {
  const { projectId, designId } = useParams({ from: "/projects/$projectId/designs/$designId/flow" });
  const pid = Number(projectId);
  const did = Number(designId);

  const designQ = useQuery({ queryKey: ["design", did], queryFn: () => api.getDesign(did).then((r) => r.design) });
  const projectQ = useQuery({ queryKey: ["project", pid], queryFn: () => api.getProject(pid).then((r) => r.project) });

  const [velocity, setVelocity] = useState(20);
  const [aoa, setAoa] = useState(5);

  const params: WingParams | null = designQ.data
    ? {
        span_m: designQ.data.span_m,
        root_chord_m: designQ.data.root_chord_m,
        tip_chord_m: designQ.data.tip_chord_m,
        sweep_deg: designQ.data.sweep_deg,
        twist_deg: designQ.data.twist_deg,
        airfoil_id: designQ.data.airfoil_id,
      }
    : null;

  const flowMut = useMutation({
    mutationFn: () =>
      api.optimize({
        baseline: params!,
        compare_condition: { velocity_mps: velocity, aoa_deg: aoa },
        optimization: { algorithm: "grid", objective: "maximize_ld", max_evaluations: 16, grid_points_per_dim: 2 },
        include_flow_fields: true,
      }),
    onError: (e: Error) => toast.error(e.message),
  });

  const result = flowMut.data;
  const baselineFlow = result?.baseline.flow_field;
  const optimizedFlow = result?.optimized.flow_field;

  const cpRows = useMemo(() => {
    if (!baselineFlow?.surface || !optimizedFlow?.surface) return [];
    const len = Math.max(baselineFlow.surface.x.length, optimizedFlow.surface.x.length);
    return Array.from({ length: len }, (_, i) => ({
      x: baselineFlow.surface!.x[i] ?? optimizedFlow.surface!.x[i],
      baseline: baselineFlow.surface!.cp[i],
      optimized: optimizedFlow.surface!.cp[i],
    }));
  }, [baselineFlow, optimizedFlow]);

  return (
    <main className="mx-auto max-w-[1600px] px-6 py-8 space-y-5">
      <div className="flex items-center gap-2 font-mono text-xs text-muted-foreground">
        <Link to="/projects" className="hover:text-primary">projects</Link>
        <ChevronRight className="h-3 w-3" />
        <Link to="/projects/$projectId" params={{ projectId }} className="hover:text-primary">
          {projectQ.data?.name ?? `#${projectId}`}
        </Link>
        <ChevronRight className="h-3 w-3" />
        <Link to="/projects/$projectId/designs/$designId" params={{ projectId, designId }} className="hover:text-primary">
          {designQ.data?.name ?? `design #${designId}`}
        </Link>
        <ChevronRight className="h-3 w-3" />
        <span className="text-foreground">flow</span>
      </div>

      <h1 className="text-2xl font-semibold tracking-tight flex items-center gap-2">
        <Wind className="h-5 w-5 text-primary" /> Flow visualization
      </h1>

      <Section title="Flight condition">
        <div className="grid md:grid-cols-[1fr_1fr_auto] gap-5 items-end">
          <div className="space-y-2">
            <Label className="font-mono text-[11px] text-muted-foreground flex justify-between">
              <span>Velocity [m/s]</span><span className="tabular-nums text-foreground">{velocity}</span>
            </Label>
            <Slider min={5} max={80} step={1} value={[velocity]} onValueChange={([v]) => setVelocity(v)} />
          </div>
          <div className="space-y-2">
            <Label className="font-mono text-[11px] text-muted-foreground flex justify-between">
              <span>AoA [°]</span><span className="tabular-nums text-foreground">{aoa}</span>
            </Label>
            <Slider min={-5} max={20} step={0.5} value={[aoa]} onValueChange={([v]) => setAoa(v)} />
          </div>
          <Button onClick={() => flowMut.mutate()} disabled={!params || flowMut.isPending}>
            {flowMut.isPending ? "Solving…" : "Compute flow"}
          </Button>
        </div>
      </Section>

      {!result ? (
        <div className="panel p-10 text-center font-mono text-sm text-muted-foreground">
          Choose a condition and compute the flow field to render Cp, pressure, velocity and streamlines.
        </div>
      ) : (
        <Tabs defaultValue="cp">
          <TabsList className="font-mono">
            <TabsTrigger value="cp">Surface Cp</TabsTrigger>
            <TabsTrigger value="pressure">Pressure</TabsTrigger>
            <TabsTrigger value="velocity">Velocity</TabsTrigger>
            <TabsTrigger value="streamlines">Streamlines</TabsTrigger>
          </TabsList>

          <TabsContent value="cp" className="mt-4">
            <Section title="Surface Cp distribution" subtitle="More negative Cp ⇒ greater suction ⇒ more lift.">
              {cpRows.length > 0 ? (
                <ResponsiveContainer width="100%" height={360}>
                  <LineChart data={cpRows} margin={{ top: 8, right: 16, bottom: 8, left: 0 }}>
                    <CartesianGrid strokeDasharray="2 4" stroke="var(--color-border)" />
                    <XAxis dataKey="x" type="number" domain={[0, 1]} tick={{ fontSize: 10, fontFamily: "var(--font-mono)" }} stroke="var(--color-muted-foreground)" />
                    <YAxis reversed tick={{ fontSize: 10, fontFamily: "var(--font-mono)" }} stroke="var(--color-muted-foreground)" />
                    <Tooltip contentStyle={{ background: "var(--color-popover)", border: "1px solid var(--color-border)", fontFamily: "var(--font-mono)", fontSize: 11 }} />
                    <Legend wrapperStyle={{ fontFamily: "var(--font-mono)", fontSize: 10 }} />
                    <Line type="monotone" dataKey="baseline" stroke="oklch(0.78 0.16 200)" dot={false} isAnimationActive={false} strokeWidth={1.6} />
                    <Line type="monotone" dataKey="optimized" stroke="oklch(0.72 0.18 80)" dot={false} isAnimationActive={false} strokeWidth={1.6} />
                  </LineChart>
                </ResponsiveContainer>
              ) : (
                <p className="text-sm text-muted-foreground font-mono">No Cp data returned.</p>
              )}
            </Section>
          </TabsContent>

          <TabsContent value="pressure" className="mt-4">
            <div className="grid md:grid-cols-2 gap-5">
              <Section title="Baseline · pressure">
                {baselineFlow?.grid?.pressure ? <ContourCanvas grid={baselineFlow.grid.pressure} /> : <p className="text-sm text-muted-foreground">No grid data.</p>}
              </Section>
              <Section title="Optimized · pressure">
                {optimizedFlow?.grid?.pressure ? <ContourCanvas grid={optimizedFlow.grid.pressure} /> : <p className="text-sm text-muted-foreground">No grid data.</p>}
              </Section>
            </div>
          </TabsContent>

          <TabsContent value="velocity" className="mt-4">
            <div className="grid md:grid-cols-2 gap-5">
              <Section title="Baseline · velocity magnitude">
                {baselineFlow?.grid?.velocity_x ? (
                  <ContourCanvas grid={magnitude(baselineFlow.grid.velocity_x, baselineFlow.grid.velocity_y)} />
                ) : <p className="text-sm text-muted-foreground">No grid data.</p>}
              </Section>
              <Section title="Optimized · velocity magnitude">
                {optimizedFlow?.grid?.velocity_x ? (
                  <ContourCanvas grid={magnitude(optimizedFlow.grid.velocity_x, optimizedFlow.grid.velocity_y)} />
                ) : <p className="text-sm text-muted-foreground">No grid data.</p>}
              </Section>
            </div>
          </TabsContent>

          <TabsContent value="streamlines" className="mt-4">
            <Section title="Streamlines" subtitle="Approximated from the velocity field.">
              <p className="text-sm text-muted-foreground font-mono">
                Streamlines are shown as velocity-magnitude contour for now; high-density vector seeding is a planned enhancement.
              </p>
              {baselineFlow?.grid?.velocity_x && (
                <div className="mt-4">
                  <ContourCanvas grid={magnitude(baselineFlow.grid.velocity_x, baselineFlow.grid.velocity_y)} height={400} />
                </div>
              )}
            </Section>
          </TabsContent>
        </Tabs>
      )}
    </main>
  );
}

function magnitude(vx: number[][], vy: number[][]): number[][] {
  return vx.map((row, r) => row.map((u, c) => Math.hypot(u, vy[r]?.[c] ?? 0)));
}