import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Base configuration."""
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key')
    REDIS_URL = os.getenv('REDIS_URL', 'redis://127.0.0.1:6379/0')
    
    # Flask settings
    FLASK_DEBUG = os.getenv('FLASK_DEBUG', 'false').lower() == 'true'
    FLASK_ENV = os.getenv('FLASK_ENV', 'development')
    
    # Application settings
    ENABLE_SSE = os.getenv('ENABLE_SSE', 'true').lower() == 'true'
    ENABLE_DEVICE_TOKEN = os.getenv('ENABLE_DEVICE_TOKEN', 'false').lower() == 'true'
    DEVICE_TOKEN_SECRET = os.getenv('DEVICE_TOKEN_SECRET', 'device-secret')
    
    # Rate limiting
    RATELIMIT_STORAGE_URL = os.getenv('RATELIMIT_STORAGE_URL', 'redis://127.0.0.1:6379/1')
    
    # Task queue
    CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL', 'redis://127.0.0.1:6379/2')
    CELERY_RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND', 'redis://127.0.0.1:6379/2')
    
    # Monitoring
    ENABLE_METRICS = os.getenv('ENABLE_METRICS', 'true').lower() == 'true'
    
    # Logging
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    LOG_FORMAT = os.getenv('LOG_FORMAT', 'text')
    
    # Security
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = int(os.getenv('WTF_CSRF_TIME_LIMIT', '3600'))
    SESSION_COOKIE_SECURE = os.getenv('SESSION_COOKIE_SECURE', 'false').lower() == 'true'
    SESSION_COOKIE_HTTPONLY = os.getenv('SESSION_COOKIE_HTTPONLY', 'true').lower() == 'true'


class DevelopmentConfig(Config):
    """Development configuration."""
    FLASK_DEBUG = True
    WTF_CSRF_ENABLED = False  # Disable CSRF for demo


class ProductionConfig(Config):
    """Production configuration."""
    FLASK_DEBUG = False
    SESSION_COOKIE_SECURE = True


class TestingConfig(Config):
    """Testing configuration."""
    TESTING = True
    WTF_CSRF_ENABLED = False
    REDIS_URL = 'redis://127.0.0.1:6379/15'  # Use separate DB for tests


config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}