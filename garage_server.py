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

PORT = 5000
DB_FILE = 'garage_management.db'

# Security configuration
PASSWORD_ITERATIONS = 100000  # PBKDF2 iterations
SESSION_INACTIVITY_TIMEOUT = 30  # minutes
MAX_INPUT_LENGTH = 500  # characters

# Password hashing with PBKDF2
def hash_password(password, salt=None):
    """Hash password using PBKDF2 with SHA256"""
    if salt is None:
        salt = secrets.token_bytes(32)
    elif isinstance(salt, str):
        salt = bytes.fromhex(salt)

    key = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, PASSWORD_ITERATIONS)
    return salt.hex() + ':' + key.hex()

def verify_password(stored_password, provided_password):
    """Verify a password against a stored hash"""
    try:
        salt_hex, key_hex = stored_password.split(':')
        salt = bytes.fromhex(salt_hex)
        stored_key = bytes.fromhex(key_hex)

        new_key = hashlib.pbkdf2_hmac('sha256', provided_password.encode(), salt, PASSWORD_ITERATIONS)
        return secrets.compare_digest(stored_key, new_key)
    except:
        return False

# Input sanitization
def sanitize_input(text, max_length=MAX_INPUT_LENGTH):
    """Sanitize user input to prevent XSS and limit length"""
    if text is None:
        return ''
    text = str(text)[:max_length]
    # Escape HTML special characters
    text = text.replace('&', '&amp;')
    text = text.replace('<', '&lt;')
    text = text.replace('>', '&gt;')
    text = text.replace('"', '&quot;')
    text = text.replace("'", '&#x27;')
    text = text.replace('/', '&#x2F;')
    return text.strip()

def validate_email(email):
    """Basic email validation"""
    import re
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

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
            last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            username TEXT,
            action TEXT NOT NULL,
            entity_type TEXT,
            entity_id INTEGER,
            details TEXT,
            ip_address TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
        )
    ''')

    # Add sample data if database is empty
    cursor.execute('SELECT COUNT(*) FROM customers')
    if cursor.fetchone()[0] == 0:
        # Add admin user with secure random password
        admin_password = secrets.token_urlsafe(16)
        password_hash = hash_password(admin_password)
        cursor.execute('INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)',
                      ('admin', password_hash, 'admin'))

        # Store the initial password to display once
        with open('.initial_admin_password.txt', 'w') as f:
            f.write(f"Initial Admin Password: {admin_password}\n")
            f.write("IMPORTANT: Save this password securely and delete this file!\n")
            f.write("You can change this password after first login.\n")

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

    conn.commit()
    conn.close()
    print(f"✅ Database initialized: {DB_FILE}")

# Audit logging
def log_audit(user_id, username, action, entity_type=None, entity_id=None, details=None, ip_address=None):
    """Log security and data events"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO audit_log (user_id, username, action, entity_type, entity_id, details, ip_address)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (user_id, username, action, entity_type, entity_id, details, ip_address))
    conn.commit()
    conn.close()

# Authentication helpers
def create_session(user_id):
    """Create a new session token for a user"""
    token = secrets.token_urlsafe(32)
    expires_at = datetime.now() + timedelta(hours=24)
    last_activity = datetime.now()
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('INSERT INTO sessions (user_id, token, expires_at, last_activity) VALUES (?, ?, ?, ?)',
                  (user_id, token, expires_at.isoformat(), last_activity.isoformat()))
    conn.commit()
    conn.close()
    return token

def verify_session(token):
    """Verify session token and check for inactivity timeout"""
    if not token:
        return None
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT u.id, u.username, u.role, s.last_activity, s.id
        FROM sessions s
        JOIN users u ON s.user_id = u.id
        WHERE s.token = ? AND s.expires_at > ?
    ''', (token, datetime.now().isoformat()))
    result = cursor.fetchone()

    if not result:
        conn.close()
        return None

    user_id, username, role, last_activity_str, session_id = result

    # Check inactivity timeout
    last_activity = datetime.fromisoformat(last_activity_str)
    inactivity_delta = datetime.now() - last_activity
    if inactivity_delta > timedelta(minutes=SESSION_INACTIVITY_TIMEOUT):
        # Session expired due to inactivity
        cursor.execute('DELETE FROM sessions WHERE id = ?', (session_id,))
        conn.commit()
        conn.close()
        return None

    # Update last activity
    cursor.execute('UPDATE sessions SET last_activity = ? WHERE id = ?',
                  (datetime.now().isoformat(), session_id))
    conn.commit()
    conn.close()

    return {'id': user_id, 'username': username, 'role': role}

