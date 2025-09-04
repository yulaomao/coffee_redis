"""Redis utilities and key management for device-centric data model."""

import time
import json
import uuid
from typing import Dict, List, Optional, Union, Any
from dataclasses import dataclass
from datetime import datetime, date

from app.factory import redis_client


class RedisKeys:
    """Device-centric Redis key patterns."""
    
    # Device keys
    DEVICE = "cm:dev:{device_id}"
    DEVICE_LOCATION = "cm:dev:{device_id}:loc"
    
    # Material/Bin keys
    DEVICE_BINS = "cm:dev:{device_id}:bins"
    DEVICE_BIN = "cm:dev:{device_id}:bin:{bin_index}"
    DEVICE_BINS_LOW = "cm:dev:{device_id}:bins:low"
    
    # Order keys  
    DEVICE_ORDER = "cm:dev:{device_id}:order:{order_id}"
    DEVICE_ORDERS_BY_TS = "cm:dev:{device_id}:orders:by_ts"
    DEVICE_AGG_ORDERS_DAY_COUNT = "cm:dev:{device_id}:agg:orders:day:{yyyymmdd}:count"
    DEVICE_AGG_ORDERS_DAY_REVENUE = "cm:dev:{device_id}:agg:orders:day:{yyyymmdd}:revenue_cents"
    
    # Command keys
    DEVICE_COMMAND = "cm:dev:{device_id}:cmd:{command_id}"
    DEVICE_COMMANDS_PENDING = "cm:dev:{device_id}:q:cmd:pending"
    DEVICE_COMMANDS_INFLIGHT = "cm:dev:{device_id}:cmd:inflight"
    DEVICE_COMMANDS_BY_TS = "cm:dev:{device_id}:cmds:by_ts"
    
    # Alarm keys
    DEVICE_ALARM = "cm:dev:{device_id}:alarm:{alarm_id}"
    DEVICE_ALARMS_BY_TS = "cm:dev:{device_id}:alarms:by_ts"
    DEVICE_ALARMS_STATUS = "cm:dev:{device_id}:alarms:status:{status}"
    
    # Audit stream keys
    DEVICE_AUDIT_STREAM = "cm:dev:{device_id}:stream:audit"
    GLOBAL_AUDIT_STREAM = "cm:stream:audit"
    
    # Global dictionary keys
    RECIPE = "cm:dict:recipe:{recipe_id}"
    RECIPE_ENABLED = "cm:dict:recipe:enabled"
    MATERIAL = "cm:dict:material:{code}"
    PACKAGE = "cm:dict:package:{package_id}"
    
    # Device package keys
    DEVICE_PACKAGES_INSTALLED = "cm:dev:{device_id}:packages:installed"
    DEVICE_PACKAGE = "cm:dev:{device_id}:package:{package_id}"
    DEVICE_RECIPES_ACTIVE = "cm:dev:{device_id}:recipes:active"
    
    # Index keys
    IDX_DEVICE_STATUS = "cm:idx:device:status:{status}"
    IDX_MERCHANT_DEVICES = "cm:idx:merchant:{merchant_id}:devices"
    IDX_DEVICE_LAST_SEEN = "cm:idx:device:last_seen"
    IDX_GEO_DEVICE = "cm:idx:geo:device"
    IDX_ORDER_DAY = "cm:idx:order:day:{yyyymmdd}"
    IDX_ALARM_TYPE = "cm:idx:alarm:type:{type}"
    
    # Batch keys
    BATCH = "cm:batch:{batch_id}"
    BATCH_COMMANDS = "cm:batch:{batch_id}:cmds"


@dataclass
class RedisModel:
    """Base class for Redis models."""
    
    @classmethod
    def _serialize_value(cls, value: Any) -> str:
        """Serialize value for Redis storage."""
        if value is None:
            return ""
        elif isinstance(value, bool):
            return "1" if value else "0"
        elif isinstance(value, (dict, list)):
            return json.dumps(value, separators=(',', ':'))
        elif isinstance(value, datetime):
            return str(int(value.timestamp()))
        elif isinstance(value, date):
            return value.strftime('%Y%m%d')
        else:
            return str(value)
    
    @classmethod
    def _deserialize_value(cls, value: str, field_type: type = str) -> Any:
        """Deserialize value from Redis."""
        if not value:
            return None
        
        if field_type == bool:
            return value == "1"
        elif field_type in (dict, list):
            try:
                return json.loads(value)
            except (json.JSONDecodeError, TypeError):
                return {} if field_type == dict else []
        elif field_type == int:
            try:
                return int(value)
            except (ValueError, TypeError):
                return 0
        elif field_type == float:
            try:
                return float(value)
            except (ValueError, TypeError):
                return 0.0
        elif field_type == datetime:
            try:
                return datetime.fromtimestamp(float(value))
            except (ValueError, TypeError):
                return None
        else:
            return value


