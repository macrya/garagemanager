#!/usr/bin/env python3
"""
Garage Management System - Standalone Web Server
No external dependencies required - uses only Python standard library
"""

import http.server
import socketserver
import json
import sqlite3
import urllib.parse
import hashlib
import secrets
from datetime import datetime, timedelta
import os
import mimetypes

PORT = int(os.environ.get('PORT', 5000))
DB_FILE = 'garage_management.db'
SECRET_KEY = os.environ.get('SECRET_KEY', secrets.token_hex(32))
MAX_LOGIN_ATTEMPTS = 5
LOGIN_ATTEMPT_WINDOW = 300  # 5 minutes

# Rate limiting storage (in production, use Redis or similar)
login_attempts = {}

# Production configuration
PRODUCTION = os.environ.get('PRODUCTION', 'false').lower() == 'true'
ALLOWED_ORIGINS = os.environ.get('ALLOWED_ORIGINS', '*').split(',')

# Password hashing with PBKDF2 (using standard library)
def hash_password(password):
    """Hash password using PBKDF2 with SHA-256"""
    salt = secrets.token_bytes(32)
    pwd_hash = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)
    # Store salt and hash together, hex encoded
    return salt.hex() + ':' + pwd_hash.hex()

def verify_password(password, stored_hash):
    """Verify password against stored PBKDF2 hash"""
    # Handle legacy SHA-256 hashes (for backward compatibility during migration)
    if ':' not in stored_hash:
        # Legacy SHA-256 hash
        return hashlib.sha256(password.encode()).hexdigest() == stored_hash

    try:
        salt_hex, pwd_hash_hex = stored_hash.split(':')
        salt = bytes.fromhex(salt_hex)
        pwd_hash = bytes.fromhex(pwd_hash_hex)
        new_hash = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)
        return new_hash == pwd_hash
    except (ValueError, AttributeError):
        return False

def check_rate_limit(identifier):
    """Check if identifier has exceeded rate limit"""
    now = datetime.now().timestamp()
    if identifier in login_attempts:
        attempts = login_attempts[identifier]
        # Clean old attempts
        attempts = [ts for ts in attempts if now - ts < LOGIN_ATTEMPT_WINDOW]
        login_attempts[identifier] = attempts
        if len(attempts) >= MAX_LOGIN_ATTEMPTS:
            return False
    return True

def record_login_attempt(identifier):
    """Record a failed login attempt"""
    now = datetime.now().timestamp()
    if identifier not in login_attempts:
        login_attempts[identifier] = []
    login_attempts[identifier].append(now)

# Initialize database
def init_database():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    # Create tables
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            phone TEXT NOT NULL,
            address TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS vehicles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER NOT NULL,
            make TEXT NOT NULL,
            model TEXT NOT NULL,
            year INTEGER NOT NULL,
            license_plate TEXT UNIQUE NOT NULL,
            vin TEXT,
            color TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE CASCADE
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS services (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vehicle_id INTEGER NOT NULL,
            service_type TEXT NOT NULL,
            description TEXT,
            cost REAL NOT NULL,
            status TEXT DEFAULT 'pending',
            service_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_date TIMESTAMP,
            technician TEXT,
            notes TEXT,
            FOREIGN KEY (vehicle_id) REFERENCES vehicles(id) ON DELETE CASCADE
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT DEFAULT 'staff',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            token TEXT UNIQUE NOT NULL,
            expires_at TIMESTAMP NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    ''')

    # Customer users table for customer login
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS customer_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            status TEXT DEFAULT 'pending_verification',
            verification_token TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE CASCADE
        )
    ''')

    # Customer sessions table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS customer_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER NOT NULL,
            token TEXT UNIQUE NOT NULL,
            expires_at TIMESTAMP NOT NULL,
            FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE CASCADE
        )
    ''')

    # Technicians table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS technicians (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            specialization TEXT,
            phone TEXT,
            email TEXT,
            status TEXT DEFAULT 'available',
            current_workload INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Parts inventory table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS parts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            part_number TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            description TEXT,
            quantity INTEGER DEFAULT 0,
            unit_price REAL NOT NULL,
            supplier TEXT,
            reorder_level INTEGER DEFAULT 5,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Service catalog table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS service_catalog (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            service_name TEXT UNIQUE NOT NULL,
            description TEXT,
            base_price REAL NOT NULL,
            estimated_duration INTEGER,
            category TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Service-Parts relationship
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS service_parts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            service_id INTEGER NOT NULL,
            part_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL,
            FOREIGN KEY (service_id) REFERENCES services(id) ON DELETE CASCADE,
            FOREIGN KEY (part_id) REFERENCES parts(id) ON DELETE CASCADE
        )
    ''')

    # Bookings table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER NOT NULL,
            vehicle_id INTEGER,
            service_catalog_id INTEGER,
            booking_date DATE NOT NULL,
            booking_time TEXT NOT NULL,
            status TEXT DEFAULT 'scheduled',
            notes TEXT,
            assigned_technician_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE CASCADE,
            FOREIGN KEY (vehicle_id) REFERENCES vehicles(id) ON DELETE SET NULL,
            FOREIGN KEY (service_catalog_id) REFERENCES service_catalog(id) ON DELETE SET NULL,
            FOREIGN KEY (assigned_technician_id) REFERENCES technicians(id) ON DELETE SET NULL
        )
    ''')

    # Migration: Add status and verification_token columns to existing customer_users table
    cursor.execute("PRAGMA table_info(customer_users)")
    columns = [column[1] for column in cursor.fetchall()]
    if 'status' not in columns:
        cursor.execute('ALTER TABLE customer_users ADD COLUMN status TEXT DEFAULT "pending_verification"')
    if 'verification_token' not in columns:
        cursor.execute('ALTER TABLE customer_users ADD COLUMN verification_token TEXT')

    # Add sample data if database is empty
    cursor.execute('SELECT COUNT(*) FROM customers')
    if cursor.fetchone()[0] == 0:
        # Add admin user with PBKDF2 hashed password
        password_hash = hash_password('admin123')
        cursor.execute('INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)',
                      ('admin', password_hash, 'admin'))

        # Add sample customers
        cursor.execute('''INSERT INTO customers (name, email, phone, address) VALUES
            ('John Smith', 'john.smith@email.com', '555-0101', '123 Main St'),
            ('Sarah Johnson', 'sarah.j@email.com', '555-0102', '456 Oak Ave'),
            ('Mike Williams', 'mike.w@email.com', '555-0103', '789 Pine Rd')
        ''')

        # Add sample vehicles
        cursor.execute('''INSERT INTO vehicles (customer_id, make, model, year, license_plate, color) VALUES
            (1, 'Toyota', 'Camry', 2020, 'ABC-123', 'Silver'),
            (1, 'Honda', 'Civic', 2019, 'XYZ-789', 'Blue'),
            (2, 'Ford', 'F-150', 2021, 'DEF-456', 'Black'),
            (3, 'Chevrolet', 'Malibu', 2018, 'GHI-789', 'White')
        ''')

        # Add sample services
        cursor.execute('''INSERT INTO services (vehicle_id, service_type, description, cost, status, technician) VALUES
            (1, 'Oil Change', 'Regular maintenance oil change', 45.00, 'completed', 'Mike'),
            (2, 'Brake Inspection', 'Annual brake system inspection', 80.00, 'in_progress', 'Sarah'),
            (3, 'Tire Rotation', 'Rotate all four tires', 35.00, 'pending', NULL),
            (4, 'Engine Diagnostic', 'Check engine light diagnosis', 120.00, 'pending', NULL)
        ''')

        # Add sample technicians
        cursor.execute('''INSERT INTO technicians (name, specialization, phone, email, status, current_workload) VALUES
            ('Mike Johnson', 'Engine Specialist', '555-1001', 'mike.j@garage.com', 'available', 2),
            ('Sarah Williams', 'Brake Systems', '555-1002', 'sarah.w@garage.com', 'available', 1),
            ('Tom Brown', 'Electrical Systems', '555-1003', 'tom.b@garage.com', 'available', 0),
            ('Lisa Davis', 'General Maintenance', '555-1004', 'lisa.d@garage.com', 'available', 0)
        ''')

        # Add sample parts
        cursor.execute('''INSERT INTO parts (part_number, name, description, quantity, unit_price, supplier, reorder_level) VALUES
            ('OIL-001', 'Engine Oil 5W-30', 'Synthetic motor oil', 50, 25.00, 'AutoParts Inc', 10),
            ('FILTER-001', 'Oil Filter', 'Standard oil filter', 30, 8.50, 'AutoParts Inc', 10),
            ('BRAKE-PAD-001', 'Brake Pads Front', 'Ceramic brake pads', 20, 45.00, 'Brake Masters', 5),
            ('TIRE-001', 'All-Season Tire 195/65R15', 'Standard tire', 16, 85.00, 'Tire World', 8),
            ('BATTERY-001', '12V Car Battery', 'Standard car battery', 10, 120.00, 'Power Source', 3),
            ('SPARK-001', 'Spark Plugs (set of 4)', 'Iridium spark plugs', 25, 32.00, 'AutoParts Inc', 5),
            ('WIPER-001', 'Windshield Wipers (pair)', 'All-weather wipers', 40, 18.00, 'AutoParts Inc', 10)
        ''')

        # Add sample service catalog
        cursor.execute('''INSERT INTO service_catalog (service_name, description, base_price, estimated_duration, category) VALUES
            ('Oil Change', 'Complete oil and filter change', 45.00, 30, 'Maintenance'),
            ('Brake Inspection', 'Full brake system inspection', 80.00, 45, 'Brakes'),
            ('Brake Pad Replacement', 'Replace front or rear brake pads', 150.00, 90, 'Brakes'),
            ('Tire Rotation', 'Rotate all four tires', 35.00, 30, 'Tires'),
            ('Wheel Alignment', 'Four-wheel alignment', 95.00, 60, 'Tires'),
            ('Engine Diagnostic', 'Computer diagnostic scan', 120.00, 60, 'Diagnostics'),
            ('Battery Replacement', 'Replace car battery', 180.00, 30, 'Electrical'),
            ('Air Filter Replacement', 'Replace engine air filter', 40.00, 20, 'Maintenance'),
            ('Transmission Service', 'Transmission fluid change', 200.00, 90, 'Maintenance'),
            ('AC System Check', 'Air conditioning inspection and recharge', 110.00, 60, 'Climate Control')
        ''')

        # Add sample customer user accounts with PBKDF2 hashed passwords
        password_hash = hash_password('customer123')
        cursor.execute('''INSERT INTO customer_users (customer_id, email, password_hash, status) VALUES
            (1, 'john.smith@email.com', ?, 'active'),
            (2, 'sarah.j@email.com', ?, 'active'),
            (3, 'mike.w@email.com', ?, 'active')
        ''', (password_hash, password_hash, password_hash))

        # Add sample bookings
        cursor.execute('''INSERT INTO bookings (customer_id, vehicle_id, service_catalog_id, booking_date, booking_time, status, assigned_technician_id) VALUES
            (1, 1, 1, '2025-11-30', '09:00', 'scheduled', 4),
            (2, 3, 2, '2025-11-28', '14:00', 'scheduled', 2),
            (3, 4, 6, '2025-12-02', '10:30', 'scheduled', 3)
        ''')

    conn.commit()
    conn.close()
    print(f"✅ Database initialized: {DB_FILE}")

# Authentication helpers
def create_session(user_id):
    token = secrets.token_urlsafe(32)
    expires_at = datetime.now() + timedelta(hours=24)
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('INSERT INTO sessions (user_id, token, expires_at) VALUES (?, ?, ?)',
                  (user_id, token, expires_at.isoformat()))
    conn.commit()
    conn.close()
    return token

def verify_session(token):
    if not token:
        return None
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT u.id, u.username, u.role
        FROM sessions s
        JOIN users u ON s.user_id = u.id
        WHERE s.token = ? AND s.expires_at > ?
    ''', (token, datetime.now().isoformat()))
    user = cursor.fetchone()
    conn.close()
    return {'id': user[0], 'username': user[1], 'role': user[2]} if user else None

# Customer authentication helpers
def create_customer_session(customer_id):
    token = secrets.token_urlsafe(32)
    expires_at = datetime.now() + timedelta(hours=24)
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('INSERT INTO customer_sessions (customer_id, token, expires_at) VALUES (?, ?, ?)',
                  (customer_id, token, expires_at.isoformat()))
    conn.commit()
    conn.close()
    return token

def verify_customer_session(token):
    if not token:
        return None
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT c.id, c.name, c.email
        FROM customer_sessions cs
        JOIN customers c ON cs.customer_id = c.id
        WHERE cs.token = ? AND cs.expires_at > ?
    ''', (token, datetime.now().isoformat()))
    customer = cursor.fetchone()
    conn.close()
    return {'id': customer[0], 'name': customer[1], 'email': customer[2]} if customer else None

def cleanup_expired_sessions():
    """Clean up expired sessions from the database"""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        now = datetime.now().isoformat()

        # Delete expired admin sessions
        cursor.execute('DELETE FROM sessions WHERE expires_at < ?', (now,))
        admin_deleted = cursor.rowcount

        # Delete expired customer sessions
        cursor.execute('DELETE FROM customer_sessions WHERE expires_at < ?', (now,))
        customer_deleted = cursor.rowcount

        conn.commit()
        conn.close()

        if admin_deleted > 0 or customer_deleted > 0:
            print(f"🧹 Cleaned up {admin_deleted} admin and {customer_deleted} customer expired sessions")

        return admin_deleted + customer_deleted
    except Exception as e:
        print(f"❌ Error cleaning up sessions: {e}")
        return 0

# Automatic technician assignment
def assign_technician():
    """Automatically assign a technician based on current workload and availability"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, name FROM technicians
        WHERE status = 'available'
        ORDER BY current_workload ASC, RANDOM()
        LIMIT 1
    ''')
    technician = cursor.fetchone()
    if technician:
        # Increment workload
        cursor.execute('UPDATE technicians SET current_workload = current_workload + 1 WHERE id = ?',
                      (technician[0],))
        conn.commit()
    conn.close()
    return technician

