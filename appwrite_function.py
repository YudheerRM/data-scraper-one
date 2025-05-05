import os
import json
import time
import logging
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Fix for module import issue - use absolute imports
import improved_scraper
from improved_scraper import ImprovedPropertyScraper
import extract_agent_info
from extract_agent_info import extract_agent_contact_info
import tempfile

# Configure logging for serverless environment
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger()

# Helper function to add CORS headers to the response
def add_cors_headers(res):
    """Add CORS headers to allow cross-origin requests"""
    res.header('Access-Control-Allow-Origin', '*')
    res.header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
    res.header('Access-Control-Allow-Headers', 'Content-Type')
    return res

def handle_scrape_multiple_listings(url, num_listings=10):
    """
    Scrape multiple listings and return as Excel file or JSON
    
    Args:
        url (str): URL to scrape from
        num_listings (int): Number of listings to scrape
    
    Returns:
        dict: Response with data file or JSON
    """
    try:
        # Determine max pages based on number of listings (assume ~20 per page)
        est_max_pages = (num_listings // 20) + 1
        
        # Create a scraper instance with limited pages
        scraper = ImprovedPropertyScraper(url, output_file="temp_properties.json")
        
        # Set a limit to avoid too many requests
        max_to_scrape = min(num_listings, 100)
        
        # Perform scraping
        scraper.scrape(max_pages=est_max_pages)
        
        # Get the scraped properties
        properties = scraper.properties[:max_to_scrape]
        
        # Try pandas for Excel, fall back to JSON if pandas is not available
        try:
            import pandas as pd
            from io import BytesIO
            
            # Convert to DataFrame for Excel export
            df = pd.DataFrame(properties)
            
            # Create Excel file in memory
            excel_buffer = BytesIO()
            df.to_excel(excel_buffer, index=False, engine='openpyxl')
            excel_buffer.seek(0)
            
            # Read the Excel data as bytes
            excel_data = excel_buffer.getvalue()
            
            # Return response with Excel data
            return {
                "success": True,
                "message": f"Successfully scraped {len(properties)} listings",
                "file_type": "excel",
                "file": {
                    "name": "property_listings.xlsx",
                    "data": excel_data,
                    "type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                }
            }
        except ImportError as e:
            logger.warning(f"Pandas not available: {str(e)}. Falling back to JSON output.")
            
            # Fall back to JSON response
            return {
                "success": True,
                "message": f"Successfully scraped {len(properties)} listings",
                "file_type": "json",
                "data": properties
            }
            
    except Exception as e:
        logger.error(f"Error in scrape_multiple_listings: {str(e)}")
        return {
            "success": False,
            "message": f"Error: {str(e)}"
        }

def handle_get_latest_listing_with_contact(url):
    """
    Get the latest listing with contact info
    
    Args:
        url (str): URL to scrape from
    
    Returns:
        dict: Latest listing with contact info
    """
    try:
        # Create scraper to get just the first page
        scraper = ImprovedPropertyScraper(url, output_file="temp_latest.json")
        
        # Scrape just one page
        scraper.scrape(max_pages=1)
        
        # Check if we got any properties
        if not scraper.properties or len(scraper.properties) == 0:
            return {
                "success": False,
                "message": "No listings found"
            }
        
        # Get the first (latest) listing
        latest_listing = scraper.properties[0]
        
        # Check if the listing has a URL
        if 'url' not in latest_listing or not latest_listing['url']:
            return {
                "success": False,
                "message": "Listing URL not found"
            }
        
        # Get the full URL if it's relative
        listing_url = latest_listing['url']
        if listing_url.startswith('/'):
            # Parse from the base url
            base_parts = url.split('/')
            if len(base_parts) > 3:
                listing_url = f"{base_parts[0]}//{base_parts[2]}{listing_url}"
        
        logger.info(f"Extracting contact info from: {listing_url}")
        
        # Extract contact info using the agent contact extractor
        # Run in non-headless mode for better interaction with dynamic elements
        contact_info = extract_agent_contact_info(listing_url, headless=False)
        
        # Combine listing info with contact info
        combined_info = {
            **latest_listing,
            "contact_details": contact_info
        }
        
        return {
            "success": True,
            "data": combined_info
        }
        
    except Exception as e:
        logger.error(f"Error in get_latest_listing_with_contact: {str(e)}")
        return {
            "success": False,
            "message": f"Error: {str(e)}"
        }

def setup_chrome_for_serverless():
    """Set up Chrome for a serverless environment"""
    chrome_options = Options()
    
    # Required for serverless environment
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    
    # Set up path for Chrome binary in serverless
    # This may need adjustment based on your Appwrite environment
    chrome_binary_location = os.environ.get("CHROME_BINARY_PATH", "/usr/bin/google-chrome")
    if os.path.exists(chrome_binary_location):
        chrome_options.binary_location = chrome_binary_location
    
    return chrome_options

def main(req, res):
    """
    Main entry point for Appwrite function
    
    Args:
        req: Request object from Appwrite
        res: Response object from Appwrite
    
    Returns:
        Response with data or error
    """
    try:
        # Add CORS headers to all responses
        res = add_cors_headers(res)
        
        # Extract parameters
        body = req.body or {}
        params = req.query or {}
        
        # Get operation mode and url
        mode = body.get('mode') or params.get('mode', 'latest')
        url = body.get('url') or params.get('url', 'https://www.privateproperty.co.za/to-rent/western-cape/cape-town/55')
        
        # Set up Chrome for serverless if needed
        # Uncomment if you need to modify the global Chrome options
        # setup_chrome_for_serverless()
        
        if mode == 'multiple':
            # Get number of listings
            num_listings = int(body.get('num_listings') or params.get('num_listings', 10))
            result = handle_scrape_multiple_listings(url, num_listings)
            
            if result.get('success', False):
                if result.get('file_type') == 'excel' and 'file' in result:
                    # Return Excel file
                    res.header('Content-Type', result['file']['type'])
                    res.header('Content-Disposition', f"attachment; filename=\"{result['file']['name']}\"")
                    return res.send(result['file']['data'], 200)
                else:
                    # Return JSON data
                    return res.json(result)
            else:
                # Return error response
                return res.json(result)
        else:
            # Get latest listing with contact info
            result = handle_get_latest_listing_with_contact(url)
            return res.json(result)
            
    except Exception as e:
        logger.error(f"Error in main function: {str(e)}")
        # Make sure CORS headers are included even in error responses
        return res.json({
            "success": False,
            "message": f"Server error: {str(e)}"
        }, 500)

# Local testing
if __name__ == "__main__":
    class MockRequest:
        def __init__(self, mode='latest', url=None, num_listings=None):
            self.body = {
                'mode': mode,
                'url': url,
                'num_listings': num_listings
            }
            self.query = {}
    
    class MockResponse:
        def __init__(self):
            self.headers = {}
            
        def header(self, key, value):
            self.headers[key] = value
            
        def json(self, data, status=200):
            print(f"Response Status: {status}")
            print(f"Response Headers: {self.headers}")
            print(f"Response Data: {json.dumps(data, indent=2)}")
            return data
            
        def send(self, data, status=200):
            print(f"Sending file, Status: {status}")
            print(f"Response Headers: {self.headers}")
            print(f"File size: {len(data)} bytes")
            return data
    
    # Test get latest with contact
    req = MockRequest(mode='latest', url='https://www.privateproperty.co.za/to-rent/western-cape/cape-town/55')
    res = MockResponse()
    main(req, res)
    
    # Test multiple listings
    # req = MockRequest(mode='multiple', url='https://www.privateproperty.co.za/to-rent/western-cape/cape-town/55', num_listings=5)
    # res = MockResponse()
    # main(req, res)
