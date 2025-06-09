import dash
from dash import dcc, html, Input, Output, State, callback_context, ALL
import dash_bootstrap_components as dbc
from dash.exceptions import PreventUpdate
import pandas as pd
from datetime import datetime, timedelta
from database import db
from database.models import User, Role, Store, VisitorCounter, Alert, AuditLog
from utils.auth import hash_password
import logging

logger = logging.getLogger(__name__)

def layout():
    """Admin panel layout"""
    return html.Div([
        # Admin navigation tabs
        dcc.Tabs(
            id='admin-tabs',
            value='users-tab',
            className='custom-tabs mb-4',
            children=[
                dcc.Tab(label='Пользователи', value='users-tab', className='custom-tab'),
                dcc.Tab(label='Магазины', value='stores-tab', className='custom-tab'),
                dcc.Tab(label='Счетчики', value='counters-tab', className='custom-tab'),
                dcc.Tab(label='Алерты', value='alerts-tab', className='custom-tab'),
                dcc.Tab(label='Аудит', value='audit-tab', className='custom-tab'),
                dcc.Tab(label='Система', value='system-tab', className='custom-tab'),
            ]
        ),
        
        # Tab content
        html.Div(id='admin-tab-content'),
        
        # Modals
        html.Div(id='admin-modals'),
        
        # Toast notifications
        html.Div(id='admin-notifications', style={'position': 'fixed', 'top': 20, 'right': 20, 'z-index': 9999})
    ])

def users_tab_content():
    """Users management tab"""
    return html.Div([
        # Users header
        dbc.Row([
            dbc.Col([
                html.H4("Управление пользователями", className="mb-0")
            ], width=8),
            dbc.Col([
                dbc.Button(
                    [html.I(className="fas fa-plus me-2"), "Добавить пользователя"],
                    id="add-user-button",
                    color="primary",
                    className="float-end"
                )
            ], width=4)
        ], className="mb-4"),
        
        # Users filters
        dbc.Card([
            dbc.CardBody([
                dbc.Row([
                    dbc.Col([
                        dcc.Dropdown(
                            id="user-role-filter",
                            placeholder="Фильтр по роли...",
                            options=[],
                            className="mb-2"
                        )
                    ], width=3),
                    dbc.Col([
                        dcc.Dropdown(
                            id="user-status-filter",
                            placeholder="Статус...",
                            options=[
                                {'label': 'Активные', 'value': True},
                                {'label': 'Неактивные', 'value': False}
                            ],
                            value=True,
                            className="mb-2"
                        )
                    ], width=3),
                    dbc.Col([
                        dbc.InputGroup([
                            dbc.Input(id="user-search", placeholder="Поиск по имени или email..."),
                            dbc.Button("Поиск", id="user-search-button", color="outline-secondary")
                        ])
                    ], width=6)
                ])
            ])
        ], className="mb-4"),
        
        # Users table
        html.Div(id="users-table-container"),
        
        # User form modal
        dbc.Modal([
            dbc.ModalHeader(dbc.ModalTitle(id="user-modal-title")),
            dbc.ModalBody([
                dbc.Form([
                    dbc.Row([
                        dbc.Col([
                            dbc.Label("Имя пользователя *"),
                            dbc.Input(id="user-username", type="text", required=True)
                        ], width=6),
                        dbc.Col([
                            dbc.Label("Email *"),
                            dbc.Input(id="user-email", type="email", required=True)
                        ], width=6)
                    ], className="mb-3"),
                    
                    dbc.Row([
                        dbc.Col([
                            dbc.Label("Имя"),
                            dbc.Input(id="user-first-name", type="text")
                        ], width=6),
                        dbc.Col([
                            dbc.Label("Фамилия"),
                            dbc.Input(id="user-last-name", type="text")
                        ], width=6)
                    ], className="mb-3"),
                    
                    dbc.Row([
                        dbc.Col([
                            dbc.Label("Роль *"),
                            dcc.Dropdown(id="user-role", options=[], required=True)
                        ], width=6),
                        dbc.Col([
                            dbc.Label("Руководитель"),
                            dcc.Dropdown(id="user-supervisor", options=[])
                        ], width=6)
                    ], className="mb-3"),
                    
                    dbc.Row([
                        dbc.Col([
                            dbc.Label("Телефон"),
                            dbc.Input(id="user-phone", type="tel")
                        ], width=6),
                        dbc.Col([
                            dbc.Label("Пароль"),
                            dbc.Input(id="user-password", type="password", placeholder="Оставьте пустым для сохранения текущего")
                        ], width=6)
                    ], className="mb-3"),
                    
                    dbc.Checklist(
                        id="user-active",
                        options=[{'label': 'Активный пользователь', 'value': True}],
                        value=[True]
                    )
                ])
            ]),
            dbc.ModalFooter([
                dbc.Button("Отмена", id="user-cancel-button", color="secondary", className="me-2"),
                dbc.Button("Сохранить", id="user-save-button", color="primary")
            ])
        ], id="user-modal", size="lg", is_open=False),
        
        # Store user ID for editing
        dcc.Store(id="editing-user-id")
    ])

