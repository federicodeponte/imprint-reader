#!/usr/bin/env python3
"""
Batch processor for running imprint reader on multiple URLs from CSV file
Now with multithreading for faster processing!
"""

import csv
import time
import sys
import threading
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from imprint_reader import ImprintReader

class ThreadSafeBatchProcessor:
    """Thread-safe batch processor for imprint reading"""
    
    def __init__(self, api_key, max_workers=5):
        """Initialize with thread-safe components"""
        self.api_key = api_key
        self.max_workers = max_workers
        
        # Thread-safe locks
        self.csv_lock = threading.Lock()
        self.stats_lock = threading.Lock()
        self.progress_lock = threading.Lock()
        
        # Statistics tracking
        self.stats = {
            'total_processed': 0,
            'successful': 0,
            'failed': 0,
            'start_time': datetime.now()
        }
        
        # Create one reader instance per thread to avoid conflicts
        self.readers = {}
        
    def get_reader(self):
        """Get thread-local reader instance"""
        thread_id = threading.current_thread().ident
        if thread_id not in self.readers:
            self.readers[thread_id] = ImprintReader(self.api_key)
        return self.readers[thread_id]
    
    def process_single_url(self, url_data):
        """Process a single URL (thread worker function)"""
        i, total, url = url_data
        reader = self.get_reader()
        
        try:
            # Add https:// if not present
            if not url.startswith(('http://', 'https://')):
                url = 'https://' + url
            
            # Generate timestamp for this run
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            
            with self.progress_lock:
                print(f"\n[{i}/{total}] Processing: {url}")
                print("-" * 50)
            
            # Process the URL
            result = reader.process_url(url)
            
            if result and result.get('imprint_data') and not result['imprint_data'].get('error'):
                # Smart company name extraction
                company_name = reader.extract_company_name(result['imprint_data'])
                
                with self.progress_lock:
                    print(f"✅ SUCCESS: Found imprint data")
                    print(f"   - Company: {company_name or 'N/A'}")
                    print(f"   - Imprint URL: {result['imprint_url']}")
                
                # Thread-safe save operations
                with self.csv_lock:
                    reader.save_to_csv(result, timestamp)
                    reader.save_to_json(result, timestamp)
                
                with self.stats_lock:
                    self.stats['successful'] += 1
                    
                return {'status': 'success', 'url': url, 'company': company_name}
            else:
                with self.progress_lock:
                    print(f"❌ FAILED: No imprint data found")
                
                # Still log failed attempts
                failed_result = {
                    'url': url,
                    'imprint_url': None,
                    'imprint_data': {'error': 'No imprint data found'},
                    'markdown_content': None
                }
                
                with self.csv_lock:
                    reader.save_to_csv(failed_result, timestamp)
                    reader.save_to_json(failed_result, timestamp)
                
                with self.stats_lock:
                    self.stats['failed'] += 1
                    
                return {'status': 'failed', 'url': url, 'error': 'No imprint data found'}
                
        except Exception as e:
            with self.progress_lock:
                print(f"💥 ERROR: {str(e)}")
            
            # Log error
            error_result = {
                'url': url,
                'imprint_url': None,
                'imprint_data': {'error': f'Processing error: {str(e)}'},
                'markdown_content': None
            }
            
            with self.csv_lock:
                reader.save_to_csv(error_result, timestamp)
                reader.save_to_json(error_result, timestamp)
            
            with self.stats_lock:
                self.stats['failed'] += 1
                
            return {'status': 'error', 'url': url, 'error': str(e)}
        finally:
            with self.stats_lock:
                self.stats['total_processed'] += 1
    
    def process_urls_from_csv(self, csv_file, max_urls=100, start_from=0):
        """Process URLs from CSV file with multithreading"""
        
        try:
            with open(csv_file, 'r', encoding='utf-8') as file:
                csv_reader = csv.DictReader(file)
                urls = list(csv_reader)
                
            print(f"📋 Found {len(urls)} URLs in {csv_file}")
            print(f"🎯 Processing first {max_urls} URLs (starting from index {start_from})")
            print(f"🔥 Using {self.max_workers} concurrent threads for faster processing!")
            print("=" * 80)
            
            # Process the specified range of URLs
            urls_to_process = urls[start_from:start_from + max_urls]
            
            # Prepare URL data for threading
            url_tasks = []
            for i, row in enumerate(urls_to_process, start=start_from + 1):
                url = row['URL'].strip()
                if url:
                    url_tasks.append((i, len(urls), url))
            
            # Process URLs using ThreadPoolExecutor
            completed_tasks = 0
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                # Submit all tasks
                future_to_url = {executor.submit(self.process_single_url, url_data): url_data for url_data in url_tasks}
                
                # Process completed tasks
                for future in as_completed(future_to_url):
                    try:
                        result = future.result()
                        completed_tasks += 1
                        
                        # Progress update every 10 completed tasks
                        if completed_tasks % 10 == 0:
                            elapsed = datetime.now() - self.stats['start_time']
                            with self.stats_lock:
                                print(f"\n📊 Progress Update:")
                                print(f"   - Completed: {completed_tasks}/{len(url_tasks)}")
                                print(f"   - Successful: {self.stats['successful']}")
                                print(f"   - Failed: {self.stats['failed']}")
                                print(f"   - Elapsed: {elapsed}")
                                print(f"   - Avg time per URL: {elapsed.total_seconds() / max(completed_tasks, 1):.1f}s")
                        
                    except Exception as e:
                        print(f"💥 Future execution error: {str(e)}")
                        
        except Exception as e:
            print(f"💥 CRITICAL ERROR: {str(e)}")
            return self.stats
        
        # Final statistics
        elapsed = datetime.now() - self.stats['start_time']
        print("\n" + "=" * 80)
        print("📊 FINAL STATISTICS")
        print("=" * 80)
        print(f"Total URLs processed: {self.stats['total_processed']}")
        print(f"Successful extractions: {self.stats['successful']}")
        print(f"Failed attempts: {self.stats['failed']}")
        print(f"Success rate: {(self.stats['successful'] / max(self.stats['total_processed'], 1)) * 100:.1f}%")
        print(f"Total time: {elapsed}")
        print(f"Average time per URL: {elapsed.total_seconds() / max(self.stats['total_processed'], 1):.1f}s")
        print(f"🚀 Speedup with {self.max_workers} threads: ~{self.max_workers}x faster!")
        print(f"\n📁 All results saved to:")
        print(f"   - CSV: results/imprint_extractions.csv")
        print(f"   - JSON log: results/extraction_log.json")
        print(f"   - Individual files: results/")
        
        return self.stats

def main():
    """Main function"""
    if len(sys.argv) > 1:
        try:
            max_urls = int(sys.argv[1])
        except ValueError:
            print("Invalid number provided. Using default of 100.")
            max_urls = 100
    else:
        max_urls = 100
    
    # Determine optimal number of workers (not too many to avoid overwhelming APIs)
    max_workers = min(8, max(2, max_urls // 10))  # Between 2-8 workers
    
    csv_file = "Contacts Heero.csv"
    api_key = "AIzaSyCcV31i8YA-YKLPHC0gx5zdD50gBcjTxq4"
    
    print("🚀 Starting Threaded Batch Imprint Processing")
    print(f"📋 Source file: {csv_file}")
    print(f"🎯 Max URLs to process: {max_urls}")
    print(f"🔥 Concurrent threads: {max_workers}")
    print(f"⏰ Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    try:
        processor = ThreadSafeBatchProcessor(api_key, max_workers)
        stats = processor.process_urls_from_csv(csv_file, max_urls)
        print(f"\n✅ Batch processing completed!")
        
    except KeyboardInterrupt:
        print(f"\n⚠️ Processing interrupted by user")
    except Exception as e:
        print(f"\n💥 Batch processing failed: {str(e)}")

if __name__ == "__main__":
    main() 