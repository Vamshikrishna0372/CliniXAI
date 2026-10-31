"""Common reusable Pydantic schemas for standardized API responses, pagination, and error payloads."""

from typing import Generic, TypeVar, Optional, Any, List
from pydantic import BaseModel, Field, ConfigDict

T = TypeVar("T")


class MessageResponse(BaseModel):
    """Simple status/message response model."""
    success: bool = True
    message: str


class ErrorPayload(BaseModel):
    """Structure of an error detail payload."""
    code: str
    message: str
    details: Optional[Any] = None


class ErrorResponse(BaseModel):
    """Standardized API Error response schema."""
    success: bool = False
    error: ErrorPayload


class APIResponse(BaseModel, Generic[T]):
    """Standardized generic API envelope response model."""
    success: bool = True
    message: Optional[str] = None
    data: Optional[T] = None

    model_config = ConfigDict(arbitrary_types_allowed=True)


class PaginationParams(BaseModel):
    """Common request pagination query parameters."""
    page: int = Field(default=1, ge=1, description="Page index (1-based)")
    page_size: int = Field(default=20, ge=1, le=100, description="Number of items per page")


class PaginationMeta(BaseModel):
    """Pagination metadata model returned in list responses."""
    page: int
    page_size: int
    total: int
    total_pages: int
    has_next: bool
    has_prev: bool

    @classmethod
    def create(cls, page: int, page_size: int, total: int) -> "PaginationMeta":
        total_pages = (total + page_size - 1) // page_size if page_size > 0 else 0
        return cls(
            page=page,
            page_size=page_size,
            total=total,
            total_pages=total_pages,
            has_next=page < total_pages,
            has_prev=page > 1,
        )


class PaginatedResponse(BaseModel, Generic[T]):
    """Standardized envelope for paginated collection responses."""
    success: bool = True
    data: List[T]
    pagination: PaginationMeta
