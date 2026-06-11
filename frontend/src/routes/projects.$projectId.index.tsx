import { createFileRoute, Link, useParams, useNavigate } from "@tanstack/react-router";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Plus, Trash2, ChevronRight, Sparkles } from "lucide-react";
import { toast } from "sonner";
import { Section } from "@/components/wing/section";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";

export const Route = createFileRoute("/projects/$projectId/")({
  head: () => ({ meta: [{ title: "Project — Aerofoil.lab" }] }),
  component: ProjectDetail,
});

function ProjectDetail() {
  const { projectId } = useParams({ from: "/projects/$projectId/" });
  const pid = Number(projectId);
  const qc = useQueryClient();
  const navigate = useNavigate();
  const [optimizeDialogOpen, setOptimizeDialogOpen] = useState(false);

  const projectQ = useQuery({ queryKey: ["project", pid], queryFn: () => api.getProject(pid).then((r) => r.project) });
  const designsQ = useQuery({ queryKey: ["designs", pid], queryFn: () => api.listDesigns(pid).then((r) => r.designs) });
  const runsQ = useQuery({ queryKey: ["runs", pid], queryFn: () => api.listRuns(pid).then((r) => r.runs) });

  const delDesign = useMutation({
    mutationFn: (id: number) => api.deleteDesign(id),
    onSuccess: () => { toast.success("Design deleted"); qc.invalidateQueries({ queryKey: ["designs", pid] }); },
    onError: (e: Error) => toast.error(e.message),
  });
  const delRun = useMutation({
    mutationFn: (id: number) => api.deleteRun(id),
    onSuccess: () => { toast.success("Run deleted"); qc.invalidateQueries({ queryKey: ["runs", pid] }); },
    onError: (e: Error) => toast.error(e.message),
  });

  const handleSelectDesignForOptimization = (designId: number) => {
    setOptimizeDialogOpen(false);
    navigate({
      to: "/projects/$projectId/designs/$designId",
      params: { projectId, designId: String(designId) },
    });
  };

  return (
    <main className="mx-auto max-w-[1600px] px-6 py-10">
      <div className="flex items-center gap-2 font-mono text-xs text-muted-foreground mb-3">
        <Link to="/projects" className="hover:text-primary">projects</Link>
        <ChevronRight className="h-3 w-3" />
        <span className="text-foreground">#{projectId}</span>
      </div>
      <div className="flex items-start justify-between mb-8 gap-4">
        <div>
          <h1 className="text-3xl font-semibold tracking-tight">{projectQ.data?.name ?? "—"}</h1>
          {projectQ.data?.description && (
            <p className="text-muted-foreground mt-2 max-w-2xl">{projectQ.data.description}</p>
          )}
        </div>
        <Button asChild>
          <Link to="/projects/$projectId/design" params={{ projectId }}>
            <Plus className="h-4 w-4 mr-1" /> New design
          </Link>
        </Button>
      </div>

      <Tabs defaultValue="designs">
        <TabsList className="font-mono">
          <TabsTrigger value="designs">Designs ({designsQ.data?.length ?? 0})</TabsTrigger>
          <TabsTrigger value="runs">Runs ({runsQ.data?.length ?? 0})</TabsTrigger>
          <TabsTrigger value="analytics">Analytics</TabsTrigger>
        </TabsList>

        <TabsContent value="designs" className="mt-4">
          <Section title="Saved designs">
            {designsQ.isLoading ? (
              <p className="text-muted-foreground">Loading…</p>
            ) : (designsQ.data ?? []).length === 0 ? (
              <p className="text-muted-foreground text-sm">No designs yet. Create one from the design editor.</p>
            ) : (
              <table className="w-full text-sm font-mono">
                <thead>
                  <tr className="text-left text-[10px] uppercase tracking-wider text-muted-foreground border-b border-border">
                    <th className="py-2 pr-4">Name</th>
                    <th className="py-2 pr-4">Type</th>
                    <th className="py-2 pr-4 text-right">Span</th>
                    <th className="py-2 pr-4 text-right">AR</th>
                    <th className="py-2 pr-4 text-right">L/D</th>
                    <th className="py-2"></th>
                  </tr>
                </thead>
                <tbody>
                  {designsQ.data!.map((d) => (
                    <tr key={d.id} className="border-b border-border/50 hover:bg-muted/30">
                      <td className="py-2 pr-4">
                        <Link
                          to="/projects/$projectId/designs/$designId"
                          params={{ projectId, designId: String(d.id) }}
                          className="hover:text-primary"
                        >
                          {d.name}
                        </Link>
                      </td>
                      <td className="py-2 pr-4 text-muted-foreground">{d.design_type}</td>
                      <td className="py-2 pr-4 text-right tabular-nums">{d.span_m?.toFixed(2)}</td>
                      <td className="py-2 pr-4 text-right tabular-nums">{d.aspect_ratio?.toFixed(2) ?? "—"}</td>
                      <td className="py-2 pr-4 text-right tabular-nums text-accent">{d.mean_ld?.toFixed(2) ?? "—"}</td>
                      <td className="py-2 text-right">
                        <Button variant="ghost" size="sm" onClick={() => delDesign.mutate(d.id)}>
                          <Trash2 className="h-3.5 w-3.5" />
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </Section>
        </TabsContent>

        <TabsContent value="runs" className="mt-4">
          <Section
            title="Optimization runs"
            action={
              <Button size="sm" variant="outline" onClick={() => setOptimizeDialogOpen(true)}>
                <Sparkles className="h-3.5 w-3.5 mr-1" /> New run
              </Button>
            }
          >
            {runsQ.isLoading ? (
              <p className="text-muted-foreground">Loading…</p>
            ) : (runsQ.data ?? []).length === 0 ? (
              <p className="text-muted-foreground text-sm">No optimization runs yet. <Button variant="link" size="sm" className="p-0 h-auto" onClick={() => setOptimizeDialogOpen(true)}>Create one</Button></p>
            ) : (
              <table className="w-full text-sm font-mono">
                <thead>
                  <tr className="text-left text-[10px] uppercase tracking-wider text-muted-foreground border-b border-border">
                    <th className="py-2 pr-4">Name</th>
                    <th className="py-2 pr-4">Algorithm</th>
                    <th className="py-2 pr-4">Objective</th>
                    <th className="py-2 pr-4 text-right">Evals</th>
                    <th className="py-2 pr-4 text-right">Δ%</th>
                    <th className="py-2 pr-4">Status</th>
                    <th className="py-2"></th>
                  </tr>
                </thead>
                <tbody>
                  {runsQ.data!.map((r) => (
                    <tr key={r.id} className="border-b border-border/50 hover:bg-muted/30">
                      <td className="py-2 pr-4">{r.name}</td>
                      <td className="py-2 pr-4 text-muted-foreground uppercase">{r.algorithm}</td>
                      <td className="py-2 pr-4 text-muted-foreground">{r.objective}</td>
                      <td className="py-2 pr-4 text-right tabular-nums">{r.num_evaluations ?? "—"}</td>
                      <td className="py-2 pr-4 text-right tabular-nums text-accent">{r.improvement_pct?.toFixed(2) ?? "—"}</td>
                      <td className="py-2 pr-4 text-muted-foreground">{r.status}</td>
                      <td className="py-2 text-right">
                        <Button variant="ghost" size="sm" onClick={() => delRun.mutate(r.id)}>
                          <Trash2 className="h-3.5 w-3.5" />
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </Section>
        </TabsContent>

        <TabsContent value="analytics" className="mt-4">
          <Section title="Summary">
            <div className="grid md:grid-cols-3 gap-px bg-border rounded-md overflow-hidden">
              <Stat label="Designs" value={designsQ.data?.length ?? 0} />
              <Stat label="Runs" value={runsQ.data?.length ?? 0} />
              <Stat
                label="Best L/D"
                value={
                  Math.max(0, ...(designsQ.data ?? []).map((d) => d.mean_ld ?? 0)).toFixed(2)
                }
              />
            </div>
          </Section>
        </TabsContent>
      </Tabs>

      <Dialog open={optimizeDialogOpen} onOpenChange={setOptimizeDialogOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Select design to optimize</DialogTitle>
            <DialogDescription>Choose a baseline design to run optimization on</DialogDescription>
          </DialogHeader>
          <div className="space-y-2 max-h-[400px] overflow-y-auto">
            {designsQ.isLoading ? (
              <p className="text-muted-foreground text-sm font-mono">Loading…</p>
            ) : (designsQ.data ?? []).length === 0 ? (
              <p className="text-muted-foreground text-sm font-mono">No designs yet. Create one first.</p>
            ) : (
              (designsQ.data ?? []).map((design) => (
                <button
                  key={design.id}
                  onClick={() => handleSelectDesignForOptimization(design.id)}
                  className="w-full text-left p-3 rounded-md border border-border hover:bg-muted/50 transition-colors"
                >
                  <div className="font-mono text-sm font-semibold">{design.name}</div>
                  <div className="text-xs text-muted-foreground font-mono mt-1">
                    Span: {design.span_m.toFixed(2)}m · AR: {design.aspect_ratio?.toFixed(2) ?? "—"}
                  </div>
                </button>
              ))
            )}
          </div>
        </DialogContent>
      </Dialog>
    </main>
  );
}

function Stat({ label, value }: { label: string; value: number | string }) {
  return (
    <div className="bg-card p-5">
      <div className="text-[10px] uppercase tracking-wider text-muted-foreground font-mono">{label}</div>
      <div className="font-mono text-2xl tabular-nums mt-1">{value}</div>
    </div>
  );
}