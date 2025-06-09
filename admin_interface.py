#!/usr/bin/env python3
"""
Admin interface with full CRUD operations
"""

from flask import Blueprint, render_template_string, request, redirect, url_for, flash, jsonify
from auth_routes import login_required, admin_required, get_current_user
from database import db
from database.models import User, Role, Store, VisitorCounter, Alert, VisitorData, AuditLog
from utils.auth import hash_password
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

ADMIN_TEMPLATE = """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Администрирование - Счетчики посетителей</title>
    <link href="https://cdn.replit.com/agent/bootstrap-agent-dark-theme.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    <style>
        .admin-sidebar {
            min-height: calc(100vh - 56px);
            background-color: var(--bs-dark);
        }
        .nav-pills .nav-link.active {
            background-color: var(--bs-primary);
        }
        .card-stat {
            border-left: 4px solid var(--bs-primary);
        }
    </style>
</head>
<body>
    <!-- Navigation -->
    <nav class="navbar navbar-expand-lg navbar-dark bg-dark">
        <div class="container-fluid">
            <a class="navbar-brand" href="/">
                <i class="fas fa-tachometer-alt me-2"></i>
                Система управления счетчиками
            </a>
            <div class="navbar-nav ms-auto">
                <div class="nav-item dropdown">
                    <a class="nav-link dropdown-toggle" href="#" role="button" data-bs-toggle="dropdown">
                        <i class="fas fa-user me-2"></i>{{ current_user.username }}
                    </a>
                    <ul class="dropdown-menu">
                        <li><a class="dropdown-item" href="/">Дашборд</a></li>
                        <li><hr class="dropdown-divider"></li>
                        <li><a class="dropdown-item" href="/logout">Выйти</a></li>
                    </ul>
                </div>
            </div>
        </div>
    </nav>

    <div class="container-fluid">
        <div class="row">
            <!-- Sidebar -->
            <div class="col-md-2 admin-sidebar p-3">
                <ul class="nav nav-pills flex-column">
                    <li class="nav-item mb-2">
                        <a class="nav-link {{ 'active' if active_tab == 'dashboard' else '' }}" 
                           href="/admin?tab=dashboard">
                            <i class="fas fa-chart-line me-2"></i>Обзор
                        </a>
                    </li>
                    <li class="nav-item mb-2">
                        <a class="nav-link {{ 'active' if active_tab == 'users' else '' }}" 
                           href="/admin?tab=users">
                            <i class="fas fa-users me-2"></i>Пользователи
                        </a>
                    </li>
                    <li class="nav-item mb-2">
                        <a class="nav-link {{ 'active' if active_tab == 'stores' else '' }}" 
                           href="/admin?tab=stores">
                            <i class="fas fa-store me-2"></i>Магазины
                        </a>
                    </li>
                    <li class="nav-item mb-2">
                        <a class="nav-link {{ 'active' if active_tab == 'counters' else '' }}" 
                           href="/admin?tab=counters">
                            <i class="fas fa-microchip me-2"></i>Счетчики
                        </a>
                    </li>
                    <li class="nav-item mb-2">
                        <a class="nav-link {{ 'active' if active_tab == 'alerts' else '' }}" 
                           href="/admin?tab=alerts">
                            <i class="fas fa-exclamation-triangle me-2"></i>Алерты
                        </a>
                    </li>
                    <li class="nav-item mb-2">
                        <a class="nav-link {{ 'active' if active_tab == 'audit' else '' }}" 
                           href="/admin?tab=audit">
                            <i class="fas fa-history me-2"></i>Аудит
                        </a>
                    </li>
                </ul>
            </div>

            <!-- Main Content -->
            <div class="col-md-10 p-4">
                {% if tab_content %}
                    {{ tab_content|safe }}
                {% else %}
                    <!-- Default Dashboard -->
                    <h2 class="mb-4">Панель администратора</h2>
                    
                    <div class="row mb-4">
                        <div class="col-md-3">
                            <div class="card card-stat">
                                <div class="card-body">
                                    <h5 class="card-title">Пользователи</h5>
                                    <h3 class="text-primary">{{ stats.users }}</h3>
                                </div>
                            </div>
                        </div>
                        <div class="col-md-3">
                            <div class="card card-stat">
                                <div class="card-body">
                                    <h5 class="card-title">Магазины</h5>
                                    <h3 class="text-success">{{ stats.stores }}</h3>
                                </div>
                            </div>
                        </div>
                        <div class="col-md-3">
                            <div class="card card-stat">
                                <div class="card-body">
                                    <h5 class="card-title">Счетчики</h5>
                                    <h3 class="text-info">{{ stats.counters }}</h3>
                                </div>
                            </div>
                        </div>
                        <div class="col-md-3">
                            <div class="card card-stat">
                                <div class="card-body">
                                    <h5 class="card-title">Активные алерты</h5>
                                    <h3 class="text-warning">{{ stats.alerts }}</h3>
                                </div>
                            </div>
                        </div>
                    </div>

                    <div class="row">
                        <div class="col-md-6">
                            <div class="card">
                                <div class="card-header">
                                    <h5 class="mb-0">Последние алерты</h5>
                                </div>
                                <div class="card-body">
                                    {% for alert in recent_alerts %}
                                    <div class="d-flex justify-content-between align-items-center mb-2">
                                        <div>
                                            <small class="text-muted">{{ alert.created_at.strftime('%d.%m.%Y %H:%M') }}</small>
                                            <p class="mb-0">{{ alert.message }}</p>
                                        </div>
                                        <span class="badge bg-{{ 'danger' if alert.severity == 'critical' else 'warning' if alert.severity == 'high' else 'secondary' }}">
                                            {{ alert.severity }}
                                        </span>
                                    </div>
                                    {% endfor %}
                                </div>
                            </div>
                        </div>
                        
                        <div class="col-md-6">
                            <div class="card">
                                <div class="card-header">
                                    <h5 class="mb-0">Активность системы</h5>
                                </div>
                                <div class="card-body">
                                    {% for log in recent_logs %}
                                    <div class="mb-2">
                                        <small class="text-muted">{{ log.timestamp.strftime('%d.%m.%Y %H:%M') }}</small>
                                        <p class="mb-0">{{ log.action }} - {{ log.user.username if log.user else 'Система' }}</p>
                                    </div>
                                    {% endfor %}
                                </div>
                            </div>
                        </div>
                    </div>
                {% endif %}
            </div>
        </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
"""

