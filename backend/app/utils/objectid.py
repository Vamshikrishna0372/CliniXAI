"""Utilities for MongoDB ObjectId validation, serialization, and conversion in Pydantic v2."""

from typing import Any
from bson import ObjectId
from pydantic import GetCoreSchemaHandler
from pydantic_core import core_schema


class PyObjectId(str):
    """Custom string type for MongoDB ObjectId validation and serialization in Pydantic v2 models."""

    @classmethod
    def __get_pydantic_core_schema__(
        cls, _source_type: Any, _handler: GetCoreSchemaHandler
    ) -> core_schema.CoreSchema:
        return core_schema.json_or_python_schema(
            json_schema=core_schema.str_schema(),
            python_schema=core_schema.no_info_plain_validator_function(cls.validate),
            serialization=core_schema.plain_serializer_function_ser_schema(
                lambda x: str(x)
            ),
        )

    @classmethod
    def validate(cls, value: Any) -> str:
        """Validates input value to ensure it can be safely represented as a MongoDB ObjectId string."""
        if isinstance(value, ObjectId):
            return str(value)
        if isinstance(value, str):
            if ObjectId.is_valid(value):
                return value
            raise ValueError(f"Invalid ObjectId string format: '{value}'")
        raise ValueError(f"Invalid ObjectId type: {type(value)}")


def is_valid_object_id(value: str) -> bool:
    """Checks if a string is a valid 24-character hexadecimal ObjectId."""
    return isinstance(value, str) and ObjectId.is_valid(value)


def to_object_id(value: str) -> ObjectId:
    """Safely converts a valid hex string to a BSON ObjectId instance.
    
    Raises ValueError if the string format is invalid.
    """
    if not is_valid_object_id(value):
        raise ValueError(f"Invalid ObjectId string format: '{value}'")
    return ObjectId(value)
