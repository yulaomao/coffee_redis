"""Material and Bin models - Device-scoped material management."""

from dataclasses import dataclass
from typing import Optional, Dict, List, Any
from datetime import datetime

from app.factory import redis_client
from app.utils.redis_utils import RedisModel, RedisKeys, get_current_ts


@dataclass
class Material(RedisModel):
    """Material dictionary - global reference for all materials."""
    
    code: str  # Unique material code
    name: str = ""
    type: str = ""  # coffee_bean, milk, sugar, cup, etc.
    unit: str = "g"  # g, ml, pieces
    enabled: bool = True
    description: str = ""
    supplier: str = ""
    cost_per_unit_cents: int = 0
    metadata: Optional[Dict[str, Any]] = None
    created_ts: Optional[int] = None
    updated_ts: Optional[int] = None
    
    @classmethod
    def get(cls, code: str) -> Optional['Material']:
        """Get material by code."""
        key = RedisKeys.MATERIAL.format(code=code)
        data = redis_client.hgetall(key)
        
        if not data:
            return None
        
        return cls(
            code=code,
            name=data.get('name', ''),
            type=data.get('type', ''),
            unit=data.get('unit', 'g'),
            enabled=cls._deserialize_value(data.get('enabled'), bool),
            description=data.get('description', ''),
            supplier=data.get('supplier', ''),
            cost_per_unit_cents=cls._deserialize_value(data.get('cost_per_unit_cents'), int),
            metadata=cls._deserialize_value(data.get('metadata_json'), dict),
            created_ts=cls._deserialize_value(data.get('created_ts'), int),
            updated_ts=cls._deserialize_value(data.get('updated_ts'), int)
        )
    
    @classmethod
    def list_all(cls, enabled_only: bool = False) -> List['Material']:
        """List all materials."""
        pattern = "cm:dict:material:*"
        materials = []
        
        for key in redis_client.scan_iter(match=pattern):
            code = key.split(':')[-1]
            material = cls.get(code)
            if material and (not enabled_only or material.enabled):
                materials.append(material)
        
        return materials
    
    def save(self) -> bool:
        """Save material to Redis."""
        if not self.created_ts:
            self.created_ts = get_current_ts()
        
        self.updated_ts = get_current_ts()
        
        key = RedisKeys.MATERIAL.format(code=self.code)
        
        data = {
            'name': self.name,
            'type': self.type,
            'unit': self.unit,
            'enabled': self._serialize_value(self.enabled),
            'description': self.description,
            'supplier': self.supplier,
            'cost_per_unit_cents': self._serialize_value(self.cost_per_unit_cents),
            'metadata_json': self._serialize_value(self.metadata),
            'created_ts': self._serialize_value(self.created_ts),
            'updated_ts': self._serialize_value(self.updated_ts)
        }
        
        redis_client.hset(key, mapping=data)
        return True
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'code': self.code,
            'name': self.name,
            'type': self.type,
            'unit': self.unit,
            'enabled': self.enabled,
            'description': self.description,
            'supplier': self.supplier,
            'cost_per_unit_cents': self.cost_per_unit_cents,
            'metadata': self.metadata or {},
            'created_ts': self.created_ts,
            'updated_ts': self.updated_ts
        }


