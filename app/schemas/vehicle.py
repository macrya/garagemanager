"""
Pydantic schemas for Vehicle.
"""
from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional


class VehicleBase(BaseModel):
    """Base vehicle schema with common fields."""
    customer_id: int
    make: str
    model: str
    year: int
    license_plate: str
    vin: Optional[str] = None
    color: Optional[str] = None


class VehicleCreate(VehicleBase):
    """Schema for creating a vehicle."""
    pass


class VehicleUpdate(BaseModel):
    """Schema for updating a vehicle."""
    customer_id: Optional[int] = None
    make: Optional[str] = None
    model: Optional[str] = None
    year: Optional[int] = None
    license_plate: Optional[str] = None
    vin: Optional[str] = None
    color: Optional[str] = None


class Vehicle(VehicleBase):
    """Schema for vehicle responses."""
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