def stores_tab_content():
    """Stores management tab"""
    return html.Div([
        dbc.Row([
            dbc.Col([
                html.H4("Управление магазинами", className="mb-0")
            ], width=8),
            dbc.Col([
                dbc.Button(
                    [html.I(className="fas fa-plus me-2"), "Добавить магазин"],
                    id="add-store-button",
                    color="primary",
                    className="float-end"
                )
            ], width=4)
        ], className="mb-4"),
        
        html.Div(id="stores-table-container"),
        
        # Store modal
        dbc.Modal([
            dbc.ModalHeader(dbc.ModalTitle(id="store-modal-title")),
            dbc.ModalBody([
                dbc.Form([
                    dbc.Row([
                        dbc.Col([
                            dbc.Label("Название магазина *"),
                            dbc.Input(id="store-name", required=True)
                        ], width=8),
                        dbc.Col([
                            dbc.Label("Код магазина *"),
                            dbc.Input(id="store-code", required=True)
                        ], width=4)
                    ], className="mb-3"),
                    
                    dbc.Row([
                        dbc.Col([
                            dbc.Label("Адрес"),
                            dbc.Textarea(id="store-address", rows=2)
                        ], width=12)
                    ], className="mb-3"),
                    
                    dbc.Row([
                        dbc.Col([
                            dbc.Label("Город"),
                            dbc.Input(id="store-city")
                        ], width=6),
                        dbc.Col([
                            dbc.Label("Регион"),
                            dbc.Input(id="store-region")
                        ], width=6)
                    ], className="mb-3"),
                    
                    dbc.Row([
                        dbc.Col([
                            dbc.Label("Телефон"),
                            dbc.Input(id="store-phone", type="tel")
                        ], width=6),
                        dbc.Col([
                            dbc.Label("Email"),
                            dbc.Input(id="store-email", type="email")
                        ], width=6)
                    ], className="mb-3"),
                    
                    dbc.Row([
                        dbc.Col([
                            dbc.Label("Менеджер"),
                            dbc.Input(id="store-manager")
                        ], width=6),
                        dbc.Col([
                            dbc.Label("Часы работы"),
                            dbc.Input(id="store-hours", placeholder="9:00 - 22:00")
                        ], width=6)
                    ], className="mb-3"),
                    
                    dbc.Checklist(
                        id="store-active",
                        options=[{'label': 'Активный магазин', 'value': True}],
                        value=[True]
                    )
                ])
            ]),
            dbc.ModalFooter([
                dbc.Button("Отмена", id="store-cancel-button", color="secondary", className="me-2"),
                dbc.Button("Сохранить", id="store-save-button", color="primary")
            ])
        ], id="store-modal", size="lg", is_open=False),
        
        dcc.Store(id="editing-store-id")
    ])

