import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Plus, FolderOpen, Trash2, Search } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { EmptyState } from "@/components/wing/empty-state";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";

export const Route = createFileRoute("/projects/")({
  head: () => ({ meta: [{ title: "Projects — Aerofoil.lab" }] }),
  component: ProjectsPage,
});

function ProjectsPage() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [query, setQuery] = useState("");
  const projectsQ = useQuery({
    queryKey: ["projects"],
    queryFn: () => api.listProjects().then((r) => r.projects),
  });

  const delMut = useMutation({
    mutationFn: (id: number) => api.deleteProject(id),
    onSuccess: () => {
      toast.success("Project deleted");
      qc.invalidateQueries({ queryKey: ["projects"] });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const items = (projectsQ.data ?? []).filter((p) =>
    p.name.toLowerCase().includes(query.toLowerCase()),
  );

  return (
    <main className="mx-auto max-w-[1600px] px-6 py-10">
      <div className="flex items-center justify-between mb-8 gap-4">
        <div>
          <h1 className="font-mono text-[11px] uppercase tracking-[0.2em] text-primary">// projects</h1>
          <h2 className="text-3xl font-semibold tracking-tight mt-1">All projects</h2>
        </div>
        <Button onClick={() => navigate({ to: "/projects/new" })}>
          <Plus className="h-4 w-4 mr-1" /> New project
        </Button>
      </div>

      <div className="relative max-w-md mb-6">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
        <Input
          placeholder="Search projects..."
          className="pl-9 font-mono"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
      </div>

      {projectsQ.isLoading ? (
        <div className="font-mono text-sm text-muted-foreground">Loading…</div>
      ) : projectsQ.isError ? (
        <EmptyState
          title="Cannot reach backend"
          description={`${(projectsQ.error as Error).message}. Make sure the FastAPI backend is running at the configured base URL.`}
        />
      ) : items.length === 0 ? (
        <EmptyState
          icon={<FolderOpen className="h-10 w-10" />}
          title="No projects yet"
          description="Create your first project to start designing and optimizing wings."
          action={
            <Button onClick={() => navigate({ to: "/projects/new" })}>
              <Plus className="h-4 w-4 mr-1" /> New project
            </Button>
          }
        />
      ) : (
        <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
          {items.map((p) => (
            <div key={p.id} className="panel p-5 hover:border-primary/60 transition group">
              <Link to="/projects/$projectId" params={{ projectId: String(p.id) }} className="block">
                <div className="font-mono text-[10px] text-muted-foreground">#{p.id}</div>
                <h3 className="font-semibold text-lg mt-1 group-hover:text-primary transition">{p.name}</h3>
                {p.description && (
                  <p className="text-sm text-muted-foreground mt-1 line-clamp-2">{p.description}</p>
                )}
                <div className="mt-4 font-mono text-[10px] text-muted-foreground/80 flex justify-between">
                  <span>updated {new Date(p.updated_at).toLocaleDateString()}</span>
                </div>
              </Link>
              <div className="mt-3 flex justify-end">
                <AlertDialog>
                  <AlertDialogTrigger asChild>
                    <Button variant="ghost" size="sm" className="text-muted-foreground hover:text-destructive">
                      <Trash2 className="h-3.5 w-3.5" />
                    </Button>
                  </AlertDialogTrigger>
                  <AlertDialogContent>
                    <AlertDialogHeader>
                      <AlertDialogTitle>Delete project?</AlertDialogTitle>
                      <AlertDialogDescription>
                        This permanently deletes "{p.name}" and all its designs and runs.
                      </AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                      <AlertDialogCancel>Cancel</AlertDialogCancel>
                      <AlertDialogAction onClick={() => delMut.mutate(p.id)}>Delete</AlertDialogAction>
                    </AlertDialogFooter>
                  </AlertDialogContent>
                </AlertDialog>
              </div>
            </div>
          ))}
        </div>
      )}
    </main>
  );
}