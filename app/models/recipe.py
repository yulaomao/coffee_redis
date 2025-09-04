"""Recipe and Package models - Global dictionaries."""

from dataclasses import dataclass
from typing import Optional, Dict, List, Any
import hashlib

from app.factory import redis_client
from app.utils.redis_utils import RedisModel, RedisKeys, generate_id, get_current_ts, add_to_index, remove_from_index


@dataclass
class Recipe(RedisModel):
    """Recipe model - Global recipe dictionary."""
    
    recipe_id: str
    name: str = ""
    description: str = ""
    enabled: bool = True
    version: str = "1.0"
    
    # Recipe schema/steps
    schema: Optional[Dict[str, Any]] = None  # JSON schema for recipe steps
    steps: Optional[List[Dict[str, Any]]] = None  # Actual recipe steps
    
    # Metadata
    category: str = ""  # coffee, tea, specialty
    difficulty: int = 1  # 1-5 difficulty level
    prep_time_seconds: int = 30
    tags: Optional[List[str]] = None
    
    # Versioning
    created_ts: Optional[int] = None
    updated_ts: Optional[int] = None
    created_by: str = ""
    
    @classmethod
    def get(cls, recipe_id: str) -> Optional['Recipe']:
        """Get recipe by ID."""
        key = RedisKeys.RECIPE.format(recipe_id=recipe_id)
        data = redis_client.hgetall(key)
        
        if not data:
            return None
        
        return cls(
            recipe_id=recipe_id,
            name=data.get('name', ''),
            description=data.get('description', ''),
            enabled=cls._deserialize_value(data.get('enabled'), bool),
            version=data.get('version', '1.0'),
            schema=cls._deserialize_value(data.get('schema_json'), dict),
            steps=cls._deserialize_value(data.get('steps_json'), list),
            category=data.get('category', ''),
            difficulty=cls._deserialize_value(data.get('difficulty'), int),
            prep_time_seconds=cls._deserialize_value(data.get('prep_time_seconds'), int),
            tags=cls._deserialize_value(data.get('tags_json'), list),
            created_ts=cls._deserialize_value(data.get('created_ts'), int),
            updated_ts=cls._deserialize_value(data.get('updated_ts'), int),
            created_by=data.get('created_by', '')
        )
    
    @classmethod
    def list_enabled(cls) -> List['Recipe']:
        """List all enabled recipes."""
        enabled_key = RedisKeys.RECIPE_ENABLED
        recipe_ids = redis_client.smembers(enabled_key)
        
        recipes = []
        for recipe_id in recipe_ids:
            recipe = cls.get(recipe_id)
            if recipe:
                recipes.append(recipe)
        
        return recipes
    
    @classmethod
    def list_all(cls) -> List['Recipe']:
        """List all recipes."""
        pattern = "cm:dict:recipe:*"
        recipes = []
        
        for key in redis_client.scan_iter(match=pattern):
            recipe_id = key.split(':')[-1]
            recipe = cls.get(recipe_id)
            if recipe:
                recipes.append(recipe)
        
        return recipes
    
    def save(self) -> bool:
        """Save recipe to Redis."""
        if not self.recipe_id:
            self.recipe_id = generate_id("rcp_")
        
        if not self.created_ts:
            self.created_ts = get_current_ts()
        
        self.updated_ts = get_current_ts()
        
        key = RedisKeys.RECIPE.format(recipe_id=self.recipe_id)
        
        data = {
            'name': self.name,
            'description': self.description,
            'enabled': self._serialize_value(self.enabled),
            'version': self.version,
            'schema_json': self._serialize_value(self.schema),
            'steps_json': self._serialize_value(self.steps),
            'category': self.category,
            'difficulty': self._serialize_value(self.difficulty),
            'prep_time_seconds': self._serialize_value(self.prep_time_seconds),
            'tags_json': self._serialize_value(self.tags),
            'created_ts': self._serialize_value(self.created_ts),
            'updated_ts': self._serialize_value(self.updated_ts),
            'created_by': self.created_by
        }
        
        # Save recipe data
        redis_client.hset(key, mapping=data)
        
        # Update enabled index
        enabled_key = RedisKeys.RECIPE_ENABLED
        if self.enabled:
            add_to_index(enabled_key, self.recipe_id)
        else:
            remove_from_index(enabled_key, self.recipe_id)
        
        return True
    
    def validate_steps(self) -> tuple[bool, List[str]]:
        """Validate recipe steps against schema."""
        errors = []
        
        if not self.steps:
            errors.append("Recipe has no steps defined")
            return False, errors
        
        # Basic validation - can be extended with JSON schema validation
        for i, step in enumerate(self.steps):
            if not isinstance(step, dict):
                errors.append(f"Step {i+1} is not a valid step object")
                continue
            
            if 'type' not in step:
                errors.append(f"Step {i+1} missing required 'type' field")
            
            if 'parameters' not in step:
                errors.append(f"Step {i+1} missing required 'parameters' field")
        
        return len(errors) == 0, errors
    
    def create_package(self, created_by: str = "") -> Optional['RecipePackage']:
        """Create a package from this recipe."""
        if not self.enabled:
            return None
        
        # Validate recipe first
        is_valid, errors = self.validate_steps()
        if not is_valid:
            return None
        
        package = RecipePackage(
            package_id=generate_id("pkg_"),
            type="recipe",
            version=self.version,
            recipe_id=self.recipe_id,
            manifest={
                'recipe_id': self.recipe_id,
                'name': self.name,
                'version': self.version,
                'schema': self.schema,
                'steps': self.steps,
                'metadata': {
                    'category': self.category,
                    'difficulty': self.difficulty,
                    'prep_time_seconds': self.prep_time_seconds,
                    'tags': self.tags
                }
            },
            created_by=created_by
        )
        
        # Calculate package hash
        package.calculate_hash()
        
        if package.save():
            return package
        
        return None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'recipe_id': self.recipe_id,
            'name': self.name,
            'description': self.description,
            'enabled': self.enabled,
            'version': self.version,
            'schema': self.schema or {},
            'steps': self.steps or [],
            'category': self.category,
            'difficulty': self.difficulty,
            'prep_time_seconds': self.prep_time_seconds,
            'tags': self.tags or [],
            'created_ts': self.created_ts,
            'updated_ts': self.updated_ts,
            'created_by': self.created_by
        }


