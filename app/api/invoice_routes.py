"""
Invoice Processing API endpoints
Main API for invoice upload, processing, and retrieval
"""

from flask import Blueprint, request, jsonify, current_app
from werkzeug.utils import secure_filename
import os
import hashlib
import logging
from datetime import datetime, timezone
import asyncio
from threading import Thread

from app import db, limiter
from app.api.auth import authenticate_api_key, get_current_user
from app.models.invoice import InvoiceHeader, LineItem, ProcessingLog
from app.models.company import Company
from app.models.customer import Customer
from app.services.ocr_service import OCRService
from app.services.extraction_service import ExtractionService
from app.services.validation_service import ValidationService

invoice_bp = Blueprint('invoice', __name__)
logger = logging.getLogger(__name__)

# Initialize services
ocr_service = OCRService()
extraction_service = ExtractionService()
validation_service = ValidationService()

def allowed_file(filename):
    """Check if file extension is allowed."""
    if '.' not in filename:
        return False
    
    extension = filename.rsplit('.', 1)[1].lower()
    allowed_extensions = current_app.config.get('ALLOWED_EXTENSIONS', {'pdf', 'jpg', 'jpeg', 'png'})
    return extension in allowed_extensions

def calculate_file_hash(file_data):
    """Calculate SHA-256 hash of file data."""
    return hashlib.sha256(file_data).hexdigest()

def save_uploaded_file(file, user_id):
    """Save uploaded file and return file info."""
    if not file or not file.filename:
        raise ValueError("No file provided")
    
    if not allowed_file(file.filename):
        raise ValueError("File type not allowed")
    
    # Read file data
    file_data = file.read()
    file.seek(0)  # Reset file pointer
    
    # Check file size
    if len(file_data) > current_app.config.get('MAX_CONTENT_LENGTH', 10 * 1024 * 1024):
        raise ValueError("File too large")
    
    # Generate secure filename
    filename = secure_filename(file.filename)
    file_hash = calculate_file_hash(file_data)
    
    # Create unique filename with timestamp
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    unique_filename = f"{user_id}_{timestamp}_{filename}"
    
    # Save file
    upload_folder = current_app.config.get('UPLOAD_FOLDER', 'uploads')
    file_path = os.path.join(upload_folder, unique_filename)
    
    os.makedirs(upload_folder, exist_ok=True)
    
    with open(file_path, 'wb') as f:
        f.write(file_data)
    
    return {
        'filename': filename,
        'file_path': file_path,
        'file_size': len(file_data),
        'file_hash': file_hash,
        'file_data': file_data
    }

