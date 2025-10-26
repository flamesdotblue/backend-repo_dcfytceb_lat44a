"""
Database Schemas

Define your MongoDB collection schemas here using Pydantic models.
Each Pydantic model represents a collection in your database.
Collection name will be the lowercase of the class name.
"""

from pydantic import BaseModel, Field
from typing import Optional, Literal

class Driver(BaseModel):
    """
    Drivers collection schema
    Collection name: "driver"
    """
    name: str = Field(..., description="Driver full name")
    phone: Optional[str] = Field(None, description="Phone number")
    license_no: Optional[str] = Field(None, description="License number")
    is_active: bool = Field(True, description="Whether the driver is active")

class Attendance(BaseModel):
    """
    Attendance collection schema
    Collection name: "attendance"
    """
    driver_id: str = Field(..., description="Related driver id as string")
    date: str = Field(..., description="Attendance date in YYYY-MM-DD format")
    status: Literal['present', 'absent', 'late'] = Field('present', description="Attendance status")
    notes: Optional[str] = Field(None, description="Optional notes")
