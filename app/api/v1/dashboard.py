"""Dashboard API endpoints."""

from flask import jsonify, request
from datetime import datetime, timedelta, date

from app.api.v1 import bp
from app.models import Device, Order
from app.utils.redis_utils import get_day_key, get_daily_counter, RedisKeys
from app.factory import redis_client


@bp.route('/dashboard/summary')
def dashboard_summary():
    """Get dashboard summary with KPIs and trends."""
    try:
        # Query parameters
        from_date = request.args.get('from')
        to_date = request.args.get('to') 
        merchant_id = request.args.get('merchant_id')
        
        # Default to last 7 days if not specified
        if not from_date or not to_date:
            end_date = date.today()
            start_date = end_date - timedelta(days=7)
            from_date = start_date.strftime('%Y%m%d')
            to_date = end_date.strftime('%Y%m%d')
        
        # Device statistics
        device_stats = _get_device_statistics(merchant_id)
        
        # Sales statistics
        sales_stats = _get_sales_statistics(from_date, to_date, merchant_id)
        
        # Alarm statistics
        alarm_stats = _get_alarm_statistics(merchant_id)
        
        # Material statistics
        material_stats = _get_material_statistics(merchant_id)
        
        # Trends data
        trends = _get_trends_data(from_date, to_date, merchant_id)
        
        data = {
            'device_total': device_stats['total'],
            'online_rate': device_stats['online_rate'],
            'sales_today': sales_stats['today'],
            'sales_week': sales_stats['week'],
            'alarms_open': alarm_stats['open'],
            'materials_low': material_stats['low_count'],
            'trends': trends
        }
        
        return jsonify({'ok': True, 'data': data})
        
    except Exception as e:
        return jsonify({'ok': False, 'error': {'code': 'SERVER_ERROR', 'message': str(e)}}), 500


def _get_device_statistics(merchant_id=None):
    """Get device statistics."""
    if merchant_id:
        devices = Device.list_by_merchant(merchant_id, limit=1000)
    else:
        # Get all devices - simplified approach
        online_devices = Device.list_by_status('online', limit=1000)
        offline_devices = Device.list_by_status('offline', limit=1000)
        devices = online_devices + offline_devices
    
    total = len(devices)
    online = len([d for d in devices if d.is_online()])
    online_rate = (online / total * 100) if total > 0 else 0
    
    return {
        'total': total,
        'online': online,
        'online_rate': round(online_rate, 1)
    }


def _get_sales_statistics(from_date, to_date, merchant_id=None):
    """Get sales statistics."""
    today = date.today()
    today_key = get_day_key(today)
    
    # Get week range
    week_start = today - timedelta(days=7)
    
    if merchant_id:
        devices = Device.list_by_merchant(merchant_id, limit=1000)
    else:
        online_devices = Device.list_by_status('online', limit=500)
        offline_devices = Device.list_by_status('offline', limit=500)
        devices = online_devices + offline_devices
    
    today_sales = 0
    week_sales = 0
    
    for device in devices:
        # Today's sales
        today_sales += get_daily_counter(
            RedisKeys.DEVICE_AGG_ORDERS_DAY_REVENUE,
            device.device_id,
            today
        )
        
        # Week's sales
        for i in range(7):
            day = week_start + timedelta(days=i)
            week_sales += get_daily_counter(
                RedisKeys.DEVICE_AGG_ORDERS_DAY_REVENUE,
                device.device_id,
                day
            )
    
    return {
        'today': today_sales,
        'week': week_sales
    }


def _get_alarm_statistics(merchant_id=None):
    """Get alarm statistics."""
    # Simplified - count open alarms across all devices
    # In production, you might maintain global alarm indexes
    
    if merchant_id:
        devices = Device.list_by_merchant(merchant_id, limit=1000)
    else:
        devices = Device.list_by_status('online', limit=500) + Device.list_by_status('offline', limit=500)
    
    open_count = 0
    for device in devices[:50]:  # Limit to avoid performance issues
        status_key = RedisKeys.DEVICE_ALARMS_STATUS.format(device_id=device.device_id, status='open')
        count = redis_client.scard(status_key)
        open_count += count
    
    return {
        'open': open_count
    }


def _get_material_statistics(merchant_id=None):
    """Get material statistics."""
    if merchant_id:
        devices = Device.list_by_merchant(merchant_id, limit=1000)
    else:
        devices = Device.list_by_status('online', limit=500) + Device.list_by_status('offline', limit=500)
    
    low_count = 0
    for device in devices[:50]:  # Limit to avoid performance issues
        low_bins_key = RedisKeys.DEVICE_BINS_LOW.format(device_id=device.device_id)
        count = redis_client.scard(low_bins_key)
        low_count += count
    
    return {
        'low_count': low_count
    }


def _get_trends_data(from_date, to_date, merchant_id=None):
    """Get trends data for charts."""
    # Simplified trends - last 7 days
    end_date = date.today()
    trends = {
        'sales': [],
        'online_rate': []
    }
    
    if merchant_id:
        devices = Device.list_by_merchant(merchant_id, limit=1000)
    else:
        devices = Device.list_by_status('online', limit=500) + Device.list_by_status('offline', limit=500)
    
    for i in range(7):
        day = end_date - timedelta(days=6-i)
        day_key = get_day_key(day)
        
        # Sales for the day
        day_sales = 0
        for device in devices:
            day_sales += get_daily_counter(
                RedisKeys.DEVICE_AGG_ORDERS_DAY_REVENUE,
                device.device_id,
                day
            )
        
        trends['sales'].append({
            'date': day_key,
            'value': day_sales
        })
        
        # Online rate (simplified - use current rate for all days)
        total = len(devices)
        online = len([d for d in devices if d.is_online()])
        online_rate = (online / total * 100) if total > 0 else 0
        
        trends['online_rate'].append({
            'date': day_key,
            'value': round(online_rate, 1)
        })
    
    return trends