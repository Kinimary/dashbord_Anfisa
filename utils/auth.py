import bcrypt
import secrets
import string
from datetime import datetime, timedelta
from database.models import User, Session, Role
from database import db
import logging

logger = logging.getLogger(__name__)

def hash_password(password):
    """Hash password using bcrypt"""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

def check_password(password, password_hash):
    """Check password against hash"""
    return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))

def generate_session_token():
    """Generate secure session token"""
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for i in range(64))

def create_user_session(user_id, ip_address=None, user_agent=None):
    """Create new user session"""
    try:
        # Invalidate old sessions for this user
        Session.query.filter_by(user_id=user_id, active=True).update({'active': False})
        
        # Create new session
        session_token = generate_session_token()
        expires_at = datetime.utcnow() + timedelta(hours=8)  # 8 hour session
        
        new_session = Session(
            user_id=user_id,
            session_token=session_token,
            ip_address=ip_address,
            user_agent=user_agent,
            expires_at=expires_at,
            active=True
        )
        
        db.session.add(new_session)
        db.session.commit()
        
        return session_token
        
    except Exception as e:
        logger.error(f"Error creating user session: {e}")
        db.session.rollback()
        return None

def validate_session(session_token):
    """Validate session token and return user"""
    try:
        session = Session.query.filter_by(
            session_token=session_token,
            active=True
        ).first()
        
        if not session:
            return None
        
        # Check if session expired
        if datetime.utcnow() > session.expires_at:
            session.active = False
            db.session.commit()
            return None
        
        # Update user's last login
        user = session.user
        user.last_login = datetime.utcnow()
        db.session.commit()
        
        return user
        
    except Exception as e:
        logger.error(f"Error validating session: {e}")
        return None

def invalidate_session(session_token):
    """Invalidate user session"""
    try:
        session = Session.query.filter_by(session_token=session_token).first()
        if session:
            session.active = False
            db.session.commit()
            return True
        return False
        
    except Exception as e:
        logger.error(f"Error invalidating session: {e}")
        return False

def authenticate_user(username, password):
    """Authenticate user by username and password"""
    try:
        user = User.query.filter_by(username=username, active=True).first()
        
        if user and user.check_password(password):
            return user
        
        return None
        
    except Exception as e:
        logger.error(f"Error authenticating user: {e}")
        return None

def check_user_permission(user, permission):
    """Check if user has specific permission"""
    try:
        from system_config import ROLE_PERMISSIONS
        
        if not user or not user.role:
            return False
        
        role_perms = ROLE_PERMISSIONS.get(user.role.name, {})
        permissions = role_perms.get('permissions', [])
        
        return permission in permissions
        
    except Exception as e:
        logger.error(f"Error checking user permission: {e}")
        return False

def get_user_accessible_stores(user):
    """Get stores accessible to user based on role hierarchy"""
    try:
        from database.models import Store, VisitorCounter
        
        if not user or not user.role:
            return []
        
        # Admin sees all stores
        if user.role.name == 'admin':
            return Store.query.filter_by(active=True).all()
        
        # RD sees stores with counters assigned to them or their subordinates
        elif user.role.name == 'rd':
            # Get subordinates
            subordinate_ids = [sub.id for sub in user.subordinates] + [user.id]
            
            store_ids = db.session.query(VisitorCounter.store_id).filter(
                VisitorCounter.assigned_user_id.in_(subordinate_ids),
                VisitorCounter.active == True
            ).distinct().all()
            
            store_ids = [sid[0] for sid in store_ids]
            return Store.query.filter(Store.id.in_(store_ids), Store.active == True).all()
        
        # TU and regular users see only stores with their assigned counters
        else:
            store_ids = db.session.query(VisitorCounter.store_id).filter(
                VisitorCounter.assigned_user_id == user.id,
                VisitorCounter.active == True
            ).distinct().all()
            
            store_ids = [sid[0] for sid in store_ids]
            return Store.query.filter(Store.id.in_(store_ids), Store.active == True).all()
        
    except Exception as e:
        logger.error(f"Error getting user accessible stores: {e}")
        return []

