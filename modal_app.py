#!/usr/bin/env python3
"""
Modal deployment for Imprint Reader Service
Returns CSV-style JSON data perfect for Supabase integration
"""

import modal
import json
import os
from datetime import datetime
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

# Modal app configuration
app = modal.App("imprint-reader")

# Create Modal image with all dependencies
image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install([
        "requests>=2.28.0",
        "beautifulsoup4>=4.11.0", 
        "markdownify>=0.11.0",
        "lxml>=4.9.0"
    ])
    .env({"GEMINI_API_KEY": os.environ.get("GEMINI_API_KEY", "AIzaSyCcV31i8YA-YKLPHC0gx5zdD50gBcjTxq4")})
)

@dataclass 
class ImprintResult:
    """Clean result structure for Supabase"""
    url: str
    imprint_url: Optional[str]
    success: bool
    company_name: str
    managing_directors: str
    street: str
    city: str
    postal_code: str
    country: str
    phone: str
    email: str
    website: str
    registration_number: str
    vat_id: str
    processing_timestamp: str
    error_message: Optional[str] = None

# Include the core ImprintReader class in Modal
@app.function(
    image=image,
    timeout=300,  # 5 minutes per URL
    memory=1024,  # 1GB RAM
    cpu=2.0       # 2 CPU cores
)
def extract_imprint(url: str) -> Dict[str, Any]:
    """Extract imprint data from a single URL"""
    
    # Import here to avoid issues with Modal's environment
    import requests
    import re
    import json
    import time
    import random
    import warnings
    from urllib.parse import urljoin, urlparse
    from bs4 import BeautifulSoup
    from markdownify import markdownify as md
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
    import urllib3
    
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    
    class ImprintReader:
        def __init__(self, api_key):
            self.api_key = api_key
            self.base_url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
            
            # Setup requests session with retries
            self.session = requests.Session()
            retry_strategy = Retry(
                total=3,
                status_forcelist=[429, 500, 502, 503, 504],
                allowed_methods=["HEAD", "GET", "POST"],
                backoff_factor=1
            )
            adapter = HTTPAdapter(max_retries=retry_strategy)
            self.session.mount("http://", adapter)
            self.session.mount("https://", adapter)
            
            self.last_request_time = 0
            self.min_request_interval = 0.5
            
        def _rate_limit(self):
            """Ensure minimum interval between requests"""
            current_time = time.time()
            time_since_last = current_time - self.last_request_time
            if time_since_last < self.min_request_interval:
                sleep_time = self.min_request_interval - time_since_last
                time.sleep(sleep_time)
            self.last_request_time = time.time()
            
        def get_page_content(self, url):
            """Fetch page content with robust error handling"""
            self._rate_limit()
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            }
            
            for attempt in range(2):
                try:
                    response = self.session.get(url, headers=headers, timeout=30, verify=True)
                    response.raise_for_status()
                    return response.text
                except requests.exceptions.SSLError:
                    if attempt == 0:
                        try:
                            response = self.session.get(url, headers=headers, timeout=30, verify=False)
                            response.raise_for_status()
                            return response.text
                        except Exception:
                            continue
                except Exception as e:
                    if attempt == 0:
                        time.sleep(2)
                        continue
                    print(f"Error fetching {url}: {e}")
            return None
            
        def extract_relative_links(self, html_content, base_url):
            """Extract relative links from HTML content"""
            try:
                soup = BeautifulSoup(html_content, 'html.parser')
                links = []
                
                for a_tag in soup.find_all('a', href=True):
                    href = a_tag['href'].strip()
                    text = a_tag.get_text(strip=True)
                    
                    if href and not href.startswith(('#', 'javascript:', 'mailto:', 'tel:')):
                        full_url = urljoin(base_url, href)
                        if urlparse(full_url).netloc == urlparse(base_url).netloc:
                            links.append({
                                'url': full_url,
                                'text': text,
                                'href': href
                            })
                
                # Try common imprint patterns if no links found
                if not links:
                    common_patterns = ['/impressum', '/imprint', '/legal', '/legal-notice']
                    for pattern in common_patterns:
                        full_url = urljoin(base_url, pattern)
                        links.append({
                            'url': full_url,
                            'text': 'Generated pattern',
                            'href': pattern
                        })
                
                return links
            except Exception as e:
                print(f"Error extracting links: {e}")
                return []
                
        def _call_gemini_api(self, prompt, max_retries=2):
            """Call Gemini API with retries"""
            headers = {'Content-Type': 'application/json'}
            data = {'contents': [{'parts': [{'text': prompt}]}]}
            
            for attempt in range(max_retries):
                try:
                    if attempt > 0:
                        wait_time = (2 ** attempt) * random.uniform(0.5, 1.5)
                        time.sleep(wait_time)
                    
                    response = self.session.post(
                        f"{self.base_url}?key={self.api_key}",
                        headers=headers,
                        json=data,
                        timeout=45
                    )
                    
                    if response.status_code == 429:
                        time.sleep(60)
                        continue
                        
                    response.raise_for_status()
                    result = response.json()
                    
                    if 'candidates' in result and len(result['candidates']) > 0:
                        if 'content' in result['candidates'][0] and 'parts' in result['candidates'][0]['content']:
                            return result['candidates'][0]['content']['parts'][0]['text']
                    
                    if attempt == max_retries - 1:
                        return None
                    continue
                    
                except Exception as e:
                    if attempt == max_retries - 1:
                        return None
                    continue
            return None
            
        def identify_imprint_page(self, links):
            """Use Gemini to identify imprint page"""
            if not links:
                return None
                
            links_text = "\n".join([f"- {link['text']} ({link['href']})" for link in links[:30]])
            
            prompt = f"""
Analyze these website links and identify which one is most likely the IMPRINT or LEGAL NOTICE page.

Look for:
- "Impressum" (German)
- "Imprint" (English) 
- "Legal Notice"
- "Legal"
- "About Us" (if it contains legal info)

Links:
{links_text}

Respond with ONLY the exact href value (like "/impressum" or "/legal") of the most likely imprint page.
If no suitable page is found, respond with "NONE".
"""

            result = self._call_gemini_api(prompt)
            if not result or result.strip() == "NONE":
                return None
                
            # Find matching link
            result = result.strip().strip('"\'')
            for link in links:
                if result in link['href'] or link['href'] in result:
                    return link
            return None
            
        def html_to_markdown(self, html_content):
            """Convert HTML to markdown"""
            try:
                return md(html_content, heading_style="ATX")[:10000]  # Limit size
            except Exception:
                return html_content[:10000]
                
        def extract_imprint_data(self, markdown_content):
            """Extract structured data using Gemini"""
            prompt = f"""
Extract legal/imprint information and return as JSON:

{{
  "company_name": "Main company name",
  "managing_directors": ["Director names"],
  "business_address": {{
    "street": "Street address",
    "city": "City", 
    "postal_code": "Postal code",
    "country": "Country"
  }},
  "phone_numbers": ["Phone numbers"],
  "email_addresses": ["Email addresses"],
  "website_url": "Website URL",
  "registration_details": {{
    "registration_number": "Registration number"
  }},
  "vat_id": "VAT ID"
}}

Content:
{markdown_content[:8000]}

Return ONLY valid JSON. Use null for missing fields.
"""

            result = self._call_gemini_api(prompt)
            if not result:
                return {"error": "No response from Gemini"}
                
            try:
                json_match = re.search(r'\{.*\}', result, re.DOTALL)
                if json_match:
                    return json.loads(json_match.group())
                return {"error": "Invalid JSON response"}
            except Exception:
                return {"error": "JSON parsing failed"}
                
        def process_url(self, url):
            """Main processing method"""
            # Add https if missing
            if not url.startswith(('http://', 'https://')):
                url = 'https://' + url
                
            # Get homepage
            html_content = self.get_page_content(url)
            if not html_content:
                return None
                
            # Extract links
            links = self.extract_relative_links(html_content, url)
            if not links:
                return None
                
            # Identify imprint page
            imprint_link = self.identify_imprint_page(links)
            if not imprint_link:
                return None
                
            # Get imprint content
            imprint_html = self.get_page_content(imprint_link['url'])
            if not imprint_html:
                return None
                
            # Convert to markdown and extract data
            markdown_content = self.html_to_markdown(imprint_html)
            imprint_data = self.extract_imprint_data(markdown_content)
            
            return {
                'url': url,
                'imprint_url': imprint_link['url'],
                'imprint_data': imprint_data
            }
    
    # Process the URL
    try:
        api_key = os.environ.get("GEMINI_API_KEY")
        reader = ImprintReader(api_key)
        result = reader.process_url(url)
        
        if result and result.get('imprint_data') and not result['imprint_data'].get('error'):
            return {
                'success': True,
                'url': result['url'],
                'imprint_url': result['imprint_url'],
                'data': result['imprint_data']
            }
        else:
            return {
                'success': False,
                'url': url,
                'error': result['imprint_data'].get('error', 'Unknown error') if result else 'Failed to process URL'
            }
    except Exception as e:
        return {
            'success': False,
            'url': url,
            'error': str(e)
        }

