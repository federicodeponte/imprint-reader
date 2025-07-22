#!/usr/bin/env python3
"""
Imprint Reader Script

This script:
1. Gets the source code of a homepage from a given URL
2. Extracts all relative links from the HTML
3. Uses Gemini-2.5-flash to identify which link is the imprint page
4. Fetches the imprint page and converts it to markdown
5. Uses Gemini to extract structured imprint data
"""

import requests
import re
import sys
import json
import csv
import os
import time
import random
import warnings
from datetime import datetime
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from markdownify import markdownify as md
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import urllib3

# Suppress SSL warnings when we disable verification
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class ImprintReader:
    def __init__(self, api_key):
        """Initialize with Gemini API key"""
        self.api_key = api_key
        self.base_url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
        
        # Setup requests session with retries
        self.session = requests.Session()
        
        # Configure retry strategy for HTTP requests
        retry_strategy = Retry(
            total=3,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "POST"],  # Updated parameter name
            backoff_factor=1
        )
        
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        
        # Add a small delay between requests to be respectful
        self.last_request_time = 0
        self.min_request_interval = 0.2  # Reduced to 0.2 seconds for threading
        
    def _call_gemini_api(self, prompt, max_retries=3):
        """Make a direct API call to Gemini with smart retry logic"""
        headers = {
            'Content-Type': 'application/json',
        }
        
        data = {
            'contents': [{
                'parts': [{
                    'text': prompt
                }]
            }]
        }
        
        for attempt in range(max_retries):
            try:
                # Add jitter to prevent thundering herd
                if attempt > 0:
                    jitter = random.uniform(0.5, 1.5)
                    wait_time = (2 ** attempt) * jitter  # Exponential backoff with jitter
                    print(f"   - Retrying Gemini API call in {wait_time:.1f}s (attempt {attempt + 1}/{max_retries})")
                    time.sleep(wait_time)
                
                response = self.session.post(
                    f"{self.base_url}?key={self.api_key}", 
                    headers=headers, 
                    json=data,
                    timeout=45  # Increased timeout
                )
                
                # Handle rate limiting
                if response.status_code == 429:
                    retry_after = int(response.headers.get('Retry-After', 60))
                    print(f"   - Rate limited, waiting {retry_after}s...")
                    time.sleep(retry_after)
                    continue
                
                response.raise_for_status()
                
                result = response.json()
                if 'candidates' in result and len(result['candidates']) > 0:
                    if 'content' in result['candidates'][0] and 'parts' in result['candidates'][0]['content']:
                        return result['candidates'][0]['content']['parts'][0]['text']
                
                # If we get here but no content, try again
                print(f"   - Empty response from Gemini (attempt {attempt + 1}/{max_retries})")
                if attempt == max_retries - 1:
                    return None
                continue
                
            except requests.exceptions.Timeout:
                print(f"   - Gemini API timeout (attempt {attempt + 1}/{max_retries})")
                if attempt == max_retries - 1:
                    return None
                continue
                
            except requests.exceptions.ConnectionError as e:
                print(f"   - Connection error (attempt {attempt + 1}/{max_retries}): {e}")
                if attempt == max_retries - 1:
                    return None
                continue
                
            except requests.RequestException as e:
                print(f"   - API error (attempt {attempt + 1}/{max_retries}): {e}")
                if attempt == max_retries - 1:
                    return None
                continue
        
        return None
    
    def get_page_content(self, url, max_retries=2):
        """Fetch the HTML content of a webpage with robust error handling"""
        # Respect rate limiting - ensure minimum interval between requests
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        if time_since_last < self.min_request_interval:
            sleep_time = self.min_request_interval - time_since_last
            time.sleep(sleep_time)
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        
        for attempt in range(max_retries):
            try:
                # First attempt with SSL verification
                response = self.session.get(
                    url, 
                    headers=headers, 
                    timeout=15,
                    verify=True
                )
                response.raise_for_status()
                self.last_request_time = time.time()  # Update timestamp
                return response.text
                
            except requests.exceptions.SSLError as e:
                print(f"   - SSL error on attempt {attempt + 1}: {e}")
                if attempt < max_retries - 1:
                    print(f"   - Retrying without SSL verification...")
                    try:
                        # Retry without SSL verification
                        response = self.session.get(
                            url, 
                            headers=headers, 
                            timeout=15,
                            verify=False
                        )
                        response.raise_for_status()
                        self.last_request_time = time.time()  # Update timestamp
                        return response.text
                    except requests.RequestException as e2:
                        print(f"   - Failed even without SSL verification: {e2}")
                        continue
                else:
                    print(f"   - SSL verification failed permanently")
                    
            except requests.exceptions.Timeout:
                print(f"   - Request timeout on attempt {attempt + 1}")
                if attempt < max_retries - 1:
                    time.sleep(2)  # Brief pause before retry
                    
            except requests.exceptions.ConnectionError as e:
                print(f"   - Connection error on attempt {attempt + 1}: {e}")
                if attempt < max_retries - 1:
                    time.sleep(2)
                    
            except requests.RequestException as e:
                print(f"   - Request error on attempt {attempt + 1}: {e}")
                if attempt < max_retries - 1:
                    time.sleep(1)
                    
        print(f"Error fetching {url} after {max_retries} attempts")
        return None
            
    def extract_relative_links(self, html_content, base_url):
        """Extract all relative links from HTML content with fallback methods"""
        soup = BeautifulSoup(html_content, 'html.parser')
        links = []
        
        # Method 1: Standard anchor tag extraction
        for link in soup.find_all('a', href=True):
            href = link.get('href')
            text = link.get_text(strip=True)
            
            # Convert relative URLs to absolute URLs
            absolute_url = urljoin(base_url, href)
            
            # Only include links that are relative or belong to the same domain
            parsed_base = urlparse(base_url)
            parsed_link = urlparse(absolute_url)
            
            if parsed_link.netloc == parsed_base.netloc:
                links.append({
                    'url': absolute_url,
                    'text': text,
                    'href': href
                })
        
        # Method 2: If no links found, try alternative extraction methods
        if not links:
            print("   - No standard links found, trying alternative extraction methods...")
            
            # Try finding links in button elements with onclick
            for button in soup.find_all(['button', 'div', 'span'], onclick=True):
                onclick = button.get('onclick')
                if onclick and ('location' in onclick or 'window.open' in onclick):
                    # Extract URL from JavaScript
                    url_match = re.search(r"['\"]([^'\"]+)['\"]", onclick)
                    if url_match:
                        href = url_match.group(1)
                        text = button.get_text(strip=True)
                        absolute_url = urljoin(base_url, href)
                        parsed_link = urlparse(absolute_url)
                        
                        if parsed_link.netloc == parsed_base.netloc:
                            links.append({
                                'url': absolute_url,
                                'text': text,
                                'href': href
                            })
            
            # Try finding navigation menus, footers with potential imprint links
            for nav_element in soup.find_all(['nav', 'footer', 'div'], class_=re.compile(r'(nav|menu|footer|legal)', re.I)):
                for link in nav_element.find_all('a', href=True):
                    href = link.get('href')
                    text = link.get_text(strip=True)
                    absolute_url = urljoin(base_url, href)
                    parsed_link = urlparse(absolute_url)
                    
                    if parsed_link.netloc == parsed_base.netloc:
                        links.append({
                            'url': absolute_url,
                            'text': text,
                            'href': href
                        })
            
            # Try common imprint URLs even if not linked
            if not links:
                print("   - Trying common imprint URL patterns...")
                common_paths = [
                    '/impressum', '/imprint', '/legal', '/legal-notice',
                    '/impressum.html', '/imprint.html', '/legal.html',
                    '/impressum.php', '/imprint.php', '/legal.php',
                    '/kontakt', '/contact', '/about', '/ueber-uns'
                ]
                
                for path in common_paths:
                    test_url = urljoin(base_url, path)
                    links.append({
                        'url': test_url,
                        'text': f'Common path: {path}',
                        'href': path
                    })
                
        return links
        
    def identify_imprint_page(self, links):
        """Use Gemini to identify which link is most likely the imprint page"""
        # Prepare the links for analysis
        link_descriptions = []
        for i, link in enumerate(links):
            link_descriptions.append(f"{i}: URL: {link['url']}, Text: '{link['text']}', Href: '{link['href']}'")
        
        links_text = "\n".join(link_descriptions)
        
        prompt = f"""
Analyze the following list of links from a website and identify which one is most likely the imprint page (also known as "Impressum" in German, legal notice, or legal information page).

Links:
{links_text}

Please respond with ONLY the number (index) of the link that is most likely the imprint page. If none of the links appear to be an imprint page, respond with "-1".

Look for keywords like: imprint, impressum, legal, notice, about, contact, terms, privacy, legal notice, disclaimer, etc.

If you see a "legal" or "legal notice" or similar page that might contain multiple legal documents including an imprint, choose that one.
"""

        try:
            result = self._call_gemini_api(prompt)
            if not result:
                return None
                
            result = result.strip()
            
            # Extract the number from the response
            match = re.search(r'-?\d+', result)
            if match:
                index = int(match.group())
                if 0 <= index < len(links):
                    return links[index]
                elif index == -1:
                    print("No imprint page found in the links")
                    return None
            
            print(f"Could not parse Gemini response: {result}")
            return None
            
        except Exception as e:
            print(f"Error identifying imprint page: {e}")
            return None
            
    def check_for_secondary_imprint_links(self, page_url, page_content):
        """Check if a legal/about page contains secondary links to an imprint page"""
        print(f"   - Checking for secondary imprint links in {page_url}")
        
        # Extract links from this page
        secondary_links = self.extract_relative_links(page_content, page_url)
        
        if not secondary_links:
            return None
            
        # Filter for likely imprint links
        imprint_candidates = []
        
        for link in secondary_links:
            link_text = link['text'].lower().strip()
            link_href = link['href'].lower()
            
            # Score the link based on how likely it is to be an imprint
            score = 0
            
            # Strong indicators (exact matches)
            if link_text in ['imprint', 'impressum', 'legal notice'] or '/imprint' in link_href or '/impressum' in link_href:
                score += 10
                
            # Good indicators
            elif 'imprint' in link_text or 'impressum' in link_text:
                score += 8
            elif 'imprint' in link_href or 'impressum' in link_href:
                score += 7
                
            # Moderate indicators
            elif link_text in ['contact', 'about us', 'legal info', 'legal information']:
                score += 3
            elif 'legal' in link_text and 'notice' in link_text:
                score += 5
                
            # Avoid false positives
            if 'privacy' in link_text or 'cookie' in link_text or 'terms' in link_text:
                score -= 2
            if len(link_text) < 3:  # Very short text is probably not useful
                score -= 3
                
            if score >= 5:  # Only consider links with decent score
                imprint_candidates.append((link, score))
        
        if imprint_candidates:
            # Sort by score (highest first)
            imprint_candidates.sort(key=lambda x: x[1], reverse=True)
            print(f"   - Found {len(imprint_candidates)} potential imprint links")
            # Return the highest scoring candidate
            return imprint_candidates[0][0]
            
        return None
            
    def html_to_markdown(self, html_content):
        """Convert HTML content to markdown"""
        try:
            # Use markdownify to convert HTML to markdown
            markdown_content = md(html_content, heading_style="ATX")
            return markdown_content
        except Exception as e:
            print(f"Error converting HTML to markdown: {e}")
            return html_content
    
    def extract_company_name(self, imprint_data):
        """Smart extraction of company name from various possible locations in JSON"""
        if not isinstance(imprint_data, dict):
            return None
            
        # Try direct company_name field first
        if imprint_data.get('company_name'):
            return imprint_data['company_name']
            
        # Try common alternative paths
        paths_to_try = [
            ['main_entity', 'organization_name'],
            ['company_info', 'name'], 
            ['main_entity', 'name'],
            ['organization_name'],
            ['name'],
            ['company'],
            ['entity_name'],
            ['business_name']
        ]
        
        for path in paths_to_try:
            current = imprint_data
            try:
                for key in path:
                    if isinstance(current, dict) and key in current:
                        current = current[key]
                    else:
                        break
                else:
                    # If we made it through the whole path
                    if current and isinstance(current, str):
                        return current
            except (KeyError, TypeError):
                continue
                
        return None
    
    def flatten_imprint_data(self, data, prefix='', max_text_length=100):
        """Flatten nested dictionary for CSV export"""
        flattened = {}
        
        for key, value in data.items():
            if prefix:
                new_key = f"{prefix}_{key}"
            else:
                new_key = key
                
            if isinstance(value, dict):
                flattened.update(self.flatten_imprint_data(value, new_key))
            elif isinstance(value, list):
                if value:  # If list is not empty
                    for i, item in enumerate(value):
                        if isinstance(item, dict):
                            flattened.update(self.flatten_imprint_data(item, f"{new_key}_{i}"))
                        else:
                            flattened[f"{new_key}_{i}"] = str(item)
                    # Also create a combined field for simple lists
                    if all(not isinstance(item, dict) for item in value):
                        combined_text = "; ".join(str(item) for item in value)
                        # Truncate if too long
                        if len(combined_text) > max_text_length:
                            combined_text = combined_text[:max_text_length-3] + "..."
                        flattened[new_key] = combined_text
                else:
                    flattened[new_key] = ""
            else:
                text_value = str(value) if value is not None else ""
                # Truncate long text fields for CSV readability
                if len(text_value) > max_text_length:
                    text_value = text_value[:max_text_length-3] + "..."
                flattened[new_key] = text_value
                
        return flattened
    
    def save_to_csv(self, run_data, timestamp):
        """Save the run data to a CSV file"""
        try:
            # Create results directory if it doesn't exist
            os.makedirs('results', exist_ok=True)
            
            # Extract key information in a clean, simplified format
            imprint_data = run_data.get('imprint_data', {})
            
            # Smart company name extraction
            company_name = self.extract_company_name(imprint_data)
            
            # Extract other key fields with fallbacks
            def safe_extract(data, paths, default=""):
                """Extract data from multiple possible paths"""
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
                                    return "; ".join(str(x) for x in current[:3])  # Max 3 items
                                return str(current)[:150]  # Limit length
                    except (KeyError, TypeError):
                        continue
                return default
            
            # Create simplified CSV row with key fields only
            csv_row = {
                'timestamp': timestamp,
                'original_url': run_data['url'],
                'imprint_url': run_data['imprint_url'] or '',
                'processing_date': datetime.now().strftime('%Y-%m-%d'),
                'processing_time': datetime.now().strftime('%H:%M:%S'),
                'company_name': company_name or safe_extract(imprint_data, [['error']]) or '',
                'managing_directors': safe_extract(imprint_data, [
                    ['managing_directors'], ['main_entity', 'managing_directors'], 
                    ['company_info', 'managing_directors']
                ]),
                'street': safe_extract(imprint_data, [
                    ['business_address', 'street'], ['main_entity', 'address', 'street'],
                    ['company_info', 'address', 'street']
                ]),
                'city': safe_extract(imprint_data, [
                    ['business_address', 'city'], ['main_entity', 'address', 'city'],
                    ['company_info', 'address', 'city']
                ]),
                'postal_code': safe_extract(imprint_data, [
                    ['business_address', 'postal_code'], ['main_entity', 'address', 'postal_code'],
                    ['company_info', 'address', 'postal_code']
                ]),
                'country': safe_extract(imprint_data, [
                    ['business_address', 'country'], ['main_entity', 'address', 'country'],
                    ['company_info', 'address', 'country']
                ]),
                'phone': safe_extract(imprint_data, [
                    ['phone_numbers'], ['main_entity', 'phone_numbers'],
                    ['company_info', 'phone_numbers']
                ]),
                'email': safe_extract(imprint_data, [
                    ['email_addresses'], ['main_entity', 'email_addresses'],
                    ['company_info', 'email_addresses']
                ]),
                'website': safe_extract(imprint_data, [
                    ['website_url'], ['main_entity', 'website_url'],
                    ['company_info', 'website_url']
                ]),
                'registration_number': safe_extract(imprint_data, [
                    ['registration_details', 'registration_number'], 
                    ['main_entity', 'registration_details', 'registration_number'],
                    ['company_info', 'registration_details', 'registration_number']
                ]),
                'vat_id': safe_extract(imprint_data, [
                    ['vat_id'], ['main_entity', 'vat_id'], ['company_info', 'vat_id']
                ])
            }
            
            # Check if CSV file exists to determine if we need headers
            csv_filename = 'results/imprint_extractions.csv'
            file_exists = os.path.exists(csv_filename)
            
            # Write to CSV
            with open(csv_filename, 'a', newline='', encoding='utf-8') as csvfile:
                if csv_row:
                    fieldnames = csv_row.keys()
                    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                    
                    # Write header only if file is new
                    if not file_exists:
                        writer.writeheader()
                    
                    writer.writerow(csv_row)
            
            print(f"CSV data appended to: {csv_filename}")
            
        except Exception as e:
            print(f"Error saving to CSV: {e}")
    
    def save_to_json(self, run_data, timestamp):
        """Save the run data to timestamped JSON files"""
        try:
            # Create results directory if it doesn't exist
            os.makedirs('results', exist_ok=True)
            
            # Add timestamp and metadata to the data
            enhanced_data = {
                'timestamp': timestamp,
                'processing_info': {
                    'date': datetime.now().strftime('%Y-%m-%d'),
                    'time': datetime.now().strftime('%H:%M:%S'),
                    'timezone': datetime.now().astimezone().strftime('%Z')
                },
                **run_data
            }
            
            # Save individual timestamped file
            domain = urlparse(run_data['url']).netloc.replace('.', '_')
            json_filename = f"results/{domain}_{timestamp}.json"
            
            with open(json_filename, 'w', encoding='utf-8') as f:
                json.dump(enhanced_data, f, indent=2, ensure_ascii=False)
            
            print(f"Individual JSON saved to: {json_filename}")
            
            # Also maintain a master log file
            log_filename = 'results/extraction_log.json'
            
            # Load existing log or create new one
            if os.path.exists(log_filename):
                with open(log_filename, 'r', encoding='utf-8') as f:
                    log_data = json.load(f)
            else:
                log_data = {'extractions': []}
            
            # Add this extraction to the log
            log_data['extractions'].append(enhanced_data)
            
            # Keep only last 1000 entries to prevent file from getting too large
            if len(log_data['extractions']) > 1000:
                log_data['extractions'] = log_data['extractions'][-1000:]
            
            # Save updated log
            with open(log_filename, 'w', encoding='utf-8') as f:
                json.dump(log_data, f, indent=2, ensure_ascii=False)
            
            print(f"Master log updated: {log_filename}")
            
        except Exception as e:
            print(f"Error saving to JSON: {e}")
            
    def extract_imprint_data(self, markdown_content):
        """Use Gemini to extract structured imprint data from markdown"""
        prompt = f"""
Analyze the following imprint/legal notice page content and extract all relevant legal and contact information. 

IMPORTANT: Please use EXACTLY this JSON structure with these field names:

{{
  "company_name": "Main company/organization name",
  "managing_directors": ["Director 1", "Director 2"],
  "business_address": {{
    "street": "Street address",
    "city": "City name", 
    "postal_code": "Postal code",
    "country": "Country"
  }},
  "phone_numbers": ["Phone 1", "Phone 2"],
  "email_addresses": ["email1@example.com"],
  "website_url": "https://website.com",
  "registration_details": {{
    "trade_register": "Register name",
    "registration_number": "Registration number",
    "court": "Court name"
  }},
  "vat_id": "VAT ID number",
  "tax_id": "Tax ID number", 
  "professional_liability_insurance": "Insurance details",
  "other_legal_info": {{
    "key": "value"
  }}
}}

Content to analyze:
{markdown_content}

Rules:
- Use null for missing information
- Keep text fields concise (max 200 characters each)
- For multiple entities, choose the PRIMARY/MAIN one
- Use consistent field names as shown above
- Do not create new field names

Respond with ONLY the JSON object, no additional text.
"""

        try:
            result = self._call_gemini_api(prompt)
            if not result:
                return {"error": "No response from Gemini API"}
                
            result = result.strip()
            
            # Try to extract JSON from the response
            json_match = re.search(r'\{.*\}', result, re.DOTALL)
            if json_match:
                try:
                    json_data = json.loads(json_match.group())
                    return json_data
                except json.JSONDecodeError:
                    pass
            
            # If JSON parsing fails, return the raw response
            return {"raw_response": result}
            
        except Exception as e:
            print(f"Error extracting imprint data: {e}")
            return {"error": str(e)}
            
    def process_url(self, url):
        """Main method to process a URL and extract imprint information"""
        print(f"Processing URL: {url}")
        
        # Step 1: Get homepage content
        print("1. Fetching homepage content...")
        html_content = self.get_page_content(url)
        if not html_content:
            return None
            
        # Step 2: Extract relative links
        print("2. Extracting relative links...")
        links = self.extract_relative_links(html_content, url)
        print(f"Found {len(links)} links")
        
        if not links:
            print("No links found on the homepage")
            return None
            
        # Step 3: Identify imprint page
        print("3. Identifying imprint page using Gemini...")
        imprint_link = self.identify_imprint_page(links)
        if not imprint_link:
            print("Could not identify imprint page")
            return None
            
        print(f"Identified imprint page: {imprint_link['url']}")
        
        # Step 3.5: Check if this might be a legal section that contains imprint links
        # Look for keywords that suggest this is a legal section rather than direct imprint
        potential_legal_section = False
        link_text = imprint_link['text'].lower()
        link_href = imprint_link['href'].lower()
        
        legal_section_keywords = ['legal', 'terms', 'policies', 'about', 'footer']
        imprint_direct_keywords = ['imprint', 'impressum']
        
        # Check if this looks like a legal section rather than direct imprint
        has_legal_keywords = any(keyword in link_text or keyword in link_href for keyword in legal_section_keywords)
        has_direct_imprint = any(keyword in link_text or keyword in link_href for keyword in imprint_direct_keywords)
        
        if has_legal_keywords and not has_direct_imprint:
            potential_legal_section = True
            print("   - This appears to be a legal section, checking for secondary imprint links...")
        
        # Step 4: Fetch imprint page content
        print("4. Fetching imprint page content...")
        imprint_html = self.get_page_content(imprint_link['url'])
        if not imprint_html:
            return None
            
        # Step 4.5: If this is a potential legal section, look for secondary imprint links
        final_imprint_link = imprint_link
        final_imprint_html = imprint_html
        
        if potential_legal_section:
            secondary_imprint = self.check_for_secondary_imprint_links(imprint_link['url'], imprint_html)
            if secondary_imprint:
                print(f"   - Found secondary imprint link: {secondary_imprint['url']}")
                print("4b. Fetching actual imprint page content...")
                secondary_html = self.get_page_content(secondary_imprint['url'])
                if secondary_html:
                    final_imprint_link = secondary_imprint
                    final_imprint_html = secondary_html
                    print(f"   - Using secondary imprint page: {secondary_imprint['url']}")
                else:
                    print("   - Failed to fetch secondary page, using original")
            else:
                print("   - No secondary imprint links found, using original page")
            
        # Step 5: Convert to markdown
        print("5. Converting to markdown...")
        markdown_content = self.html_to_markdown(final_imprint_html)
        
        # Step 6: Extract imprint data
        print("6. Extracting imprint data using Gemini...")
        imprint_data = self.extract_imprint_data(markdown_content)
        
        return {
            'url': url,
            'imprint_url': final_imprint_link['url'],
            'imprint_data': imprint_data,
            'markdown_content': markdown_content
        }

