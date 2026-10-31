import { useState, type InputHTMLAttributes } from "react";
import { Eye, EyeOff } from "lucide-react";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";

type Props = InputHTMLAttributes<HTMLInputElement> & { wrapperClassName?: string };

export function PasswordInput({ wrapperClassName, className, ...props }: Props) {
  const [show, setShow] = useState(false);
  return (
    <div className={cn("relative", wrapperClassName)}>
      <Input {...props} type={show ? "text" : "password"} className={cn("pr-10", className)} />
      <button
        type="button"
        onClick={() => setShow((s) => !s)}
        aria-label={show ? "Hide password" : "Show password"}
        className="absolute inset-y-0 right-0 grid w-10 place-items-center text-muted-foreground hover:text-foreground"
      >
        {show ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
      </button>
    </div>
  );
}

export function scorePassword(pw: string): { score: 0 | 1 | 2 | 3 | 4; label: string; checks: { label: string; ok: boolean }[] } {
  const checks = [
    { label: "At least 8 characters", ok: pw.length >= 8 },
    { label: "Upper & lowercase letters", ok: /[a-z]/.test(pw) && /[A-Z]/.test(pw) },
    { label: "A number", ok: /\d/.test(pw) },
    { label: "A symbol", ok: /[^A-Za-z0-9]/.test(pw) },
  ];
  const score = checks.filter((c) => c.ok).length as 0 | 1 | 2 | 3 | 4;
  const label = ["Too weak", "Weak", "Fair", "Strong", "Excellent"][score];
  return { score, label, checks };
}

export function PasswordStrength({ password }: { password: string }) {
  const { score, label, checks } = scorePassword(password);
  const colors = ["bg-error", "bg-error", "bg-warning", "bg-info", "bg-success"];
  return (
    <div className="mt-2 space-y-2">
      <div className="flex gap-1.5">
        {[0, 1, 2, 3].map((i) => (
          <div key={i} className={cn("h-1.5 flex-1 rounded-full transition-colors", i < score ? colors[score] : "bg-muted")} />
        ))}
      </div>
      <div className="flex items-center justify-between text-xs">
        <span className="text-muted-foreground">Password strength</span>
        <span className="font-medium text-foreground">{password ? label : "—"}</span>
      </div>
      <ul className="grid grid-cols-1 gap-1 text-xs text-muted-foreground sm:grid-cols-2">
        {checks.map((c) => (
          <li key={c.label} className={cn("flex items-center gap-1.5", c.ok && "text-success")}>
            <span className={cn("h-1.5 w-1.5 rounded-full", c.ok ? "bg-success" : "bg-muted-foreground/40")} />
            {c.label}
          </li>
        ))}
      </ul>
    </div>
  );
}