@dataclass
class RecipePackage(RedisModel):
    """Package model for distributing recipes and updates."""
    
    package_id: str
    type: str = "recipe"  # recipe, firmware, config
    version: str = "1.0"
    
    # Package content
    manifest: Optional[Dict[str, Any]] = None  # Package manifest with metadata and content
    package_url: str = ""  # URL to download package (if applicable)
    md5: str = ""  # MD5 hash of package
    size_bytes: int = 0
    
    # Relations
    recipe_id: Optional[str] = None  # If package contains a recipe
    
    # Metadata
    description: str = ""
    notes: str = ""
    created_ts: Optional[int] = None
    created_by: str = ""
    
    @classmethod
    def get(cls, package_id: str) -> Optional['RecipePackage']:
        """Get package by ID."""
        key = RedisKeys.PACKAGE.format(package_id=package_id)
        data = redis_client.hgetall(key)
        
        if not data:
            return None
        
        return cls(
            package_id=package_id,
            type=data.get('type', 'recipe'),
            version=data.get('version', '1.0'),
            manifest=cls._deserialize_value(data.get('manifest_json'), dict),
            package_url=data.get('package_url', ''),
            md5=data.get('md5', ''),
            size_bytes=cls._deserialize_value(data.get('size_bytes'), int),
            recipe_id=data.get('recipe_id'),
            description=data.get('description', ''),
            notes=data.get('notes', ''),
            created_ts=cls._deserialize_value(data.get('created_ts'), int),
            created_by=data.get('created_by', '')
        )
    
    @classmethod
    def list_all(cls) -> List['RecipePackage']:
        """List all packages."""
        pattern = "cm:dict:package:*"
        packages = []
        
        for key in redis_client.scan_iter(match=pattern):
            package_id = key.split(':')[-1]
            package = cls.get(package_id)
            if package:
                packages.append(package)
        
        return packages
    
    def save(self) -> bool:
        """Save package to Redis."""
        if not self.package_id:
            self.package_id = generate_id("pkg_")
        
        if not self.created_ts:
            self.created_ts = get_current_ts()
        
        key = RedisKeys.PACKAGE.format(package_id=self.package_id)
        
        data = {
            'type': self.type,
            'version': self.version,
            'manifest_json': self._serialize_value(self.manifest),
            'package_url': self.package_url,
            'md5': self.md5,
            'size_bytes': self._serialize_value(self.size_bytes),
            'recipe_id': self.recipe_id or '',
            'description': self.description,
            'notes': self.notes,
            'created_ts': self._serialize_value(self.created_ts),
            'created_by': self.created_by
        }
        
        redis_client.hset(key, mapping=data)
        return True
    
    def calculate_hash(self) -> str:
        """Calculate MD5 hash of package manifest."""
        if not self.manifest:
            self.md5 = ""
            return self.md5
        
        manifest_str = self._serialize_value(self.manifest)
        self.md5 = hashlib.md5(manifest_str.encode()).hexdigest()
        return self.md5
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'package_id': self.package_id,
            'type': self.type,
            'version': self.version,
            'manifest': self.manifest or {},
            'package_url': self.package_url,
            'md5': self.md5,
            'size_bytes': self.size_bytes,
            'recipe_id': self.recipe_id,
            'description': self.description,
            'notes': self.notes,
            'created_ts': self.created_ts,
            'created_by': self.created_by
        }


