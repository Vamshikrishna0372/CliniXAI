"""Administrative Operations, Financial Analytics, and CSV Reporting Service for CliniXAI Phase 6.

All metrics are dynamically aggregated from existing MongoDB collections (users, patients, doctors,
staff, departments, appointments, consultations, billing, notifications).
NO new analytics/reports collections are created.
"""

import io
import csv
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.logging import logger
from app.core.exceptions import ForbiddenError, AppValidationError
from app.database.collections import (
    COLLECTION_USERS, COLLECTION_PATIENTS, COLLECTION_DOCTORS, COLLECTION_STAFF,
    COLLECTION_DEPARTMENTS, COLLECTION_APPOINTMENTS, COLLECTION_CONSULTATIONS,
    COLLECTION_BILLING, COLLECTION_NOTIFICATIONS
)
from app.models.user import UserInDB, UserRole
from app.utils.datetime import utc_now


class AnalyticsService:
    """Core hospital administrative and financial analytics service."""

    @staticmethod
    def _assert_admin(current_user: UserInDB) -> None:
        if current_user.role not in (UserRole.HOSPITAL_ADMIN, UserRole.ADMIN):
            raise ForbiddenError("Access forbidden. Hospital Admin privileges required.")

    # ── Operational Summary ──────────────────────────────────────────────────

    @staticmethod
    async def get_operational_summary(
        db: AsyncIOMotorDatabase, current_user: UserInDB
    ) -> Dict[str, Any]:
        """Calculates hospital-wide administrative operational metrics."""
        AnalyticsService._assert_admin(current_user)

        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        # Concurrent aggregation counts
        total_patients = await db[COLLECTION_PATIENTS].count_documents({})
        total_doctors = await db[COLLECTION_DOCTORS].count_documents({"is_active": True})
        if total_doctors == 0:
            total_doctors = await db[COLLECTION_DOCTORS].count_documents({})

        total_staff = await db[COLLECTION_STAFF].count_documents({"is_active": True})
        if total_staff == 0:
            total_staff = await db[COLLECTION_STAFF].count_documents({})

        total_departments = await db[COLLECTION_DEPARTMENTS].count_documents({"is_active": True})

        # Today's appointments & queue status
        today_appointments = await db[COLLECTION_APPOINTMENTS].count_documents({
            "appointment_date": today_str
        })
        checked_in_patients = await db[COLLECTION_APPOINTMENTS].count_documents({
            "appointment_date": today_str,
            "status": "checked_in"
        })
        in_queue_patients = await db[COLLECTION_APPOINTMENTS].count_documents({
            "appointment_date": today_str,
            "queue_token": {"$ne": None},
            "status": {"$in": ["checked_in", "scheduled"]}
        })
        completed_consultations_today = await db[COLLECTION_CONSULTATIONS].count_documents({
            "status": "completed"
        })

        # Today's billing revenue
        billing_cursor = db[COLLECTION_BILLING].find({"status": {"$in": ["paid", "partially_paid"]}})
        bills = await billing_cursor.to_list(length=1000)
        revenue_today = sum(b.get("amount_paid", 0.0) for b in bills)

        outstanding_bills_count = await db[COLLECTION_BILLING].count_documents({
            "status": {"$in": ["issued", "partially_paid", "unpaid", "draft"]}
        })

        return {
            "total_patients": total_patients,
            "active_doctors": total_doctors,
            "active_staff": total_staff,
            "active_departments": total_departments,
            "today_appointments": today_appointments,
            "checked_in_patients": checked_in_patients,
            "in_queue_patients": in_queue_patients,
            "completed_consultations_today": completed_consultations_today,
            "outstanding_bills_count": outstanding_bills_count,
            "revenue_collected_today": round(revenue_today, 2),
            "currency": "INR",
            "generated_at": utc_now(),
        }

    # ── Financial Summary ────────────────────────────────────────────────────

    @staticmethod
    async def get_financial_summary(
        db: AsyncIOMotorDatabase,
        current_user: UserInDB,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Calculates hospital financial metrics (billed, collected, balance, by method)."""
        AnalyticsService._assert_admin(current_user)

        query: Dict[str, Any] = {}
        if start_date or end_date:
            query["created_at"] = {}
            if start_date:
                query["created_at"]["$gte"] = start_date
            if end_date:
                query["created_at"]["$lte"] = end_date

        bills = await db[COLLECTION_BILLING].find(query).to_list(length=5000)

        total_billed = sum(b.get("grand_total", 0.0) for b in bills)
        total_collected = sum(b.get("amount_paid", 0.0) for b in bills)
        total_outstanding = sum(b.get("balance_due", 0.0) for b in bills)

        status_counts = {
            "draft": 0,
            "issued": 0,
            "partially_paid": 0,
            "paid": 0,
            "cancelled": 0,
        }
        for b in bills:
            st = b.get("status", "draft")
            status_counts[st] = status_counts.get(st, 0) + 1

        # Payment method totals
        cash_total = 0.0
        upi_total = 0.0
        card_total = 0.0

        for b in bills:
            for p in b.get("payments", []):
                if p.get("status") == "completed":
                    method = str(p.get("method", "")).lower()
                    amt = float(p.get("amount", 0.0))
                    if method == "cash":
                        cash_total += amt
                    elif method == "upi":
                        upi_total += amt
                    elif method == "card":
                        card_total += amt

        return {
            "total_billed": round(total_billed, 2),
            "total_collected": round(total_collected, 2),
            "outstanding_balance": round(total_outstanding, 2),
            "status_breakdown": status_counts,
            "payment_methods": {
                "cash": round(cash_total, 2),
                "upi": round(upi_total, 2),
                "card": round(card_total, 2),
            },
            "currency": "INR",
            "generated_at": utc_now(),
        }

    # ── Revenue by Department ────────────────────────────────────────────────

    @staticmethod
    async def get_revenue_by_department(
        db: AsyncIOMotorDatabase, current_user: UserInDB
    ) -> List[Dict[str, Any]]:
        """Aggregates revenue and billed totals grouped by department."""
        AnalyticsService._assert_admin(current_user)

        departments = await db[COLLECTION_DEPARTMENTS].find({}).to_list(length=100)
        dept_map = {d["department_id"]: d.get("name", d["department_id"]) for d in departments}

        pipeline = [
            {
                "$group": {
                    "_id": "$department_id",
                    "total_billed": {"$sum": "$grand_total"},
                    "total_collected": {"$sum": "$amount_paid"},
                    "bill_count": {"$sum": 1},
                }
            }
        ]
        results = await db[COLLECTION_BILLING].aggregate(pipeline).to_list(length=100)

        revenue_list = []
        for r in results:
            dept_id = r["_id"] or "unassigned"
            dept_name = dept_map.get(dept_id, dept_id)
            revenue_list.append({
                "department_id": dept_id,
                "department_name": dept_name,
                "total_billed": round(r["total_billed"], 2),
                "total_collected": round(r["total_collected"], 2),
                "bill_count": r["bill_count"],
            })

        return revenue_list

    # ── Payment Method Mix ────────────────────────────────────────────────────

    @staticmethod
    async def get_payment_method_mix(
        db: AsyncIOMotorDatabase, current_user: UserInDB
    ) -> Dict[str, Any]:
        """Aggregates payment transactions by Cash, UPI, and Card."""
        AnalyticsService._assert_admin(current_user)

        bills = await db[COLLECTION_BILLING].find({"payments": {"$ne": []}}).to_list(length=5000)

        method_mix = {
            "cash": {"count": 0, "amount": 0.0},
            "upi": {"count": 0, "amount": 0.0},
            "card": {"count": 0, "amount": 0.0},
            "other": {"count": 0, "amount": 0.0},
        }

        for b in bills:
            for p in b.get("payments", []):
                if p.get("status") == "completed":
                    m = str(p.get("method", "other")).lower()
                    amt = float(p.get("amount", 0.0))
                    if m not in method_mix:
                        m = "other"
                    method_mix[m]["count"] += 1
                    method_mix[m]["amount"] += amt

        for k in method_mix:
            method_mix[k]["amount"] = round(method_mix[k]["amount"], 2)

        return {"payment_methods": method_mix, "currency": "INR", "generated_at": utc_now()}

    # ── Appointment Analytics ────────────────────────────────────────────────

    @staticmethod
    async def get_appointment_analytics(
        db: AsyncIOMotorDatabase, current_user: UserInDB
    ) -> Dict[str, Any]:
        """Aggregates appointment statistics by status and department."""
        AnalyticsService._assert_admin(current_user)

        total_appointments = await db[COLLECTION_APPOINTMENTS].count_documents({})

        pipeline_status = [
            {"$group": {"_id": "$status", "count": {"$sum": 1}}}
        ]
        status_results = await db[COLLECTION_APPOINTMENTS].aggregate(pipeline_status).to_list(length=50)
        by_status = {r["_id"]: r["count"] for r in status_results if r["_id"]}

        pipeline_dept = [
            {"$group": {"_id": "$department_id", "count": {"$sum": 1}}}
        ]
        dept_results = await db[COLLECTION_APPOINTMENTS].aggregate(pipeline_dept).to_list(length=50)
        by_department = {r["_id"] or "unassigned": r["count"] for r in dept_results}

        return {
            "total_appointments": total_appointments,
            "by_status": by_status,
            "by_department": by_department,
            "generated_at": utc_now(),
        }

    # ── CSV Export ────────────────────────────────────────────────────────────

    @staticmethod
    async def export_billing_csv(
        db: AsyncIOMotorDatabase, current_user: UserInDB
    ) -> str:
        """Generates a sanitized CSV report of hospital billing data for Admin export."""
        AnalyticsService._assert_admin(current_user)

        bills = await db[COLLECTION_BILLING].find({}).sort("created_at", -1).to_list(length=5000)

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "Bill ID", "Patient ID", "Doctor ID", "Grand Total (INR)",
            "Amount Paid (INR)", "Balance Due (INR)", "Status", "Created At"
        ])

        for b in bills:
            writer.writerow([
                b.get("bill_id"),
                b.get("patient_id"),
                b.get("doctor_id", ""),
                f"{b.get('grand_total', 0.0):.2f}",
                f"{b.get('amount_paid', 0.0):.2f}",
                f"{b.get('balance_due', 0.0):.2f}",
                b.get("status"),
                str(b.get("created_at")),
            ])

        return output.getvalue()
