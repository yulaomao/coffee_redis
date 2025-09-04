import os
import logging
from flask import Flask
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import redis

from config import config

# Extensions
login_manager = LoginManager()
csrf = CSRFProtect()
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"]
)

# Redis connection
redis_client = None


def create_app(config_name=None):
    """Application factory pattern."""
    app = Flask(__name__, 
                template_folder='ui/templates',
                static_folder='ui/static')
    
    # Load configuration
    config_name = config_name or os.getenv('FLASK_ENV', 'development')
    app.config.from_object(config[config_name])
    
    # Initialize Redis
    global redis_client
    try:
        redis_client = redis.from_url(app.config['REDIS_URL'], decode_responses=True)
        redis_client.ping()  # Test connection
        app.logger.info("Redis connection established")
    except Exception as e:
        app.logger.warning(f"Redis not available: {e}. Running in demo mode.")
        redis_client = None
    
    # Initialize extensions
    login_manager.init_app(app)
    login_manager.login_view = 'ui.login'
    login_manager.login_message = 'Please log in to access this page.'
    login_manager.login_message_category = 'info'
    
    csrf.init_app(app)
    
    # Initialize rate limiter
    limiter.init_app(app)
    
    # Setup logging
    setup_logging(app)
    
    # Register blueprints
    register_blueprints(app)
    
    # Register error handlers
    register_error_handlers(app)
    
    return app


def register_blueprints(app):
    """Register application blueprints."""
    from app.api.v1 import bp as api_v1_bp
    from app.ui import bp as ui_bp
    
    app.register_blueprint(api_v1_bp, url_prefix='/api/v1')
    app.register_blueprint(ui_bp)


def register_error_handlers(app):
    """Register error handlers."""
    @app.errorhandler(404)
    def not_found_error(error):
        return {'error': 'Not found'}, 404
    
    @app.errorhandler(500)
    def internal_error(error):
        return {'error': 'Internal server error'}, 500


def setup_logging(app):
    """Setup logging configuration."""
    if not app.debug and not app.testing:
        if app.config.get('LOG_FORMAT') == 'json':
            import json
            import sys
            
            class JSONFormatter(logging.Formatter):
                def format(self, record):
                    log_entry = {
                        'timestamp': self.formatTime(record),
                        'level': record.levelname,
                        'module': record.module,
                        'message': record.getMessage()
                    }
                    return json.dumps(log_entry)
            
            handler = logging.StreamHandler(sys.stdout)
            handler.setFormatter(JSONFormatter())
        else:
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter(
                '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
            ))
        
        handler.setLevel(getattr(logging, app.config.get('LOG_LEVEL', 'INFO')))
        app.logger.addHandler(handler)
        app.logger.setLevel(getattr(logging, app.config.get('LOG_LEVEL', 'INFO')))
        app.logger.info('Coffee Redis Management System startup')


@login_manager.user_loader
def load_user(user_id):
    """Load user for Flask-Login."""
    try:
        from app.models.user import User
        return User.get(user_id)
    except:
        # Demo mode fallback
        from app.utils.demo_data import get_demo_data
        try:
            demo_data = get_demo_data()
            for user_data in demo_data.get('users', {}).values():
                if user_data['id'] == user_id:
                    from app.models.user import User
                    return User(
                        id=user_data['id'],
                        username=user_data['username'],
                        email=user_data['email'],
                        password_hash=user_data['password_hash'],
                        is_active=user_data['is_active'],
                        is_admin=user_data['is_admin']
                    )
        except:
            pass
        return None