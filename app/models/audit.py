"""Audit model using Redis Streams."""

from dataclasses import dataclass
from typing import Optional, Dict, List, Any, Union
from datetime import datetime

from app.factory import redis_client
from app.utils.redis_utils import RedisModel, RedisKeys, get_current_ts


@dataclass
class AuditEvent(RedisModel):
    """Audit event stored in Redis streams."""
    
    event_id: str  # Redis stream message ID
    device_id: Optional[str] = None  # None for global events
    action: str = ""  # login, device_update, order_create, command_dispatch, etc.
    target_type: str = ""  # device, order, command, user, etc.
    target_id: str = ""
    actor_type: str = "user"  # user, device, system
    actor_id: str = ""
    details: Optional[Dict[str, Any]] = None
    timestamp: Optional[int] = None
    
    @classmethod
    def add_global_event(cls, action: str, target_type: str = "", target_id: str = "",
                        actor_type: str = "user", actor_id: str = "",
                        details: Dict[str, Any] = None) -> str:
        """Add a global audit event."""
        
        stream_key = RedisKeys.GLOBAL_AUDIT_STREAM
        
        event_data = {
            'action': action,
            'target_type': target_type,
            'target_id': target_id,
            'actor_type': actor_type,
            'actor_id': actor_id,
            'timestamp': str(get_current_ts()),
            'details_json': cls._serialize_value(details) if details else "{}"
        }
        
        # Add to stream
        event_id = redis_client.xadd(stream_key, event_data)
        
        # Trim stream to keep last 10000 events
        redis_client.xtrim(stream_key, maxlen=10000, approximate=True)
        
        return event_id
    
    @classmethod
    def add_device_event(cls, device_id: str, action: str, target_type: str = "",
                        target_id: str = "", actor_type: str = "device",
                        actor_id: str = "", details: Dict[str, Any] = None) -> str:
        """Add a device-specific audit event."""
        
        stream_key = RedisKeys.DEVICE_AUDIT_STREAM.format(device_id=device_id)
        
        event_data = {
            'device_id': device_id,
            'action': action,
            'target_type': target_type,
            'target_id': target_id,
            'actor_type': actor_type,
            'actor_id': actor_id or device_id,
            'timestamp': str(get_current_ts()),
            'details_json': cls._serialize_value(details) if details else "{}"
        }
        
        # Add to stream
        event_id = redis_client.xadd(stream_key, event_data)
        
        # Trim stream to keep last 1000 events per device
        redis_client.xtrim(stream_key, maxlen=1000, approximate=True)
        
        return event_id
    
    @classmethod
    def list_global_events(cls, count: int = 100, start_id: str = None) -> List['AuditEvent']:
        """List global audit events."""
        stream_key = RedisKeys.GLOBAL_AUDIT_STREAM
        
        if start_id:
            # Get events from specific ID
            messages = redis_client.xrange(stream_key, min=start_id, count=count)
        else:
            # Get latest events
            messages = redis_client.xrevrange(stream_key, count=count)
        
        events = []
        for event_id, fields in messages:
            event = cls._create_from_stream_message(event_id, fields)
            if event:
                events.append(event)
        
        return events
    
    @classmethod
    def list_device_events(cls, device_id: str, count: int = 100,
                          start_id: str = None) -> List['AuditEvent']:
        """List device-specific audit events."""
        stream_key = RedisKeys.DEVICE_AUDIT_STREAM.format(device_id=device_id)
        
        if start_id:
            messages = redis_client.xrange(stream_key, min=start_id, count=count)
        else:
            messages = redis_client.xrevrange(stream_key, count=count)
        
        events = []
        for event_id, fields in messages:
            event = cls._create_from_stream_message(event_id, fields, device_id=device_id)
            if event:
                events.append(event)
        
        return events
    
    @classmethod
    def _create_from_stream_message(cls, event_id: str, fields: Dict[str, str],
                                   device_id: str = None) -> Optional['AuditEvent']:
        """Create AuditEvent from Redis stream message."""
        try:
            return cls(
                event_id=event_id,
                device_id=device_id or fields.get('device_id'),
                action=fields.get('action', ''),
                target_type=fields.get('target_type', ''),
                target_id=fields.get('target_id', ''),
                actor_type=fields.get('actor_type', 'user'),
                actor_id=fields.get('actor_id', ''),
                details=cls._deserialize_value(fields.get('details_json', '{}'), dict),
                timestamp=cls._deserialize_value(fields.get('timestamp'), int)
            )
        except Exception:
            return None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'event_id': self.event_id,
            'device_id': self.device_id,
            'action': self.action,
            'target_type': self.target_type,
            'target_id': self.target_id,
            'actor_type': self.actor_type,
            'actor_id': self.actor_id,
            'details': self.details or {},
            'timestamp': self.timestamp
        }


