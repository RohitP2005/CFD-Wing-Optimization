import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useForm } from "react-hook-form";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { toast } from "sonner";

export const Route = createFileRoute("/projects/new")({
  head: () => ({ meta: [{ title: "New project — Aerofoil.lab" }] }),
  component: NewProject,
});

function NewProject() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const { register, handleSubmit, formState } = useForm<{ name: string; description: string }>({
    defaultValues: { name: "", description: "" },
    mode: "onChange",
  });

  const createMut = useMutation({
    mutationFn: (vars: { name: string; description: string }) => api.createProject(vars),
    onSuccess: (r) => {
      toast.success("Project created");
      qc.invalidateQueries({ queryKey: ["projects"] });
      navigate({ to: "/projects/$projectId/design", params: { projectId: String(r.project.id) } });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  return (
    <main className="mx-auto max-w-2xl px-6 py-10">
      <h1 className="font-mono text-[11px] uppercase tracking-[0.2em] text-primary">// new</h1>
      <h2 className="text-3xl font-semibold tracking-tight mt-1 mb-8">Create a project</h2>
      <form
        onSubmit={handleSubmit((d) => createMut.mutate(d))}
        className="panel p-6 space-y-5"
      >
        <div className="space-y-2">
          <Label htmlFor="name" className="font-mono text-[11px] uppercase tracking-wider text-muted-foreground">
            Project name
          </Label>
          <Input id="name" placeholder="UAV cruise wing" {...register("name", { required: true })} />
        </div>
        <div className="space-y-2">
          <Label htmlFor="description" className="font-mono text-[11px] uppercase tracking-wider text-muted-foreground">
            Description
          </Label>
          <Textarea id="description" rows={4} placeholder="Optimizing for cruise efficiency at 20 m/s." {...register("description")} />
        </div>
        <div className="flex gap-2 justify-end">
          <Button type="button" variant="ghost" onClick={() => navigate({ to: "/projects" })}>Cancel</Button>
          <Button type="submit" disabled={!formState.isValid || createMut.isPending}>
            {createMut.isPending ? "Creating…" : "Create project"}
          </Button>
        </div>
      </form>
    </main>
  );
}