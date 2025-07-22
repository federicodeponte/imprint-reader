#!/usr/bin/env python3
"""
Consolidate all individual JSON files into one clean master file
"""

import json
import os
import glob
from datetime import datetime

def consolidate_json_files():
    """Consolidate all individual JSON files into one master file"""
    
    # Get all individual JSON files (exclude master log)
    json_files = glob.glob("results/*_20250722_*.json")
    
    print(f"Found {len(json_files)} individual JSON files to consolidate...")
    
    consolidated_data = {
        "metadata": {
            "total_urls_processed": len(json_files),
            "consolidation_date": datetime.now().isoformat(),
            "processing_date": "2025-01-22",
            "source": "imprint-reader batch processing"
        },
        "extractions": []
    }
    
    successful_count = 0
    failed_count = 0
    
    for json_file in sorted(json_files):
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            # Extract relevant information
            extraction = {
                "url": data.get("url", ""),
                "imprint_url": data.get("imprint_url", ""),
                "timestamp": data.get("timestamp", ""),
                "success": data.get("imprint_data", {}).get("error") is None,
                "imprint_data": data.get("imprint_data", {})
            }
            
            # Count successes/failures
            if extraction["success"] and extraction["imprint_data"] and not extraction["imprint_data"].get("error"):
                successful_count += 1
            else:
                failed_count += 1
            
            consolidated_data["extractions"].append(extraction)
            
        except Exception as e:
            print(f"Error processing {json_file}: {e}")
            failed_count += 1
    
    # Update metadata with final counts
    consolidated_data["metadata"]["successful_extractions"] = successful_count
    consolidated_data["metadata"]["failed_extractions"] = failed_count
    consolidated_data["metadata"]["success_rate"] = round(successful_count / len(json_files) * 100, 1) if json_files else 0
    
    # Save consolidated file
    output_file = "results/consolidated_extractions.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(consolidated_data, f, indent=2, ensure_ascii=False)
    
    print(f"✅ Consolidated {len(json_files)} files into {output_file}")
    print(f"   - Successful: {successful_count}")
    print(f"   - Failed: {failed_count}")
    print(f"   - Success rate: {consolidated_data['metadata']['success_rate']}%")
    
    return output_file

if __name__ == "__main__":
    consolidate_json_files() 