USERS_TAB = """
<div class="d-flex justify-content-between align-items-center mb-4">
    <h2>Управление пользователями</h2>
    <button class="btn btn-primary" data-bs-toggle="modal" data-bs-target="#userModal">
        <i class="fas fa-plus me-2"></i>Добавить пользователя
    </button>
</div>

<div class="card">
    <div class="card-body">
        <div class="table-responsive">
            <table class="table table-dark table-striped">
                <thead>
                    <tr>
                        <th>ID</th>
                        <th>Имя пользователя</th>
                        <th>Email</th>
                        <th>Полное имя</th>
                        <th>Роль</th>
                        <th>Статус</th>
                        <th>Последний вход</th>
                        <th>Действия</th>
                    </tr>
                </thead>
                <tbody>
                    {% for user in users %}
                    <tr>
                        <td>{{ user.id }}</td>
                        <td>{{ user.username }}</td>
                        <td>{{ user.email }}</td>
                        <td>{{ user.full_name }}</td>
                        <td>
                            <span class="badge bg-{{ 'success' if user.role.name == 'admin' else 'info' if user.role.name == 'rd' else 'warning' if user.role.name == 'tu' else 'secondary' }}">
                                {{ user.role.description }}
                            </span>
                        </td>
                        <td>
                            <span class="badge bg-{{ 'success' if user.active else 'secondary' }}">
                                {{ 'Активен' if user.active else 'Неактивен' }}
                            </span>
                        </td>
                        <td>{{ user.last_login.strftime('%d.%m.%Y %H:%M') if user.last_login else 'Никогда' }}</td>
                        <td>
                            <a href="/admin/user/{{ user.id }}/edit" class="btn btn-sm btn-outline-primary">
                                <i class="fas fa-edit"></i>
                            </a>
                            {% if user.id != current_user.id %}
                            <a href="/admin/user/{{ user.id }}/toggle" class="btn btn-sm btn-outline-warning">
                                <i class="fas fa-{{ 'pause' if user.active else 'play' }}"></i>
                            </a>
                            {% endif %}
                        </td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </div>
</div>

<!-- User Modal -->
<div class="modal fade" id="userModal" tabindex="-1">
    <div class="modal-dialog">
        <div class="modal-content">
            <div class="modal-header">
                <h5 class="modal-title">Добавить пользователя</h5>
                <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
            </div>
            <form method="POST" action="/admin/user/create">
                <div class="modal-body">
                    <div class="mb-3">
                        <label class="form-label">Имя пользователя</label>
                        <input type="text" class="form-control" name="username" required>
                    </div>
                    <div class="mb-3">
                        <label class="form-label">Email</label>
                        <input type="email" class="form-control" name="email" required>
                    </div>
                    <div class="row">
                        <div class="col-md-6">
                            <div class="mb-3">
                                <label class="form-label">Имя</label>
                                <input type="text" class="form-control" name="first_name">
                            </div>
                        </div>
                        <div class="col-md-6">
                            <div class="mb-3">
                                <label class="form-label">Фамилия</label>
                                <input type="text" class="form-control" name="last_name">
                            </div>
                        </div>
                    </div>
                    <div class="mb-3">
                        <label class="form-label">Роль</label>
                        <select class="form-select" name="role_id" required>
                            {% for role in roles %}
                            <option value="{{ role.id }}">{{ role.description }}</option>
                            {% endfor %}
                        </select>
                    </div>
                    <div class="mb-3">
                        <label class="form-label">Пароль</label>
                        <input type="password" class="form-control" name="password" required>
                    </div>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Отмена</button>
                    <button type="submit" class="btn btn-primary">Создать</button>
                </div>
            </form>
        </div>
    </div>
</div>
"""

