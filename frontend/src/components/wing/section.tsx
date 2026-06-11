import type { ReactNode } from "react";

export function Section({ title, subtitle, action, children, className = "" }: {
  title: string;
  subtitle?: string;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={`panel p-5 ${className}`}>
      <div className="flex items-start justify-between mb-4 gap-4">
        <div>
          <h3 className="font-mono text-[11px] uppercase tracking-[0.18em] text-primary">{title}</h3>
          {subtitle && <p className="text-xs text-muted-foreground mt-1">{subtitle}</p>}
        </div>
        {action}
      </div>
      {children}
    </section>
  );
}