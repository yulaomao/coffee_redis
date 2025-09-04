"""Devices API endpoints."""

from flask import jsonify, request
from datetime import datetime, timedelta

from app.api.v1 import bp
from app.models import Device, DeviceBin, Order, RemoteCommand
from app.models.audit import AuditLogger
from app.utils.redis_utils import get_current_ts


@bp.route('/devices')
def list_devices():
    """List devices with filtering and pagination."""
    try:
        # Check if we're in demo mode (Redis not available)
        try:
            from app.factory import redis_client
            redis_client.ping()
        except:
            # Demo mode
            from app.utils.demo_data import get_devices_list, init_demo_data
            
            try:
                devices = get_devices_list()
            except:
                init_demo_data()
                devices = get_devices_list()
            
            return jsonify({
                'ok': True,
                'data': {
                    'devices': devices,
                    'pagination': {
                        'page': 1,
                        'page_size': len(devices),
                        'total': len(devices),
                        'has_more': False
                    }
                }
            })
        
        # Production mode with Redis (original implementation)
        # Query parameters
        merchant_id = request.args.get('merchant_id')
        status = request.args.get('status')
        model = request.args.get('model')
        query = request.args.get('query')  # Search term
        page = int(request.args.get('page', 1))
        page_size = min(int(request.args.get('page_size', 50)), 100)
        
        # Get devices based on filters
        devices = []
        
        if merchant_id:
            devices = Device.list_by_merchant(merchant_id, limit=page_size * 2)
        elif status:
            devices = Device.list_by_status(status, limit=page_size * 2)
        else:
            # Get recently seen devices
            devices = Device.list_recently_seen(limit=page_size * 2)
        
        # Apply additional filters
        if model:
            devices = [d for d in devices if d.model.lower() == model.lower()]
        
        if query:
            query = query.lower()
            devices = [d for d in devices if (
                query in d.device_id.lower() or
                query in d.alias.lower() or
                query in d.ip.lower()
            )]
        
        # Pagination
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        page_devices = devices[start_idx:end_idx]
        
        # Convert to dict format
        device_data = []
        for device in page_devices:
            device_dict = device.to_dict()
            
            # Add today's sales
            today_stats = Order.get_daily_stats(device.device_id)
            device_dict['today_orders'] = today_stats['order_count']
            device_dict['today_revenue_cents'] = today_stats['revenue_cents']
            
            # Check for low materials
            low_bins_count = len(DeviceBin.list_low_bins(device.device_id))
            device_dict['low_materials_count'] = low_bins_count
            
            device_data.append(device_dict)
        
        return jsonify({
            'ok': True,
            'data': {
                'devices': device_data,
                'pagination': {
                    'page': page,
                    'page_size': page_size,
                    'total': len(devices),
                    'has_more': end_idx < len(devices)
                }
            }
        })
        
    except Exception as e:
        return jsonify({'ok': False, 'error': {'code': 'SERVER_ERROR', 'message': str(e)}}), 500


# Add more endpoints here...

