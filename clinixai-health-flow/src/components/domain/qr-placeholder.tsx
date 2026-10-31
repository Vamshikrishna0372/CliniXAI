import { cn } from "@/lib/utils";

// Deterministic QR-like SVG pattern (visually a QR code — not scannable). Mock-only.
export function QRPlaceholder({ value, size = 192, className }: { value: string; size?: number; className?: string }) {
  const grid = 21;
  // seed-based pseudo-random
  let seed = 0;
  for (let i = 0; i < value.length; i++) seed = (seed * 31 + value.charCodeAt(i)) >>> 0;
  const rand = () => {
    seed = (seed * 1664525 + 1013904223) >>> 0;
    return seed / 0xffffffff;
  };
  const cells: boolean[][] = Array.from({ length: grid }, () => Array(grid).fill(false));
  for (let y = 0; y < grid; y++) for (let x = 0; x < grid; x++) cells[y][x] = rand() > 0.5;
  // finder patterns
  const finder = (ox: number, oy: number) => {
    for (let y = 0; y < 7; y++) for (let x = 0; x < 7; x++) {
      const outer = x === 0 || x === 6 || y === 0 || y === 6;
      const inner = x >= 2 && x <= 4 && y >= 2 && y <= 4;
      cells[oy + y][ox + x] = outer || inner;
    }
  };
  finder(0, 0); finder(grid - 7, 0); finder(0, grid - 7);
  const cs = size / grid;
  return (
    <svg
      viewBox={`0 0 ${size} ${size}`}
      width={size}
      height={size}
      className={cn("rounded-lg bg-white p-2", className)}
      role="img"
      aria-label="Mock QR code"
    >
      {cells.flatMap((row, y) =>
        row.map((on, x) =>
          on ? <rect key={`${x}-${y}`} x={x * cs} y={y * cs} width={cs} height={cs} fill="#0f172a" /> : null,
        ),
      )}
    </svg>
  );
}
