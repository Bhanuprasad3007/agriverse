import click
from flask.cli import with_appcontext
from .models import db, create_sample_schemes, User, GovScheme
from werkzeug.security import generate_password_hash
import traceback

def init_app(app):
    app.cli.add_command(create_sample_schemes)
    app.cli.add_command(create_admin)

@click.command('create-sample-schemes')
@with_appcontext
def create_sample_schemes():
    """Create sample government schemes."""
    from .models import create_sample_schemes
    schemes = create_sample_schemes()
    for scheme in schemes:
        db.session.add(scheme)
    db.session.commit()
    click.echo('Created sample government schemes.')

@click.command('create-admin')
@click.option('--email', prompt=True, help='Admin email address')
@click.option('--password', prompt=True, hide_input=True, confirmation_prompt=True, help='Admin password')
@click.option('--name', prompt=True, help='Admin name')
@with_appcontext
def create_admin(email, password, name):
    """Create an admin user."""
    try:
        click.echo('Starting admin user creation...')
        
        # Input validation
        if not email or not password or not name:
            click.echo('Error: All fields are required.')
            return
            
        # Check if admin already exists
        click.echo('Checking for existing admin...')
        existing_admin = User.query.filter_by(email=email).first()
        if existing_admin:
            click.echo('Error: An user with this email already exists.')
            return

        # Create admin user
        click.echo('Creating admin user...')
        admin = User(
            email=email,
            password_hash=generate_password_hash(password),
            name=name,
            role='admin',
            is_active=True,
            is_verified=True
        )
        
        # Add to database
        click.echo('Adding to database...')
        db.session.add(admin)
        db.session.commit()
        click.echo('Admin user created successfully!')
        click.echo(f'Email: {email}')
        click.echo(f'Name: {name}')
        click.echo('You can now login with these credentials.')
        
    except Exception as e:
        db.session.rollback()
        click.echo('Error creating admin user:')
        click.echo(str(e))
        click.echo('Traceback:')
        click.echo(traceback.format_exc())
        click.echo('\nPlease check your database configuration and try again.') 