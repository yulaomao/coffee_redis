"""Alarm model - Device-scoped alarm management."""

from dataclasses import dataclass
from typing import Optional, Dict, List, Any
from datetime import datetime

from app.factory import redis_client
from app.utils.redis_utils import (
    RedisModel, RedisKeys, generate_id, get_current_ts, add_to_index, remove_from_index
)


@dataclass
class Alarm(RedisModel):
    """Device alarm with device-scoped storage."""
    
    alarm_id: str
    device_id: str
    type: str = ""  # material_low, temperature_high, connection_lost, hardware_error, etc.
    severity: str = "medium"  # low, medium, high, critical
    status: str = "open"  # open, acknowledged, closed
    title: str = ""
    message: str = ""
    details: Optional[Dict[str, Any]] = None
    
    # Timestamps
    created_ts: Optional[int] = None
    acknowledged_ts: Optional[int] = None
    closed_ts: Optional[int] = None
    
    # User tracking
    acknowledged_by: str = ""
    closed_by: str = ""
    
    # Metadata
    auto_generated: bool = True
    source: str = "system"  # system, device, user
    tags: Optional[List[str]] = None
    
    @classmethod
    def get(cls, device_id: str, alarm_id: str) -> Optional['Alarm']:
        """Get alarm by device_id and alarm_id."""
        key = RedisKeys.DEVICE_ALARM.format(device_id=device_id, alarm_id=alarm_id)
        data = redis_client.hgetall(key)
        
        if not data:
            return None
        
        return cls(
            alarm_id=alarm_id,
            device_id=device_id,
            type=data.get('type', ''),
            severity=data.get('severity', 'medium'),
            status=data.get('status', 'open'),
            title=data.get('title', ''),
            message=data.get('message', ''),
            details=cls._deserialize_value(data.get('details_json'), dict),
            created_ts=cls._deserialize_value(data.get('created_ts'), int),
            acknowledged_ts=cls._deserialize_value(data.get('acknowledged_ts'), int),
            closed_ts=cls._deserialize_value(data.get('closed_ts'), int),
            acknowledged_by=data.get('acknowledged_by', ''),
            closed_by=data.get('closed_by', ''),
            auto_generated=cls._deserialize_value(data.get('auto_generated'), bool),
            source=data.get('source', 'system'),
            tags=cls._deserialize_value(data.get('tags_json'), list)
        )
    
    @classmethod
    def list_by_device(cls, device_id: str, status: str = None, limit: int = 50, 
                      offset: int = 0) -> List['Alarm']:
        """List alarms for a device, optionally filtered by status."""
        if status:
            # Use status index
            status_key = RedisKeys.DEVICE_ALARMS_STATUS.format(device_id=device_id, status=status)
            alarm_ids = list(redis_client.smembers(status_key))
            
            # Get alarms and sort by created_ts desc
            alarms = []
            for alarm_id in alarm_ids:
                alarm = cls.get(device_id, alarm_id)
                if alarm:
                    alarms.append(alarm)
            
            alarms.sort(key=lambda x: x.created_ts or 0, reverse=True)
            return alarms[offset:offset + limit]
        else:
            # Use time-ordered index
            ts_key = RedisKeys.DEVICE_ALARMS_BY_TS.format(device_id=device_id)
            alarm_ids = redis_client.zrevrange(ts_key, offset, offset + limit - 1)
            
            alarms = []
            for alarm_id in alarm_ids:
                alarm = cls.get(device_id, alarm_id)
                if alarm:
                    alarms.append(alarm)
            
            return alarms
    
    @classmethod
    def list_by_type(cls, alarm_type: str, limit: int = 100) -> List['Alarm']:
        """List alarms by type across all devices."""
        type_key = RedisKeys.IDX_ALARM_TYPE.format(type=alarm_type)
        alarm_refs = list(redis_client.smembers(type_key))
        
        alarms = []
        for ref in alarm_refs[:limit]:
            try:
                device_id, alarm_id = ref.split('|', 1)
                alarm = cls.get(device_id, alarm_id)
                if alarm:
                    alarms.append(alarm)
            except ValueError:
                continue
        
        # Sort by created time desc
        alarms.sort(key=lambda x: x.created_ts or 0, reverse=True)
        return alarms
    
    @classmethod
    def create_material_low_alarm(cls, device_id: str, bin_index: int, 
                                 material_code: str, remaining: float, 
                                 threshold_pct: float) -> 'Alarm':
        """Create a material low alarm."""
        alarm = cls(
            alarm_id=generate_id("alm_"),
            device_id=device_id,
            type="material_low",
            severity="medium",
            title=f"Material Low - Bin {bin_index}",
            message=f"Material {material_code} in bin {bin_index} is low ({remaining:.1f}g, {threshold_pct:.1f}% threshold)",
            details={
                'bin_index': bin_index,
                'material_code': material_code,
                'remaining': remaining,
                'threshold_pct': threshold_pct
            },
            auto_generated=True,
            source="system"
        )
        
        alarm.save()
        return alarm
    
    @classmethod
    def create_device_offline_alarm(cls, device_id: str, last_seen_ts: int) -> 'Alarm':
        """Create a device offline alarm."""
        offline_duration = get_current_ts() - last_seen_ts
        
        alarm = cls(
            alarm_id=generate_id("alm_"),
            device_id=device_id,
            type="device_offline",
            severity="high",
            title="Device Offline",
            message=f"Device has been offline for {offline_duration // 60} minutes",
            details={
                'last_seen_ts': last_seen_ts,
                'offline_duration_seconds': offline_duration
            },
            auto_generated=True,
            source="system"
        )
        
        alarm.save()
        return alarm
    
    def save(self) -> bool:
        """Save alarm to Redis with index updates."""
        if not self.alarm_id:
            self.alarm_id = generate_id("alm_")
        
        if not self.created_ts:
            self.created_ts = get_current_ts()
        
        key = RedisKeys.DEVICE_ALARM.format(device_id=self.device_id, alarm_id=self.alarm_id)
        
        data = {
            'type': self.type,
            'severity': self.severity,
            'status': self.status,
            'title': self.title,
            'message': self.message,
            'details_json': self._serialize_value(self.details),
            'created_ts': self._serialize_value(self.created_ts),
            'acknowledged_ts': self._serialize_value(self.acknowledged_ts),
            'closed_ts': self._serialize_value(self.closed_ts),
            'acknowledged_by': self.acknowledged_by,
            'closed_by': self.closed_by,
            'auto_generated': self._serialize_value(self.auto_generated),
            'source': self.source,
            'tags_json': self._serialize_value(self.tags)
        }
        
        # Save alarm data
        redis_client.hset(key, mapping=data)
        
        # Add to time-ordered index
        ts_key = RedisKeys.DEVICE_ALARMS_BY_TS.format(device_id=self.device_id)
        redis_client.zadd(ts_key, {self.alarm_id: self.created_ts})
        
        # Update status index
        self._update_status_index()
        
        # Add to type index (global)
        if self.type:
            type_key = RedisKeys.IDX_ALARM_TYPE.format(type=self.type)
            add_to_index(type_key, f"{self.device_id}|{self.alarm_id}")
        
        return True
    
    def _update_status_index(self):
        """Update status indexes when status changes."""
        statuses = ['open', 'acknowledged', 'closed']
        
        # Remove from all status indexes first
        for status in statuses:
            status_key = RedisKeys.DEVICE_ALARMS_STATUS.format(device_id=self.device_id, status=status)
            redis_client.srem(status_key, self.alarm_id)
        
        # Add to current status index
        current_status_key = RedisKeys.DEVICE_ALARMS_STATUS.format(
            device_id=self.device_id, status=self.status
        )
        redis_client.sadd(current_status_key, self.alarm_id)
    
    def acknowledge(self, user_id: str = "", save_to_db: bool = True) -> bool:
        """Acknowledge the alarm."""
        if self.status == 'closed':
            return False
        
        self.status = 'acknowledged'
        self.acknowledged_ts = get_current_ts()
        self.acknowledged_by = user_id
        
        if save_to_db:
            key = RedisKeys.DEVICE_ALARM.format(device_id=self.device_id, alarm_id=self.alarm_id)
            redis_client.hset(key, mapping={
                'status': self.status,
                'acknowledged_ts': self._serialize_value(self.acknowledged_ts),
                'acknowledged_by': self.acknowledged_by
            })
            
            self._update_status_index()
        
        return True
    
    def close(self, user_id: str = "", save_to_db: bool = True) -> bool:
        """Close the alarm."""
        self.status = 'closed'
        self.closed_ts = get_current_ts()
        self.closed_by = user_id
        
        if save_to_db:
            key = RedisKeys.DEVICE_ALARM.format(device_id=self.device_id, alarm_id=self.alarm_id)
            redis_client.hset(key, mapping={
                'status': self.status,
                'closed_ts': self._serialize_value(self.closed_ts),
                'closed_by': self.closed_by
            })
            
            self._update_status_index()
        
        return True
    
    def reopen(self, save_to_db: bool = True) -> bool:
        """Reopen a closed alarm."""
        self.status = 'open'
        self.closed_ts = None
        self.closed_by = ""
        
        if save_to_db:
            key = RedisKeys.DEVICE_ALARM.format(device_id=self.device_id, alarm_id=self.alarm_id)
            redis_client.hset(key, mapping={
                'status': self.status,
                'closed_ts': '',
                'closed_by': ''
            })
            
            self._update_status_index()
        
        return True
    
    def is_active(self) -> bool:
        """Check if alarm is active (not closed)."""
        return self.status != 'closed'
    
    def get_age_seconds(self) -> int:
        """Get alarm age in seconds."""
        if not self.created_ts:
            return 0
        
        return get_current_ts() - self.created_ts
    
    def get_severity_level(self) -> int:
        """Get numeric severity level for sorting."""
        severity_levels = {
            'low': 1,
            'medium': 2,  
            'high': 3,
            'critical': 4
        }
        return severity_levels.get(self.severity, 2)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'alarm_id': self.alarm_id,
            'device_id': self.device_id,
            'type': self.type,
            'severity': self.severity,
            'status': self.status,
            'title': self.title,
            'message': self.message,
            'details': self.details or {},
            'created_ts': self.created_ts,
            'acknowledged_ts': self.acknowledged_ts,
            'closed_ts': self.closed_ts,
            'acknowledged_by': self.acknowledged_by,
            'closed_by': self.closed_by,
            'auto_generated': self.auto_generated,
            'source': self.source,
            'tags': self.tags or [],
            'is_active': self.is_active(),
            'age_seconds': self.get_age_seconds(),
            'severity_level': self.get_severity_level()
        }