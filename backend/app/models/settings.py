"""Hospital and System Settings Domain Model."""

from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, EmailStr, Field

from app.utils.datetime import utc_now


class HospitalSettingsInDB(BaseModel):
    """Hospital system configuration persisted in MongoDB."""

    setting_id: str = "default"
    hospital_name: str = "CliniXAI Multispecialty Hospital"
    tagline: Optional[str] = "AI-Powered Clinical Excellence & Hospital Care"
    contact_email: str = "contact@clinixai.com"
    contact_phone: str = "+91 80 2345 6789"
    emergency_number: str = "+91 80 2345 0000"
    address: str = "124 Innovation Park, Health City, Bengaluru, Karnataka 560100"
    opening_time: str = "08:00"
    closing_time: str = "20:00"
    appointment_slot_duration_minutes: int = 30
    timezone: str = "Asia/Kolkata"
    currency: str = "INR"
    total_bed_capacity: int = 250
    emergency_contact: Optional[str] = "+91 80 2345 0000"
    ai_auto_suggest: bool = True
    ai_confidence_threshold: int = 70
    updated_at: datetime = Field(default_factory=utc_now)
    updated_by: Optional[str] = None

    def to_mongo_dict(self) -> Dict[str, Any]:
        return self.model_dump()