@admin_bp.route('/')
@admin_required
def index():
    tab = request.args.get('tab', 'dashboard')
    current_user = get_current_user()
    
    # Get statistics
    stats = {
        'users': User.query.count(),
        'stores': Store.query.count(),
        'counters': VisitorCounter.query.count(),
        'alerts': Alert.query.filter_by(is_resolved=False).count()
    }
    
    # Get recent data
    recent_alerts = Alert.query.filter_by(is_resolved=False).order_by(Alert.created_at.desc()).limit(5).all()
    recent_logs = AuditLog.query.order_by(AuditLog.timestamp.desc()).limit(5).all()
    
    tab_content = None
    if tab == 'users':
        users = User.query.all()
        roles = Role.query.all()
        tab_content = render_template_string(USERS_TAB, users=users, roles=roles, current_user=current_user)
    elif tab == 'stores':
        tab_content = render_stores_tab()
    elif tab == 'counters':
        tab_content = render_counters_tab()
    elif tab == 'alerts':
        tab_content = render_alerts_tab()
    elif tab == 'audit':
        tab_content = render_audit_tab()
    
    return render_template_string(ADMIN_TEMPLATE, 
                                active_tab=tab,
                                current_user=current_user,
                                stats=stats,
                                recent_alerts=recent_alerts,
                                recent_logs=recent_logs,
                                tab_content=tab_content)