def process_invoice_async(invoice_id, file_data, user_id, tenant_id):
    """Process invoice asynchronously."""
    try:
        invoice = InvoiceHeader.query.get(invoice_id)
        if not invoice:
            logger.error(f"Invoice {invoice_id} not found for async processing")
            return
        
        # Update status to processing
        invoice.processing_status = 'processing'
        db.session.commit()
        
        # Log processing start
        ProcessingLog.log(
            invoice_id=invoice_id,
            process_stage='processing_start',
            message='Starting invoice processing',
            user_id=user_id
        )
        db.session.commit()
        
        # OCR text extraction
        logger.info(f"Starting OCR for invoice {invoice_id}")
        ocr_start_time = datetime.now()
        
        ocr_result = ocr_service.extract_text(
            file_data, 
            confidence_threshold=current_app.config.get('OCR_CONFIDENCE_THRESHOLD', 0.7)
        )
        
        ocr_time = (datetime.now() - ocr_start_time).total_seconds() * 1000
        
        # Store OCR text
        invoice.ocr_text = ocr_result.get('full_text', '')
        
        ProcessingLog.log(
            invoice_id=invoice_id,
            process_stage='ocr',
            message=f'OCR completed with {ocr_result.get("total_blocks", 0)} text blocks',
            user_id=user_id,
            processing_time_ms=int(ocr_time),
            confidence_score=ocr_result.get('overall_confidence', 0.0),
            metadata=ocr_result
        )
        db.session.commit()
        
        # Data extraction
        logger.info(f"Starting data extraction for invoice {invoice_id}")
        extraction_start_time = datetime.now()
        
        extracted_data = extraction_service.extract_invoice_data(
            invoice.ocr_text, 
            tenant_id
        )
        
        extraction_time = (datetime.now() - extraction_start_time).total_seconds() * 1000
        
        # Update invoice with extracted data
        update_invoice_with_extracted_data(invoice, extracted_data)
        
        ProcessingLog.log(
            invoice_id=invoice_id,
            process_stage='extraction',
            message=f'Data extraction completed with {len(extracted_data.get("line_items", []))} line items',
            user_id=user_id,
            processing_time_ms=int(extraction_time),
            confidence_score=extracted_data.get('extraction_metadata', {}).get('overall_confidence', 0.0),
            metadata=extracted_data.get('extraction_metadata', {})
        )
        db.session.commit()
        
        # Validation
        logger.info(f"Starting validation for invoice {invoice_id}")
        validation_start_time = datetime.now()
        
        validation_result = validation_service.validate_invoice_data(extracted_data)
        
        validation_time = (datetime.now() - validation_start_time).total_seconds() * 1000
        
        # Update invoice status based on validation
        if validation_result.get('is_valid', False):
            invoice.processing_status = 'completed'
            invoice.requires_review = validation_result.get('requires_review', False)
        else:
            invoice.processing_status = 'failed'
            invoice.requires_review = True
        
        # Set overall confidence
        invoice.extraction_confidence = extracted_data.get('extraction_metadata', {}).get('overall_confidence', 0.0)
        
        ProcessingLog.log(
            invoice_id=invoice_id,
            process_stage='validation',
            message=f'Validation completed - Valid: {validation_result.get("is_valid", False)}',
            user_id=user_id,
            processing_time_ms=int(validation_time),
            confidence_score=validation_result.get('confidence_score', 0.0),
            metadata=validation_result
        )
        
        # Final processing log
        ProcessingLog.log(
            invoice_id=invoice_id,
            process_stage='completion',
            message=f'Invoice processing completed with status: {invoice.processing_status}',
            user_id=user_id,
            confidence_score=invoice.extraction_confidence
        )
        
        db.session.commit()
        logger.info(f"Invoice {invoice_id} processed successfully")
        
    except Exception as e:
        logger.error(f"Invoice processing failed for {invoice_id}: {str(e)}")
        
        # Update invoice status to failed
        try:
            invoice = InvoiceHeader.query.get(invoice_id)
            if invoice:
                invoice.processing_status = 'failed'
                invoice.requires_review = True
                
                ProcessingLog.log(
                    invoice_id=invoice_id,
                    process_stage='error',
                    message=f'Processing failed: {str(e)}',
                    log_level='ERROR',
                    user_id=user_id,
                    error_code='PROCESSING_FAILED',
                    error_details=str(e)
                )
                
                db.session.commit()
        except Exception as e2:
            logger.error(f"Failed to update invoice status after error: {str(e2)}")

def update_invoice_with_extracted_data(invoice, extracted_data):
    """Update invoice with extracted data."""
    try:
        # Update invoice metadata
        metadata = extracted_data.get('invoice_metadata', {})
        if metadata.get('invoice_number'):
            invoice.invoice_number = metadata['invoice_number']
        if metadata.get('invoice_date'):
            invoice.invoice_date = metadata['invoice_date']
        if metadata.get('due_date'):
            invoice.due_date = metadata['due_date']
        if metadata.get('po_number'):
            invoice.po_number = metadata['po_number']
        
        # Update financial data
        financial = extracted_data.get('financial_data', {})
        invoice.currency = financial.get('currency', 'USD')
        invoice.subtotal_amount = financial.get('subtotal_amount', 0.0)
        invoice.tax_amount = financial.get('tax_amount', 0.0)
        invoice.tax_rate = financial.get('tax_rate', 0.0)
        invoice.discount_amount = financial.get('discount_amount', 0.0)
        invoice.shipping_amount = financial.get('shipping_amount', 0.0)
        invoice.total_amount = financial.get('total_amount', 0.0)
        invoice.payment_terms = financial.get('payment_terms', '')
        
        # Handle company data
        company_data = extracted_data.get('company_data', {})
        if company_data.get('existing_company_id'):
            invoice.company_id = company_data['existing_company_id']
        elif company_data.get('name'):
            # Create new company
            company = create_or_update_company(company_data, invoice.tenant_id)
            invoice.company_id = company.id
        
        # Handle customer data  
        customer_data = extracted_data.get('customer_data', {})
        if customer_data.get('existing_customer_id'):
            invoice.customer_id = customer_data['existing_customer_id']
        elif customer_data.get('name'):
            # Create new customer
            customer = create_or_update_customer(customer_data, invoice.tenant_id)
            invoice.customer_id = customer.id
        
        # Store extraction metadata
        invoice.set_extraction_metadata(extracted_data.get('extraction_metadata', {}))
        
        # Create line items
        line_items_data = extracted_data.get('line_items', [])
        for item_data in line_items_data:
            line_item = LineItem(
                invoice_id=invoice.id,
                line_number=item_data.get('line_number', 1),
                description=item_data.get('description', ''),
                item_code=item_data.get('item_code', ''),
                quantity=item_data.get('quantity', 1.0),
                unit_of_measure=item_data.get('unit_of_measure', 'each'),
                unit_price=item_data.get('unit_price', 0.0),
                total_price=item_data.get('total_price', 0.0),
                confidence_score=item_data.get('confidence', 0.0)
            )
            db.session.add(line_item)
        
        # Calculate totals if line items exist
        invoice.calculate_totals()
        
    except Exception as e:
        logger.error(f"Failed to update invoice with extracted data: {str(e)}")
        raise

