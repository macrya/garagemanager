"""
Pydantic schemas for request/response validation.
"""
from app.schemas.customer import CustomerBase, CustomerCreate, CustomerUpdate, Customer
from app.schemas.vehicle import VehicleBase, VehicleCreate, VehicleUpdate, Vehicle
from app.schemas.service import ServiceBase, ServiceCreate, ServiceUpdate, Service
from app.schemas.user import UserBase, UserCreate, UserUpdate, User, Token

__all__ = [
    "CustomerBase", "CustomerCreate", "CustomerUpdate", "Customer",
    "VehicleBase", "VehicleCreate", "VehicleUpdate", "Vehicle",
    "ServiceBase", "ServiceCreate", "ServiceUpdate", "Service",
    "UserBase", "UserCreate", "UserUpdate", "User", "Token",
]
