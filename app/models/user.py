"""User model for authentication."""

from dataclasses import dataclass
from typing import Optional
from flask_login import UserMixin

from app.factory import redis_client
from app.utils.redis_utils import RedisModel


@dataclass
class User(UserMixin, RedisModel):
    """User model for Flask-Login."""
    
    id: str
    username: str
    email: str
    password_hash: str
    is_active: bool = True
    is_admin: bool = False
    created_ts: Optional[int] = None
    last_login_ts: Optional[int] = None
    
    @classmethod
    def get(cls, user_id: str) -> Optional['User']:
        """Get user by ID."""
        key = f"cm:user:{user_id}"
        data = redis_client.hgetall(key)
        
        if not data:
            return None
        
        return cls(
            id=user_id,
            username=data.get('username', ''),
            email=data.get('email', ''),
            password_hash=data.get('password_hash', ''),
            is_active=cls._deserialize_value(data.get('is_active', '1'), bool),
            is_admin=cls._deserialize_value(data.get('is_admin', '0'), bool),
            created_ts=cls._deserialize_value(data.get('created_ts'), int),
            last_login_ts=cls._deserialize_value(data.get('last_login_ts'), int)
        )
    
    @classmethod
    def get_by_username(cls, username: str) -> Optional['User']:
        """Get user by username."""
        user_id = redis_client.hget("cm:idx:user:username", username)
        if user_id:
            return cls.get(user_id)
        return None
    
    def save(self) -> bool:
        """Save user to Redis."""
        key = f"cm:user:{self.id}"
        
        data = {
            'username': self.username,
            'email': self.email,
            'password_hash': self.password_hash,
            'is_active': self._serialize_value(self.is_active),
            'is_admin': self._serialize_value(self.is_admin),
            'created_ts': self._serialize_value(self.created_ts),
            'last_login_ts': self._serialize_value(self.last_login_ts)
        }
        
        # Save user data
        redis_client.hset(key, mapping=data)
        
        # Update username index
        redis_client.hset("cm:idx:user:username", self.username, self.id)
        
        return True
    
    def check_password(self, password: str) -> bool:
        """Check if password is correct."""
        from werkzeug.security import check_password_hash
        return check_password_hash(self.password_hash, password)
    
    def set_password(self, password: str):
        """Set user password."""
        from werkzeug.security import generate_password_hash
        self.password_hash = generate_password_hash(password)