@admin_bp.route('/user/create', methods=['POST'])
@admin_required
def create_user():
    try:
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        first_name = request.form.get('first_name', '').strip()
        last_name = request.form.get('last_name', '').strip()
        role_id = request.form.get('role_id')
        password = request.form.get('password', '')
        
        if not all([username, email, role_id, password]):
            flash('Заполните все обязательные поля', 'error')
            return redirect(url_for('admin.index', tab='users'))
        
        # Check if user exists
        if User.query.filter_by(username=username).first():
            flash('Пользователь с таким именем уже существует', 'error')
            return redirect(url_for('admin.index', tab='users'))
        
        if User.query.filter_by(email=email).first():
            flash('Пользователь с таким email уже существует', 'error')
            return redirect(url_for('admin.index', tab='users'))
        
        # Create user
        user = User(
            username=username,
            email=email,
            first_name=first_name,
            last_name=last_name,
            role_id=int(role_id),
            active=True
        )
        user.set_password(password)
        
        db.session.add(user)
        db.session.commit()
        
        # Log action
        from utils.auth import log_user_action
        log_user_action(get_current_user().id, f'USER_CREATED', {'username': username})
        
        flash(f'Пользователь {username} успешно создан', 'success')
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error creating user: {e}")
        flash('Ошибка при создании пользователя', 'error')
    
    return redirect(url_for('admin.index', tab='users'))

@admin_bp.route('/user/<int:user_id>/toggle')
@admin_required
def toggle_user(user_id):
    try:
        user = User.query.get_or_404(user_id)
        current_user = get_current_user()
        
        if user.id == current_user.id:
            flash('Нельзя изменить свой собственный статус', 'error')
            return redirect(url_for('admin.index', tab='users'))
        
        user.active = not user.active
        db.session.commit()
        
        # Log action
        from utils.auth import log_user_action
        log_user_action(current_user.id, f'USER_{"ACTIVATED" if user.active else "DEACTIVATED"}', {'username': user.username})
        
        flash(f'Пользователь {user.username} {"активирован" if user.active else "деактивирован"}', 'success')
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error toggling user: {e}")
        flash('Ошибка при изменении статуса пользователя', 'error')
    
    return redirect(url_for('admin.index', tab='users'))

def render_stores_tab():
    stores = Store.query.all()
    return f"""
    <div class="d-flex justify-content-between align-items-center mb-4">
        <h2>Управление магазинами</h2>
        <button class="btn btn-primary">
            <i class="fas fa-plus me-2"></i>Добавить магазин
        </button>
    </div>
    
    <div class="card">
        <div class="card-body">
            <div class="table-responsive">
                <table class="table table-dark table-striped">
                    <thead>
                        <tr>
                            <th>Код</th>
                            <th>Название</th>
                            <th>Город</th>
                            <th>Регион</th>
                            <th>Менеджер</th>
                            <th>Статус</th>
                            <th>Действия</th>
                        </tr>
                    </thead>
                    <tbody>
                        {''.join([f'''
                        <tr>
                            <td>{store.store_code}</td>
                            <td>{store.name}</td>
                            <td>{store.city}</td>
                            <td>{store.region}</td>
                            <td>{store.manager_name or "Не указан"}</td>
                            <td>
                                <span class="badge bg-{'success' if store.active else 'secondary'}">
                                    {'Активен' if store.active else 'Неактивен'}
                                </span>
                            </td>
                            <td>
                                <button class="btn btn-sm btn-outline-primary">
                                    <i class="fas fa-edit"></i>
                                </button>
                            </td>
                        </tr>
                        ''' for store in stores])}
                    </tbody>
                </table>
            </div>
        </div>
    </div>
    """

def render_counters_tab():
    counters = VisitorCounter.query.join(Store).all()
    return f"""
    <div class="d-flex justify-content-between align-items-center mb-4">
        <h2>Управление счетчиками</h2>
        <button class="btn btn-primary">
            <i class="fas fa-plus me-2"></i>Добавить счетчик
        </button>
    </div>
    
    <div class="card">
        <div class="card-body">
            <div class="table-responsive">
                <table class="table table-dark table-striped">
                    <thead>
                        <tr>
                            <th>Device ID</th>
                            <th>Название</th>
                            <th>Магазин</th>
                            <th>Тип</th>
                            <th>Ответственный</th>
                            <th>Статус</th>
                            <th>Действия</th>
                        </tr>
                    </thead>
                    <tbody>
                        {''.join([f'''
                        <tr>
                            <td><code>{counter.device_id}</code></td>
                            <td>{counter.name}</td>
                            <td>{counter.store.name}</td>
                            <td>{counter.counter_type}</td>
                            <td>{counter.assigned_user.username if counter.assigned_user else "Не назначен"}</td>
                            <td>
                                <span class="badge bg-{'success' if counter.active else 'secondary'}">
                                    {'Активен' if counter.active else 'Неактивен'}
                                </span>
                            </td>
                            <td>
                                <button class="btn btn-sm btn-outline-primary">
                                    <i class="fas fa-edit"></i>
                                </button>
                            </td>
                        </tr>
                        ''' for counter in counters])}
                    </tbody>
                </table>
            </div>
        </div>
    </div>
    """

