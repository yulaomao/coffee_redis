"""Device model - Core entity in device-centric architecture."""

from dataclasses import dataclass
from typing import Optional, Dict, List, Any
from datetime import datetime

from app.factory import redis_client
from app.utils.redis_utils import (
    RedisModel, RedisKeys, generate_id, get_current_ts,
    add_to_index, remove_from_index, rebuild_device_indexes
)


@dataclass
class Device(RedisModel):
    """Device model with device-centric Redis storage."""
    
    device_id: str
    merchant_id: Optional[str] = None
    alias: str = ""
    model: str = ""
    fw_version: str = ""
    status: str = "offline"  # online, offline, maintenance, error
    last_seen_ts: Optional[int] = None
    ip: str = ""
    wifi_ssid: str = ""
    temperature: Optional[float] = None
    tags: Optional[Dict[str, Any]] = None
    extra: Optional[Dict[str, Any]] = None
    created_ts: Optional[int] = None
    updated_ts: Optional[int] = None
    
    @classmethod
    def get(cls, device_id: str) -> Optional['Device']:
        """Get device by ID."""
        key = RedisKeys.DEVICE.format(device_id=device_id)
        data = redis_client.hgetall(key)
        
        if not data:
            return None
        
        return cls(
            device_id=device_id,
            merchant_id=data.get('merchant_id'),
            alias=data.get('alias', ''),
            model=data.get('model', ''),
            fw_version=data.get('fw_version', ''),
            status=data.get('status', 'offline'),
            last_seen_ts=cls._deserialize_value(data.get('last_seen_ts'), int),
            ip=data.get('ip', ''),
            wifi_ssid=data.get('wifi_ssid', ''),
            temperature=cls._deserialize_value(data.get('temperature'), float),
            tags=cls._deserialize_value(data.get('tags_json'), dict),
            extra=cls._deserialize_value(data.get('extra_json'), dict),
            created_ts=cls._deserialize_value(data.get('created_ts'), int),
            updated_ts=cls._deserialize_value(data.get('updated_ts'), int)
        )
    
    @classmethod  
    def list_by_status(cls, status: str, limit: int = 100) -> List['Device']:
        """List devices by status."""
        key = RedisKeys.IDX_DEVICE_STATUS.format(status=status)
        device_ids = redis_client.smembers(key)
        
        devices = []
        for device_id in list(device_ids)[:limit]:
            device = cls.get(device_id)
            if device:
                devices.append(device)
        
        return devices
    
    @classmethod
    def list_by_merchant(cls, merchant_id: str, limit: int = 100) -> List['Device']:
        """List devices by merchant."""
        key = RedisKeys.IDX_MERCHANT_DEVICES.format(merchant_id=merchant_id)
        device_ids = redis_client.smembers(key)
        
        devices = []
        for device_id in list(device_ids)[:limit]:
            device = cls.get(device_id)
            if device:
                devices.append(device)
        
        return devices
    
    @classmethod
    def list_recently_seen(cls, limit: int = 100) -> List['Device']:
        """List devices by last seen time (most recent first)."""
        key = RedisKeys.IDX_DEVICE_LAST_SEEN
        device_ids = redis_client.zrevrange(key, 0, limit - 1)
        
        devices = []
        for device_id in device_ids:
            device = cls.get(device_id)
            if device:
                devices.append(device)
        
        return devices
    
    def save(self) -> bool:
        """Save device to Redis with index updates."""
        if not self.device_id:
            self.device_id = generate_id("dev_")
        
        if not self.created_ts:
            self.created_ts = get_current_ts()
        
        self.updated_ts = get_current_ts()
        
        key = RedisKeys.DEVICE.format(device_id=self.device_id)
        
        data = {
            'merchant_id': self.merchant_id or '',
            'alias': self.alias,
            'model': self.model,
            'fw_version': self.fw_version,
            'status': self.status,
            'last_seen_ts': self._serialize_value(self.last_seen_ts),
            'ip': self.ip,
            'wifi_ssid': self.wifi_ssid,
            'temperature': self._serialize_value(self.temperature),
            'tags_json': self._serialize_value(self.tags),
            'extra_json': self._serialize_value(self.extra),
            'created_ts': self._serialize_value(self.created_ts),
            'updated_ts': self._serialize_value(self.updated_ts)
        }
        
        # Save device data
        redis_client.hset(key, mapping=data)
        
        # Update indexes
        rebuild_device_indexes(self.device_id)
        
        return True
    
    def update_status(self, status: str, save_to_db: bool = True) -> bool:
        """Update device status."""
        old_status = self.status
        self.status = status
        self.last_seen_ts = get_current_ts()
        
        if save_to_db:
            # Update status in Redis
            key = RedisKeys.DEVICE.format(device_id=self.device_id)
            redis_client.hset(key, mapping={
                'status': status,
                'last_seen_ts': self._serialize_value(self.last_seen_ts),
                'updated_ts': self._serialize_value(get_current_ts())
            })
            
            # Update indexes
            if old_status != status:
                if old_status:
                    remove_from_index(RedisKeys.IDX_DEVICE_STATUS.format(status=old_status), self.device_id)
                add_to_index(RedisKeys.IDX_DEVICE_STATUS.format(status=status), self.device_id)
            
            # Update last seen index
            add_to_index(RedisKeys.IDX_DEVICE_LAST_SEEN, self.device_id, self.last_seen_ts)
        
        return True
    
    def is_online(self) -> bool:
        """Check if device is online (last seen within 5 minutes)."""
        if not self.last_seen_ts:
            return False
        
        current_ts = get_current_ts()
        return (current_ts - self.last_seen_ts) <= 300  # 5 minutes
    
    def get_location(self) -> Optional[Dict[str, Any]]:
        """Get device location data."""
        key = RedisKeys.DEVICE_LOCATION.format(device_id=self.device_id)
        data = redis_client.hgetall(key)
        
        if not data:
            return None
        
        return {
            'name': data.get('name', ''),
            'address': data.get('address', ''),
            'lat': self._deserialize_value(data.get('lat'), float),
            'lng': self._deserialize_value(data.get('lng'), float),
            'scene': data.get('scene', ''),
            'updated_ts': self._deserialize_value(data.get('updated_ts'), int)
        }
    
    def set_location(self, name: str = '', address: str = '', lat: float = None, lng: float = None, scene: str = ''):
        """Set device location."""
        key = RedisKeys.DEVICE_LOCATION.format(device_id=self.device_id)
        
        data = {
            'name': name,
            'address': address,
            'lat': self._serialize_value(lat),
            'lng': self._serialize_value(lng),
            'scene': scene,
            'updated_ts': self._serialize_value(get_current_ts())
        }
        
        redis_client.hset(key, mapping=data)
        
        # Update geo index if coordinates provided
        if lat is not None and lng is not None:
            geo_key = RedisKeys.IDX_GEO_DEVICE
            redis_client.geoadd(geo_key, [lng, lat, self.device_id])
    
    def delete(self) -> bool:
        """Delete device and all related data."""
        # Delete main device data
        key = RedisKeys.DEVICE.format(device_id=self.device_id)
        redis_client.delete(key)
        
        # Delete location
        loc_key = RedisKeys.DEVICE_LOCATION.format(device_id=self.device_id)
        redis_client.delete(loc_key)
        
        # Remove from indexes
        if self.status:
            remove_from_index(RedisKeys.IDX_DEVICE_STATUS.format(status=self.status), self.device_id)
        
        if self.merchant_id:
            remove_from_index(RedisKeys.IDX_MERCHANT_DEVICES.format(merchant_id=self.merchant_id), self.device_id)
        
        remove_from_index(RedisKeys.IDX_DEVICE_LAST_SEEN, self.device_id)
        
        # Delete geo data
        geo_key = RedisKeys.IDX_GEO_DEVICE
        redis_client.zrem(geo_key, self.device_id)
        
        # Note: This doesn't delete orders, commands, alarms etc.
        # In production you might want to clean those up too or have TTL
        
        return True
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'device_id': self.device_id,
            'merchant_id': self.merchant_id,
            'alias': self.alias,
            'model': self.model,
            'fw_version': self.fw_version,
            'status': self.status,
            'last_seen_ts': self.last_seen_ts,
            'ip': self.ip,
            'wifi_ssid': self.wifi_ssid,
            'temperature': self.temperature,
            'tags': self.tags or {},
            'extra': self.extra or {},
            'created_ts': self.created_ts,
            'updated_ts': self.updated_ts,
            'is_online': self.is_online(),
            'location': self.get_location()
        }