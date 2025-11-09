// API Configuration
const API_URL = 'http://localhost:5000/api';
let authToken = null;
let currentUser = null;

// ==================== UTILITY FUNCTIONS ====================

// Show/hide loading spinner on buttons
function setButtonLoading(buttonId, isLoading) {
    const btn = document.getElementById(buttonId);
    const btnText = btn.querySelector('.btn-text');
    const spinner = btn.querySelector('.loading-spinner');
    
    if (isLoading) {
        btn.disabled = true;
        btnText.classList.add('hidden');
        spinner.classList.remove('hidden');
    } else {
        btn.disabled = false;
        btnText.classList.remove('hidden');
        spinner.classList.add('hidden');
    }
}

// Show alert message
function showAlert(elementId, message, type = 'danger') {
    const alertElement = document.getElementById(elementId);
    alertElement.innerHTML = `
        <div class="alert alert-${type} alert-dismissible fade show" role="alert">
            <i class="fas fa-${type === 'success' ? 'check-circle' : type === 'warning' ? 'exclamation-triangle' : 'exclamation-circle'} me-2"></i>
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        </div>
    `;
    
    // Auto dismiss after 5 seconds
    setTimeout(() => {
        const alert = alertElement.querySelector('.alert');
        if (alert) {
            const bsAlert = new bootstrap.Alert(alert);
            bsAlert.close();
        }
    }, 5000);
}

// Clear all alerts
function clearAlerts() {
    const alertElements = document.querySelectorAll('[id$="-alert"]');
    alertElements.forEach(el => el.innerHTML = '');
}

// Validate field and show feedback
function validateField(input, isValid, errorMessage = '') {
    const feedback = input.parentElement.querySelector('.invalid-feedback') || 
                    input.closest('.form-group').querySelector('.invalid-feedback');
    
    if (isValid) {
        input.classList.remove('is-invalid');
        input.classList.add('is-valid');
        if (feedback) feedback.textContent = '';
    } else {
        input.classList.remove('is-valid');
        input.classList.add('is-invalid');
        if (feedback) feedback.textContent = errorMessage;
    }
}

// Clear field validation
function clearFieldValidation(input) {
    input.classList.remove('is-valid', 'is-invalid');
    const feedback = input.parentElement.querySelector('.invalid-feedback') || 
                    input.closest('.form-group').querySelector('.invalid-feedback');
    if (feedback) feedback.textContent = '';
}

// ==================== VALIDATION FUNCTIONS ====================

// Email validation
function validateEmail(email) {
    const regex = /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/;
    return regex.test(email);
}

// Username validation
function validateUsername(username) {
    return username.length >= 3 && username.length <= 50 && /^[a-zA-Z0-9_.-]+$/.test(username);
}

// Password validation
function validatePassword(password) {
    const checks = {
        length: password.length >= 8,
        uppercase: /[A-Z]/.test(password),
        lowercase: /[a-z]/.test(password),
        number: /\d/.test(password)
    };
    
    return {
        isValid: Object.values(checks).every(v => v),
        checks: checks,
        strength: calculatePasswordStrength(password)
    };
}

// Calculate password strength
function calculatePasswordStrength(password) {
    let strength = 0;
    if (password.length >= 8) strength += 25;
    if (password.length >= 12) strength += 25;
    if (/[a-z]/.test(password) && /[A-Z]/.test(password)) strength += 20;
    if (/\d/.test(password)) strength += 15;
    if (/[^a-zA-Z0-9]/.test(password)) strength += 15;
    return Math.min(strength, 100);
}

// Update password strength indicator
function updatePasswordStrength(inputId, barId, textId) {
    const input = document.getElementById(inputId);
    const bar = document.getElementById(barId);
    const text = document.getElementById(textId);
    
    if (!input || !bar || !text) return;
    
    const password = input.value;
    const validation = validatePassword(password);
    const strength = validation.strength;
    
    // Update bar
    bar.style.width = strength + '%';
    
    // Update color and text
    if (strength < 40) {
        bar.style.backgroundColor = '#e74c3c';
        text.textContent = 'Weak password';
        text.style.color = '#e74c3c';
    } else if (strength < 70) {
        bar.style.backgroundColor = '#f39c12';
        text.textContent = 'Medium password';
        text.style.color = '#f39c12';
    } else {
        bar.style.backgroundColor = '#27ae60';
        text.textContent = 'Strong password';
        text.style.color = '#27ae60';
    }
}

