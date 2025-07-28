#!/usr/bin/env python3
"""
Database setup script for Invoice Extraction System
Creates tables, indexes, and initial data
"""

import os
import sys
from datetime import datetime, timezone

# Add parent directory to path to import app
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db
from app.models import User, Company, Customer, InvoiceHeader, LineItem, ProcessingLog

def create_database():
    """Create all database tables and indexes."""
    print("Creating database tables...")
    
    try:
        # Create all tables
        db.create_all()
        print("✅ Database tables created successfully")
        
        # Create additional indexes for performance
        create_performance_indexes()
        
        return True
        
    except Exception as e:
        print(f"❌ Error creating database: {str(e)}")
        return False

def create_performance_indexes():
    """Create additional performance indexes."""
    print("Creating performance indexes...")
    
    try:
        # Additional indexes for better query performance
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_invoice_created_at ON invoice_headers(created_at DESC);",
            "CREATE INDEX IF NOT EXISTS idx_invoice_amount_date ON invoice_headers(total_amount, invoice_date);",
            "CREATE INDEX IF NOT EXISTS idx_company_active_name ON companies(is_active, name);",
            "CREATE INDEX IF NOT EXISTS idx_customer_active_name ON customers(is_active, name);",
            "CREATE INDEX IF NOT EXISTS idx_log_created_level ON processing_logs(created_at DESC, log_level);",
            "CREATE INDEX IF NOT EXISTS idx_user_last_login ON users(last_login_at DESC);",
        ]
        
        for index_sql in indexes:
            try:
                db.session.execute(index_sql)
                db.session.commit()
            except Exception as e:
                print(f"Warning: Could not create index: {str(e)}")
        
        print("✅ Performance indexes created")
        
    except Exception as e:
        print(f"⚠️  Warning: Some indexes could not be created: {str(e)}")

def create_admin_user():
    """Create initial admin user."""
    print("\nCreating admin user...")
    
    # Check if admin already exists
    existing_admin = User.query.filter_by(role='super_admin').first()
    if existing_admin:
        print(f"✅ Admin user already exists: {existing_admin.email}")
        return existing_admin
    
    # Get admin details
    email = input("Enter admin email: ").strip()
    if not email:
        print("❌ Email is required")
        return None
    
    # Check if user with this email exists
    existing_user = User.query.filter_by(email=email).first()
    if existing_user:
        print(f"❌ User with email {email} already exists")
        return None
    
    password = input("Enter admin password (min 8 characters): ").strip()
    if len(password) < 8:
        print("❌ Password must be at least 8 characters")
        return None
    
    first_name = input("Enter first name: ").strip() or "Admin"
    last_name = input("Enter last name: ").strip() or "User"
    
    try:
        # Create admin user
        admin = User(
            email=email,
            first_name=first_name,
            last_name=last_name,
            role='super_admin',
            is_active=True,
            is_verified=True,
            tenant_id='default'
        )
        
        admin.set_password(password)
        
        db.session.add(admin)
        db.session.commit()
        
        print(f"✅ Admin user created successfully!")
        print(f"   Email: {admin.email}")
        print(f"   API Key: {admin.api_key}")
        print(f"   Role: {admin.role}")
        
        return admin
        
    except Exception as e:
        print(f"❌ Error creating admin user: {str(e)}")
        db.session.rollback()
        return None

def create_sample_data():
    """Create sample data for testing."""
    print("\nDo you want to create sample data for testing? (y/N): ", end="")
    choice = input().strip().lower()
    
    if choice != 'y':
        print("Skipping sample data creation")
        return
    
    print("Creating sample data...")
    
    try:
        # Create sample company
        sample_company = Company(
            name="ABC Corporation",
            legal_name="ABC Corp Ltd.",
            email="billing@abc-corp.com",
            phone="(555) 123-4567",
            address_line1="123 Business St",
            city="New York",
            state_province="NY",
            postal_code="10001",
            country="USA",
            tax_id="12-3456789",
            tenant_id="default",
            is_verified=True
        )
        
        # Create sample customer
        sample_customer = Customer(
            name="John Smith",
            customer_type="individual",
            email="john.smith@email.com",
            phone="(555) 987-6543",
            billing_address_line1="456 Customer Ave",
            billing_city="New York",
            billing_state_province="NY",
            billing_postal_code="10002",
            billing_country="USA",
            tenant_id="default",
            is_verified=True
        )
        
        db.session.add(sample_company)
        db.session.add(sample_customer)
        db.session.commit()
        
        print("✅ Sample data created successfully")
        print(f"   Sample Company: {sample_company.name}")
        print(f"   Sample Customer: {sample_customer.name}")
        
    except Exception as e:
        print(f"❌ Error creating sample data: {str(e)}")
        db.session.rollback()

def check_database_health():
    """Check database connectivity and basic operations."""
    print("\nChecking database health...")
    
    try:
        # Test basic query
        user_count = User.query.count()
        company_count = Company.query.count()
        customer_count = Customer.query.count()
        invoice_count = InvoiceHeader.query.count()
        
        print(f"✅ Database connection successful")
        print(f"   Users: {user_count}")
        print(f"   Companies: {company_count}")
        print(f"   Customers: {customer_count}")
        print(f"   Invoices: {invoice_count}")
        
        return True
        
    except Exception as e:
        print(f"❌ Database health check failed: {str(e)}")
        return False

def main():
    """Main setup function."""
    print("🚀 Invoice Extraction System - Database Setup")
    print("=" * 50)
    
    # Create Flask app
    app = create_app()
    
    with app.app_context():
        # Create database tables
        if not create_database():
            print("❌ Setup failed at database creation step")
            return False
        
        # Create admin user
        admin = create_admin_user()
        if not admin:
            print("❌ Setup failed at admin user creation step")
            return False
        
        # Create sample data (optional)
        create_sample_data()
        
        # Check database health
        if not check_database_health():
            print("❌ Setup failed at health check step")
            return False
        
        print("\n" + "=" * 50)
        print("🎉 Database setup completed successfully!")
        print("\nNext steps:")
        print("1. Start the application: python app.py")
        print("2. Test the API with your admin API key")
        print("3. Upload a sample invoice to test the system")
        print("\nFor production deployment, see the README.md file.")
        
        return True

if __name__ == "__main__":
    main()