@dataclass
class DeviceBin(RedisModel):
    """Material bin for a specific device."""
    
    device_id: str
    bin_index: int  # Physical bin position (0-based)
    material_code: str = ""
    remaining: float = 0.0  # Current amount
    capacity: float = 1000.0  # Maximum capacity
    unit: str = "g"
    threshold_low_pct: float = 20.0  # Low threshold percentage
    last_sync_ts: Optional[int] = None  # Last sync from device
    last_refill_ts: Optional[int] = None
    calibrated: bool = False
    metadata: Optional[Dict[str, Any]] = None
    
    @classmethod
    def get(cls, device_id: str, bin_index: int) -> Optional['DeviceBin']:
        """Get bin by device_id and bin_index."""
        key = RedisKeys.DEVICE_BIN.format(device_id=device_id, bin_index=bin_index)
        data = redis_client.hgetall(key)
        
        if not data:
            return None
        
        return cls(
            device_id=device_id,
            bin_index=bin_index,
            material_code=data.get('material_code', ''),
            remaining=cls._deserialize_value(data.get('remaining'), float),
            capacity=cls._deserialize_value(data.get('capacity'), float),
            unit=data.get('unit', 'g'),
            threshold_low_pct=cls._deserialize_value(data.get('threshold_low_pct'), float),
            last_sync_ts=cls._deserialize_value(data.get('last_sync_ts'), int),
            last_refill_ts=cls._deserialize_value(data.get('last_refill_ts'), int),
            calibrated=cls._deserialize_value(data.get('calibrated'), bool),
            metadata=cls._deserialize_value(data.get('metadata_json'), dict)
        )
    
    @classmethod
    def list_by_device(cls, device_id: str) -> List['DeviceBin']:
        """List all bins for a device."""
        bins_key = RedisKeys.DEVICE_BINS.format(device_id=device_id)
        bin_indices = redis_client.smembers(bins_key)
        
        bins = []
        for bin_index_str in bin_indices:
            try:
                bin_index = int(bin_index_str)
                bin_obj = cls.get(device_id, bin_index)
                if bin_obj:
                    bins.append(bin_obj)
            except ValueError:
                continue
        
        # Sort by bin index
        bins.sort(key=lambda x: x.bin_index)
        return bins
    
    @classmethod
    def list_low_bins(cls, device_id: str) -> List['DeviceBin']:
        """List bins that are below threshold for a device."""
        low_bins_key = RedisKeys.DEVICE_BINS_LOW.format(device_id=device_id)
        low_bin_indices = redis_client.smembers(low_bins_key)
        
        bins = []
        for bin_index_str in low_bin_indices:
            try:
                bin_index = int(bin_index_str)
                bin_obj = cls.get(device_id, bin_index)
                if bin_obj and bin_obj.is_low():
                    bins.append(bin_obj)
            except ValueError:
                continue
        
        bins.sort(key=lambda x: x.bin_index)
        return bins
    
    def save(self) -> bool:
        """Save bin to Redis with automatic low-level tracking."""
        key = RedisKeys.DEVICE_BIN.format(device_id=self.device_id, bin_index=self.bin_index)
        
        data = {
            'material_code': self.material_code,
            'remaining': self._serialize_value(self.remaining),
            'capacity': self._serialize_value(self.capacity),
            'unit': self.unit,
            'threshold_low_pct': self._serialize_value(self.threshold_low_pct),
            'last_sync_ts': self._serialize_value(self.last_sync_ts),
            'last_refill_ts': self._serialize_value(self.last_refill_ts),
            'calibrated': self._serialize_value(self.calibrated),
            'metadata_json': self._serialize_value(self.metadata)
        }
        
        # Save bin data
        redis_client.hset(key, mapping=data)
        
        # Add to device bins set
        bins_key = RedisKeys.DEVICE_BINS.format(device_id=self.device_id)
        redis_client.sadd(bins_key, self.bin_index)
        
        # Update low bins tracking
        low_bins_key = RedisKeys.DEVICE_BINS_LOW.format(device_id=self.device_id)
        if self.is_low():
            redis_client.sadd(low_bins_key, self.bin_index)
        else:
            redis_client.srem(low_bins_key, self.bin_index)
        
        return True
    
    def update_remaining(self, new_amount: float, sync_ts: int = None) -> bool:
        """Update remaining amount and sync timestamp."""
        self.remaining = max(0.0, new_amount)  # Never go negative
        self.last_sync_ts = sync_ts or get_current_ts()
        
        return self.save()
    
    def refill(self, amount: float = None) -> bool:
        """Refill bin to capacity or add specific amount."""
        if amount is None:
            self.remaining = self.capacity
        else:
            self.remaining = min(self.capacity, self.remaining + amount)
        
        self.last_refill_ts = get_current_ts()
        self.last_sync_ts = self.last_refill_ts
        
        return self.save()
    
    def consume(self, amount: float) -> bool:
        """Consume material from bin."""
        if amount <= 0:
            return False
        
        self.remaining = max(0.0, self.remaining - amount)
        self.last_sync_ts = get_current_ts()
        
        return self.save()
    
    def is_low(self) -> bool:
        """Check if bin is below low threshold."""
        if self.capacity <= 0:
            return False
        
        current_pct = (self.remaining / self.capacity) * 100
        return current_pct < self.threshold_low_pct
    
    def is_empty(self) -> bool:
        """Check if bin is empty."""
        return self.remaining <= 0
    
    def get_fill_percentage(self) -> float:
        """Get current fill percentage."""
        if self.capacity <= 0:
            return 0.0
        
        return (self.remaining / self.capacity) * 100
    
    def get_material(self) -> Optional[Material]:
        """Get the material assigned to this bin."""
        if not self.material_code:
            return None
        
        return Material.get(self.material_code)
    
    def bind_material(self, material_code: str, capacity: float = None, 
                      threshold_low_pct: float = None) -> bool:
        """Bind a material to this bin."""
        material = Material.get(material_code)
        if not material:
            return False
        
        self.material_code = material_code
        self.unit = material.unit
        
        if capacity is not None:
            self.capacity = capacity
        
        if threshold_low_pct is not None:
            self.threshold_low_pct = threshold_low_pct
        
        return self.save()
    
    def unbind_material(self) -> bool:
        """Remove material binding from this bin."""
        self.material_code = ""
        self.remaining = 0.0
        self.last_sync_ts = get_current_ts()
        
        return self.save()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        material = self.get_material()
        
        return {
            'device_id': self.device_id,
            'bin_index': self.bin_index,
            'material_code': self.material_code,
            'material_name': material.name if material else '',
            'remaining': self.remaining,
            'capacity': self.capacity,
            'unit': self.unit,
            'threshold_low_pct': self.threshold_low_pct,
            'fill_percentage': self.get_fill_percentage(),
            'is_low': self.is_low(),
            'is_empty': self.is_empty(),
            'last_sync_ts': self.last_sync_ts,
            'last_refill_ts': self.last_refill_ts,
            'calibrated': self.calibrated,
            'metadata': self.metadata or {}
        }