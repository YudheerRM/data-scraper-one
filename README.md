# Property Scraper Appwrite Function

This function scrapes property listings from websites and returns either:
1. The latest listing with contact info
2. Multiple listings in an Excel file

## Deployment Instructions

### 1. Install the Appwrite CLI
```bash
npm install -g appwrite-cli
```

### 2. Login to Appwrite
```bash
appwrite login
```

### 3. Initialize the project (if not already done)
```bash
appwrite init function
```

### 4. Deploy the function
```bash
appwrite deploy function
```

### 5. Important Notes

- Make sure the function has all necessary files:
  - appwrite_function.py (main entry point)
  - improved_scraper.py
  - extract_agent_info.py
  - __init__.py
  - requirements.txt

- The function requires a headless Chrome browser to be available in the serverless environment
- The default timeout is set to 300 seconds (5 minutes)

## Usage

The function accepts the following parameters:

- `mode`: Either 'latest' or 'multiple'
- `url`: The property listing website URL to scrape
- `num_listings`: For 'multiple' mode, the number of listings to scrape (default: 10)

Example request:
```json
{
  "mode": "latest",
  "url": "https://www.privateproperty.co.za/to-rent/western-cape/cape-town/55"
}
```