def get_user_accessible_counters(user):
    """Get counters accessible to user based on role hierarchy"""
    try:
        from database.models import VisitorCounter
        
        if not user or not user.role:
            return []
        
        # Admin sees all counters
        if user.role.name == 'admin':
            return VisitorCounter.query.filter_by(active=True).all()
        
        # RD sees counters assigned to them or their subordinates
        elif user.role.name == 'rd':
            subordinate_ids = [sub.id for sub in user.subordinates] + [user.id]
            return VisitorCounter.query.filter(
                VisitorCounter.assigned_user_id.in_(subordinate_ids),
                VisitorCounter.active == True
            ).all()
        
        # TU and regular users see only their assigned counters
        else:
            return VisitorCounter.query.filter_by(
                assigned_user_id=user.id,
                active=True
            ).all()
        
    except Exception as e:
        logger.error(f"Error getting user accessible counters: {e}")
        return []

def create_default_admin():
    """Create default admin user if none exists"""
    try:
        # Check if admin role exists
        admin_role = Role.query.filter_by(name='admin').first()
        if not admin_role:
            admin_role = Role(
                name='admin',
                description='Администратор системы',
                level=3
            )
            db.session.add(admin_role)
            db.session.flush()  # Get the ID
        
        # Check if admin user exists
        admin_user = User.query.filter_by(username='admin').first()
        if not admin_user:
            admin_user = User(
                username='admin',
                email='admin@retail.ru',
                first_name='Системный',
                last_name='Администратор',
                role_id=admin_role.id,
                active=True
            )
            admin_user.set_password('admin123')  # Default password
            
            db.session.add(admin_user)
            db.session.commit()
            
            logger.info("Default admin user created: admin/admin123")
            return True
        
        return False
        
    except Exception as e:
        logger.error(f"Error creating default admin: {e}")
        db.session.rollback()
        return False

def validate_password_strength(password):
    """Validate password strength"""
    if len(password) < 8:
        return False, "Пароль должен содержать минимум 8 символов"
    
    if not any(c.isdigit() for c in password):
        return False, "Пароль должен содержать хотя бы одну цифру"
    
    if not any(c.isupper() for c in password):
        return False, "Пароль должен содержать хотя бы одну заглавную букву"
    
    if not any(c.islower() for c in password):
        return False, "Пароль должен содержать хотя бы одну строчную букву"
    
    return True, "Пароль соответствует требованиям"

def get_user_role_hierarchy():
    """Get role hierarchy for user management"""
    return {
        'admin': ['admin', 'rd', 'tu', 'user'],
        'rd': ['tu', 'user'],
        'tu': ['user'],
        'user': []
    }

def can_manage_user(manager, target_user):
    """Check if manager can manage target user"""
    if not manager or not target_user:
        return False
    
    # Admin can manage everyone
    if manager.role.name == 'admin':
        return True
    
    # RD can manage TU and users under them
    if manager.role.name == 'rd':
        if target_user.role.name in ['tu', 'user']:
            # Check if target is subordinate or subordinate's subordinate
            return (target_user.supervisor_id == manager.id or 
                   (target_user.supervisor and target_user.supervisor.supervisor_id == manager.id))
    
    # TU can manage only direct subordinates with user role
    if manager.role.name == 'tu':
        return (target_user.role.name == 'user' and 
               target_user.supervisor_id == manager.id)
    
    return False

def log_user_action(user_id, action, details=None, ip_address=None):
    """Log user action for audit trail"""
    try:
        from database.models import AuditLog
        import json
        
        audit_log = AuditLog(
            user_id=user_id,
            action=action,
            new_values=json.dumps(details) if details else None,
            ip_address=ip_address
        )
        
        db.session.add(audit_log)
        db.session.commit()
        
    except Exception as e:
        logger.error(f"Error logging user action: {e}")