def safe_extract(data, paths, default=""):
    """Safely extract data from nested dict"""
    if not isinstance(data, dict):
        return default
    for path in paths:
        current = data
        try:
            for key in path:
                if isinstance(current, dict) and key in current:
                    current = current[key]
                else:
                    break
            else:
                if current:
                    if isinstance(current, list):
                        return "; ".join(str(x) for x in current[:3])
                    return str(current)[:150]
        except (KeyError, TypeError):
            continue
    return default

def extract_company_name(imprint_data):
    """Smart company name extraction"""
    if not isinstance(imprint_data, dict):
        return ""
    
    name_paths = [
        ['company_name'],
        ['main_entity', 'organization_name'],
        ['company_info', 'name'],
        ['organization_name'],
        ['name']
    ]
    
    return safe_extract(imprint_data, name_paths, "")

@app.function(
    image=image,
    timeout=1800,  # 30 minutes total
    memory=2048,   # 2GB RAM
    cpu=4.0        # 4 CPU cores for parallel processing
)
def process_urls(urls: List[str]) -> List[Dict[str, Any]]:
    """Process multiple URLs and return CSV-style JSON results"""
    
    results = []
    
    for i, url in enumerate(urls):
        print(f"Processing {i+1}/{len(urls)}: {url}")
        
        try:
            # Process the URL
            result = extract_imprint.remote(url.strip())
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            if result['success']:
                imprint_data = result['data']
                company_name = extract_company_name(imprint_data)
                
                # Create CSV-style row
                row = {
                    'timestamp': timestamp,
                    'original_url': result['url'],
                    'imprint_url': result['imprint_url'],
                    'processing_date': datetime.now().strftime('%Y-%m-%d'),
                    'processing_time': datetime.now().strftime('%H:%M:%S'),
                    'company_name': company_name or '',
                    'managing_directors': safe_extract(imprint_data, [['managing_directors'], ['main_entity', 'managing_directors']]),
                    'street': safe_extract(imprint_data, [['business_address', 'street'], ['main_entity', 'address', 'street']]),
                    'city': safe_extract(imprint_data, [['business_address', 'city'], ['main_entity', 'address', 'city']]),
                    'postal_code': safe_extract(imprint_data, [['business_address', 'postal_code'], ['main_entity', 'address', 'postal_code']]),
                    'country': safe_extract(imprint_data, [['business_address', 'country'], ['main_entity', 'address', 'country']]),
                    'phone': safe_extract(imprint_data, [['phone_numbers'], ['main_entity', 'phone_numbers']]),
                    'email': safe_extract(imprint_data, [['email_addresses'], ['main_entity', 'email_addresses']]),
                    'website': safe_extract(imprint_data, [['website_url'], ['main_entity', 'website_url']]),
                    'registration_number': safe_extract(imprint_data, [['registration_details', 'registration_number'], ['main_entity', 'registration_details', 'registration_number']]),
                    'vat_id': safe_extract(imprint_data, [['vat_id'], ['main_entity', 'vat_id']]),
                    'success': True,
                    'error_message': None
                }
                print(f"✅ SUCCESS: {company_name}")
            else:
                # Failed extraction
                row = {
                    'timestamp': timestamp,
                    'original_url': url,
                    'imprint_url': None,
                    'processing_date': datetime.now().strftime('%Y-%m-%d'),
                    'processing_time': datetime.now().strftime('%H:%M:%S'),
                    'company_name': '',
                    'managing_directors': '',
                    'street': '',
                    'city': '',
                    'postal_code': '',
                    'country': '',
                    'phone': '',
                    'email': '',
                    'website': '',
                    'registration_number': '',
                    'vat_id': '',
                    'success': False,
                    'error_message': result.get('error', 'Unknown error')
                }
                print(f"❌ FAILED: {result.get('error', 'Unknown error')}")
            
            results.append(row)
            
        except Exception as e:
            # Exception handling
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            row = {
                'timestamp': timestamp,
                'original_url': url,
                'imprint_url': None,
                'processing_date': datetime.now().strftime('%Y-%m-%d'),
                'processing_time': datetime.now().strftime('%H:%M:%S'),
                'company_name': '',
                'managing_directors': '',
                'street': '',
                'city': '',
                'postal_code': '',
                'country': '',
                'phone': '',
                'email': '',
                'website': '',
                'registration_number': '',
                'vat_id': '',
                'success': False,
                'error_message': f'Processing exception: {str(e)}'
            }
            results.append(row)
            print(f"💥 ERROR: {str(e)}")
    
    return results