def counters_tab_content():
    """Counters management tab"""
    return html.Div([
        dbc.Row([
            dbc.Col([
                html.H4("Управление счетчиками", className="mb-0")
            ], width=8),
            dbc.Col([
                dbc.Button(
                    [html.I(className="fas fa-plus me-2"), "Добавить счетчик"],
                    id="add-counter-button",
                    color="primary",
                    className="float-end"
                )
            ], width=4)
        ], className="mb-4"),
        
        html.Div(id="counters-table-container"),
        
        # Counter modal
        dbc.Modal([
            dbc.ModalHeader(dbc.ModalTitle(id="counter-modal-title")),
            dbc.ModalBody([
                dbc.Form([
                    dbc.Row([
                        dbc.Col([
                            dbc.Label("Название счетчика *"),
                            dbc.Input(id="counter-name", required=True)
                        ], width=8),
                        dbc.Col([
                            dbc.Label("ID устройства *"),
                            dbc.Input(id="counter-device-id", required=True)
                        ], width=4)
                    ], className="mb-3"),
                    
                    dbc.Row([
                        dbc.Col([
                            dbc.Label("Магазин *"),
                            dcc.Dropdown(id="counter-store", required=True)
                        ], width=6),
                        dbc.Col([
                            dbc.Label("Тип счетчика"),
                            dcc.Dropdown(
                                id="counter-type",
                                options=[
                                    {'label': 'Двунаправленный', 'value': 'bidirectional'},
                                    {'label': 'Только вход', 'value': 'entrance_only'},
                                    {'label': 'Только выход', 'value': 'exit_only'},
                                    {'label': 'Турникет', 'value': 'turnstile'},
                                    {'label': 'Тепловизионная камера', 'value': 'thermal_camera'}
                                ],
                                value='bidirectional'
                            )
                        ], width=6)
                    ], className="mb-3"),
                    
                    dbc.Row([
                        dbc.Col([
                            dbc.Label("Описание расположения"),
                            dbc.Textarea(id="counter-location", rows=2)
                        ], width=12)
                    ], className="mb-3"),
                    
                    dbc.Row([
                        dbc.Col([
                            dbc.Label("Ответственный"),
                            dcc.Dropdown(id="counter-assigned-user")
                        ], width=6),
                        dbc.Col([
                            dbc.Label("Версия прошивки"),
                            dbc.Input(id="counter-firmware")
                        ], width=6)
                    ], className="mb-3"),
                    
                    dbc.Checklist(
                        id="counter-active",
                        options=[{'label': 'Активный счетчик', 'value': True}],
                        value=[True]
                    )
                ])
            ]),
            dbc.ModalFooter([
                dbc.Button("Отмена", id="counter-cancel-button", color="secondary", className="me-2"),
                dbc.Button("Сохранить", id="counter-save-button", color="primary")
            ])
        ], id="counter-modal", size="lg", is_open=False),
        
        dcc.Store(id="editing-counter-id")
    ])

def alerts_tab_content():
    """Alerts management tab"""
    return html.Div([
        html.H4("Управление алертами", className="mb-4"),
        
        # Alert filters
        dbc.Card([
            dbc.CardBody([
                dbc.Row([
                    dbc.Col([
                        dcc.Dropdown(
                            id="alert-severity-filter",
                            placeholder="Уровень важности...",
                            options=[
                                {'label': 'Критический', 'value': 'critical'},
                                {'label': 'Высокий', 'value': 'high'},
                                {'label': 'Средний', 'value': 'medium'},
                                {'label': 'Низкий', 'value': 'low'}
                            ]
                        )
                    ], width=3),
                    dbc.Col([
                        dcc.Dropdown(
                            id="alert-status-filter",
                            placeholder="Статус...",
                            options=[
                                {'label': 'Активные', 'value': False},
                                {'label': 'Решенные', 'value': True}
                            ],
                            value=False
                        )
                    ], width=3),
                    dbc.Col([
                        dbc.Button("Обновить", id="refresh-alerts-button", color="primary")
                    ], width=2)
                ])
            ])
        ], className="mb-4"),
        
        html.Div(id="alerts-table-container")
    ])

