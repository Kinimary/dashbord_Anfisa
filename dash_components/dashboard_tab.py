import dash
from dash import dcc, html, Input, Output, State, callback_context
import dash_bootstrap_components as dbc
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
from datetime import datetime, timedelta
from database import db
from database.models import VisitorData, VisitorCounter, Store, Alert
import logging

logger = logging.getLogger(__name__)

def layout():
    """Main dashboard layout"""
    return html.Div([
        # Top metrics cards
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.Div([
                            html.I(className="fas fa-users fa-2x text-primary"),
                            html.Div([
                                html.H4(id="total-visitors-today", children="0", className="mb-0"),
                                html.P("Посетители сегодня", className="text-muted mb-0")
                            ], className="ms-3")
                        ], className="d-flex align-items-center")
                    ])
                ], className="h-100")
            ], width=3),
            
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.Div([
                            html.I(className="fas fa-chart-line fa-2x text-success"),
                            html.Div([
                                html.H4(id="current-occupancy", children="0", className="mb-0"),
                                html.P("Текущая заполненность", className="text-muted mb-0")
                            ], className="ms-3")
                        ], className="d-flex align-items-center")
                    ])
                ], className="h-100")
            ], width=3),
            
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.Div([
                            html.I(className="fas fa-exclamation-triangle fa-2x text-warning"),
                            html.Div([
                                html.H4(id="active-alerts", children="0", className="mb-0"),
                                html.P("Активные алерты", className="text-muted mb-0")
                            ], className="ms-3")
                        ], className="d-flex align-items-center")
                    ])
                ], className="h-100")
            ], width=3),
            
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.Div([
                            html.I(className="fas fa-wifi fa-2x text-info"),
                            html.Div([
                                html.H4(id="online-counters", children="0", className="mb-0"),
                                html.P("Счетчики онлайн", className="text-muted mb-0")
                            ], className="ms-3")
                        ], className="d-flex align-items-center")
                    ])
                ], className="h-100")
            ], width=3),
        ], className="mb-4"),
        
        # Filters section
        dbc.Card([
            dbc.CardBody([
                dbc.Row([
                    dbc.Col([
                        html.Label("Магазин:", className="form-label"),
                        dcc.Dropdown(
                            id="store-filter",
                            placeholder="Выберите магазин...",
                            className="mb-2"
                        )
                    ], width=3),
                    
                    dbc.Col([
                        html.Label("Счетчик:", className="form-label"),
                        dcc.Dropdown(
                            id="counter-filter",
                            placeholder="Выберите счетчик...",
                            className="mb-2"
                        )
                    ], width=3),
                    
                    dbc.Col([
                        html.Label("Период:", className="form-label"),
                        dcc.DatePickerRange(
                            id="date-range",
                            start_date=datetime.now().date() - timedelta(days=7),
                            end_date=datetime.now().date(),
                            display_format="DD.MM.YYYY",
                            className="mb-2"
                        )
                    ], width=4),
                    
                    dbc.Col([
                        html.Label("", className="form-label d-block"),
                        dbc.Button(
                            "Обновить",
                            id="refresh-button",
                            color="primary",
                            className="me-2"
                        ),
                        dbc.Button(
                            "Экспорт",
                            id="export-button",
                            color="secondary",
                            outline=True
                        )
                    ], width=2, className="d-flex align-items-end")
                ])
            ])
        ], className="mb-4"),
        
        # Charts section
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader([
                        html.H5("Динамика посещений", className="mb-0")
                    ]),
                    dbc.CardBody([
                        dcc.Graph(id="visitor-trend-chart", style={"height": "400px"})
                    ])
                ])
            ], width=8),
            
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader([
                        html.H5("Заполненность по часам", className="mb-0")
                    ]),
                    dbc.CardBody([
                        dcc.Graph(id="hourly-occupancy-chart", style={"height": "400px"})
                    ])
                ])
            ], width=4),
        ], className="mb-4"),
        
        # Real-time data and alerts
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader([
                        html.H5("Текущие данные по счетчикам", className="mb-0")
                    ]),
                    dbc.CardBody([
                        html.Div(id="counters-table")
                    ])
                ])
            ], width=8),
            
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader([
                        html.H5("Последние алерты", className="mb-0")
                    ]),
                    dbc.CardBody([
                        html.Div(id="alerts-list")
                    ])
                ])
            ], width=4),
        ]),
        
        # Auto-refresh interval
        dcc.Interval(
            id='interval-component',
            interval=30*1000,  # Update every 30 seconds
            n_intervals=0
        ),
        
        # Download component for export
        dcc.Download(id="download-data")
    ])

