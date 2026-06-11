import { createFileRoute } from "@tanstack/react-router";
import { Link } from "@tanstack/react-router";
import { Plane, Workflow, BarChart3, Wind } from "lucide-react";
import { SiteHeader } from "@/components/site-header";
import { Button } from "@/components/ui/button";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "Aerofoil.lab — Interactive wing design & optimization" },
      { name: "description", content: "Browser-based wing design, multi-objective optimization, and aerodynamic flow visualization." },
      { property: "og:title", content: "Aerofoil.lab" },
      { property: "og:description", content: "Interactive wing design and optimization studio." },
    ],
  }),
  component: Index,
});

function Index() {
  return (
    <div className="min-h-screen">
      <SiteHeader />
      <main className="mx-auto max-w-[1600px] px-6 py-16 md:py-24">
        <div className="grid md:grid-cols-[1.2fr_1fr] gap-12 items-center">
          <div>
            <div className="inline-flex items-center gap-2 font-mono text-[11px] uppercase tracking-[0.2em] text-primary mb-6 border border-primary/30 rounded-full px-3 py-1">
              <span className="inline-block w-1.5 h-1.5 rounded-full bg-primary animate-pulse" />
              v2.0 · aerodynamic design studio
            </div>
            <h1 className="text-5xl md:text-6xl font-semibold tracking-tight leading-[1.05]">
              Design wings.<br />
              <span className="text-primary">Optimize</span> performance.<br />
              <span className="text-accent">Visualize</span> flow.
            </h1>
            <p className="mt-6 text-lg text-muted-foreground max-w-xl leading-relaxed">
              An interactive workbench for parametric wing geometry, multi-objective
              optimization (GA, NSGA2, grid search) and in-browser flow field rendering.
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <Button asChild size="lg">
                <Link to="/projects/new">Start a new project</Link>
              </Button>
              <Button asChild variant="outline" size="lg">
                <Link to="/projects">Open projects</Link>
              </Button>
            </div>
          </div>

          <div className="panel p-6 font-mono text-[11px] text-muted-foreground/90">
            <div className="flex items-center justify-between text-primary mb-3">
              <span>// baseline.json</span>
              <span className="text-muted-foreground/60">readonly</span>
            </div>
            <pre className="leading-relaxed">{`{
  "span_m":        10.5,
  "root_chord_m":   2.0,
  "tip_chord_m":    1.0,
  "sweep_deg":     20.0,
  "twist_deg":      5.0,
  "airfoil_id":  "NACA4412"
}`}</pre>
            <div className="mt-4 border-t border-border pt-3 grid grid-cols-3 gap-2 text-foreground tabular-nums">
              <div><div className="text-[9px] text-muted-foreground">CL</div>0.604</div>
              <div><div className="text-[9px] text-muted-foreground">CD</div>0.0251</div>
              <div><div className="text-[9px] text-accent">L/D</div><span className="text-accent">24.06</span></div>
            </div>
          </div>
        </div>

        <div className="grid md:grid-cols-4 gap-4 mt-20">
          {[
            { icon: Plane, title: "Design", text: "Parametric wing form with live preview" },
            { icon: Workflow, title: "Optimize", text: "GA, NSGA2 & grid search algorithms" },
            { icon: BarChart3, title: "Compare", text: "Baseline vs. optimized overlays" },
            { icon: Wind, title: "Visualize", text: "Cp, pressure, velocity, streamlines" },
          ].map(({ icon: Icon, title, text }) => (
            <div key={title} className="panel p-5">
              <Icon className="h-5 w-5 text-primary mb-3" />
              <div className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">{title}</div>
              <div className="text-sm mt-1">{text}</div>
            </div>
          ))}
        </div>
      </main>
    </div>
  );
}
