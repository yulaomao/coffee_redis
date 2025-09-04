"""API routes for v1."""

from app.api.v1 import bp

@bp.route('/health')
def health():
    """Health check endpoint."""
    return {'ok': True, 'data': {'status': 'healthy', 'version': '1.0'}}


# Import all route modules
from app.api.v1 import dashboard, devices, orders, commands, materials, recipes, packages, alarms, tasks, audit