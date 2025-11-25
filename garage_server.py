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

    # Add sample data if database is empty
    cursor.execute('SELECT COUNT(*) FROM customers')
    if cursor.fetchone()[0] == 0:
        # Add admin user
        password_hash = hashlib.sha256('admin123'.encode()).hexdigest()
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

# Request handler
class GarageRequestHandler(http.server.SimpleHTTPRequestHandler):

    def do_GET(self):
        if self.path == '/' or self.path == '/index.html':
            self.serve_frontend()
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
        elif self.path == '/api/customers':
            self.handle_add_customer(data)
        elif self.path == '/api/vehicles':
            self.handle_add_vehicle(data)
        elif self.path == '/api/services':
            self.handle_add_service(data)
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
        username = data.get('username')
        password = data.get('password')
        password_hash = hashlib.sha256(password.encode()).hexdigest()

        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('SELECT id FROM users WHERE username = ? AND password_hash = ?',
                      (username, password_hash))
        user = cursor.fetchone()
        conn.close()

        if user:
            token = create_session(user[0])
            self.send_json_response({'success': True, 'token': token})
        else:
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
