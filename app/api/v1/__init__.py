"""API v1 Blueprint"""
from flask import Blueprint

bp = Blueprint('api_v1', __name__)

# Import routes after blueprint creation to avoid circular imports
from app.api.v1 import routes