"""Command model - Remote command dispatch and lifecycle management."""

from dataclasses import dataclass
from typing import Optional, Dict, List, Any
from datetime import datetime
import json

from app.factory import redis_client
from app.utils.redis_utils import (
    RedisModel, RedisKeys, generate_id, get_current_ts, add_to_index
)


@dataclass
class RemoteCommand(RedisModel):
    """Remote command with device-scoped storage and atomic operations."""
    
    command_id: str
    device_id: str
    command_type: str  # upgrade, config_update, recipe_sync, restart, etc.
    payload: Optional[Dict[str, Any]] = None
    status: str = "pending"  # pending, sent, success, failed
    priority: int = 0  # Higher number = higher priority
    
    # Timestamps
    issued_ts: Optional[int] = None    # When command was created
    sent_ts: Optional[int] = None      # When device claimed command  
    result_ts: Optional[int] = None    # When result was received
    timeout_ts: Optional[int] = None   # When command times out
    
    # Execution details
    attempts: int = 0
    max_attempts: int = 3
    timeout_seconds: int = 300  # 5 minutes default
    
    # Result and error info
    result_payload: Optional[Dict[str, Any]] = None
    last_error: str = ""
    
    # Metadata
    batch_id: Optional[str] = None
    notes: str = ""
    issued_by: str = ""
    
    @classmethod
    def get(cls, device_id: str, command_id: str) -> Optional['RemoteCommand']:
        """Get command by device_id and command_id."""
        key = RedisKeys.DEVICE_COMMAND.format(device_id=device_id, command_id=command_id)
        data = redis_client.hgetall(key)
        
        if not data:
            return None
        
        return cls(
            command_id=command_id,
            device_id=device_id,
            command_type=data.get('command_type', ''),
            payload=cls._deserialize_value(data.get('payload_json'), dict),
            status=data.get('status', 'pending'),
            priority=cls._deserialize_value(data.get('priority'), int),
            issued_ts=cls._deserialize_value(data.get('issued_ts'), int),
            sent_ts=cls._deserialize_value(data.get('sent_ts'), int),
            result_ts=cls._deserialize_value(data.get('result_ts'), int),
            timeout_ts=cls._deserialize_value(data.get('timeout_ts'), int),
            attempts=cls._deserialize_value(data.get('attempts'), int),
            max_attempts=cls._deserialize_value(data.get('max_attempts'), int),
            timeout_seconds=cls._deserialize_value(data.get('timeout_seconds'), int),
            result_payload=cls._deserialize_value(data.get('result_payload_json'), dict),
            last_error=data.get('last_error', ''),
            batch_id=data.get('batch_id'),
            notes=data.get('notes', ''),
            issued_by=data.get('issued_by', '')
        )
    
    @classmethod
    def list_by_device(cls, device_id: str, limit: int = 50, offset: int = 0) -> List['RemoteCommand']:
        """List commands for a device, sorted by issued_ts (most recent first)."""
        key = RedisKeys.DEVICE_COMMANDS_BY_TS.format(device_id=device_id)
        
        # Get command IDs sorted by timestamp (desc)
        command_ids = redis_client.zrevrange(key, offset, offset + limit - 1)
        
        commands = []
        for command_id in command_ids:
            command = cls.get(device_id, command_id)
            if command:
                commands.append(command)
        
        return commands
    
    @classmethod
    def claim_pending_commands(cls, device_id: str, max_commands: int = 5) -> List['RemoteCommand']:
        """
        Atomically claim pending commands for a device.
        This is called by devices when polling for commands.
        """
        # Use Lua script for atomic operation
        lua_script = """
        local device_id = ARGV[1]
        local max_commands = tonumber(ARGV[2])
        local current_ts = tonumber(ARGV[3])
        
        local pending_key = 'cm:dev:' .. device_id .. ':q:cmd:pending'
        local inflight_key = 'cm:dev:' .. device_id .. ':cmd:inflight'
        
        -- Pop up to max_commands from pending queue
        local claimed_ids = {}
        for i = 1, max_commands do
            local cmd_id = redis.call('RPOP', pending_key)
            if not cmd_id then
                break
            end
            
            -- Add to inflight with current timestamp as score
            redis.call('ZADD', inflight_key, current_ts, cmd_id)
            table.insert(claimed_ids, cmd_id)
            
            -- Update command status to 'sent'
            local cmd_key = 'cm:dev:' .. device_id .. ':cmd:' .. cmd_id
            redis.call('HSET', cmd_key, 'status', 'sent', 'sent_ts', current_ts)
            redis.call('HINCRBY', cmd_key, 'attempts', 1)
        end
        
        return claimed_ids
        """
        
        current_ts = get_current_ts()
        claimed_ids = redis_client.eval(lua_script, 0, device_id, max_commands, current_ts)
        
        # Fetch full command data
        commands = []
        for command_id in claimed_ids:
            command = cls.get(device_id, command_id)
            if command:
                commands.append(command)
        
        return commands
    
    @classmethod
    def recover_timed_out_commands(cls, device_id: str = None):
        """
        Recover commands that have timed out from inflight back to pending.
        Called by background task.
        """
        current_ts = get_current_ts()
        
        if device_id:
            device_ids = [device_id]
        else:
            # Get all devices with inflight commands - simplified approach
            # In production, you might maintain an index of devices with inflight commands
            device_ids = []
            pattern = "cm:dev:*:cmd:inflight"
            for key in redis_client.scan_iter(match=pattern):
                parts = key.split(':')
                if len(parts) >= 3:
                    device_ids.append(parts[2])
        
        for dev_id in device_ids:
            cls._recover_device_timed_out_commands(dev_id, current_ts)
    
    @classmethod
    def _recover_device_timed_out_commands(cls, device_id: str, current_ts: int):
        """Recover timed out commands for a specific device."""
        inflight_key = RedisKeys.DEVICE_COMMANDS_INFLIGHT.format(device_id=device_id)
        pending_key = RedisKeys.DEVICE_COMMANDS_PENDING.format(device_id=device_id)
        
        # Find commands that have been inflight too long
        # Commands are scored by their claim timestamp
        timeout_cutoff = current_ts - 300  # Default 5 minutes timeout
        
        timed_out_ids = redis_client.zrangebyscore(inflight_key, 0, timeout_cutoff)
        
        for command_id in timed_out_ids:
            command = cls.get(device_id, command_id)
            if not command:
                continue
            
            # Use command's specific timeout if set
            if command.timeout_ts and current_ts < command.timeout_ts:
                continue
            
            # Check if max attempts exceeded
            if command.attempts >= command.max_attempts:
                # Mark as failed
                command.update_status('failed', f'Timeout after {command.attempts} attempts')
                redis_client.zrem(inflight_key, command_id)
            else:
                # Put back in pending queue for retry
                command.update_status('pending', 'Timeout, retrying')
                redis_client.lpush(pending_key, command_id)
                redis_client.zrem(inflight_key, command_id)
    
    def save(self) -> bool:
        """Save command to Redis and enqueue if pending."""
        if not self.command_id:
            self.command_id = generate_id("cmd_")
        
        if not self.issued_ts:
            self.issued_ts = get_current_ts()
        
        # Set timeout timestamp
        if not self.timeout_ts and self.timeout_seconds > 0:
            self.timeout_ts = self.issued_ts + self.timeout_seconds
        
        key = RedisKeys.DEVICE_COMMAND.format(device_id=self.device_id, command_id=self.command_id)
        
        data = {
            'command_type': self.command_type,
            'payload_json': self._serialize_value(self.payload),
            'status': self.status,
            'priority': self._serialize_value(self.priority),
            'issued_ts': self._serialize_value(self.issued_ts),
            'sent_ts': self._serialize_value(self.sent_ts),
            'result_ts': self._serialize_value(self.result_ts),
            'timeout_ts': self._serialize_value(self.timeout_ts),
            'attempts': self._serialize_value(self.attempts),
            'max_attempts': self._serialize_value(self.max_attempts),
            'timeout_seconds': self._serialize_value(self.timeout_seconds),
            'result_payload_json': self._serialize_value(self.result_payload),
            'last_error': self.last_error,
            'batch_id': self.batch_id or '',
            'notes': self.notes,
            'issued_by': self.issued_by
        }
        
        # Save command data
        redis_client.hset(key, mapping=data)
        
        # Add to time-ordered index
        ts_key = RedisKeys.DEVICE_COMMANDS_BY_TS.format(device_id=self.device_id)
        redis_client.zadd(ts_key, {self.command_id: self.issued_ts})
        
        # If pending, add to pending queue
        if self.status == 'pending':
            pending_key = RedisKeys.DEVICE_COMMANDS_PENDING.format(device_id=self.device_id)
            # Use priority - higher priority goes to front
            if self.priority > 0:
                redis_client.lpush(pending_key, self.command_id)
            else:
                redis_client.rpush(pending_key, self.command_id)
        
        return True
    
    def update_status(self, status: str, error_message: str = "", result_payload: Dict[str, Any] = None):
        """Update command status."""
        self.status = status
        
        if status in ['success', 'failed']:
            self.result_ts = get_current_ts()
            
            # Remove from inflight
            inflight_key = RedisKeys.DEVICE_COMMANDS_INFLIGHT.format(device_id=self.device_id)
            redis_client.zrem(inflight_key, self.command_id)
        
        if error_message:
            self.last_error = error_message
        
        if result_payload:
            self.result_payload = result_payload
        
        # Update in Redis
        key = RedisKeys.DEVICE_COMMAND.format(device_id=self.device_id, command_id=self.command_id)
        update_data = {
            'status': self.status,
            'last_error': self.last_error,
            'result_payload_json': self._serialize_value(self.result_payload)
        }
        
        if self.result_ts:
            update_data['result_ts'] = self._serialize_value(self.result_ts)
        
        redis_client.hset(key, mapping=update_data)
    
    def is_completed(self) -> bool:
        """Check if command is in terminal state."""
        return self.status in ['success', 'failed']
    
    def is_expired(self) -> bool:
        """Check if command has expired."""
        if not self.timeout_ts:
            return False
        return get_current_ts() > self.timeout_ts
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'command_id': self.command_id,
            'device_id': self.device_id,
            'command_type': self.command_type,
            'payload': self.payload or {},
            'status': self.status,
            'priority': self.priority,
            'issued_ts': self.issued_ts,
            'sent_ts': self.sent_ts,
            'result_ts': self.result_ts,
            'timeout_ts': self.timeout_ts,
            'attempts': self.attempts,
            'max_attempts': self.max_attempts,
            'timeout_seconds': self.timeout_seconds,
            'result_payload': self.result_payload or {},
            'last_error': self.last_error,
            'batch_id': self.batch_id,
            'notes': self.notes,
            'issued_by': self.issued_by,
            'is_completed': self.is_completed(),
            'is_expired': self.is_expired()
        }


