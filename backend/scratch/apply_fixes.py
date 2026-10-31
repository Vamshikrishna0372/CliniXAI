import os

# 1. Update roles.ts
roles_path = r"clinixai-health-flow/src/lib/roles.ts"
with open(roles_path, "r", encoding="utf-8") as f:
    roles_content = f.read()

target_roles = 'patient: ["book", "doctors", "appointments", "medical-records", "timeline", "ai-reports", "prescriptions", "bills", "qr-card", "settings", "profile", "notifications", "documents"],'
repl_roles = 'patient: ["book", "doctors", "appointments", "medical-records", "timeline", "ai-reports", "prescriptions", "bills", "qr-card", "settings", "profile", "notifications", "documents", "ai-analysis"],'

if target_roles in roles_content:
    roles_content = roles_content.replace(target_roles, repl_roles)
    with open(roles_path, "w", encoding="utf-8") as f:
        f.write(roles_content)
    print("roles.ts updated successfully")
else:
    print("target_roles not found in roles.ts")

# 2. Update app.ai-analysis.tsx to redirect patient to /app/ai-reports
ai_analysis_path = r"clinixai-health-flow/src/routes/app.ai-analysis.tsx"
with open(ai_analysis_path, "r", encoding="utf-8") as f:
    ai_analysis_content = f.read()

old_component = """function AIAnalysisPage() {
  const isChild = useMatch({ from: "/app/ai-analysis/$id", shouldThrow: false });
  if (isChild) {
    return <Outlet />;
  }

  return <AIAnalysisForm />;
}"""

