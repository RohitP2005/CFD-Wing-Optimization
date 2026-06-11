import { createFileRoute, useParams, Link } from "@tanstack/react-router";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api, type OptimizeResponse, type WingParams } from "@/lib/api";
import { Section } from "@/components/wing/section";
import { AirfoilChart } from "@/components/wing/airfoil-chart";
import { PlanformChart } from "@/components/wing/planform-chart";
import { MetricsPanel } from "@/components/wing/metrics-panel";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Slider } from "@/components/ui/slider";
import { Checkbox } from "@/components/ui/checkbox";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
} from "recharts";
import { ChevronRight, Sparkles, TrendingUp, TrendingDown, Save, Eye } from "lucide-react";
import { toast } from "sonner";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

export const Route = createFileRoute("/projects/$projectId/designs/$designId/")({
  head: () => ({ meta: [{ title: "Design — Aerofoil.lab" }] }),
  component: DesignDetail,
});

function DesignDetail() {
  const { projectId, designId } = useParams({ from: "/projects/$projectId/designs/$designId/" });
  const pid = Number(projectId);
  const did = Number(designId);
  const qc = useQueryClient();

  const designQ = useQuery({ queryKey: ["design", did], queryFn: () => api.getDesign(did).then((r) => r.design) });
  const defaultsQ = useQuery({ queryKey: ["defaults"], queryFn: api.defaults, staleTime: Infinity });
  const projectQ = useQuery({ queryKey: ["project", pid], queryFn: () => api.getProject(pid).then((r) => r.project) });

  const [algorithm, setAlgorithm] = useState("ga");
  const [objective, setObjective] = useState("maximize_ld");
  const [maxEvals, setMaxEvals] = useState(240);
  const [popSize, setPopSize] = useState(24);
  const [generations, setGenerations] = useState(10);
  const [gridPoints, setGridPoints] = useState(4);
  const [velocity, setVelocity] = useState(20);
  const [aoa, setAoa] = useState(5);
  const [includeFlow, setIncludeFlow] = useState(true);
  const [result, setResult] = useState<OptimizeResponse | null>(null);
  const [saveOpen, setSaveOpen] = useState(false);
  const [runName, setRunName] = useState("");

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

  const optimizeMut = useMutation({
    mutationFn: () =>
      api.optimize({
        baseline: params!,
        compare_condition: { velocity_mps: velocity, aoa_deg: aoa },
        optimization: {
          algorithm,
          objective,
          max_evaluations: maxEvals,
          population_size: popSize,
          generations,
          grid_points_per_dim: gridPoints,
        },
        include_flow_fields: includeFlow,
      }),
    onSuccess: (data) => {
      setResult(data);
      toast.success(`Optimization complete · ${data.optimization.num_evaluations} evals`);
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const saveRunMut = useMutation({
    mutationFn: () =>
      api.createRun(pid, {
        baseline_design_id: did,
        name: runName.trim() || `Run · ${algorithm.toUpperCase()} ${maxEvals}`,
        algorithm,
        objective,
        max_evaluations: maxEvals,
        num_evaluations: result?.optimization.num_evaluations,
        best_cost: result?.optimization.best_cost,
        improvement_pct:
          result?.comparison.find((c) => c.metric.toUpperCase() === "LD")?.pct_change,
      }),
    onSuccess: () => {
      toast.success("Run saved");
      qc.invalidateQueries({ queryKey: ["runs", pid] });
      setSaveOpen(false);
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const algoOptions = defaultsQ.data?.optimization?.algorithms ?? ["grid", "ga", "nsga2"];
  const objOptions =
    defaultsQ.data?.optimization?.objectives ?? ["maximize_ld", "maximize_cl", "minimize_cd"];

  return (
    <main className="mx-auto max-w-[1600px] px-6 py-8 space-y-5">
      <div className="flex items-center gap-2 font-mono text-xs text-muted-foreground">
        <Link to="/projects" className="hover:text-primary">projects</Link>
        <ChevronRight className="h-3 w-3" />
        <Link to="/projects/$projectId" params={{ projectId }} className="hover:text-primary">
          {projectQ.data?.name ?? `#${projectId}`}
        </Link>
        <ChevronRight className="h-3 w-3" />
        <span className="text-foreground">{designQ.data?.name ?? `design #${designId}`}</span>
      </div>

      <div className="panel p-5 flex flex-wrap items-center justify-between gap-3">
        <div>
          <div className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
            {designQ.data?.design_type ?? "design"}
          </div>
          <h1 className="text-2xl font-semibold tracking-tight mt-0.5">
            {designQ.data?.name ?? "—"}
          </h1>
        </div>
        {designQ.data && (
          <div className="grid grid-cols-4 gap-px bg-border rounded overflow-hidden text-sm font-mono">
            {[
              ["Area", designQ.data.wing_area_m2?.toFixed(2)],
              ["AR", designQ.data.aspect_ratio?.toFixed(2)],
              ["CL", designQ.data.mean_cl?.toFixed(3)],
              ["L/D", designQ.data.mean_ld?.toFixed(2)],
            ].map(([k, v]) => (
              <div key={k as string} className="bg-card px-4 py-2">
                <div className="text-[9px] text-muted-foreground uppercase">{k}</div>
                <div className="tabular-nums">{v ?? "—"}</div>
              </div>
            ))}
          </div>
        )}
        {result && (
          <Button variant="outline" asChild>
            <Link to="/projects/$projectId/designs/$designId/flow" params={{ projectId, designId }}>
              <Eye className="h-4 w-4 mr-1" /> Flow visualization
            </Link>
          </Button>
        )}
      </div>

      <div className="grid md:grid-cols-[400px_1fr] gap-5 items-start">
        <Section title="Optimization control" subtitle="Configure and launch a search">
          <div className="space-y-4">
            <div className="space-y-2">
              <Label className="font-mono text-[11px] uppercase tracking-wider text-muted-foreground">Algorithm</Label>
              <Select value={algorithm} onValueChange={setAlgorithm}>
                <SelectTrigger className="font-mono"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {algoOptions.map((a) => (
                    <SelectItem key={a} value={a} className="font-mono uppercase">{a}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label className="font-mono text-[11px] uppercase tracking-wider text-muted-foreground">Objective</Label>
              <Select value={objective} onValueChange={setObjective}>
                <SelectTrigger className="font-mono"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {objOptions.map((o) => (
                    <SelectItem key={o} value={o} className="font-mono">{o}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label className="font-mono text-[11px] uppercase tracking-wider text-muted-foreground flex justify-between">
                <span>Max evaluations</span><span className="text-foreground tabular-nums">{maxEvals}</span>
              </Label>
              <Slider min={10} max={2000} step={10} value={[maxEvals]} onValueChange={([v]) => setMaxEvals(v)} />
            </div>

            {algorithm !== "grid" ? (
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-2">
                  <Label className="font-mono text-[11px] uppercase tracking-wider text-muted-foreground">Pop. size</Label>
                  <Input type="number" value={popSize} className="font-mono" onChange={(e) => setPopSize(+e.target.value)} />
                </div>
                <div className="space-y-2">
                  <Label className="font-mono text-[11px] uppercase tracking-wider text-muted-foreground">Generations</Label>
                  <Input type="number" value={generations} className="font-mono" onChange={(e) => setGenerations(+e.target.value)} />
                </div>
              </div>
            ) : (
              <div className="space-y-2">
                <Label className="font-mono text-[11px] uppercase tracking-wider text-muted-foreground flex justify-between">
                  <span>Grid pts/dim</span><span className="text-foreground tabular-nums">{gridPoints}</span>
                </Label>
                <Slider min={2} max={8} step={1} value={[gridPoints]} onValueChange={([v]) => setGridPoints(v)} />
              </div>
            )}

            <div className="pt-3 border-t border-border space-y-3">
              <p className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">Compare condition</p>
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
              <label className="flex items-center gap-2 font-mono text-xs text-muted-foreground cursor-pointer">
                <Checkbox checked={includeFlow} onCheckedChange={(v) => setIncludeFlow(!!v)} />
                Include flow fields
              </label>
            </div>

            <Button
              onClick={() => optimizeMut.mutate()}
              disabled={!params || optimizeMut.isPending}
              className="w-full"
            >
              <Sparkles className="h-4 w-4 mr-1.5" />
              {optimizeMut.isPending ? "Optimizing…" : "Start optimization"}
            </Button>
          </div>
        </Section>

        <div className="space-y-5">
          {optimizeMut.isPending && (
            <div className="panel p-8 text-center font-mono text-sm text-muted-foreground">
              <div className="inline-block h-6 w-6 border-2 border-primary border-t-transparent rounded-full animate-spin mb-3" />
              <div>Running {algorithm.toUpperCase()} · {maxEvals} evaluations</div>
              <div className="text-xs text-muted-foreground/70 mt-1">This may take 5–60 seconds.</div>
            </div>
          )}

          {!result && !optimizeMut.isPending && (
            <div className="panel p-10 text-center">
              <p className="font-mono text-sm text-muted-foreground">
                Configure and launch an optimization to see baseline vs. optimized comparison here.
              </p>
            </div>
          )}

          {result && (
            <>
              <Section
                title="Force comparison"
                action={
                  <Button size="sm" variant="outline" onClick={() => { setRunName(""); setSaveOpen(true); }}>
                    <Save className="h-3.5 w-3.5 mr-1" /> Save run
                  </Button>
                }
              >
                <table className="w-full text-sm font-mono">
                  <thead>
                    <tr className="text-[10px] uppercase tracking-wider text-muted-foreground border-b border-border">
                      <th className="text-left py-2">Metric</th>
                      <th className="text-right py-2">Baseline</th>
                      <th className="text-right py-2">Optimized</th>
                      <th className="text-right py-2">Δ</th>
                      <th className="text-right py-2">Δ %</th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.comparison.map((c) => {
                      const positive = c.pct_change >= 0;
                      return (
                        <tr key={c.metric} className="border-b border-border/40">
                          <td className="py-2.5 uppercase">{c.metric}</td>
                          <td className="text-right tabular-nums">{c.baseline.toFixed(4)}</td>
                          <td className="text-right tabular-nums text-foreground">{c.optimized.toFixed(4)}</td>
                          <td className="text-right tabular-nums">{c.delta >= 0 ? "+" : ""}{c.delta.toFixed(4)}</td>
                          <td className={`text-right tabular-nums py-2.5 ${positive ? "text-accent" : "text-destructive"}`}>
                            <span className="inline-flex items-center gap-1 justify-end">
                              {positive ? <TrendingUp className="h-3 w-3" /> : <TrendingDown className="h-3 w-3" />}
                              {c.pct_change >= 0 ? "+" : ""}{c.pct_change.toFixed(2)}%
                            </span>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </Section>

              <Section title="Convergence" subtitle={`${result.optimization.algorithm.toUpperCase()} · ${result.optimization.num_evaluations} evals · best ${result.optimization.best_cost.toFixed(4)}`}>
                <ResponsiveContainer width="100%" height={220}>
                  <LineChart data={result.optimization.convergence.map((record: any) => ({ eval: record.evaluation, cost: record.best_cost }))} margin={{ top: 8, right: 16, left: 0, bottom: 8 }}>
                    <CartesianGrid strokeDasharray="2 4" stroke="var(--color-border)" />
                    <XAxis dataKey="eval" tick={{ fontSize: 10, fontFamily: "var(--font-mono)" }} stroke="var(--color-muted-foreground)" />
                    <YAxis tick={{ fontSize: 10, fontFamily: "var(--font-mono)" }} stroke="var(--color-muted-foreground)" />
                    <Tooltip contentStyle={{ background: "var(--color-popover)", border: "1px solid var(--color-border)", fontFamily: "var(--font-mono)", fontSize: 11 }} />
                    <Line type="monotone" dataKey="cost" stroke="var(--color-primary)" strokeWidth={1.8} dot={false} isAnimationActive={false} />
                  </LineChart>
                </ResponsiveContainer>
              </Section>

              <div className="grid lg:grid-cols-2 gap-5">
                <Section title="Airfoil overlay">
                  <AirfoilChart
                    series={[
                      { data: result.baseline.airfoil_plot, label: "baseline", color: "oklch(0.78 0.16 200)" },
                      { data: result.optimized.airfoil_plot, label: "optimized", color: "oklch(0.72 0.18 80)" },
                    ]}
                  />
                </Section>
                <Section title="Planform overlay">
                  <PlanformChart
                    series={[
                      { data: result.baseline.planform_plot, label: "baseline", color: "oklch(0.78 0.16 200)" },
                      { data: result.optimized.planform_plot, label: "optimized", color: "oklch(0.72 0.18 80)", dashed: true },
                    ]}
                  />
                </Section>
              </div>

              <div className="grid lg:grid-cols-2 gap-5">
                <Section title="Baseline metrics">
                  <MetricsPanel metrics={result.baseline.metrics} />
                </Section>
                <Section title="Optimized metrics">
                  <MetricsPanel metrics={result.optimized.metrics} />
                </Section>
              </div>
            </>
          )}
        </div>
      </div>

      <Dialog open={saveOpen} onOpenChange={setSaveOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Save optimization run</DialogTitle>
          </DialogHeader>
          <div className="space-y-2">
            <Label className="font-mono text-[11px] uppercase tracking-wider text-muted-foreground">Run name</Label>
            <Input value={runName} onChange={(e) => setRunName(e.target.value)} placeholder={`Run · ${algorithm.toUpperCase()} ${maxEvals}`} />
          </div>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setSaveOpen(false)}>Cancel</Button>
            <Button onClick={() => saveRunMut.mutate()} disabled={saveRunMut.isPending}>
              {saveRunMut.isPending ? "Saving…" : "Save"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </main>
  );
}
