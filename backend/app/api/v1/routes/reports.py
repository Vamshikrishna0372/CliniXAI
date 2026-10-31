"""Administrative Operations, Financial Summary, and Reporting API Routes for CliniXAI Phase 6."""

from typing import Optional
from fastapi import APIRouter, Depends, Query, Response, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.dependencies.database import get_database
from app.dependencies.auth import get_current_user
from app.models.user import UserInDB
from app.schemas.common import APIResponse
from app.services.analytics_service import AnalyticsService

router = APIRouter(prefix="/admin", tags=["Admin Operations & Analytics"])


@router.get(
    "/summary",
    response_model=APIResponse[dict],
    summary="Get Hospital Operational Summary (Admin Only)",
)
async def get_operational_summary(
    current_user: UserInDB = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Returns administrative operational summary (patient count, doctor count, today's appointments, queue, completed consultations)."""
    summary = await AnalyticsService.get_operational_summary(db, current_user)
    return APIResponse(data=summary)


@router.get(
    "/financial-summary",
    response_model=APIResponse[dict],
    summary="Get Hospital Financial Summary (Admin Only)",
)
async def get_financial_summary(
    start_date: Optional[str] = Query(None, description="Start date ISO YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="End date ISO YYYY-MM-DD"),
    current_user: UserInDB = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Returns financial aggregates (total billed, total collected, balance, status breakdown, payment method mix)."""
    summary = await AnalyticsService.get_financial_summary(db, current_user, start_date, end_date)
    return APIResponse(data=summary)


@router.get(
    "/revenue-by-department",
    response_model=APIResponse[list],
    summary="Get Revenue Grouped by Department (Admin Only)",
)
async def get_revenue_by_department(
    current_user: UserInDB = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Aggregates billed and collected revenue grouped by department."""
    revenue = await AnalyticsService.get_revenue_by_department(db, current_user)
    return APIResponse(data=revenue)


@router.get(
    "/payment-method-mix",
    response_model=APIResponse[dict],
    summary="Get Payment Method Breakdown (Admin Only)",
)
async def get_payment_method_mix(
    current_user: UserInDB = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Aggregates payment transactions by Cash, UPI, and Card."""
    mix = await AnalyticsService.get_payment_method_mix(db, current_user)
    return APIResponse(data=mix)


@router.get(
    "/appointment-analytics",
    response_model=APIResponse[dict],
    summary="Get Appointment Analytics (Admin Only)",
)
async def get_appointment_analytics(
    current_user: UserInDB = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Aggregates appointment statistics by status and department."""
    analytics = await AnalyticsService.get_appointment_analytics(db, current_user)
    return APIResponse(data=analytics)


@router.get(
    "/reports/csv",
    summary="Export Billing Report as CSV (Admin Only)",
    responses={200: {"content": {"text/csv": {}}, "description": "CSV export file"}},
)
async def export_billing_csv(
    current_user: UserInDB = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Generates and downloads a sanitized CSV report of hospital billing data."""
    csv_content = await AnalyticsService.export_billing_csv(db, current_user)
    headers = {"Content-Disposition": 'attachment; filename="clinixai_billing_report.csv"'}
    return Response(content=csv_content, media_type="text/csv", headers=headers)
