"""Payment recording request and response Pydantic schemas."""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field

from app.models.payment import PaymentMethod, PaymentStatus


class RecordPaymentRequest(BaseModel):
    """Schema for recording a payment transaction on a bill."""
    bill_id: str
    amount: float = Field(..., ge=0.01)
    payment_method: PaymentMethod = PaymentMethod.CASH
    reference_number: Optional[str] = Field(None, max_length=100)
    notes: Optional[str] = Field(None, max_length=500)


class PaymentResponse(BaseModel):
    """Public response model for a payment transaction."""
    payment_id: str
    bill_id: str
    patient_id: str
    amount: float
    payment_method: PaymentMethod
    reference_number: Optional[str] = None
    notes: Optional[str] = None
    status: PaymentStatus
    recorded_by: Optional[str] = None
    created_at: datetime


class PaymentListResponse(BaseModel):
    """List response for payments."""
    total: int
    items: List[PaymentResponse]
