import { useCallback, useEffect, useRef, useState } from "react";
import { ZoomIn, ZoomOut, RotateCcw, Maximize2, Minimize2, SplitSquareHorizontal, Layers, ImageIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Slider } from "@/components/ui/slider";
import { cn } from "@/lib/utils";

export type ImageViewMode = "side" | "overlay" | "original";

type Props = {
  /** Whether a Grad-CAM heatmap is available for this analysis. */
  heatmapAvailable?: boolean;
  /** Image source URL or base64 data URI for original image */
  originalSrc?: string;
  /** Image source URL or base64 data URI for Grad-CAM overlay image */
  gradcamSrc?: string;
  className?: string;
  mode?: ImageViewMode;
  onModeChange?: (mode: ImageViewMode) => void;
};

const MIN_SCALE = 1;
const MAX_SCALE = 5;

/**
 * Reusable medical-image viewer with Grad-CAM overlay, zoom/pan,
 * fullscreen and view-mode switching. Supports actual image URLs and fallback placeholders.
 */
export function MedicalImageViewer({ heatmapAvailable = true, originalSrc, gradcamSrc, className, mode: modeProp, onModeChange }: Props) {
  const [modeState, setModeState] = useState<ImageViewMode>("side");
  const mode = modeProp ?? modeState;
  const setMode = (m: ImageViewMode) => {
    setModeState(m);
    onModeChange?.(m);
  };
  const [opacity, setOpacity] = useState(0.7);
  const [scale, setScale] = useState(1);
  const [offset, setOffset] = useState({ x: 0, y: 0 });
  const [fullscreen, setFullscreen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const dragRef = useRef<{ x: number; y: number; ox: number; oy: number } | null>(null);

  const clampScale = (s: number) => Math.min(MAX_SCALE, Math.max(MIN_SCALE, s));

  const zoomAt = useCallback((factor: number, clientX?: number, clientY?: number) => {
    setScale((prev) => {
      const next = clampScale(prev * factor);
      if (containerRef.current && clientX !== undefined && clientY !== undefined) {
        const rect = containerRef.current.getBoundingClientRect();
        const cx = clientX - rect.left - rect.width / 2;
        const cy = clientY - rect.top - rect.height / 2;
        setOffset((o) => ({
          x: cx - (cx - o.x) * (next / prev),
          y: cy - (cy - o.y) * (next / prev),
        }));
      }
      return next;
    });
  }, []);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      const factor = Math.exp(-e.deltaY * 0.0015);
      zoomAt(factor, e.clientX, e.clientY);
    };
    el.addEventListener("wheel", onWheel, { passive: false });
    return () => el.removeEventListener("wheel", onWheel);
  }, [zoomAt]);

  const reset = () => {
    setScale(1);
    setOffset({ x: 0, y: 0 });
  };

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "+" || e.key === "=") { e.preventDefault(); zoomAt(1.2); }
    else if (e.key === "-" || e.key === "_") { e.preventDefault(); zoomAt(1 / 1.2); }
    else if (e.key === "0") { e.preventDefault(); reset(); }
  };

  const startDrag = (x: number, y: number) => {
    dragRef.current = { x, y, ox: offset.x, oy: offset.y };
  };
  const moveDrag = (x: number, y: number) => {
    if (!dragRef.current) return;
    const d = dragRef.current;
    setOffset({ x: d.ox + (x - d.x), y: d.oy + (y - d.y) });
  };
  const endDrag = () => { dragRef.current = null; };

  const imageStyle: React.CSSProperties = {
    transform: `translate(${offset.x}px, ${offset.y}px) scale(${scale})`,
    transition: dragRef.current ? "none" : "transform 0.05s linear",
  };

  const Frame = ({ children, label, isHeatmap }: { children?: React.ReactNode; label: string; isHeatmap?: boolean }) => {
    const src = isHeatmap ? (gradcamSrc || originalSrc) : originalSrc;
    return (
      <div
        className={cn(
          "relative aspect-video min-w-0 select-none overflow-hidden rounded-lg border border-border bg-gradient-to-br from-slate-800 to-slate-950",
          isHeatmap && "border-none",
        )}
      >
        <div
          className="absolute inset-0 grid place-items-center will-change-transform"
          style={isHeatmap ? { ...imageStyle, opacity } : imageStyle}
        >
          {src ? (
            <img src={src} alt={label} className="h-full w-full object-contain" />
          ) : (
            <div className="flex flex-col items-center justify-center p-6 text-center text-xs text-muted-foreground/60 select-none">
              <ImageIcon className="h-8 w-8 mb-2 opacity-40" />
              <span>{isHeatmap ? "Grad-CAM heatmap unavailable" : "Original scan unavailable"}</span>
            </div>
          )}
        </div>
        {label && <span className="pointer-events-none absolute bottom-1.5 left-1.5 rounded bg-black/50 px-1.5 py-0.5 text-[10px] text-white/80">{label}</span>}
      </div>
    );
  };

  return (
    <div className={cn("space-y-3", className, fullscreen && "fixed inset-0 z-50 bg-background p-4 overflow-auto")}>
      <div className="flex flex-wrap items-center gap-2">
        <div className="flex flex-wrap gap-1" role="group" aria-label="View mode">
          <Button type="button" variant={mode === "side" ? "default" : "outline"} size="sm" onClick={() => setMode("side")} disabled={!heatmapAvailable}>
            <SplitSquareHorizontal className="h-4 w-4" /> Side-by-side
          </Button>
          <Button type="button" variant={mode === "overlay" ? "default" : "outline"} size="sm" onClick={() => setMode("overlay")} disabled={!heatmapAvailable}>
            <Layers className="h-4 w-4" /> Overlay
          </Button>
          <Button type="button" variant={mode === "original" ? "default" : "outline"} size="sm" onClick={() => setMode("original")}>
            <ImageIcon className="h-4 w-4" /> Original only
          </Button>
        </div>
        <div className="ml-auto flex items-center gap-1">
          <Button type="button" variant="outline" size="icon" aria-label="Zoom out" onClick={() => zoomAt(1 / 1.2)}><ZoomOut className="h-4 w-4" /></Button>
          <Button type="button" variant="outline" size="icon" aria-label="Zoom in" onClick={() => zoomAt(1.2)}><ZoomIn className="h-4 w-4" /></Button>
          <Button type="button" variant="outline" size="icon" aria-label="Reset zoom and pan" onClick={reset}><RotateCcw className="h-4 w-4" /></Button>
          <Button type="button" variant="outline" size="icon" aria-label={fullscreen ? "Exit fullscreen" : "Enter fullscreen"} onClick={() => setFullscreen((f) => !f)}>
            {fullscreen ? <Minimize2 className="h-4 w-4" /> : <Maximize2 className="h-4 w-4" />}
          </Button>
        </div>
      </div>

      <div
        ref={containerRef}
        tabIndex={0}
        role="application"
        aria-label="Medical image viewer. Use plus and minus to zoom, 0 to reset, drag to pan."
        onKeyDown={onKeyDown}
        onMouseDown={(e) => startDrag(e.clientX, e.clientY)}
        onMouseMove={(e) => moveDrag(e.clientX, e.clientY)}
        onMouseUp={endDrag}
        onMouseLeave={endDrag}
        onTouchStart={(e) => { const t = e.touches[0]; if (t) startDrag(t.clientX, t.clientY); }}
        onTouchMove={(e) => { const t = e.touches[0]; if (t) moveDrag(t.clientX, t.clientY); }}
        onTouchEnd={endDrag}
        className="cursor-grab rounded-lg outline-none focus-visible:ring-2 focus-visible:ring-ring active:cursor-grabbing"
      >
        {mode === "side" && heatmapAvailable ? (
          <div className="grid gap-3 sm:grid-cols-2">
            <Frame label="Original image" />
            <Frame label="Grad-CAM heatmap" isHeatmap />
          </div>
        ) : mode === "overlay" && heatmapAvailable ? (
          <div className="relative">
            <Frame label="Original + Grad-CAM" />
            <div className="pointer-events-none absolute inset-0">
              <Frame label="" isHeatmap />
            </div>
          </div>
        ) : (
          <Frame label={heatmapAvailable ? "Original image" : "Original image (Grad-CAM unavailable)"} />
        )}
      </div>

      {heatmapAvailable && mode !== "original" && (
        <div className="flex items-center gap-3">
          <span className="text-xs text-muted-foreground shrink-0">Heatmap opacity</span>
          <Slider
            id="gradcam-opacity-slider"
            data-testid="gradcam-opacity-slider"
            value={[opacity * 100]}
            min={0}
            max={100}
            step={5}
            className="max-w-xs"
            onValueChange={([v]) => setOpacity((v ?? 70) / 100)}
            aria-label="Heatmap opacity"
          />
          <span className="w-10 shrink-0 text-right text-xs tabular-nums text-muted-foreground" data-testid="opacity-value-label">{Math.round(opacity * 100)}%</span>
        </div>
      )}

      <p className="text-xs text-muted-foreground">
        Highlighted regions indicate areas that contributed more strongly to the model's prediction. They do not prove disease.
      </p>
    </div>
  );
}
