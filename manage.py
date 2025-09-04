#!/usr/bin/env python3
"""Management CLI for Coffee Redis System."""

import os
import sys
import click
from flask.cli import with_appcontext

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.factory import create_app


@click.group()
def cli():
    """Coffee Redis Management System CLI."""
    pass


@cli.command()
@click.option('--host', default='127.0.0.1', help='Host to run the server on.')
@click.option('--port', default=5000, help='Port to run the server on.')
@click.option('--debug', is_flag=True, help='Run in debug mode.')
def run_web(host, port, debug):
    """Run the web server."""
    app = create_app()
    app.run(host=host, port=port, debug=debug)


@cli.command()
def run_worker():
    """Run the task worker."""
    from app.tasks.worker import create_worker
    
    app = create_app()
    with app.app_context():
        worker = create_worker()
        worker.start()


@cli.command()
def init_db():
    """Initialize the database with seed data."""
    app = create_app()
    with app.app_context():
        from app.utils.seed_data import initialize_seed_data
        
        click.echo('Initializing database with seed data...')
        initialize_seed_data()
        click.echo('Database initialized successfully.')


@cli.command()
def clear_db():
    """Clear all data from the database."""
    app = create_app()
    with app.app_context():
        from app.factory import redis_client
        
        if click.confirm('This will delete all data. Are you sure?'):
            redis_client.flushdb()
            click.echo('Database cleared.')


@cli.command()
def shell():
    """Start an interactive shell."""
    import code
    app = create_app()
    with app.app_context():
        from app.factory import redis_client
        from app.models import Device, Order, RemoteCommand
        
        local_vars = {
            'app': app,
            'redis': redis_client,
            'Device': Device,
            'Order': Order,
            'Command': RemoteCommand,
        }
        
        code.interact(local=local_vars)


if __name__ == '__main__':
    cli()