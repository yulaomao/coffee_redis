"""UI Blueprint for management interface"""
from flask import Blueprint

bp = Blueprint('ui', __name__)

from app.ui import views, auth