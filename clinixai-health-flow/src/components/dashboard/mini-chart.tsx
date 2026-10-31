import { cn } from "@/lib/utils";

/* Lightweight dependency-free SVG charts. */

export function BarSeries({
  data, height = 180, formatValue, className,
}: {
  data: { label: string; value: number }[];
  height?: number;
  formatValue?: (v: number) => string;
  className?: string;
}) {
  const max = Math.max(1, ...data.map((d) => d.value));
  return (
    <div className={cn("w-full overflow-x-auto", className)}>
      <div className="flex min-w-full items-end gap-2" style={{ height }}>
        {data.map((d) => {
          const h = Math.max(4, (d.value / max) * (height - 40));
          return (
            <div key={d.label} className="flex min-w-[38px] flex-1 flex-col items-center gap-1.5">
              <span className="text-[10px] font-medium text-muted-foreground">
                {formatValue ? formatValue(d.value) : d.value}
              </span>
              <div
                className="w-full rounded-t-md bg-primary/80 transition-colors hover:bg-primary"
                style={{ height: h }}
                aria-label={`${d.label}: ${d.value}`}
                role="img"
              />
              <span className="w-full truncate text-center text-[10px] text-muted-foreground" title={d.label}>
                {d.label}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export function LineSeries({
  data, height = 180, className,
}: {
  data: { label: string; value: number }[];
  height?: number;
  className?: string;
}) {
  if (data.length === 0) return null;
  const w = 600;
  const max = Math.max(1, ...data.map((d) => d.value));
  const step = w / Math.max(1, data.length - 1);
  const points = data.map((d, i) => `${i * step},${height - (d.value / max) * (height - 20) - 10}`);
  const area = `M0,${height} L${points.join(" L")} L${w},${height} Z`;
  return (
    <div className={cn("w-full", className)}>
      <svg viewBox={`0 0 ${w} ${height}`} preserveAspectRatio="none" className="h-[180px] w-full text-primary">
        <path d={area} fill="currentColor" opacity="0.12" />
        <polyline points={points.join(" ")} fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
        {data.map((d, i) => (
          <circle key={i} cx={i * step} cy={height - (d.value / max) * (height - 20) - 10} r="3" fill="currentColor" />
        ))}
      </svg>
      <div className="mt-1 flex justify-between gap-2 text-[10px] text-muted-foreground">
        {data.map((d) => <span key={d.label} className="truncate">{d.label}</span>)}
      </div>
    </div>
  );
}

export function DonutChart({
  data, size = 160, className,
}: {
  data: { label: string; value: number; color?: string }[];
  size?: number;
  className?: string;
}) {
  const total = data.reduce((s, d) => s + d.value, 0) || 1;
  const palette = ["hsl(var(--primary))", "hsl(var(--accent))", "hsl(var(--warning))", "hsl(var(--success))", "hsl(var(--error))", "hsl(var(--muted-foreground))"];
  let acc = 0;
  const r = size / 2 - 12;
  const cx = size / 2;
  const cy = size / 2;
  const segs = data.map((d, i) => {
    const start = (acc / total) * 2 * Math.PI;
    acc += d.value;
    const end = (acc / total) * 2 * Math.PI;
    const large = end - start > Math.PI ? 1 : 0;
    const x1 = cx + r * Math.sin(start);
    const y1 = cy - r * Math.cos(start);
    const x2 = cx + r * Math.sin(end);
    const y2 = cy - r * Math.cos(end);
    return {
      path: `M ${cx} ${cy} L ${x1} ${y1} A ${r} ${r} 0 ${large} 1 ${x2} ${y2} Z`,
      color: d.color ?? palette[i % palette.length],
      label: d.label,
      value: d.value,
    };
  });
  return (
    <div className={cn("flex flex-wrap items-center gap-4", className)}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
        {segs.map((s, i) => <path key={i} d={s.path} fill={s.color} />)}
        <circle cx={cx} cy={cy} r={r * 0.6} fill="hsl(var(--card))" />
        <text x={cx} y={cy + 4} textAnchor="middle" className="fill-foreground text-sm font-semibold">{total}</text>
      </svg>
      <ul className="min-w-0 space-y-1.5 text-xs">
        {segs.map((s) => (
          <li key={s.label} className="flex items-center gap-2">
            <span className="h-2.5 w-2.5 shrink-0 rounded-sm" style={{ background: s.color }} />
            <span className="capitalize text-foreground">{s.label}</span>
            <span className="text-muted-foreground">· {s.value}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function HBarSeries({
  data, formatValue, className,
}: {
  data: { label: string; value: number }[];
  formatValue?: (v: number) => string;
  className?: string;
}) {
  const max = Math.max(1, ...data.map((d) => d.value));
  return (
    <ul className={cn("space-y-2", className)}>
      {data.map((d) => (
        <li key={d.label}>
          <div className="mb-1 flex items-center justify-between gap-3 text-xs">
            <span className="min-w-0 truncate text-foreground">{d.label}</span>
            <span className="shrink-0 font-medium text-muted-foreground">{formatValue ? formatValue(d.value) : d.value}</span>
          </div>
          <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
            <div className="h-full rounded-full bg-primary" style={{ width: `${(d.value / max) * 100}%` }} />
          </div>
        </li>
      ))}
    </ul>
  );
}