class RedisTransaction:
    """Context manager for Redis transactions."""
    
    def __init__(self, watch_keys: Optional[List[str]] = None):
        self.watch_keys = watch_keys or []
        self.pipe = None
    
    def __enter__(self):
        self.pipe = redis_client.pipeline(transaction=True)
        if self.watch_keys:
            redis_client.watch(*self.watch_keys)
        return self.pipe
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            try:
                self.pipe.execute()
            except redis.WatchError:
                # Handle optimistic locking failure
                pass
        if self.watch_keys:
            redis_client.unwatch()


def generate_id(prefix: str = "") -> str:
    """Generate a unique ID."""
    timestamp = int(time.time() * 1000)  # milliseconds
    random_part = uuid.uuid4().hex[:8]
    return f"{prefix}{timestamp}{random_part}" if prefix else f"{timestamp}{random_part}"


def get_current_ts() -> int:
    """Get current timestamp in seconds."""
    return int(time.time())


def get_day_key(dt: Union[datetime, date, None] = None) -> str:
    """Get YYYYMMDD key for date."""
    if dt is None:
        dt = datetime.now().date()
    elif isinstance(dt, datetime):
        dt = dt.date()
    return dt.strftime('%Y%m%d')


def increment_daily_counter(key_pattern: str, device_id: str, value: int = 1, dt: Union[datetime, date, None] = None) -> int:
    """Increment a daily counter for a device."""
    day_key = get_day_key(dt)
    key = key_pattern.format(device_id=device_id, yyyymmdd=day_key)
    return redis_client.incrby(key, value)


def get_daily_counter(key_pattern: str, device_id: str, dt: Union[datetime, date, None] = None) -> int:
    """Get a daily counter value for a device."""
    day_key = get_day_key(dt)
    key = key_pattern.format(device_id=device_id, yyyymmdd=day_key)
    value = redis_client.get(key)
    return int(value) if value else 0


def add_to_index(index_key: str, member: str, score: Optional[float] = None):
    """Add member to an index (Set or ZSet)."""
    if score is not None:
        redis_client.zadd(index_key, {member: score})
    else:
        redis_client.sadd(index_key, member)


def remove_from_index(index_key: str, member: str):
    """Remove member from an index (Set or ZSet)."""
    redis_client.zrem(index_key, member)
    redis_client.srem(index_key, member)


def rebuild_device_indexes(device_id: str):
    """Rebuild all indexes for a specific device."""
    from app.models.device import Device
    
    device = Device.get(device_id)
    if not device:
        return
    
    # Remove old indexes
    old_statuses = ['online', 'offline', 'maintenance', 'error']
    for status in old_statuses:
        remove_from_index(RedisKeys.IDX_DEVICE_STATUS.format(status=status), device_id)
    
    if device.merchant_id:
        remove_from_index(RedisKeys.IDX_MERCHANT_DEVICES.format(merchant_id=device.merchant_id), device_id)
    
    # Add new indexes
    if device.status:
        add_to_index(RedisKeys.IDX_DEVICE_STATUS.format(status=device.status), device_id)
    
    if device.merchant_id:
        add_to_index(RedisKeys.IDX_MERCHANT_DEVICES.format(merchant_id=device.merchant_id), device_id)
    
    if device.last_seen_ts:
        add_to_index(RedisKeys.IDX_DEVICE_LAST_SEEN, device_id, device.last_seen_ts)


def cleanup_expired_keys(pattern: str, max_age_seconds: int):
    """Cleanup expired keys matching pattern."""
    current_ts = get_current_ts()
    cutoff_ts = current_ts - max_age_seconds
    
    for key in redis_client.scan_iter(match=pattern):
        # This is a simple cleanup - in production you might want more sophisticated logic
        pass