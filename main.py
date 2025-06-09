#!/usr/bin/env python3
"""
Main entry point for visitor counter management system
"""

import os
import logging
from datetime import datetime, timedelta, timezone
from flask import Flask, render_template_string, jsonify, request, redirect, url_for, session, send_file
from database import db, Base
from database.models import User, Store, VisitorCounter, VisitorData, Alert, AuditLog, Role
from auth_routes import auth_bp, login_required, get_current_user
from admin_interface import admin_bp
from utils.auth import create_default_admin
import pandas as pd
import io

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create Flask app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "dev-secret-key-change-in-production")

# Database configuration
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}

# Initialize extensions
db.init_app(app)

# Register blueprints
app.register_blueprint(auth_bp)
app.register_blueprint(admin_bp)

# Import and register API endpoints
from api_endpoints import api_bp
app.register_blueprint(api_bp)

# Import and register email reports (temporarily disabled due to import issues)
# from email_reports import reports_bp
# app.register_blueprint(reports_bp)

# Set session timeout
app.permanent_session_lifetime = timedelta(hours=8)

# Dashboard template with charts and role hierarchy
DASHBOARD_TEMPLATE = """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Дашборд - Счетчики посетителей</title>
    <link href="https://cdn.replit.com/agent/bootstrap-agent-dark-theme.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
    <style>
        .metric-card {
            border-left: 4px solid;
            transition: transform 0.2s;
        }
        .metric-card:hover {
            transform: translateY(-2px);
        }
        .metric-card.primary { border-left-color: #0d6efd; }
        .metric-card.success { border-left-color: #198754; }
        .metric-card.info { border-left-color: #0dcaf0; }
        .metric-card.warning { border-left-color: #ffc107; }
        .chart-container {
            background: rgba(255,255,255,0.05);
            border-radius: 8px;
            padding: 1rem;
            margin-bottom: 1rem;
        }
    </style>
</head>
<body>
    <!-- Navigation -->
    <nav class="navbar navbar-expand-lg navbar-dark bg-dark">
        <div class="container-fluid">
            <a class="navbar-brand" href="/">
                <i class="fas fa-tachometer-alt me-2"></i>
                Система управления счетчиками посетителей
            </a>
            <div class="navbar-nav ms-auto">
                <span class="navbar-text me-3">
                    <i class="fas fa-user me-2"></i>{{ current_user.username }} ({{ current_user.role.description }})
                </span>
                {% if current_user.role.name == 'admin' %}
                <a class="nav-link" href="/admin">
                    <i class="fas fa-cog me-2"></i>Администрирование
                </a>
                {% endif %}
                <div class="nav-item dropdown">
                    <a class="nav-link dropdown-toggle" href="#" role="button" data-bs-toggle="dropdown">
                        <i class="fas fa-download me-2"></i>Отчеты
                    </a>
                    <ul class="dropdown-menu">
                        <li><a class="dropdown-item" href="/export/excel?period=week">
                            <i class="fas fa-file-excel me-2"></i>Экспорт за неделю
                        </a></li>
                        <li><a class="dropdown-item" href="/export/excel?period=month">
                            <i class="fas fa-file-excel me-2"></i>Экспорт за месяц
                        </a></li>
                        <li><hr class="dropdown-divider"></li>
                        <li><a class="dropdown-item" href="/reports/schedule">
                            <i class="fas fa-calendar me-2"></i>Настройка отчетов
                        </a></li>
                    </ul>
                </div>
                <a class="nav-link" href="/logout">
                    <i class="fas fa-sign-out-alt me-2"></i>Выйти
                </a>
            </div>
        </div>
    </nav>

    <div class="container-fluid mt-4">
        <!-- Access Level Info -->
        <div class="row mb-3">
            <div class="col-12">
                <div class="alert alert-info">
                    <i class="fas fa-info-circle me-2"></i>
                    Уровень доступа: {{ access_level }}. 
                    Доступно магазинов: {{ accessible_stores|length }}, счетчиков: {{ accessible_counters|length }}
                </div>
            </div>
        </div>

        <!-- Metrics Cards -->
        <div class="row mb-4">
            <div class="col-md-3">
                <div class="card metric-card primary">
                    <div class="card-body">
                        <div class="d-flex justify-content-between align-items-center">
                            <div>
                                <h6 class="card-subtitle mb-2 text-muted">Посетители за сегодня</h6>
                                <h3 class="card-title mb-0" id="totalVisitors">{{ metrics.total_visitors }}</h3>
                            </div>
                            <div class="text-primary">
                                <i class="fas fa-users fa-2x"></i>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            
            <div class="col-md-3">
                <div class="card metric-card success">
                    <div class="card-body">
                        <div class="d-flex justify-content-between align-items-center">
                            <div>
                                <h6 class="card-subtitle mb-2 text-muted">Текущая посещаемость</h6>
                                <h3 class="card-title mb-0" id="currentOccupancy">{{ metrics.current_occupancy }}</h3>
                            </div>
                            <div class="text-success">
                                <i class="fas fa-chart-line fa-2x"></i>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            
            <div class="col-md-3">
                <div class="card metric-card info">
                    <div class="card-body">
                        <div class="d-flex justify-content-between align-items-center">
                            <div>
                                <h6 class="card-subtitle mb-2 text-muted">Активные счетчики</h6>
                                <h3 class="card-title mb-0" id="onlineCounters">{{ metrics.online_counters }}/{{ metrics.total_counters }}</h3>
                            </div>
                            <div class="text-info">
                                <i class="fas fa-microchip fa-2x"></i>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            
            <div class="col-md-3">
                <div class="card metric-card warning">
                    <div class="card-body">
                        <div class="d-flex justify-content-between align-items-center">
                            <div>
                                <h6 class="card-subtitle mb-2 text-muted">Активные алерты</h6>
                                <h3 class="card-title mb-0" id="activeAlerts">{{ metrics.active_alerts }}</h3>
                            </div>
                            <div class="text-warning">
                                <i class="fas fa-exclamation-triangle fa-2x"></i>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Charts Row -->
        <div class="row mb-4">
            <div class="col-md-6">
                <div class="card">
                    <div class="card-header">
                        <h5 class="mb-0">Трафик посетителей (7 дней)</h5>
                    </div>
                    <div class="card-body">
                        <div id="trafficChart" style="height: 300px;"></div>
                    </div>
                </div>
            </div>
            
            <div class="col-md-6">
                <div class="card">
                    <div class="card-header">
                        <h5 class="mb-0">Почасовая загрузка</h5>
                    </div>
                    <div class="card-body">
                        <div id="hourlyChart" style="height: 300px;"></div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Store Performance Chart -->
        <div class="row mb-4">
            <div class="col-12">
                <div class="card">
                    <div class="card-header">
                        <h5 class="mb-0">Производительность магазинов</h5>
                    </div>
                    <div class="card-body">
                        <div id="storeChart" style="height: 400px;"></div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Tables Row -->
        <div class="row">
            <div class="col-md-8">
                <div class="card">
                    <div class="card-header">
                        <h5 class="mb-0">Статус счетчиков</h5>
                    </div>
                    <div class="card-body">
                        <div class="table-responsive">
                            <table class="table table-dark table-striped">
                                <thead>
                                    <tr>
                                        <th>Счетчик</th>
                                        <th>Магазин</th>
                                        <th>Сегодня</th>
                                        <th>Онлайн</th>
                                        <th>Последнее обновление</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {% for counter in accessible_counters %}
                                    <tr>
                                        <td>{{ counter.name }}</td>
                                        <td>{{ counter.store.name }}</td>
                                        <td>{{ counter.today_visitors }}</td>
                                        <td>
                                            <span class="badge bg-{{ 'success' if counter.is_online else 'danger' }}">
                                                {{ 'Онлайн' if counter.is_online else 'Офлайн' }}
                                            </span>
                                        </td>
                                        <td>{{ counter.last_update.strftime('%H:%M') if counter.last_update else 'Нет данных' }}</td>
                                    </tr>
                                    {% endfor %}
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>
            </div>
            
            <div class="col-md-4">
                <div class="card">
                    <div class="card-header">
                        <h5 class="mb-0">Активные алерты</h5>
                    </div>
                    <div class="card-body">
                        {% for alert in recent_alerts %}
                        <div class="alert alert-{{ 'danger' if alert.severity == 'critical' else 'warning' if alert.severity == 'high' else 'info' }} alert-sm">
                            <strong>{{ alert.counter.store.name }}</strong><br>
                            <small>{{ alert.message }}</small><br>
                            <small class="text-muted">{{ alert.created_at.strftime('%d.%m.%Y %H:%M') }}</small>
                        </div>
                        {% endfor %}
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    <script>
        // Initialize charts
        document.addEventListener('DOMContentLoaded', function() {
            initTrafficChart();
            initHourlyChart();
            initStoreChart();
            
            // Auto-update every 30 seconds
            setInterval(updateMetrics, 30000);
        });

        function initTrafficChart() {
            const trace = {
                x: {{ chart_data.daily_dates | safe }},
                y: {{ chart_data.daily_visitors | safe }},
                type: 'scatter',
                mode: 'lines+markers',
                line: { color: '#0d6efd', width: 3 },
                marker: { size: 6 },
                name: 'Посетители'
            };

            const layout = {
                paper_bgcolor: 'transparent',
                plot_bgcolor: 'transparent',
                font: { color: '#ffffff' },
                xaxis: { gridcolor: '#444' },
                yaxis: { gridcolor: '#444' },
                margin: { t: 20, r: 20, b: 50, l: 50 }
            };

            Plotly.newPlot('trafficChart', [trace], layout, {responsive: true});
        }

        function initHourlyChart() {
            const trace = {
                x: {{ chart_data.hourly_hours | safe }},
                y: {{ chart_data.hourly_visitors | safe }},
                type: 'bar',
                marker: { color: '#198754' },
                name: 'Посетители по часам'
            };

            const layout = {
                paper_bgcolor: 'transparent',
                plot_bgcolor: 'transparent',
                font: { color: '#ffffff' },
                xaxis: { gridcolor: '#444', title: 'Час' },
                yaxis: { gridcolor: '#444', title: 'Посетители' },
                margin: { t: 20, r: 20, b: 50, l: 50 }
            };

            Plotly.newPlot('hourlyChart', [trace], layout, {responsive: true});
        }

        function initStoreChart() {
            const trace = {
                x: {{ chart_data.store_names | safe }},
                y: {{ chart_data.store_visitors | safe }},
                type: 'bar',
                marker: { color: '#0dcaf0' },
                name: 'Посетители по магазинам'
            };

            const layout = {
                paper_bgcolor: 'transparent',
                plot_bgcolor: 'transparent',
                font: { color: '#ffffff' },
                xaxis: { gridcolor: '#444', title: 'Магазины' },
                yaxis: { gridcolor: '#444', title: 'Посетители' },
                margin: { t: 20, r: 20, b: 80, l: 50 }
            };

            Plotly.newPlot('storeChart', [trace], layout, {responsive: true});
        }

        function updateMetrics() {
            fetch('/api/metrics')
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        document.getElementById('totalVisitors').textContent = data.metrics.total_visitors;
                        document.getElementById('currentOccupancy').textContent = data.metrics.current_occupancy;
                        document.getElementById('onlineCounters').textContent = 
                            data.metrics.online_counters + '/' + data.metrics.total_counters;
                        document.getElementById('activeAlerts').textContent = data.metrics.active_alerts;
                    }
                })
                .catch(error => console.error('Error updating metrics:', error));
        }
    </script>
</body>
</html>
"""

