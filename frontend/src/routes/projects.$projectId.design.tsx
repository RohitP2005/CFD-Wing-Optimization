import { createFileRoute, useParams, useNavigate, Link } from "@tanstack/react-router";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api, DEFAULT_PARAMS, type WingParams, type PreviewResponse } from "@/lib/api";
import { WingParameterForm } from "@/components/wing/wing-param-form";
import { AirfoilChart } from "@/components/wing/airfoil-chart";
import { PlanformChart } from "@/components/wing/planform-chart";
import { MetricsPanel } from "@/components/wing/metrics-panel";
import { Section } from "@/components/wing/section";
import { ChevronRight } from "lucide-react";
import { toast } from "sonner";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";

export const Route = createFileRoute("/projects/$projectId/design")({
  head: () => ({ meta: [{ title: "Design wing — Aerofoil.lab" }] }),
  component: DesignEditor,
});

function DesignEditor() {
  const { projectId } = useParams({ from: "/projects/$projectId/design" });
  const pid = Number(projectId);
  const qc = useQueryClient();
  const navigate = useNavigate();

  const defaultsQ = useQuery({ queryKey: ["defaults"], queryFn: api.defaults, staleTime: Infinity });
  const projectQ = useQuery({ queryKey: ["project", pid], queryFn: () => api.getProject(pid).then((r) => r.project) });

  const [preview, setPreview] = useState<PreviewResponse | null>(null);
  const [currentParams, setCurrentParams] = useState<WingParams>(DEFAULT_PARAMS);
  const [saveName, setSaveName] = useState("");
  const [dialogOpen, setDialogOpen] = useState(false);

  const previewMut = useMutation({
    mutationFn: api.previewWing,
    onSuccess: (data, vars) => { setPreview(data); setCurrentParams(vars); },
    onError: (e: Error) => toast.error(e.message),
  });

  const saveMut = useMutation({
    mutationFn: (vars: { name: string; params: WingParams }) =>
      api.createDesign(pid, { name: vars.name, params: vars.params, design_type: "baseline" }),
    onSuccess: (r) => {
      toast.success("Design saved");
      qc.invalidateQueries({ queryKey: ["designs", pid] });
      setDialogOpen(false);
      navigate({
        to: "/projects/$projectId/designs/$designId",
        params: { projectId, designId: String(r.design.id) },
      });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  return (
    <main className="mx-auto max-w-[1600px] px-6 py-8">
      <div className="flex items-center gap-2 font-mono text-xs text-muted-foreground mb-3">
        <Link to="/projects" className="hover:text-primary">projects</Link>
        <ChevronRight className="h-3 w-3" />
        <Link to="/projects/$projectId" params={{ projectId }} className="hover:text-primary">
          {projectQ.data?.name ?? `#${projectId}`}
        </Link>
        <ChevronRight className="h-3 w-3" />
        <span className="text-foreground">design</span>
      </div>
      <h1 className="text-3xl font-semibold tracking-tight mb-6">Wing design</h1>

      {defaultsQ.isError && (
        <div className="panel p-4 text-destructive font-mono text-sm mb-4">
          Backend unreachable: {(defaultsQ.error as Error).message}
        </div>
      )}

      <div className="grid md:grid-cols-[400px_1fr] gap-5">
        <Section title="Parameters">
          {defaultsQ.data ? (
            <WingParameterForm
              defaults={defaultsQ.data}
              initial={currentParams}
              isLoading={previewMut.isPending}
              onPreview={(p) => previewMut.mutate(p)}
              onSave={() => setDialogOpen(true)}
              saveLabel="Save…"
            />
          ) : (
            <p className="text-muted-foreground text-sm font-mono">Loading defaults…</p>
          )}

          <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Save design</DialogTitle>
              </DialogHeader>
              <div className="space-y-2">
                <Label className="font-mono text-[11px] uppercase tracking-wider text-muted-foreground">Name</Label>
                <Input value={saveName} onChange={(e) => setSaveName(e.target.value)} placeholder="Baseline v1" />
              </div>
              <DialogFooter>
                <Button variant="ghost" onClick={() => setDialogOpen(false)}>Cancel</Button>
                <Button
                  disabled={!saveName.trim() || saveMut.isPending}
                  onClick={() => saveMut.mutate({ name: saveName.trim(), params: currentParams })}
                >
                  {saveMut.isPending ? "Saving…" : "Save"}
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        </Section>

        <div className="space-y-5">
          <Section title="Airfoil profile">
            {preview ? (
              <AirfoilChart
                series={[{ data: preview.airfoil_plot, label: preview.params.airfoil_id, color: "var(--color-primary)" }]}
              />
            ) : (
              <p className="text-sm text-muted-foreground font-mono">Submit parameters to preview the airfoil.</p>
            )}
          </Section>
          <Section title="Planform (top-down)">
            {preview ? (
              <PlanformChart
                series={[{ data: preview.planform_plot, label: "Wing", color: "var(--color-primary)" }]}
              />
            ) : (
              <p className="text-sm text-muted-foreground font-mono">Submit parameters to preview the planform.</p>
            )}
          </Section>
          <Section title="Geometry metrics">
            {preview ? (
              <MetricsPanel metrics={preview.metrics} />
            ) : (
              <p className="text-sm text-muted-foreground font-mono">Pending preview.</p>
            )}
          </Section>
        </div>
      </div>
    </main>
  );
}