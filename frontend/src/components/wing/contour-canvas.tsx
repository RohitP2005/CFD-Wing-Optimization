import { useEffect, useRef } from "react";

function turbo(t: number): [number, number, number] {
  t = Math.max(0, Math.min(1, t));
  const r = Math.round(34 + 220 * Math.sin(Math.PI * t));
  const g = Math.round(50 + 200 * Math.sin(Math.PI * (t + 0.25)));
  const b = Math.round(255 - 220 * t);
  return [Math.max(0, Math.min(255, r)), Math.max(0, Math.min(255, g)), Math.max(0, Math.min(255, b))];
}

export function ContourCanvas({ grid, height = 320 }: { grid: number[][]; height?: number }) {
  const ref = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const cvs = ref.current;
    if (!cvs || !grid?.length) return;
    const rows = grid.length;
    const cols = grid[0].length;
    let min = Infinity, max = -Infinity;
    for (const row of grid) for (const v of row) {
      if (Number.isFinite(v)) { if (v < min) min = v; if (v > max) max = v; }
    }
    const span = max - min || 1;
    cvs.width = cols;
    cvs.height = rows;
    const ctx = cvs.getContext("2d")!;
    const img = ctx.createImageData(cols, rows);
    for (let r = 0; r < rows; r++) {
      for (let c = 0; c < cols; c++) {
        const v = grid[r][c];
        const t = (v - min) / span;
        const [rr, gg, bb] = turbo(t);
        const idx = (r * cols + c) * 4;
        img.data[idx] = rr;
        img.data[idx + 1] = gg;
        img.data[idx + 2] = bb;
        img.data[idx + 3] = 235;
      }
    }
    ctx.putImageData(img, 0, 0);
  }, [grid]);

  return (
    <canvas
      ref={ref}
      style={{
        width: "100%",
        height,
        imageRendering: "auto",
        borderRadius: 6,
        border: "1px solid var(--color-border)",
        background: "var(--color-card)",
      }}
    />
  );
}