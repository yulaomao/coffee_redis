#!/usr/bin/env python3
"""Basic test script to validate the app structure."""

import sys
import os

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_imports():
    """Test that all modules can be imported."""
    try:
        from app.factory import create_app
        print("✓ Factory import successful")
        
        from app.models import User, Device, Order, RemoteCommand, Material, Alarm
        print("✓ Models import successful")
        
        from app.utils.redis_utils import RedisKeys, generate_id
        print("✓ Redis utils import successful")
        
        # Test app creation (without Redis connection)
        os.environ['REDIS_URL'] = 'redis://localhost:6379/15'  # Use test DB
        app = create_app('testing')
        print("✓ App creation successful")
        
        print("All imports successful!")
        return True
        
    except ImportError as e:
        print(f"✗ Import error: {e}")
        return False
    except Exception as e:
        print(f"✗ Error: {e}")
        return False


if __name__ == '__main__':
    success = test_imports()
    sys.exit(0 if success else 1)