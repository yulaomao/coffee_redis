"""Seed data for Coffee Redis Management System."""

import random
from datetime import datetime, date, timedelta
from werkzeug.security import generate_password_hash

from app.factory import redis_client
from app.models import (
    User, Device, Order, RemoteCommand, Material, DeviceBin,
    Alarm, Recipe, RecipePackage
)
from app.utils.redis_utils import generate_id, get_current_ts


def clear_all_data():
    """Clear all Redis data."""
    print("Clearing all Redis data...")
    redis_client.flushdb()
    print("✓ Data cleared")


def create_admin_user():
    """Create default admin user."""
    print("Creating admin user...")
    
    admin = User(
        id=generate_id('user_'),
        username='admin',
        email='admin@example.com',
        password_hash=generate_password_hash('admin123'),
        is_active=True,
        is_admin=True,
        created_ts=get_current_ts()
    )
    
    if admin.save():
        print(f"✓ Admin user created: admin/admin123")
    else:
        print("✗ Failed to create admin user")


def create_materials():
    """Create material dictionary."""
    print("Creating materials...")
    
    materials = [
        {
            'code': 'coffee_arabica',
            'name': 'Arabica Coffee Beans',
            'type': 'coffee_bean',
            'unit': 'g',
            'cost_per_unit_cents': 15
        },
        {
            'code': 'coffee_robusta',
            'name': 'Robusta Coffee Beans',
            'type': 'coffee_bean', 
            'unit': 'g',
            'cost_per_unit_cents': 12
        },
        {
            'code': 'milk',
            'name': 'Fresh Milk',
            'type': 'milk',
            'unit': 'ml',
            'cost_per_unit_cents': 8
        },
        {
            'code': 'sugar',
            'name': 'White Sugar',
            'type': 'sweetener',
            'unit': 'g',
            'cost_per_unit_cents': 2
        },
        {
            'code': 'cocoa',
            'name': 'Cocoa Powder',
            'type': 'additive',
            'unit': 'g',
            'cost_per_unit_cents': 25
        },
        {
            'code': 'cup_paper',
            'name': 'Paper Cup 12oz',
            'type': 'cup',
            'unit': 'pieces',
            'cost_per_unit_cents': 50
        }
    ]
    
    for mat_data in materials:
        material = Material(
            code=mat_data['code'],
            name=mat_data['name'],
            type=mat_data['type'],
            unit=mat_data['unit'],
            enabled=True,
            cost_per_unit_cents=mat_data['cost_per_unit_cents']
        )
        
        if material.save():
            print(f"✓ Material: {material.name}")


def create_recipes():
    """Create sample recipes."""
    print("Creating recipes...")
    
    recipes = [
        {
            'name': 'Americano',
            'category': 'coffee',
            'difficulty': 1,
            'prep_time_seconds': 30,
            'steps': [
                {'type': 'grind_beans', 'parameters': {'material': 'coffee_arabica', 'amount': 18, 'grind_size': 'medium'}},
                {'type': 'brew_espresso', 'parameters': {'shots': 2, 'temperature': 92, 'pressure': 9}},
                {'type': 'add_water', 'parameters': {'amount': 120, 'temperature': 85}},
                {'type': 'serve', 'parameters': {'cup': 'cup_paper'}}
            ]
        },
        {
            'name': 'Cappuccino',
            'category': 'coffee',
            'difficulty': 3,
            'prep_time_seconds': 45,
            'steps': [
                {'type': 'grind_beans', 'parameters': {'material': 'coffee_arabica', 'amount': 18, 'grind_size': 'fine'}},
                {'type': 'brew_espresso', 'parameters': {'shots': 1, 'temperature': 92, 'pressure': 9}},
                {'type': 'steam_milk', 'parameters': {'material': 'milk', 'amount': 60, 'temperature': 65, 'texture': 'microfoam'}},
                {'type': 'pour_milk', 'parameters': {'ratio': 0.5}},
                {'type': 'serve', 'parameters': {'cup': 'cup_paper'}}
            ]
        },
        {
            'name': 'Mocha',
            'category': 'specialty',
            'difficulty': 2,
            'prep_time_seconds': 60,
            'steps': [
                {'type': 'grind_beans', 'parameters': {'material': 'coffee_arabica', 'amount': 16, 'grind_size': 'medium'}},
                {'type': 'add_cocoa', 'parameters': {'material': 'cocoa', 'amount': 10}},
                {'type': 'brew_espresso', 'parameters': {'shots': 1, 'temperature': 92, 'pressure': 9}},
                {'type': 'steam_milk', 'parameters': {'material': 'milk', 'amount': 80, 'temperature': 65}},
                {'type': 'serve', 'parameters': {'cup': 'cup_paper'}}
            ]
        }
    ]
    
    for recipe_data in recipes:
        recipe = Recipe(
            recipe_id=generate_id('rcp_'),
            name=recipe_data['name'],
            category=recipe_data['category'],
            difficulty=recipe_data['difficulty'],
            prep_time_seconds=recipe_data['prep_time_seconds'],
            steps=recipe_data['steps'],
            enabled=True,
            version='1.0'
        )
        
        if recipe.save():
            print(f"✓ Recipe: {recipe.name}")
            
            # Create package
            package = recipe.create_package('admin')
            if package:
                print(f"  ✓ Package: {package.package_id}")


