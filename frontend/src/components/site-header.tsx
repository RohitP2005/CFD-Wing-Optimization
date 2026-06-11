import { Link } from "@tanstack/react-router";
import { Plane } from "lucide-react";

export function SiteHeader() {
  return (
    <header className="sticky top-0 z-40 border-b border-border bg-background/80 backdrop-blur-md">
      <div className="mx-auto flex h-14 max-w-[1600px] items-center justify-between px-6">
        <Link to="/" className="flex items-center gap-2.5 group">
          <div className="flex h-8 w-8 items-center justify-center rounded-md bg-primary/15 text-primary group-hover:bg-primary/25 transition">
            <Plane className="h-4 w-4" strokeWidth={2.5} />
          </div>
          <div className="font-mono text-sm tracking-tight">
            <span className="text-foreground font-semibold">AEROFOIL</span>
            <span className="text-muted-foreground">.lab</span>
          </div>
        </Link>
        <nav className="flex items-center gap-1 font-mono text-xs uppercase tracking-wider">
          <Link
            to="/"
            activeOptions={{ exact: true }}
            activeProps={{ className: "text-primary" }}
            inactiveProps={{ className: "text-muted-foreground" }}
            className="px-3 py-1.5 rounded hover:text-foreground transition"
          >
            Home
          </Link>
          <Link
            to="/projects"
            activeProps={{ className: "text-primary" }}
            inactiveProps={{ className: "text-muted-foreground" }}
            className="px-3 py-1.5 rounded hover:text-foreground transition"
          >
            Projects
          </Link>
        </nav>
      </div>
    </header>
  );
}