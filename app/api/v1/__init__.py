"""API v1 Blueprint"""
from flask import Blueprint

bp = Blueprint('api_v1', __name__)

from app.api.v1 import dashboard, devices, orders, commands, materials, recipes, packages, alarms, tasks, audit