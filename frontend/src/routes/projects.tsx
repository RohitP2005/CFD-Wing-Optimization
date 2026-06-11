import { createFileRoute, Outlet } from "@tanstack/react-router";
import { SiteHeader } from "@/components/site-header";

export const Route = createFileRoute("/projects")({
  component: () => (
    <div className="min-h-screen">
      <SiteHeader />
      <Outlet />
    </div>
  ),
});