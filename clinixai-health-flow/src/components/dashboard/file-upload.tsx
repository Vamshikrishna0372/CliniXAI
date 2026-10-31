import { useRef, useState, type ChangeEvent, type DragEvent } from "react";
import { UploadCloud, X, FileIcon, CheckCircle2, AlertCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

type SelectedItem = {
  id: string;
  file: File;
  previewUrl?: string;
  error?: string;
};

function fmt(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10MB

export function FileUpload({
  accept = "image/jpeg,image/png,image/webp,application/pdf",
  multiple = false,
  label = "Drag & drop medical file here",
  hint = "JPEG, PNG, WEBP, PDF up to 10 MB",
  className,
  onFileSelect,
}: {
  accept?: string;
  multiple?: boolean;
  label?: string;
  hint?: string;
  className?: string;
  onFileSelect?: (file: File) => void;
}) {
  const [items, setItems] = useState<SelectedItem[]>([]);
  const [drag, setDrag] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const addFiles = (fs: FileList | null) => {
    if (!fs || fs.length === 0) return;
    const fileList = Array.from(fs);
    const validItems: SelectedItem[] = [];

    fileList.forEach((f) => {
      let err: string | undefined;
      if (f.size > MAX_FILE_SIZE) {
        err = `Exceeds 10 MB limit (${(f.size / (1024 * 1024)).toFixed(1)} MB)`;
      } else if (f.size === 0) {
        err = "File is empty (0 bytes)";
      }

      const item: SelectedItem = {
        id: crypto.randomUUID(),
        file: f,
        previewUrl: f.type.startsWith("image/") ? URL.createObjectURL(f) : undefined,
        error: err,
      };
      validItems.push(item);
      if (!err) {
        onFileSelect?.(f);
      }
    });

    setItems((prev) => (multiple ? [...prev, ...validItems] : validItems));
  };

  const onDrop = (e: DragEvent) => {
    e.preventDefault();
    setDrag(false);
    addFiles(e.dataTransfer.files);
  };

  const remove = (id: string) => setItems((xs) => xs.filter((x) => x.id !== id));

  return (
    <div className={cn("space-y-3", className)}>
      <div
        onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
        onDragLeave={() => setDrag(false)}
        onDrop={onDrop}
        onClick={() => inputRef.current?.click()}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && inputRef.current?.click()}
        className={cn(
          "flex cursor-pointer flex-col items-center justify-center rounded-2xl border-2 border-dashed border-border bg-muted/30 px-6 py-8 text-center transition-colors",
          drag && "border-primary bg-primary-soft/40",
        )}
      >
        <span className="grid h-12 w-12 place-items-center rounded-full bg-primary/10 text-primary">
          <UploadCloud className="h-6 w-6" />
        </span>
        <p className="mt-3 text-sm font-medium text-foreground">{label}</p>
        <p className="text-xs text-muted-foreground">{hint}</p>
        <input
          ref={inputRef}
          type="file"
          aria-label={label}
          accept={accept}
          multiple={multiple}
          className="hidden"
          tabIndex={-1}
          onChange={(e: ChangeEvent<HTMLInputElement>) => addFiles(e.target.files)}
        />
      </div>

      {items.length > 0 && (
        <ul className="space-y-2">
          {items.map((it) => (
            <li
              key={it.id}
              className={cn(
                "flex items-center gap-3 rounded-xl border p-3 bg-card",
                it.error ? "border-destructive/40 bg-destructive/5" : "border-border"
              )}
            >
              <div className="grid h-11 w-11 shrink-0 place-items-center overflow-hidden rounded-lg bg-muted">
                {it.previewUrl ? (
                  <img src={it.previewUrl} alt={it.file.name} className="h-full w-full object-cover" />
                ) : (
                  <FileIcon className="h-5 w-5 text-muted-foreground" />
                )}
              </div>
              <div className="min-w-0 flex-1">
                <div className="flex items-center justify-between gap-2">
                  <p className="truncate text-sm font-medium text-foreground">{it.file.name}</p>
                  <span className="shrink-0 text-xs text-muted-foreground">{fmt(it.file.size)}</span>
                </div>
                {it.error ? (
                  <div className="mt-1 flex items-center gap-1.5 text-xs text-destructive">
                    <AlertCircle className="h-3.5 w-3.5 shrink-0" />
                    <span>{it.error}</span>
                  </div>
                ) : (
                  <div className="mt-1 flex items-center gap-1.5 text-xs text-success">
                    <CheckCircle2 className="h-3.5 w-3.5 shrink-0" />
                    <span>Ready to upload</span>
                  </div>
                )}
              </div>
              <Button
                variant="ghost"
                size="icon"
                onClick={(e) => { e.stopPropagation(); remove(it.id); }}
                aria-label="Remove"
              >
                <X className="h-4 w-4" />
              </Button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