new_component = """function AIAnalysisPage() {
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

if old_component in ai_analysis_content:
    if "Navigate" not in ai_analysis_content:
        ai_analysis_content = ai_analysis_content.replace(
            'import { createFileRoute, Link, useNavigate, Outlet, useMatch } from "@tanstack/react-router";',
            'import { createFileRoute, Link, useNavigate, Outlet, useMatch, Navigate } from "@tanstack/react-router";'
        )
    ai_analysis_content = ai_analysis_content.replace(old_component, new_component)
    with open(ai_analysis_path, "w", encoding="utf-8") as f:
        f.write(ai_analysis_content)
    print("app.ai-analysis.tsx updated successfully")
else:
    print("old_component not found in app.ai-analysis.tsx")

# 3. Update app.ai-analysis.$id.tsx to redirect patient to /app/ai-reports/$id
ai_analysis_detail_path = r"clinixai-health-flow/src/routes/app.ai-analysis.$id.tsx"
with open(ai_analysis_detail_path, "r", encoding="utf-8") as f:
    ai_detail_content = f.read()

old_detail_nav = """  const { id } = useParams({ from: "/app/ai-analysis/$id" });
  const navigate = useNavigate();"""

if "Navigate" not in ai_detail_content:
    ai_detail_content = ai_detail_content.replace(
        'import { createFileRoute, Link, useParams } from "@tanstack/react-router";',
        'import { createFileRoute, Link, useParams, Navigate } from "@tanstack/react-router";'
    )

target_hook = """  const activeReport = remoteReport || storeReport;
  const activePatient = remotePatient || storePatient;"""

repl_hook = """  const { user } = useAuth();

  if (user?.role === "patient") {
    return <Navigate to="/app/ai-reports/$id" params={{ id }} replace />;
  }

  const activeReport = remoteReport || storeReport;
  const activePatient = remotePatient || storePatient;"""

if target_hook in ai_detail_content:
    ai_detail_content = ai_detail_content.replace(target_hook, repl_hook)
    with open(ai_analysis_detail_path, "w", encoding="utf-8") as f:
        f.write(ai_detail_content)
    print("app.ai-analysis.$id.tsx updated successfully")
else:
    print("target_hook not found in app.ai-analysis.$id.tsx")

# 4. Update app.notifications.tsx
notif_path = r"clinixai-health-flow/src/routes/app.notifications.tsx"
with open(notif_path, "r", encoding="utf-8") as f:
    notif_content = f.read()

target_notif = """                  } else if (n.category === "ai-report" || n.referenceType === "ai_analysis") {
                    navigate({ to: "/app/ai-analysis" });
                  }"""

repl_notif = """                  } else if (n.category === "ai-report" || n.referenceType === "ai_analysis") {
                    const isPatient = user?.role === "patient";
                    if (isPatient) {
                      if (n.referenceId) navigate({ to: "/app/ai-reports/$id", params: { id: n.referenceId } });
                      else navigate({ to: "/app/ai-reports" });
                    } else {
                      if (n.referenceId) navigate({ to: "/app/ai-analysis/$id", params: { id: n.referenceId } });
                      else navigate({ to: "/app/ai-analysis" });
                    }
                  }"""

if target_notif in notif_content:
    notif_content = notif_content.replace(target_notif, repl_notif)
    with open(notif_path, "w", encoding="utf-8") as f:
        f.write(notif_content)
    print("app.notifications.tsx updated successfully")
else:
    print("target_notif not found in app.notifications.tsx")

# 5. Update notifications-panel.tsx
panel_path = r"clinixai-health-flow/src/components/app-shell/notifications-panel.tsx"
with open(panel_path, "r", encoding="utf-8") as f:
    panel_content = f.read()

target_panel = """                  } else if (n.category === "ai-report" || n.referenceType === "ai_analysis") {
                    navigate({ to: "/app/ai-analysis" });
                  }"""

repl_panel = """                  } else if (n.category === "ai-report" || n.referenceType === "ai_analysis") {
                    const isPatient = (user?.rawRole || user?.role || "").toLowerCase() === "patient";
                    if (isPatient) {
                      if (n.referenceId) navigate({ to: "/app/ai-reports/$id", params: { id: n.referenceId } });
                      else navigate({ to: "/app/ai-reports" });
                    } else {
                      if (n.referenceId) navigate({ to: "/app/ai-analysis/$id", params: { id: n.referenceId } });
                      else navigate({ to: "/app/ai-analysis" });
                    }
                  }"""

if target_panel in panel_content:
    panel_content = panel_content.replace(target_panel, repl_panel)
    with open(panel_path, "w", encoding="utf-8") as f:
        f.write(panel_content)
    print("notifications-panel.tsx updated successfully")
else:
    print("target_panel not found in notifications-panel.tsx")

# 6. Update app.ai-reports.$id.tsx to load original image via apiClient.ai.getOriginalImageBlob
reports_detail_path = r"clinixai-health-flow/src/routes/app.ai-reports.$id.tsx"
with open(reports_detail_path, "r", encoding="utf-8") as f:
    rep_content = f.read()

target_rep_img = """      if (r.documentId) {
        apiClient.documents.getFileBlob(r.documentId)
          .then((blob) => {
            if (!cancelled && blob) {
              origUrl = URL.createObjectURL(blob);
              setOriginalBlobUrl(origUrl);
            }
          })
          .catch(() => {});
      } else if (r.medicalRecordId) {
        apiClient.medicalRecords.getFileBlob(r.medicalRecordId)
          .then((blob) => {
            if (!cancelled && blob) {
              origUrl = URL.createObjectURL(blob);
              setOriginalBlobUrl(origUrl);
            }
          })
          .catch(() => {});
      }"""

repl_rep_img = """      apiClient.ai.getOriginalImageBlob(r.id)
        .then((blob) => {
          if (!cancelled && blob) {
            origUrl = URL.createObjectURL(blob);
            setOriginalBlobUrl(origUrl);
          }
        })
        .catch(() => {
          if (r.documentId) {
            apiClient.documents.getFileBlob(r.documentId)
              .then((blob) => {
                if (!cancelled && blob) {
                  origUrl = URL.createObjectURL(blob);
                  setOriginalBlobUrl(origUrl);
                }
              })
              .catch(() => {});
          } else if (r.medicalRecordId) {
            apiClient.medicalRecords.getFileBlob(r.medicalRecordId)
              .then((blob) => {
                if (!cancelled && blob) {
                  origUrl = URL.createObjectURL(blob);
                  setOriginalBlobUrl(origUrl);
                }
              })
              .catch(() => {});
          }
        });"""

if target_rep_img in rep_content:
    rep_content = rep_content.replace(target_rep_img, repl_rep_img)
    with open(reports_detail_path, "w", encoding="utf-8") as f:
        f.write(rep_content)
    print("app.ai-reports.$id.tsx updated successfully")
else:
    print("target_rep_img not found in app.ai-reports.$id.tsx")

# 7. Update backend ai_service.py patient resolution
service_path = r"backend/app/services/ai_service.py"
with open(service_path, "r", encoding="utf-8") as f:
    service_content = f.read()

target_svc_list = 'patient = await db[COLLECTION_PATIENTS].find_one({"user_id": current_user.user_id})'
repl_svc_list = 'patient = await db[COLLECTION_PATIENTS].find_one({"$or": [{"user_id": current_user.user_id}, {"email": current_user.email}, {"patient_id": current_user.user_id}]})'

count_repl = service_content.count(target_svc_list)
if count_repl > 0:
    service_content = service_content.replace(target_svc_list, repl_svc_list)
    with open(service_path, "w", encoding="utf-8") as f:
        f.write(service_content)
    print(f"ai_service.py updated {count_repl} occurrences")
else:
    print("target_svc_list not found in ai_service.py")

