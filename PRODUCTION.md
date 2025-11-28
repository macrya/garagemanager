# Production Deployment Guide

## Overview

This Garage Management System is a production-ready web application with enterprise-grade security features including PBKDF2 password hashing, rate limiting, secure session management, and comprehensive security headers.

## Features

### Security
- ✅ PBKDF2 password hashing (100,000 iterations)
- ✅ Rate limiting (5 attempts per 5 minutes)
- ✅ Secure session management with auto-cleanup
- ✅ Security headers (CSP, HSTS, X-Frame-Options, etc.)
- ✅ CORS configuration
- ✅ Input validation and sanitization
- ✅ SQL injection protection (parameterized queries)

### User Management
- ✅ Admin/Staff authentication
- ✅ Customer registration and login
- ✅ Password strength validation
- ✅ Account status management (active, suspended, pending)

### Monitoring
- ✅ Health check endpoint (`/health` or `/api/health`)
- ✅ Automatic session cleanup
- ✅ Database connection monitoring

## Quick Start

### Development

```bash
# Clone the repository
cd garagemanager

# Run the server (no dependencies required!)
python3 garage_server.py
```

The server will start on http://localhost:5000

**Default Credentials:**
- Admin: `admin` / `admin123`
- Customer: `john.smith@email.com` / `customer123`

### Production Deployment

#### 1. Environment Configuration

```bash
# Copy the example environment file
cp .env.example .env

# Edit .env with your production settings
nano .env
```

Set these critical values:
```bash
PORT=5000
PRODUCTION=true
SECRET_KEY=<generate-secure-random-key>
ALLOWED_ORIGINS=https://yourdomain.com
```

