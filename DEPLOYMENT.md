# Garage Management System - Quick Deployment Guide

## Overview
A complete web-based garage management system built with Python. No external dependencies required - uses only Python standard library!

## Features
- Customer Management (Add, Edit, Delete)
- Vehicle Tracking
- Service Records with status tracking (Pending, In Progress, Completed)
- Dashboard with statistics
- User Authentication
- Responsive web interface
- SQLite database (automatically created)

## Quick Start (30 seconds!)

### Option 1: Using the startup script
```bash
chmod +x start.sh
./start.sh
```

### Option 2: Direct Python execution
```bash
python3 garage_server.py
```

### Option 3: Make it executable
```bash
chmod +x garage_server.py
./garage_server.py
```

## Access the System

1. Open your web browser
2. Navigate to: `http://localhost:5000`
3. Login with default credentials:
   - **Username:** admin
   - **Password:** admin123

## System Requirements

- Python 3.6 or higher (no additional packages needed!)
- Any modern web browser
- Approximately 5MB of disk space

## Default Data

The system comes pre-loaded with sample data:
- 3 customers
- 4 vehicles
- 4 service records

You can delete these and add your own data through the web interface.

## Features Walkthrough

### Dashboard
- View total customers, vehicles, pending services
- See total revenue from completed services
- Quick overview of your garage operations

### Customers Tab
- Add new customers with contact information
- Edit existing customer details
- Delete customers (removes all associated vehicles and services)

### Vehicles Tab
- Register vehicles with make, model, year
- Track license plates and VIN numbers
- Associate vehicles with customers

### Services Tab
- Create service records for vehicles
- Track service status (Pending → In Progress → Completed)
- Assign technicians to services
- Record costs and generate revenue reports

## Deployment Options

### Local Development
```bash
python3 garage_server.py
```

### Production (Linux/Unix)
```bash
# Run in background
nohup python3 garage_server.py > garage.log 2>&1 &

# Or use screen
screen -S garage
python3 garage_server.py
# Press Ctrl+A then D to detach
```

### Docker Deployment (Optional)
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY garage_server.py .
EXPOSE 5000
CMD ["python3", "garage_server.py"]
```

```bash
docker build -t garage-system .
docker run -p 5000:5000 -v $(pwd)/data:/app garage-system
```

### Cloud Deployment

#### AWS EC2 / DigitalOcean / Linode
```bash
# SSH into your server
ssh user@your-server-ip

# Upload the file
scp garage_server.py user@your-server-ip:~/

# Run it
python3 garage_server.py
```

#### Heroku
```bash
# Create Procfile
echo "web: python3 garage_server.py" > Procfile

# Deploy
heroku create your-garage-app
git push heroku main
```

#### Render.com
This repository is configured for Render deployment. See [RENDER_SETUP.md](RENDER_SETUP.md) for detailed instructions.

**Quick Deploy:**
1. Connect your GitHub repository to Render
2. Create a new Web Service
3. Select "Deploy from render.yaml"
4. Render will automatically use the configuration

**Important:** Make sure your service's start command is set to:
```bash
python3 garage_server.py
```

NOT:
```bash
gunicorn your_application.wsgi  # ❌ WRONG - will cause errors
```

See RENDER_SETUP.md for troubleshooting if you encounter "ModuleNotFoundError: No module named 'your_application'".

## Security Notes

**IMPORTANT:** Before deploying to production:

1. **Change the default admin password:**
   - The default password is `admin123`
   - You should change this in the database after first login

2. **Use HTTPS:**
   - In production, use a reverse proxy (nginx/Apache) with SSL
   - Never transmit passwords over unencrypted HTTP in production

3. **Firewall:**
   - Only expose port 5000 to trusted networks
   - Use SSH tunneling for remote access if needed

## Database

The system uses SQLite with the following tables:
- `customers` - Customer information
- `vehicles` - Vehicle details
- `services` - Service records
- `users` - System users
- `sessions` - Authentication sessions

Database file: `garage_management.db` (created automatically)

## Backup

To backup your data:
```bash
# Backup database
cp garage_management.db garage_management_backup_$(date +%Y%m%d).db

# Restore from backup
cp garage_management_backup_20231113.db garage_management.db
```

## Troubleshooting

### Port already in use
```bash
# Find process using port 5000
lsof -i :5000
# Kill it
kill -9 <PID>
```

### Cannot connect
- Check firewall settings
- Ensure port 5000 is open
- Try accessing via `http://127.0.0.1:5000` instead

### Database locked
- Only one server instance can run at a time
- Check for other running instances: `ps aux | grep garage_server`

## Customization

### Change Port
Edit line 12 in `garage_server.py`:
```python
PORT = 8080  # Change to your preferred port
```

### Change Database Location
Edit line 13 in `garage_server.py`:
```python
DB_FILE = '/path/to/your/database.db'
```

## API Endpoints

The system provides a RESTful API:

- `POST /api/login` - User authentication
- `GET /api/stats` - Dashboard statistics
- `GET /api/customers` - List all customers
- `POST /api/customers` - Add new customer
- `DELETE /api/customers/{id}` - Delete customer
- `GET /api/vehicles` - List all vehicles
- `POST /api/vehicles` - Add new vehicle
- `DELETE /api/vehicles/{id}` - Delete vehicle
- `GET /api/services` - List all services
- `POST /api/services` - Add new service
- `DELETE /api/services/{id}` - Delete service

## Support

For issues or questions:
1. Check the logs for error messages
2. Verify Python version: `python3 --version`
3. Ensure no other service is using port 5000

## License

This is a simple garage management system for educational and small business use.

---

**Deployment Time: ~30 seconds**
**Setup Complexity: Minimal**
**Dependencies: None (Pure Python)**

Enjoy managing your garage! 🔧
