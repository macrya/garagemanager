# 🚀 Garage Management System - FastAPI Edition

A **production-ready**, high-performance Garage Management System built with **FastAPI**, PostgreSQL, and Docker. This modern implementation leverages async/await for superior performance and scalability.

## ✨ Features

### **Performance & Architecture**
- ⚡ **FastAPI Framework**: Async/await for high concurrency
- 🔄 **ASGI Server**: Uvicorn with Gunicorn for production
- 📊 **PostgreSQL Database**: Production-grade relational database
- 🎯 **Type-Safe**: Pydantic validation for all data
- 🔐 **Secure**: JWT authentication with password hashing

### **API Features**
- 📚 **Auto-generated Documentation**: Interactive Swagger UI & ReDoc
- 🔍 **Data Validation**: Automatic request/response validation
- 🏗️ **Clean Architecture**: Separation of concerns (models, schemas, routes)
- 🔄 **Async Operations**: Non-blocking database operations
- 🌐 **CORS Support**: Configurable cross-origin requests

### **DevOps Ready**
- 🐳 **Docker**: Containerized for consistent deployment
- 🎼 **Docker Compose**: Multi-container orchestration
- 🔧 **Development Mode**: Hot reload for rapid development
- 📈 **Health Checks**: Built-in monitoring endpoints
- 🚀 **Production Ready**: Optimized multi-stage Docker builds

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────┐
│                     Client/Browser                       │
└─────────────────────┬───────────────────────────────────┘
                      │ HTTP/HTTPS
                      │
┌─────────────────────▼───────────────────────────────────┐
│              Nginx/Load Balancer (Optional)             │
└─────────────────────┬───────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────┐
│         FastAPI Application (Uvicorn Workers)           │
│  ┌──────────────────────────────────────────────────┐   │
│  │              API Routes (Async)                  │   │
│  │  - Authentication  - Customers                   │   │
│  │  - Vehicles        - Services                    │   │
│  └─────────────────┬────────────────────────────────┘   │
│                    │                                     │
│  ┌─────────────────▼────────────────────────────────┐   │
│  │         Pydantic Validation Layer               │   │
│  └─────────────────┬────────────────────────────────┘   │
│                    │                                     │
│  ┌─────────────────▼────────────────────────────────┐   │
│  │      SQLAlchemy ORM (Async Engine)              │   │
│  └─────────────────┬────────────────────────────────┘   │
└────────────────────┼─────────────────────────────────────┘
                     │
┌────────────────────▼─────────────────────────────────────┐
│            PostgreSQL Database                           │
│  - Customers    - Vehicles    - Services    - Users      │
└──────────────────────────────────────────────────────────┘
```

## 📦 Tech Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Framework** | FastAPI 0.104+ | High-performance async web framework |
| **Server** | Uvicorn + Gunicorn | ASGI server with worker management |
| **Database** | PostgreSQL 15 | Production-grade RDBMS |
| **ORM** | SQLAlchemy 2.0 | Async database operations |
| **Validation** | Pydantic 2.5+ | Type-safe data validation |
| **Authentication** | JWT (python-jose) | Secure token-based auth |
| **Password Hashing** | Passlib (bcrypt) | Secure password storage |
| **Containerization** | Docker & Docker Compose | Deployment & orchestration |

## 🚀 Quick Start

### Prerequisites
- Docker & Docker Compose
- Git

### 1. Clone & Setup

```bash
git clone <repository-url>
cd garagemanager

# Create environment file
cp .env.example .env

# Generate a secure secret key (Linux/Mac)
openssl rand -hex 32
# Update SECRET_KEY in .env with generated key
```

### 2. Run with Docker Compose

#### Production Mode
```bash
# Build and start all services
docker compose up -d

# View logs
docker compose logs -f api

# Stop services
docker compose down
```

#### Development Mode (with hot reload)
```bash
# Start development environment
docker compose -f docker-compose.dev.yml up

# The API will reload automatically when you modify code
```

### 3. Access the Application

- **API Endpoint**: http://localhost:8000
- **Interactive Docs (Swagger)**: http://localhost:8000/docs
- **Alternative Docs (ReDoc)**: http://localhost:8000/redoc
- **Health Check**: http://localhost:8000/health

### 4. Create Your First User

Using the interactive docs (http://localhost:8000/docs):

1. Navigate to **POST /api/v1/auth/register**
2. Click "Try it out"
3. Enter user details:
```json
{
  "username": "admin",
  "email": "admin@garage.com",
  "password": "SecurePassword123!",
  "full_name": "Admin User",
  "role": "admin"
}
```
4. Click "Execute"

### 5. Login & Get Access Token

1. Navigate to **POST /api/v1/auth/login**
2. Enter credentials:
```json
{
  "username": "admin",
  "password": "SecurePassword123!"
}
```
3. Copy the `access_token` from the response
4. Click "Authorize" button (top right)
5. Enter: `Bearer <your-access-token>`
6. Now you can access all protected endpoints!

## 📚 API Documentation

### Authentication Endpoints

```bash
POST /api/v1/auth/register  # Register new user
POST /api/v1/auth/login     # Login and get JWT token
```

### Customer Endpoints

```bash
GET    /api/v1/customers           # List all customers
GET    /api/v1/customers/{id}      # Get specific customer
POST   /api/v1/customers           # Create new customer
PUT    /api/v1/customers/{id}      # Update customer
DELETE /api/v1/customers/{id}      # Delete customer
```

### Vehicle Endpoints

```bash
GET    /api/v1/vehicles            # List all vehicles
GET    /api/v1/vehicles/{id}       # Get specific vehicle
POST   /api/v1/vehicles            # Create new vehicle
PUT    /api/v1/vehicles/{id}       # Update vehicle
DELETE /api/v1/vehicles/{id}       # Delete vehicle
```

### Service Endpoints

```bash
GET    /api/v1/services            # List all services (with status filter)
GET    /api/v1/services/{id}       # Get specific service
POST   /api/v1/services            # Create new service
PUT    /api/v1/services/{id}       # Update service
DELETE /api/v1/services/{id}       # Delete service
```

## 🛠️ Development

### Local Development (without Docker)

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set up PostgreSQL locally and update DATABASE_URL in .env

# Run the application
uvicorn app.main:app --reload
```

