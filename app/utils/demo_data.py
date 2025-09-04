"""Demo mode with in-memory data (Redis not required)."""

import json
from datetime import datetime, timedelta, date
from werkzeug.security import generate_password_hash, check_password_hash

# In-memory storage
_demo_data = {
    'users': {},
    'devices': {},
    'orders': {},
    'commands': {},
    'materials': {},
    'bins': {},
    'alarms': {},
    'recipes': {},
    'packages': {},
    'counters': {}
}

def get_demo_data():
    """Get demo data store."""
    return _demo_data

def init_demo_data():
    """Initialize demo data."""
    
    # Create admin user
    _demo_data['users']['admin'] = {
        'id': 'user_admin',
        'username': 'admin',
        'email': 'admin@example.com', 
        'password_hash': generate_password_hash('admin123'),
        'is_active': True,
        'is_admin': True,
        'created_ts': int(datetime.now().timestamp())
    }
    
    # Create materials
    materials = {
        'coffee_arabica': {'name': 'Arabica Coffee Beans', 'type': 'coffee_bean', 'unit': 'g'},
        'coffee_robusta': {'name': 'Robusta Coffee Beans', 'type': 'coffee_bean', 'unit': 'g'},
        'milk': {'name': 'Fresh Milk', 'type': 'milk', 'unit': 'ml'},
        'sugar': {'name': 'White Sugar', 'type': 'sweetener', 'unit': 'g'},
        'cocoa': {'name': 'Cocoa Powder', 'type': 'additive', 'unit': 'g'},
        'cup_paper': {'name': 'Paper Cup 12oz', 'type': 'cup', 'unit': 'pieces'}
    }
    _demo_data['materials'] = materials
    
    # Create devices
    devices = {
        'CM001': {
            'device_id': 'CM001',
            'alias': 'Main Lobby Coffee Machine',
            'model': 'CoffeeMax Pro 3000',
            'status': 'online',
            'last_seen_ts': int(datetime.now().timestamp()) - 300,
            'temperature': 22.5,
            'location': {
                'name': 'Office Building Lobby',
                'address': '123 Business St, Shanghai'
            }
        },
        'CM002': {
            'device_id': 'CM002', 
            'alias': 'Cafeteria Coffee Station',
            'model': 'CoffeeMax Lite 2000',
            'status': 'online',
            'last_seen_ts': int(datetime.now().timestamp()) - 120,
            'temperature': 23.1,
            'location': {
                'name': 'Employee Cafeteria',
                'address': '456 Corporate Ave, Shanghai'
            }
        },
        'CM003': {
            'device_id': 'CM003',
            'alias': 'Mall Kiosk Coffee',
            'model': 'CoffeeMax Express 1500', 
            'status': 'offline',
            'last_seen_ts': int(datetime.now().timestamp()) - 3600,
            'temperature': None,
            'location': {
                'name': 'Central Mall Food Court',
                'address': '789 Shopping Blvd, Shanghai'
            }
        }
    }
    _demo_data['devices'] = devices
    
    # Create bins for devices
    for device_id in devices:
        _demo_data['bins'][device_id] = {
            0: {'bin_index': 0, 'material_code': 'coffee_arabica', 'remaining': 1800, 'capacity': 2000, 'is_low': False},
            1: {'bin_index': 1, 'material_code': 'milk', 'remaining': 450, 'capacity': 3000, 'is_low': True},
            2: {'bin_index': 2, 'material_code': 'sugar', 'remaining': 320, 'capacity': 500, 'is_low': False},
            3: {'bin_index': 3, 'material_code': 'cup_paper', 'remaining': 45, 'capacity': 200, 'is_low': True}
        }
    
    # Create sample orders for today
    today = datetime.now()
    for i, device_id in enumerate(devices):
        orders_count = 15 + i * 5
        daily_revenue = 0
        
        for j in range(orders_count):
            order_id = f'ord_{device_id}_{j:03d}'
            order_time = today - timedelta(hours=j//3, minutes=j*7)
            amount = 800 + (j % 3) * 200  # 800, 1000, 1200 cents
            daily_revenue += amount
            
            _demo_data['orders'][order_id] = {
                'order_id': order_id,
                'device_id': device_id,
                'items': [{'name': 'Americano', 'price_cents': amount}],
                'total_amount_cents': amount,
                'payment_status': 'paid',
                'order_status': 'completed',
                'created_ts': int(order_time.timestamp())
            }
        
        # Store daily stats
        _demo_data['counters'][f'{device_id}_orders_today'] = orders_count
        _demo_data['counters'][f'{device_id}_revenue_today'] = daily_revenue
    
    # Create sample alarms
    _demo_data['alarms']['alm_001'] = {
        'alarm_id': 'alm_001',
        'device_id': 'CM002',
        'type': 'material_low',
        'severity': 'medium',
        'status': 'open',
        'title': 'Milk Supply Low',
        'message': 'Milk level is below 20% threshold',
        'created_ts': int(datetime.now().timestamp()) - 1800
    }
    
    print("Demo data initialized successfully!")

def get_dashboard_summary():
    """Get dashboard summary data."""
    devices = _demo_data['devices']
    
    total_devices = len(devices)
    online_devices = sum(1 for d in devices.values() if d['status'] == 'online')
    online_rate = (online_devices / total_devices * 100) if total_devices > 0 else 0
    
    # Calculate today's sales
    sales_today = sum(_demo_data['counters'].get(f'{device_id}_revenue_today', 0) for device_id in devices)
    
    # Open alarms
    open_alarms = sum(1 for a in _demo_data['alarms'].values() if a['status'] == 'open')
    
    # Low materials
    materials_low = 0
    for device_bins in _demo_data['bins'].values():
        materials_low += sum(1 for bin_data in device_bins.values() if bin_data.get('is_low', False))
    
    # Sample trends (last 7 days)
    trends = {
        'sales': [],
        'online_rate': []
    }
    
    for i in range(7):
        day = datetime.now().date() - timedelta(days=6-i)
        day_key = day.strftime('%Y%m%d')
        
        # Simulate varying sales
        base_sales = sales_today
        day_sales = base_sales + (i - 3) * 2000 + (i % 2) * 3000
        
        trends['sales'].append({
            'date': day_key,
            'value': max(0, day_sales)
        })
        
        # Simulate stable online rate
        day_online_rate = online_rate + (i % 3 - 1) * 5
        trends['online_rate'].append({
            'date': day_key, 
            'value': max(0, min(100, day_online_rate))
        })
    
    return {
        'device_total': total_devices,
        'online_rate': round(online_rate, 1),
        'sales_today': sales_today,
        'sales_week': sales_today * 6,  # Simulate
        'alarms_open': open_alarms,
        'materials_low': materials_low,
        'trends': trends
    }

def get_devices_list():
    """Get devices list with stats."""
    devices = []
    
    for device_data in _demo_data['devices'].values():
        device_id = device_data['device_id']
        
        # Add calculated fields
        device_dict = device_data.copy()
        device_dict['is_online'] = device_data['status'] == 'online' and \
                                  (int(datetime.now().timestamp()) - device_data['last_seen_ts']) <= 300
        
        device_dict['today_orders'] = _demo_data['counters'].get(f'{device_id}_orders_today', 0)
        device_dict['today_revenue_cents'] = _demo_data['counters'].get(f'{device_id}_revenue_today', 0)
        
        # Count low materials
        device_bins = _demo_data['bins'].get(device_id, {})
        low_count = sum(1 for bin_data in device_bins.values() if bin_data.get('is_low', False))
        device_dict['low_materials_count'] = low_count
        
        devices.append(device_dict)
    
    return devices

def get_device_bins_demo(device_id):
    """Get device bins configuration for demo mode."""
    demo_data = get_demo_data()
    device_bins = demo_data['bins'].get(device_id, {})
    
    # Convert to list format expected by UI
    bins = []
    for bin_index in range(4):  # Assume 4 bins per device
        bin_data = device_bins.get(bin_index, {
            'bin_index': bin_index,
            'material_code': '',
            'remaining': 0,
            'capacity': 0,
            'unit': 'g',
            'threshold_low_pct': 20,
            'is_low': False
        })
        bins.append(bin_data)
    
    return bins


def get_orders_list(args=None):
    """Get orders list with filtering and pagination for demo mode."""
    orders = list(_demo_data['orders'].values())
    
    if args:
        # Apply filters
        device_id = args.get('device_id')
        if device_id:
            orders = [o for o in orders if o['device_id'] == device_id]
        
        payment_status = args.get('payment_status')
        if payment_status:
            orders = [o for o in orders if o['payment_status'] == payment_status]
        
        order_status = args.get('order_status')
        if order_status:
            orders = [o for o in orders if o['order_status'] == order_status]
        
        from_date = args.get('from_date')
        to_date = args.get('to_date')
        if from_date or to_date:
            # Filter by date range (simplified)
            if from_date:
                from_ts = int(datetime.strptime(from_date, '%Y-%m-%d').timestamp())
                orders = [o for o in orders if o['created_ts'] >= from_ts]
            if to_date:
                to_ts = int((datetime.strptime(to_date, '%Y-%m-%d') + timedelta(days=1)).timestamp())
                orders = [o for o in orders if o['created_ts'] < to_ts]
    
    # Sort by created timestamp (most recent first)
    orders.sort(key=lambda x: x['created_ts'], reverse=True)
    
    # Pagination
    page = int(args.get('page', 1)) if args else 1
    page_size = int(args.get('page_size', 20)) if args else 20
    
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    page_orders = orders[start_idx:end_idx]
    
    return {
        'orders': page_orders,
        'pagination': {
            'page': page,
            'page_size': page_size,
            'total': len(orders),
            'has_more': end_idx < len(orders)
        }
    }


def authenticate_user(username, password):
    """Authenticate user in demo mode."""
    user_data = _demo_data['users'].get(username)
    if user_data and check_password_hash(user_data['password_hash'], password):
        return user_data
    return None