class AuditLogger:
    """Helper class for common audit operations."""
    
    @staticmethod
    def log_user_login(user_id: str, details: Dict[str, Any] = None):
        """Log user login event."""
        AuditEvent.add_global_event(
            action="user_login",
            target_type="user",
            target_id=user_id,
            actor_type="user",
            actor_id=user_id,
            details=details
        )
    
    @staticmethod
    def log_device_status_change(device_id: str, old_status: str, new_status: str,
                                user_id: str = ""):
        """Log device status change."""
        details = {
            'old_status': old_status,
            'new_status': new_status
        }
        
        AuditEvent.add_device_event(
            device_id=device_id,
            action="device_status_change",
            target_type="device",
            target_id=device_id,
            actor_type="user" if user_id else "system",
            actor_id=user_id or "system",
            details=details
        )
    
    @staticmethod
    def log_order_created(device_id: str, order_id: str, total_amount_cents: int):
        """Log order creation."""
        details = {
            'total_amount_cents': total_amount_cents
        }
        
        AuditEvent.add_device_event(
            device_id=device_id,
            action="order_created",
            target_type="order",
            target_id=order_id,
            actor_type="device",
            actor_id=device_id,
            details=details
        )
    
    @staticmethod
    def log_command_dispatched(device_id: str, command_id: str, command_type: str,
                              user_id: str = "", batch_id: str = ""):
        """Log command dispatch."""
        details = {
            'command_type': command_type,
            'batch_id': batch_id
        }
        
        AuditEvent.add_device_event(
            device_id=device_id,
            action="command_dispatched",
            target_type="command",
            target_id=command_id,
            actor_type="user" if user_id else "system",
            actor_id=user_id or "system",
            details=details
        )
    
    @staticmethod
    def log_command_completed(device_id: str, command_id: str, status: str, error: str = ""):
        """Log command completion."""
        details = {
            'status': status,
            'error': error
        }
        
        AuditEvent.add_device_event(
            device_id=device_id,
            action="command_completed",
            target_type="command",
            target_id=command_id,
            actor_type="device",
            actor_id=device_id,
            details=details
        )
    
    @staticmethod
    def log_alarm_created(device_id: str, alarm_id: str, alarm_type: str, severity: str):
        """Log alarm creation."""
        details = {
            'alarm_type': alarm_type,
            'severity': severity
        }
        
        AuditEvent.add_device_event(
            device_id=device_id,
            action="alarm_created",
            target_type="alarm",
            target_id=alarm_id,
            actor_type="system",
            details=details
        )
    
    @staticmethod
    def log_material_refilled(device_id: str, bin_index: int, material_code: str,
                             amount: float, user_id: str = ""):
        """Log material refill."""
        details = {
            'bin_index': bin_index,
            'material_code': material_code,
            'amount': amount
        }
        
        AuditEvent.add_device_event(
            device_id=device_id,
            action="material_refilled",
            target_type="bin",
            target_id=f"{device_id}:{bin_index}",
            actor_type="user" if user_id else "device",
            actor_id=user_id or device_id,
            details=details
        )