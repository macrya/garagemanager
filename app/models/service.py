"""
Service model for database.
"""
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base
import enum


class ServiceStatus(str, enum.Enum):
    """Service status enumeration."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class Service(Base):
    """Service database model."""

    __tablename__ = "services"

    id = Column(Integer, primary_key=True, index=True)
    vehicle_id = Column(Integer, ForeignKey("vehicles.id", ondelete="CASCADE"), nullable=False)
    service_type = Column(String, nullable=False)
    description = Column(String, nullable=True)
    cost = Column(Float, nullable=False)
    status = Column(SQLEnum(ServiceStatus), default=ServiceStatus.PENDING, nullable=False)
    technician = Column(String, nullable=True)
    notes = Column(String, nullable=True)
    service_date = Column(DateTime(timezone=True), server_default=func.now())
    completed_date = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    vehicle = relationship("Vehicle", back_populates="services")