def create_or_update_company(company_data, tenant_id):
    """Create or update company from extracted data."""
    # Check for existing similar companies
    similar_companies = Company.find_similar(
        company_data.get('name', ''),
        company_data.get('tax_id'),
        tenant_id
    )
    
    if similar_companies:
        # Update existing company with new data
        company = similar_companies[0]
        for key, value in company_data.items():
            if value and hasattr(company, key):
                setattr(company, key, value)
    else:
        # Create new company
        company = Company(
            name=company_data.get('name', ''),
            tax_id=company_data.get('tax_id'),
            email=company_data.get('email'),
            phone=company_data.get('phone'),
            website=company_data.get('website'),
            address_line1=company_data.get('address_line1'),
            address_line2=company_data.get('address_line2'),
            city=company_data.get('city'),
            state_province=company_data.get('state_province'),
            postal_code=company_data.get('postal_code'),
            country=company_data.get('country'),
            tenant_id=tenant_id,
            confidence_score=company_data.get('confidence', 0.0)
        )
        db.session.add(company)
    
    return company

def create_or_update_customer(customer_data, tenant_id):
    """Create or update customer from extracted data."""
    # Check for existing similar customers
    similar_customers = Customer.find_similar(
        customer_data.get('name'),
        customer_data.get('email'),
        None,
        tenant_id
    )
    
    if similar_customers:
        # Update existing customer
        customer = similar_customers[0]
        for key, value in customer_data.items():
            if value and hasattr(customer, key):
                setattr(customer, key, value)
    else:
        # Create new customer
        customer = Customer(
            name=customer_data.get('name', ''),
            company_name=customer_data.get('company_name'),
            email=customer_data.get('email'),
            phone=customer_data.get('phone'),
            billing_address_line1=customer_data.get('billing_address_line1'),
            billing_address_line2=customer_data.get('billing_address_line2'),
            billing_city=customer_data.get('billing_city'),
            billing_state_province=customer_data.get('billing_state_province'),
            billing_postal_code=customer_data.get('billing_postal_code'),
            billing_country=customer_data.get('billing_country'),
            tenant_id=tenant_id,
            confidence_score=customer_data.get('confidence', 0.0)
        )
        db.session.add(customer)
    
    return customer

@invoice_bp.route('/process_invoice', methods=['POST'])
@authenticate_api_key
@limiter.limit("10 per minute")
def process_invoice():
    """Upload and process an invoice."""
    try:
        user = get_current_user()
        
        # Check if file is in request
        if 'file' not in request.files:
            return jsonify({
                'error': 'No file provided',
                'message': 'Invoice file is required'
            }), 400
        
        file = request.files['file']
        
        # Save uploaded file
        try:
            file_info = save_uploaded_file(file, user.id)
        except ValueError as e:
            return jsonify({
                'error': 'File upload failed',
                'message': str(e)
            }), 400
        
        # Check for duplicate files
        existing_invoice = InvoiceHeader.find_potential_duplicates(
            file_info['file_hash'],
            None,  # Don't know invoice number yet
            None,  # Don't know company yet
            user.tenant_id
        )
        
        if existing_invoice:
            return jsonify({
                'error': 'Duplicate file',
                'message': 'This file has already been processed',
                'existing_invoice_id': existing_invoice.id
            }), 409
        
        # Create invoice record
        invoice = InvoiceHeader(
            invoice_number='PENDING',  # Will be updated after extraction
            invoice_date=datetime.now().date(),
            user_id=user.id,
            tenant_id=user.tenant_id,
            processing_status='pending',
            original_filename=file_info['filename'],
            file_path=file_info['file_path'],
            file_size=file_info['file_size'],
            file_hash=file_info['file_hash']
        )
        
        db.session.add(invoice)
        db.session.commit()
        
        # Log initial upload
        ProcessingLog.log(
            invoice_id=invoice.id,
            process_stage='upload',
            message=f'Invoice uploaded: {file_info["filename"]} ({file_info["file_size"]} bytes)',
            user_id=user.id,
            ip_address=request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr),
            user_agent=request.headers.get('User-Agent')
        )
        db.session.commit()
        
        # Start async processing
        processing_thread = Thread(
            target=process_invoice_async,
            args=(invoice.id, file_info['file_data'], user.id, user.tenant_id)
        )
        processing_thread.start()
        
        logger.info(f"Invoice {invoice.id} queued for processing by user {user.email}")
        
        return jsonify({
            'message': 'Invoice uploaded and queued for processing',
            'invoice_id': invoice.id,
            'status': 'pending',
            'estimated_processing_time': '30-60 seconds'
        }), 202
        
    except Exception as e:
        logger.error(f"Invoice upload failed: {str(e)}")
        db.session.rollback()
        return jsonify({
            'error': 'Upload failed',
            'message': 'An error occurred while uploading the invoice'
        }), 500

