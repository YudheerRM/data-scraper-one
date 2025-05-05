import requests
import logging
import json
import time
import random
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from improved_scraper import ImprovedPropertyScraper

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("listing_analysis.log")
    ]
)
logger = logging.getLogger()

class ListingAnalyzer:
    def __init__(self):
        self.scraper = ImprovedPropertyScraper("https://www.privateproperty.co.za")
    
    def get_headers(self):
        """Generate random headers to avoid detection"""
        return self.scraper.get_random_headers()
    
    def fetch_with_requests(self, url):
        """Fetch the listing page using requests"""
        try:
            logger.info(f"Fetching URL with requests: {url}")
            headers = self.get_headers()
            response = requests.get(url, headers=headers, timeout=20)
            
            if response.status_code != 200:
                logger.error(f"Failed to fetch page: {response.status_code}")
                return None
                
            return response.text
        except Exception as e:
            logger.error(f"Error fetching with requests: {str(e)}")
            return None
    
    def fetch_with_selenium(self, url):
        """Fetch the listing page using Selenium"""
        driver = None
        try:
            options = Options()
            options.add_argument("--headless")
            options.add_argument("--disable-gpu")
            options.add_argument(f"user-agent={self.scraper.get_random_user_agent()}")
            
            driver = webdriver.Chrome(options=options)
            logger.info(f"Fetching URL with Selenium: {url}")
            driver.get(url)
            
            # Wait for page to load dynamically
            time.sleep(5)
            
            # Save the HTML for analysis
            html = driver.page_source
            driver.quit()
            return html
            
        except Exception as e:
            logger.error(f"Error fetching with Selenium: {str(e)}")
            if driver:
                driver.quit()
            return None
    
    def analyze_listing_page(self, url):
        """Analyze a specific property listing page"""
        # Try with requests first
        html_content = self.fetch_with_requests(url)
        
        # If requests fails, try with Selenium
        if not html_content:
            logger.info("Requests failed, trying with Selenium")
            html_content = self.fetch_with_selenium(url)
        
        if not html_content:
            logger.error("Failed to fetch the listing page content")
            return False
        
        # Save the HTML for reference
        listing_id = url.split('/')[-1]
        with open(f"listing_{listing_id}.html", "w", encoding="utf-8") as f:
            f.write(html_content)
        
        # Parse the HTML
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Analyze the property listing structure
        self.analyze_property_structure(soup, url)
        
        return True
    
    def analyze_property_structure(self, soup, url):
        """Analyze the structure of a property listing page"""
        print("\n=== Property Listing Analysis ===")
        print(f"URL: {url}")
        
        # Extract main details
        try:
            # Find property title
            title_selectors = [
                '.detail-title h1', 
                '.listing-title', 
                'h1.title',
                'h1'
            ]
            
            for selector in title_selectors:
                title = soup.select_one(selector)
                if title:
                    print(f"\nTitle: {title.text.strip()}")
                    print(f"Selector: {selector}")
                    break
            
            # Find property price
            price_selectors = [
                '.detail-price', 
                '.listing-price', 
                '.price',
                'span.price'
            ]
            
            for selector in price_selectors:
                price = soup.select_one(selector)
                if price:
                    print(f"\nPrice: {price.text.strip()}")
                    print(f"Selector: {selector}")
                    break
            
            # Find property features
            feature_selectors = [
                '.property-features', 
                '.listing-features', 
                '.features',
                '.property-info'
            ]
            
            for selector in feature_selectors:
                features = soup.select_one(selector)
                if features:
                    print(f"\nFeatures found with selector: {selector}")
                    feature_items = features.select('li') or features.select('.feature')
                    for item in feature_items:
                        print(f"  - {item.text.strip()}")
                    break
            
            # Find property description
            desc_selectors = [
                '.propertyDescription', 
                '.listing-description', 
                '.description',
                '#description'
            ]
            
            for selector in desc_selectors:
                description = soup.select_one(selector)
                if description:
                    desc_text = description.text.strip()
                    print(f"\nDescription: {desc_text[:150]}...")
                    print(f"Selector: {selector}")
                    break
            
            # Find property images
            image_selectors = [
                '.property-images img', 
                '.listing-images img', 
                '.gallery img',
                '.carousel img'
            ]
            
            for selector in image_selectors:
                images = soup.select(selector)
                if images:
                    print(f"\nFound {len(images)} images with selector: {selector}")
                    for i, img in enumerate(images[:3]):  # Show first 3 images
                        print(f"  Image {i+1}: {img.get('src', img.get('data-src', 'No source'))}")
                    break
            
            # Find agent/contact info
            agent_selectors = [
                '.agent-details', 
                '.listing-agent', 
                '.contact-info',
                '.agent-card'
            ]
            
            for selector in agent_selectors:
                agent = soup.select_one(selector)
                if agent:
                    print(f"\nAgent/Contact info found with selector: {selector}")
                    agent_name = agent.select_one('.name, .agent-name')
                    if agent_name:
                        print(f"  Name: {agent_name.text.strip()}")
                    agent_phone = agent.select_one('.phone, .tel, .contact')
                    if agent_phone:
                        print(f"  Contact: {agent_phone.text.strip()}")
                    break
            
            # Find all elements with itemtype attributes (Schema.org)
            schema_elements = soup.find_all(attrs={"itemtype": True})
            if schema_elements:
                print("\nSchema.org markup found:")
                for elem in schema_elements[:5]:  # Show first 5
                    print(f"  Type: {elem.get('itemtype')}")
            
            # Find meta tags with property information
            meta_tags = soup.find_all('meta', attrs={'property': True})
            if meta_tags:
                print("\nMeta tags with property information:")
                for tag in meta_tags[:5]:  # Show first 5
                    print(f"  {tag.get('property')}: {tag.get('content', '')[:50]}")
            
            # Find all structured data scripts
            json_ld_scripts = soup.select('script[type="application/ld+json"]')
            if json_ld_scripts:
                print("\nStructured data found:")
                for script in json_ld_scripts:
                    try:
                        json_data = json.loads(script.string)
                        print(f"  Type: {json_data.get('@type', 'Unknown')}")
                    except:
                        print("  Could not parse JSON-LD script")
            
        except Exception as e:
            logger.error(f"Error analyzing property structure: {str(e)}")

def main():
    if len(sys.argv) > 1:
        url = sys.argv[1]
    else:
        url = "https://www.privateproperty.co.za/to-rent/western-cape/cape-town/bellville/oakglen/RR4191874"
    
    analyzer = ListingAnalyzer()
    analyzer.analyze_listing_page(url)

if __name__ == "__main__":
    import sys
    main()
