#!/usr/bin/env python3
"""
Email reporting system for visitor counter management
"""

import os
import logging
from datetime import datetime, timedelta, timezone
from flask import Blueprint, render_template_string, request, redirect, url_for, flash, jsonify
from database import db
from database.models import User, Store, VisitorCounter, VisitorData, Alert
from auth_routes import login_required, admin_required, get_current_user
import pandas as pd
import io
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
# import schedule
import threading
import time

logger = logging.getLogger(__name__)

reports_bp = Blueprint('reports', __name__, url_prefix='/reports')

# Email configuration
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
EMAIL_FROM = os.environ.get("EMAIL_FROM", "reports@company.com")
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD", "")

# Report scheduling storage (in production use Redis or database)
scheduled_reports = {}

def send_email_report(recipient_email, subject, html_content, excel_data=None, filename=None):
    """Send email report with optional Excel attachment"""
    try:
        if not EMAIL_PASSWORD:
            logger.error("EMAIL_PASSWORD not configured")
            return False
        
        msg = MIMEMultipart()
        msg['From'] = EMAIL_FROM
        msg['To'] = recipient_email
        msg['Subject'] = subject
        
        # Add HTML content
        msg.attach(MIMEText(html_content, 'html'))
        
        # Add Excel attachment if provided
        if excel_data and filename:
            part = MIMEBase('application', 'octet-stream')
            part.set_payload(excel_data)
            encoders.encode_base64(part)
            part.add_header(
                'Content-Disposition',
                f'attachment; filename= {filename}'
            )
            msg.attach(part)
        
        # Send email
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(EMAIL_FROM, EMAIL_PASSWORD)
        text = msg.as_string()
        server.sendmail(EMAIL_FROM, recipient_email, text)
        server.quit()
        
        logger.info(f"Email report sent to {recipient_email}")
        return True
        
    except Exception as e:
        logger.error(f"Error sending email report: {e}")
        return False

def generate_report_data(start_date, end_date, store_ids=None, counter_ids=None):
    """Generate report data for specified period and filters"""
    query = db.session.query(
        VisitorData.timestamp,
        Store.name.label('store_name'),
        VisitorCounter.name.label('counter_name'),
        VisitorData.entries,
        VisitorData.exits,
        VisitorData.current_occupancy
    ).join(VisitorCounter).join(Store).filter(
        VisitorData.timestamp >= start_date,
        VisitorData.timestamp <= end_date
    )
    
    if store_ids:
        query = query.filter(Store.id.in_(store_ids))
    
    if counter_ids:
        query = query.filter(VisitorCounter.id.in_(counter_ids))
    
    data = query.order_by(VisitorData.timestamp.desc()).all()
    
    # Calculate summary statistics
    total_visitors = sum(row.entries for row in data)
    total_stores = len(set(row.store_name for row in data))
    total_counters = len(set(row.counter_name for row in data))
    avg_occupancy = sum(row.current_occupancy for row in data) / len(data) if data else 0
    
    return {
        'data': data,
        'summary': {
            'total_visitors': total_visitors,
            'total_stores': total_stores,
            'total_counters': total_counters,
            'avg_occupancy': round(avg_occupancy, 1),
            'period_start': start_date.strftime('%Y-%m-%d'),
            'period_end': end_date.strftime('%Y-%m-%d')
        }
    }

def create_excel_report(report_data):
    """Create Excel report from data"""
    output = io.BytesIO()
    
    # Convert data to DataFrame
    df = pd.DataFrame([{
        'Дата и время': row.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
        'Магазин': row.store_name,
        'Счетчик': row.counter_name,
        'Вход': row.entries,
        'Выход': row.exits,
        'Текущая посещаемость': row.current_occupancy
    } for row in report_data['data']])
    
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        # Main data sheet
        df.to_excel(writer, sheet_name='Данные посетителей', index=False)
        
        # Summary sheet
        summary_df = pd.DataFrame([{
            'Показатель': 'Всего посетителей',
            'Значение': report_data['summary']['total_visitors']
        }, {
            'Показатель': 'Магазинов',
            'Значение': report_data['summary']['total_stores']
        }, {
            'Показатель': 'Счетчиков',
            'Значение': report_data['summary']['total_counters']
        }, {
            'Показатель': 'Средняя посещаемость',
            'Значение': report_data['summary']['avg_occupancy']
        }, {
            'Показатель': 'Период с',
            'Значение': report_data['summary']['period_start']
        }, {
            'Показатель': 'Период по',
            'Значение': report_data['summary']['period_end']
        }])
        summary_df.to_excel(writer, sheet_name='Сводка', index=False)
    
    output.seek(0)
    return output.getvalue()

