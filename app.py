"""
Main application entry point for Invoice Extraction System
"""

import os
from app import create_app, db
from app.models import User, Company, Customer, InvoiceHeader, LineItem, ProcessingLog

# Create Flask application
app = create_app()

@app.shell_context_processor
def make_shell_context():
    """Make database models available in Flask shell."""
    return {
        'db': db,
        'User': User,
        'Company': Company,
        'Customer': Customer,
        'InvoiceHeader': InvoiceHeader,
        'LineItem': LineItem,
        'ProcessingLog': ProcessingLog
    }

@app.cli.command()
def init_db():
    """Initialize the database."""
    db.create_all()
    print("Database initialized successfully!")

@app.cli.command() 
def create_admin():
    """Create admin user."""
    email = input("Enter admin email: ")
    password = input("Enter admin password: ")
    first_name = input("Enter first name: ")
    last_name = input("Enter last name: ")
    
    admin = User(
        email=email,
        first_name=first_name,
        last_name=last_name,
        role='super_admin',
        is_verified=True
    )
    admin.set_password(password)
    
    db.session.add(admin)
    db.session.commit()
    
    print(f"Admin user created successfully!")
    print(f"API Key: {admin.api_key}")

if __name__ == '__main__':
    # Development server
    app.run(host='0.0.0.0', port=5000, debug=True)