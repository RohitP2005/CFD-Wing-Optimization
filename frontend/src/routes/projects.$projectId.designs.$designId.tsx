import { createFileRoute, Outlet } from "@tanstack/react-router";

export const Route = createFileRoute("/projects/$projectId/designs/$designId")({
  component: () => <Outlet />,
});