Generate a secure secret key:
```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

#### 2. Database Setup

The application uses SQLite by default. For production:

**Option A: SQLite (recommended for small-medium deployments)**
- Works out of the box
- Suitable for up to 100,000 requests/day
- Ensure regular backups

```bash
# Backup script example
cp garage_management.db backups/garage_$(date +%Y%m%d).db
```

**Option B: PostgreSQL (for high-traffic deployments)**
- Requires code modification to use PostgreSQL adapter
- Recommended for > 100,000 requests/day

#### 3. Reverse Proxy with HTTPS

**Using Nginx:**

```nginx
server {
    listen 80;
    server_name yourdomain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name yourdomain.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    # Security headers (additional layer)
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Frame-Options "DENY" always;
    add_header X-Content-Type-Options "nosniff" always;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

#### 4. Systemd Service (Linux)

Create `/etc/systemd/system/garage-manager.service`:

```ini
[Unit]
Description=Garage Management System
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/var/www/garagemanager
Environment="PRODUCTION=true"
Environment="SECRET_KEY=your-secret-key-here"
ExecStart=/usr/bin/python3 /var/www/garagemanager/garage_server.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable garage-manager
sudo systemctl start garage-manager
sudo systemctl status garage-manager
```

#### 5. Docker Deployment (Optional)

Create `Dockerfile`:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY garage_server.py .
COPY .env .

EXPOSE 5000

ENV PRODUCTION=true

CMD ["python3", "garage_server.py"]
```

Build and run:
```bash
docker build -t garage-manager .
docker run -d -p 5000:5000 --env-file .env garage-manager
```

## API Endpoints

### Authentication
- `POST /api/login` - Admin/staff login
- `POST /api/customer-login` - Customer login
- `POST /api/customer-register` - Customer registration

### Admin Dashboard
- `GET /api/dashboard` - Dashboard statistics
- `GET /api/customers` - List customers
- `GET /api/vehicles` - List vehicles
- `GET /api/services` - List services
- `GET /api/technicians` - List technicians
- `GET /api/parts` - Parts inventory
- `GET /api/service-catalog` - Available services
- `GET /api/bookings` - Service bookings

### Customer Portal
- `GET /api/customer/my-vehicles` - Customer's vehicles
- `GET /api/customer/my-bookings` - Customer's bookings
- `POST /api/bookings` - Create booking
- `GET /api/service-catalog` - Browse services
- `POST /api/cost-calculator` - Calculate service costs

### Monitoring
- `GET /health` or `GET /api/health` - Health check endpoint

## Security Best Practices

### 1. Password Policy
- Minimum 8 characters
- Must include uppercase, lowercase, and number
- PBKDF2 hashing with 100,000 iterations

### 2. Rate Limiting
- 5 failed login attempts per 5 minutes
- Automatic IP-based blocking
- Separate limits for admin and customer logins

### 3. Session Management
- 24-hour session expiration
- Secure token generation (32-byte random)
- Automatic cleanup of expired sessions

### 4. Security Headers
- Content Security Policy (CSP)
- HTTP Strict Transport Security (HSTS)
- X-Frame-Options: DENY
- X-Content-Type-Options: nosniff
- X-XSS-Protection

### 5. HTTPS
- **Required** in production
- Use Let's Encrypt for free SSL certificates
- Enforce HTTPS redirects

## Monitoring and Maintenance

### Health Checks

```bash
# Check application health
curl https://yourdomain.com/health

# Expected response:
{
  "status": "healthy",
  "timestamp": "2025-11-27T...",
  "database": "connected",
  "sessions_cleaned": 0,
  "version": "2.0.0",
  "environment": "production"
}
```

### Logs

Monitor application logs:
```bash
# Systemd
sudo journalctl -u garage-manager -f

# Docker
docker logs -f garage-manager
```

### Database Backups

```bash
# Daily backup (add to cron)
0 2 * * * cp /var/www/garagemanager/garage_management.db /backups/garage_$(date +\%Y\%m\%d).db
```

### Session Cleanup

Sessions are automatically cleaned on health check requests. Schedule regular health checks:

```bash
# Add to cron (every hour)
0 * * * * curl -s https://yourdomain.com/health > /dev/null
```

## Scaling Considerations

### Small Scale (< 1000 users)
- Single server with SQLite
- Nginx reverse proxy
- Works perfectly out of the box

### Medium Scale (1000 - 10,000 users)
- Consider PostgreSQL
- Add Redis for rate limiting
- Load balancer for multiple instances

### Large Scale (> 10,000 users)
- PostgreSQL with connection pooling
- Redis for sessions and rate limiting
- Multiple application instances
- CDN for static assets

## Troubleshooting

### Port Already in Use
```bash
# Find process using port 5000
sudo lsof -i :5000

# Kill the process
kill -9 <PID>
```

### Database Locked
```bash
# Check for zombie processes
ps aux | grep garage_server.py

# Restart the service
sudo systemctl restart garage-manager
```

### High Memory Usage
- Consider using PostgreSQL instead of SQLite
- Implement connection pooling
- Add periodic restarts

## Support and Maintenance

### Updating the Application

```bash
# Stop the service
sudo systemctl stop garage-manager

# Backup database
cp garage_management.db garage_management.db.backup

# Update code
git pull origin main

# Restart service
sudo systemctl start garage-manager
```

### Changing Admin Password

```python
import hashlib
import sqlite3

def hash_password(password):
    import secrets
    salt = secrets.token_bytes(32)
    pwd_hash = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)
    return salt.hex() + ':' + pwd_hash.hex()

# Connect to database
conn = sqlite3.connect('garage_management.db')
cursor = conn.cursor()

# Update admin password
new_password = "YourNewSecurePassword123"
cursor.execute(
    'UPDATE users SET password_hash = ? WHERE username = ?',
    (hash_password(new_password), 'admin')
)
conn.commit()
conn.close()
```

## License

This is a production-ready application. Ensure you comply with all relevant licenses and regulations when deploying.

## Version

Current Version: 2.0.0
Release Date: 2025-11-27