@dataclass  
class CommandBatch(RedisModel):
    """Batch of commands for bulk operations."""
    
    batch_id: str
    name: str = ""
    description: str = ""
    command_type: str = ""
    total_commands: int = 0
    completed_commands: int = 0
    failed_commands: int = 0
    created_ts: Optional[int] = None
    created_by: str = ""
    
    @classmethod
    def get(cls, batch_id: str) -> Optional['CommandBatch']:
        """Get batch by ID."""
        key = RedisKeys.BATCH.format(batch_id=batch_id)
        data = redis_client.hgetall(key)
        
        if not data:
            return None
        
        return cls(
            batch_id=batch_id,
            name=data.get('name', ''),
            description=data.get('description', ''),
            command_type=data.get('command_type', ''),
            total_commands=cls._deserialize_value(data.get('total_commands'), int),
            completed_commands=cls._deserialize_value(data.get('completed_commands'), int),
            failed_commands=cls._deserialize_value(data.get('failed_commands'), int),
            created_ts=cls._deserialize_value(data.get('created_ts'), int),
            created_by=data.get('created_by', '')
        )
    
    def save(self) -> bool:
        """Save batch to Redis."""
        if not self.batch_id:
            self.batch_id = generate_id("batch_")
        
        if not self.created_ts:
            self.created_ts = get_current_ts()
        
        key = RedisKeys.BATCH.format(batch_id=self.batch_id)
        
        data = {
            'name': self.name,
            'description': self.description,
            'command_type': self.command_type,
            'total_commands': self._serialize_value(self.total_commands),
            'completed_commands': self._serialize_value(self.completed_commands),
            'failed_commands': self._serialize_value(self.failed_commands),
            'created_ts': self._serialize_value(self.created_ts),
            'created_by': self.created_by
        }
        
        redis_client.hset(key, mapping=data)
        return True
    
    def add_command(self, command_id: str, device_id: str):
        """Add command to batch."""
        commands_key = RedisKeys.BATCH_COMMANDS.format(batch_id=self.batch_id)
        redis_client.sadd(commands_key, f"{device_id}|{command_id}")
    
    def get_commands(self) -> List[str]:
        """Get all command IDs in batch."""
        commands_key = RedisKeys.BATCH_COMMANDS.format(batch_id=self.batch_id)
        return list(redis_client.smembers(commands_key))
    
    def update_stats(self):
        """Update completion statistics."""
        command_refs = self.get_commands()
        
        completed = 0
        failed = 0
        
        for ref in command_refs:
            try:
                device_id, command_id = ref.split('|', 1)
                command = RemoteCommand.get(device_id, command_id)
                if command:
                    if command.status == 'success':
                        completed += 1
                    elif command.status == 'failed':
                        failed += 1
            except ValueError:
                continue
        
        self.completed_commands = completed
        self.failed_commands = failed
        self.save()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'batch_id': self.batch_id,
            'name': self.name,
            'description': self.description,
            'command_type': self.command_type,
            'total_commands': self.total_commands,
            'completed_commands': self.completed_commands,
            'failed_commands': self.failed_commands,
            'success_rate': (self.completed_commands / self.total_commands * 100) if self.total_commands > 0 else 0,
            'created_ts': self.created_ts,
            'created_by': self.created_by
        }