def audit_tab_content():
    """Audit log tab"""
    return html.Div([
        html.H4("Журнал аудита", className="mb-4"),
        
        dbc.Card([
            dbc.CardBody([
                dbc.Row([
                    dbc.Col([
                        dcc.DatePickerRange(
                            id="audit-date-range",
                            start_date=datetime.now().date() - timedelta(days=7),
                            end_date=datetime.now().date(),
                            display_format="DD.MM.YYYY"
                        )
                    ], width=4),
                    dbc.Col([
                        dcc.Dropdown(
                            id="audit-user-filter",
                            placeholder="Пользователь...",
                            options=[]
                        )
                    ], width=4),
                    dbc.Col([
                        dbc.Button("Обновить", id="refresh-audit-button", color="primary")
                    ], width=2)
                ])
            ])
        ], className="mb-4"),
        
        html.Div(id="audit-table-container")
    ])

def system_tab_content():
    """System information tab"""
    return html.Div([
        html.H4("Системная информация", className="mb-4"),
        
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader("Статистика системы"),
                    dbc.CardBody(id="system-stats")
                ])
            ], width=6),
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader("Производительность"),
                    dbc.CardBody(id="system-performance")
                ])
            ], width=6)
        ], className="mb-4"),
        
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader("Действия системы"),
                    dbc.CardBody([
                        dbc.ButtonGroup([
                            dbc.Button("Очистить кэш", id="clear-cache-button", color="warning", outline=True),
                            dbc.Button("Оптимизировать БД", id="optimize-db-button", color="info", outline=True),
                            dbc.Button("Создать резервную копию", id="backup-db-button", color="success", outline=True)
                        ], className="mb-3"),
                        html.Div(id="system-actions-result")
                    ])
                ])
            ], width=12)
        ])
    ])

