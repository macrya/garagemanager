"""
Service routes.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
from datetime import datetime

from app.database import get_db
from app.models.service import Service, ServiceStatus
from app.models.user import User
from app.schemas.service import Service as ServiceSchema, ServiceCreate, ServiceUpdate
from app.auth import get_current_active_user

router = APIRouter(prefix="/services", tags=["services"])


@router.get("/", response_model=List[ServiceSchema])
async def get_services(
    skip: int = 0,
    limit: int = 100,
    status_filter: ServiceStatus = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Get all services with pagination and optional status filter.
    """
    query = select(Service)

    if status_filter:
        query = query.where(Service.status == status_filter)

    result = await db.execute(query.offset(skip).limit(limit))
    services = result.scalars().all()
    return services


@router.get("/{service_id}", response_model=ServiceSchema)
async def get_service(
    service_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Get a specific service by ID.
    """
    result = await db.execute(select(Service).where(Service.id == service_id))
    service = result.scalar_one_or_none()

    if not service:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Service not found"
        )

    return service


@router.post("/", response_model=ServiceSchema, status_code=status.HTTP_201_CREATED)
async def create_service(
    service: ServiceCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Create a new service.
    """
    db_service = Service(**service.model_dump())
    db.add(db_service)
    await db.commit()
    await db.refresh(db_service)

    return db_service


@router.put("/{service_id}", response_model=ServiceSchema)
async def update_service(
    service_id: int,
    service_update: ServiceUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Update a service.
    """
    result = await db.execute(select(Service).where(Service.id == service_id))
    db_service = result.scalar_one_or_none()

    if not db_service:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Service not found"
        )

    # Update only provided fields
    update_data = service_update.model_dump(exclude_unset=True)

    # Auto-set completed_date when status changes to completed
    if "status" in update_data and update_data["status"] == ServiceStatus.COMPLETED:
        if db_service.status != ServiceStatus.COMPLETED:
            update_data["completed_date"] = datetime.utcnow()

    for field, value in update_data.items():
        setattr(db_service, field, value)

    await db.commit()
    await db.refresh(db_service)

    return db_service


@router.delete("/{service_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_service(
    service_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Delete a service.
    """
    result = await db.execute(select(Service).where(Service.id == service_id))
    db_service = result.scalar_one_or_none()

    if not db_service:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Service not found"
        )

    await db.delete(db_service)
    await db.commit()

    return None
