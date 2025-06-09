from datetime import datetime, timezone
from database import db
from sqlalchemy import Integer, String, DateTime, Boolean, Float, Text, ForeignKey, Index
from sqlalchemy.orm import relationship
import bcrypt

class Role(db.Model):
    __tablename__ = 'roles'
    
    id = db.Column(Integer, primary_key=True)
    name = db.Column(String(50), unique=True, nullable=False)
    description = db.Column(String(200))
    level = db.Column(Integer, nullable=False, default=0)
    created_at = db.Column(DateTime, default=lambda: datetime.now(timezone.utc))
    
    # Relationships
    users = relationship("User", back_populates="role")
    
    def __repr__(self):
        return f'<Role {self.name}>'

class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(Integer, primary_key=True)
    username = db.Column(String(80), unique=True, nullable=False)
    email = db.Column(String(120), unique=True, nullable=False)
    password_hash = db.Column(String(256), nullable=False)
    first_name = db.Column(String(100))
    last_name = db.Column(String(100))
    phone = db.Column(String(20))
    active = db.Column(Boolean, default=True)
    role_id = db.Column(Integer, ForeignKey('roles.id'), nullable=False)
    supervisor_id = db.Column(Integer, ForeignKey('users.id'))
    last_login = db.Column(DateTime)
    created_at = db.Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Relationships
    role = relationship("Role", back_populates="users")
    supervisor = relationship("User", remote_side=[id])
    subordinates = relationship("User", back_populates="supervisor")
    assigned_counters = relationship("VisitorCounter", back_populates="assigned_user")
    audit_logs = relationship("AuditLog", back_populates="user")
    sessions = relationship("Session", back_populates="user")
    
    def set_password(self, password):
        """Hash and set password"""
        salt = bcrypt.gensalt()
        self.password_hash = bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')
    
    def check_password(self, password):
        """Check password against hash"""
        return bcrypt.checkpw(password.encode('utf-8'), self.password_hash.encode('utf-8'))
    
    @property
    def full_name(self):
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        return self.username
    
    def __repr__(self):
        return f'<User {self.username}>'

class Store(db.Model):
    __tablename__ = 'stores'
    
    id = db.Column(Integer, primary_key=True)
    name = db.Column(String(200), nullable=False)
    store_code = db.Column(String(20), unique=True, nullable=False)
    address = db.Column(Text)
    city = db.Column(String(100))
    region = db.Column(String(100))
    contact_phone = db.Column(String(20))
    contact_email = db.Column(String(120))
    manager_name = db.Column(String(200))
    opening_hours = db.Column(String(100))
    timezone = db.Column(String(50), default='Europe/Moscow')
    active = db.Column(Boolean, default=True)
    created_at = db.Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Relationships
    visitor_counters = relationship("VisitorCounter", back_populates="store")
    
    def __repr__(self):
        return f'<Store {self.name} ({self.store_code})>'

class VisitorCounter(db.Model):
    __tablename__ = 'visitor_counters'
    
    id = db.Column(Integer, primary_key=True)
    name = db.Column(String(200), nullable=False)
    device_id = db.Column(String(100), unique=True, nullable=False)
    location_description = db.Column(Text)
    counter_type = db.Column(String(50), nullable=False, default='bidirectional')
    store_id = db.Column(Integer, ForeignKey('stores.id'), nullable=False)
    assigned_user_id = db.Column(Integer, ForeignKey('users.id'))
    installation_date = db.Column(DateTime)
    last_maintenance = db.Column(DateTime)
    next_maintenance = db.Column(DateTime)
    firmware_version = db.Column(String(20))
    hardware_version = db.Column(String(20))
    active = db.Column(Boolean, default=True)
    created_at = db.Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Relationships
    store = relationship("Store", back_populates="visitor_counters")
    assigned_user = relationship("User", back_populates="assigned_counters")
    visitor_data = relationship("VisitorData", back_populates="counter")
    alerts = relationship("Alert", back_populates="counter")
    
    def __repr__(self):
        return f'<VisitorCounter {self.name} ({self.device_id})>'

