#!/usr/bin/env python3
"""
Initialize database with basic test data
"""

import os
import sys
from datetime import datetime, timedelta
import random

# Add path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import db
from database.models import Role, User, Store, VisitorCounter, VisitorData, Alert

def create_sample_data():
    """Create sample data for demonstration"""
    
    # Function will be called with app context from main.py
        print("Creating sample stores...")
        
        # Create sample stores
        stores_data = [
            {'name': 'ТЦ Европейский', 'store_code': 'MSK001', 'city': 'Москва', 'region': 'Центральный'},
            {'name': 'ТЦ Галерея', 'store_code': 'SPB001', 'city': 'Санкт-Петербург', 'region': 'Северо-Западный'},
            {'name': 'ТЦ Мега', 'store_code': 'EKB001', 'city': 'Екатеринбург', 'region': 'Уральский'},
            {'name': 'ТЦ Аврора', 'store_code': 'NSK001', 'city': 'Новосибирск', 'region': 'Сибирский'},
            {'name': 'ТЦ Континент', 'store_code': 'KRD001', 'city': 'Краснодар', 'region': 'Южный'},
        ]
        
        stores = []
        for store_data in stores_data:
            if not Store.query.filter_by(store_code=store_data['store_code']).first():
                store = Store(
                    name=store_data['name'],
                    store_code=store_data['store_code'],
                    address=f"ул. Торговая, д. {random.randint(1, 100)}",
                    city=store_data['city'],
                    region=store_data['region'],
                    contact_phone=f"+7-{random.randint(100, 999)}-{random.randint(100, 999)}-{random.randint(10, 99)}-{random.randint(10, 99)}",
                    contact_email=f"manager@{store_data['store_code'].lower()}.ru",
                    manager_name=f"Менеджер {store_data['store_code']}",
                    opening_hours="10:00 - 22:00",
                    active=True
                )
                db.session.add(store)
                stores.append(store)
                print(f"  Created store: {store_data['name']}")
        
        db.session.commit()
        
        # Get all stores
        all_stores = Store.query.filter_by(active=True).all()
        
        print("Creating sample users...")
        
        # Create sample users
        users_data = [
            {'username': 'regional_director', 'email': 'rd@retail.ru', 'role': 'rd', 'first_name': 'Анна', 'last_name': 'Директорова'},
            {'username': 'tech_user1', 'email': 'tech1@retail.ru', 'role': 'tu', 'first_name': 'Иван', 'last_name': 'Техников'},
            {'username': 'tech_user2', 'email': 'tech2@retail.ru', 'role': 'tu', 'first_name': 'Петр', 'last_name': 'Инженеров'},
            {'username': 'store_user1', 'email': 'user1@retail.ru', 'role': 'user', 'first_name': 'Мария', 'last_name': 'Пользователева'},
            {'username': 'store_user2', 'email': 'user2@retail.ru', 'role': 'user', 'first_name': 'Сергей', 'last_name': 'Работников'},
        ]
        
        created_users = []
        for user_data in users_data:
            if not User.query.filter_by(username=user_data['username']).first():
                role = Role.query.filter_by(name=user_data['role']).first()
                if role:
                    user = User(
                        username=user_data['username'],
                        email=user_data['email'],
                        first_name=user_data['first_name'],
                        last_name=user_data['last_name'],
                        role_id=role.id,
                        active=True,
                        phone=f"+7-{random.randint(100, 999)}-{random.randint(100, 999)}-{random.randint(10, 99)}-{random.randint(10, 99)}"
                    )
                    user.set_password('demo123')
                    db.session.add(user)
                    created_users.append(user)
                    print(f"  Created user: {user_data['username']} ({user_data['role']})")
        
        db.session.commit()
        
        print("Creating sample counters...")
        
        # Create sample counters
        tech_users = [u for u in created_users if u.role.name == 'tu']
        
        counters = []
        for i, store in enumerate(all_stores[:3]):  # Only first 3 stores
            for j in range(2):  # 2 counters per store
                counter = VisitorCounter(
                    name=f"{store.name} - Вход {j+1}",
                    device_id=f"DEVICE_{store.store_code}_{j+1:03d}",
                    location_description=f"{'Главный' if j == 0 else 'Боковой'} вход",
                    counter_type='bidirectional',
                    store_id=store.id,
                    assigned_user_id=tech_users[i % len(tech_users)].id if tech_users else None,
                    installation_date=datetime.now() - timedelta(days=random.randint(30, 365)),
                    firmware_version=f"v2.{random.randint(0, 5)}.{random.randint(0, 9)}",
                    hardware_version="HW3.1",
                    active=True
                )
                db.session.add(counter)
                counters.append(counter)
                print(f"  Created counter: {counter.name}")
        
        db.session.commit()
        
        print("Creating sample visitor data...")
        
        # Create sample visitor data for last 7 days
        for counter in counters:
            for days_ago in range(7):
                for hour in range(9, 22):  # Business hours 9-21
                    timestamp = datetime.now() - timedelta(days=days_ago, hours=23-hour)
                    
                    # Simulate realistic visitor patterns
                    if hour in [12, 13, 18, 19]:  # Peak hours
                        entries = random.randint(20, 50)
                        exits = random.randint(15, 45)
                    elif hour in [9, 10, 21]:  # Low hours
                        entries = random.randint(5, 15)
                        exits = random.randint(8, 20)
                    else:  # Normal hours
                        entries = random.randint(10, 30)
                        exits = random.randint(8, 25)
                    
                    # Weekend modifier
                    if timestamp.weekday() >= 5:
                        entries = int(entries * 1.2)
                        exits = int(exits * 1.2)
                    
                    occupancy = max(0, random.randint(5, 100))
                    
                    visitor_data = VisitorData(
                        counter_id=counter.id,
                        timestamp=timestamp,
                        entries=entries,
                        exits=exits,
                        current_occupancy=occupancy,
                        hourly_peak=occupancy + random.randint(5, 20),
                        temperature=round(random.uniform(18.0, 24.0), 1),
                        humidity=random.randint(40, 60),
                        sensor_status='normal',
                        battery_level=random.randint(80, 100),
                        signal_strength=random.randint(70, 100)
                    )
                    db.session.add(visitor_data)
        
        db.session.commit()
        print(f"  Created visitor data for {len(counters)} counters over 7 days")
        
        print("Creating sample alerts...")
        
        # Create sample alerts
        alert_types = ['high_occupancy', 'battery_low', 'sensor_error']
        for i, counter in enumerate(counters[:2]):  # Only first 2 counters
            alert_type = alert_types[i % len(alert_types)]
            
            if alert_type == 'high_occupancy':
                message = f"Высокая заполненность (180 чел.) в {counter.store.name}"
                severity = 'medium'
            elif alert_type == 'battery_low':
                message = f"Низкий заряд батареи (15%) у {counter.name}"
                severity = 'medium'
            else:
                message = f"Ошибка датчика у счетчика {counter.name}"
                severity = 'high'
            
            alert = Alert(
                counter_id=counter.id,
                alert_type=alert_type,
                severity=severity,
                message=message,
                is_read=False,
                is_resolved=False,
                created_at=datetime.now() - timedelta(hours=random.randint(1, 24))
            )
            db.session.add(alert)
            print(f"  Created alert: {alert_type} for {counter.name}")
        
        db.session.commit()
        
        print("\n✅ Sample data created successfully!")
        print("\nSystem Statistics:")
        print(f"  - Stores: {Store.query.count()}")
        print(f"  - Users: {User.query.count()}")
        print(f"  - Counters: {VisitorCounter.query.count()}")
        print(f"  - Data points: {VisitorData.query.count()}")
        print(f"  - Active alerts: {Alert.query.filter_by(is_resolved=False).count()}")

if __name__ == '__main__':
    try:
        create_sample_data()
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)