@app.route('/')
@login_required
def index():
    """Main dashboard page with role-based access"""
    return dashboard()

@app.route('/dashboard')
@login_required
def dashboard():
    """Dashboard with role hierarchy and charts"""
    try:
        current_user = get_current_user()
        
        # Implement full role hierarchy
        if current_user and hasattr(current_user, 'role') and current_user.role:
            if current_user.role.name == 'admin':
                # Admin sees everything
                access_level = "Администратор - полный доступ"
                accessible_stores = Store.query.filter_by(active=True).all()
                accessible_counters = VisitorCounter.query.filter_by(active=True).all()
                
            elif current_user.role.name == 'rd':
                # Regional Director sees stores and counters of subordinate TUs
                access_level = "Региональный директор - доступ к подчиненным"
                # Get subordinate TU users
                subordinate_users = User.query.filter_by(supervisor_id=current_user.id, active=True).all()
                subordinate_user_ids = [user.id for user in subordinate_users] + [current_user.id]
                
                # Get counters assigned to subordinates
                accessible_counters = VisitorCounter.query.filter(
                    VisitorCounter.assigned_user_id.in_(subordinate_user_ids),
                    VisitorCounter.active == True
                ).all()
                
                # Get stores that have these counters
                store_ids_with_counters = {counter.store_id for counter in accessible_counters}
                accessible_stores = Store.query.filter(
                    Store.id.in_(store_ids_with_counters),
                    Store.active == True
                ).all() if store_ids_with_counters else []
                
            elif current_user.role.name == 'tu':
                # Technical User sees only assigned counters
                access_level = "Технический пользователь - назначенные счетчики"
                accessible_counters = VisitorCounter.query.filter_by(
                    assigned_user_id=current_user.id,
                    active=True
                ).all()
                
                # Get stores that have these counters
                store_ids_with_counters = {counter.store_id for counter in accessible_counters}
                accessible_stores = Store.query.filter(
                    Store.id.in_(store_ids_with_counters),
                    Store.active == True
                ).all() if store_ids_with_counters else []
                
            else:
                # Basic user - very limited access
                access_level = "Базовый пользователь - ограниченный доступ"
                accessible_counters = VisitorCounter.query.filter_by(
                    assigned_user_id=current_user.id,
                    active=True
                ).limit(2).all()
                
                store_ids_with_counters = {counter.store_id for counter in accessible_counters}
                accessible_stores = Store.query.filter(
                    Store.id.in_(store_ids_with_counters),
                    Store.active == True
                ).all() if store_ids_with_counters else []
        else:
            access_level = "Гость - базовый доступ"
            accessible_stores = []
            accessible_counters = []
        
        store_ids = [store.id for store in accessible_stores]
        counter_ids = [counter.id for counter in accessible_counters]
        
        # Get metrics for accessible data
        today = datetime.now(timezone.utc).date()
        yesterday = datetime.now(timezone.utc) - timedelta(days=1)
        
        # Visitor data for accessible counters
        recent_data = VisitorData.query.filter(
            VisitorData.counter_id.in_(counter_ids),
            VisitorData.timestamp >= yesterday
        ).all()
        
        total_visitors = sum(data.entries for data in recent_data)
        current_occupancy = sum(data.current_occupancy for data in recent_data)
        active_alerts = Alert.query.filter(
            Alert.counter_id.in_(counter_ids),
            Alert.is_resolved == False
        ).count()
        
        # Format numbers
        def format_number(num):
            return f"{num:,}".replace(',', ' ')
        
        metrics = {
            'total_visitors': format_number(total_visitors),
            'current_occupancy': format_number(current_occupancy),
            'total_counters': len(counter_ids),
            'online_counters': len([c for c in accessible_counters if getattr(c, 'is_online', False)]),
            'active_alerts': active_alerts
        }
        
        # Generate chart data with error handling
        try:
            chart_data = generate_chart_data(counter_ids) if counter_ids else {
                'daily_dates': [],
                'daily_visitors': [],
                'hourly_hours': [],
                'hourly_visitors': [],
                'store_names': [],
                'store_visitors': []
            }
        except Exception as e:
            logger.error(f"Error generating chart data: {e}")
            chart_data = {
                'daily_dates': [],
                'daily_visitors': [],
                'hourly_hours': [],
                'hourly_visitors': [],
                'store_names': [],
                'store_visitors': []
            }
        
        # Enhance counter data with real-time info
        for counter in accessible_counters:
            try:
                today_data = VisitorData.query.filter(
                    VisitorData.counter_id == counter.id,
                    VisitorData.timestamp >= datetime.combine(today, datetime.min.time().replace(tzinfo=timezone.utc))
                ).all()
                
                counter.today_visitors = sum(data.entries for data in today_data)
                counter.is_online = len(today_data) > 0
                counter.last_update = max([data.timestamp for data in today_data]) if today_data else None
            except Exception as e:
                logger.error(f"Error processing counter {counter.id}: {e}")
                counter.today_visitors = 0
                counter.is_online = False
                counter.last_update = None
        
        # Get recent alerts for accessible counters
        recent_alerts = Alert.query.filter(
            Alert.counter_id.in_(counter_ids),
            Alert.is_resolved == False
        ).order_by(Alert.created_at.desc()).limit(10).all()
        
        return render_template_string(DASHBOARD_TEMPLATE,
                                    current_user=current_user,
                                    access_level=access_level,
                                    accessible_stores=accessible_stores,
                                    accessible_counters=accessible_counters,
                                    metrics=metrics,
                                    chart_data=chart_data,
                                    recent_alerts=recent_alerts)
    
    except Exception as e:
        logger.error(f"Error in dashboard: {e}")
        return jsonify({'error': str(e)}), 500

