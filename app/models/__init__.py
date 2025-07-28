"""
Database models for Invoice Extraction System
Normalized schema with proper relationships and indexing
"""

from app.models.user import User
from app.models.company import Company
from app.models.customer import Customer
from app.models.invoice import InvoiceHeader, LineItem, ProcessingLog

__all__ = [
    'User',
    'Company', 
    'Customer',
    'InvoiceHeader',
    'LineItem',
    'ProcessingLog'
]