def logout_all_sessions(user_id):
    """Logout user from all sessions"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM sessions WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()

def check_permission(user_role, required_role):
    """Check if user has required permissions"""
    role_hierarchy = {'admin': 2, 'staff': 1}
    return role_hierarchy.get(user_role, 0) >= role_hierarchy.get(required_role, 0)

# Request handler
class GarageRequestHandler(http.server.SimpleHTTPRequestHandler):

    def get_user_from_request(self):
        """Extract and verify user session from request"""
        token = self.headers.get('Authorization')
        return verify_session(token)

    def require_auth(self, required_role=None):
        """Require authentication and optionally check role"""
        user = self.get_user_from_request()
        if not user:
            self.send_json_response({'success': False, 'message': 'Unauthorized'}, 401)
            return None
        if required_role and not check_permission(user['role'], required_role):
            self.send_json_response({'success': False, 'message': 'Insufficient permissions'}, 403)
            return None
        return user

    def do_GET(self):
        if self.path == '/' or self.path == '/index.html':
            self.serve_frontend()
        elif self.path.startswith('/api/dashboard'):
            if self.require_auth():
                self.handle_dashboard()
        elif self.path.startswith('/api/customers'):
            if self.require_auth():
                self.handle_get_customers()
        elif self.path.startswith('/api/vehicles'):
            if self.require_auth():
                self.handle_get_vehicles()
        elif self.path.startswith('/api/services'):
            if self.require_auth():
                self.handle_get_services()
        elif self.path.startswith('/api/stats'):
            if self.require_auth():
                self.handle_stats()
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
        elif self.path == '/api/logout':
            self.handle_logout()
        elif self.path == '/api/logout_all':
            self.handle_logout_all()
        elif self.path == '/api/customers':
            user = self.require_auth()
            if user:
                self.handle_add_customer(data, user)
        elif self.path == '/api/vehicles':
            user = self.require_auth()
            if user:
                self.handle_add_vehicle(data, user)
        elif self.path == '/api/services':
            user = self.require_auth()
            if user:
                self.handle_add_service(data, user)
        else:
            self.send_error(404, 'Not Found')

    def do_PUT(self):
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length).decode('utf-8') if content_length > 0 else '{}'

        try:
            data = json.loads(body) if body else {}
        except:
            data = {}

        user = self.require_auth()
        if not user:
            return

        if self.path.startswith('/api/customers/'):
            customer_id = self.path.split('/')[-1]
            self.handle_update_customer(customer_id, data, user)
        elif self.path.startswith('/api/vehicles/'):
            vehicle_id = self.path.split('/')[-1]
            self.handle_update_vehicle(vehicle_id, data, user)
        elif self.path.startswith('/api/services/'):
            service_id = self.path.split('/')[-1]
            self.handle_update_service(service_id, data, user)
        else:
            self.send_error(404, 'Not Found')

    def do_DELETE(self):
        # Only admins can delete records
        user = self.require_auth('admin')
        if not user:
            return

        if self.path.startswith('/api/customers/'):
            customer_id = self.path.split('/')[-1]
            self.handle_delete_customer(customer_id, user)
        elif self.path.startswith('/api/vehicles/'):
            vehicle_id = self.path.split('/')[-1]
            self.handle_delete_vehicle(vehicle_id, user)
        elif self.path.startswith('/api/services/'):
            service_id = self.path.split('/')[-1]
            self.handle_delete_service(service_id, user)
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
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        .container { max-width: 1400px; margin: 0 auto; }
        .header {
            background: white;
            padding: 20px 30px;
            border-radius: 10px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            margin-bottom: 30px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .header h1 { color: #667eea; font-size: 28px; }
        .stats {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        .stat-card {
            background: white;
            padding: 25px;
            border-radius: 10px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }
        .stat-card h3 { color: #666; font-size: 14px; margin-bottom: 10px; }
        .stat-card .value { font-size: 36px; font-weight: bold; color: #667eea; }
        .content {
            background: white;
            padding: 30px;
            border-radius: 10px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
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
            transition: all 0.3s;
        }
        .tab.active {
            color: #667eea;
            border-bottom-color: #667eea;
        }
        .tab-content { display: none; }
        .tab-content.active { display: block; }
        table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 20px;
        }
        th, td {
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #eee;
        }
        th {
            background: #f8f9fa;
            font-weight: 600;
            color: #333;
        }
        tr:hover { background: #f8f9fa; }
        .btn {
            padding: 10px 20px;
            border: none;
            border-radius: 5px;
            cursor: pointer;
            font-size: 14px;
            transition: all 0.3s;
        }
        .btn-primary {
            background: #667eea;
            color: white;
        }
        .btn-primary:hover { background: #5568d3; }
        .btn-success {
            background: #27ae60;
            color: white;
        }
        .btn-danger {
            background: #e74c3c;
            color: white;
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
            background: rgba(0,0,0,0.5);
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
        }
        .modal-content h2 { margin-bottom: 20px; color: #667eea; }
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
        }
        .form-group textarea { min-height: 100px; }
        .form-actions {
            display: flex;
            gap: 10px;
            justify-content: flex-end;
            margin-top: 20px;
        }
        .login-container {
            max-width: 400px;
            margin: 100px auto;
            background: white;
            padding: 40px;
            border-radius: 10px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }
        .login-container h2 {
            color: #667eea;
            margin-bottom: 30px;
            text-align: center;
        }
        .hidden { display: none !important; }
    </style>
</head>
<body>
    <div id="loginView" class="login-container">
        <h2>🔧 Garage Management System</h2>
        <form id="loginForm">
            <div class="form-group">
                <label>Username</label>
                <input type="text" id="username" required autofocus>
            </div>
            <div class="form-group">
                <label>Password</label>
                <input type="password" id="password" required>
            </div>
            <div id="loginError" style="color: red; margin-top: 10px; display: none;"></div>
            <button type="submit" class="btn btn-primary" style="width: 100%; margin-top: 10px;">Login</button>
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
            </div>

            <div id="customersTab" class="tab-content active">
                <button class="btn btn-primary" onclick="showAddCustomer()">+ Add Customer</button>
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

            <div id="vehiclesTab" class="tab-content">
                <button class="btn btn-primary" onclick="showAddVehicle()">+ Add Vehicle</button>
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

            <div id="servicesTab" class="tab-content">
                <button class="btn btn-primary" onclick="showAddService()">+ Add Service</button>
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
    </div>

    <div id="modal" class="modal">
        <div class="modal-content" id="modalContent"></div>
    </div>

    <script>
        let token = localStorage.getItem('token');
        let userRole = localStorage.getItem('userRole') || 'staff';
        let customers = [];
        let vehicles = [];
        let services = [];

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
            const loginError = document.getElementById('loginError');

            const result = await api('/api/login', {
                method: 'POST',
                body: JSON.stringify({ username, password })
            });

            if (result && result.success) {
                token = result.token;
                userRole = result.role || 'staff';
                localStorage.setItem('token', token);
                localStorage.setItem('userRole', userRole);
                document.getElementById('loginView').classList.add('hidden');
                document.getElementById('mainView').classList.remove('hidden');
                loadData();
            } else {
                loginError.textContent = result?.message || 'Login failed. Please check your credentials.';
                loginError.style.display = 'block';
                document.getElementById('password').value = '';
            }
        });

        async function logout() {
            await api('/api/logout', { method: 'POST' });
            localStorage.removeItem('token');
            localStorage.removeItem('userRole');
            location.reload();
        }

        async function loadData() {
            const [statsData, customersData, vehiclesData, servicesData] = await Promise.all([
                api('/api/stats'),
                api('/api/customers'),
                api('/api/vehicles'),
                api('/api/services')
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
                    <div class="value">$${stats.total_revenue.toFixed(2)}</div>
                </div>
            `;
        }

        function renderCustomers() {
            const deleteBtn = (id) => userRole === 'admin'
                ? `<button class="btn btn-sm btn-danger" onclick="deleteCustomer(${id})">Delete</button>`
                : '';
            document.getElementById('customersTable').innerHTML = customers.map(c => `
                <tr>
                    <td>${c.name}</td>
                    <td>${c.email}</td>
                    <td>${c.phone}</td>
                    <td>${c.address || 'N/A'}</td>
                    <td>
                        <button class="btn btn-sm btn-primary" onclick="editCustomer(${c.id})">Edit</button>
                        ${deleteBtn(c.id)}
                    </td>
                </tr>
            `).join('');
        }

        function renderVehicles() {
            const deleteBtn = (id) => userRole === 'admin'
                ? `<button class="btn btn-sm btn-danger" onclick="deleteVehicle(${id})">Delete</button>`
                : '';
            document.getElementById('vehiclesTable').innerHTML = vehicles.map(v => `
                <tr>
                    <td>${v.owner_name}</td>
                    <td>${v.make} ${v.model}</td>
                    <td>${v.year}</td>
                    <td>${v.license_plate}</td>
                    <td>${v.color || 'N/A'}</td>
                    <td>
                        <button class="btn btn-sm btn-primary" onclick="editVehicle(${v.id})">Edit</button>
                        ${deleteBtn(v.id)}
                    </td>
                </tr>
            `).join('');
        }

        function renderServices() {
            const deleteBtn = (id) => userRole === 'admin'
                ? `<button class="btn btn-sm btn-danger" onclick="deleteService(${id})">Delete</button>`
                : '';
            document.getElementById('servicesTable').innerHTML = services.map(s => `
                <tr>
                    <td>${s.vehicle_info}</td>
                    <td>${s.service_type}</td>
                    <td>$${s.cost.toFixed(2)}</td>
                    <td><span class="status-badge status-${s.status}">${s.status.replace('_', ' ')}</span></td>
                    <td>${s.technician || 'Unassigned'}</td>
                    <td>${new Date(s.service_date).toLocaleDateString()}</td>
                    <td>
                        <button class="btn btn-sm btn-primary" onclick="editService(${s.id})">Edit</button>
                        ${deleteBtn(s.id)}
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
                } else {
                    alert(result?.message || 'Failed to update customer');
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
                } else {
                    alert(result?.message || 'Failed to update vehicle');
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
                            ${vehicles.map(v => `<option value="${v.id}" ${v.id === service.vehicle_id ? 'selected' : ''}>${v.owner_name} - ${v.make} ${v.model} (${v.license_plate})</option>`).join('')}
                        </select>
                    </div>
                    <div class="form-group">
                        <label>Service Type *</label>
                        <input type="text" name="service_type" value="${service.service_type}" required>
                    </div>
                    <div class="form-group">
                        <label>Description</label>
                        <textarea name="description">${service.description || ''}</textarea>
                    </div>
                    <div class="form-group">
                        <label>Cost *</label>
                        <input type="number" name="cost" step="0.01" value="${service.cost}" required>
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
                        <textarea name="notes">${service.notes || ''}</textarea>
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
                } else {
                    alert(result?.message || 'Failed to update service');
                }
            });
            document.getElementById('modal').classList.add('active');
        }

        async function deleteCustomer(id) {
            const customer = customers.find(c => c.id === id);
            const customerName = customer ? customer.name : 'this customer';
            if (confirm(`Delete ${customerName} and all associated vehicles/services?`)) {
                const result = await api(`/api/customers/${id}`, { method: 'DELETE' });
                if (result && result.success) {
                    loadData();
                } else {
                    alert(result?.message || 'Failed to delete customer');
                }
            }
        }

        async function deleteVehicle(id) {
            const vehicle = vehicles.find(v => v.id === id);
            const vehicleInfo = vehicle ? `${vehicle.make} ${vehicle.model} (${vehicle.license_plate})` : 'this vehicle';
            if (confirm(`Delete ${vehicleInfo} and all associated services?`)) {
                const result = await api(`/api/vehicles/${id}`, { method: 'DELETE' });
                if (result && result.success) {
                    loadData();
                } else {
                    alert(result?.message || 'Failed to delete vehicle');
                }
            }
        }

        async function deleteService(id) {
            const service = services.find(s => s.id === id);
            const serviceInfo = service ? service.service_type : 'this service';
            if (confirm(`Delete ${serviceInfo}?`)) {
                const result = await api(`/api/services/${id}`, { method: 'DELETE' });
                if (result && result.success) {
                    loadData();
                } else {
                    alert(result?.message || 'Failed to delete service');
                }
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
        self.end_headers()
        self.wfile.write(html.encode())

    def handle_login(self, data):
        username = sanitize_input(data.get('username', ''), 100)
        password = data.get('password', '')

        if not username or not password:
            self.send_json_response({'success': False, 'message': 'Username and password required'}, 400)
            return

        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('SELECT id, password_hash, role FROM users WHERE username = ?', (username,))
        user = cursor.fetchone()
        conn.close()

        if user and verify_password(user[1], password):
            user_id = user[0]
            token = create_session(user_id)
            log_audit(user_id, username, 'login', ip_address=self.client_address[0])
            self.send_json_response({'success': True, 'token': token, 'role': user[2]})
        else:
            log_audit(None, username, 'failed_login', details='Invalid credentials', ip_address=self.client_address[0])
            self.send_json_response({'success': False, 'message': 'Invalid credentials'}, 401)

    def handle_logout(self):
        user = self.get_user_from_request()
        if user:
            token = self.headers.get('Authorization')
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute('DELETE FROM sessions WHERE token = ?', (token,))
            conn.commit()
            conn.close()
            log_audit(user['id'], user['username'], 'logout', ip_address=self.client_address[0])
            self.send_json_response({'success': True})
        else:
            self.send_json_response({'success': False}, 401)

    def handle_logout_all(self):
        user = self.get_user_from_request()
        if user:
            logout_all_sessions(user['id'])
            log_audit(user['id'], user['username'], 'logout_all', ip_address=self.client_address[0])
            self.send_json_response({'success': True})
        else:
            self.send_json_response({'success': False}, 401)

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

    def handle_add_customer(self, data, user):
        try:
            # Sanitize and validate inputs
            name = sanitize_input(data.get('name', ''))
            email = sanitize_input(data.get('email', ''))
            phone = sanitize_input(data.get('phone', ''))
            address = sanitize_input(data.get('address', ''))

            if not name or not email or not phone:
                self.send_json_response({'success': False, 'message': 'Name, email, and phone are required'}, 400)
                return

            if not validate_email(email):
                self.send_json_response({'success': False, 'message': 'Invalid email format'}, 400)
                return

            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute('''INSERT INTO customers (name, email, phone, address) VALUES (?, ?, ?, ?)''',
                          (name, email, phone, address))
            conn.commit()
            customer_id = cursor.lastrowid
            conn.close()

            log_audit(user['id'], user['username'], 'create', 'customer', customer_id,
                     f"Created customer: {name}", self.client_address[0])
            self.send_json_response({'success': True, 'id': customer_id})
        except sqlite3.IntegrityError as e:
            self.send_json_response({'success': False, 'message': 'Email already exists'}, 400)
        except Exception as e:
            self.send_json_response({'success': False, 'message': 'Failed to create customer'}, 400)

    def handle_add_vehicle(self, data, user):
        try:
            # Sanitize and validate inputs
            customer_id = int(data.get('customer_id', 0))
            make = sanitize_input(data.get('make', ''))
            model = sanitize_input(data.get('model', ''))
            year = int(data.get('year', 0))
            license_plate = sanitize_input(data.get('license_plate', ''))
            vin = sanitize_input(data.get('vin', ''))
            color = sanitize_input(data.get('color', ''))

            if not customer_id or not make or not model or not year or not license_plate:
                self.send_json_response({'success': False, 'message': 'Required fields missing'}, 400)
                return

            if year < 1900 or year > 2100:
                self.send_json_response({'success': False, 'message': 'Invalid year'}, 400)
                return

            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO vehicles (customer_id, make, model, year, license_plate, vin, color)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (customer_id, make, model, year, license_plate, vin, color))
            conn.commit()
            vehicle_id = cursor.lastrowid
            conn.close()

            log_audit(user['id'], user['username'], 'create', 'vehicle', vehicle_id,
                     f"Created vehicle: {make} {model} ({license_plate})", self.client_address[0])
            self.send_json_response({'success': True, 'id': vehicle_id})
        except sqlite3.IntegrityError:
            self.send_json_response({'success': False, 'message': 'License plate already exists'}, 400)
        except ValueError:
            self.send_json_response({'success': False, 'message': 'Invalid data format'}, 400)
        except Exception as e:
            self.send_json_response({'success': False, 'message': 'Failed to create vehicle'}, 400)

    def handle_add_service(self, data, user):
        try:
            # Sanitize and validate inputs
            vehicle_id = int(data.get('vehicle_id', 0))
            service_type = sanitize_input(data.get('service_type', ''))
            description = sanitize_input(data.get('description', ''))
            cost = float(data.get('cost', 0))
            status = sanitize_input(data.get('status', 'pending'))
            technician = sanitize_input(data.get('technician', ''))
            notes = sanitize_input(data.get('notes', ''))

            if not vehicle_id or not service_type or cost < 0:
                self.send_json_response({'success': False, 'message': 'Required fields missing or invalid'}, 400)
                return

            if status not in ['pending', 'in_progress', 'completed']:
                status = 'pending'

            # Auto-set completed_date if status is completed
            completed_date = datetime.now().isoformat() if status == 'completed' else None

            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO services (vehicle_id, service_type, description, cost, status, technician, notes, completed_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (vehicle_id, service_type, description, cost, status, technician, notes, completed_date))
            conn.commit()
            service_id = cursor.lastrowid
            conn.close()

            log_audit(user['id'], user['username'], 'create', 'service', service_id,
                     f"Created service: {service_type}", self.client_address[0])
            self.send_json_response({'success': True, 'id': service_id})
        except ValueError:
            self.send_json_response({'success': False, 'message': 'Invalid data format'}, 400)
        except Exception as e:
            self.send_json_response({'success': False, 'message': 'Failed to create service'}, 400)

    def handle_update_customer(self, customer_id, data, user):
        try:
            # Sanitize and validate inputs
            name = sanitize_input(data.get('name', ''))
            email = sanitize_input(data.get('email', ''))
            phone = sanitize_input(data.get('phone', ''))
            address = sanitize_input(data.get('address', ''))

            if not name or not email or not phone:
                self.send_json_response({'success': False, 'message': 'Name, email, and phone are required'}, 400)
                return

            if not validate_email(email):
                self.send_json_response({'success': False, 'message': 'Invalid email format'}, 400)
                return

            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE customers SET name = ?, email = ?, phone = ?, address = ?
                WHERE id = ?
            ''', (name, email, phone, address, customer_id))
            conn.commit()
            conn.close()

            log_audit(user['id'], user['username'], 'update', 'customer', customer_id,
                     f"Updated customer: {name}", self.client_address[0])
            self.send_json_response({'success': True})
        except sqlite3.IntegrityError:
            self.send_json_response({'success': False, 'message': 'Email already exists'}, 400)
        except Exception as e:
            self.send_json_response({'success': False, 'message': 'Failed to update customer'}, 400)

    def handle_update_vehicle(self, vehicle_id, data, user):
        try:
            # Sanitize and validate inputs
            customer_id = int(data.get('customer_id', 0))
            make = sanitize_input(data.get('make', ''))
            model = sanitize_input(data.get('model', ''))
            year = int(data.get('year', 0))
            license_plate = sanitize_input(data.get('license_plate', ''))
            vin = sanitize_input(data.get('vin', ''))
            color = sanitize_input(data.get('color', ''))

            if not customer_id or not make or not model or not year or not license_plate:
                self.send_json_response({'success': False, 'message': 'Required fields missing'}, 400)
                return

            if year < 1900 or year > 2100:
                self.send_json_response({'success': False, 'message': 'Invalid year'}, 400)
                return

            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE vehicles SET customer_id = ?, make = ?, model = ?, year = ?,
                                   license_plate = ?, vin = ?, color = ?
                WHERE id = ?
            ''', (customer_id, make, model, year, license_plate, vin, color, vehicle_id))
            conn.commit()
            conn.close()

            log_audit(user['id'], user['username'], 'update', 'vehicle', vehicle_id,
                     f"Updated vehicle: {make} {model} ({license_plate})", self.client_address[0])
            self.send_json_response({'success': True})
        except sqlite3.IntegrityError:
            self.send_json_response({'success': False, 'message': 'License plate already exists'}, 400)
        except ValueError:
            self.send_json_response({'success': False, 'message': 'Invalid data format'}, 400)
        except Exception as e:
            self.send_json_response({'success': False, 'message': 'Failed to update vehicle'}, 400)

    def handle_update_service(self, service_id, data, user):
        try:
            # Sanitize and validate inputs
            vehicle_id = int(data.get('vehicle_id', 0))
            service_type = sanitize_input(data.get('service_type', ''))
            description = sanitize_input(data.get('description', ''))
            cost = float(data.get('cost', 0))
            status = sanitize_input(data.get('status', 'pending'))
            technician = sanitize_input(data.get('technician', ''))
            notes = sanitize_input(data.get('notes', ''))

            if not vehicle_id or not service_type or cost < 0:
                self.send_json_response({'success': False, 'message': 'Required fields missing or invalid'}, 400)
                return

            if status not in ['pending', 'in_progress', 'completed']:
                status = 'pending'

            # Auto-set completed_date if status changed to completed
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute('SELECT status FROM services WHERE id = ?', (service_id,))
            old_status = cursor.fetchone()

            completed_date = None
            if status == 'completed' and (not old_status or old_status[0] != 'completed'):
                completed_date = datetime.now().isoformat()

            cursor.execute('''
                UPDATE services SET vehicle_id = ?, service_type = ?, description = ?,
                                   cost = ?, status = ?, technician = ?, notes = ?
                WHERE id = ?
            ''', (vehicle_id, service_type, description, cost, status, technician, notes, service_id))

            if completed_date:
                cursor.execute('UPDATE services SET completed_date = ? WHERE id = ?',
                             (completed_date, service_id))

            conn.commit()
            conn.close()

            log_audit(user['id'], user['username'], 'update', 'service', service_id,
                     f"Updated service: {service_type} (status: {status})", self.client_address[0])
            self.send_json_response({'success': True})
        except ValueError:
            self.send_json_response({'success': False, 'message': 'Invalid data format'}, 400)
        except Exception as e:
            self.send_json_response({'success': False, 'message': 'Failed to update service'}, 400)

    def handle_delete_customer(self, customer_id, user):
        try:
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()

            # Get customer name for audit log
            cursor.execute('SELECT name FROM customers WHERE id = ?', (customer_id,))
            customer = cursor.fetchone()
            customer_name = customer[0] if customer else 'Unknown'

            cursor.execute('DELETE FROM customers WHERE id = ?', (customer_id,))
            conn.commit()
            conn.close()

            log_audit(user['id'], user['username'], 'delete', 'customer', customer_id,
                     f"Deleted customer: {customer_name}", self.client_address[0])
            self.send_json_response({'success': True})
        except Exception as e:
            self.send_json_response({'success': False, 'message': 'Failed to delete customer'}, 400)

    def handle_delete_vehicle(self, vehicle_id, user):
        try:
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()

            # Get vehicle info for audit log
            cursor.execute('SELECT make, model, license_plate FROM vehicles WHERE id = ?', (vehicle_id,))
            vehicle = cursor.fetchone()
            vehicle_info = f"{vehicle[0]} {vehicle[1]} ({vehicle[2]})" if vehicle else 'Unknown'

            cursor.execute('DELETE FROM vehicles WHERE id = ?', (vehicle_id,))
            conn.commit()
            conn.close()

            log_audit(user['id'], user['username'], 'delete', 'vehicle', vehicle_id,
                     f"Deleted vehicle: {vehicle_info}", self.client_address[0])
            self.send_json_response({'success': True})
        except Exception as e:
            self.send_json_response({'success': False, 'message': 'Failed to delete vehicle'}, 400)

    def handle_delete_service(self, service_id, user):
        try:
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()

            # Get service info for audit log
            cursor.execute('SELECT service_type FROM services WHERE id = ?', (service_id,))
            service = cursor.fetchone()
            service_type = service[0] if service else 'Unknown'

            cursor.execute('DELETE FROM services WHERE id = ?', (service_id,))
            conn.commit()
            conn.close()

            log_audit(user['id'], user['username'], 'delete', 'service', service_id,
                     f"Deleted service: {service_type}", self.client_address[0])
            self.send_json_response({'success': True})
        except Exception as e:
            self.send_json_response({'success': False, 'message': 'Failed to delete service'}, 400)

    def handle_dashboard(self):
        self.handle_stats()

    def send_json_response(self, data, status=200):
        self.send_response(status)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
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
    print(f"\n🔐 Login Information:")
    print(f"   Username: admin")

    # Check if initial password file exists
    if os.path.exists('.initial_admin_password.txt'):
        with open('.initial_admin_password.txt', 'r') as f:
            password_line = f.readline().strip()
            password = password_line.split(': ')[1] if ': ' in password_line else 'See .initial_admin_password.txt'
        print(f"   Password: {password}")
        print(f"\n⚠️  IMPORTANT: This is a one-time generated password!")
        print(f"   Save it securely and delete .initial_admin_password.txt")
    else:
        print(f"   Password: (use previously set password)")

    print(f"\n🌐 Open your browser and navigate to:")
    print(f"   http://localhost:{PORT}")
    print(f"\n🔒 Security Features:")
    print(f"   - PBKDF2 password hashing with salt")
    print(f"   - {SESSION_INACTIVITY_TIMEOUT}-minute session inactivity timeout")
    print(f"   - Role-based access control (RBAC)")
    print(f"   - Input sanitization and validation")
    print(f"   - Comprehensive audit logging")
    print("\n✅ Server is running... Press Ctrl+C to stop\n")
    print("=" * 60 + "\n")

    Handler = GarageRequestHandler
    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n\n👋 Shutting down server...")
            print("=" * 60)
