# Commercial Invoice Extraction System

A production-ready AI-powered invoice processing system for retail billing with comprehensive API support and commercial licensing compliance.

## 🚀 Features

### Core Capabilities
- **AI-Powered OCR**: Extract text from invoice images (PDF, JPG, PNG) using commercial-safe libraries
- **Intelligent Data Extraction**: Rule-based pattern matching for invoice fields without spaCy dependency
- **Multi-Tenant Architecture**: Support for multiple clients with data isolation
- **Real-Time Processing**: Async processing with background job queues
- **Comprehensive Validation**: Business rule validation and data quality checks

### Business Features
- **Company & Customer Management**: Automatic duplicate detection and relationship management
- **Financial Data Validation**: Tax calculations, totals verification, and currency support
- **Line Item Processing**: Detailed product/service breakdown with pricing
- **Audit Trail**: Complete processing logs for compliance
- **Data Export**: CSV, JSON, Excel export capabilities

### Security & Compliance
- **JWT Authentication**: Secure token-based authentication
- **API Key Management**: Rate limiting and usage tracking
- **Multi-Factor Security**: Account lockout protection and security headers
- **GDPR Compliance**: Data retention policies and privacy controls
- **Commercial Licensing**: All dependencies are commercial-safe (Apache 2.0/BSD)

## 📋 Requirements

### System Requirements
- Python 3.11+
- PostgreSQL 13+ (or SQLite for development)
- Redis 6+ (for caching and job queuing)
- Docker & Docker Compose (recommended)

### Hardware Requirements
- **Minimum**: 2 CPU cores, 4GB RAM, 20GB storage
- **Recommended**: 4 CPU cores, 8GB RAM, 100GB storage
- **Production**: 8+ CPU cores, 16GB+ RAM, SSD storage

## 🛠 Installation

### Option 1: Docker Deployment (Recommended)

1. **Clone the repository**
```bash
git clone <repository_url>
cd invoice_extraction_system
```

2. **Configure environment variables**
```bash
cp .env.example .env
# Edit .env file with your configuration
```

3. **Deploy with Docker Compose**
```bash
cd docker
docker-compose up -d
```

4. **Initialize the database**
```bash
docker-compose exec app flask init-db
docker-compose exec app flask create-admin
```

### Option 2: Manual Installation

1. **Install system dependencies**
```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install -y python3.11 python3-pip postgresql redis-server tesseract-ocr

# macOS
brew install python@3.11 postgresql redis tesseract
```

2. **Create virtual environment**
```bash
python3.11 -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate  # Windows
```

3. **Install Python dependencies**
```bash
pip install -r requirements.txt
```

4. **Configure database**
```bash
# Create PostgreSQL database
sudo -u postgres createdb invoice_db
sudo -u postgres createuser invoice_user
```

5. **Set environment variables**
```bash
export FLASK_ENV=development
export DATABASE_URL=postgresql://invoice_user:password@localhost/invoice_db
export REDIS_URL=redis://localhost:6379/0
```

6. **Initialize application**
```bash
flask init-db
flask create-admin
python app.py
```

## 🔧 Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | `sqlite:///invoice.db` |
| `REDIS_URL` | Redis connection string | `redis://localhost:6379/0` |
| `JWT_SECRET_KEY` | JWT signing key | `dev-secret-key` |
| `OCR_CONFIDENCE_THRESHOLD` | Minimum OCR confidence | `0.7` |
| `MAX_CONTENT_LENGTH` | Max file size (bytes) | `10485760` (10MB) |
| `SENTRY_DSN` | Error tracking DSN | `""` |

### Business Rules Configuration

Edit `app/services/validation_service.py` to customize:
- Maximum invoice amount limits
- Tax rate validation rules
- Required field configurations
- Confidence score thresholds

## 📚 API Documentation

### Authentication

All API endpoints require authentication via API key:

```bash
curl -H "X-API-Key: your-api-key" https://api.yoursite.com/api/invoices
```

### Core Endpoints

#### Upload and Process Invoice
```http
POST /api/process_invoice
Content-Type: multipart/form-data

file: [invoice file]
```

**Response:**
```json
{
  "message": "Invoice uploaded and queued for processing",
  "invoice_id": "uuid-here",
  "status": "pending",
  "estimated_processing_time": "30-60 seconds"
}
```

#### Get Invoice Details
```http
GET /api/invoice/{invoice_id}?include_line_items=true&include_logs=true
```

**Response:**
```json
{
  "invoice": {
    "id": "uuid-here",
    "invoice_number": "INV-2024-001",
    "invoice_date": "2024-01-15",
    "total_amount": 1250.00,
    "company": {
      "name": "ABC Corp",
      "email": "billing@abc.com"
    },
    "line_items": [
      {
        "description": "Professional Services",
        "quantity": 10,
        "unit_price": 100.00,
        "total_price": 1000.00
      }
    ],
    "processing": {
      "status": "completed",
      "confidence": 0.95,
      "requires_review": false
    }
  }
}
```

#### List Invoices
```http
GET /api/invoices?page=1&per_page=20&status=completed&date_from=2024-01-01
```