### Project Structure

```
garagemanager/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI app entry point
│   ├── config.py            # Configuration management
│   ├── database.py          # Database setup
│   ├── auth.py              # Authentication utilities
│   ├── models/              # SQLAlchemy models
│   │   ├── __init__.py
│   │   ├── customer.py
│   │   ├── vehicle.py
│   │   ├── service.py
│   │   └── user.py
│   ├── schemas/             # Pydantic schemas
│   │   ├── __init__.py
│   │   ├── customer.py
│   │   ├── vehicle.py
│   │   ├── service.py
│   │   └── user.py
│   └── routers/             # API routes
│       ├── __init__.py
│       ├── auth.py
│       ├── customers.py
│       ├── vehicles.py
│       └── services.py
├── requirements.txt         # Python dependencies
├── Dockerfile              # Production Docker image
├── docker-compose.yml      # Production compose file
├── docker-compose.dev.yml  # Development compose file
├── .env.example            # Environment template
└── README_FASTAPI.md       # This file
```

## 🔒 Security Best Practices

1. **Change Default Secrets**
   ```bash
   # Generate secure secret key
   openssl rand -hex 32
   # Update .env file
   ```

2. **Use Environment Variables**
   - Never commit `.env` files
   - Use `.env.example` as template
   - Set different secrets for production

3. **HTTPS in Production**
   - Use reverse proxy (Nginx) with SSL
   - Consider Let's Encrypt for certificates

4. **Database Security**
   - Use strong passwords
   - Restrict network access
   - Regular backups

## 📈 Performance Optimization

### Async Operations
All database operations are async, allowing the server to handle multiple requests concurrently without blocking.

### Connection Pooling
SQLAlchemy is configured with connection pooling:
- Pool size: 10
- Max overflow: 20

### Production Server
Gunicorn with 4 Uvicorn workers provides optimal performance:
```bash
gunicorn app.main:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000
```

## 🐳 Docker Commands

```bash
# Build images
docker compose build

# Start services in background
docker compose up -d

# View logs
docker compose logs -f
docker compose logs -f api    # Just API logs

# Restart service
docker compose restart api

# Stop services
docker compose stop

# Remove containers and volumes
docker compose down -v

# Access PostgreSQL
docker compose exec db psql -U garage_user -d garage_db

# Access API container
docker compose exec api sh
```

## 🧪 Testing

```bash
# Install test dependencies
pip install pytest pytest-asyncio httpx

# Run tests
pytest

# Run with coverage
pytest --cov=app tests/
```

## 🚀 Production Deployment

### Option 1: Cloud Platforms (Recommended)

#### **Render.com**
1. Connect GitHub repository
2. Create PostgreSQL database
3. Create Web Service (Docker)
4. Set environment variables
5. Deploy!

#### **Google Cloud Run**
```bash
gcloud run deploy garage-api \
  --source . \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated
```

#### **AWS ECS/Fargate**
- Build and push Docker image to ECR
- Create ECS task definition
- Deploy service with load balancer

### Option 2: VPS (DigitalOcean, Linode, etc.)

```bash
# On server
git clone <repository>
cd garagemanager

# Set up environment
cp .env.example .env
# Edit .env with production values

# Run with Docker Compose
docker compose up -d

# Set up Nginx reverse proxy (recommended)
# Install SSL certificate (Let's Encrypt)
```

## 📊 Monitoring

### Health Checks
```bash
# Application health
curl http://localhost:8000/health

# Database health (inside container)
docker compose exec db pg_isready -U garage_user
```

### Logs
```bash
# Application logs
docker compose logs -f api

# Database logs
docker compose logs -f db
```

## 🔧 Troubleshooting

### Database Connection Issues
```bash
# Check if database is running
docker compose ps

# Check database logs
docker compose logs db

# Verify connection string in .env
```

### Port Already in Use
```bash
# Change port in docker-compose.yml
ports:
  - "8001:8000"  # Use port 8001 instead
```

### Permission Issues (Linux)
```bash
# Fix volume permissions
sudo chown -R $USER:$USER .
```

## 🎯 Next Steps

- [ ] Add unit and integration tests
- [ ] Implement database migrations (Alembic)
- [ ] Add Redis for caching
- [ ] Implement rate limiting
- [ ] Add email notifications
- [ ] Create admin dashboard
- [ ] Add API versioning
- [ ] Implement WebSocket support for real-time updates

## 📝 License

Free to use for educational and commercial purposes.

## 🤝 Contributing

Contributions welcome! Please feel free to submit a Pull Request.

---

**Built with ❤️ using FastAPI, PostgreSQL, and Docker**

**Performance:** 🚀 Lightning Fast | **Scalability:** 📈 Cloud Ready | **Security:** 🔒 Production Grade
