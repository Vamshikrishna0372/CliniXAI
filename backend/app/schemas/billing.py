"""Billing & Payment Pydantic request and response schemas for CliniXAI Phase 16."""

import math
from datetime import datetime
from typing import Optional, List, Any
from pydantic import BaseModel, Field, field_validator, model_validator, ConfigDict

from app.models.billing import (
    BillingStatus, PaymentMethod, PaymentStatus
)


# ── Request Schemas ────────────────────────────────────────────────────────────

class BillLineItemRequest(BaseModel):
    """Schema for a single line item in a bill creation or modification request."""
    model_config = ConfigDict(extra="ignore")

    item_code: str = Field(default="ITEM-001", max_length=50)
    description: str = Field(..., min_length=1, max_length=300)
    quantity: float = Field(default=1.0, gt=0.0)
    unit_price: float = Field(..., ge=0.0)
    tax_percent: float = Field(default=0.0, ge=0.0, le=100.0)
    discount_amount: float = Field(default=0.0, ge=0.0)

    @field_validator("quantity")
    @classmethod
    def validate_quantity(cls, v: float) -> float:
        if math.isnan(v) or math.isinf(v) or v <= 0:
            raise ValueError("Quantity must be a positive finite number greater than zero.")
        return round(v, 4)

    @field_validator("unit_price")
    @classmethod
    def validate_unit_price(cls, v: float) -> float:
        if math.isnan(v) or math.isinf(v) or v < 0:
            raise ValueError("Unit price must be a non-negative finite number.")
        return round(v, 2)

    @field_validator("tax_percent", "discount_amount")
    @classmethod
    def validate_finite(cls, v: float) -> float:
        if math.isnan(v) or math.isinf(v) or v < 0:
            raise ValueError("Amount must be a non-negative finite number.")
        return round(v, 2)


class CreateBillRequest(BaseModel):
    """Schema for creating a new patient bill."""
    model_config = ConfigDict(extra="ignore")

    patient_id: Optional[str] = Field(None, max_length=64)
    appointment_id: Optional[str] = Field(None, max_length=64)
    consultation_id: Optional[str] = Field(None, max_length=64)
    prescription_id: Optional[str] = Field(None, max_length=64)
    line_items: List[BillLineItemRequest] = Field(..., min_length=1)
    discount: Optional[float] = Field(default=0.0, ge=0.0)
    notes: Optional[str] = Field(None, max_length=1000)
    idempotency_key: Optional[str] = Field(None, max_length=128)

    @field_validator("discount")
    @classmethod
    def validate_discount(cls, v: Optional[float]) -> float:
        if v is None:
            return 0.0
        if math.isnan(v) or math.isinf(v) or v < 0:
            raise ValueError("Discount must be a non-negative finite number.")
        return round(v, 2)


class AddLineItemRequest(BaseModel):
    """Schema for adding a line item to an existing bill."""
    model_config = ConfigDict(extra="ignore")

    item_code: str = Field(default="ITEM-001", max_length=50)
    description: str = Field(..., min_length=1, max_length=300)
    quantity: float = Field(default=1.0, gt=0.0)
    unit_price: float = Field(..., ge=0.0)
    tax_percent: float = Field(default=0.0, ge=0.0, le=100.0)
    discount_amount: float = Field(default=0.0, ge=0.0)

    @field_validator("quantity")
    @classmethod
    def validate_quantity(cls, v: float) -> float:
        if math.isnan(v) or math.isinf(v) or v <= 0:
            raise ValueError("Quantity must be a positive finite number greater than zero.")
        return round(v, 4)

    @field_validator("unit_price")
    @classmethod
    def validate_unit_price(cls, v: float) -> float:
        if math.isnan(v) or math.isinf(v) or v < 0:
            raise ValueError("Unit price must be a non-negative finite number.")
        return round(v, 2)

    @field_validator("tax_percent", "discount_amount")
    @classmethod
    def validate_finite(cls, v: float) -> float:
        if math.isnan(v) or math.isinf(v) or v < 0:
            raise ValueError("Amount must be a non-negative finite number.")
        return round(v, 2)


class RecordPaymentRequest(BaseModel):
    """Schema for recording an offline payment against a bill."""
    model_config = ConfigDict(extra="ignore")

    amount: float = Field(..., gt=0.0, description="Payment amount in INR")
    method: PaymentMethod
    reference_number: Optional[str] = Field(None, max_length=100)
    reference: Optional[str] = Field(None, max_length=100)
    notes: Optional[str] = Field(None, max_length=300)
    idempotency_key: Optional[str] = Field(None, max_length=128)

    @field_validator("amount")
    @classmethod
    def validate_amount(cls, v: float) -> float:
        if math.isnan(v) or math.isinf(v) or v <= 0:
            raise ValueError("Payment amount must be a positive finite number.")
        return round(v, 2)

    @field_validator("method", mode="before")
    @classmethod
    def normalize_method(cls, v: Any) -> Any:
        if isinstance(v, str):
            v_lower = v.strip().lower()
            # Reject unsupported online gateways or crypto
            if v_lower in {"razorpay", "stripe", "paypal", "bitcoin", "crypto"}:
                raise ValueError(f"Online gateway or cryptocurrency payment method '{v}' is not supported in offline billing.")
            return v_lower
        return v


