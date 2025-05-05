import sys
import logging
import os
from bs4 import BeautifulSoup
from improved_scraper import ImprovedPropertyScraper

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("pagination_test.log")
    ]
)
logger = logging.getLogger()

def test_pagination_detection(html_file):
    """Test if pagination detection works correctly"""
    with open(html_file, 'r', encoding='utf-8') as f:
        html_content = f.read()
    
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Create a scraper instance
    scraper = ImprovedPropertyScraper("https://www.privateproperty.co.za")
    
    # Check for next page
    has_next = scraper.has_next_page(soup)
    
    if has_next:
        print("✓ Next page detected in the HTML!")
        
        # Get the next page URL
        current_url = "https://www.privateproperty.co.za/to-rent/western-cape/cape-town/55"
        next_url = scraper.get_next_page_url(soup, current_url, 1)
        print(f"Next page URL: {next_url}")
        
        return True
    else:
        print("✗ No next page detected in the HTML")
        
        # See if we can find any pagination elements at all
        pagination_elements = []
        print("\nSearching for potential pagination elements:")
        for selector in [".paging", ".pagination", "nav", "ul.pages", ".page-navigation"]:
            elements = soup.select(selector)
            if elements:
                print(f"Found potential pagination container: {selector}")
                pagination_elements.extend(elements)
        
        if pagination_elements:
            print("\nExamining potential pagination elements:")
            for i, elem in enumerate(pagination_elements):
                print(f"Element {i+1}:")
                print(f"  Tag: {elem.name}")
                print(f"  Classes: {elem.get('class', [])}")
                print(f"  Text: {elem.text.strip()[:50]}...")
                
                # Look for links inside
                links = elem.select("a")
                if links:
                    print(f"  Contains {len(links)} links:")
                    for j, link in enumerate(links[:5]):  # Show first 5 links
                        print(f"    Link {j+1}: href='{link.get('href')}', text='{link.text.strip()}'")
        
        return False

def check_pagination_across_multiple_pages(base_url, max_pages=3):
    """Test pagination by actually navigating through pages"""
    print(f"Testing pagination across multiple pages from {base_url}")
    
    scraper = ImprovedPropertyScraper(base_url)
    page = 1
    next_url = base_url
    
    while next_url and page <= max_pages:
        print(f"\n--- Page {page} ---")
        
        # Try to scrape the page and get next URL
        next_url_result = scraper.scrape_with_selenium(url=next_url, page=page)
        
        if isinstance(next_url_result, str):
            print(f"✓ Successfully found next page: {next_url_result}")
            next_url = next_url_result
            page += 1
        else:
            print("✗ No more pages found or error occurred")
            break
        
        # Short delay between pages
        import time
        time.sleep(2)
    
    print(f"\nScraped {len(scraper.properties)} total properties across {page-1} pages")
    scraper.save_properties()
    
    return page > 1

if __name__ == "__main__":
    if len(sys.argv) > 1:
        if sys.argv[1] == '--navigate':
            # Test by actually navigating through pages
            url = "https://www.privateproperty.co.za/to-rent/western-cape/cape-town/55"
            check_pagination_across_multiple_pages(url)
        else:
            # Test with HTML file
            html_file = sys.argv[1]
            test_pagination_detection(html_file)
    else:
        # Try to find the most recent selenium HTML file
        files = [f for f in os.listdir('.') if f.startswith('page_') and f.endswith('_selenium.html')]
        if files:
            latest_file = max(files)
            print(f"Found latest Selenium HTML file: {latest_file}")
            test_pagination_detection(latest_file)
        else:
            print("Usage: python test_pagination.py path/to/html_file.html")
            print("       python test_pagination.py --navigate")
            print("No HTML files found in the current directory")
