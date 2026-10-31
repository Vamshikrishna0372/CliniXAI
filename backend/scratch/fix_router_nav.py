# Fix app.ai-analysis.tsx
p1 = r"clinixai-health-flow/src/routes/app.ai-analysis.tsx"
with open(p1, "r", encoding="utf-8") as f:
    c1 = f.read()

# Make sure imports are clean
c1 = c1.replace(
    'import { createFileRoute, Link, useNavigate, Outlet, useMatch, Navigate } from "@tanstack/react-router";',
    'import { createFileRoute, Link, useNavigate, Outlet, useMatch } from "@tanstack/react-router";'
)

old_comp_1 = """function AIAnalysisPage() {
  const { user } = useAuth();
  const isChild = useMatch({ from: "/app/ai-analysis/$id", shouldThrow: false });
  if (isChild) {
    return <Outlet />;
  }

  if (user?.role === "patient") {
    return <Navigate to="/app/ai-reports" replace />;
  }

  return <AIAnalysisForm />;
}"""

new_comp_1 = """function AIAnalysisPage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const isChild = useMatch({ from: "/app/ai-analysis/$id", shouldThrow: false });

  useEffect(() => {
    if (user?.role === "patient" && !isChild) {
      navigate({ to: "/app/ai-reports", replace: true });
    }
  }, [user?.role, isChild, navigate]);

  if (isChild) {
    return <Outlet />;
  }

  if (user?.role === "patient") {
    return null;
  }

  return <AIAnalysisForm />;
}"""

if old_comp_1 in c1:
    c1 = c1.replace(old_comp_1, new_comp_1)
    with open(p1, "w", encoding="utf-8") as f:
        f.write(c1)
    print("Fixed app.ai-analysis.tsx")
else:
    print("Could not find old_comp_1")

# Fix app.ai-analysis.$id.tsx
p2 = r"clinixai-health-flow/src/routes/app.ai-analysis.$id.tsx"
with open(p2, "r", encoding="utf-8") as f:
    c2 = f.read()

c2 = c2.replace(
    'import { createFileRoute, Link, useParams, Navigate } from "@tanstack/react-router";',
    'import { createFileRoute, Link, useParams, useNavigate } from "@tanstack/react-router";'
)

if 'import { useAuth } from "@/lib/auth-context";' not in c2:
    c2 = c2.replace(
        'import { useClinix } from "@/lib/store/clinix-store";',
        'import { useClinix } from "@/lib/store/clinix-store";\nimport { useAuth } from "@/lib/auth-context";'
    )

old_comp_2 = """  const { user } = useAuth();

  if (user?.role === "patient") {
    return <Navigate to="/app/ai-reports/$id" params={{ id }} replace />;
  }

  const activeReport = remoteReport || storeReport;
  const activePatient = remotePatient || storePatient;"""

new_comp_2 = """  const { user } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    if (user?.role === "patient") {
      navigate({ to: "/app/ai-reports/$id", params: { id }, replace: true });
    }
  }, [user?.role, id, navigate]);

  const activeReport = remoteReport || storeReport;
  const activePatient = remotePatient || storePatient;"""

if old_comp_2 in c2:
    c2 = c2.replace(old_comp_2, new_comp_2)
    with open(p2, "w", encoding="utf-8") as f:
        f.write(c2)
    print("Fixed app.ai-analysis.$id.tsx")
else:
    print("Could not find old_comp_2")

