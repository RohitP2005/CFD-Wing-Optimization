import type { ReactNode } from "react";

export function EmptyState({ icon, title, description, action }: {
  icon?: ReactNode;
  title: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <div className="panel p-10 flex flex-col items-center text-center">
      {icon && <div className="mb-3 text-muted-foreground/70">{icon}</div>}
      <h3 className="font-mono text-sm uppercase tracking-wider text-foreground">{title}</h3>
      {description && <p className="text-sm text-muted-foreground mt-1 max-w-md">{description}</p>}
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}