import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  Legend,
} from "recharts";
import type { AirfoilPlot } from "@/lib/api";

interface Series {
  data: AirfoilPlot;
  label: string;
  color: string;
}

export function AirfoilChart({ series, height = 260 }: { series: Series[]; height?: number }) {
  const len = Math.max(...series.map((s) => s.data.x.length));
  const rows = Array.from({ length: len }, (_, i) => {
    const row: any = { x: series[0].data.x[i] };
    series.forEach((s) => {
      row[`${s.label}_upper`] = s.data.upper_y[i];
      row[`${s.label}_lower`] = s.data.lower_y[i];
      row[`${s.label}_camber`] = s.data.camber_y[i];
    });
    return row;
  });

  const allX = series.flatMap((s) => s.data.x);
  const allY = series.flatMap((s) => [...s.data.upper_y, ...s.data.lower_y, ...s.data.camber_y]);
  const xMin = Math.min(...allX);
  const xMax = Math.max(...allX);
  const yMin = Math.min(...allY);
  const yMax = Math.max(...allY);
  const xPad = (xMax - xMin) * 0.04;
  const yPad = (yMax - yMin) * 0.15;

  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={rows} margin={{ top: 8, right: 16, bottom: 8, left: 0 }}>
        <CartesianGrid strokeDasharray="2 4" stroke="var(--color-border)" />
        <XAxis
          dataKey="x"
          type="number"
          domain={[xMin - xPad, xMax + xPad]}
          tick={{ fontSize: 10, fontFamily: "var(--font-mono)" }}
          stroke="var(--color-muted-foreground)"
          tickFormatter={(v) => v.toFixed(2)}
        />
        <YAxis
          domain={[yMin - yPad, yMax + yPad]}
          tick={{ fontSize: 10, fontFamily: "var(--font-mono)" }}
          stroke="var(--color-muted-foreground)"
          tickFormatter={(v) => v.toFixed(3)}
        />
        <Tooltip
          contentStyle={{
            background: "var(--color-popover)",
            border: "1px solid var(--color-border)",
            fontFamily: "var(--font-mono)",
            fontSize: 11,
          }}
        />
        <Legend wrapperStyle={{ fontFamily: "var(--font-mono)", fontSize: 10 }} />
        {series.flatMap((s) => [
          <Line key={`${s.label}-u`} type="monotone" dataKey={`${s.label}_upper`} name={`${s.label} upper`} stroke={s.color} dot={false} strokeWidth={1.5} isAnimationActive={false} />,
          <Line key={`${s.label}-l`} type="monotone" dataKey={`${s.label}_lower`} name={`${s.label} lower`} stroke={s.color} dot={false} strokeWidth={1.5} isAnimationActive={false} />,
          <Line key={`${s.label}-c`} type="monotone" dataKey={`${s.label}_camber`} name={`${s.label} camber`} stroke={s.color} dot={false} strokeDasharray="3 3" strokeWidth={1} opacity={0.6} isAnimationActive={false} />,
        ])}
      </LineChart>
    </ResponsiveContainer>
  );
}