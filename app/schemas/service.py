"""
Pydantic schemas for Service.
"""
from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional
from app.models.service import ServiceStatus


class ServiceBase(BaseModel):
    """Base service schema with common fields."""
    vehicle_id: int
    service_type: str
    description: Optional[str] = None
    cost: float
    status: ServiceStatus = ServiceStatus.PENDING
    technician: Optional[str] = None
    notes: Optional[str] = None


class ServiceCreate(ServiceBase):
    """Schema for creating a service."""
    pass


class ServiceUpdate(BaseModel):
    """Schema for updating a service."""
    vehicle_id: Optional[int] = None
    service_type: Optional[str] = None
    description: Optional[str] = None
    cost: Optional[float] = None
    status: Optional[ServiceStatus] = None
    technician: Optional[str] = None
    notes: Optional[str] = None
    completed_date: Optional[datetime] = None


class Service(ServiceBase):
    """Schema for service responses."""
    id: int
    service_date: datetime
    completed_date: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