@invoice_bp.route('/invoice/<invoice_id>', methods=['GET'])
@authenticate_api_key
def get_invoice(invoice_id):
    """Get invoice details by ID."""
    try:
        user = get_current_user()
        
        invoice = InvoiceHeader.query.filter_by(
            id=invoice_id,
            tenant_id=user.tenant_id
        ).first()
        
        if not invoice:
            return jsonify({
                'error': 'Invoice not found',
                'message': 'Invoice not found or access denied'
            }), 404
        
        # Include line items and logs based on query parameters
        include_line_items = request.args.get('include_line_items', 'false').lower() == 'true'
        include_logs = request.args.get('include_logs', 'false').lower() == 'true'
        
        return jsonify({
            'invoice': invoice.to_dict(
                include_line_items=include_line_items,
                include_logs=include_logs
            )
        }), 200
        
    except Exception as e:
        logger.error(f"Get invoice failed: {str(e)}")
        return jsonify({
            'error': 'Retrieval failed',
            'message': 'An error occurred while retrieving the invoice'
        }), 500

@invoice_bp.route('/invoices', methods=['GET'])
@authenticate_api_key
def list_invoices():
    """List invoices with pagination and filtering."""
    try:
        user = get_current_user()
        
        # Pagination parameters
        page = int(request.args.get('page', 1))
        per_page = min(int(request.args.get('per_page', 20)), 100)  # Max 100 per page
        
        # Filtering parameters
        status = request.args.get('status')
        company_id = request.args.get('company_id')
        customer_id = request.args.get('customer_id')
        date_from = request.args.get('date_from')
        date_to = request.args.get('date_to')
        
        # Build query
        query = InvoiceHeader.query.filter_by(
            tenant_id=user.tenant_id,
            is_archived=False
        )
        
        # Apply filters
        if status:
            query = query.filter(InvoiceHeader.processing_status == status)
        
        if company_id:
            query = query.filter(InvoiceHeader.company_id == company_id)
        
        if customer_id:
            query = query.filter(InvoiceHeader.customer_id == customer_id)
        
        if date_from:
            try:
                from_date = datetime.strptime(date_from, '%Y-%m-%d').date()
                query = query.filter(InvoiceHeader.invoice_date >= from_date)
            except ValueError:
                pass
        
        if date_to:
            try:
                to_date = datetime.strptime(date_to, '%Y-%m-%d').date()
                query = query.filter(InvoiceHeader.invoice_date <= to_date)
            except ValueError:
                pass
        
        # Order by creation date (newest first)
        query = query.order_by(InvoiceHeader.created_at.desc())
        
        # Paginate
        pagination = query.paginate(
            page=page, 
            per_page=per_page, 
            error_out=False
        )
        
        invoices = [invoice.to_dict() for invoice in pagination.items]
        
        return jsonify({
            'invoices': invoices,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': pagination.total,
                'pages': pagination.pages,
                'has_prev': pagination.has_prev,
                'has_next': pagination.has_next
            }
        }), 200
        
    except Exception as e:
        logger.error(f"List invoices failed: {str(e)}")
        return jsonify({
            'error': 'List failed',
            'message': 'An error occurred while listing invoices'
        }), 500

@invoice_bp.route('/processing_status/<invoice_id>', methods=['GET'])
@authenticate_api_key
def get_processing_status(invoice_id):
    """Get processing status of an invoice."""
    try:
        user = get_current_user()
        
        invoice = InvoiceHeader.query.filter_by(
            id=invoice_id,
            tenant_id=user.tenant_id
        ).first()
        
        if not invoice:
            return jsonify({
                'error': 'Invoice not found',
                'message': 'Invoice not found or access denied'
            }), 404
        
        # Get recent processing logs
        recent_logs = ProcessingLog.query.filter_by(
            invoice_id=invoice_id
        ).order_by(ProcessingLog.created_at.desc()).limit(5).all()
        
        return jsonify({
            'invoice_id': invoice_id,
            'status': invoice.processing_status,
            'confidence': invoice.extraction_confidence,
            'requires_review': invoice.requires_review,
            'created_at': invoice.created_at.isoformat(),
            'updated_at': invoice.updated_at.isoformat(),
            'recent_logs': [log.to_dict() for log in recent_logs]
        }), 200
        
    except Exception as e:
        logger.error(f"Get processing status failed: {str(e)}")
        return jsonify({
            'error': 'Status retrieval failed',
            'message': 'An error occurred while retrieving processing status'
        }), 500