class VoidPaymentRequest(BaseModel):
    """Schema for voiding a recorded payment."""
    model_config = ConfigDict(extra="ignore")

    reason: str = Field(..., min_length=3, max_length=500)


class CancelBillRequest(BaseModel):
    """Schema for cancelling an unpaid bill."""
    model_config = ConfigDict(extra="ignore")

    reason: Optional[str] = Field(None, max_length=500)


# ── Response Schemas ───────────────────────────────────────────────────────────

class LineItemResponse(BaseModel):
    """Bill line item response with computed totals."""
    item_code: str
    description: str
    quantity: float
    unit_price: float
    tax_percent: float
    discount_amount: float
    subtotal: float = 0.0
    tax_amount: float = 0.0
    total: float = 0.0

    @model_validator(mode="before")
    @classmethod
    def compute_fields_if_missing(cls, data: Any) -> Any:
        if isinstance(data, dict):
            qty = data.get("quantity", 1.0)
            price = data.get("unit_price", 0.0)
            tax_pct = data.get("tax_percent", 0.0)
            disc = data.get("discount_amount", 0.0)

            subtotal = round(qty * price, 2)
            tax = round(subtotal * (tax_pct / 100.0), 2)
            tot = round(subtotal + tax - disc, 2)

            if "subtotal" not in data or data["subtotal"] is None:
                data["subtotal"] = subtotal
            if "tax_amount" not in data or data["tax_amount"] is None:
                data["tax_amount"] = tax
            if "total" not in data or data["total"] is None:
                data["total"] = tot
        return data


class PaymentRecordResponse(BaseModel):
    """Payment transaction record response."""
    payment_id: str
    bill_id: Optional[str] = None
    patient_id: Optional[str] = None
    amount: float
    method: PaymentMethod
    status: PaymentStatus
    reference_number: Optional[str] = None
    reference: Optional[str] = None
    notes: Optional[str] = None
    paid_at: datetime
    recorded_at: Optional[datetime] = None
    recorded_by: str
    voided_at: Optional[datetime] = None
    voided_by: Optional[str] = None
    void_reason: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def sync_reference_and_timestamps(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if not data.get("reference") and data.get("reference_number"):
                data["reference"] = data["reference_number"]
            if not data.get("reference_number") and data.get("reference"):
                data["reference_number"] = data["reference"]
            if not data.get("recorded_at") and data.get("paid_at"):
                data["recorded_at"] = data["paid_at"]
        return data


class BillResponse(BaseModel):
    """Full billing record response."""
    bill_id: str
    patient_id: str
    appointment_id: Optional[str] = None
    consultation_id: Optional[str] = None
    prescription_id: Optional[str] = None
    department_id: Optional[str] = None
    doctor_id: Optional[str] = None
    line_items: List[LineItemResponse]
    subtotal: float
    total_tax: float
    total_discount: float
    discount: float = 0.0
    grand_total: float
    total_amount: float = 0.0
    amount_paid: float
    paid_amount: float = 0.0
    balance_due: float
    balance_amount: float = 0.0
    currency: str = "INR"
    payments: List[PaymentRecordResponse]
    status: BillingStatus
    notes: Optional[str] = None
    created_by: str
    issued_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    cancelled_by: Optional[str] = None
    cancellation_reason: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="before")
    @classmethod
    def sync_aliases(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "total_amount" not in data or data["total_amount"] == 0.0:
                data["total_amount"] = data.get("grand_total", 0.0)
            if "paid_amount" not in data or data["paid_amount"] == 0.0:
                data["paid_amount"] = data.get("amount_paid", 0.0)
            if "balance_amount" not in data or data["balance_amount"] == 0.0:
                data["balance_amount"] = data.get("balance_due", 0.0)
            if "discount" not in data or data["discount"] == 0.0:
                data["discount"] = data.get("total_discount", 0.0)
            if "total_discount" not in data:
                data["total_discount"] = data.get("discount", 0.0)
            if "subtotal" not in data:
                data["subtotal"] = data.get("grand_total", 0.0)
            if "total_tax" not in data:
                data["total_tax"] = 0.0
            if "line_items" not in data or data["line_items"] is None:
                data["line_items"] = []
            if "created_by" not in data or not data["created_by"]:
                data["created_by"] = "system"
        return data


class BillSummaryResponse(BaseModel):
    """Compact bill card for list views."""
    bill_id: str
    patient_id: str
    appointment_id: Optional[str] = None
    consultation_id: Optional[str] = None
    grand_total: float
    total_amount: float = 0.0
    amount_paid: float
    paid_amount: float = 0.0
    balance_due: float
    balance_amount: float = 0.0
    status: BillingStatus
    created_at: datetime

    @model_validator(mode="before")
    @classmethod
    def sync_summary_aliases(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "total_amount" not in data or data["total_amount"] == 0.0:
                data["total_amount"] = data.get("grand_total", 0.0)
            if "paid_amount" not in data or data["paid_amount"] == 0.0:
                data["paid_amount"] = data.get("amount_paid", 0.0)
            if "balance_amount" not in data or data["balance_amount"] == 0.0:
                data["balance_amount"] = data.get("balance_due", 0.0)
        return data