def create_devices():
    """Create sample devices."""
    print("Creating devices...")
    
    device_configs = [
        {
            'device_id': 'CM001',
            'alias': 'Main Lobby Coffee Machine',
            'model': 'CoffeeMax Pro 3000',
            'merchant_id': 'merchant_001',
            'location': {
                'name': 'Office Building Lobby',
                'address': '123 Business St, Shanghai',
                'lat': 31.2304,
                'lng': 121.4737,
                'scene': 'office'
            }
        },
        {
            'device_id': 'CM002',
            'alias': 'Cafeteria Coffee Station',
            'model': 'CoffeeMax Lite 2000',
            'merchant_id': 'merchant_001',
            'location': {
                'name': 'Employee Cafeteria',
                'address': '456 Corporate Ave, Shanghai',
                'lat': 31.2204,
                'lng': 121.4837,
                'scene': 'cafeteria'
            }
        },
        {
            'device_id': 'CM003',
            'alias': 'Mall Kiosk Coffee',
            'model': 'CoffeeMax Express 1500',
            'merchant_id': 'merchant_002',
            'location': {
                'name': 'Central Mall Food Court',
                'address': '789 Shopping Blvd, Shanghai',
                'lat': 31.2104,
                'lng': 121.4937,
                'scene': 'retail'
            }
        },
        {
            'device_id': 'CM004',
            'alias': 'Hotel Breakfast Corner',
            'model': 'CoffeeMax Pro 3000',
            'merchant_id': 'merchant_003',
            'location': {
                'name': 'Grand Hotel Breakfast Area',
                'address': '321 Hospitality Way, Shanghai',
                'lat': 31.1904,
                'lng': 121.5037,
                'scene': 'hotel'
            }
        }
    ]
    
    current_time = get_current_ts()
    
    for device_config in device_configs:
        # Create device
        device = Device(
            device_id=device_config['device_id'],
            alias=device_config['alias'],
            model=device_config['model'],
            merchant_id=device_config['merchant_id'],
            fw_version='2.1.0',
            status=random.choice(['online', 'online', 'online', 'offline']),  # Mostly online
            last_seen_ts=current_time - random.randint(0, 3600),  # Within last hour
            temperature=random.randint(18, 25),
            created_ts=current_time - random.randint(86400, 86400 * 30)  # Created within last 30 days
        )
        
        device.save()
        print(f"✓ Device: {device.device_id} ({device.alias})")
        
        # Set location
        loc = device_config['location']
        device.set_location(
            name=loc['name'],
            address=loc['address'], 
            lat=loc['lat'],
            lng=loc['lng'],
            scene=loc['scene']
        )
        
        # Create bins with materials
        create_device_bins(device.device_id)
        
        # Create some orders
        create_device_orders(device.device_id)
        
        # Create some alarms (randomly)
        if random.random() < 0.3:  # 30% chance
            create_device_alarms(device.device_id)