// Update password requirements checklist
function updatePasswordRequirements(password) {
    const validation = validatePassword(password);
    const checks = validation.checks;
    
    const updateRequirement = (id, isValid) => {
        const element = document.getElementById(id);
        if (element) {
            if (isValid) {
                element.classList.add('valid');
            } else {
                element.classList.remove('valid');
            }
        }
    };
    
    updateRequirement('req-length', checks.length);
    updateRequirement('req-uppercase', checks.uppercase);
    updateRequirement('req-lowercase', checks.lowercase);
    updateRequirement('req-number', checks.number);
}

// Phone validation
function validatePhone(phone) {
    const cleaned = phone.replace(/[^\d+]/g, '');
    return /^\+?[\d]{10,15}$/.test(cleaned);
}

// Toggle password visibility
function togglePassword(inputId) {
    const input = document.getElementById(inputId);
    const icon = input.parentElement.querySelector('.password-toggle i');
    
    if (input.type === 'password') {
        input.type = 'text';
        icon.classList.remove('fa-eye');
        icon.classList.add('fa-eye-slash');
    } else {
        input.type = 'password';
        icon.classList.remove('fa-eye-slash');
        icon.classList.add('fa-eye');
    }
}

// ==================== PAGE NAVIGATION ====================

function showLogin() {
    clearAlerts();
    document.getElementById('login-page').classList.remove('hidden');
    document.getElementById('register-page').classList.add('hidden');
    document.getElementById('forgot-password-page').classList.add('hidden');
    document.getElementById('reset-password-page').classList.add('hidden');
    document.getElementById('app-section').classList.add('hidden');
}

function showRegister() {
    clearAlerts();
    document.getElementById('login-page').classList.add('hidden');
    document.getElementById('register-page').classList.remove('hidden');
    document.getElementById('forgot-password-page').classList.add('hidden');
    document.getElementById('reset-password-page').classList.add('hidden');
    document.getElementById('app-section').classList.add('hidden');
}

function showForgotPassword() {
    clearAlerts();
    document.getElementById('login-page').classList.add('hidden');
    document.getElementById('register-page').classList.add('hidden');
    document.getElementById('forgot-password-page').classList.remove('hidden');
    document.getElementById('reset-password-page').classList.add('hidden');
    document.getElementById('app-section').classList.add('hidden');
}

function showResetPassword(token) {
    clearAlerts();
    document.getElementById('reset-token').value = token;
    document.getElementById('login-page').classList.add('hidden');
    document.getElementById('register-page').classList.add('hidden');
    document.getElementById('forgot-password-page').classList.add('hidden');
    document.getElementById('reset-password-page').classList.remove('hidden');
    document.getElementById('app-section').classList.add('hidden');
}

function showApp() {
    clearAlerts();
    document.getElementById('login-page').classList.add('hidden');
    document.getElementById('register-page').classList.add('hidden');
    document.getElementById('forgot-password-page').classList.add('hidden');
    document.getElementById('reset-password-page').classList.add('hidden');
    document.getElementById('app-section').classList.remove('hidden');
    
    // Load dashboard data
    loadDashboard();
}

function showSection(sectionName) {
    // Hide all sections
    document.querySelectorAll('.section-content').forEach(section => {
        section.classList.add('hidden');
    });
    
    // Remove active class from all nav links
    document.querySelectorAll('.sidebar .nav-link').forEach(link => {
        link.classList.remove('active');
    });
    
    // Show selected section
    document.getElementById(`${sectionName}-section`).classList.remove('hidden');
    
    // Add active class to current nav link
    event.target.classList.add('active');
    
    // Load section data
    switch(sectionName) {
        case 'dashboard':
            loadDashboard();
            break;
        case 'clients':
            loadClients();
            break;
        case 'bookings':
            loadBookings();
            break;
        case 'inventory':
            loadInventory();
            break;
        case 'payments':
            loadPayments();
            break;
    }
}

// ==================== AUTHENTICATION ====================