def register_callbacks(app):
    """Register all dashboard callbacks"""
    
    @app.callback(
        [Output('store-filter', 'options'),
         Output('store-filter', 'value')],
        Input('interval-component', 'n_intervals')
    )
    def update_store_options(n):
        """Update store dropdown options"""
        try:
            stores = Store.query.filter_by(active=True).all()
            options = [{'label': f"{store.name} ({store.store_code})", 'value': store.id} for store in stores]
            
            # Default to first store if none selected
            default_value = options[0]['value'] if options else None
            
            return options, default_value
        except Exception as e:
            logger.error(f"Error updating store options: {e}")
            return [], None
    
    @app.callback(
        [Output('counter-filter', 'options'),
         Output('counter-filter', 'value')],
        [Input('store-filter', 'value'),
         Input('interval-component', 'n_intervals')]
    )
    def update_counter_options(store_id, n):
        """Update counter dropdown based on selected store"""
        if not store_id:
            return [], None
        
        try:
            counters = VisitorCounter.query.filter_by(store_id=store_id, active=True).all()
            options = [{'label': counter.name, 'value': counter.id} for counter in counters]
            
            return options, None
        except Exception as e:
            logger.error(f"Error updating counter options: {e}")
            return [], None
    
    @app.callback(
        [Output('total-visitors-today', 'children'),
         Output('current-occupancy', 'children'),
         Output('active-alerts', 'children'),
         Output('online-counters', 'children')],
        [Input('interval-component', 'n_intervals'),
         Input('store-filter', 'value')]
    )
    def update_metrics(n, store_id):
        """Update top metrics cards"""
        try:
            today = datetime.now().date()
            
            # Build base query
            query = db.session.query(VisitorData).join(VisitorCounter)
            if store_id:
                query = query.filter(VisitorCounter.store_id == store_id)
            
            # Total visitors today
            today_data = query.filter(
                db.func.date(VisitorData.timestamp) == today
            ).all()
            
            total_entries = sum(d.entries for d in today_data)
            current_occupancy = sum(d.current_occupancy for d in today_data[-50:]) if today_data else 0  # Last 50 records
            
            # Active alerts
            alert_query = Alert.query.join(VisitorCounter).filter(Alert.is_resolved == False)
            if store_id:
                alert_query = alert_query.filter(VisitorCounter.store_id == store_id)
            active_alerts_count = alert_query.count()
            
            # Online counters (received data in last 30 minutes)
            thirty_min_ago = datetime.now() - timedelta(minutes=30)
            counter_query = VisitorCounter.query.filter(VisitorCounter.active == True)
            if store_id:
                counter_query = counter_query.filter(VisitorCounter.store_id == store_id)
            
            online_counters = counter_query.join(VisitorData).filter(
                VisitorData.timestamp >= thirty_min_ago
            ).distinct().count()
            
            return (
                f"{total_entries:,}",
                f"{current_occupancy:,}",
                str(active_alerts_count),
                str(online_counters)
            )
            
        except Exception as e:
            logger.error(f"Error updating metrics: {e}")
            return "0", "0", "0", "0"
    
    @app.callback(
        Output('visitor-trend-chart', 'figure'),
        [Input('refresh-button', 'n_clicks'),
         Input('interval-component', 'n_intervals'),
         Input('store-filter', 'value'),
         Input('counter-filter', 'value'),
         Input('date-range', 'start_date'),
         Input('date-range', 'end_date')]
    )
    def update_visitor_trend(n_clicks, n_intervals, store_id, counter_id, start_date, end_date):
        """Update visitor trend chart"""
        try:
            # Build query
            query = db.session.query(VisitorData).join(VisitorCounter)
            
            if store_id:
                query = query.filter(VisitorCounter.store_id == store_id)
            if counter_id:
                query = query.filter(VisitorData.counter_id == counter_id)
            if start_date:
                query = query.filter(VisitorData.timestamp >= start_date)
            if end_date:
                query = query.filter(VisitorData.timestamp <= end_date)
            
            data = query.order_by(VisitorData.timestamp).all()
            
            if not data:
                fig = go.Figure()
                fig.add_annotation(text="Нет данных для отображения", 
                                 xref="paper", yref="paper", x=0.5, y=0.5, 
                                 showarrow=False, font_size=16)
                fig.update_layout(
                    template="plotly_dark",
                    paper_bgcolor='rgba(0,0,0,0)',
                    plot_bgcolor='rgba(0,0,0,0)'
                )
                return fig
            
            # Create DataFrame
            df = pd.DataFrame([{
                'timestamp': d.timestamp,
                'entries': d.entries,
                'exits': d.exits,
                'occupancy': d.current_occupancy
            } for d in data])
            
            # Group by hour for better visualization
            df['hour'] = df['timestamp'].dt.floor('H')
            hourly_data = df.groupby('hour').agg({
                'entries': 'sum',
                'exits': 'sum',
                'occupancy': 'mean'
            }).reset_index()
            
            # Create figure
            fig = make_subplots(
                rows=2, cols=1,
                subplot_titles=('Входы и выходы', 'Заполненность'),
                vertical_spacing=0.1
            )
            
            # Entries and exits
            fig.add_trace(
                go.Scatter(x=hourly_data['hour'], y=hourly_data['entries'], 
                          name='Входы', line=dict(color='#28a745')),
                row=1, col=1
            )
            fig.add_trace(
                go.Scatter(x=hourly_data['hour'], y=hourly_data['exits'], 
                          name='Выходы', line=dict(color='#dc3545')),
                row=1, col=1
            )
            
            # Occupancy
            fig.add_trace(
                go.Scatter(x=hourly_data['hour'], y=hourly_data['occupancy'], 
                          name='Заполненность', line=dict(color='#17a2b8')),
                row=2, col=1
            )
            
            fig.update_layout(
                height=400,
                template="plotly_dark",
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)'
            )
            
            return fig
            
        except Exception as e:
            logger.error(f"Error updating visitor trend chart: {e}")
            return go.Figure()
    
    @app.callback(
        Output('hourly-occupancy-chart', 'figure'),
        [Input('refresh-button', 'n_clicks'),
         Input('interval-component', 'n_intervals'),
         Input('store-filter', 'value'),
         Input('counter-filter', 'value')]
    )
    def update_hourly_occupancy(n_clicks, n_intervals, store_id, counter_id):
        """Update hourly occupancy chart"""
        try:
            today = datetime.now().date()
            
            # Build query for today's data
            query = db.session.query(VisitorData).join(VisitorCounter).filter(
                db.func.date(VisitorData.timestamp) == today
            )
            
            if store_id:
                query = query.filter(VisitorCounter.store_id == store_id)
            if counter_id:
                query = query.filter(VisitorData.counter_id == counter_id)
            
            data = query.all()
            
            if not data:
                fig = go.Figure()
                fig.add_annotation(text="Нет данных за сегодня", 
                                 xref="paper", yref="paper", x=0.5, y=0.5, 
                                 showarrow=False, font_size=16)
                fig.update_layout(
                    template="plotly_dark",
                    paper_bgcolor='rgba(0,0,0,0)',
                    plot_bgcolor='rgba(0,0,0,0)'
                )
                return fig
            
            # Create DataFrame and group by hour
            df = pd.DataFrame([{
                'hour': d.timestamp.hour,
                'occupancy': d.current_occupancy
            } for d in data])
            
            hourly_avg = df.groupby('hour')['occupancy'].mean().reset_index()
            
            # Create bar chart
            fig = go.Figure(data=[
                go.Bar(x=hourly_avg['hour'], y=hourly_avg['occupancy'],
                       marker_color='#17a2b8')
            ])
            
            fig.update_layout(
                title="Средняя заполненность по часам",
                xaxis_title="Час дня",
                yaxis_title="Посетители",
                template="plotly_dark",
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)'
            )
            
            return fig
            
        except Exception as e:
            logger.error(f"Error updating hourly occupancy chart: {e}")
            return go.Figure()
    
    @app.callback(
        Output('counters-table', 'children'),
        [Input('interval-component', 'n_intervals'),
         Input('store-filter', 'value')]
    )
    def update_counters_table(n, store_id):
        """Update counters status table"""
        try:
            # Get counters with latest data
            query = db.session.query(VisitorCounter).filter(VisitorCounter.active == True)
            if store_id:
                query = query.filter(VisitorCounter.store_id == store_id)
            
            counters = query.all()
            
            if not counters:
                return dbc.Alert("Нет активных счетчиков", color="info")
            
            rows = []
            for counter in counters:
                # Get latest data
                latest_data = VisitorData.query.filter_by(counter_id=counter.id).order_by(
                    VisitorData.timestamp.desc()
                ).first()
                
                if latest_data:
                    time_diff = datetime.now() - latest_data.timestamp.replace(tzinfo=None)
                    status = "Онлайн" if time_diff.total_seconds() < 1800 else "Офлайн"  # 30 minutes
                    status_color = "success" if status == "Онлайн" else "danger"
                    
                    rows.append(
                        html.Tr([
                            html.Td(counter.name),
                            html.Td(counter.store.name),
                            html.Td(latest_data.current_occupancy),
                            html.Td(latest_data.timestamp.strftime("%H:%M")),
                            html.Td([
                                dbc.Badge(status, color=status_color, className="me-1"),
                                dbc.Badge(f"{latest_data.battery_level}%" if latest_data.battery_level else "N/A", 
                                         color="warning" if latest_data.battery_level and latest_data.battery_level < 30 else "secondary")
                            ])
                        ])
                    )
                else:
                    rows.append(
                        html.Tr([
                            html.Td(counter.name),
                            html.Td(counter.store.name),
                            html.Td("—"),
                            html.Td("—"),
                            html.Td(dbc.Badge("Нет данных", color="secondary"))
                        ])
                    )
            
            table = dbc.Table([
                html.Thead([
                    html.Tr([
                        html.Th("Счетчик"),
                        html.Th("Магазин"),
                        html.Th("Заполненность"),
                        html.Th("Последние данные"),
                        html.Th("Статус")
                    ])
                ]),
                html.Tbody(rows)
            ], striped=True, bordered=True, hover=True, size="sm")
            
            return table
            
        except Exception as e:
            logger.error(f"Error updating counters table: {e}")
            return dbc.Alert("Ошибка загрузки данных", color="danger")
    
    @app.callback(
        Output('alerts-list', 'children'),
        [Input('interval-component', 'n_intervals'),
         Input('store-filter', 'value')]
    )
    def update_alerts_list(n, store_id):
        """Update alerts list"""
        try:
            query = Alert.query.join(VisitorCounter).filter(Alert.is_resolved == False)
            if store_id:
                query = query.filter(VisitorCounter.store_id == store_id)
            
            alerts = query.order_by(Alert.created_at.desc()).limit(10).all()
            
            if not alerts:
                return dbc.Alert("Нет активных алертов", color="success")
            
            alert_items = []
            for alert in alerts:
                severity_colors = {
                    'low': 'info',
                    'medium': 'warning', 
                    'high': 'danger',
                    'critical': 'danger'
                }
                
                alert_items.append(
                    dbc.ListGroupItem([
                        html.Div([
                            dbc.Badge(alert.severity.upper(), 
                                    color=severity_colors.get(alert.severity, 'secondary'),
                                    className="me-2"),
                            html.Strong(alert.message),
                        ], className="d-flex justify-content-between align-items-start"),
                        html.Small([
                            html.I(className="fas fa-clock me-1"),
                            alert.created_at.strftime("%d.%m %H:%M"),
                            " | ",
                            html.I(className="fas fa-map-marker-alt me-1"),
                            alert.counter.store.name
                        ], className="text-muted")
                    ])
                )
            
            return dbc.ListGroup(alert_items, flush=True)
            
        except Exception as e:
            logger.error(f"Error updating alerts list: {e}")
            return dbc.Alert("Ошибка загрузки алертов", color="danger")
    
    @app.callback(
        Output("download-data", "data"),
        Input("export-button", "n_clicks"),
        [State('store-filter', 'value'),
         State('counter-filter', 'value'),
         State('date-range', 'start_date'),
         State('date-range', 'end_date')],
        prevent_initial_call=True
    )
    def export_data(n_clicks, store_id, counter_id, start_date, end_date):
        """Export filtered data to Excel"""
        if not n_clicks:
            return dash.no_update
        
        try:
            # Build query
            query = db.session.query(VisitorData).join(VisitorCounter).join(Store)
            
            if store_id:
                query = query.filter(VisitorCounter.store_id == store_id)
            if counter_id:
                query = query.filter(VisitorData.counter_id == counter_id)
            if start_date:
                query = query.filter(VisitorData.timestamp >= start_date)
            if end_date:
                query = query.filter(VisitorData.timestamp <= end_date)
            
            data = query.order_by(VisitorData.timestamp).all()
            
            # Create DataFrame
            df = pd.DataFrame([{
                'Дата и время': d.timestamp.strftime("%d.%m.%Y %H:%M"),
                'Магазин': d.counter.store.name,
                'Счетчик': d.counter.name,
                'Входы': d.entries,
                'Выходы': d.exits,
                'Заполненность': d.current_occupancy,
                'Пиковая заполненность': d.hourly_peak,
                'Температура': d.temperature,
                'Влажность': d.humidity,
                'Статус датчика': d.sensor_status,
                'Заряд батареи': d.battery_level
            } for d in data])
            
            filename = f"visitor_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
            
            return dcc.send_data_frame(df.to_excel, filename, sheet_name="Данные посетителей", index=False)
            
        except Exception as e:
            logger.error(f"Error exporting data: {e}")
            return dash.no_update