class VisitorData(db.Model):
    __tablename__ = 'visitor_data'
    
    id = db.Column(Integer, primary_key=True)
    counter_id = db.Column(Integer, ForeignKey('visitor_counters.id'), nullable=False)
    timestamp = db.Column(DateTime, nullable=False)
    entries = db.Column(Integer, nullable=False, default=0)
    exits = db.Column(Integer, nullable=False, default=0)
    current_occupancy = db.Column(Integer, nullable=False, default=0)
    hourly_peak = db.Column(Integer, default=0)
    temperature = db.Column(Float)
    humidity = db.Column(Float)
    sensor_status = db.Column(String(20), default='normal')
    battery_level = db.Column(Integer)
    signal_strength = db.Column(Integer)
    created_at = db.Column(DateTime, default=lambda: datetime.now(timezone.utc))
    
    # Relationships
    counter = relationship("VisitorCounter", back_populates="visitor_data")
    
    # Indexes for performance
    __table_args__ = (
        Index('idx_visitor_data_counter_timestamp', 'counter_id', 'timestamp'),
        Index('idx_visitor_data_timestamp', 'timestamp'),
    )
    
    def __repr__(self):
        return f'<VisitorData counter_id={self.counter_id} timestamp={self.timestamp}>'

class Alert(db.Model):
    __tablename__ = 'alerts'
    
    id = db.Column(Integer, primary_key=True)
    counter_id = db.Column(Integer, ForeignKey('visitor_counters.id'), nullable=False)
    alert_type = db.Column(String(50), nullable=False)
    severity = db.Column(String(20), nullable=False, default='medium')
    message = db.Column(Text, nullable=False)
    is_read = db.Column(Boolean, default=False)
    is_resolved = db.Column(Boolean, default=False)
    resolved_by_id = db.Column(Integer, ForeignKey('users.id'))
    resolved_at = db.Column(DateTime)
    resolution_notes = db.Column(Text)
    created_at = db.Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Relationships
    counter = relationship("VisitorCounter", back_populates="alerts")
    resolved_by = relationship("User", foreign_keys=[resolved_by_id])
    
    # Indexes for performance
    __table_args__ = (
        Index('idx_alerts_unresolved', 'is_resolved', 'created_at'),
        Index('idx_alerts_counter_unresolved', 'counter_id', 'is_resolved'),
    )
    
    def __repr__(self):
        return f'<Alert {self.alert_type} severity={self.severity}>'

class AuditLog(db.Model):
    __tablename__ = 'audit_logs'
    
    id = db.Column(Integer, primary_key=True)
    user_id = db.Column(Integer, ForeignKey('users.id'))
    action = db.Column(String(100), nullable=False)
    table_name = db.Column(String(50))
    record_id = db.Column(Integer)
    old_values = db.Column(Text)  # JSON
    new_values = db.Column(Text)  # JSON
    ip_address = db.Column(String(45))
    user_agent = db.Column(Text)
    timestamp = db.Column(DateTime, default=lambda: datetime.now(timezone.utc))
    
    # Relationships
    user = relationship("User", back_populates="audit_logs")
    
    def __repr__(self):
        return f'<AuditLog {self.action} by user_id={self.user_id}>'

class Session(db.Model):
    __tablename__ = 'sessions'
    
    id = db.Column(Integer, primary_key=True)
    user_id = db.Column(Integer, ForeignKey('users.id'), nullable=False)
    session_token = db.Column(String(255), unique=True, nullable=False)
    ip_address = db.Column(String(45))
    user_agent = db.Column(Text)
    created_at = db.Column(DateTime, default=lambda: datetime.now(timezone.utc))
    expires_at = db.Column(DateTime, nullable=False)
    active = db.Column(Boolean, default=True)
    
    # Relationships
    user = relationship("User", back_populates="sessions")
    
    def __repr__(self):
        return f'<Session user_id={self.user_id} active={self.active}>'
