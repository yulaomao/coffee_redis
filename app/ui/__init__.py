"""UI Blueprint for management interface"""
from flask import Blueprint

bp = Blueprint('ui', __name__)

# Import routes after blueprint creation
from app.ui import views, auth