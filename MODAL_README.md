# 🚀 Imprint Reader - Modal API Service

Production-ready AI-powered imprint extraction service deployed on Modal. Extracts legal/contact information from websites using Gemini-2.5-flash with **85.9% success rate**.

## 🌐 Live API Endpoint

```
POST https://federicodeponte--imprint-reader-api-extract-imprints.modal.run
```

## 📚 API Usage

### Request Format
```json
{
  "urls": [
    "https://example.com",
    "https://example2.de", 
    "www.example3.com"
  ]
}
```

### Response Format (CSV-compatible JSON for Supabase)
```json
{
  "success": true,
  "total_urls": 3,
  "successful_extractions": 2,
  "failed_extractions": 1,
  "success_rate_percent": 66.7,
  "processing_time_seconds": 45.2,
  "results": [
    {
      "timestamp": "2025-01-22 10:15:30",
      "original_url": "https://example.com",
      "imprint_url": "https://example.com/impressum",
      "processing_date": "2025-01-22",
      "processing_time": "10:15:30",
      "company_name": "Example GmbH",
      "managing_directors": "John Doe; Jane Smith",
      "street": "Hauptstraße 123",
      "city": "Berlin",
      "postal_code": "10115",
      "country": "Deutschland",
      "phone": "+49 30 123456789",
      "email": "info@example.com",
      "website": "https://example.com",
      "registration_number": "HRB 12345",
      "vat_id": "DE123456789",
      "success": true,
      "error_message": null
    },
    {
      "timestamp": "2025-01-22 10:16:15",
      "original_url": "https://example2.de",
      "imprint_url": null,
      "processing_date": "2025-01-22", 
      "processing_time": "10:16:15",
      "company_name": "",
      "managing_directors": "",
      "street": "",
      "city": "",
      "postal_code": "",
      "country": "",
      "phone": "",
      "email": "",
      "website": "",
      "registration_number": "",
      "vat_id": "",
      "success": false,
      "error_message": "No imprint page found"
    }
  ]
}
```

## 🔧 Quick Start Examples

### cURL
```bash
curl -X POST https://federicodeponte--imprint-reader-api-extract-imprints.modal.run \
  -H "Content-Type: application/json" \
  -d '{"urls": ["https://www.elenra.de", "https://www.bahn.de"]}'
```

### Python
```python
import requests

response = requests.post(
    "https://federicodeponte--imprint-reader-api-extract-imprints.modal.run",
    json={"urls": ["https://www.elenra.de", "https://www.bahn.de"]}
)

data = response.json()
print(f"Success rate: {data['success_rate_percent']}%")
print(f"Processed {data['total_urls']} URLs in {data['processing_time_seconds']}s")

# Results ready for Supabase
for result in data['results']:
    if result['success']:
        print(f"✅ {result['company_name']} - {result['city']}")
    else:
        print(f"❌ {result['original_url']} - {result['error_message']}")
```

### JavaScript
```javascript
const response = await fetch(
  'https://federicodeponte--imprint-reader-api-extract-imprints.modal.run',
  {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      urls: ['https://www.elenra.de', 'https://www.bahn.de']
    })
  }
);

const data = await response.json();
console.log(`Success rate: ${data.success_rate_percent}%`);

// Insert directly into Supabase
const { data: insertData, error } = await supabase
  .from('imprint_extractions')
  .insert(data.results);
```

## 🎯 Features

### ✅ **Smart Navigation**
- Two-step imprint detection (legal → imprint)
- Multi-language support (German Impressum, English Imprint)
- Fallback to common URL patterns

### ✅ **Robust Processing**
- SSL error handling with fallbacks
- Automatic retries with exponential backoff
- Rate limiting and timeout management
- Thread-safe parallel processing

### ✅ **Clean Data Output**
- 16-column CSV-compatible structure
- Consistent field names for Supabase integration
- Smart company name extraction from nested JSON
- Text truncation for readability

### ✅ **Production Ready**
- Modal serverless deployment
- Auto-scaling based on demand
- Built-in error monitoring
- No infrastructure management

## 📊 Performance Metrics

| Metric | Value |
|--------|-------|
| **Success Rate** | 85.9% (671/781 URLs tested) |
| **Average Processing Time** | 2.1 seconds per URL |
| **Concurrent Processing** | Up to 8 URLs in parallel |
| **Max Batch Size** | 100 URLs per request |
| **Timeout** | 300 seconds per URL |

## 🔒 Limits & Constraints

- **Max URLs per request**: 100
- **Request timeout**: 30 minutes
- **Individual URL timeout**: 5 minutes
- **Memory**: 2GB per batch
- **API calls**: Uses Gemini-2.5-flash (rate limited)

## 🛠️ Deployment

### Deploy to Modal
```bash
# Install Modal CLI
pip install modal

# Authenticate
modal token new

# Deploy the app
modal deploy modal_app.py

# Your endpoint will be live at:
# https://federicodeponte--imprint-reader-api-extract-imprints.modal.run
```

### Environment Variables
```bash
export GEMINI_API_KEY="your-gemini-api-key"
```

## 💾 Supabase Integration

The response format is designed for direct insertion into Supabase:

```sql
-- Create table
CREATE TABLE imprint_extractions (
  id SERIAL PRIMARY KEY,
  timestamp TEXT,
  original_url TEXT,
  imprint_url TEXT,
  processing_date DATE,
  processing_time TIME,
  company_name TEXT,
  managing_directors TEXT,
  street TEXT,
  city TEXT,
  postal_code TEXT,
  country TEXT,
  phone TEXT,
  email TEXT,
  website TEXT,
  registration_number TEXT,
  vat_id TEXT,
  success BOOLEAN,
  error_message TEXT,
  created_at TIMESTAMP DEFAULT NOW()
);
```

```javascript
// Insert results
const { data, error } = await supabase
  .from('imprint_extractions')
  .insert(response.results);
```

## 🔍 Error Handling

Common errors and solutions:

| Error | Cause | Solution |
|-------|-------|----------|
| `No URLs provided` | Empty request | Include `urls` array in request |
| `Maximum 100 URLs allowed` | Too many URLs | Split into multiple requests |
| `No imprint page found` | Website structure | Website doesn't have accessible imprint |
| `SSL certificate errors` | HTTPS issues | Automatic fallback to non-SSL |
| `Processing timeout` | Complex sites | Individual URL timeout after 5 minutes |

## 📈 Monitoring & Analytics

Built-in metrics in every response:
- Success/failure counts
- Processing time per batch
- Success rate percentage
- Individual error messages

Perfect for tracking API performance and data quality over time.

## 🎯 Use Cases

### ✅ **Lead Generation**
Extract contact information from prospect websites

### ✅ **Compliance Checking** 
Verify legal requirements across multiple sites

### ✅ **Market Research**
Gather company information at scale

### ✅ **Data Enrichment**
Enhance existing datasets with legal/contact details

---

**🚀 Ready to extract imprints at scale with 85.9% accuracy!** 