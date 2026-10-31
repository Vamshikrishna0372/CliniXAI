from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, Header, Query, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.dependencies.database import get_database
from app.dependencies.auth import get_current_user
from app.models.user import UserInDB
from app.models.billing import BillingStatus
from app.schemas.billing import (
    CreateBillRequest, AddLineItemRequest, RecordPaymentRequest,
    VoidPaymentRequest, CancelBillRequest, BillResponse, BillSummaryResponse
)
from app.schemas.common import APIResponse, PaginatedResponse, PaginationMeta
from app.services.billing_service import BillingService

router = APIRouter(prefix="/billing", tags=["Billing & Payments"])


@router.post(
    "",
    response_model=APIResponse[BillResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create Draft Bill (Admin/Staff)",
)
async def create_bill(
    request: CreateBillRequest,
    current_user: UserInDB = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Creates a new patient billing record in DRAFT status."""
    bill = await BillingService.create_bill(db, request, current_user)
    return APIResponse(message="Bill created successfully", data=bill.model_dump())


@router.post(
    "/from-consultation/{consultation_id}",
    response_model=APIResponse[BillResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Auto-Create Bill from Completed Consultation",
)
async def create_bill_from_consultation(
    consultation_id: str,
    current_user: UserInDB = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Automatically generates a bill using Doctor's consultation fee from completed consultation."""
    bill = await BillingService.create_bill_from_consultation(db, consultation_id, current_user)
    return APIResponse(message="Consultation bill created successfully", data=bill.model_dump())


@router.get(
    "",
    response_model=PaginatedResponse[BillSummaryResponse],
    summary="List Bills (Role-Aware)",
)
async def list_bills(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    patient_id: Optional[str] = Query(default=None),
    status: Optional[BillingStatus] = Query(default=None),
    current_user: UserInDB = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Role-aware listing of patient bills."""
    docs, total = await BillingService.list_bills(
        db, current_user, page=page, page_size=page_size, patient_id=patient_id, status=status
    )
    meta = PaginationMeta.create(page=page, page_size=page_size, total=total)

    results = [
        BillSummaryResponse(
            bill_id=d["bill_id"],
            patient_id=d["patient_id"],
            appointment_id=d.get("appointment_id"),
            consultation_id=d.get("consultation_id"),
            grand_total=d["grand_total"],
            total_amount=d.get("total_amount", d["grand_total"]),
            amount_paid=d["amount_paid"],
            paid_amount=d.get("paid_amount", d["amount_paid"]),
            balance_due=d["balance_due"],
            balance_amount=d.get("balance_amount", d["balance_due"]),
            status=d["status"],
            created_at=d["created_at"],
        )
        for d in docs
    ]
    return PaginatedResponse(data=results, pagination=meta)


@router.get(
    "/{bill_id}",
    response_model=APIResponse[BillResponse],
    summary="Get Bill Detail",
)
async def get_bill_detail(
    bill_id: str,
    current_user: UserInDB = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Fetch complete billing detail including line items and payment transactions."""
    bill = await BillingService.get_bill_by_id(db, bill_id, current_user)
    return APIResponse(data=bill)


@router.get(
    "/{bill_id}/receipt",
    response_model=APIResponse[dict],
    summary="Get Receipt Data",
)
async def get_receipt_data(
    bill_id: str,
    payment_id: Optional[str] = Query(default=None, description="Optional payment transaction ID"),
    current_user: UserInDB = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Returns structured receipt payload for printing / frontend display."""
    receipt = await BillingService.get_receipt_data(db, bill_id, payment_id, current_user)
    return APIResponse(data=receipt)


@router.post(
    "/{bill_id}/issue",
    response_model=APIResponse[BillResponse],
    summary="Issue Bill (Draft -> Issued)",
)
async def issue_bill(
    bill_id: str,
    current_user: UserInDB = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Issues a draft bill and notifies the patient."""
    issued = await BillingService.issue_bill(db, bill_id, current_user)
    return APIResponse(message="Bill issued successfully", data=issued)


@router.post(
    "/{bill_id}/line-items",
    response_model=APIResponse[BillResponse],
    summary="Add Line Item to Bill",
)
async def add_line_item(
    bill_id: str,
    request: AddLineItemRequest,
    current_user: UserInDB = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Appends a new line item to an active bill and updates totals."""
    updated = await BillingService.add_line_item(db, bill_id, request, current_user)
    return APIResponse(message="Line item added successfully", data=updated)


@router.post(
    "/{bill_id}/payments",
    response_model=APIResponse[BillResponse],
    summary="Record Payment",
)
async def record_payment(
    bill_id: str,
    request: RecordPaymentRequest,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    x_idempotency_key: Optional[str] = Header(None, alias="X-Idempotency-Key"),
    current_user: UserInDB = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Records an offline Cash/UPI/Card payment transaction against a bill."""
    if not request.idempotency_key:
        request.idempotency_key = idempotency_key or x_idempotency_key
    updated = await BillingService.record_payment(db, bill_id, request, current_user)
    return APIResponse(message="Payment recorded successfully", data=updated)


@router.post(
    "/{bill_id}/payments/{payment_id}/void",
    response_model=APIResponse[BillResponse],
    summary="Void Payment",
)
async def void_payment(
    bill_id: str,
    payment_id: str,
    request: VoidPaymentRequest,
    current_user: UserInDB = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Voids a previously recorded payment transaction."""
    updated = await BillingService.void_payment(db, bill_id, payment_id, request, current_user)
    return APIResponse(message="Payment voided successfully", data=updated)


@router.post(
    "/{bill_id}/cancel",
    response_model=APIResponse[BillResponse],
    summary="Cancel Bill",
)
async def cancel_bill(
    bill_id: str,
    request: Optional[CancelBillRequest] = None,
    current_user: UserInDB = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Cancels an unpaid bill."""
    reason = request.reason if request else None
    cancelled = await BillingService.cancel_bill(db, bill_id, current_user, reason=reason)
    return APIResponse(message="Bill cancelled successfully", data=cancelled)
