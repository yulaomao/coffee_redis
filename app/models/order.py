"""Order model - Device-scoped orders."""

from dataclasses import dataclass
from typing import Optional, Dict, List, Any
from datetime import datetime, date

from app.factory import redis_client
from app.utils.redis_utils import (
    RedisModel, RedisKeys, generate_id, get_current_ts, get_day_key,
    increment_daily_counter, add_to_index
)


@dataclass
class Order(RedisModel):
    """Order model with device-scoped storage."""
    
    order_id: str
    device_id: str
    customer_id: Optional[str] = None
    items: Optional[List[Dict[str, Any]]] = None
    total_amount_cents: int = 0
    currency: str = "CNY"
    payment_method: str = ""
    payment_status: str = "pending"  # pending, paid, failed, refunded
    order_status: str = "created"    # created, processing, completed, cancelled
    notes: str = ""
    metadata: Optional[Dict[str, Any]] = None
    created_ts: Optional[int] = None
    updated_ts: Optional[int] = None
    completed_ts: Optional[int] = None
    server_ts: Optional[int] = None  # When received by server
    
    @classmethod
    def get(cls, device_id: str, order_id: str) -> Optional['Order']:
        """Get order by device_id and order_id."""
        key = RedisKeys.DEVICE_ORDER.format(device_id=device_id, order_id=order_id)
        data = redis_client.hgetall(key)
        
        if not data:
            return None
        
        return cls(
            order_id=order_id,
            device_id=device_id,
            customer_id=data.get('customer_id'),
            items=cls._deserialize_value(data.get('items_json'), list),
            total_amount_cents=cls._deserialize_value(data.get('total_amount_cents'), int),
            currency=data.get('currency', 'CNY'),
            payment_method=data.get('payment_method', ''),
            payment_status=data.get('payment_status', 'pending'),
            order_status=data.get('order_status', 'created'),
            notes=data.get('notes', ''),
            metadata=cls._deserialize_value(data.get('metadata_json'), dict),
            created_ts=cls._deserialize_value(data.get('created_ts'), int),
            updated_ts=cls._deserialize_value(data.get('updated_ts'), int),
            completed_ts=cls._deserialize_value(data.get('completed_ts'), int),
            server_ts=cls._deserialize_value(data.get('server_ts'), int)
        )
    
    @classmethod
    def list_by_device(cls, device_id: str, limit: int = 50, offset: int = 0) -> List['Order']:
        """List orders for a device, sorted by server_ts (most recent first)."""
        key = RedisKeys.DEVICE_ORDERS_BY_TS.format(device_id=device_id)
        
        # Get order IDs sorted by timestamp (desc)
        order_ids = redis_client.zrevrange(key, offset, offset + limit - 1)
        
        orders = []
        for order_id in order_ids:
            order = cls.get(device_id, order_id)
            if order:
                orders.append(order)
        
        return orders
    
    @classmethod
    def list_by_time_range(cls, device_id: str, start_ts: int, end_ts: int, limit: int = 100) -> List['Order']:
        """List orders within time range for a device."""
        key = RedisKeys.DEVICE_ORDERS_BY_TS.format(device_id=device_id)
        
        # Get order IDs within time range
        order_ids = redis_client.zrevrangebyscore(key, end_ts, start_ts, start=0, num=limit)
        
        orders = []
        for order_id in order_ids:
            order = cls.get(device_id, order_id)
            if order:
                orders.append(order)
        
        return orders
    
    @classmethod
    def get_daily_stats(cls, device_id: str, target_date: Optional[date] = None) -> Dict[str, Any]:
        """Get daily order statistics for a device."""
        day_key = get_day_key(target_date)
        
        count_key = RedisKeys.DEVICE_AGG_ORDERS_DAY_COUNT.format(
            device_id=device_id, yyyymmdd=day_key
        )
        revenue_key = RedisKeys.DEVICE_AGG_ORDERS_DAY_REVENUE.format(
            device_id=device_id, yyyymmdd=day_key
        )
        
        count = redis_client.get(count_key)
        revenue = redis_client.get(revenue_key)
        
        return {
            'date': day_key,
            'order_count': int(count) if count else 0,
            'revenue_cents': int(revenue) if revenue else 0
        }
    
    def save(self) -> bool:
        """Save order to Redis with aggregations."""
        if not self.order_id:
            self.order_id = generate_id("ord_")
        
        if not self.created_ts:
            self.created_ts = get_current_ts()
        
        if not self.server_ts:
            self.server_ts = get_current_ts()
        
        self.updated_ts = get_current_ts()
        
        key = RedisKeys.DEVICE_ORDER.format(device_id=self.device_id, order_id=self.order_id)
        
        data = {
            'customer_id': self.customer_id or '',
            'items_json': self._serialize_value(self.items),
            'total_amount_cents': self._serialize_value(self.total_amount_cents),
            'currency': self.currency,
            'payment_method': self.payment_method,
            'payment_status': self.payment_status,
            'order_status': self.order_status,
            'notes': self.notes,
            'metadata_json': self._serialize_value(self.metadata),
            'created_ts': self._serialize_value(self.created_ts),
            'updated_ts': self._serialize_value(self.updated_ts),
            'completed_ts': self._serialize_value(self.completed_ts),
            'server_ts': self._serialize_value(self.server_ts)
        }
        
        # Save order data
        redis_client.hset(key, mapping=data)
        
        # Add to time-ordered index
        ts_key = RedisKeys.DEVICE_ORDERS_BY_TS.format(device_id=self.device_id)
        redis_client.zadd(ts_key, {self.order_id: self.server_ts})
        
        # Update daily aggregations
        order_date = datetime.fromtimestamp(self.server_ts).date()
        increment_daily_counter(
            RedisKeys.DEVICE_AGG_ORDERS_DAY_COUNT,
            self.device_id,
            1,
            order_date
        )
        increment_daily_counter(
            RedisKeys.DEVICE_AGG_ORDERS_DAY_REVENUE,
            self.device_id,
            self.total_amount_cents,
            order_date
        )
        
        # Optional: Add to global daily index for cross-device queries
        global_day_key = RedisKeys.IDX_ORDER_DAY.format(yyyymmdd=get_day_key(order_date))
        global_member = f"{self.device_id}|{self.order_id}"
        add_to_index(global_day_key, global_member, self.server_ts)
        
        return True
    
    def update_status(self, payment_status: str = None, order_status: str = None, 
                     completed_ts: int = None, save_to_db: bool = True) -> bool:
        """Update order status."""
        if payment_status:
            self.payment_status = payment_status
        
        if order_status:
            self.order_status = order_status
        
        if completed_ts:
            self.completed_ts = completed_ts
        elif order_status == 'completed' and not self.completed_ts:
            self.completed_ts = get_current_ts()
        
        if save_to_db:
            self.updated_ts = get_current_ts()
            
            key = RedisKeys.DEVICE_ORDER.format(device_id=self.device_id, order_id=self.order_id)
            update_data = {
                'payment_status': self.payment_status,
                'order_status': self.order_status,
                'updated_ts': self._serialize_value(self.updated_ts)
            }
            
            if self.completed_ts:
                update_data['completed_ts'] = self._serialize_value(self.completed_ts)
            
            redis_client.hset(key, mapping=update_data)
        
        return True
    
    def calculate_total(self) -> int:
        """Calculate total amount from items."""
        if not self.items:
            return 0
        
        total = 0
        for item in self.items:
            price = item.get('price_cents', 0)
            quantity = item.get('quantity', 1)
            total += price * quantity
        
        return total
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'order_id': self.order_id,
            'device_id': self.device_id,
            'customer_id': self.customer_id,
            'items': self.items or [],
            'total_amount_cents': self.total_amount_cents,
            'currency': self.currency,
            'payment_method': self.payment_method,
            'payment_status': self.payment_status,
            'order_status': self.order_status,
            'notes': self.notes,
            'metadata': self.metadata or {},
            'created_ts': self.created_ts,
            'updated_ts': self.updated_ts,
            'completed_ts': self.completed_ts,
            'server_ts': self.server_ts
        }