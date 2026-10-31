"""Billing & Payment domain model for CliniXAI Phase 16."""

from enum import Enum
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, computed_field

from app.utils.datetime import utc_now


class BillingStatus(str, Enum):
    """Lifecycle status of a billing record."""
    DRAFT = "draft"
    PENDING = "pending"
    ISSUED = "issued"
    PARTIALLY_PAID = "partially_paid"
    PAID = "paid"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"


class PaymentMethod(str, Enum):
    """Supported offline payment methods."""
    CASH = "cash"
    UPI = "upi"
    CARD = "card"
    # Legacy / non-processed methods for backward compatibility
    INSURANCE = "insurance"
    ONLINE = "online"
    OTHER = "other"


class PaymentStatus(str, Enum):
    """Status of individual payment transaction."""
    PENDING = "pending"
    COMPLETED = "completed"
    RECORDED = "recorded"
    VOIDED = "voided"
    FAILED = "failed"
    REFUNDED = "refunded"


class BillLineItem(BaseModel):
    """A single chargeable line item in a bill."""
    item_code: str = Field(..., max_length=50, description="Unique item code e.g. 'CONSULT-001'")
    description: str = Field(..., min_length=1, max_length=300)
    quantity: float = Field(default=1.0, gt=0.0)
    unit_price: float = Field(..., ge=0.0, description="Price per unit in INR")
    tax_percent: float = Field(default=0.0, ge=0.0, le=100.0)
    discount_amount: float = Field(default=0.0, ge=0.0)

    @computed_field
    @property
    def subtotal(self) -> float:
        """Gross amount before tax and discounts."""
        return round(self.quantity * self.unit_price, 2)

    @computed_field
    @property
    def tax_amount(self) -> float:
        return round(self.subtotal * (self.tax_percent / 100), 2)

    @computed_field
    @property
    def total(self) -> float:
        return round(self.subtotal + self.tax_amount - self.discount_amount, 2)


class PaymentRecord(BaseModel):
    """Individual payment transaction record."""
    payment_id: str
    bill_id: Optional[str] = None
    patient_id: Optional[str] = None
    amount: float = Field(..., gt=0.0)
    method: PaymentMethod
    status: PaymentStatus = PaymentStatus.COMPLETED
    reference_number: Optional[str] = Field(None, max_length=100, description="UPI UTR / card reference")
    reference: Optional[str] = Field(None, max_length=100, description="Alias for reference_number")
    idempotency_key: Optional[str] = Field(None, max_length=128, description="Client idempotency key")
    notes: Optional[str] = Field(None, max_length=300)
    paid_at: datetime = Field(default_factory=utc_now)
    recorded_at: Optional[datetime] = None
    recorded_by: str  # user_id of the staff who recorded payment
    voided_at: Optional[datetime] = None
    voided_by: Optional[str] = None
    void_reason: Optional[str] = None


class BillingInDB(BaseModel):
    """Internal billing document stored in MongoDB `billing` collection."""

    bill_id: str
    patient_id: str
    appointment_id: Optional[str] = None
    consultation_id: Optional[str] = None
    prescription_id: Optional[str] = None
    department_id: Optional[str] = None
    doctor_id: Optional[str] = None

    line_items: List[BillLineItem] = Field(default_factory=list)

    # Computed financial fields (denormalized for query performance)
    subtotal: float = Field(default=0.0, ge=0.0)
    total_tax: float = Field(default=0.0, ge=0.0)
    total_discount: float = Field(default=0.0, ge=0.0)
    discount: float = Field(default=0.0, ge=0.0)
    grand_total: float = Field(default=0.0, ge=0.0)
    total_amount: float = Field(default=0.0, ge=0.0)
    amount_paid: float = Field(default=0.0, ge=0.0)
    paid_amount: float = Field(default=0.0, ge=0.0)
    balance_due: float = Field(default=0.0)
    balance_amount: float = Field(default=0.0)
    currency: str = "INR"

    payments: List[PaymentRecord] = Field(default_factory=list)
    status: BillingStatus = BillingStatus.DRAFT

    notes: Optional[str] = Field(None, max_length=1000)
    created_by: str   # user_id
    issued_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    cancelled_by: Optional[str] = None
    cancellation_reason: Optional[str] = None
    idempotency_key: Optional[str] = None

    # Soft Delete Metadata
    is_deleted: bool = False
    deleted_at: Optional[datetime] = None
    deleted_by: Optional[str] = None

    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    def recalculate_totals(self) -> None:
        """Recomputes all aggregate financial fields from line_items and payments."""
        self.subtotal = round(sum(li.subtotal for li in self.line_items), 2)
        self.total_tax = round(sum(li.tax_amount for li in self.line_items), 2)
        base_item_discounts = sum(li.discount_amount for li in self.line_items)
        self.total_discount = round(base_item_discounts + self.discount, 2)
        self.grand_total = round(self.subtotal + self.total_tax - self.total_discount, 2)
        self.total_amount = self.grand_total
        
        valid_statuses = (PaymentStatus.COMPLETED, PaymentStatus.RECORDED)
        self.amount_paid = round(
            sum(p.amount for p in self.payments if p.status in valid_statuses), 2
        )
        self.paid_amount = self.amount_paid
        self.balance_due = round(self.grand_total - self.amount_paid, 2)
        self.balance_amount = self.balance_due

    def to_mongo_dict(self) -> Dict[str, Any]:
        """Converts billing instance to MongoDB-ready dictionary."""
        return self.model_dump()