@dataclass
class DevicePackage(RedisModel):
    """Tracks packages installed on devices."""
    
    device_id: str
    package_id: str
    installed_ts: Optional[int] = None
    version: str = ""
    md5: str = ""
    status: str = "installed"  # installed, failed, pending
    error_message: str = ""
    
    @classmethod
    def get(cls, device_id: str, package_id: str) -> Optional['DevicePackage']:
        """Get device package installation record."""
        key = RedisKeys.DEVICE_PACKAGE.format(device_id=device_id, package_id=package_id)
        data = redis_client.hgetall(key)
        
        if not data:
            return None
        
        return cls(
            device_id=device_id,
            package_id=package_id,
            installed_ts=cls._deserialize_value(data.get('installed_ts'), int),
            version=data.get('version', ''),
            md5=data.get('md5', ''),
            status=data.get('status', 'installed'),
            error_message=data.get('error_message', '')
        )
    
    @classmethod
    def list_by_device(cls, device_id: str) -> List['DevicePackage']:
        """List all packages installed on a device."""
        installed_key = RedisKeys.DEVICE_PACKAGES_INSTALLED.format(device_id=device_id)
        package_ids = redis_client.smembers(installed_key)
        
        packages = []
        for package_id in package_ids:
            device_pkg = cls.get(device_id, package_id)
            if device_pkg:
                packages.append(device_pkg)
        
        return packages
    
    def save(self) -> bool:
        """Save device package record."""
        if not self.installed_ts:
            self.installed_ts = get_current_ts()
        
        key = RedisKeys.DEVICE_PACKAGE.format(device_id=self.device_id, package_id=self.package_id)
        
        data = {
            'installed_ts': self._serialize_value(self.installed_ts),
            'version': self.version,
            'md5': self.md5,
            'status': self.status,
            'error_message': self.error_message
        }
        
        redis_client.hset(key, mapping=data)
        
        # Add to installed packages set
        if self.status == 'installed':
            installed_key = RedisKeys.DEVICE_PACKAGES_INSTALLED.format(device_id=self.device_id)
            redis_client.sadd(installed_key, self.package_id)
        
        return True
    
    def get_package(self) -> Optional[RecipePackage]:
        """Get the package definition."""
        return RecipePackage.get(self.package_id)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        package = self.get_package()
        
        return {
            'device_id': self.device_id,
            'package_id': self.package_id,
            'package_name': package.description if package else '',
            'package_type': package.type if package else '',
            'installed_ts': self.installed_ts,
            'version': self.version,
            'md5': self.md5,
            'status': self.status,
            'error_message': self.error_message
        }