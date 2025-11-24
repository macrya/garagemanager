"""
Main FastAPI application entry point.
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.database import init_db
from app.routers import auth, customers, vehicles, services

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan events for the application.
    Handles startup and shutdown events.
    """
    # Startup
    print("🚀 Starting Garage Management System...")
    print(f"📊 Initializing database...")
    await init_db()
    print("✅ Database initialized successfully")
    print(f"🌐 API available at: {settings.api_v1_prefix}")
    print(f"📖 Interactive docs: http://localhost:8000/docs")
    print(f"🔧 ReDoc: http://localhost:8000/redoc")

    yield

    # Shutdown
    print("👋 Shutting down Garage Management System...")


# Create FastAPI application
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="""
    ## 🔧 Garage Management System API

    A modern, production-ready API for managing garage operations built with FastAPI.

    ### Features:
    * **Fast & Efficient**: Built with async/await for high performance
    * **Type-Safe**: Pydantic validation for all requests and responses
    * **Auto Documentation**: Interactive API docs with Swagger UI
    * **Secure**: JWT-based authentication
    * **Scalable**: PostgreSQL database with SQLAlchemy ORM

    ### Entities:
    * **Customers**: Manage customer information
    * **Vehicles**: Track customer vehicles
    * **Services**: Record service history and jobs
    * **Users**: Authentication and user management
    """,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router, prefix=settings.api_v1_prefix)
app.include_router(customers.router, prefix=settings.api_v1_prefix)
app.include_router(vehicles.router, prefix=settings.api_v1_prefix)
app.include_router(services.router, prefix=settings.api_v1_prefix)


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "Welcome to Garage Management System API",
        "version": settings.app_version,
        "docs": "/docs",
        "redoc": "/redoc",
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "version": settings.app_version,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
    )