def register_callbacks(app):
    """Register admin panel callbacks"""
    
    @app.callback(
        Output('admin-tab-content', 'children'),
        Input('admin-tabs', 'value')
    )
    def render_admin_tab_content(active_tab):
        """Render active admin tab content"""
        if active_tab == 'users-tab':
            return users_tab_content()
        elif active_tab == 'stores-tab':
            return stores_tab_content()
        elif active_tab == 'counters-tab':
            return counters_tab_content()
        elif active_tab == 'alerts-tab':
            return alerts_tab_content()
        elif active_tab == 'audit-tab':
            return audit_tab_content()
        elif active_tab == 'system-tab':
            return system_tab_content()
        return html.Div("Выберите вкладку")
    
    # Users tab callbacks
    @app.callback(
        [Output('user-role-filter', 'options'),
         Output('user-role', 'options'),
         Output('user-supervisor', 'options')],
        Input('admin-tabs', 'value')
    )
    def update_user_dropdowns(active_tab):
        """Update user-related dropdowns"""
        if active_tab != 'users-tab':
            return [], [], []
        
        try:
            # Role options
            roles = Role.query.all()
            role_options = [{'label': f"{role.name.upper()} - {role.description}", 'value': role.id} for role in roles]
            
            # Supervisor options (users with RD or admin roles)
            supervisors = User.query.join(Role).filter(
                Role.level >= 2, User.active == True
            ).all()
            supervisor_options = [{'label': f"{user.full_name} ({user.username})", 'value': user.id} for user in supervisors]
            
            return role_options, role_options, supervisor_options
            
        except Exception as e:
            logger.error(f"Error updating user dropdowns: {e}")
            return [], [], []
    
    @app.callback(
        Output('users-table-container', 'children'),
        [Input('user-search-button', 'n_clicks'),
         Input('user-role-filter', 'value'),
         Input('user-status-filter', 'value')],
        State('user-search', 'value')
    )
    def update_users_table(n_clicks, role_filter, status_filter, search_term):
        """Update users table"""
        try:
            query = User.query.join(Role)
            
            if role_filter:
                query = query.filter(User.role_id == role_filter)
            if status_filter is not None:
                query = query.filter(User.active == status_filter)
            if search_term:
                query = query.filter(
                    db.or_(
                        User.username.ilike(f"%{search_term}%"),
                        User.email.ilike(f"%{search_term}%"),
                        User.first_name.ilike(f"%{search_term}%"),
                        User.last_name.ilike(f"%{search_term}%")
                    )
                )
            
            users = query.order_by(User.created_at.desc()).all()
            
            if not users:
                return dbc.Alert("Пользователи не найдены", color="info")
            
            rows = []
            for user in users:
                status_badge = dbc.Badge("Активен", color="success") if user.active else dbc.Badge("Неактивен", color="secondary")
                
                rows.append(
                    html.Tr([
                        html.Td(user.username),
                        html.Td(user.full_name),
                        html.Td(user.email),
                        html.Td(user.role.name.upper()),
                        html.Td(user.supervisor.full_name if user.supervisor else "—"),
                        html.Td(status_badge),
                        html.Td(user.last_login.strftime("%d.%m.%Y %H:%M") if user.last_login else "Никогда"),
                        html.Td([
                            dbc.ButtonGroup([
                                dbc.Button([html.I(className="fas fa-edit")], 
                                         id={'type': 'edit-user', 'index': user.id},
                                         color="primary", size="sm", outline=True),
                                dbc.Button([html.I(className="fas fa-trash")], 
                                         id={'type': 'delete-user', 'index': user.id},
                                         color="danger", size="sm", outline=True)
                            ], size="sm")
                        ])
                    ])
                )
            
            table = dbc.Table([
                html.Thead([
                    html.Tr([
                        html.Th("Логин"),
                        html.Th("ФИО"),
                        html.Th("Email"),
                        html.Th("Роль"),
                        html.Th("Руководитель"),
                        html.Th("Статус"),
                        html.Th("Последний вход"),
                        html.Th("Действия")
                    ])
                ]),
                html.Tbody(rows)
            ], striped=True, bordered=True, hover=True, responsive=True)
            
            return table
            
        except Exception as e:
            logger.error(f"Error updating users table: {e}")
            return dbc.Alert("Ошибка загрузки пользователей", color="danger")
    
    @app.callback(
        [Output('user-modal', 'is_open'),
         Output('user-modal-title', 'children'),
         Output('editing-user-id', 'data')],
        [Input('add-user-button', 'n_clicks'),
         Input({'type': 'edit-user', 'index': ALL}, 'n_clicks'),
         Input('user-cancel-button', 'n_clicks'),
         Input('user-save-button', 'n_clicks')],
        State('user-modal', 'is_open')
    )
    def toggle_user_modal(add_clicks, edit_clicks, cancel_clicks, save_clicks, is_open):
        """Toggle user modal"""
        ctx = callback_context
        if not ctx.triggered:
            return False, "", None
        
        trigger = ctx.triggered[0]['prop_id']
        
        if 'add-user-button' in trigger:
            return True, "Добавить пользователя", None
        elif 'edit-user' in trigger:
            user_id = ctx.triggered[0]['prop_id'].split('"index":')[1].split('}')[0]
            return True, "Редактировать пользователя", int(user_id)
        elif any([cancel_clicks, save_clicks]):
            return False, "", None
        
        return is_open, "", None
    
    # Similar callbacks for stores, counters, alerts, and audit tabs...
    # (Implementation would follow the same pattern)
    
    @app.callback(
        Output('system-stats', 'children'),
        Input('admin-tabs', 'value')
    )
    def update_system_stats(active_tab):
        """Update system statistics"""
        if active_tab != 'system-tab':
            return ""
        
        try:
            # Get counts
            total_users = User.query.count()
            active_users = User.query.filter_by(active=True).count()
            total_stores = Store.query.count()
            active_stores = Store.query.filter_by(active=True).count()
            total_counters = VisitorCounter.query.count()
            active_counters = VisitorCounter.query.filter_by(active=True).count()
            unresolved_alerts = Alert.query.filter_by(is_resolved=False).count()
            
            return [
                html.P([html.Strong("Пользователи: "), f"{active_users}/{total_users}"]),
                html.P([html.Strong("Магазины: "), f"{active_stores}/{total_stores}"]),
                html.P([html.Strong("Счетчики: "), f"{active_counters}/{total_counters}"]),
                html.P([html.Strong("Активные алерты: "), str(unresolved_alerts)]),
                html.Hr(),
                html.P([html.Strong("Версия системы: "), "1.0.0"]),
                html.P([html.Strong("Последний перезапуск: "), datetime.now().strftime("%d.%m.%Y %H:%M")])
            ]
            
        except Exception as e:
            logger.error(f"Error updating system stats: {e}")
            return dbc.Alert("Ошибка загрузки статистики", color="danger")