# Request handler
class GarageRequestHandler(http.server.SimpleHTTPRequestHandler):

    def do_GET(self):
        if self.path == '/' or self.path == '/index.html':
            self.serve_frontend()
        elif self.path == '/customer':
            self.serve_customer_portal()
        elif self.path.startswith('/api/dashboard'):
            self.handle_dashboard()
        elif self.path.startswith('/api/customers'):
            self.handle_get_customers()
        elif self.path.startswith('/api/vehicles'):
            self.handle_get_vehicles()
        elif self.path.startswith('/api/services'):
            self.handle_get_services()
        elif self.path.startswith('/api/stats'):
            self.handle_stats()
        elif self.path.startswith('/api/technicians'):
            self.handle_get_technicians()
        elif self.path.startswith('/api/parts'):
            self.handle_get_parts()
        elif self.path.startswith('/api/service-catalog'):
            self.handle_get_service_catalog()
        elif self.path.startswith('/api/bookings'):
            self.handle_get_bookings()
        elif self.path.startswith('/api/customer/my-vehicles'):
            self.handle_customer_vehicles()
        elif self.path.startswith('/api/customer/my-bookings'):
            self.handle_customer_bookings()
        elif self.path.startswith('/api/cost-calculator'):
            self.handle_cost_calculator()
        elif self.path == '/health' or self.path == '/api/health':
            self.handle_health_check()
        else:
            self.send_error(404, 'Not Found')

    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length).decode('utf-8') if content_length > 0 else '{}'

        try:
            data = json.loads(body) if body else {}
        except:
            data = {}

        if self.path == '/api/login':
            self.handle_login(data)
        elif self.path == '/api/customer-login':
            self.handle_customer_login(data)
        elif self.path == '/api/customer-register':
            self.handle_customer_register(data)
        elif self.path == '/api/customers':
            self.handle_add_customer(data)
        elif self.path == '/api/vehicles':
            self.handle_add_vehicle(data)
        elif self.path == '/api/services':
            self.handle_add_service(data)
        elif self.path == '/api/technicians':
            self.handle_add_technician(data)
        elif self.path == '/api/parts':
            self.handle_add_part(data)
        elif self.path == '/api/service-catalog':
            self.handle_add_service_catalog(data)
        elif self.path == '/api/bookings':
            self.handle_add_booking(data)
        elif self.path == '/api/cost-calculator':
            self.handle_cost_calculator_post(data)
        else:
            self.send_error(404, 'Not Found')

    def do_PUT(self):
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length).decode('utf-8') if content_length > 0 else '{}'

        try:
            data = json.loads(body) if body else {}
        except:
            data = {}

        if self.path.startswith('/api/customers/'):
            customer_id = self.path.split('/')[-1]
            self.handle_update_customer(customer_id, data)
        elif self.path.startswith('/api/vehicles/'):
            vehicle_id = self.path.split('/')[-1]
            self.handle_update_vehicle(vehicle_id, data)
        elif self.path.startswith('/api/services/'):
            service_id = self.path.split('/')[-1]
            self.handle_update_service(service_id, data)
        elif self.path.startswith('/api/technicians/'):
            technician_id = self.path.split('/')[-1]
            self.handle_update_technician(technician_id, data)
        elif self.path.startswith('/api/parts/'):
            part_id = self.path.split('/')[-1]
            self.handle_update_part(part_id, data)
        elif self.path.startswith('/api/service-catalog/'):
            catalog_id = self.path.split('/')[-1]
            self.handle_update_service_catalog(catalog_id, data)
        elif self.path.startswith('/api/bookings/'):
            booking_id = self.path.split('/')[-1]
            self.handle_update_booking(booking_id, data)
        else:
            self.send_error(404, 'Not Found')

    def do_DELETE(self):
        if self.path.startswith('/api/customers/'):
            customer_id = self.path.split('/')[-1]
            self.handle_delete_customer(customer_id)
        elif self.path.startswith('/api/vehicles/'):
            vehicle_id = self.path.split('/')[-1]
            self.handle_delete_vehicle(vehicle_id)
        elif self.path.startswith('/api/services/'):
            service_id = self.path.split('/')[-1]
            self.handle_delete_service(service_id)
        elif self.path.startswith('/api/technicians/'):
            technician_id = self.path.split('/')[-1]
            self.handle_delete_technician(technician_id)
        elif self.path.startswith('/api/parts/'):
            part_id = self.path.split('/')[-1]
            self.handle_delete_part(part_id)
        elif self.path.startswith('/api/service-catalog/'):
            catalog_id = self.path.split('/')[-1]
            self.handle_delete_service_catalog(catalog_id)
        elif self.path.startswith('/api/bookings/'):
            booking_id = self.path.split('/')[-1]
            self.handle_delete_booking(booking_id)
        else:
            self.send_error(404, 'Not Found')

    def serve_frontend(self):
        html = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Garage Management System</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background:
                /* Tire track pattern */
                repeating-linear-gradient(
                    90deg,
                    rgba(255,255,255,0.03) 0px,
                    rgba(255,255,255,0.03) 2px,
                    transparent 2px,
                    transparent 12px
                ),
                repeating-linear-gradient(
                    0deg,
                    rgba(255,255,255,0.02) 0px,
                    rgba(255,255,255,0.02) 2px,
                    transparent 2px,
                    transparent 12px
                ),
                /* Racing stripes subtle effect */
                linear-gradient(
                    135deg,
                    rgba(230,230,230,0.1) 0%,
                    transparent 50%,
                    rgba(230,230,230,0.1) 100%
                ),
                /* Main automotive gradient - dark asphalt to lighter road */
                linear-gradient(135deg, #1a1a2e 0%, #16213e 25%, #0f3460 50%, #533483 100%);
            min-height: 100vh;
            padding: 20px;
            position: relative;
        }
        /* Automotive accent - racing stripe on left edge */
        body::before {
            content: '';
            position: fixed;
            left: 0;
            top: 0;
            bottom: 0;
            width: 4px;
            background: linear-gradient(180deg, #ff6b35 0%, #f7931e 25%, #ffd700 50%, #f7931e 75%, #ff6b35 100%);
            box-shadow: 0 0 10px rgba(255,107,53,0.5);
            z-index: 1;
        }
        .container { max-width: 1400px; margin: 0 auto; position: relative; z-index: 2; }
        .header {
            background: linear-gradient(135deg, rgba(255,255,255,0.98) 0%, rgba(255,255,255,0.95) 100%);
            backdrop-filter: blur(10px);
            padding: 20px 30px;
            border-radius: 10px;
            box-shadow: 0 8px 16px rgba(0,0,0,0.2), 0 0 1px rgba(255,107,53,0.3);
            margin-bottom: 30px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-left: 4px solid #ff6b35;
        }
        .header h1 {
            color: #16213e;
            font-size: 28px;
            text-shadow: 0 1px 2px rgba(0,0,0,0.1);
        }
        .stats {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        .stat-card {
            background: linear-gradient(135deg, rgba(255,255,255,0.98) 0%, rgba(255,255,255,0.95) 100%);
            backdrop-filter: blur(10px);
            padding: 25px;
            border-radius: 10px;
            box-shadow: 0 8px 16px rgba(0,0,0,0.2);
            border-left: 4px solid #ff6b35;
            transition: transform 0.3s, box-shadow 0.3s;
        }
        .stat-card:hover {
            transform: translateY(-4px);
            box-shadow: 0 12px 20px rgba(0,0,0,0.3);
        }
        .stat-card h3 { color: #666; font-size: 14px; margin-bottom: 10px; text-transform: uppercase; letter-spacing: 0.5px; }
        .stat-card .value { font-size: 36px; font-weight: bold; color: #ff6b35; }
        .content {
            background: linear-gradient(135deg, rgba(255,255,255,0.98) 0%, rgba(255,255,255,0.95) 100%);
            backdrop-filter: blur(10px);
            padding: 30px;
            border-radius: 10px;
            box-shadow: 0 8px 16px rgba(0,0,0,0.2);
        }
        .tabs {
            display: flex;
            gap: 10px;
            margin-bottom: 30px;
            border-bottom: 2px solid #eee;
            overflow-x: auto;
            -webkit-overflow-scrolling: touch;
        }
        .tab {
            padding: 12px 24px;
            background: none;
            border: none;
            cursor: pointer;
            font-size: 16px;
            color: #666;
            border-bottom: 3px solid transparent;
            transition: all 0.3s;
            white-space: nowrap;
        }
        .tab.active {
            color: #ff6b35;
            border-bottom-color: #ff6b35;
        }
        .tab:hover {
            color: #ff6b35;
            background: rgba(255,107,53,0.05);
        }
        .tab-content { display: none; }
        .tab-content.active { display: block; }
        .table-wrapper {
            overflow-x: auto;
            -webkit-overflow-scrolling: touch;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 20px;
            min-width: 600px;
        }
        th, td {
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #eee;
        }
        th {
            background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
            font-weight: 600;
            color: #333;
            white-space: nowrap;
        }
        tr:hover { background: rgba(255,107,53,0.05); }
        .btn {
            padding: 10px 20px;
            border: none;
            border-radius: 5px;
            cursor: pointer;
            font-size: 14px;
            transition: all 0.3s;
            font-weight: 500;
        }
        .btn-primary {
            background: linear-gradient(135deg, #ff6b35 0%, #f7931e 100%);
            color: white;
            box-shadow: 0 4px 8px rgba(255,107,53,0.3);
        }
        .btn-primary:hover {
            background: linear-gradient(135deg, #e55a24 0%, #e6820d 100%);
            box-shadow: 0 6px 12px rgba(255,107,53,0.4);
            transform: translateY(-2px);
        }
        .btn-success {
            background: #27ae60;
            color: white;
        }
        .btn-success:hover {
            background: #229954;
            transform: translateY(-2px);
        }
        .btn-danger {
            background: #e74c3c;
            color: white;
        }
        .btn-danger:hover {
            background: #c0392b;
            transform: translateY(-2px);
        }
        .btn-sm { padding: 6px 12px; font-size: 12px; margin: 0 2px; }
        .status-badge {
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 12px;
            font-weight: 600;
        }
        .status-pending { background: #fff3cd; color: #856404; }
        .status-in_progress { background: #cfe2ff; color: #084298; }
        .status-completed { background: #d1e7dd; color: #0f5132; }
        .modal {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0,0,0,0.7);
            justify-content: center;
            align-items: center;
            z-index: 1000;
        }
        .modal.active { display: flex; }
        .modal-content {
            background: white;
            padding: 30px;
            border-radius: 10px;
            max-width: 500px;
            width: 90%;
            max-height: 90vh;
            overflow-y: auto;
            box-shadow: 0 12px 24px rgba(0,0,0,0.3);
        }
        .modal-content h2 { margin-bottom: 20px; color: #ff6b35; }
        .form-group {
            margin-bottom: 15px;
        }
        .form-group label {
            display: block;
            margin-bottom: 5px;
            font-weight: 600;
            color: #333;
        }
        .form-group input,
        .form-group select,
        .form-group textarea {
            width: 100%;
            padding: 10px;
            border: 1px solid #ddd;
            border-radius: 5px;
            font-size: 14px;
            transition: border-color 0.3s;
        }
        .form-group input:focus,
        .form-group select:focus,
        .form-group textarea:focus {
            outline: none;
            border-color: #ff6b35;
            box-shadow: 0 0 0 3px rgba(255,107,53,0.1);
        }
        .form-group textarea { min-height: 100px; }
        .form-actions {
            display: flex;
            gap: 10px;
            justify-content: flex-end;
            margin-top: 20px;
            flex-wrap: wrap;
        }
        .login-container {
            max-width: 400px;
            margin: 100px auto;
            background: linear-gradient(135deg, rgba(255,255,255,0.98) 0%, rgba(255,255,255,0.95) 100%);
            backdrop-filter: blur(10px);
            padding: 40px;
            border-radius: 10px;
            box-shadow: 0 12px 24px rgba(0,0,0,0.3);
            border-left: 4px solid #ff6b35;
        }
        .login-container h2 {
            color: #16213e;
            margin-bottom: 30px;
            text-align: center;
        }
        .hidden { display: none !important; }

        /* Mobile Responsiveness - Tablets */
        @media (max-width: 1024px) {
            .container { padding: 0 10px; }
            .stats {
                grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                gap: 15px;
            }
            .header h1 { font-size: 24px; }
        }

        /* Mobile Responsiveness - Small Tablets & Large Phones */
        @media (max-width: 768px) {
            body { padding: 15px; }
            body::before { width: 3px; }

            .header {
                flex-direction: column;
                gap: 15px;
                padding: 20px;
                text-align: center;
            }
            .header h1 { font-size: 22px; }

            .stats {
                grid-template-columns: 1fr;
                gap: 15px;
            }

            .stat-card {
                padding: 20px;
            }
            .stat-card .value { font-size: 32px; }

            .content { padding: 20px; }

            .tabs {
                gap: 5px;
                margin-bottom: 20px;
            }
            .tab {
                padding: 10px 16px;
                font-size: 14px;
            }

            table { font-size: 14px; }
            th, td { padding: 10px 8px; }

            .modal-content {
                padding: 20px;
                width: 95%;
            }

            .login-container {
                margin: 50px auto;
                padding: 30px;
                width: 90%;
            }
        }

        /* Mobile Responsiveness - Phones */
        @media (max-width: 480px) {
            body { padding: 10px; }
            body::before { width: 2px; }

            .header {
                padding: 15px;
                border-radius: 8px;
            }
            .header h1 { font-size: 18px; }
            .header button { width: 100%; }

            .stats {
                margin-bottom: 20px;
            }

            .stat-card {
                padding: 15px;
            }
            .stat-card h3 { font-size: 12px; }
            .stat-card .value { font-size: 28px; }

            .content {
                padding: 15px;
                border-radius: 8px;
            }

            .tabs {
                gap: 3px;
                margin-bottom: 15px;
            }
            .tab {
                padding: 8px 12px;
                font-size: 13px;
            }

            table {
                font-size: 12px;
                min-width: 500px;
            }
            th, td {
                padding: 8px 6px;
                font-size: 12px;
            }

            .btn {
                padding: 8px 16px;
                font-size: 13px;
            }
            .btn-sm {
                padding: 5px 10px;
                font-size: 11px;
            }

            .form-actions {
                flex-direction: column;
            }
            .form-actions .btn {
                width: 100%;
            }

            .modal-content {
                padding: 15px;
                border-radius: 8px;
            }
            .modal-content h2 { font-size: 20px; }

            .login-container {
                margin: 30px auto;
                padding: 20px;
                border-radius: 8px;
            }
            .login-container h2 { font-size: 20px; }
        }

        /* Extra small devices */
        @media (max-width: 360px) {
            .header h1 { font-size: 16px; }
            .stat-card .value { font-size: 24px; }
            table { min-width: 450px; }
        }
    </style>
</head>
<body>
    <div id="loginView" class="login-container">
        <h2>🔧 Garage Management System</h2>
        <form id="loginForm">
            <div class="form-group">
                <label>Username</label>
                <input type="text" id="username" value="admin" required>
            </div>
            <div class="form-group">
                <label>Password</label>
                <input type="password" id="password" value="admin123" required>
            </div>
            <button type="submit" class="btn btn-primary" style="width: 100%">Login</button>
        </form>
    </div>

    <div id="mainView" class="container hidden">
        <div class="header">
            <h1>🔧 Garage Management System</h1>
            <button class="btn btn-danger" onclick="logout()">Logout</button>
        </div>

        <div class="stats" id="stats"></div>

        <div class="content">
            <div class="tabs">
                <button class="tab active" onclick="showTab('customers')">Customers</button>
                <button class="tab" onclick="showTab('vehicles')">Vehicles</button>
                <button class="tab" onclick="showTab('services')">Services</button>
                <button class="tab" onclick="showTab('bookings')">Bookings</button>
                <button class="tab" onclick="showTab('technicians')">Technicians</button>
                <button class="tab" onclick="showTab('parts')">Parts Inventory</button>
                <button class="tab" onclick="showTab('catalog')">Service Catalog</button>
            </div>

            <div id="customersTab" class="tab-content active">
                <button class="btn btn-primary" onclick="showAddCustomer()">+ Add Customer</button>
                <div class="table-wrapper">
                    <table>
                        <thead>
                            <tr>
                                <th>Name</th>
                                <th>Email</th>
                                <th>Phone</th>
                                <th>Address</th>
                                <th>Actions</th>
                            </tr>
                        </thead>
                        <tbody id="customersTable"></tbody>
                    </table>
                </div>
            </div>

            <div id="vehiclesTab" class="tab-content">
                <button class="btn btn-primary" onclick="showAddVehicle()">+ Add Vehicle</button>
                <div class="table-wrapper">
                    <table>
                        <thead>
                            <tr>
                                <th>Owner</th>
                                <th>Make/Model</th>
                                <th>Year</th>
                                <th>License Plate</th>
                                <th>Color</th>
                                <th>Actions</th>
                            </tr>
                        </thead>
                        <tbody id="vehiclesTable"></tbody>
                    </table>
                </div>
            </div>

            <div id="servicesTab" class="tab-content">
                <button class="btn btn-primary" onclick="showAddService()">+ Add Service</button>
                <div class="table-wrapper">
                    <table>
                        <thead>
                            <tr>
                                <th>Vehicle</th>
                                <th>Service Type</th>
                                <th>Cost</th>
                                <th>Status</th>
                                <th>Technician</th>
                                <th>Date</th>
                                <th>Actions</th>
                            </tr>
                        </thead>
                        <tbody id="servicesTable"></tbody>
                    </table>
                </div>
            </div>

            <div id="bookingsTab" class="tab-content">
                <button class="btn btn-primary" onclick="showAddBooking()">+ Add Booking</button>
                <div class="table-wrapper">
                    <table>
                        <thead>
                            <tr>
                                <th>Customer</th>
                                <th>Vehicle</th>
                                <th>Service</th>
                                <th>Date</th>
                                <th>Time</th>
                                <th>Technician</th>
                                <th>Status</th>
                                <th>Actions</th>
                            </tr>
                        </thead>
                        <tbody id="bookingsTable"></tbody>
                    </table>
                </div>
            </div>

            <div id="techniciansTab" class="tab-content">
                <button class="btn btn-primary" onclick="showAddTechnician()">+ Add Technician</button>
                <div class="table-wrapper">
                    <table>
                        <thead>
                            <tr>
                                <th>Name</th>
                                <th>Specialization</th>
                                <th>Phone</th>
                                <th>Email</th>
                                <th>Status</th>
                                <th>Workload</th>
                                <th>Actions</th>
                            </tr>
                        </thead>
                        <tbody id="techniciansTable"></tbody>
                    </table>
                </div>
            </div>

            <div id="partsTab" class="tab-content">
                <button class="btn btn-primary" onclick="showAddPart()">+ Add Part</button>
                <div class="table-wrapper">
                    <table>
                        <thead>
                            <tr>
                                <th>Part Number</th>
                                <th>Name</th>
                                <th>Quantity</th>
                                <th>Unit Price</th>
                                <th>Supplier</th>
                                <th>Reorder Level</th>
                                <th>Actions</th>
                            </tr>
                        </thead>
                        <tbody id="partsTable"></tbody>
                    </table>
                </div>
            </div>

            <div id="catalogTab" class="tab-content">
                <button class="btn btn-primary" onclick="showAddCatalog()">+ Add Service</button>
                <div class="table-wrapper">
                    <table>
                        <thead>
                            <tr>
                                <th>Service Name</th>
                                <th>Description</th>
                                <th>Base Price</th>
                                <th>Duration (min)</th>
                                <th>Category</th>
                                <th>Actions</th>
                            </tr>
                        </thead>
                        <tbody id="catalogTable"></tbody>
                    </table>
                </div>
            </div>
        </div>
    </div>

    <div id="modal" class="modal">
        <div class="modal-content" id="modalContent"></div>
    </div>

    <script>
        let token = localStorage.getItem('token');
        let customers = [];
        let vehicles = [];
        let services = [];
        let bookings = [];
        let technicians = [];
        let parts = [];
        let serviceCatalog = [];

        function showTab(tab) {
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
            event.target.classList.add('active');
            document.getElementById(tab + 'Tab').classList.add('active');
        }

        async function api(url, options = {}) {
            const headers = { 'Content-Type': 'application/json' };
            if (token) headers['Authorization'] = token;
            const response = await fetch(url, { ...options, headers });
            if (response.status === 401) {
                logout();
                return null;
            }
            return response.json();
        }

        document.getElementById('loginForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            const username = document.getElementById('username').value;
            const password = document.getElementById('password').value;
            const result = await api('/api/login', {
                method: 'POST',
                body: JSON.stringify({ username, password })
            });
            if (result && result.success) {
                token = result.token;
                localStorage.setItem('token', token);
                document.getElementById('loginView').classList.add('hidden');
                document.getElementById('mainView').classList.remove('hidden');
                loadData();
            } else {
                alert('Login failed');
            }
        });

        function logout() {
            localStorage.removeItem('token');
            location.reload();
        }

        async function loadData() {
            const [statsData, customersData, vehiclesData, servicesData, bookingsData,
                   techniciansData, partsData, catalogData] = await Promise.all([
                api('/api/stats'),
                api('/api/customers'),
                api('/api/vehicles'),
                api('/api/services'),
                api('/api/bookings'),
                api('/api/technicians'),
                api('/api/parts'),
                api('/api/service-catalog')
            ]);

            if (statsData) renderStats(statsData);
            if (customersData) {
                customers = customersData;
                renderCustomers();
            }
            if (vehiclesData) {
                vehicles = vehiclesData;
                renderVehicles();
            }
            if (servicesData) {
                services = servicesData;
                renderServices();
            }
            if (bookingsData) {
                bookings = bookingsData;
                renderBookings();
            }
            if (techniciansData) {
                technicians = techniciansData;
                renderTechnicians();
            }
            if (partsData) {
                parts = partsData;
                renderParts();
            }
            if (catalogData) {
                serviceCatalog = catalogData;
                renderCatalog();
            }
        }

        function renderStats(stats) {
            document.getElementById('stats').innerHTML = `
                <div class="stat-card">
                    <h3>Total Customers</h3>
                    <div class="value">${stats.total_customers}</div>
                </div>
                <div class="stat-card">
                    <h3>Total Vehicles</h3>
                    <div class="value">${stats.total_vehicles}</div>
                </div>
                <div class="stat-card">
                    <h3>Pending Services</h3>
                    <div class="value">${stats.pending_services}</div>
                </div>
                <div class="stat-card">
                    <h3>Total Revenue</h3>
                    <div class="value">KSh ${stats.total_revenue.toFixed(2)}</div>
                </div>
            `;
        }

        function renderCustomers() {
            document.getElementById('customersTable').innerHTML = customers.map(c => `
                <tr>
                    <td>${c.name}</td>
                    <td>${c.email}</td>
                    <td>${c.phone}</td>
                    <td>${c.address || 'N/A'}</td>
                    <td>
                        <button class="btn btn-sm btn-primary" onclick="editCustomer(${c.id})">Edit</button>
                        <button class="btn btn-sm btn-danger" onclick="deleteCustomer(${c.id})">Delete</button>
                    </td>
                </tr>
            `).join('');
        }

        function renderVehicles() {
            document.getElementById('vehiclesTable').innerHTML = vehicles.map(v => `
                <tr>
                    <td>${v.owner_name}</td>
                    <td>${v.make} ${v.model}</td>
                    <td>${v.year}</td>
                    <td>${v.license_plate}</td>
                    <td>${v.color || 'N/A'}</td>
                    <td>
                        <button class="btn btn-sm btn-primary" onclick="editVehicle(${v.id})">Edit</button>
                        <button class="btn btn-sm btn-danger" onclick="deleteVehicle(${v.id})">Delete</button>
                    </td>
                </tr>
            `).join('');
        }

        function renderServices() {
            document.getElementById('servicesTable').innerHTML = services.map(s => `
                <tr>
                    <td>${s.vehicle_info}</td>
                    <td>${s.service_type}</td>
                    <td>KSh ${s.cost.toFixed(2)}</td>
                    <td><span class="status-badge status-${s.status}">${s.status.replace('_', ' ')}</span></td>
                    <td>${s.technician || 'Unassigned'}</td>
                    <td>${new Date(s.service_date).toLocaleDateString()}</td>
                    <td>
                        <button class="btn btn-sm btn-primary" onclick="editService(${s.id})">Edit</button>
                        <button class="btn btn-sm btn-danger" onclick="deleteService(${s.id})">Delete</button>
                    </td>
                </tr>
            `).join('');
        }

        function showAddCustomer() {
            document.getElementById('modalContent').innerHTML = `
                <h2>Add Customer</h2>
                <form id="customerForm">
                    <div class="form-group">
                        <label>Name *</label>
                        <input type="text" name="name" required>
                    </div>
                    <div class="form-group">
                        <label>Email *</label>
                        <input type="email" name="email" required>
                    </div>
                    <div class="form-group">
                        <label>Phone *</label>
                        <input type="tel" name="phone" required>
                    </div>
                    <div class="form-group">
                        <label>Address</label>
                        <input type="text" name="address">
                    </div>
                    <div class="form-actions">
                        <button type="button" class="btn" onclick="closeModal()">Cancel</button>
                        <button type="submit" class="btn btn-primary">Add Customer</button>
                    </div>
                </form>
            `;
            document.getElementById('customerForm').addEventListener('submit', async (e) => {
                e.preventDefault();
                const formData = new FormData(e.target);
                const data = Object.fromEntries(formData);
                const result = await api('/api/customers', {
                    method: 'POST',
                    body: JSON.stringify(data)
                });
                if (result && result.success) {
                    closeModal();
                    loadData();
                }
            });
            document.getElementById('modal').classList.add('active');
        }

        function showAddVehicle() {
            document.getElementById('modalContent').innerHTML = `
                <h2>Add Vehicle</h2>
                <form id="vehicleForm">
                    <div class="form-group">
                        <label>Customer *</label>
                        <select name="customer_id" required>
                            <option value="">Select Customer</option>
                            ${customers.map(c => `<option value="${c.id}">${c.name}</option>`).join('')}
                        </select>
                    </div>
                    <div class="form-group">
                        <label>Make *</label>
                        <input type="text" name="make" required>
                    </div>
                    <div class="form-group">
                        <label>Model *</label>
                        <input type="text" name="model" required>
                    </div>
                    <div class="form-group">
                        <label>Year *</label>
                        <input type="number" name="year" required min="1900" max="2100">
                    </div>
                    <div class="form-group">
                        <label>License Plate *</label>
                        <input type="text" name="license_plate" required>
                    </div>
                    <div class="form-group">
                        <label>VIN</label>
                        <input type="text" name="vin">
                    </div>
                    <div class="form-group">
                        <label>Color</label>
                        <input type="text" name="color">
                    </div>
                    <div class="form-actions">
                        <button type="button" class="btn" onclick="closeModal()">Cancel</button>
                        <button type="submit" class="btn btn-primary">Add Vehicle</button>
                    </div>
                </form>
            `;
            document.getElementById('vehicleForm').addEventListener('submit', async (e) => {
                e.preventDefault();
                const formData = new FormData(e.target);
                const data = Object.fromEntries(formData);
                const result = await api('/api/vehicles', {
                    method: 'POST',
                    body: JSON.stringify(data)
                });
                if (result && result.success) {
                    closeModal();
                    loadData();
                }
            });
            document.getElementById('modal').classList.add('active');
        }

        function showAddService() {
            document.getElementById('modalContent').innerHTML = `
                <h2>Add Service</h2>
                <form id="serviceForm">
                    <div class="form-group">
                        <label>Vehicle *</label>
                        <select name="vehicle_id" required>
                            <option value="">Select Vehicle</option>
                            ${vehicles.map(v => `<option value="${v.id}">${v.owner_name} - ${v.make} ${v.model} (${v.license_plate})</option>`).join('')}
                        </select>
                    </div>
                    <div class="form-group">
                        <label>Service Type *</label>
                        <input type="text" name="service_type" required>
                    </div>
                    <div class="form-group">
                        <label>Description</label>
                        <textarea name="description"></textarea>
                    </div>
                    <div class="form-group">
                        <label>Cost *</label>
                        <input type="number" name="cost" step="0.01" required>
                    </div>
                    <div class="form-group">
                        <label>Status *</label>
                        <select name="status" required>
                            <option value="pending">Pending</option>
                            <option value="in_progress">In Progress</option>
                            <option value="completed">Completed</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label>Technician</label>
                        <input type="text" name="technician">
                    </div>
                    <div class="form-group">
                        <label>Notes</label>
                        <textarea name="notes"></textarea>
                    </div>
                    <div class="form-actions">
                        <button type="button" class="btn" onclick="closeModal()">Cancel</button>
                        <button type="submit" class="btn btn-primary">Add Service</button>
                    </div>
                </form>
            `;
            document.getElementById('serviceForm').addEventListener('submit', async (e) => {
                e.preventDefault();
                const formData = new FormData(e.target);
                const data = Object.fromEntries(formData);
                const result = await api('/api/services', {
                    method: 'POST',
                    body: JSON.stringify(data)
                });
                if (result && result.success) {
                    closeModal();
                    loadData();
                }
            });
            document.getElementById('modal').classList.add('active');
        }

        async function deleteCustomer(id) {
            if (confirm('Delete this customer and all associated vehicles/services?')) {
                await api(`/api/customers/${id}`, { method: 'DELETE' });
                loadData();
            }
        }

        async function deleteVehicle(id) {
            if (confirm('Delete this vehicle and all associated services?')) {
                await api(`/api/vehicles/${id}`, { method: 'DELETE' });
                loadData();
            }
        }

        async function deleteService(id) {
            if (confirm('Delete this service?')) {
                await api(`/api/services/${id}`, { method: 'DELETE' });
                loadData();
            }
        }

        // Render functions for new features
        function renderBookings() {
            document.getElementById('bookingsTable').innerHTML = bookings.map(b => `
                <tr>
                    <td>${b.customer_name}</td>
                    <td>${b.vehicle_info}</td>
                    <td>${b.service_name}</td>
                    <td>${b.booking_date}</td>
                    <td>${b.booking_time}</td>
                    <td>${b.technician_name}</td>
                    <td><span class="status-badge status-${b.status}">${b.status}</span></td>
                    <td>
                        <button class="btn btn-sm btn-primary" onclick="editBooking(${b.id})">Edit</button>
                        <button class="btn btn-sm btn-danger" onclick="deleteBooking(${b.id})">Delete</button>
                    </td>
                </tr>
            `).join('');
        }

        function renderTechnicians() {
            document.getElementById('techniciansTable').innerHTML = technicians.map(t => `
                <tr>
                    <td>${t.name}</td>
                    <td>${t.specialization || 'N/A'}</td>
                    <td>${t.phone || 'N/A'}</td>
                    <td>${t.email || 'N/A'}</td>
                    <td>${t.status}</td>
                    <td>${t.current_workload}</td>
                    <td>
                        <button class="btn btn-sm btn-primary" onclick="editTechnician(${t.id})">Edit</button>
                        <button class="btn btn-sm btn-danger" onclick="deleteTechnician(${t.id})">Delete</button>
                    </td>
                </tr>
            `).join('');
        }

        function renderParts() {
            document.getElementById('partsTable').innerHTML = parts.map(p => `
                <tr ${p.quantity <= p.reorder_level ? 'style="background: #fff3cd;"' : ''}>
                    <td>${p.part_number}</td>
                    <td>${p.name}</td>
                    <td>${p.quantity}${p.quantity <= p.reorder_level ? ' ⚠️' : ''}</td>
                    <td>KSh ${p.unit_price.toFixed(2)}</td>
                    <td>${p.supplier || 'N/A'}</td>
                    <td>${p.reorder_level}</td>
                    <td>
                        <button class="btn btn-sm btn-primary" onclick="editPart(${p.id})">Edit</button>
                        <button class="btn btn-sm btn-danger" onclick="deletePart(${p.id})">Delete</button>
                    </td>
                </tr>
            `).join('');
        }

        function renderCatalog() {
            document.getElementById('catalogTable').innerHTML = serviceCatalog.map(s => `
                <tr>
                    <td>${s.service_name}</td>
                    <td>${s.description || 'N/A'}</td>
                    <td>KSh ${s.base_price.toFixed(2)}</td>
                    <td>${s.estimated_duration}</td>
                    <td>${s.category}</td>
                    <td>
                        <button class="btn btn-sm btn-primary" onclick="editCatalog(${s.id})">Edit</button>
                        <button class="btn btn-sm btn-danger" onclick="deleteCatalog(${s.id})">Delete</button>
                    </td>
                </tr>
            `).join('');
        }

        // Add/Edit/Delete functions for new features
        function showAddBooking() {
            document.getElementById('modalContent').innerHTML = `
                <h2>Add Booking</h2>
                <form id="bookingForm">
                    <div class="form-group">
                        <label>Customer *</label>
                        <select name="customer_id" required>
                            <option value="">Select Customer</option>
                            ${customers.map(c => `<option value="${c.id}">${c.name}</option>`).join('')}
                        </select>
                    </div>
                    <div class="form-group">
                        <label>Vehicle</label>
                        <select name="vehicle_id">
                            <option value="">Select Vehicle</option>
                            ${vehicles.map(v => `<option value="${v.id}">${v.owner_name} - ${v.make} ${v.model} (${v.license_plate})</option>`).join('')}
                        </select>
                    </div>
                    <div class="form-group">
                        <label>Service from Catalog</label>
                        <select name="service_catalog_id">
                            <option value="">Select Service</option>
                            ${serviceCatalog.map(s => `<option value="${s.id}">${s.service_name} - KSh ${s.base_price}</option>`).join('')}
                        </select>
                    </div>
                    <div class="form-group">
                        <label>Date *</label>
                        <input type="date" name="booking_date" required>
                    </div>
                    <div class="form-group">
                        <label>Time *</label>
                        <input type="time" name="booking_time" required>
                    </div>
                    <div class="form-group">
                        <label>Status *</label>
                        <select name="status">
                            <option value="scheduled">Scheduled</option>
                            <option value="completed">Completed</option>
                            <option value="cancelled">Cancelled</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label>Notes</label>
                        <textarea name="notes"></textarea>
                    </div>
                    <div class="form-actions">
                        <button type="button" class="btn" onclick="closeModal()">Cancel</button>
                        <button type="submit" class="btn btn-primary">Add Booking</button>
                    </div>
                </form>
            `;
            document.getElementById('bookingForm').addEventListener('submit', async (e) => {
                e.preventDefault();
                const formData = new FormData(e.target);
                const data = Object.fromEntries(formData);
                const result = await api('/api/bookings', {
                    method: 'POST',
                    body: JSON.stringify(data)
                });
                if (result && result.success) {
                    if (result.assigned_technician_id) {
                        alert(`Booking created! Auto-assigned to technician.`);
                    }
                    closeModal();
                    loadData();
                }
            });
            document.getElementById('modal').classList.add('active');
        }

        function showAddTechnician() {
            document.getElementById('modalContent').innerHTML = `
                <h2>Add Technician</h2>
                <form id="technicianForm">
                    <div class="form-group">
                        <label>Name *</label>
                        <input type="text" name="name" required>
                    </div>
                    <div class="form-group">
                        <label>Specialization</label>
                        <input type="text" name="specialization">
                    </div>
                    <div class="form-group">
                        <label>Phone</label>
                        <input type="tel" name="phone">
                    </div>
                    <div class="form-group">
                        <label>Email</label>
                        <input type="email" name="email">
                    </div>
                    <div class="form-group">
                        <label>Status *</label>
                        <select name="status">
                            <option value="available">Available</option>
                            <option value="busy">Busy</option>
                            <option value="offline">Offline</option>
                        </select>
                    </div>
                    <div class="form-actions">
                        <button type="button" class="btn" onclick="closeModal()">Cancel</button>
                        <button type="submit" class="btn btn-primary">Add Technician</button>
                    </div>
                </form>
            `;
            document.getElementById('technicianForm').addEventListener('submit', async (e) => {
                e.preventDefault();
                const formData = new FormData(e.target);
                const data = Object.fromEntries(formData);
                const result = await api('/api/technicians', {
                    method: 'POST',
                    body: JSON.stringify(data)
                });
                if (result && result.success) {
                    closeModal();
                    loadData();
                }
            });
            document.getElementById('modal').classList.add('active');
        }

        function showAddPart() {
            document.getElementById('modalContent').innerHTML = `
                <h2>Add Part</h2>
                <form id="partForm">
                    <div class="form-group">
                        <label>Part Number *</label>
                        <input type="text" name="part_number" required>
                    </div>
                    <div class="form-group">
                        <label>Name *</label>
                        <input type="text" name="name" required>
                    </div>
                    <div class="form-group">
                        <label>Description</label>
                        <textarea name="description"></textarea>
                    </div>
                    <div class="form-group">
                        <label>Quantity *</label>
                        <input type="number" name="quantity" value="0" required>
                    </div>
                    <div class="form-group">
                        <label>Unit Price *</label>
                        <input type="number" name="unit_price" step="0.01" required>
                    </div>
                    <div class="form-group">
                        <label>Supplier</label>
                        <input type="text" name="supplier">
                    </div>
                    <div class="form-group">
                        <label>Reorder Level</label>
                        <input type="number" name="reorder_level" value="5">
                    </div>
                    <div class="form-actions">
                        <button type="button" class="btn" onclick="closeModal()">Cancel</button>
                        <button type="submit" class="btn btn-primary">Add Part</button>
                    </div>
                </form>
            `;
            document.getElementById('partForm').addEventListener('submit', async (e) => {
                e.preventDefault();
                const formData = new FormData(e.target);
                const data = Object.fromEntries(formData);
                const result = await api('/api/parts', {
                    method: 'POST',
                    body: JSON.stringify(data)
                });
                if (result && result.success) {
                    closeModal();
                    loadData();
                }
            });
            document.getElementById('modal').classList.add('active');
        }

        function showAddCatalog() {
            document.getElementById('modalContent').innerHTML = `
                <h2>Add Service to Catalog</h2>
                <form id="catalogForm">
                    <div class="form-group">
                        <label>Service Name *</label>
                        <input type="text" name="service_name" required>
                    </div>
                    <div class="form-group">
                        <label>Description</label>
                        <textarea name="description"></textarea>
                    </div>
                    <div class="form-group">
                        <label>Base Price *</label>
                        <input type="number" name="base_price" step="0.01" required>
                    </div>
                    <div class="form-group">
                        <label>Estimated Duration (minutes)</label>
                        <input type="number" name="estimated_duration" value="60">
                    </div>
                    <div class="form-group">
                        <label>Category</label>
                        <select name="category">
                            <option value="Maintenance">Maintenance</option>
                            <option value="Brakes">Brakes</option>
                            <option value="Tires">Tires</option>
                            <option value="Electrical">Electrical</option>
                            <option value="Diagnostics">Diagnostics</option>
                            <option value="Climate Control">Climate Control</option>
                        </select>
                    </div>
                    <div class="form-actions">
                        <button type="button" class="btn" onclick="closeModal()">Cancel</button>
                        <button type="submit" class="btn btn-primary">Add Service</button>
                    </div>
                </form>
            `;
            document.getElementById('catalogForm').addEventListener('submit', async (e) => {
                e.preventDefault();
                const formData = new FormData(e.target);
                const data = Object.fromEntries(formData);
                const result = await api('/api/service-catalog', {
                    method: 'POST',
                    body: JSON.stringify(data)
                });
                if (result && result.success) {
                    closeModal();
                    loadData();
                }
            });
            document.getElementById('modal').classList.add('active');
        }

        // Edit functions
        function editCustomer(id) {
            const customer = customers.find(c => c.id === id);
            if (!customer) return;

            document.getElementById('modalContent').innerHTML = `
                <h2>Edit Customer</h2>
                <form id="customerForm">
                    <div class="form-group">
                        <label>Name *</label>
                        <input type="text" name="name" value="${customer.name}" required>
                    </div>
                    <div class="form-group">
                        <label>Email *</label>
                        <input type="email" name="email" value="${customer.email}" required>
                    </div>
                    <div class="form-group">
                        <label>Phone *</label>
                        <input type="tel" name="phone" value="${customer.phone}" required>
                    </div>
                    <div class="form-group">
                        <label>Address</label>
                        <input type="text" name="address" value="${customer.address || ''}">
                    </div>
                    <div class="form-actions">
                        <button type="button" class="btn" onclick="closeModal()">Cancel</button>
                        <button type="submit" class="btn btn-primary">Update Customer</button>
                    </div>
                </form>
            `;
            document.getElementById('customerForm').addEventListener('submit', async (e) => {
                e.preventDefault();
                const formData = new FormData(e.target);
                const data = Object.fromEntries(formData);
                const result = await api(`/api/customers/${id}`, {
                    method: 'PUT',
                    body: JSON.stringify(data)
                });
                if (result && result.success) {
                    closeModal();
                    loadData();
                }
            });
            document.getElementById('modal').classList.add('active');
        }

        function editVehicle(id) {
            const vehicle = vehicles.find(v => v.id === id);
            if (!vehicle) return;

            document.getElementById('modalContent').innerHTML = `
                <h2>Edit Vehicle</h2>
                <form id="vehicleForm">
                    <div class="form-group">
                        <label>Customer *</label>
                        <select name="customer_id" required>
                            ${customers.map(c => `<option value="${c.id}" ${c.id === vehicle.customer_id ? 'selected' : ''}>${c.name}</option>`).join('')}
                        </select>
                    </div>
                    <div class="form-group">
                        <label>Make *</label>
                        <input type="text" name="make" value="${vehicle.make}" required>
                    </div>
                    <div class="form-group">
                        <label>Model *</label>
                        <input type="text" name="model" value="${vehicle.model}" required>
                    </div>
                    <div class="form-group">
                        <label>Year *</label>
                        <input type="number" name="year" value="${vehicle.year}" required min="1900" max="2100">
                    </div>
                    <div class="form-group">
                        <label>License Plate *</label>
                        <input type="text" name="license_plate" value="${vehicle.license_plate}" required>
                    </div>
                    <div class="form-group">
                        <label>VIN</label>
                        <input type="text" name="vin" value="${vehicle.vin || ''}">
                    </div>
                    <div class="form-group">
                        <label>Color</label>
                        <input type="text" name="color" value="${vehicle.color || ''}">
                    </div>
                    <div class="form-actions">
                        <button type="button" class="btn" onclick="closeModal()">Cancel</button>
                        <button type="submit" class="btn btn-primary">Update Vehicle</button>
                    </div>
                </form>
            `;
            document.getElementById('vehicleForm').addEventListener('submit', async (e) => {
                e.preventDefault();
                const formData = new FormData(e.target);
                const data = Object.fromEntries(formData);
                const result = await api(`/api/vehicles/${id}`, {
                    method: 'PUT',
                    body: JSON.stringify(data)
                });
                if (result && result.success) {
                    closeModal();
                    loadData();
                }
            });
            document.getElementById('modal').classList.add('active');
        }

        function editService(id) {
            const service = services.find(s => s.id === id);
            if (!service) return;

            document.getElementById('modalContent').innerHTML = `
                <h2>Edit Service</h2>
                <form id="serviceForm">
                    <div class="form-group">
                        <label>Vehicle *</label>
                        <select name="vehicle_id" required>
                            ${vehicles.map(v => `<option value="${v.id}" ${v.id === service.vehicle_id ? 'selected' : ''}>${v.make} ${v.model} (${v.license_plate})</option>`).join('')}
                        </select>
                    </div>
                    <div class="form-group">
                        <label>Service Type *</label>
                        <input type="text" name="service_type" value="${service.service_type}" required>
                    </div>
                    <div class="form-group">
                        <label>Description</label>
                        <textarea name="description" rows="3">${service.description || ''}</textarea>
                    </div>
                    <div class="form-group">
                        <label>Cost (KSh) *</label>
                        <input type="number" name="cost" value="${service.cost}" step="0.01" required>
                    </div>
                    <div class="form-group">
                        <label>Status *</label>
                        <select name="status" required>
                            <option value="pending" ${service.status === 'pending' ? 'selected' : ''}>Pending</option>
                            <option value="in_progress" ${service.status === 'in_progress' ? 'selected' : ''}>In Progress</option>
                            <option value="completed" ${service.status === 'completed' ? 'selected' : ''}>Completed</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label>Technician</label>
                        <input type="text" name="technician" value="${service.technician || ''}">
                    </div>
                    <div class="form-group">
                        <label>Notes</label>
                        <textarea name="notes" rows="2">${service.notes || ''}</textarea>
                    </div>
                    <div class="form-actions">
                        <button type="button" class="btn" onclick="closeModal()">Cancel</button>
                        <button type="submit" class="btn btn-primary">Update Service</button>
                    </div>
                </form>
            `;
            document.getElementById('serviceForm').addEventListener('submit', async (e) => {
                e.preventDefault();
                const formData = new FormData(e.target);
                const data = Object.fromEntries(formData);
                const result = await api(`/api/services/${id}`, {
                    method: 'PUT',
                    body: JSON.stringify(data)
                });
                if (result && result.success) {
                    closeModal();
                    loadData();
                }
            });
            document.getElementById('modal').classList.add('active');
        }

        function editBooking(id) {
            const booking = bookings.find(b => b.id === id);
            if (!booking) return;

            document.getElementById('modalContent').innerHTML = `
                <h2>Edit Booking</h2>
                <form id="bookingForm">
                    <div class="form-group">
                        <label>Vehicle *</label>
                        <select name="vehicle_id" required>
                            ${vehicles.map(v => `<option value="${v.id}" ${v.id === booking.vehicle_id ? 'selected' : ''}>${v.make} ${v.model} (${v.license_plate})</option>`).join('')}
                        </select>
                    </div>
                    <div class="form-group">
                        <label>Service *</label>
                        <select name="service_catalog_id" required>
                            ${catalog.map(s => `<option value="${s.id}" ${s.id === booking.service_catalog_id ? 'selected' : ''}>${s.service_name} - KSh ${s.base_price}</option>`).join('')}
                        </select>
                    </div>
                    <div class="form-group">
                        <label>Date *</label>
                        <input type="date" name="booking_date" value="${booking.booking_date}" required>
                    </div>
                    <div class="form-group">
                        <label>Time *</label>
                        <input type="time" name="booking_time" value="${booking.booking_time}" required>
                    </div>
                    <div class="form-group">
                        <label>Technician</label>
                        <select name="assigned_technician_id">
                            <option value="">Not assigned</option>
                            ${technicians.map(t => `<option value="${t.id}" ${t.id === booking.assigned_technician_id ? 'selected' : ''}>${t.name}</option>`).join('')}
                        </select>
                    </div>
                    <div class="form-group">
                        <label>Status *</label>
                        <select name="status" required>
                            <option value="scheduled" ${booking.status === 'scheduled' ? 'selected' : ''}>Scheduled</option>
                            <option value="completed" ${booking.status === 'completed' ? 'selected' : ''}>Completed</option>
                            <option value="cancelled" ${booking.status === 'cancelled' ? 'selected' : ''}>Cancelled</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label>Notes</label>
                        <textarea name="notes" rows="2">${booking.notes || ''}</textarea>
                    </div>
                    <div class="form-actions">
                        <button type="button" class="btn" onclick="closeModal()">Cancel</button>
                        <button type="submit" class="btn btn-primary">Update Booking</button>
                    </div>
                </form>
            `;
            document.getElementById('bookingForm').addEventListener('submit', async (e) => {
                e.preventDefault();
                const formData = new FormData(e.target);
                const data = Object.fromEntries(formData);
                const result = await api(`/api/bookings/${id}`, {
                    method: 'PUT',
                    body: JSON.stringify(data)
                });
                if (result && result.success) {
                    closeModal();
                    loadData();
                }
            });
            document.getElementById('modal').classList.add('active');
        }

        function editTechnician(id) {
            const tech = technicians.find(t => t.id === id);
            if (!tech) return;

            document.getElementById('modalContent').innerHTML = `
                <h2>Edit Technician</h2>
                <form id="technicianForm">
                    <div class="form-group">
                        <label>Name *</label>
                        <input type="text" name="name" value="${tech.name}" required>
                    </div>
                    <div class="form-group">
                        <label>Specialization</label>
                        <input type="text" name="specialization" value="${tech.specialization || ''}">
                    </div>
                    <div class="form-group">
                        <label>Phone</label>
                        <input type="tel" name="phone" value="${tech.phone || ''}">
                    </div>
                    <div class="form-group">
                        <label>Email</label>
                        <input type="email" name="email" value="${tech.email || ''}">
                    </div>
                    <div class="form-group">
                        <label>Status *</label>
                        <select name="status" required>
                            <option value="available" ${tech.status === 'available' ? 'selected' : ''}>Available</option>
                            <option value="busy" ${tech.status === 'busy' ? 'selected' : ''}>Busy</option>
                        </select>
                    </div>
                    <div class="form-actions">
                        <button type="button" class="btn" onclick="closeModal()">Cancel</button>
                        <button type="submit" class="btn btn-primary">Update Technician</button>
                    </div>
                </form>
            `;
            document.getElementById('technicianForm').addEventListener('submit', async (e) => {
                e.preventDefault();
                const formData = new FormData(e.target);
                const data = Object.fromEntries(formData);
                const result = await api(`/api/technicians/${id}`, {
                    method: 'PUT',
                    body: JSON.stringify(data)
                });
                if (result && result.success) {
                    closeModal();
                    loadData();
                }
            });
            document.getElementById('modal').classList.add('active');
        }

        function editPart(id) {
            const part = parts.find(p => p.id === id);
            if (!part) return;

            document.getElementById('modalContent').innerHTML = `
                <h2>Edit Part</h2>
                <form id="partForm">
                    <div class="form-group">
                        <label>Part Number *</label>
                        <input type="text" name="part_number" value="${part.part_number}" required>
                    </div>
                    <div class="form-group">
                        <label>Name *</label>
                        <input type="text" name="name" value="${part.name}" required>
                    </div>
                    <div class="form-group">
                        <label>Description</label>
                        <textarea name="description" rows="2">${part.description || ''}</textarea>
                    </div>
                    <div class="form-group">
                        <label>Quantity *</label>
                        <input type="number" name="quantity" value="${part.quantity}" required min="0">
                    </div>
                    <div class="form-group">
                        <label>Unit Price (KSh) *</label>
                        <input type="number" name="unit_price" value="${part.unit_price}" step="0.01" required>
                    </div>
                    <div class="form-group">
                        <label>Supplier</label>
                        <input type="text" name="supplier" value="${part.supplier || ''}">
                    </div>
                    <div class="form-group">
                        <label>Reorder Level *</label>
                        <input type="number" name="reorder_level" value="${part.reorder_level}" required min="0">
                    </div>
                    <div class="form-actions">
                        <button type="button" class="btn" onclick="closeModal()">Cancel</button>
                        <button type="submit" class="btn btn-primary">Update Part</button>
                    </div>
                </form>
            `;
            document.getElementById('partForm').addEventListener('submit', async (e) => {
                e.preventDefault();
                const formData = new FormData(e.target);
                const data = Object.fromEntries(formData);
                const result = await api(`/api/parts/${id}`, {
                    method: 'PUT',
                    body: JSON.stringify(data)
                });
                if (result && result.success) {
                    closeModal();
                    loadData();
                }
            });
            document.getElementById('modal').classList.add('active');
        }

        function editCatalog(id) {
            const service = catalog.find(s => s.id === id);
            if (!service) return;

            document.getElementById('modalContent').innerHTML = `
                <h2>Edit Service Catalog</h2>
                <form id="catalogForm">
                    <div class="form-group">
                        <label>Service Name *</label>
                        <input type="text" name="service_name" value="${service.service_name}" required>
                    </div>
                    <div class="form-group">
                        <label>Description</label>
                        <textarea name="description" rows="3">${service.description || ''}</textarea>
                    </div>
                    <div class="form-group">
                        <label>Base Price (KSh) *</label>
                        <input type="number" name="base_price" value="${service.base_price}" step="0.01" required>
                    </div>
                    <div class="form-group">
                        <label>Estimated Duration (minutes) *</label>
                        <input type="number" name="estimated_duration" value="${service.estimated_duration}" required min="1">
                    </div>
                    <div class="form-group">
                        <label>Category</label>
                        <input type="text" name="category" value="${service.category || ''}">
                    </div>
                    <div class="form-actions">
                        <button type="button" class="btn" onclick="closeModal()">Cancel</button>
                        <button type="submit" class="btn btn-primary">Update Service</button>
                    </div>
                </form>
            `;
            document.getElementById('catalogForm').addEventListener('submit', async (e) => {
                e.preventDefault();
                const formData = new FormData(e.target);
                const data = Object.fromEntries(formData);
                const result = await api(`/api/service-catalog/${id}`, {
                    method: 'PUT',
                    body: JSON.stringify(data)
                });
                if (result && result.success) {
                    closeModal();
                    loadData();
                }
            });
            document.getElementById('modal').classList.add('active');
        }

        // Delete functions for new features
        async function deleteBooking(id) {
            if (confirm('Delete this booking?')) {
                await api(`/api/bookings/${id}`, { method: 'DELETE' });
                loadData();
            }
        }

        async function deleteTechnician(id) {
            if (confirm('Delete this technician?')) {
                await api(`/api/technicians/${id}`, { method: 'DELETE' });
                loadData();
            }
        }

        async function deletePart(id) {
            if (confirm('Delete this part?')) {
                await api(`/api/parts/${id}`, { method: 'DELETE' });
                loadData();
            }
        }

        async function deleteCatalog(id) {
            if (confirm('Delete this service from catalog?')) {
                await api(`/api/service-catalog/${id}`, { method: 'DELETE' });
                loadData();
            }
        }

        function closeModal() {
            document.getElementById('modal').classList.remove('active');
        }

        document.getElementById('modal').addEventListener('click', (e) => {
            if (e.target.id === 'modal') closeModal();
        });

        if (token) {
            document.getElementById('loginView').classList.add('hidden');
            document.getElementById('mainView').classList.remove('hidden');
            loadData();
        }
    </script>
</body>
</html>'''

        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.send_security_headers()
        self.end_headers()
        self.wfile.write(html.encode())

    def handle_login(self, data):
        username = data.get('username', '').strip()
        password = data.get('password', '')

        if not username or not password:
            self.send_json_response({'success': False, 'message': 'Username and password are required'}, 400)
            return

        # Rate limiting
        identifier = f"admin_{username}"
        if not check_rate_limit(identifier):
            self.send_json_response({'success': False, 'message': 'Too many login attempts. Please try again later.'}, 429)
            return

        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('SELECT id, password_hash FROM users WHERE username = ?', (username,))
        user = cursor.fetchone()
        conn.close()

        if user and verify_password(password, user[1]):
            token = create_session(user[0])
            self.send_json_response({'success': True, 'token': token})
        else:
            record_login_attempt(identifier)
            self.send_json_response({'success': False, 'message': 'Invalid credentials'}, 401)

    def handle_stats(self):
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()

        cursor.execute('SELECT COUNT(*) FROM customers')
        total_customers = cursor.fetchone()[0]

        cursor.execute('SELECT COUNT(*) FROM vehicles')
        total_vehicles = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM services WHERE status = 'pending'")
        pending_services = cursor.fetchone()[0]

        cursor.execute("SELECT SUM(cost) FROM services WHERE status = 'completed'")
        total_revenue = cursor.fetchone()[0] or 0

        conn.close()

        self.send_json_response({
            'total_customers': total_customers,
            'total_vehicles': total_vehicles,
            'pending_services': pending_services,
            'total_revenue': total_revenue
        })

    def handle_get_customers(self):
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('SELECT id, name, email, phone, address FROM customers ORDER BY name')
        customers = [{'id': row[0], 'name': row[1], 'email': row[2], 'phone': row[3], 'address': row[4]}
                    for row in cursor.fetchall()]
        conn.close()
        self.send_json_response(customers)

    def handle_get_vehicles(self):
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT v.id, v.customer_id, v.make, v.model, v.year, v.license_plate, v.vin, v.color, c.name
            FROM vehicles v
            JOIN customers c ON v.customer_id = c.id
            ORDER BY c.name, v.make
        ''')
        vehicles = [{'id': row[0], 'customer_id': row[1], 'make': row[2], 'model': row[3],
                    'year': row[4], 'license_plate': row[5], 'vin': row[6], 'color': row[7],
                    'owner_name': row[8]} for row in cursor.fetchall()]
        conn.close()
        self.send_json_response(vehicles)

    def handle_get_services(self):
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT s.id, s.vehicle_id, s.service_type, s.description, s.cost, s.status,
                   s.service_date, s.completed_date, s.technician, s.notes,
                   c.name, v.make, v.model, v.license_plate
            FROM services s
            JOIN vehicles v ON s.vehicle_id = v.id
            JOIN customers c ON v.customer_id = c.id
            ORDER BY s.service_date DESC
        ''')
        services = [{
            'id': row[0], 'vehicle_id': row[1], 'service_type': row[2], 'description': row[3],
            'cost': row[4], 'status': row[5], 'service_date': row[6], 'completed_date': row[7],
            'technician': row[8], 'notes': row[9],
            'vehicle_info': f"{row[10]} - {row[11]} {row[12]} ({row[13]})"
        } for row in cursor.fetchall()]
        conn.close()
        self.send_json_response(services)

    def handle_add_customer(self, data):
        try:
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute('''INSERT INTO customers (name, email, phone, address) VALUES (?, ?, ?, ?)''',
                          (data['name'], data['email'], data['phone'], data.get('address', '')))
            conn.commit()
            customer_id = cursor.lastrowid
            conn.close()
            self.send_json_response({'success': True, 'id': customer_id})
        except Exception as e:
            self.send_json_response({'success': False, 'message': str(e)}, 400)

    def handle_add_vehicle(self, data):
        try:
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO vehicles (customer_id, make, model, year, license_plate, vin, color)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (data['customer_id'], data['make'], data['model'], data['year'],
                  data['license_plate'], data.get('vin', ''), data.get('color', '')))
            conn.commit()
            vehicle_id = cursor.lastrowid
            conn.close()
            self.send_json_response({'success': True, 'id': vehicle_id})
        except Exception as e:
            self.send_json_response({'success': False, 'message': str(e)}, 400)

    def handle_add_service(self, data):
        try:
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO services (vehicle_id, service_type, description, cost, status, technician, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (data['vehicle_id'], data['service_type'], data.get('description', ''),
                  data['cost'], data.get('status', 'pending'), data.get('technician', ''),
                  data.get('notes', '')))
            conn.commit()
            service_id = cursor.lastrowid
            conn.close()
            self.send_json_response({'success': True, 'id': service_id})
        except Exception as e:
            self.send_json_response({'success': False, 'message': str(e)}, 400)

    def handle_delete_customer(self, customer_id):
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('DELETE FROM customers WHERE id = ?', (customer_id,))
        conn.commit()
        conn.close()
        self.send_json_response({'success': True})

    def handle_delete_vehicle(self, vehicle_id):
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('DELETE FROM vehicles WHERE id = ?', (vehicle_id,))
        conn.commit()
        conn.close()
        self.send_json_response({'success': True})

    def handle_delete_service(self, service_id):
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('DELETE FROM services WHERE id = ?', (service_id,))
        conn.commit()
        conn.close()
        self.send_json_response({'success': True})

    # Missing update handlers (fixing broken edit functionality)
    def handle_update_customer(self, customer_id, data):
        try:
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE customers
                SET name=?, email=?, phone=?, address=?
                WHERE id=?
            ''', (data['name'], data['email'], data['phone'],
                  data.get('address', ''), customer_id))
            conn.commit()
            conn.close()
            self.send_json_response({'success': True})
        except Exception as e:
            self.send_json_response({'success': False, 'message': str(e)}, 400)

    def handle_update_vehicle(self, vehicle_id, data):
        try:
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE vehicles
                SET customer_id=?, make=?, model=?, year=?, license_plate=?, vin=?, color=?
                WHERE id=?
            ''', (data['customer_id'], data['make'], data['model'], data['year'],
                  data['license_plate'], data.get('vin', ''), data.get('color', ''), vehicle_id))
            conn.commit()
            conn.close()
            self.send_json_response({'success': True})
        except Exception as e:
            self.send_json_response({'success': False, 'message': str(e)}, 400)

    def handle_update_service(self, service_id, data):
        try:
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE services
                SET vehicle_id=?, service_type=?, description=?, cost=?, status=?, technician=?, notes=?
                WHERE id=?
            ''', (data['vehicle_id'], data['service_type'], data.get('description', ''),
                  data['cost'], data.get('status', 'pending'), data.get('technician', ''),
                  data.get('notes', ''), service_id))
            conn.commit()
            conn.close()
            self.send_json_response({'success': True})
        except Exception as e:
            self.send_json_response({'success': False, 'message': str(e)}, 400)

    # Customer authentication
    def handle_customer_login(self, data):
        email = data.get('email', '').strip().lower()
        password = data.get('password', '')

        if not email or not password:
            self.send_json_response({'success': False, 'message': 'Email and password are required'}, 400)
            return

        # Rate limiting
        identifier = f"customer_{email}"
        if not check_rate_limit(identifier):
            self.send_json_response({'success': False, 'message': 'Too many login attempts. Please try again in 5 minutes.'}, 429)
            return

        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT cu.customer_id, c.name, cu.status, cu.password_hash
            FROM customer_users cu
            JOIN customers c ON cu.customer_id = c.id
            WHERE cu.email = ?
        ''', (email,))
        customer = cursor.fetchone()
        conn.close()

        if customer and verify_password(password, customer[3]):
            # Check if account is active
            if customer[2] == 'suspended':
                self.send_json_response({'success': False, 'message': 'Account suspended. Please contact support.'}, 403)
            elif customer[2] == 'pending_verification':
                self.send_json_response({'success': False, 'message': 'Account pending verification. Please check your email.'}, 403)
            else:
                token = create_customer_session(customer[0])
                self.send_json_response({'success': True, 'token': token, 'name': customer[1]})
        else:
            record_login_attempt(identifier)
            self.send_json_response({'success': False, 'message': 'Invalid credentials'}, 401)

    def handle_customer_register(self, data):
        import re

        # Validate required fields
        email = data.get('email', '').strip().lower()
        password = data.get('password', '')
        name = data.get('name', '').strip()
        phone = data.get('phone', '').strip()

        if not email or not password or not name:
            self.send_json_response({'success': False, 'message': 'Email, password, and name are required'}, 400)
            return

        # Validate email format
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, email):
            self.send_json_response({'success': False, 'message': 'Invalid email format'}, 400)
            return

        # Validate password strength (min 8 chars, has uppercase, lowercase, and number)
        if len(password) < 8:
            self.send_json_response({'success': False, 'message': 'Password must be at least 8 characters long'}, 400)
            return
        if not re.search(r'[A-Z]', password):
            self.send_json_response({'success': False, 'message': 'Password must contain at least one uppercase letter'}, 400)
            return
        if not re.search(r'[a-z]', password):
            self.send_json_response({'success': False, 'message': 'Password must contain at least one lowercase letter'}, 400)
            return
        if not re.search(r'\d', password):
            self.send_json_response({'success': False, 'message': 'Password must contain at least one number'}, 400)
            return

        try:
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()

            # Check if email already exists
            cursor.execute('SELECT id FROM customer_users WHERE email = ?', (email,))
            if cursor.fetchone():
                conn.close()
                self.send_json_response({'success': False, 'message': 'Email already registered'}, 400)
                return

            # Check if email exists in customers table
            cursor.execute('SELECT id FROM customers WHERE email = ?', (email,))
            existing_customer = cursor.fetchone()

            if existing_customer:
                customer_id = existing_customer[0]
            else:
                # Create customer record
                cursor.execute('''
                    INSERT INTO customers (name, email, phone, address)
                    VALUES (?, ?, ?, ?)
                ''', (name, email, phone, data.get('address', '')))
                customer_id = cursor.lastrowid

            # Hash password with PBKDF2
            password_hash = hash_password(password)

            # Generate verification token
            verification_token = secrets.token_urlsafe(32)

            # Create customer_user record as active (email verification can be added later)
            # Changed to 'active' for immediate login after registration
            cursor.execute('''
                INSERT INTO customer_users (customer_id, email, password_hash, status, verification_token)
                VALUES (?, ?, ?, ?, ?)
            ''', (customer_id, email, password_hash, 'active', verification_token))

            user_id = cursor.lastrowid
            conn.commit()
            conn.close()

            # In a production application, you would send a verification email here
            # For now, we'll activate the account immediately for better UX
            self.send_json_response({
                'success': True,
                'user_id': user_id,
                'message': 'Registration successful! You can now log in with your credentials.'
            })

        except Exception as e:
            self.send_json_response({'success': False, 'message': str(e)}, 400)

    # Technician handlers
    def handle_get_technicians(self):
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, name, specialization, phone, email, status, current_workload
            FROM technicians ORDER BY name
        ''')
        technicians = [{'id': row[0], 'name': row[1], 'specialization': row[2],
                       'phone': row[3], 'email': row[4], 'status': row[5],
                       'current_workload': row[6]} for row in cursor.fetchall()]
        conn.close()
        self.send_json_response(technicians)

    def handle_add_technician(self, data):
        try:
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO technicians (name, specialization, phone, email, status)
                VALUES (?, ?, ?, ?, ?)
            ''', (data['name'], data.get('specialization', ''), data.get('phone', ''),
                  data.get('email', ''), data.get('status', 'available')))
            conn.commit()
            technician_id = cursor.lastrowid
            conn.close()
            self.send_json_response({'success': True, 'id': technician_id})
        except Exception as e:
            self.send_json_response({'success': False, 'message': str(e)}, 400)

    def handle_update_technician(self, technician_id, data):
        try:
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE technicians
                SET name=?, specialization=?, phone=?, email=?, status=?
                WHERE id=?
            ''', (data['name'], data.get('specialization', ''), data.get('phone', ''),
                  data.get('email', ''), data.get('status', 'available'), technician_id))
            conn.commit()
            conn.close()
            self.send_json_response({'success': True})
        except Exception as e:
            self.send_json_response({'success': False, 'message': str(e)}, 400)

    def handle_delete_technician(self, technician_id):
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('DELETE FROM technicians WHERE id = ?', (technician_id,))
        conn.commit()
        conn.close()
        self.send_json_response({'success': True})

    # Parts inventory handlers
    def handle_get_parts(self):
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, part_number, name, description, quantity, unit_price, supplier, reorder_level
            FROM parts ORDER BY name
        ''')
        parts = [{'id': row[0], 'part_number': row[1], 'name': row[2], 'description': row[3],
                 'quantity': row[4], 'unit_price': row[5], 'supplier': row[6],
                 'reorder_level': row[7]} for row in cursor.fetchall()]
        conn.close()
        self.send_json_response(parts)

    def handle_add_part(self, data):
        try:
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO parts (part_number, name, description, quantity, unit_price, supplier, reorder_level)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (data['part_number'], data['name'], data.get('description', ''),
                  data.get('quantity', 0), data['unit_price'], data.get('supplier', ''),
                  data.get('reorder_level', 5)))
            conn.commit()
            part_id = cursor.lastrowid
            conn.close()
            self.send_json_response({'success': True, 'id': part_id})
        except Exception as e:
            self.send_json_response({'success': False, 'message': str(e)}, 400)

    def handle_update_part(self, part_id, data):
        try:
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE parts
                SET part_number=?, name=?, description=?, quantity=?, unit_price=?, supplier=?, reorder_level=?
                WHERE id=?
            ''', (data['part_number'], data['name'], data.get('description', ''),
                  data.get('quantity', 0), data['unit_price'], data.get('supplier', ''),
                  data.get('reorder_level', 5), part_id))
            conn.commit()
            conn.close()
            self.send_json_response({'success': True})
        except Exception as e:
            self.send_json_response({'success': False, 'message': str(e)}, 400)

    def handle_delete_part(self, part_id):
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('DELETE FROM parts WHERE id = ?', (part_id,))
        conn.commit()
        conn.close()
        self.send_json_response({'success': True})

    # Service catalog handlers
    def handle_get_service_catalog(self):
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, service_name, description, base_price, estimated_duration, category
            FROM service_catalog ORDER BY category, service_name
        ''')
        catalog = [{'id': row[0], 'service_name': row[1], 'description': row[2],
                   'base_price': row[3], 'estimated_duration': row[4], 'category': row[5]}
                   for row in cursor.fetchall()]
        conn.close()
        self.send_json_response(catalog)

    def handle_add_service_catalog(self, data):
        try:
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO service_catalog (service_name, description, base_price, estimated_duration, category)
                VALUES (?, ?, ?, ?, ?)
            ''', (data['service_name'], data.get('description', ''), data['base_price'],
                  data.get('estimated_duration', 60), data.get('category', 'General')))
            conn.commit()
            catalog_id = cursor.lastrowid
            conn.close()
            self.send_json_response({'success': True, 'id': catalog_id})
        except Exception as e:
            self.send_json_response({'success': False, 'message': str(e)}, 400)

    def handle_update_service_catalog(self, catalog_id, data):
        try:
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE service_catalog
                SET service_name=?, description=?, base_price=?, estimated_duration=?, category=?
                WHERE id=?
            ''', (data['service_name'], data.get('description', ''), data['base_price'],
                  data.get('estimated_duration', 60), data.get('category', 'General'), catalog_id))
            conn.commit()
            conn.close()
            self.send_json_response({'success': True})
        except Exception as e:
            self.send_json_response({'success': False, 'message': str(e)}, 400)

    def handle_delete_service_catalog(self, catalog_id):
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('DELETE FROM service_catalog WHERE id = ?', (catalog_id,))
        conn.commit()
        conn.close()
        self.send_json_response({'success': True})

    # Bookings handlers
    def handle_get_bookings(self):
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT b.id, b.customer_id, b.vehicle_id, b.service_catalog_id,
                   b.booking_date, b.booking_time, b.status, b.notes,
                   b.assigned_technician_id, c.name as customer_name,
                   v.make, v.model, v.license_plate,
                   sc.service_name, t.name as technician_name
            FROM bookings b
            JOIN customers c ON b.customer_id = c.id
            LEFT JOIN vehicles v ON b.vehicle_id = v.id
            LEFT JOIN service_catalog sc ON b.service_catalog_id = sc.id
            LEFT JOIN technicians t ON b.assigned_technician_id = t.id
            ORDER BY b.booking_date, b.booking_time
        ''')
        bookings = [{
            'id': row[0], 'customer_id': row[1], 'vehicle_id': row[2],
            'service_catalog_id': row[3], 'booking_date': row[4], 'booking_time': row[5],
            'status': row[6], 'notes': row[7], 'assigned_technician_id': row[8],
            'customer_name': row[9],
            'vehicle_info': f"{row[10]} {row[11]} ({row[12]})" if row[10] else 'N/A',
            'service_name': row[13] or 'N/A',
            'technician_name': row[14] or 'Unassigned'
        } for row in cursor.fetchall()]
        conn.close()
        self.send_json_response(bookings)

    def handle_add_booking(self, data):
        try:
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()

            # Auto-assign technician if not provided
            assigned_technician_id = data.get('assigned_technician_id')
            if not assigned_technician_id:
                technician = assign_technician()
                if technician:
                    assigned_technician_id = technician[0]

            cursor.execute('''
                INSERT INTO bookings (customer_id, vehicle_id, service_catalog_id, booking_date,
                                     booking_time, status, notes, assigned_technician_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (data['customer_id'], data.get('vehicle_id'), data.get('service_catalog_id'),
                  data['booking_date'], data['booking_time'], data.get('status', 'scheduled'),
                  data.get('notes', ''), assigned_technician_id))
            conn.commit()
            booking_id = cursor.lastrowid
            conn.close()
            self.send_json_response({'success': True, 'id': booking_id,
                                    'assigned_technician_id': assigned_technician_id})
        except Exception as e:
            self.send_json_response({'success': False, 'message': str(e)}, 400)

    def handle_update_booking(self, booking_id, data):
        try:
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE bookings
                SET customer_id=?, vehicle_id=?, service_catalog_id=?, booking_date=?,
                    booking_time=?, status=?, notes=?, assigned_technician_id=?
                WHERE id=?
            ''', (data['customer_id'], data.get('vehicle_id'), data.get('service_catalog_id'),
                  data['booking_date'], data['booking_time'], data.get('status', 'scheduled'),
                  data.get('notes', ''), data.get('assigned_technician_id'), booking_id))
            conn.commit()
            conn.close()
            self.send_json_response({'success': True})
        except Exception as e:
            self.send_json_response({'success': False, 'message': str(e)}, 400)

    def handle_delete_booking(self, booking_id):
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        # Decrement technician workload when deleting booking
        cursor.execute('''
            SELECT assigned_technician_id FROM bookings WHERE id = ?
        ''', (booking_id,))
        result = cursor.fetchone()
        if result and result[0]:
            cursor.execute('''
                UPDATE technicians SET current_workload = MAX(0, current_workload - 1)
                WHERE id = ?
            ''', (result[0],))
        cursor.execute('DELETE FROM bookings WHERE id = ?', (booking_id,))
        conn.commit()
        conn.close()
        self.send_json_response({'success': True})

    # Customer portal handlers
    def handle_customer_vehicles(self):
        token = self.headers.get('Authorization')
        customer = verify_customer_session(token)
        if not customer:
            self.send_json_response({'success': False, 'message': 'Unauthorized'}, 401)
            return

        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, make, model, year, license_plate, color
            FROM vehicles WHERE customer_id = ?
            ORDER BY make, model
        ''', (customer['id'],))
        vehicles = [{'id': row[0], 'make': row[1], 'model': row[2],
                    'year': row[3], 'license_plate': row[4], 'color': row[5]}
                    for row in cursor.fetchall()]
        conn.close()
        self.send_json_response(vehicles)

    def handle_customer_bookings(self):
        token = self.headers.get('Authorization')
        customer = verify_customer_session(token)
        if not customer:
            self.send_json_response({'success': False, 'message': 'Unauthorized'}, 401)
            return

        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT b.id, b.booking_date, b.booking_time, b.status,
                   v.make, v.model, v.license_plate,
                   sc.service_name, sc.base_price, t.name as technician_name
            FROM bookings b
            LEFT JOIN vehicles v ON b.vehicle_id = v.id
            LEFT JOIN service_catalog sc ON b.service_catalog_id = sc.id
            LEFT JOIN technicians t ON b.assigned_technician_id = t.id
            WHERE b.customer_id = ?
            ORDER BY b.booking_date DESC, b.booking_time DESC
        ''', (customer['id'],))
        bookings = [{
            'id': row[0], 'booking_date': row[1], 'booking_time': row[2],
            'status': row[3],
            'vehicle_info': f"{row[4]} {row[5]} ({row[6]})" if row[4] else 'N/A',
            'service_name': row[7] or 'N/A',
            'price': row[8] or 0,
            'technician_name': row[9] or 'Unassigned'
        } for row in cursor.fetchall()]
        conn.close()
        self.send_json_response(bookings)

    # Cost calculator
    def handle_cost_calculator(self):
        # GET request - just return success
        self.send_json_response({'success': True})

    def handle_cost_calculator_post(self, data):
        try:
            total_cost = 0
            breakdown = []

            # Add service costs from catalog
            if data.get('service_ids'):
                conn = sqlite3.connect(DB_FILE)
                cursor = conn.cursor()
                placeholders = ','.join('?' * len(data['service_ids']))
                cursor.execute(f'''
                    SELECT service_name, base_price
                    FROM service_catalog
                    WHERE id IN ({placeholders})
                ''', data['service_ids'])
                services = cursor.fetchall()
                for service in services:
                    total_cost += service[1]
                    breakdown.append({'type': 'service', 'name': service[0], 'price': service[1]})
                conn.close()

            # Add parts costs
            if data.get('part_ids'):
                conn = sqlite3.connect(DB_FILE)
                cursor = conn.cursor()
                placeholders = ','.join('?' * len(data['part_ids']))
                cursor.execute(f'''
                    SELECT name, unit_price
                    FROM parts
                    WHERE id IN ({placeholders})
                ''', data['part_ids'])
                parts = cursor.fetchall()
                for part in parts:
                    total_cost += part[1]
                    breakdown.append({'type': 'part', 'name': part[0], 'price': part[1]})
                conn.close()

            # Calculate tax (16% VAT for Kenya)
            tax = total_cost * 0.16
            grand_total = total_cost + tax

            self.send_json_response({
                'success': True,
                'subtotal': round(total_cost, 2),
                'tax': round(tax, 2),
                'total': round(grand_total, 2),
                'breakdown': breakdown
            })
        except Exception as e:
            self.send_json_response({'success': False, 'message': str(e)}, 400)

    def serve_customer_portal(self):
        html = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Customer Portal - Garage Management</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
            min-height: 100vh;
            padding: 20px;
        }
        .container { max-width: 1200px; margin: 0 auto; }
        .header {
            background: white;
            padding: 20px 30px;
            border-radius: 10px;
            box-shadow: 0 8px 16px rgba(0,0,0,0.2);
            margin-bottom: 30px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .btn {
            padding: 10px 20px;
            border: none;
            border-radius: 5px;
            cursor: pointer;
            font-size: 14px;
            transition: all 0.3s;
        }
        .btn-primary {
            background: linear-gradient(135deg, #ff6b35 0%, #f7931e 100%);
            color: white;
        }
        .btn-danger { background: #e74c3c; color: white; }
        .content {
            background: white;
            padding: 30px;
            border-radius: 10px;
            box-shadow: 0 8px 16px rgba(0,0,0,0.2);
        }
        .tabs {
            display: flex;
            gap: 10px;
            margin-bottom: 30px;
            border-bottom: 2px solid #eee;
        }
        .tab {
            padding: 12px 24px;
            background: none;
            border: none;
            cursor: pointer;
            font-size: 16px;
            color: #666;
            border-bottom: 3px solid transparent;
        }
        .tab.active { color: #ff6b35; border-bottom-color: #ff6b35; }
        .tab-content { display: none; }
        .tab-content.active { display: block; }
        table { width: 100%; border-collapse: collapse; margin-top: 20px; }
        th, td { padding: 12px; text-align: left; border-bottom: 1px solid #eee; }
        th { background: #f8f9fa; font-weight: 600; }
        .login-container {
            max-width: 400px;
            margin: 100px auto;
            background: white;
            padding: 40px;
            border-radius: 10px;
            box-shadow: 0 12px 24px rgba(0,0,0,0.3);
        }
        .form-group { margin-bottom: 15px; }
        .form-group label { display: block; margin-bottom: 5px; font-weight: 600; }
        .form-group input, .form-group select {
            width: 100%;
            padding: 10px;
            border: 1px solid #ddd;
            border-radius: 5px;
        }
        .hidden { display: none !important; }
        .modal {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0,0,0,0.7);
            justify-content: center;
            align-items: center;
            z-index: 1000;
        }
        .modal.active { display: flex; }
        .modal-content {
            background: white;
            padding: 30px;
            border-radius: 10px;
            max-width: 500px;
            width: 90%;
        }
        .form-actions { display: flex; gap: 10px; justify-content: flex-end; margin-top: 20px; }
        .status-badge {
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 12px;
            font-weight: 600;
        }
        .status-scheduled { background: #cfe2ff; color: #084298; }
        .status-completed { background: #d1e7dd; color: #0f5132; }
        .status-cancelled { background: #f8d7da; color: #842029; }

        /* Password Strength Indicator */
        .password-strength {
            margin-top: 8px;
            height: 4px;
            background: #e0e0e0;
            border-radius: 2px;
            overflow: hidden;
        }
        .password-strength-bar {
            height: 100%;
            transition: all 0.3s;
            width: 0%;
        }
        .strength-weak { background: #f44336; width: 33%; }
        .strength-medium { background: #ff9800; width: 66%; }
        .strength-strong { background: #4caf50; width: 100%; }
        .password-strength-text {
            font-size: 12px;
            margin-top: 4px;
            font-weight: 600;
        }
        .text-weak { color: #f44336; }
        .text-medium { color: #ff9800; }
        .text-strong { color: #4caf50; }

        /* Error/Success Messages */
        .message {
            padding: 12px 16px;
            border-radius: 5px;
            margin-bottom: 15px;
            font-size: 14px;
            display: none;
        }
        .message.show { display: block; }
        .message-error {
            background: #f8d7da;
            color: #842029;
            border: 1px solid #f5c2c7;
        }
        .message-success {
            background: #d1e7dd;
            color: #0f5132;
            border: 1px solid #badbcc;
        }

        /* Loading State */
        .btn-loading {
            position: relative;
            color: transparent !important;
        }
        .btn-loading::after {
            content: "";
            position: absolute;
            width: 16px;
            height: 16px;
            top: 50%;
            left: 50%;
            margin-left: -8px;
            margin-top: -8px;
            border: 2px solid #ffffff;
            border-radius: 50%;
            border-top-color: transparent;
            animation: spinner 0.6s linear infinite;
        }
        @keyframes spinner {
            to { transform: rotate(360deg); }
        }

        /* Better input focus states */
        .form-group input:focus {
            outline: none;
            border-color: #ff6b35;
            box-shadow: 0 0 0 3px rgba(255, 107, 53, 0.1);
        }
    </style>
</head>
<body>
    <div id="loginView" class="login-container">
        <h2>Customer Portal</h2>
        <p style="margin-bottom: 20px; color: #666;">Login to view your bookings and vehicles</p>
        <div id="loginError" class="message message-error"></div>
        <form id="loginForm">
            <div class="form-group">
                <label>Email</label>
                <input type="email" id="email" placeholder="your.email@example.com" required autocomplete="email">
            </div>
            <div class="form-group">
                <label>Password</label>
                <input type="password" id="password" placeholder="Enter your password" required autocomplete="current-password">
            </div>
            <button type="submit" id="loginBtn" class="btn btn-primary" style="width: 100%">Login</button>
        </form>
        <p style="margin-top: 20px; text-align: center;">
            Don't have an account? <a href="#" onclick="showRegister(); return false;" style="color: #ff6b35;">Register here</a>
        </p>
        <p style="margin-top: 10px; text-align: center;">
            <a href="/" style="color: #666;">Staff Login</a>
        </p>
    </div>

    <div id="registerView" class="login-container hidden">
        <h2>Create Account</h2>
        <p style="margin-bottom: 20px; color: #666;">Register to manage your vehicle services</p>
        <div id="registerError" class="message message-error"></div>
        <div id="registerSuccess" class="message message-success"></div>
        <form id="registerForm">
            <div class="form-group">
                <label>Full Name *</label>
                <input type="text" id="reg_name" placeholder="John Doe" required autocomplete="name">
            </div>
            <div class="form-group">
                <label>Email *</label>
                <input type="email" id="reg_email" placeholder="your.email@example.com" required autocomplete="email">
            </div>
            <div class="form-group">
                <label>Phone</label>
                <input type="tel" id="reg_phone" placeholder="555-0123" autocomplete="tel">
            </div>
            <div class="form-group">
                <label>Address</label>
                <input type="text" id="reg_address" placeholder="123 Main Street" autocomplete="street-address">
            </div>
            <div class="form-group">
                <label>Password *</label>
                <input type="password" id="reg_password" placeholder="Create a strong password" required autocomplete="new-password">
                <div class="password-strength">
                    <div id="strengthBar" class="password-strength-bar"></div>
                </div>
                <div id="strengthText" class="password-strength-text"></div>
                <small style="color: #666; font-size: 12px;">Min 8 characters, must include uppercase, lowercase, and number</small>
            </div>
            <div class="form-group">
                <label>Confirm Password *</label>
                <input type="password" id="reg_confirm_password" placeholder="Re-enter your password" required autocomplete="new-password">
            </div>
            <button type="submit" id="registerBtn" class="btn btn-primary" style="width: 100%">Register</button>
        </form>
        <p style="margin-top: 20px; text-align: center;">
            Already have an account? <a href="#" onclick="showLogin(); return false;" style="color: #ff6b35;">Login here</a>
        </p>
    </div>

    <div id="mainView" class="container hidden">
        <div class="header">
            <div>
                <h1>Welcome, <span id="customerName"></span></h1>
                <p style="color: #666; margin-top: 5px;">Customer Portal</p>
            </div>
            <button class="btn btn-danger" onclick="logout()">Logout</button>
        </div>

        <div class="content">
            <div class="tabs">
                <button class="tab active" onclick="showTab('bookings')">My Bookings</button>
                <button class="tab" onclick="showTab('vehicles')">My Vehicles</button>
                <button class="tab" onclick="showTab('services')">Available Services</button>
                <button class="tab" onclick="showTab('calculator')">Cost Calculator</button>
            </div>

            <div id="bookingsTab" class="tab-content active">
                <button class="btn btn-primary" onclick="showBookingForm()">+ New Booking</button>
                <table>
                    <thead>
                        <tr>
                            <th>Date</th>
                            <th>Time</th>
                            <th>Vehicle</th>
                            <th>Service</th>
                            <th>Price</th>
                            <th>Technician</th>
                            <th>Status</th>
                        </tr>
                    </thead>
                    <tbody id="bookingsTable"></tbody>
                </table>
            </div>

            <div id="vehiclesTab" class="tab-content">
                <table>
                    <thead>
                        <tr>
                            <th>Make/Model</th>
                            <th>Year</th>
                            <th>License Plate</th>
                            <th>Color</th>
                        </tr>
                    </thead>
                    <tbody id="vehiclesTable"></tbody>
                </table>
            </div>

            <div id="servicesTab" class="tab-content">
                <h3>Available Services</h3>
                <table>
                    <thead>
                        <tr>
                            <th>Service</th>
                            <th>Description</th>
                            <th>Price</th>
                            <th>Duration (min)</th>
                            <th>Category</th>
                        </tr>
                    </thead>
                    <tbody id="servicesTable"></tbody>
                </table>
            </div>

            <div id="calculatorTab" class="tab-content">
                <h3>Cost Calculator</h3>
                <div id="calculatorForm">
                    <div class="form-group">
                        <label>Select Services</label>
                        <div id="servicesList"></div>
                    </div>
                    <button class="btn btn-primary" onclick="calculateCost()">Calculate Total</button>
                    <div id="calculatorResult" style="margin-top: 20px;"></div>
                </div>
            </div>
        </div>
    </div>

    <div id="modal" class="modal">
        <div class="modal-content" id="modalContent"></div>
    </div>

    <script>
        let token = localStorage.getItem('customer_token');
        let customerName = '';
        let customerId = null;
        let vehicles = [];
        let services = [];
        let selectedServices = [];

        function showTab(tab) {
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
            event.target.classList.add('active');
            document.getElementById(tab + 'Tab').classList.add('active');
        }

        async function api(url, options = {}) {
            const headers = { 'Content-Type': 'application/json' };
            if (token) headers['Authorization'] = token;
            const response = await fetch(url, { ...options, headers });
            if (response.status === 401) {
                logout();
                return null;
            }
            return response.json();
        }

        // Helper functions for UI
        function showMessage(elementId, message, isError = true) {
            const el = document.getElementById(elementId);
            el.textContent = message;
            el.className = isError ? 'message message-error show' : 'message message-success show';
            setTimeout(() => el.classList.remove('show'), 5000);
        }

        function setLoading(buttonId, isLoading) {
            const btn = document.getElementById(buttonId);
            if (isLoading) {
                btn.classList.add('btn-loading');
                btn.disabled = true;
            } else {
                btn.classList.remove('btn-loading');
                btn.disabled = false;
            }
        }

        // Password strength checker
        function checkPasswordStrength(password) {
            let strength = 0;
            const strengthBar = document.getElementById('strengthBar');
            const strengthText = document.getElementById('strengthText');

            if (!password) {
                strengthBar.className = 'password-strength-bar';
                strengthText.textContent = '';
                return;
            }

            // Check length
            if (password.length >= 8) strength++;
            if (password.length >= 12) strength++;

            // Check character types
            if (/[a-z]/.test(password)) strength++;
            if (/[A-Z]/.test(password)) strength++;
            if (/\d/.test(password)) strength++;
            if (/[^a-zA-Z0-9]/.test(password)) strength++;

            // Determine strength level
            if (strength <= 2) {
                strengthBar.className = 'password-strength-bar strength-weak';
                strengthText.className = 'password-strength-text text-weak';
                strengthText.textContent = 'Weak password';
            } else if (strength <= 4) {
                strengthBar.className = 'password-strength-bar strength-medium';
                strengthText.className = 'password-strength-text text-medium';
                strengthText.textContent = 'Medium strength';
            } else {
                strengthBar.className = 'password-strength-bar strength-strong';
                strengthText.className = 'password-strength-text text-strong';
                strengthText.textContent = 'Strong password';
            }
        }

        // Add password strength checker to registration password field
        document.getElementById('reg_password').addEventListener('input', (e) => {
            checkPasswordStrength(e.target.value);
        });

        document.getElementById('loginForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            const email = document.getElementById('email').value.trim();
            const password = document.getElementById('password').value;

            setLoading('loginBtn', true);
            document.getElementById('loginError').classList.remove('show');

            try {
                const result = await api('/api/customer-login', {
                    method: 'POST',
                    body: JSON.stringify({ email, password })
                });

                if (result && result.success) {
                    token = result.token;
                    customerName = result.name;
                    localStorage.setItem('customer_token', token);
                    document.getElementById('loginView').classList.add('hidden');
                    document.getElementById('mainView').classList.remove('hidden');
                    document.getElementById('customerName').textContent = customerName;
                    loadData();
                } else {
                    showMessage('loginError', result.message || 'Login failed. Please check your credentials.');
                }
            } catch (error) {
                showMessage('loginError', 'Network error. Please try again.');
            } finally {
                setLoading('loginBtn', false);
            }
        });

        document.getElementById('registerForm').addEventListener('submit', async (e) => {
            e.preventDefault();

            const name = document.getElementById('reg_name').value.trim();
            const email = document.getElementById('reg_email').value.trim();
            const phone = document.getElementById('reg_phone').value.trim();
            const address = document.getElementById('reg_address').value.trim();
            const password = document.getElementById('reg_password').value;
            const confirmPassword = document.getElementById('reg_confirm_password').value;

            // Hide previous messages
            document.getElementById('registerError').classList.remove('show');
            document.getElementById('registerSuccess').classList.remove('show');

            // Client-side validation
            if (password !== confirmPassword) {
                showMessage('registerError', 'Passwords do not match');
                return;
            }

            // Validate password strength
            if (password.length < 8) {
                showMessage('registerError', 'Password must be at least 8 characters long');
                return;
            }
            if (!/[A-Z]/.test(password)) {
                showMessage('registerError', 'Password must contain at least one uppercase letter');
                return;
            }
            if (!/[a-z]/.test(password)) {
                showMessage('registerError', 'Password must contain at least one lowercase letter');
                return;
            }
            if (!/\d/.test(password)) {
                showMessage('registerError', 'Password must contain at least one number');
                return;
            }

            setLoading('registerBtn', true);

            try {
                const result = await api('/api/customer-register', {
                    method: 'POST',
                    body: JSON.stringify({ name, email, phone, address, password })
                });

                if (result && result.success) {
                    showMessage('registerSuccess', result.message || 'Registration successful! Redirecting to login...', false);
                    // Clear form
                    document.getElementById('registerForm').reset();
                    // Reset password strength indicator
                    checkPasswordStrength('');
                    // Redirect to login after 2 seconds
                    setTimeout(() => {
                        showLogin();
                        // Pre-fill login email
                        document.getElementById('email').value = email;
                        showMessage('loginError', 'Please login with your new credentials', false);
                    }, 2000);
                } else {
                    showMessage('registerError', result.message || 'Registration failed. Please try again.');
                }
            } catch (error) {
                showMessage('registerError', 'Network error. Please try again.');
            } finally {
                setLoading('registerBtn', false);
            }
        });

        function showRegister() {
            document.getElementById('loginView').classList.add('hidden');
            document.getElementById('registerView').classList.remove('hidden');
        }

        function showLogin() {
            document.getElementById('registerView').classList.add('hidden');
            document.getElementById('loginView').classList.remove('hidden');
        }

        function logout() {
            localStorage.removeItem('customer_token');
            location.reload();
        }

        async function loadData() {
            const [bookingsData, vehiclesData, servicesData] = await Promise.all([
                api('/api/customer/my-bookings'),
                api('/api/customer/my-vehicles'),
                api('/api/service-catalog')
            ]);

            if (bookingsData) renderBookings(bookingsData);
            if (vehiclesData) {
                vehicles = vehiclesData;
                renderVehicles();
            }
            if (servicesData) {
                services = servicesData;
                renderServices();
                renderServicesList();
            }
        }

        function renderBookings(bookings) {
            document.getElementById('bookingsTable').innerHTML = bookings.map(b => `
                <tr>
                    <td>${b.booking_date}</td>
                    <td>${b.booking_time}</td>
                    <td>${b.vehicle_info}</td>
                    <td>${b.service_name}</td>
                    <td>KSh ${b.price.toFixed(2)}</td>
                    <td>${b.technician_name}</td>
                    <td><span class="status-badge status-${b.status}">${b.status}</span></td>
                </tr>
            `).join('');
        }

        function renderVehicles() {
            document.getElementById('vehiclesTable').innerHTML = vehicles.map(v => `
                <tr>
                    <td>${v.make} ${v.model}</td>
                    <td>${v.year}</td>
                    <td><strong>${v.license_plate}</strong></td>
                    <td>${v.color || 'N/A'}</td>
                </tr>
            `).join('');
        }

        function renderServices() {
            document.getElementById('servicesTable').innerHTML = services.map(s => `
                <tr>
                    <td><strong>${s.service_name}</strong></td>
                    <td>${s.description || 'N/A'}</td>
                    <td>KSh ${s.base_price.toFixed(2)}</td>
                    <td>${s.estimated_duration}</td>
                    <td>${s.category}</td>
                </tr>
            `).join('');
        }

        function renderServicesList() {
            document.getElementById('servicesList').innerHTML = services.map(s => `
                <label style="display: block; margin: 10px 0;">
                    <input type="checkbox" value="${s.id}" onchange="toggleService(${s.id})">
                    ${s.service_name} - KSh ${s.base_price.toFixed(2)}
                </label>
            `).join('');
        }

        function toggleService(serviceId) {
            const index = selectedServices.indexOf(serviceId);
            if (index > -1) {
                selectedServices.splice(index, 1);
            } else {
                selectedServices.push(serviceId);
            }
        }

        async function calculateCost() {
            if (selectedServices.length === 0) {
                alert('Please select at least one service');
                return;
            }

            const result = await api('/api/cost-calculator', {
                method: 'POST',
                body: JSON.stringify({ service_ids: selectedServices })
            });

            if (result && result.success) {
                document.getElementById('calculatorResult').innerHTML = `
                    <div style="background: #f8f9fa; padding: 20px; border-radius: 5px;">
                        <h4>Cost Breakdown</h4>
                        ${result.breakdown.map(item => `
                            <div style="display: flex; justify-content: space-between; margin: 10px 0;">
                                <span>${item.name}</span>
                                <span>KSh ${item.price.toFixed(2)}</span>
                            </div>
                        `).join('')}
                        <hr style="margin: 15px 0;">
                        <div style="display: flex; justify-content: space-between;">
                            <span>Subtotal:</span>
                            <span>KSh ${result.subtotal.toFixed(2)}</span>
                        </div>
                        <div style="display: flex; justify-content: space-between;">
                            <span>Tax (16% VAT):</span>
                            <span>KSh ${result.tax.toFixed(2)}</span>
                        </div>
                        <div style="display: flex; justify-content: space-between; font-weight: bold; font-size: 18px; margin-top: 10px;">
                            <span>Total:</span>
                            <span>KSh ${result.total.toFixed(2)}</span>
                        </div>
                    </div>
                `;
            }
        }

        function showBookingForm() {
            document.getElementById('modalContent').innerHTML = `
                <h2>New Booking</h2>
                <form id="bookingForm">
                    <div class="form-group">
                        <label>Vehicle *</label>
                        <select name="vehicle_id" required>
                            <option value="">Select Vehicle</option>
                            ${vehicles.map(v => `<option value="${v.id}">${v.make} ${v.model} (${v.license_plate})</option>`).join('')}
                        </select>
                    </div>
                    <div class="form-group">
                        <label>Service *</label>
                        <select name="service_catalog_id" required>
                            <option value="">Select Service</option>
                            ${services.map(s => `<option value="${s.id}">${s.service_name} - KSh ${s.base_price}</option>`).join('')}
                        </select>
                    </div>
                    <div class="form-group">
                        <label>Date *</label>
                        <input type="date" name="booking_date" required>
                    </div>
                    <div class="form-group">
                        <label>Time *</label>
                        <input type="time" name="booking_time" required>
                    </div>
                    <div class="form-group">
                        <label>Notes</label>
                        <textarea name="notes" rows="3"></textarea>
                    </div>
                    <div class="form-actions">
                        <button type="button" class="btn" onclick="closeModal()">Cancel</button>
                        <button type="submit" class="btn btn-primary">Book Appointment</button>
                    </div>
                </form>
            `;
            document.getElementById('bookingForm').addEventListener('submit', async (e) => {
                e.preventDefault();
                const formData = new FormData(e.target);
                const data = Object.fromEntries(formData);
                // We need to get customer_id from the session somehow
                alert('Booking feature requires customer ID integration. Please contact staff to make a booking.');
                closeModal();
            });
            document.getElementById('modal').classList.add('active');
        }

        function closeModal() {
            document.getElementById('modal').classList.remove('active');
        }

        if (token) {
            document.getElementById('loginView').classList.add('hidden');
            document.getElementById('mainView').classList.remove('hidden');
            loadData();
        }
    </script>
</body>
</html>'''
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.send_security_headers()
        self.end_headers()
        self.wfile.write(html.encode())

    def handle_dashboard(self):
        self.handle_stats()

    def handle_health_check(self):
        """Health check endpoint for monitoring"""
        try:
            # Check database connection
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM users')
            cursor.fetchone()
            conn.close()

            # Clean up expired sessions
            cleaned = cleanup_expired_sessions()

            health_data = {
                'status': 'healthy',
                'timestamp': datetime.now().isoformat(),
                'database': 'connected',
                'sessions_cleaned': cleaned,
                'version': '2.0.0',
                'environment': 'production' if PRODUCTION else 'development'
            }
            self.send_json_response(health_data)
        except Exception as e:
            health_data = {
                'status': 'unhealthy',
                'timestamp': datetime.now().isoformat(),
                'error': str(e)
            }
            self.send_json_response(health_data, 503)

    def send_security_headers(self):
        """Send security headers for production"""
        # CORS - restrict in production
        origin = ALLOWED_ORIGINS[0] if PRODUCTION and ALLOWED_ORIGINS[0] != '*' else '*'
        self.send_header('Access-Control-Allow-Origin', origin)

        # Security headers
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('X-Frame-Options', 'DENY')
        self.send_header('X-XSS-Protection', '1; mode=block')
        self.send_header('Referrer-Policy', 'strict-origin-when-cross-origin')

        # CSP - Content Security Policy
        csp = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; "
            "font-src 'self'; "
            "connect-src 'self'; "
            "frame-ancestors 'none';"
        )
        self.send_header('Content-Security-Policy', csp)

        # HSTS - only in production with HTTPS
        if PRODUCTION:
            self.send_header('Strict-Transport-Security', 'max-age=31536000; includeSubDomains')

    def send_json_response(self, data, status=200):
        self.send_response(status)
        self.send_header('Content-type', 'application/json')
        self.send_security_headers()
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def log_message(self, format, *args):
        # Simplified logging
        return

if __name__ == '__main__':
    print("=" * 60)
    print("🔧 GARAGE MANAGEMENT SYSTEM")
    print("=" * 60)
    print(f"\n📊 Initializing database...")
    init_database()
    print(f"\n🚀 Starting server on http://localhost:{PORT}")
    print(f"\n🔐 Default Login:")
    print(f"   Username: admin")
    print(f"   Password: admin123")
    print(f"\n🌐 Open your browser and navigate to:")
    print(f"   http://localhost:{PORT}")
    print("\n✅ Server is running... Press Ctrl+C to stop\n")
    print("=" * 60 + "\n")

    Handler = GarageRequestHandler
    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n\n👋 Shutting down server...")
            print("=" * 60)
