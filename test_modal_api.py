#!/usr/bin/env python3
"""
Test script for Modal API
"""

import requests
import json
import time

def test_modal_api():
    """Test the Modal API with sample URLs"""
    
    # API endpoint (will be updated after deployment)
    api_url = "https://federicodeponte--imprint-reader-api-extract-imprints.modal.run"
    
    # Test data
    test_urls = [
        "https://www.elenra.de",
        "https://www.bahn.de", 
        "https://www.stadtwerke-baden-baden.de"
    ]
    
    print(f"🧪 Testing Modal API with {len(test_urls)} URLs")
    print(f"🌐 Endpoint: {api_url}")
    print("-" * 60)
    
    # Prepare request
    payload = {"urls": test_urls}
    headers = {"Content-Type": "application/json"}
    
    try:
        print("📤 Sending request...")
        start_time = time.time()
        
        response = requests.post(api_url, json=payload, headers=headers, timeout=300)
        
        processing_time = time.time() - start_time
        print(f"⏱️  Response time: {processing_time:.1f}s")
        
        if response.status_code == 200:
            data = response.json()
            print("✅ API Response Successful!")
            print(f"📊 Success rate: {data.get('success_rate_percent', 0)}%")
            print(f"✅ Successful: {data.get('successful_extractions', 0)}")
            print(f"❌ Failed: {data.get('failed_extractions', 0)}")
            
            # Show sample results
            results = data.get('results', [])
            print(f"\n📋 Sample Results ({len(results)} total):")
            print("-" * 60)
            
            for i, result in enumerate(results[:3], 1):
                status = "✅" if result['success'] else "❌"
                print(f"{status} {i}. {result['original_url']}")
                if result['success']:
                    print(f"   Company: {result['company_name']}")
                    print(f"   City: {result['city']}")
                    print(f"   Imprint URL: {result['imprint_url']}")
                else:
                    print(f"   Error: {result['error_message']}")
                print()
            
            print("🎯 Results are ready for Supabase integration!")
            
        else:
            print(f"❌ API Error: {response.status_code}")
            print(f"Response: {response.text}")
            
    except requests.exceptions.Timeout:
        print("⏰ Request timed out (>5 minutes)")
    except requests.exceptions.ConnectionError:
        print("🌐 Connection error - check if Modal app is deployed")
    except Exception as e:
        print(f"💥 Error: {str(e)}")

def test_local_validation():
    """Test input validation without calling API"""
    print("\n🔧 Testing input validation...")
    
    # Test cases
    test_cases = [
        {"urls": []},  # Empty
        {"urls": ["invalid-url"]},  # Invalid URL
        {"urls": ["https://example.com"] * 150},  # Too many URLs
        {"urls": ["https://example.com"]},  # Valid
    ]
    
    for i, test_case in enumerate(test_cases, 1):
        urls = test_case["urls"]
        print(f"Test {i}: {len(urls)} URLs - ", end="")
        
        if len(urls) == 0:
            print("❌ Empty (should fail)")
        elif len(urls) > 100:
            print("❌ Too many (should fail)")
        elif any(not url.startswith(('http://', 'https://')) and not '.' in url for url in urls):
            print("⚠️  Invalid format (might fail)")
        else:
            print("✅ Valid format")

if __name__ == "__main__":
    print("🚀 Modal API Test Suite")
    print("=" * 60)
    
    # Test validation logic
    test_local_validation()
    
    # Test actual API (comment out if not deployed yet)
    print("\n" + "=" * 60)
    test_modal_api()
    
    print("\n�� Test complete!") 