"""UI views for management interface."""

from flask import render_template, redirect, url_for, flash
from flask_login import login_required

from app.ui import bp


@bp.route('/')
@login_required
def index():
    """Dashboard index page."""
    return redirect(url_for('ui.dashboard'))


@bp.route('/dashboard')
@login_required  
def dashboard():
    """Main dashboard."""
    return render_template('dashboard.html', title='Dashboard')


@bp.route('/devices')
@login_required
def devices():
    """Devices list page."""
    return render_template('devices.html', title='Devices')


@bp.route('/devices/<device_id>')
@login_required
def device_detail(device_id):
    """Device detail page."""
    return render_template('device_detail.html', title='Device Details', device_id=device_id)


@bp.route('/orders')
@login_required
def orders():
    """Orders list page."""
    return render_template('orders.html', title='Orders')


@bp.route('/materials')
@login_required
def materials():
    """Materials management page."""
    return render_template('materials.html', title='Materials')


@bp.route('/recipes')
@login_required
def recipes():
    """Recipes management page."""
    return render_template('recipes.html', title='Recipes')


@bp.route('/dispatch')
@login_required
def dispatch():
    """Command dispatch center."""
    return render_template('dispatch.html', title='Command Dispatch')


@bp.route('/alarms')
@login_required
def alarms():
    """Alarms page."""
    return render_template('alarms.html', title='Alarms')


@bp.route('/audit')
@login_required
def audit():
    """Audit logs page."""
    return render_template('audit.html', title='Audit Logs')