// Login
document.getElementById('login-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const username = document.getElementById('login-username').value.trim();
    const password = document.getElementById('login-password').value;
    
    // Clear previous validation
    clearFieldValidation(document.getElementById('login-username'));
    clearFieldValidation(document.getElementById('login-password'));
    
    // Validate inputs
    if (!username) {
        validateField(document.getElementById('login-username'), false, 'Username is required');
        return;
    }
    
    if (!password) {
        validateField(document.getElementById('login-password'), false, 'Password is required');
        return;
    }
    
    setButtonLoading('login-btn', true);
    
    try {
        const response = await fetch(`${API_URL}/auth/login`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ username, password })
        });
        
        const data = await response.json();
        
        if (response.ok && data.success) {
            authToken = data.access_token;
            currentUser = data.user;
            localStorage.setItem('authToken', authToken);
            localStorage.setItem('currentUser', JSON.stringify(currentUser));
            
            // Update user name in navbar
            document.getElementById('user-name').textContent = currentUser.name;
            
            showApp();
        } else {
            showAlert('login-alert', data.message || 'Login failed. Please try again.', 'danger');
        }
    } catch (error) {
        showAlert('login-alert', 'Network error. Please check your connection and try again.', 'danger');
        console.error('Login error:', error);
    } finally {
        setButtonLoading('login-btn', false);
    }
});

// Register
document.getElementById('register-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const name = document.getElementById('register-name').value.trim();
    const username = document.getElementById('register-username').value.trim();
    const email = document.getElementById('register-email').value.trim();
    const password = document.getElementById('register-password').value;
    const confirmPassword = document.getElementById('register-confirm-password').value;
    
    // Clear previous validation
    ['register-name', 'register-username', 'register-email', 'register-password', 'register-confirm-password'].forEach(id => {
        clearFieldValidation(document.getElementById(id));
    });
    
    // Validate name
    if (!name || name.length < 2) {
        validateField(document.getElementById('register-name'), false, 'Name must be at least 2 characters');
        return;
    }
    
    // Validate username
    if (!validateUsername(username)) {
        validateField(document.getElementById('register-username'), false, 'Username must be 3-50 characters and contain only letters, numbers, dots, hyphens, and underscores');
        return;
    }
    
    // Validate email
    if (!validateEmail(email)) {
        validateField(document.getElementById('register-email'), false, 'Please enter a valid email address');
        return;
    }
    
    // Validate password
    const passwordValidation = validatePassword(password);
    if (!passwordValidation.isValid) {
        validateField(document.getElementById('register-password'), false, 'Password does not meet requirements');
        return;
    }
    
    // Validate password confirmation
    if (password !== confirmPassword) {
        validateField(document.getElementById('register-confirm-password'), false, 'Passwords do not match');
        return;
    }
    
    setButtonLoading('register-btn', true);
    
    try {
        const response = await fetch(`${API_URL}/auth/register`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ name, username, email, password })
        });
        
        const data = await response.json();
        
        if (response.ok && data.success) {
            showAlert('register-alert', 'Registration successful! Please sign in.', 'success');
            setTimeout(() => showLogin(), 2000);
        } else {
            showAlert('register-alert', data.message || 'Registration failed. Please try again.', 'danger');
        }
    } catch (error) {
        showAlert('register-alert', 'Network error. Please check your connection and try again.', 'danger');
        console.error('Registration error:', error);
    } finally {
        setButtonLoading('register-btn', false);
    }
});

// Forgot Password
document.getElementById('forgot-password-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const email = document.getElementById('forgot-email').value.trim();
    
    // Clear previous validation
    clearFieldValidation(document.getElementById('forgot-email'));
    
    // Validate email
    if (!validateEmail(email)) {
        validateField(document.getElementById('forgot-email'), false, 'Please enter a valid email address');
        return;
    }
    
    setButtonLoading('forgot-password-btn', true);
    
    try {
        const response = await fetch(`${API_URL}/auth/forgot-password`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ email })
        });
        
        const data = await response.json();
        
        if (response.ok && data.success) {
            showAlert('forgot-password-alert', 
                'If an account with that email exists, a password reset link has been sent. Please check your email.', 
                'success');
            
            // Show reset link in development (remove in production)
            if (data.reset_link) {
                console.log('Reset link:', data.reset_link);
                const token = new URL(data.reset_link).searchParams.get('token');
                setTimeout(() => showResetPassword(token), 2000);
            }
        } else {
            showAlert('forgot-password-alert', data.message || 'Failed to send reset link. Please try again.', 'danger');
        }
    } catch (error) {
        showAlert('forgot-password-alert', 'Network error. Please check your connection and try again.', 'danger');
        console.error('Forgot password error:', error);
    } finally {
        setButtonLoading('forgot-password-btn', false);
    }
});

