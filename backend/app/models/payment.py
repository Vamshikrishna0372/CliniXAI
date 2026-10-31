"""Payment transaction domain model for CliniXAI."""

from enum import Enum
from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field

from app.utils.datetime import utc_now


class PaymentMethod(str, Enum):
    """Supported payment methods."""
    CASH = "cash"
    CREDIT_CARD = "credit_card"
    DEBIT_CARD = "debit_card"
    INSURANCE = "insurance"
    BANK_TRANSFER = "bank_transfer"
    ONLINE = "online"


class PaymentStatus(str, Enum):
    """Payment transaction status."""
    COMPLETED = "completed"
    PENDING = "pending"
    FAILED = "failed"
    REFUNDED = "refunded"


class PaymentInDB(BaseModel):
    """Internal payment record stored in MongoDB `payments` collection."""

    payment_id: str
    bill_id: str
    patient_id: str
    amount: float
    payment_method: PaymentMethod = PaymentMethod.CASH
    reference_number: Optional[str] = None
    notes: Optional[str] = None
    status: PaymentStatus = PaymentStatus.COMPLETED
    recorded_by: Optional[str] = None

    # Soft Delete Metadata
    is_deleted: bool = False
    deleted_at: Optional[datetime] = None
    deleted_by: Optional[str] = None

    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    def to_mongo_dict(self) -> Dict[str, Any]:
        """Converts payment model to dictionary for MongoDB."""
        return self.model_dump()