EMAIL_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; color: #333; }
        .header { background-color: #007bff; color: white; padding: 20px; text-align: center; }
        .content { padding: 20px; }
        .summary { background-color: #f8f9fa; padding: 15px; margin: 20px 0; border-radius: 5px; }
        .metric { display: inline-block; margin: 10px 20px; text-align: center; }
        .metric-value { font-size: 24px; font-weight: bold; color: #007bff; }
        .metric-label { font-size: 14px; color: #666; }
        table { width: 100%; border-collapse: collapse; margin-top: 20px; }
        th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
        th { background-color: #f2f2f2; }
        .footer { margin-top: 30px; padding-top: 20px; border-top: 1px solid #ddd; font-size: 12px; color: #666; }
    </style>
</head>
<body>
    <div class="header">
        <h1>Отчет по посещаемости</h1>
        <p>Период: {{ summary.period_start }} - {{ summary.period_end }}</p>
    </div>
    
    <div class="content">
        <div class="summary">
            <h2>Сводная информация</h2>
            <div class="metric">
                <div class="metric-value">{{ summary.total_visitors }}</div>
                <div class="metric-label">Всего посетителей</div>
            </div>
            <div class="metric">
                <div class="metric-value">{{ summary.total_stores }}</div>
                <div class="metric-label">Магазинов</div>
            </div>
            <div class="metric">
                <div class="metric-value">{{ summary.total_counters }}</div>
                <div class="metric-label">Счетчиков</div>
            </div>
            <div class="metric">
                <div class="metric-value">{{ summary.avg_occupancy }}</div>
                <div class="metric-label">Средняя посещаемость</div>
            </div>
        </div>
        
        <h2>Детальные данные</h2>
        <p>Полный отчет с детальными данными прикреплен в виде Excel файла.</p>
        
        {% if recent_alerts %}
        <h2>Активные алерты</h2>
        <table>
            <tr>
                <th>Дата</th>
                <th>Счетчик</th>
                <th>Тип</th>
                <th>Сообщение</th>
            </tr>
            {% for alert in recent_alerts %}
            <tr>
                <td>{{ alert.created_at.strftime('%d.%m.%Y %H:%M') }}</td>
                <td>{{ alert.counter.name }}</td>
                <td>{{ alert.alert_type }}</td>
                <td>{{ alert.message }}</td>
            </tr>
            {% endfor %}
        </table>
        {% endif %}
    </div>
    
    <div class="footer">
        <p>Отчет сгенерирован автоматически системой управления счетчиками посетителей</p>
        <p>Дата создания: {{ generation_time }}</p>
    </div>
</body>
</html>
"""

@reports_bp.route('/schedule')
@admin_required
def schedule_reports():
    """Configure scheduled reports"""
    users = User.query.filter_by(active=True).all()
    stores = Store.query.filter_by(active=True).all()
    
    template = """
    <!DOCTYPE html>
    <html lang="ru">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Настройка отчетов</title>
        <link href="https://cdn.replit.com/agent/bootstrap-agent-dark-theme.min.css" rel="stylesheet">
        <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    </head>
    <body>
        <nav class="navbar navbar-dark bg-dark">
            <div class="container-fluid">
                <a class="navbar-brand" href="/">
                    <i class="fas fa-tachometer-alt me-2"></i>Система управления счетчиками
                </a>
                <a class="nav-link" href="/admin">
                    <i class="fas fa-arrow-left me-2"></i>Назад к админ-панели
                </a>
            </div>
        </nav>
        
        <div class="container mt-4">
            <h2>Настройка автоматических отчетов</h2>
            
            <div class="card">
                <div class="card-header">
                    <h5>Создать новый автоматический отчет</h5>
                </div>
                <div class="card-body">
                    <form method="POST" action="/reports/create-schedule">
                        <div class="row">
                            <div class="col-md-6">
                                <div class="mb-3">
                                    <label class="form-label">Название отчета</label>
                                    <input type="text" class="form-control" name="report_name" required>
                                </div>
                            </div>
                            <div class="col-md-6">
                                <div class="mb-3">
                                    <label class="form-label">Email получателя</label>
                                    <select class="form-select" name="recipient_email" required>
                                        {% for user in users %}
                                        <option value="{{ user.email }}">{{ user.username }} ({{ user.email }})</option>
                                        {% endfor %}
                                    </select>
                                </div>
                            </div>
                        </div>
                        
                        <div class="row">
                            <div class="col-md-6">
                                <div class="mb-3">
                                    <label class="form-label">Частота отправки</label>
                                    <select class="form-select" name="frequency" required>
                                        <option value="daily">Ежедневно</option>
                                        <option value="weekly">Еженедельно</option>
                                        <option value="monthly">Ежемесячно</option>
                                    </select>
                                </div>
                            </div>
                            <div class="col-md-6">
                                <div class="mb-3">
                                    <label class="form-label">Время отправки</label>
                                    <input type="time" class="form-control" name="send_time" value="09:00" required>
                                </div>
                            </div>
                        </div>
                        
                        <div class="mb-3">
                            <label class="form-label">Магазины (оставьте пустым для всех)</label>
                            <select class="form-select" name="store_ids" multiple>
                                {% for store in stores %}
                                <option value="{{ store.id }}">{{ store.name }}</option>
                                {% endfor %}
                            </select>
                        </div>
                        
                        <div class="form-check mb-3">
                            <input class="form-check-input" type="checkbox" name="include_alerts" checked>
                            <label class="form-check-label">Включать активные алерты в отчет</label>
                        </div>
                        
                        <button type="submit" class="btn btn-primary">
                            <i class="fas fa-plus me-2"></i>Создать расписание
                        </button>
                    </form>
                </div>
            </div>
            
            <div class="card mt-4">
                <div class="card-header">
                    <h5>Быстрая отправка отчета</h5>
                </div>
                <div class="card-body">
                    <form method="POST" action="/reports/send-now">
                        <div class="row">
                            <div class="col-md-4">
                                <div class="mb-3">
                                    <label class="form-label">Email получателя</label>
                                    <select class="form-select" name="recipient_email" required>
                                        {% for user in users %}
                                        <option value="{{ user.email }}">{{ user.username }} ({{ user.email }})</option>
                                        {% endfor %}
                                    </select>
                                </div>
                            </div>
                            <div class="col-md-4">
                                <div class="mb-3">
                                    <label class="form-label">Период</label>
                                    <select class="form-select" name="period" required>
                                        <option value="today">Сегодня</option>
                                        <option value="yesterday">Вчера</option>
                                        <option value="week">Последняя неделя</option>
                                        <option value="month">Последний месяц</option>
                                    </select>
                                </div>
                            </div>
                            <div class="col-md-4">
                                <div class="mb-3">
                                    <label class="form-label">&nbsp;</label>
                                    <button type="submit" class="btn btn-success w-100">
                                        <i class="fas fa-paper-plane me-2"></i>Отправить сейчас
                                    </button>
                                </div>
                            </div>
                        </div>
                    </form>
                </div>
            </div>
        </div>
        
        <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    </body>
    </html>
    """
    
    return render_template_string(template, users=users, stores=stores)

@reports_bp.route('/send-now', methods=['POST'])
@admin_required
def send_report_now():
    """Send report immediately"""
    try:
        recipient_email = request.form.get('recipient_email')
        period = request.form.get('period')
        
        # Calculate date range
        now = datetime.now(timezone.utc)
        if period == 'today':
            start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = now
        elif period == 'yesterday':
            start_date = (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif period == 'week':
            start_date = now - timedelta(days=7)
            end_date = now
        elif period == 'month':
            start_date = now - timedelta(days=30)
            end_date = now
        else:
            start_date = now - timedelta(days=7)
            end_date = now
        
        # Generate report
        report_data = generate_report_data(start_date, end_date)
        excel_data = create_excel_report(report_data)
        
        # Get recent alerts
        recent_alerts = Alert.query.filter_by(is_resolved=False).order_by(
            Alert.created_at.desc()
        ).limit(10).all()
        
        # Create email content
        email_content = render_template_string(EMAIL_TEMPLATE,
                                             summary=report_data['summary'],
                                             recent_alerts=recent_alerts,
                                             generation_time=now.strftime('%Y-%m-%d %H:%M:%S'))
        
        filename = f"visitor_report_{period}_{now.strftime('%Y%m%d')}.xlsx"
        subject = f"Отчет по посещаемости - {period}"
        
        success = send_email_report(recipient_email, subject, email_content, excel_data, filename)
        
        if success:
            flash('Отчет успешно отправлен', 'success')
        else:
            flash('Ошибка при отправке отчета. Проверьте настройки email.', 'error')
        
    except Exception as e:
        logger.error(f"Error sending report: {e}")
        flash('Ошибка при создании отчета', 'error')
    
    return redirect(url_for('reports.schedule_reports'))

def start_scheduler():
    """Start the report scheduler in a separate thread"""
    # TODO: Implement scheduling when schedule module is available
    logger.info("Report scheduler placeholder - implement when schedule module available")