def create_device_bins(device_id):
    """Create bins for a device."""
    bin_configs = [
        {'index': 0, 'material': 'coffee_arabica', 'capacity': 2000, 'remaining_pct': random.randint(20, 100)},
        {'index': 1, 'material': 'coffee_robusta', 'capacity': 1500, 'remaining_pct': random.randint(15, 90)},
        {'index': 2, 'material': 'milk', 'capacity': 3000, 'remaining_pct': random.randint(25, 95)},
        {'index': 3, 'material': 'sugar', 'capacity': 500, 'remaining_pct': random.randint(10, 80)},
        {'index': 4, 'material': 'cocoa', 'capacity': 300, 'remaining_pct': random.randint(30, 100)},
        {'index': 5, 'material': 'cup_paper', 'capacity': 200, 'remaining_pct': random.randint(20, 100)}
    ]
    
    for bin_config in bin_configs:
        remaining = bin_config['capacity'] * bin_config['remaining_pct'] / 100
        
        bin_obj = DeviceBin(
            device_id=device_id,
            bin_index=bin_config['index'],
            material_code=bin_config['material'],
            remaining=remaining,
            capacity=bin_config['capacity'],
            threshold_low_pct=20.0,
            last_sync_ts=get_current_ts() - random.randint(0, 1800),  # Within last 30 min
            calibrated=True
        )
        
        bin_obj.save()


def create_device_orders(device_id):
    """Create sample orders for a device."""
    recipes = ['Americano', 'Cappuccino', 'Mocha']
    
    # Create orders for last 7 days
    for days_ago in range(7):
        target_date = datetime.now() - timedelta(days=days_ago)
        orders_count = random.randint(5, 30)  # 5-30 orders per day
        
        for _ in range(orders_count):
            recipe_name = random.choice(recipes)
            base_price = {'Americano': 800, 'Cappuccino': 1200, 'Mocha': 1400}[recipe_name]  # cents
            
            # Add some randomness to order time
            order_time = target_date.replace(
                hour=random.randint(7, 19),
                minute=random.randint(0, 59)
            )
            
            order = Order(
                order_id=generate_id('ord_'),
                device_id=device_id,
                items=[{
                    'name': recipe_name,
                    'quantity': 1,
                    'price_cents': base_price
                }],
                total_amount_cents=base_price,
                currency='CNY',
                payment_method=random.choice(['wechat_pay', 'alipay', 'card']),
                payment_status='paid',
                order_status='completed',
                created_ts=int(order_time.timestamp()),
                server_ts=int(order_time.timestamp()),
                completed_ts=int(order_time.timestamp()) + random.randint(30, 120)
            )
            
            order.save()


def create_device_alarms(device_id):
    """Create sample alarms for a device."""
    alarm_types = [
        ('material_low', 'medium', 'Coffee beans running low'),
        ('temperature_high', 'high', 'Machine temperature above normal'),
        ('connection_lost', 'critical', 'Lost network connection'),
        ('maintenance_due', 'low', 'Scheduled maintenance reminder')
    ]
    
    alarm_type, severity, title = random.choice(alarm_types)
    
    alarm = Alarm(
        alarm_id=generate_id('alm_'),
        device_id=device_id,
        type=alarm_type,
        severity=severity,
        title=title,
        message=f"Device {device_id}: {title}",
        status=random.choice(['open', 'open', 'acknowledged']),  # Mostly open
        created_ts=get_current_ts() - random.randint(0, 86400)  # Within last day
    )
    
    alarm.save()


def initialize_seed_data():
    """Initialize all seed data."""
    print("Initializing Coffee Redis Management System seed data...\n")
    
    clear_all_data()
    create_admin_user()
    create_materials()
    create_recipes()
    create_devices()
    
    print(f"\n✓ Seed data initialization complete!")
    print("\nYou can now:")
    print("1. Start the web server: python manage.py run-web")
    print("2. Login with admin/admin123")
    print("3. Visit http://localhost:5000 for the dashboard")


if __name__ == '__main__':
    initialize_seed_data()