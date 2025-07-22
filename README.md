# Imprint Reader

A Python script that automatically finds and extracts imprint/legal information from websites using Google's Gemini-2.5-flash AI.

## Features

- Scrapes any website's homepage
- Extracts all relative links from the page
- Uses Gemini-2.5-flash AI to intelligently identify the imprint/legal notice page
- Converts the imprint page to markdown format
- Extracts structured legal information (company name, address, managing director, etc.)
- Outputs results in JSON format

## Installation

1. Install the required dependencies:
```bash
pip install -r requirements.txt
```

## Usage

Run the script with any website URL:

```bash
python imprint_reader.py <URL>
```

Examples:
```bash
python imprint_reader.py https://example.com
python imprint_reader.py example.com  # https:// will be added automatically
```

You can also use the test script to see how it works:
```bash
python test_example.py
```

## Output

The script will:
1. Display progress information as it processes the website
2. Print the extracted imprint data in JSON format
3. Save data in multiple formats:
   - **CSV**: Appends to `results/imprint_extractions.csv` (cumulative log with timestamps)
   - **JSON**: Individual timestamped files in `results/` directory
   - **Master Log**: `results/extraction_log.json` (maintains last 1000 extractions)
   - **Legacy**: `imprint_data_<domain>.json` (for backward compatibility)

## Sample Output

```json
{
  "company_name": "Example GmbH",
  "managing_director": "John Doe",
  "address": {
    "street": "Main Street 123",
    "city": "Berlin",
    "postal_code": "10115",
    "country": "Germany"
  },
  "contact": {
    "phone": "+49 30 12345678",
    "email": "info@example.com"
  },
  "registration": {
    "trade_register": "HRB 12345",
    "court": "Amtsgericht Berlin"
  },
  "vat_id": "DE123456789"
}
```

## Requirements

- Python 3.8+
- Internet connection
- Valid Google Gemini API key (already configured in the script)

## How it Works

1. **Homepage Scraping**: Fetches the HTML content of the provided URL
2. **Link Extraction**: Parses all relative links from the homepage
3. **AI Identification**: Uses Gemini-2.5-flash AI to identify which link is most likely the imprint page
4. **Content Extraction**: Fetches and converts the imprint page to markdown
5. **Data Structuring**: Uses Gemini-2.5-flash AI to extract structured legal information from the content

## File Structure

After running the script, the following directory structure is created:

```
imprint-reader/
├── results/
│   ├── imprint_extractions.csv          # Cumulative CSV log
│   ├── extraction_log.json              # Master JSON log
│   ├── www_example_com_20250114_143022.json  # Individual timestamped files
│   └── ...
├── imprint_data_www_example_com.json    # Legacy format
└── ...
```

## Supported Languages

The script works with websites in multiple languages, including:
- English (imprint, legal notice)
- German (Impressum)
- And other languages where legal notice pages are commonly found 