# API endpoint
@app.function(
    image=image,
    memory=512,
    cpu=1.0
)
@modal.web_endpoint(method="POST")
def api_extract_imprints(request_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    API endpoint for imprint extraction
    
    Expected input:
    {
        "urls": ["https://example.com", "https://example2.com", ...]
    }
    
    Returns CSV-style JSON data ready for Supabase:
    {
        "success": true,
        "total_urls": 2,
        "successful_extractions": 1,
        "failed_extractions": 1,
        "processing_time_seconds": 45.2,
        "results": [
            {
                "timestamp": "2025-01-22 10:15:30",
                "original_url": "https://example.com",
                "imprint_url": "https://example.com/impressum",
                "company_name": "Example GmbH",
                "managing_directors": "John Doe",
                "street": "Main St 123",
                "city": "Berlin",
                "postal_code": "10115",
                "country": "Germany",
                "phone": "+49 30 123456",
                "email": "info@example.com",
                "website": "https://example.com",
                "registration_number": "HRB 12345",
                "vat_id": "DE123456789",
                "success": true,
                "error_message": null
            }
        ]
    }
    """
    
    start_time = datetime.now()
    
    try:
        urls = request_data.get('urls', [])
        if not urls:
            return {
                "success": False,
                "error": "No URLs provided",
                "total_urls": 0,
                "results": []
            }
        
        if len(urls) > 100:
            return {
                "success": False,
                "error": "Maximum 100 URLs allowed per request",
                "total_urls": len(urls),
                "results": []
            }
        
        print(f"🚀 Processing {len(urls)} URLs via Modal")
        
        # Process all URLs
        results = process_urls.remote(urls)
        
        # Calculate statistics
        successful = sum(1 for r in results if r['success'])
        failed = len(results) - successful
        processing_time = (datetime.now() - start_time).total_seconds()
        
        return {
            "success": True,
            "total_urls": len(urls),
            "successful_extractions": successful,
            "failed_extractions": failed,
            "success_rate_percent": round((successful / len(urls)) * 100, 1) if urls else 0,
            "processing_time_seconds": round(processing_time, 1),
            "results": results
        }
        
    except Exception as e:
        processing_time = (datetime.now() - start_time).total_seconds()
        return {
            "success": False,
            "error": str(e),
            "total_urls": len(request_data.get('urls', [])),
            "processing_time_seconds": round(processing_time, 1),
            "results": []
        }

if __name__ == "__main__":
    print("Imprint Reader Modal App - Ready for deployment!")
    print("Deploy with: modal deploy modal_app.py")
    print("API endpoint will be available at: https://<app-id>--api-extract-imprints-dev.modal.run") 