def generate_chart_data(counter_ids):
    """Generate chart data for accessible counters"""
    if not counter_ids:
        return {
            'daily_dates': [],
            'daily_visitors': [],
            'hourly_hours': [],
            'hourly_visitors': [],
            'store_names': [],
            'store_visitors': []
        }
    
    # Daily data for last 7 days
    week_ago = datetime.now(timezone.utc) - timedelta(days=7)
    daily_data = db.session.query(
        db.func.date(VisitorData.timestamp).label('date'),
        db.func.sum(VisitorData.entries).label('total_entries')
    ).filter(
        VisitorData.counter_id.in_(counter_ids),
        VisitorData.timestamp >= week_ago
    ).group_by(
        db.func.date(VisitorData.timestamp)
    ).order_by('date').all()
    
    # Hourly data for today
    today = datetime.now(timezone.utc).date()
    hourly_data = db.session.query(
        db.func.extract('hour', VisitorData.timestamp).label('hour'),
        db.func.sum(VisitorData.entries).label('total_entries')
    ).filter(
        VisitorData.counter_id.in_(counter_ids),
        db.func.date(VisitorData.timestamp) == today
    ).group_by(
        db.func.extract('hour', VisitorData.timestamp)
    ).order_by('hour').all()
    
    # Store performance data with explicit joins
    store_data = db.session.query(
        Store.name,
        db.func.sum(VisitorData.entries).label('total_entries')
    ).select_from(
        VisitorData.query.join(VisitorCounter).join(Store).subquery()
    ).filter(
        VisitorData.counter_id.in_(counter_ids),
        VisitorData.timestamp >= week_ago
    ).group_by(Store.name).all()
    
    return {
        'daily_dates': [row.date.strftime('%Y-%m-%d') for row in daily_data],
        'daily_visitors': [int(row.total_entries) for row in daily_data],
        'hourly_hours': [f"{int(row.hour):02d}:00" for row in hourly_data],
        'hourly_visitors': [int(row.total_entries) for row in hourly_data],
        'store_names': [row.name for row in store_data] if store_data else [],
        'store_visitors': [int(row.total_entries) for row in store_data] if store_data else []
    }

