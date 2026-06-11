import { useMemo } from "react";
import type { PlanformPlot } from "@/lib/api";

interface Series {
  data: PlanformPlot;
  label: string;
  color: string;
  dashed?: boolean;
}

export function PlanformChart({ series, height = 260 }: { series: Series[]; height?: number }) {
  const { paths, bounds } = useMemo(() => {
    let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
    for (const s of series) {
      for (let i = 0; i < s.data.outline_chord_x.length; i++) {
        const x = s.data.outline_chord_x[i];
        const y = s.data.outline_span_y[i];
        if (x < minX) minX = x;
        if (x > maxX) maxX = x;
        if (y < minY) minY = y;
        if (y > maxY) maxY = y;
      }
    }
    const padX = (maxX - minX) * 0.08 || 0.5;
    const padY = (maxY - minY) * 0.08 || 0.5;
    return {
      paths: series.map((s) => ({
        ...s,
        d:
          s.data.outline_chord_x
            .map((x, i) => `${i === 0 ? "M" : "L"} ${x} ${s.data.outline_span_y[i]}`)
            .join(" ") + " Z",
      })),
      bounds: { minX: minX - padX, maxX: maxX + padX, minY: minY - padY, maxY: maxY + padY },
    };
  }, [series]);

  const w = bounds.maxX - bounds.minX;
  const h = bounds.maxY - bounds.minY;

  return (
    <div className="w-full" style={{ height }}>
      <svg
        viewBox={`${bounds.minX} ${bounds.minY} ${w} ${h}`}
        preserveAspectRatio="xMidYMid meet"
        className="w-full h-full"
      >
        <line x1={bounds.minX} y1={0} x2={bounds.maxX} y2={0} stroke="var(--color-muted-foreground)" strokeWidth={0.02} strokeDasharray="0.1 0.1" />
        <line x1={0} y1={bounds.minY} x2={0} y2={bounds.maxY} stroke="var(--color-muted-foreground)" strokeWidth={0.02} strokeDasharray="0.1 0.1" />
        {paths.map((p, i) => (
          <path
            key={i}
            d={p.d}
            fill={p.color}
            fillOpacity={0.08}
            stroke={p.color}
            strokeWidth={0.04}
            strokeDasharray={p.dashed ? "0.15 0.1" : undefined}
            vectorEffect="non-scaling-stroke"
          />
        ))}
      </svg>
    </div>
  );
}