#### Check Processing Status
```http
GET /api/processing_status/{invoice_id}
```

### Data Management Endpoints

#### Get Companies
```http
GET /api/companies?page=1&per_page=20
```

#### Get Customers
```http
GET /api/customers?page=1&per_page=20
```

#### Export Data
```http
GET /api/export/{format}?date_from=2024-01-01&date_to=2024-12-31
```

### Authentication Endpoints

#### Register User
```http
POST /api/auth/register
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "secure_password",
  "first_name": "John",
  "last_name": "Doe",
  "tenant_id": "company_abc"
}
```

#### Login
```http
POST /api/auth/login
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "secure_password"
}
```

## 🚀 Deployment

### Production Deployment with Docker

1. **Prepare production environment**
```bash
# Set secure environment variables
export POSTGRES_PASSWORD=secure_db_password
export REDIS_PASSWORD=secure_redis_password
export JWT_SECRET_KEY=your-super-secure-jwt-key
export SECRET_KEY=your-super-secure-flask-key
```

2. **Deploy services**
```bash
docker-compose -f docker-compose.yml up -d
```

3. **Configure SSL (recommended)**
```bash
# Add SSL certificates to docker/ssl/
# Update nginx.conf for HTTPS
```

4. **Set up monitoring (optional)**
```bash
docker-compose --profile monitoring up -d
```

### Scaling Considerations

- **Horizontal Scaling**: Run multiple app containers behind a load balancer
- **Database Scaling**: Use PostgreSQL read replicas for heavy read workloads
- **File Storage**: Use cloud storage (S3, Azure Blob) for uploaded files
- **Caching**: Implement Redis cluster for high availability

## 🔒 Security

### Best Practices Implemented

- **Input Validation**: All inputs are validated and sanitized
- **Rate Limiting**: API endpoints have configurable rate limits
- **Security Headers**: CSRF, XSS, and other security headers
- **Database Security**: Parameterized queries prevent SQL injection
- **File Upload Security**: File type validation and virus scanning ready

### Additional Security Measures

1. **Enable SSL/TLS** in production
2. **Use strong passwords** for all accounts
3. **Regularly update** dependencies
4. **Monitor logs** for suspicious activity
5. **Implement network security** (firewalls, VPNs)

## 📊 Monitoring & Analytics

### Built-in Monitoring

- **Health Checks**: `/health` endpoint for load balancer monitoring
- **Processing Logs**: Detailed audit trail for all operations
- **Performance Metrics**: Processing times and confidence scores
- **Error Tracking**: Comprehensive error logging with Sentry integration

### Optional Monitoring Stack

- **Prometheus**: Metrics collection
- **Grafana**: Dashboards and visualization
- **Elasticsearch**: Log aggregation and search

## 🧪 Testing

### Run Tests
```bash
# Unit tests
python -m pytest tests/

# Integration tests
python -m pytest tests/test_api.py

# Load testing
python scripts/load_test.py
```

### Test Coverage
```bash
python -m pytest --cov=app tests/
```

## 📋 Performance

### Benchmarks

- **Processing Speed**: < 30 seconds per invoice (10MB)
- **Throughput**: 100+ concurrent uploads
- **Accuracy**: >85% field extraction rate
- **Availability**: 99.9% uptime target

### Optimization Tips

1. **Optimize images** before upload (reduce size, improve quality)
2. **Use appropriate instance sizes** based on volume
3. **Enable caching** for frequently accessed data
4. **Monitor resource usage** and scale accordingly

## 🤝 Support & Contributing

### Getting Help

- **Documentation**: Check this README and API docs
- **Issues**: Submit issues via GitHub
- **Commercial Support**: Contact for enterprise support options

### Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## 📄 License

This project uses only commercial-friendly dependencies:

- **Flask**: BSD-3-Clause License ✅
- **OpenCV**: Apache 2.0 License ✅
- **EasyOCR**: Apache 2.0 License ✅
- **PostgreSQL**: PostgreSQL License ✅
- **Redis**: BSD-3-Clause License ✅

**Commercial Use**: This software is suitable for commercial use without licensing restrictions.

## 🔮 Roadmap

### Upcoming Features

- [ ] Machine Learning model training for better accuracy
- [ ] Mobile app SDK for direct integration
- [ ] Advanced analytics and reporting
- [ ] Multi-language OCR support
- [ ] Blockchain integration for audit trails
- [ ] AI-powered duplicate detection

### Version History

- **v1.0.0**: Initial commercial release
- **v0.9.0**: Beta release with core features
- **v0.8.0**: Alpha release for testing

---

## Quick Start Commands

```bash
# Clone and setup
git clone <repo> && cd invoice_extraction_system

# Docker deployment
cd docker && docker-compose up -d

# Create admin user
docker-compose exec app flask create-admin

# Test the API
curl -X POST -H "X-API-Key: your-key" \
  -F "file=@sample_invoice.pdf" \
  http://localhost:5000/api/process_invoice
```

For detailed setup instructions and troubleshooting, see our [Deployment Guide](docs/deployment_guide.md).

---

**Built with ❤️ for commercial invoice processing**