def render_alerts_tab():
    alerts = Alert.query.join(VisitorCounter).join(Store).order_by(Alert.created_at.desc()).limit(50).all()
    return f"""
    <div class="d-flex justify-content-between align-items-center mb-4">
        <h2>Управление алертами</h2>
        <div>
            <button class="btn btn-success me-2">
                <i class="fas fa-check-double me-2"></i>Отметить все как прочитанные
            </button>
            <button class="btn btn-warning">
                <i class="fas fa-archive me-2"></i>Архивировать решенные
            </button>
        </div>
    </div>
    
    <div class="card">
        <div class="card-body">
            <div class="table-responsive">
                <table class="table table-dark table-striped">
                    <thead>
                        <tr>
                            <th>Дата</th>
                            <th>Тип</th>
                            <th>Уровень</th>
                            <th>Сообщение</th>
                            <th>Счетчик</th>
                            <th>Магазин</th>
                            <th>Статус</th>
                            <th>Действия</th>
                        </tr>
                    </thead>
                    <tbody>
                        {''.join([f'''
                        <tr class="{'table-warning' if not alert.is_read else ''}">
                            <td>{alert.created_at.strftime('%d.%m.%Y %H:%M')}</td>
                            <td>{alert.alert_type}</td>
                            <td>
                                <span class="badge bg-{'danger' if alert.severity == 'critical' else 'warning' if alert.severity == 'high' else 'info' if alert.severity == 'medium' else 'secondary'}">
                                    {alert.severity}
                                </span>
                            </td>
                            <td>{alert.message}</td>
                            <td>{alert.counter.name}</td>
                            <td>{alert.counter.store.name}</td>
                            <td>
                                <span class="badge bg-{'success' if alert.is_resolved else 'warning' if alert.is_read else 'danger'}">
                                    {'Решен' if alert.is_resolved else 'Прочитан' if alert.is_read else 'Новый'}
                                </span>
                            </td>
                            <td>
                                <button class="btn btn-sm btn-outline-success">
                                    <i class="fas fa-check"></i>
                                </button>
                            </td>
                        </tr>
                        ''' for alert in alerts])}
                    </tbody>
                </table>
            </div>
        </div>
    </div>
    """

def render_audit_tab():
    logs = AuditLog.query.order_by(AuditLog.timestamp.desc()).limit(100).all()
    return f"""
    <h2 class="mb-4">Журнал аудита</h2>
    
    <div class="card">
        <div class="card-body">
            <div class="table-responsive">
                <table class="table table-dark table-striped">
                    <thead>
                        <tr>
                            <th>Дата и время</th>
                            <th>Пользователь</th>
                            <th>Действие</th>
                            <th>Таблица</th>
                            <th>IP адрес</th>
                            <th>Детали</th>
                        </tr>
                    </thead>
                    <tbody>
                        {''.join([f'''
                        <tr>
                            <td>{log.timestamp.strftime('%d.%m.%Y %H:%M:%S')}</td>
                            <td>{log.user.username if log.user else 'Система'}</td>
                            <td>
                                <span class="badge bg-primary">
                                    {log.action}
                                </span>
                            </td>
                            <td>{log.table_name or '-'}</td>
                            <td>{log.ip_address or '-'}</td>
                            <td>
                                <small class="text-muted">
                                    {log.new_values[:100] if log.new_values else '-'}
                                </small>
                            </td>
                        </tr>
                        ''' for log in logs])}
                    </tbody>
                </table>
            </div>
        </div>
    </div>
    """