def main():
    """Main function to run the script"""
    if len(sys.argv) != 2:
        print("Usage: python imprint_reader.py <URL>")
        sys.exit(1)
        
    url = sys.argv[1]
    
    # Validate URL
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
        
    # Generate timestamp for this run
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # Initialize the imprint reader
    api_key = "AIzaSyCcV31i8YA-YKLPHC0gx5zdD50gBcjTxq4"
    reader = ImprintReader(api_key)
    
    # Process the URL
    result = reader.process_url(url)
    
    if result:
        print("\n" + "="*50)
        print("RESULTS")
        print("="*50)
        print(f"Original URL: {result['url']}")
        print(f"Imprint URL: {result['imprint_url']}")
        print("\nExtracted Imprint Data:")
        print(json.dumps(result['imprint_data'], indent=2, ensure_ascii=False))
        
        # Save to timestamped files (CSV + JSON)
        print("\n" + "="*50)
        print("SAVING DATA")
        print("="*50)
        
        # Save to CSV and JSON with timestamp
        reader.save_to_csv(result, timestamp)
        reader.save_to_json(result, timestamp)
        
        # Also save legacy format for backward compatibility
        output_file = f"imprint_data_{urlparse(url).netloc.replace('.', '_')}.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        print(f"Legacy format saved to: {output_file}")
    else:
        print("Failed to extract imprint information")
        
        # Still log failed attempts
        failed_result = {
            'url': url,
            'imprint_url': None,
            'imprint_data': {'error': 'Failed to extract imprint information'},
            'markdown_content': None
        }
        reader.save_to_csv(failed_result, timestamp)
        reader.save_to_json(failed_result, timestamp)

if __name__ == "__main__":
    main() 