@app.route('/export/excel')
@login_required
def export_excel():
    """Export data to Excel based on user permissions"""
    try:
        current_user = get_current_user()
        period = request.args.get('period', 'week')
        
        # Get user's accessible counters based on role
        if current_user.role.name == 'admin':
            accessible_counters = VisitorCounter.query.filter_by(active=True).all()
        elif current_user.role.name == 'rd':
            subordinate_users = User.query.filter_by(supervisor_id=current_user.id, active=True).all()
            subordinate_user_ids = [user.id for user in subordinate_users] + [current_user.id]
            accessible_counters = VisitorCounter.query.filter(
                VisitorCounter.assigned_user_id.in_(subordinate_user_ids),
                VisitorCounter.active == True
            ).all()
        elif current_user.role.name == 'tu':
            accessible_counters = VisitorCounter.query.filter_by(
                assigned_user_id=current_user.id, active=True
            ).all()
        else:
            accessible_counters = VisitorCounter.query.filter_by(
                assigned_user_id=current_user.id, active=True
            ).limit(2).all()
        
        counter_ids = [counter.id for counter in accessible_counters]
        
        # Date range
        if period == 'week':
            start_date = datetime.now(timezone.utc) - timedelta(days=7)
            filename = f"visitor_report_week_{datetime.now().strftime('%Y%m%d')}.xlsx"
        elif period == 'month':
            start_date = datetime.now(timezone.utc) - timedelta(days=30)
            filename = f"visitor_report_month_{datetime.now().strftime('%Y%m%d')}.xlsx"
        else:
            start_date = datetime.now(timezone.utc) - timedelta(days=7)
            filename = f"visitor_report_{datetime.now().strftime('%Y%m%d')}.xlsx"
        
        # Get data for accessible counters only
        data = db.session.query(
            VisitorData.timestamp,
            Store.name.label('store_name'),
            VisitorCounter.name.label('counter_name'),
            VisitorData.entries,
            VisitorData.exits,
            VisitorData.current_occupancy
        ).join(VisitorCounter).join(Store).filter(
            VisitorData.counter_id.in_(counter_ids) if counter_ids else False,
            VisitorData.timestamp >= start_date
        ).order_by(VisitorData.timestamp.desc()).all()
        
        # Create DataFrame
        df = pd.DataFrame([{
            'Дата и время': row.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            'Магазин': row.store_name,
            'Счетчик': row.counter_name,
            'Вход': row.entries,
            'Выход': row.exits,
            'Текущая посещаемость': row.current_occupancy
        } for row in data])
        
        # Create Excel file
        output = io.BytesIO()
        
        # Use xlsxwriter engine directly
        import xlsxwriter
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        
        # Main data worksheet
        worksheet1 = workbook.add_worksheet('Данные посетителей')
        
        # Write headers
        headers = ['Дата и время', 'Магазин', 'Счетчик', 'Вход', 'Выход', 'Текущая посещаемость']
        for col, header in enumerate(headers):
            worksheet1.write(0, col, header)
        
        # Write data
        for row_num, row in enumerate(data, 1):
            worksheet1.write(row_num, 0, row.timestamp.strftime('%Y-%m-%d %H:%M:%S'))
            worksheet1.write(row_num, 1, row.store_name)
            worksheet1.write(row_num, 2, row.counter_name)
            worksheet1.write(row_num, 3, row.entries)
            worksheet1.write(row_num, 4, row.exits)
            worksheet1.write(row_num, 5, row.current_occupancy)
        
        # Summary worksheet
        worksheet2 = workbook.add_worksheet('Сводка')
        summary_data = [
            ['Период', period],
            ['Дата экспорта', datetime.now().strftime('%Y-%m-%d %H:%M:%S')],
            ['Пользователь', current_user.username],
            ['Роль', current_user.role.description],
            ['Всего записей', len(data)],
            ['Всего посетителей', sum(row.entries for row in data)],
            ['Доступных счетчиков', len(accessible_counters)]
        ]
        
        for row_num, (label, value) in enumerate(summary_data):
            worksheet2.write(row_num, 0, label)
            worksheet2.write(row_num, 1, str(value))
        
        workbook.close()
        output.seek(0)
        
        return send_file(
            output,
            as_attachment=True,
            download_name=filename,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        
    except Exception as e:
        logger.error(f"Error exporting to Excel: {e}")
        return jsonify({'error': 'Ошибка при экспорте данных'}), 500

@app.route('/api/metrics')
def api_metrics():
    """API endpoint for real-time metrics"""
    try:
        # Get basic counts
        total_stores = Store.query.count()
        total_counters = VisitorCounter.query.count()
        active_alerts = Alert.query.filter_by(is_resolved=False).count()
        
        # Get visitor data from last 24 hours
        yesterday = datetime.now(timezone.utc) - timedelta(days=1)
        recent_data = VisitorData.query.filter(VisitorData.timestamp >= yesterday).all()
        
        total_visitors = sum(data.entries for data in recent_data)
        current_occupancy = sum(data.current_occupancy for data in recent_data)
        
        # Format numbers
        def format_number(num):
            return f"{num:,}".replace(',', ' ')
        
        metrics = {
            'total_visitors': format_number(total_visitors),
            'current_occupancy': format_number(current_occupancy),
            'total_stores': total_stores,
            'total_counters': total_counters,
            'online_counters': 0,  # TODO: Implement real-time status
            'active_alerts': active_alerts
        }
        
        return jsonify({
            'success': True,
            'metrics': metrics
        })
    except Exception as e:
        logger.error(f"Error getting metrics: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/health')
def health_check():
    """Health check endpoint"""
    try:
        # Test database connection
        db.session.execute(db.text('SELECT 1'))
        return jsonify({
            'status': 'healthy',
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'database': 'connected'
        }), 200
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return jsonify({
            'status': 'unhealthy',
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'error': str(e)
        }), 500

def initialize_database():
    """Initialize database with tables and default data"""
    try:
        with app.app_context():
            # Create all tables
            db.create_all()
            logger.info("Database tables created successfully")
            
            # Create default admin user
            create_default_admin()
            
            # Initialize sample data if needed
            if User.query.count() <= 1:  # Only admin exists
                logger.info("Initializing sample data...")
                import init_data
                init_data.create_sample_data()
                logger.info("Sample data created successfully")
            
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
        raise

# Initialize database when module is imported
initialize_database()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)