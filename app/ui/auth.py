"""Authentication views."""

from flask import render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, current_user
from werkzeug.security import generate_password_hash

from app.ui import bp
from app.models import User
from app.models.audit import AuditLogger
from app.utils.redis_utils import generate_id, get_current_ts


@bp.route('/login', methods=['GET', 'POST'])
def login():
    """Login page."""
    if current_user.is_authenticated:
        return redirect(url_for('ui.dashboard'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if not username or not password:
            flash('Username and password are required', 'error')
            return render_template('auth/login.html')
        
        user = None
        
        # Try demo mode first
        try:
            from app.utils.demo_data import authenticate_user, init_demo_data
            try:
                user_data = authenticate_user(username, password)
            except:
                init_demo_data()
                user_data = authenticate_user(username, password)
                
            if user_data:
                # Create user object for Flask-Login
                user = User(
                    id=user_data['id'],
                    username=user_data['username'],
                    email=user_data['email'],
                    password_hash=user_data['password_hash'],
                    is_active=user_data['is_active'],
                    is_admin=user_data['is_admin']
                )
        except:
            # Fallback to Redis mode
            user = User.get_by_username(username)
            if user and user.check_password(password):
                user.last_login_ts = get_current_ts()
                user.save()
        
        if user:
            login_user(user, remember=request.form.get('remember_me'))
            
            # Log login event (only in Redis mode)
            try:
                AuditLogger.log_user_login(user.id, {
                    'ip': request.remote_addr,
                    'user_agent': request.headers.get('User-Agent', '')[:200]
                })
            except:
                pass  # Demo mode
            
            next_page = request.args.get('next')
            if next_page:
                return redirect(next_page)
            return redirect(url_for('ui.dashboard'))
        else:
            flash('Invalid username or password', 'error')
    
    return render_template('auth/login.html')


@bp.route('/logout')
def logout():
    """Logout."""
    logout_user()
    return redirect(url_for('ui.login'))


@bp.route('/setup', methods=['GET', 'POST'])
def setup():
    """Initial setup - create admin user."""
    # Check demo mode first
    try:
        from app.utils.demo_data import get_demo_data, init_demo_data
        demo_data = get_demo_data()
        
        if 'admin' in demo_data.get('users', {}):
            flash('Demo mode: Use admin/admin123 to login', 'info')
            return redirect(url_for('ui.login'))
        else:
            init_demo_data()
            flash('Demo mode initialized: Use admin/admin123 to login', 'success')
            return redirect(url_for('ui.login'))
            
    except ImportError:
        pass
    
    # Redis mode
    try:
        # Check if admin user already exists
        admin_user = User.get_by_username('admin')
        if admin_user:
            flash('Setup already completed', 'info')
            return redirect(url_for('ui.login'))
        
        if request.method == 'POST':
            username = request.form.get('username', 'admin')
            password = request.form.get('password')
            email = request.form.get('email', 'admin@example.com')
            
            if not password or len(password) < 6:
                flash('Password must be at least 6 characters', 'error')
                return render_template('auth/setup.html')
            
            # Create admin user
            user = User(
                id=generate_id('user_'),
                username=username,
                email=email,
                password_hash='',
                is_active=True,
                is_admin=True,
                created_ts=get_current_ts()
            )
            user.set_password(password)
            
            if user.save():
                flash('Admin user created successfully. Please log in.', 'success')
                return redirect(url_for('ui.login'))
            else:
                flash('Failed to create admin user', 'error')
        
        return render_template('auth/setup.html')
        
    except Exception:
        # Fallback to demo mode message
        flash('Redis not available. Starting in demo mode with admin/admin123', 'info')
        return redirect(url_for('ui.login'))