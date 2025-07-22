#!/usr/bin/env python3
"""
Simple test example for the Imprint Reader
"""

from imprint_reader import ImprintReader
import json

def test_imprint_reader():
    """Test the imprint reader with a sample website"""
    
    # Initialize the reader with your API key
    api_key = "AIzaSyCcV31i8YA-YKLPHC0gx5zdD50gBcjTxq4"
    reader = ImprintReader(api_key)
    
    # Test URL - you can replace this with any website
    test_url = "https://www.google.com"
    
    print(f"Testing Imprint Reader with: {test_url}")
    print("-" * 50)
    
    # Process the URL
    result = reader.process_url(test_url)
    
    if result:
        print("✅ Successfully extracted imprint information!")
        print(f"Original URL: {result['url']}")
        print(f"Imprint URL: {result['imprint_url']}")
        print("\nExtracted Data:")
        print(json.dumps(result['imprint_data'], indent=2, ensure_ascii=False))
    else:
        print("❌ Failed to extract imprint information")
        print("This could be because:")
        print("- The website doesn't have an imprint page")
        print("- The imprint page is not linked from the homepage")
        print("- The website structure is unusual")

if __name__ == "__main__":
    test_imprint_reader() 