#!/usr/bin/env python3
"""
API endpoints for receiving data from Arduino devices
"""

import logging
from datetime import datetime, timezone
from flask import Blueprint, request, jsonify
from database import db
from database.models import VisitorCounter, VisitorData, Store, Alert
from utils.auth import log_user_action

logger = logging.getLogger(__name__)

api_bp = Blueprint('api', __name__, url_prefix='/api')

@api_bp.route('/visitor-count', methods=['POST'])
def receive_visitor_count():
    """Receive visitor count data from Arduino devices"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'status': 'error',
                'message': 'No JSON data provided'
            }), 400
        
        # Validate required fields
        required_fields = ['device_id', 'count', 'timestamp']
        for field in required_fields:
            if field not in data:
                return jsonify({
                    'status': 'error',
                    'message': f'Missing required field: {field}'
                }), 400
        
        device_id = data['device_id']
        count = int(data['count'])
        timestamp_str = data['timestamp']
        
        # Find the counter by device_id
        counter = VisitorCounter.query.filter_by(device_id=device_id).first()
        if not counter:
            # Create new counter if doesn't exist
            logger.info(f"Creating new counter for device_id: {device_id}")
            
            # Try to find a default store or create one
            default_store = Store.query.first()
            if not default_store:
                default_store = Store(
                    name="Автоматически созданный магазин",
                    store_code="AUTO_001",
                    city="Не указан",
                    region="Автоматически",
                    active=True
                )
                db.session.add(default_store)
                db.session.flush()
            
            counter = VisitorCounter(
                name=f"Счетчик {device_id}",
                device_id=device_id,
                location_description="Автоматически зарегистрирован",
                counter_type="bidirectional",
                store_id=default_store.id,
                active=True
            )
            db.session.add(counter)
            db.session.flush()
        
        # Parse timestamp
        try:
            if timestamp_str.endswith('Z'):
                timestamp = datetime.fromisoformat(timestamp_str[:-1]).replace(tzinfo=timezone.utc)
            else:
                timestamp = datetime.fromisoformat(timestamp_str)
                if timestamp.tzinfo is None:
                    timestamp = timestamp.replace(tzinfo=timezone.utc)
        except ValueError:
            timestamp = datetime.now(timezone.utc)
        
        # Get the last visitor data entry for this counter
        last_entry = VisitorData.query.filter_by(counter_id=counter.id).order_by(
            VisitorData.timestamp.desc()
        ).first()
        
        # Calculate entries (difference from last count)
        if last_entry and last_entry.entries is not None:
            entries = max(0, count - last_entry.entries)
        else:
            entries = count
        
        # Calculate current occupancy (simple estimation)
        # In real implementation, this would track entries vs exits
        current_occupancy = max(0, entries - (entries // 4))  # Assume 25% exit rate
        
        # Create new visitor data entry
        visitor_data = VisitorData(
            counter_id=counter.id,
            timestamp=timestamp,
            entries=count,  # Total count from Arduino
            exits=0,  # Arduino doesn't track exits separately
            current_occupancy=current_occupancy,
            sensor_status='normal',
            battery_level=data.get('battery_level', 100),
            signal_strength=data.get('signal_strength', 100)
        )
        
        db.session.add(visitor_data)
        
        # Check for alerts based on the data
        create_alerts_if_needed(counter, visitor_data, data)
        
        db.session.commit()
        
        logger.info(f"Received data from {device_id}: count={count}, entries={entries}")
        
        return jsonify({
            'status': 'success',
            'message': 'Data received successfully',
            'counter_id': counter.id,
            'total_count': count,
            'new_entries': entries,
            'timestamp': timestamp.isoformat()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error processing visitor count data: {e}")
        return jsonify({
            'status': 'error',
            'message': 'Internal server error'
        }), 500

@api_bp.route('/device-status', methods=['POST'])
def receive_device_status():
    """Receive device status updates from Arduino"""
    try:
        data = request.get_json()
        
        if not data or 'device_id' not in data:
            return jsonify({
                'status': 'error',
                'message': 'device_id is required'
            }), 400
        
        device_id = data['device_id']
        counter = VisitorCounter.query.filter_by(device_id=device_id).first()
        
        if not counter:
            return jsonify({
                'status': 'error',
                'message': 'Device not found'
            }), 404
        
        # Update device status fields
        if 'firmware_version' in data:
            counter.firmware_version = data['firmware_version']
        if 'hardware_version' in data:
            counter.hardware_version = data['hardware_version']
        
        # Create status entry
        status_data = VisitorData(
            counter_id=counter.id,
            timestamp=datetime.now(timezone.utc),
            entries=0,
            exits=0,
            current_occupancy=0,
            battery_level=data.get('battery_level', 100),
            signal_strength=data.get('signal_strength', 100),
            sensor_status=data.get('sensor_status', 'normal')
        )
        
        db.session.add(status_data)
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'message': 'Status updated successfully'
        }), 200
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error processing device status: {e}")
        return jsonify({
            'status': 'error',
            'message': 'Internal server error'
        }), 500

@api_bp.route('/device-config/<device_id>', methods=['GET'])
def get_device_config(device_id):
    """Get configuration for a specific device"""
    try:
        counter = VisitorCounter.query.filter_by(device_id=device_id).first()
        
        if not counter:
            return jsonify({
                'status': 'error',
                'message': 'Device not found'
            }), 404
        
        config = {
            'device_id': counter.device_id,
            'name': counter.name,
            'location': counter.location_description,
            'counter_type': counter.counter_type,
            'store_name': counter.store.name,
            'active': counter.active,
            'settings': {
                'measurement_interval': 100,  # milliseconds
                'send_interval': 60000,       # milliseconds
                'zone_threshold': 160,        # cm
                'exit_threshold': 150,        # cm
                'min_distance': 10           # cm
            }
        }
        
        return jsonify({
            'status': 'success',
            'config': config
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting device config: {e}")
        return jsonify({
            'status': 'error',
            'message': 'Internal server error'
        }), 500

@api_bp.route('/devices', methods=['GET'])
def list_devices():
    """List all registered devices"""
    try:
        counters = VisitorCounter.query.join(Store).all()
        
        devices = []
        for counter in counters:
            # Get latest data
            latest_data = VisitorData.query.filter_by(counter_id=counter.id).order_by(
                VisitorData.timestamp.desc()
            ).first()
            
            device_info = {
                'device_id': counter.device_id,
                'name': counter.name,
                'store_name': counter.store.name,
                'location': counter.location_description,
                'active': counter.active,
                'last_seen': latest_data.timestamp.isoformat() if latest_data else None,
                'total_count': latest_data.entries if latest_data else 0,
                'battery_level': latest_data.battery_level if latest_data else None,
                'signal_strength': latest_data.signal_strength if latest_data else None,
                'status': latest_data.sensor_status if latest_data else 'unknown'
            }
            devices.append(device_info)
        
        return jsonify({
            'status': 'success',
            'devices': devices,
            'total': len(devices)
        }), 200
        
    except Exception as e:
        logger.error(f"Error listing devices: {e}")
        return jsonify({
            'status': 'error',
            'message': 'Internal server error'
        }), 500

def create_alerts_if_needed(counter, visitor_data, raw_data):
    """Create alerts based on visitor data analysis"""
    try:
        # Battery level alert
        if visitor_data.battery_level and visitor_data.battery_level < 20:
            existing_alert = Alert.query.filter_by(
                counter_id=counter.id,
                alert_type='battery_low',
                is_resolved=False
            ).first()
            
            if not existing_alert:
                alert = Alert(
                    counter_id=counter.id,
                    alert_type='battery_low',
                    severity='high',
                    message=f'Низкий заряд батареи: {visitor_data.battery_level}%',
                    is_read=False,
                    is_resolved=False
                )
                db.session.add(alert)
        
        # Signal strength alert
        if visitor_data.signal_strength and visitor_data.signal_strength < 30:
            existing_alert = Alert.query.filter_by(
                counter_id=counter.id,
                alert_type='weak_signal',
                is_resolved=False
            ).first()
            
            if not existing_alert:
                alert = Alert(
                    counter_id=counter.id,
                    alert_type='weak_signal',
                    severity='medium',
                    message=f'Слабый сигнал: {visitor_data.signal_strength}%',
                    is_read=False,
                    is_resolved=False
                )
                db.session.add(alert)
        
        # Device offline alert (if no data for more than 5 minutes)
        from datetime import timedelta
        five_minutes_ago = datetime.now(timezone.utc) - timedelta(minutes=5)
        
        if visitor_data.timestamp < five_minutes_ago:
            existing_alert = Alert.query.filter_by(
                counter_id=counter.id,
                alert_type='device_offline',
                is_resolved=False
            ).first()
            
            if not existing_alert:
                alert = Alert(
                    counter_id=counter.id,
                    alert_type='device_offline',
                    severity='critical',
                    message=f'Устройство не отвечает более 5 минут',
                    is_read=False,
                    is_resolved=False
                )
                db.session.add(alert)
        
    except Exception as e:
        logger.error(f"Error creating alerts: {e}")

# Health check endpoint specifically for devices
@api_bp.route('/health', methods=['GET'])
def api_health():
    """Health check endpoint for devices"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'service': 'visitor-counter-api'
    }), 200