// Reset Password
document.getElementById('reset-password-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const token = document.getElementById('reset-token').value;
    const newPassword = document.getElementById('new-password').value;
    const confirmPassword = document.getElementById('confirm-new-password').value;
    
    // Clear previous validation
    clearFieldValidation(document.getElementById('new-password'));
    clearFieldValidation(document.getElementById('confirm-new-password'));
    
    // Validate password
    const passwordValidation = validatePassword(newPassword);
    if (!passwordValidation.isValid) {
        validateField(document.getElementById('new-password'), false, 'Password does not meet requirements');
        return;
    }
    
    // Validate password confirmation
    if (newPassword !== confirmPassword) {
        validateField(document.getElementById('confirm-new-password'), false, 'Passwords do not match');
        return;
    }
    
    setButtonLoading('reset-password-btn', true);
    
    try {
        const response = await fetch(`${API_URL}/auth/reset-password`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ token, password: newPassword })
        });
        
        const data = await response.json();
        
        if (response.ok && data.success) {
            showAlert('reset-password-alert', 'Password reset successful! You can now sign in with your new password.', 'success');
            setTimeout(() => showLogin(), 2000);
        } else {
            showAlert('reset-password-alert', data.message || 'Password reset failed. Please try again.', 'danger');
        }
    } catch (error) {
        showAlert('reset-password-alert', 'Network error. Please check your connection and try again.', 'danger');
        console.error('Reset password error:', error);
    } finally {
        setButtonLoading('reset-password-btn', false);
    }
});

// Change Password
function showChangePassword() {
    const modal = new bootstrap.Modal(document.getElementById('change-password-modal'));
    modal.show();
}

