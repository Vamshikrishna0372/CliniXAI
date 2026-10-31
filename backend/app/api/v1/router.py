"""API v1 Central Router assembling feature route modules."""

from fastapi import APIRouter
from app.api.v1.routes import (
    health, auth, patients, departments, doctors, staff, appointments,
    consultations, prescriptions, medical_records, billing, notifications, reports,
    ai_analyses, integrations, qr, follow_ups, documents, audit_logs, search, admin
)

api_v1_router = APIRouter()

# Mount feature sub-routers
api_v1_router.include_router(health.router)
api_v1_router.include_router(auth.router)
api_v1_router.include_router(patients.router)
api_v1_router.include_router(departments.router)
api_v1_router.include_router(doctors.router)
api_v1_router.include_router(staff.router)
api_v1_router.include_router(appointments.router)
api_v1_router.include_router(consultations.router)
api_v1_router.include_router(prescriptions.router)
api_v1_router.include_router(medical_records.router)
api_v1_router.include_router(billing.router)
api_v1_router.include_router(notifications.router)
api_v1_router.include_router(reports.router)
api_v1_router.include_router(ai_analyses.router)
api_v1_router.include_router(integrations.router)
api_v1_router.include_router(qr.router)
api_v1_router.include_router(follow_ups.router)
api_v1_router.include_router(documents.router)
api_v1_router.include_router(audit_logs.router)
api_v1_router.include_router(search.router)
api_v1_router.include_router(admin.router)

# WebSocket route alias for Phase 17
api_v1_router.add_api_websocket_route("/ws/notifications", notifications.websocket_notifications)


