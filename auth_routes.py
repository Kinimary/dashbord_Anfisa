#!/usr/bin/env python3
"""
Authentication routes and login system
"""

from flask import Blueprint, request, render_template_string, redirect, url_for, session, flash, jsonify
from utils.auth import authenticate_user, create_user_session, invalidate_session, validate_session
from database.models import User
from database import db
import logging

logger = logging.getLogger(__name__)

auth_bp = Blueprint('auth', __name__)

# Login template
LOGIN_TEMPLATE = """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Вход в систему - Счетчики посетителей</title>
    <link href="https://cdn.replit.com/agent/bootstrap-agent-dark-theme.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    <style>
        .login-container {
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            background: linear-gradient(135deg, #1a1a1a 0%, #2d2d2d 100%);
        }
        .login-card {
            width: 100%;
            max-width: 400px;
            padding: 2rem;
            border-radius: 15px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.3);
        }
        .logo {
            font-size: 2.5rem;
            color: var(--bs-primary);
            margin-bottom: 1rem;
        }
    </style>
</head>
<body>
    <div class="login-container">
        <div class="login-card card">
            <div class="card-body text-center">
                <div class="logo">
                    <i class="fas fa-tachometer-alt"></i>
                </div>
                <h3 class="card-title mb-4">Система управления счетчиками</h3>
                
                {% if error %}
                <div class="alert alert-danger">
                    <i class="fas fa-exclamation-triangle me-2"></i>
                    {{ error }}
                </div>
                {% endif %}
                
                <form method="POST" action="/login">
                    <div class="mb-3">
                        <div class="input-group">
                            <span class="input-group-text">
                                <i class="fas fa-user"></i>
                            </span>
                            <input type="text" class="form-control" name="username" placeholder="Имя пользователя" required>
                        </div>
                    </div>
                    
                    <div class="mb-4">
                        <div class="input-group">
                            <span class="input-group-text">
                                <i class="fas fa-lock"></i>
                            </span>
                            <input type="password" class="form-control" name="password" placeholder="Пароль" required>
                        </div>
                    </div>
                    
                    <button type="submit" class="btn btn-primary w-100 mb-3">
                        <i class="fas fa-sign-in-alt me-2"></i>
                        Войти
                    </button>
                </form>
                
                <div class="text-muted small">
                    <hr>
                    <p class="mb-1"><strong>Тестовые аккаунты:</strong></p>
                    <p class="mb-1">admin / admin123 (Администратор)</p>
                    <p class="mb-1">regional_director / demo123 (РД)</p>
                    <p class="mb-0">tech_user1 / demo123 (Технический)</p>
                </div>
            </div>
        </div>
    </div>
</body>
</html>
"""

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        
        if not username or not password:
            return render_template_string(LOGIN_TEMPLATE, error="Введите имя пользователя и пароль")
        
        user = authenticate_user(username, password)
        if user:
            session_token = create_user_session(user.id, request.remote_addr, request.headers.get('User-Agent'))
            if session_token:
                session['user_id'] = user.id
                session['session_token'] = session_token
                session['username'] = user.username
                session['role'] = user.role.name
                session.permanent = True
                
                logger.info(f"User {username} logged in successfully")
                return redirect(url_for('dashboard'))
            else:
                return render_template_string(LOGIN_TEMPLATE, error="Ошибка создания сессии")
        else:
            logger.warning(f"Failed login attempt for username: {username}")
            return render_template_string(LOGIN_TEMPLATE, error="Неверное имя пользователя или пароль")
    
    return render_template_string(LOGIN_TEMPLATE)

@auth_bp.route('/logout')
def logout():
    if 'session_token' in session:
        invalidate_session(session['session_token'])
    
    session.clear()
    flash('Вы успешно вышли из системы', 'info')
    return redirect(url_for('auth.login'))

def login_required(f):
    """Decorator to require login for routes"""
    from functools import wraps
    
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or 'session_token' not in session:
            return redirect(url_for('auth.login'))
        
        # Validate session
        user = validate_session(session['session_token'])
        if not user:
            session.clear()
            return redirect(url_for('auth.login'))
        
        return f(*args, **kwargs)
    
    return decorated_function

def admin_required(f):
    """Decorator to require admin role"""
    from functools import wraps
    
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if session.get('role') != 'admin':
            flash('Доступ запрещен: требуются права администратора', 'error')
            return redirect(url_for('dashboard'))
        
        return f(*args, **kwargs)
    
    return decorated_function

def get_current_user():
    """Get current logged in user"""
    if 'user_id' in session:
        return User.query.get(session['user_id'])
    return None