async function changePassword() {
    const currentPassword = document.getElementById('current-password').value;
    const newPassword = document.getElementById('change-new-password').value;
    const confirmPassword = document.getElementById('change-confirm-password').value;
    
    // Clear previous validation
    ['current-password', 'change-new-password', 'change-confirm-password'].forEach(id => {
        clearFieldValidation(document.getElementById(id));
    });
    
    // Validate inputs
    if (!currentPassword) {
        validateField(document.getElementById('current-password'), false, 'Current password is required');
        return;
    }
    
    const passwordValidation = validatePassword(newPassword);
    if (!passwordValidation.isValid) {
        validateField(document.getElementById('change-new-password'), false, 'Password does not meet requirements');
        return;
    }
    
    if (newPassword !== confirmPassword) {
        validateField(document.getElementById('change-confirm-password'), false, 'Passwords do not match');
        return;
    }
    
    try {
        const response = await fetch(`${API_URL}/auth/change-password`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${authToken}`
            },
            body: JSON.stringify({
                current_password: currentPassword,
                new_password: newPassword
            })
        });
        
        const data = await response.json();
        
        if (response.ok && data.success) {
            showAlert('change-password-alert', 'Password changed successfully!', 'success');
            setTimeout(() => {
                bootstrap.Modal.getInstance(document.getElementById('change-password-modal')).hide();
                document.getElementById('change-password-form').reset();
            }, 1500);
        } else {
            showAlert('change-password-alert', data.message || 'Password change failed. Please try again.', 'danger');
        }
    } catch (error) {
        showAlert('change-password-alert', 'Network error. Please check your connection and try again.', 'danger');
        console.error('Change password error:', error);
    }
}

// Logout
function logout() {
    authToken = null;
    currentUser = null;
    localStorage.removeItem('authToken');
    localStorage.removeItem('currentUser');
    showLogin();
}

// ==================== DATA LOADING FUNCTIONS ====================

async function loadDashboard() {
    try {
        const response = await fetch(`${API_URL}/dashboard`, {
            headers: {
                'Authorization': `Bearer ${authToken}`
            }
        });
        
        const result = await response.json();
        
        if (response.ok && result.success) {
            const data = result.data;
            
            // Update stats
            document.getElementById('stat-clients').textContent = data.total_clients;
            document.getElementById('stat-bookings').textContent = data.pending_bookings;
            document.getElementById('stat-low-stock').textContent = data.low_stock_items;
            document.getElementById('stat-payments').textContent = data.pending_payments;
            
            // Update recent bookings
            const bookingsList = document.getElementById('recent-bookings-list');
            if (data.recent_bookings && data.recent_bookings.length > 0) {
                bookingsList.innerHTML = data.recent_bookings.map(booking => `
                    <div class="d-flex justify-content-between align-items-center mb-3 pb-3 border-bottom">
                        <div>
                            <strong>${booking.client_name}</strong><br>
                            <small class="text-muted">${booking.service_type}</small>
                        </div>
                        <div class="text-end">
                            <div>${booking.booking_date}</div>
                            <span class="badge bg-${booking.status === 'confirmed' ? 'success' : 'warning'}">${booking.status}</span>
                        </div>
                    </div>
                `).join('');
            } else {
                bookingsList.innerHTML = '<p class="text-muted text-center">No recent bookings</p>';
            }
            
            // Update low stock alerts
            const stockList = document.getElementById('low-stock-list');
            if (data.low_stock_alerts && data.low_stock_alerts.length > 0) {
                stockList.innerHTML = data.low_stock_alerts.map(item => `
                    <div class="d-flex justify-content-between align-items-center mb-3 pb-3 border-bottom">
                        <div>
                            <strong>${item.name}</strong>
                        </div>
                        <div class="text-end">
                            <span class="badge bg-danger">${item.stock_quantity} / ${item.min_stock}</span>
                        </div>
                    </div>
                `).join('');
            } else {
                stockList.innerHTML = '<p class="text-muted text-center">No low stock items</p>';
            }
        }
    } catch (error) {
        console.error('Error loading dashboard:', error);
    }
}

async function loadClients() {
    try {
        const response = await fetch(`${API_URL}/clients`, {
            headers: {
                'Authorization': `Bearer ${authToken}`
            }
        });
        
        const result = await response.json();
        
        if (response.ok && result.success) {
            const tableBody = document.getElementById('clients-table-body');
            
            if (result.data && result.data.length > 0) {
                tableBody.innerHTML = result.data.map(client => `
                    <tr>
                        <td>${client.name}</td>
                        <td>${client.phone}</td>
                        <td>${client.email || 'N/A'}</td>
                        <td>${client.vehicle_details}</td>
                        <td>
                            <button class="btn btn-sm btn-primary" onclick="editClient(${client.id})">
                                <i class="fas fa-edit"></i>
                            </button>
                            <button class="btn btn-sm btn-danger" onclick="deleteClient(${client.id})">
                                <i class="fas fa-trash"></i>
                            </button>
                        </td>
                    </tr>
                `).join('');
            } else {
                tableBody.innerHTML = '<tr><td colspan="5" class="text-center text-muted">No clients found</td></tr>';
            }
        }
    } catch (error) {
        console.error('Error loading clients:', error);
    }
}

async function loadBookings() {
    try {
        const response = await fetch(`${API_URL}/bookings`, {
            headers: {
                'Authorization': `Bearer ${authToken}`
            }
        });
        
        const result = await response.json();
        
        if (response.ok && result.success) {
            const tableBody = document.getElementById('bookings-table-body');
            
            if (result.data && result.data.length > 0) {
                tableBody.innerHTML = result.data.map(booking => `
                    <tr>
                        <td>${booking.client_name || 'N/A'}</td>
                        <td>${booking.service_type}</td>
                        <td>${booking.booking_date}</td>
                        <td>${booking.booking_time}</td>
                        <td><span class="badge bg-${booking.status === 'completed' ? 'success' : booking.status === 'confirmed' ? 'info' : booking.status === 'cancelled' ? 'danger' : 'warning'}">${booking.status}</span></td>
                        <td>
                            <button class="btn btn-sm btn-primary" onclick="editBooking(${booking.id})">
                                <i class="fas fa-edit"></i>
                            </button>
                            <button class="btn btn-sm btn-danger" onclick="deleteBooking(${booking.id})">
                                <i class="fas fa-trash"></i>
                            </button>
                        </td>
                    </tr>
                `).join('');
            } else {
                tableBody.innerHTML = '<tr><td colspan="6" class="text-center text-muted">No bookings found</td></tr>';
            }
        }
    } catch (error) {
        console.error('Error loading bookings:', error);
    }
}

async function loadInventory() {
    try {
        const response = await fetch(`${API_URL}/inventory`, {
            headers: {
                'Authorization': `Bearer ${authToken}`
            }
        });
        
        const result = await response.json();
        
        if (response.ok && result.success) {
            const tableBody = document.getElementById('inventory-table-body');
            
            if (result.data && result.data.length > 0) {
                tableBody.innerHTML = result.data.map(item => `
                    <tr>
                        <td>${item.name}</td>
                        <td>${item.category}</td>
                        <td>${item.stock_quantity}</td>
                        <td>${item.price.toFixed(2)}</td>
                        <td><span class="badge bg-${item.is_low_stock ? 'danger' : 'success'}">${item.is_low_stock ? 'Low Stock' : 'In Stock'}</span></td>
                        <td>
                            <button class="btn btn-sm btn-primary" onclick="editInventory(${item.id})">
                                <i class="fas fa-edit"></i>
                            </button>
                            <button class="btn btn-sm btn-danger" onclick="deleteInventory(${item.id})">
                                <i class="fas fa-trash"></i>
                            </button>
                        </td>
                    </tr>
                `).join('');
            } else {
                tableBody.innerHTML = '<tr><td colspan="6" class="text-center text-muted">No inventory items found</td></tr>';
            }
        }
    } catch (error) {
        console.error('Error loading inventory:', error);
    }
}

async function loadPayments() {
    try {
        const response = await fetch(`${API_URL}/payments`, {
            headers: {
                'Authorization': `Bearer ${authToken}`
            }
        });
        
        const result = await response.json();
        
        if (response.ok && result.success) {
            const tableBody = document.getElementById('payments-table-body');
            
            if (result.data && result.data.length > 0) {
                tableBody.innerHTML = result.data.map(payment => `
                    <tr>
                        <td>#${payment.booking_id}</td>
                        <td>${payment.amount.toFixed(2)}</td>
                        <td>${payment.payment_method}</td>
                        <td><span class="badge bg-${payment.status === 'completed' ? 'success' : payment.status === 'failed' ? 'danger' : 'warning'}">${payment.status}</span></td>
                        <td>${new Date(payment.payment_date).toLocaleDateString()}</td>
                        <td>
                            <button class="btn btn-sm btn-info" onclick="viewPayment(${payment.id})">
                                <i class="fas fa-eye"></i>
                            </button>
                        </td>
                    </tr>
                `).join('');
            } else {
                tableBody.innerHTML = '<tr><td colspan="6" class="text-center text-muted">No payments found</td></tr>';
            }
        }
    } catch (error) {
        console.error('Error loading payments:', error);
    }
}

// Placeholder functions for CRUD operations
function showAddClientModal() {
    alert('Add Client functionality - implement modal form');
}

function editClient(id) {
    alert('Edit Client ' + id);
}

function deleteClient(id) {
    if (confirm('Are you sure you want to delete this client?')) {
        alert('Delete Client ' + id);
    }
}

function showAddBookingModal() {
    alert('Add Booking functionality - implement modal form');
}

function editBooking(id) {
    alert('Edit Booking ' + id);
}

function deleteBooking(id) {
    if (confirm('Are you sure you want to delete this booking?')) {
        alert('Delete Booking ' + id);
    }
}

function showAddInventoryModal() {
    alert('Add Inventory functionality - implement modal form');
}

function editInventory(id) {
    alert('Edit Inventory ' + id);
}

function deleteInventory(id) {
    if (confirm('Are you sure you want to delete this item?')) {
        alert('Delete Inventory ' + id);
    }
}

function viewPayment(id) {
    alert('View Payment ' + id);
}

// ==================== EVENT LISTENERS ====================

// Password strength indicators
document.getElementById('register-password')?.addEventListener('input', (e) => {
    updatePasswordStrength('register-password', 'password-strength-bar', 'password-strength-text');
    updatePasswordRequirements(e.target.value);
});

document.getElementById('new-password')?.addEventListener('input', (e) => {
    updatePasswordStrength('new-password', 'new-password-strength-bar', 'new-password-strength-text');
});

// ==================== INITIALIZATION ====================

// Check for existing session on page load
window.addEventListener('DOMContentLoaded', () => {
    const savedToken = localStorage.getItem('authToken');
    const savedUser = localStorage.getItem('currentUser');
    
    // Check if there's a reset token in URL
    const urlParams = new URLSearchParams(window.location.search);
    const resetToken = urlParams.get('token');
    
    if (resetToken) {
        showResetPassword(resetToken);
    } else if (savedToken && savedUser) {
        authToken = savedToken;
        currentUser = JSON.parse(savedUser);
        document.getElementById('user-name').textContent = currentUser.name;
        showApp();
    } else {
        showLogin();
    }

    const checkbox = document.getElementById('checkbox');
    checkbox.addEventListener('change', () => {
        document.body.classList.toggle('dark-mode');
        document.body.classList.toggle('light-mode');
    });

    // Hide loader after page loads
    const loader = document.getElementById('loader');
    loader.style.display = 'none';
});
