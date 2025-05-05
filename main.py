import os
import json
import time
import logging
import sys
import re
import random
import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from urllib.parse import urlparse
import tempfile

# Try to import optional dependencies
try:
    from fake_useragent import UserAgent
    has_fake_ua = True
except ImportError:
    has_fake_ua = False
    # Fallback list of common user agents
    COMMON_USER_AGENTS = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.2 Safari/605.1.15',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:90.0) Gecko/20100101 Firefox/90.0',
    ]

# Configure logging for serverless environment
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger()

#############################################################################
# SECTION 1: PROPERTY SCRAPER 
# (originally from improved_scraper.py)
#############################################################################

class ImprovedPropertyScraper:
    def __init__(self, base_url, output_file="properties.json"):
        self.base_url = base_url
        self.output_file = output_file
        self.properties = []
        
        # Handle user agent with or without the fake_useragent package
        if has_fake_ua:
            self.ua = UserAgent()
            self.get_random_user_agent = lambda: self.ua.random
        else:
            self.get_random_user_agent = lambda: random.choice(COMMON_USER_AGENTS)
        
        # Configure various selectors to try (fallbacks)
        self.property_selectors = [
            ".featured-listing",            # Private Property featured listings
            ".listing-result",              # Private Property standard listings
            ".property-card",               # Common class for property cards
            ".listing-item",                # Alternative common class
            "[data-testid='property-card']", # Data attribute selector
            ".result-card",                  # Another common pattern
            "div[itemtype='http://schema.org/Product']", # Schema.org markup
            ".property",                    # Basic property class
            ".real-estate-item",            # Another common pattern
            ".card",                        # Generic card class that might contain properties
            "article",                      # Many sites use article tags for listings
            ".grid-item"                    # Grid-based layouts
        ]
        
        # Website-specific extraction strategies
        self.site_extractors = {
            "privateproperty.co.za": self.extract_privateproperty_data
        }
        
        # Add pagination selectors - updated with newer syntax
        self.pagination_selectors = [
            ".paging a.next",  # Private Property pagination
            ".pagination-next",
            ".pagination a[rel='next']",
            ".pagination-container .next",
            "a.next-page",
            "a[aria-label='Next page']",
            "a:-soup-contains('Next')",  # Updated from :contains to :-soup-contains
            "a:-soup-contains('>')",     # Updated from :contains to :-soup-contains
            ".pager-next a",
            "[data-testid='pagination-next']"
        ]
        
        # Add max retries for failed pages
        self.max_retries = 3
        
        # Track scraped pages to avoid duplicates
        self.scraped_pages = set()
    
    def get_random_headers(self):
        """Generate random headers to avoid detection"""
        return {
            'User-Agent': self.get_random_user_agent(),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Referer': 'https://www.google.com/',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
    
    def scrape_with_requests(self, url=None, page=1):
        """Attempt to scrape using requests and BeautifulSoup"""
        try:
            if url is None:
                url = f"{self.base_url}?page={page}"
            
            # Skip if this URL has already been scraped
            if url in self.scraped_pages:
                logger.info(f"Skipping already scraped URL: {url}")
                return False
            
            logger.info(f"Scraping with requests: {url}")
            
            headers = self.get_random_headers()
            response = requests.get(url, headers=headers, timeout=20)
            
            if response.status_code != 200:
                logger.error(f"Failed to fetch page: {response.status_code}")
                return False
            
            self.scraped_pages.add(url)  # Mark as scraped
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Debug - save HTML for inspection in non-serverless environment
            # with open(f"page_{page}_source.html", "w", encoding="utf-8") as f:
            #     f.write(response.text)
            
            # Try different selectors
            properties_found = 0
            for selector in self.property_selectors:
                property_elements = soup.select(selector)
                if property_elements:
                    logger.info(f"Found {len(property_elements)} properties with selector: {selector}")
                    properties_found = len(property_elements)
                    self.extract_properties(property_elements)
                    break
            
            if properties_found == 0:
                logger.warning("No properties found with standard selectors")
                return False
            
            # Check if there's a next page and return its URL
            has_next = self.has_next_page(soup)
            if has_next:
                return self.get_next_page_url(soup, url, page)
            else:
                logger.info("No more pages to scrape")
                return None
            
        except Exception as e:
            logger.error(f"Error in requests scraping: {str(e)}")
            return False
    
    def scrape_with_selenium(self, url=None, page=1):
        """Fallback to Selenium for JavaScript-heavy pages"""
        driver = None
        try:
            options = Options()
            options.add_argument("--headless")
            options.add_argument("--disable-gpu")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument(f"user-agent={self.get_random_user_agent()}")
            
            driver = webdriver.Chrome(options=options)
            
            if url is None:
                url = f"{self.base_url}?page={page}"
            
            # Skip if this URL has already been scraped
            if url in self.scraped_pages:
                logger.info(f"Skipping already scraped URL: {url}")
                if driver:
                    driver.quit()
                return False
            
            logger.info(f"Scraping with Selenium: {url}")
            driver.get(url)
            
            # Wait for page to load dynamically
            time.sleep(5)  # Base wait
            
            self.scraped_pages.add(url)  # Mark as scraped
            
            properties_found = 0
            for selector in self.property_selectors:
                try:
                    # Wait for elements to be present
                    WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                    )
                    property_elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    
                    if property_elements:
                        logger.info(f"Found {len(property_elements)} properties with Selenium using selector: {selector}")
                        properties_found = len(property_elements)
                        self.extract_properties_selenium(property_elements)
                        break
                except TimeoutException:
                    continue
            
            if properties_found == 0:
                logger.warning("No properties found with Selenium")
                if driver:
                    driver.quit()
                return False
            
            # Check if there's a next page
            has_next = self.has_next_page_selenium(driver)
            
            if has_next:
                # Get the current URL before clicking (in case we need to construct the next URL)
                current_url = driver.current_url
                
                # Try to click the next button
                clicked = self.click_next_page_selenium(driver)
                
                if clicked:
                    # Return the new URL after navigation
                    next_url = driver.current_url
                    if next_url != current_url:  # Ensure we actually navigated
                        driver.quit()
                        return next_url
                
                # Fallback: construct the next URL if click didn't work
                driver.quit()
                return self.get_next_page_url(BeautifulSoup(driver.page_source, 'html.parser'), 
                                            current_url, page)
            else:
                logger.info("No more pages to scrape with Selenium")
                driver.quit()
                return None
            
        except Exception as e:
            logger.error(f"Error in Selenium scraping: {str(e)}")
            if driver:
                driver.quit()
            return False
    
    def extract_properties(self, property_elements):
        """Extract property data from BeautifulSoup elements"""
        # Check if we have a site-specific extractor for the current domain
        domain = self.base_url.split('/')[2] if '//' in self.base_url else self.base_url.split('/')[0]
        
        # Use site-specific extractor if available
        for site, extractor in self.site_extractors.items():
            if site in domain:
                logger.info(f"Using specialized extractor for {site}")
                extractor(property_elements)
                return
        
        # Default generic extractor
        for elem in property_elements:
            try:
                # These are generic selectors - adapt to your target site
                title = elem.select_one('.property-title, .listing-title, h2, h3')
                price = elem.select_one('.property-price, .listing-price, .price')
                location = elem.select_one('.property-location, .listing-location, .address')
                
                property_data = {
                    'title': title.text.strip() if title else 'No Title',
                    'price': price.text.strip() if price else 'No Price',
                    'location': location.text.strip() if location else 'No Location',
                    # Add more fields as needed
                }
                
                self.properties.append(property_data)
                logger.debug(f"Extracted property: {property_data['title']}")
                
            except Exception as e:
                logger.error(f"Error extracting property data: {str(e)}")

    def extract_privateproperty_data(self, property_elements):
        """Extract property data specific to privateproperty.co.za"""
        for elem in property_elements:
            try:
                # Determine if it's a featured listing or a standard listing
                is_featured = 'featured-listing' in elem.get('class', [])
                
                # Select appropriate class prefixes based on listing type
                prefix = 'featured-listing' if is_featured else 'listing-result'
                
                # Extract property details
                title = elem.select_one(f'.{prefix}__title')
                price = elem.select_one(f'.{prefix}__price')
                location = elem.select_one(f'.{prefix}__address')
                description = elem.select_one(f'.{prefix}__description')
                
                # Extract features (bedrooms, bathrooms, etc.)
                features = {}
                feature_elements = elem.select(f'.{prefix}__feature')
                for feature in feature_elements:
                    feature_title = feature.get('title', '').lower()
                    if feature_title:
                        feature_value = feature.text.strip()
                        features[feature_title] = feature_value
                
                # Extract listing ID and type
                listing_id = None
                listing_type = None
                wishlist_btn = elem.select_one(f'.{prefix}__wishlist-btn')
                if wishlist_btn:
                    listing_id = wishlist_btn.get('data-listing-id')
                    listing_type = wishlist_btn.get('data-listing-type')
                
                # Extract agent or agency info
                agent_name = elem.select_one(f'.{prefix}__agent-name')
                advertiser_info = elem.select_one(f'.{prefix}__advertiser')
                
                # Create comprehensive property data
                property_data = {
                    'title': title.text.strip() if title else 'No Title',
                    'price': price.text.strip() if price else 'No Price',
                    'location': location.text.strip() if location else 'No Location',
                    'description': description.text.strip() if description else '',
                    'features': features,
                    'listing_id': listing_id,
                    'listing_type': listing_type,
                    'is_featured': is_featured,
                    'agent': agent_name.text.strip() if agent_name else '',
                    'url': elem.get('href', '')
                }
                
                self.properties.append(property_data)
                logger.debug(f"Extracted property from Private Property: {property_data['title']}")
                
            except Exception as e:
                logger.error(f"Error extracting Private Property data: {str(e)}")

    def extract_properties_selenium(self, property_elements):
        """Extract property data from Selenium elements"""
        # Check if we have a site-specific extractor for the current domain
        domain = self.base_url.split('/')[2] if '//' in self.base_url else self.base_url.split('/')[0]
        
        # Use site-specific selenium extractor if available
        for site, extractor in self.site_extractors.items():
            if site in domain:
                logger.info(f"Using specialized Selenium extractor for {site}")
                self.extract_privateproperty_data_selenium(property_elements)
                return
        
        # Default generic Selenium extractor
        for elem in property_elements:
            try:
                # Generic selectors - adapt to your target site
                title = elem.find_elements(By.CSS_SELECTOR, '.property-title, .listing-title, h2, h3')
                price = elem.find_elements(By.CSS_SELECTOR, '.property-price, .listing-price, .price')
                location = elem.find_elements(By.CSS_SELECTOR, '.property-location, .listing-location, .address')
                
                property_data = {
                    'title': title[0].text.strip() if title else 'No Title',
                    'price': price[0].text.strip() if price else 'No Price',
                    'location': location[0].text.strip() if location else 'No Location',
                    # Add more fields as needed
                }
                
                self.properties.append(property_data)
                logger.debug(f"Extracted property with Selenium: {property_data['title']}")
                
            except Exception as e:
                logger.error(f"Error extracting property data with Selenium: {str(e)}")
                
    def extract_privateproperty_data_selenium(self, property_elements):
        """Extract property data from Selenium elements specific to privateproperty.co.za"""
        for elem in property_elements:
            try:
                # Determine if it's a featured listing or a standard listing
                class_attribute = elem.get_attribute('class')
                is_featured = class_attribute and 'featured-listing' in class_attribute
                
                # Select appropriate class prefixes based on listing type
                prefix = 'featured-listing' if is_featured else 'listing-result'
                
                # Extract property details
                title = elem.find_elements(By.CSS_SELECTOR, f'.{prefix}__title')
                price = elem.find_elements(By.CSS_SELECTOR, f'.{prefix}__price')
                location = elem.find_elements(By.CSS_SELECTOR, f'.{prefix}__address')
                description = elem.find_elements(By.CSS_SELECTOR, f'.{prefix}__description')
                
                # Extract features (bedrooms, bathrooms, etc.)
                features = {}
                feature_elements = elem.find_elements(By.CSS_SELECTOR, f'.{prefix}__feature')
                for feature in feature_elements:
                    feature_title = feature.get_attribute('title')
                    if feature_title:
                        feature_title = feature_title.lower()
                        feature_value = feature.text.strip()
                        features[feature_title] = feature_value
                
                # Extract listing ID and type
                listing_id = None
                listing_type = None
                wishlist_btn = elem.find_elements(By.CSS_SELECTOR, f'.{prefix}__wishlist-btn')
                if wishlist_btn:
                    listing_id = wishlist_btn[0].get_attribute('data-listing-id')
                    listing_type = wishlist_btn[0].get_attribute('data-listing-type')
                
                # Extract agent or agency info
                agent_name = elem.find_elements(By.CSS_SELECTOR, f'.{prefix}__agent-name')
                
                # Create comprehensive property data
                property_data = {
                    'title': title[0].text.strip() if title else 'No Title',
                    'price': price[0].text.strip() if price else 'No Price',
                    'location': location[0].text.strip() if location else 'No Location',
                    'description': description[0].text.strip() if description else '',
                    'features': features,
                    'listing_id': listing_id,
                    'listing_type': listing_type,
                    'is_featured': is_featured,
                    'agent': agent_name[0].text.strip() if agent_name else '',
                    'url': elem.get_attribute('href') or ''
                }
                
                self.properties.append(property_data)
                logger.debug(f"Extracted property from Private Property with Selenium: {property_data['title']}")
                
            except Exception as e:
                logger.error(f"Error extracting Private Property data with Selenium: {str(e)}")
    
    def save_properties(self):
        """Save the scraped properties to JSON file"""
        if not self.properties:
            logger.warning("No properties to save")
            return False
        
        try:
            with open(self.output_file, 'w', encoding='utf-8') as f:
                json.dump(self.properties, f, ensure_ascii=False, indent=2)
            logger.info(f"Saved {len(self.properties)} properties to {self.output_file}")
            return True
        except Exception as e:
            logger.error(f"Error saving properties: {str(e)}")
            return False
    
    def has_next_page(self, soup):
        """Check if there is a next page available based on pagination elements"""
        for selector in self.pagination_selectors:
            try:
                next_button = soup.select_one(selector)
                if next_button:
                    # Check if the next button is disabled
                    disabled = next_button.get('disabled') or 'disabled' in next_button.get('class', [])
                    if not disabled:
                        return True
            except Exception as e:
                logger.debug(f"Error checking pagination with selector {selector}: {str(e)}")
        return False
    
    def has_next_page_selenium(self, driver):
        """Check if there is a next page available using Selenium"""
        for selector in self.pagination_selectors:
            try:
                next_buttons = driver.find_elements(By.CSS_SELECTOR, selector)
                if next_buttons and len(next_buttons) > 0:
                    # Check if the next button is disabled
                    disabled = next_buttons[0].get_attribute('disabled') or 'disabled' in (next_buttons[0].get_attribute('class') or '')
                    if not disabled:
                        return True
            except Exception as e:
                logger.debug(f"Error checking pagination with Selenium selector {selector}: {str(e)}")
        return False
    
    def get_next_page_url(self, soup, current_url, current_page):
        """Extract the URL of the next page"""
        # First try to find a direct link to the next page
        for selector in self.pagination_selectors:
            try:
                next_button = soup.select_one(selector)
                if next_button and next_button.get('href'):
                    next_url = next_button.get('href')
                    # Handle relative URLs
                    if next_url.startswith('/'):
                        parsed_url = urlparse(current_url)
                        next_url = f"{parsed_url.scheme}://{parsed_url.netloc}{next_url}"
                    return next_url
            except Exception:
                continue
        
        # If no direct link found, construct the URL with page parameter
        # Check if current URL already has query parameters
        if '?' in current_url:
            if 'page=' in current_url:
                return re.sub(r'page=\d+', f'page={current_page + 1}', current_url)
            else:
                return f"{current_url}&page={current_page + 1}"
        else:
            return f"{current_url}?page={current_page + 1}"
    
    def click_next_page_selenium(self, driver):
        """Click on the next page button using Selenium"""
        for selector in self.pagination_selectors:
            try:
                next_buttons = driver.find_elements(By.CSS_SELECTOR, selector)
                if next_buttons and len(next_buttons) > 0 and next_buttons[0].is_displayed():
                    # Check if the next button is disabled
                    disabled = next_buttons[0].get_attribute('disabled') or 'disabled' in (next_buttons[0].get_attribute('class') or '')
                    if not disabled:
                        logger.info("Clicking on next page button")
                        next_buttons[0].click()
                        # Wait for page to load
                        time.sleep(3)  
                        return True
            except Exception as e:
                logger.debug(f"Error clicking next page with selector {selector}: {str(e)}")
        return False
    
    def scrape(self, max_pages=None):
        """Main scraping method with multiple strategies and auto pagination"""
        total_properties = 0
        page = 1
        next_url = self.base_url  # Start with base URL
        retries = 0
        
        while next_url and (max_pages is None or page <= max_pages):
            logger.info(f"Processing page {page}")
            
            # Try requests first
            next_url_result = self.scrape_with_requests(url=next_url, page=page)
            
            if next_url_result:
                if isinstance(next_url_result, str):  # It's a URL for the next page
                    logger.info(f"Successfully scraped page {page} with requests")
                    next_url = next_url_result
                    page += 1
                    retries = 0  # Reset retries on success
                else:
                    # No more pages to scrape
                    next_url = None
            else:
                # Fall back to Selenium if requests failed
                logger.info(f"Falling back to Selenium for page {page}")
                next_url_result = self.scrape_with_selenium(url=next_url, page=page)
                
                if next_url_result:
                    if isinstance(next_url_result, str):  # It's a URL for the next page
                        logger.info(f"Successfully scraped page {page} with Selenium")
                        next_url = next_url_result
                        page += 1
                        retries = 0  # Reset retries on success
                    else:
                        # No more pages to scrape
                        next_url = None
                else:
                    # Both scraping methods failed
                    retries += 1
                    logger.warning(f"Both scraping methods failed on page {page}, retry {retries}/{self.max_retries}")
                    
                    if retries >= self.max_retries:
                        logger.error(f"Maximum retries reached for page {page}, moving to next page")
                        # Attempt to construct next page URL
                        next_url = f"{self.base_url}?page={page + 1}"
                        page += 1
                        retries = 0
            
            # Add a random delay between requests
            time.sleep(random.uniform(2, 5))
            
            # Save properties periodically (every 3 pages)
            if page % 3 == 0:
                self.save_properties()
        
        total_properties = len(self.properties)
        logger.info(f"Scraping completed. Total properties found: {total_properties}")
        
        if total_properties > 0:
            self.save_properties()
        else:
            logger.warning("No properties found across all pages and methods")

#############################################################################
# SECTION 2: AGENT CONTACT INFO EXTRACTOR 
# (originally from extract_agent_info.py)
#############################################################################

def extract_agent_contact_info(url, headless=False, timeout=30):
    """
    Extract agent contact information from a property listing page
    
    Args:
        url (str): URL of the property listing
        headless (bool): Whether to run browser in headless mode
        timeout (int): Maximum time to wait for elements
    
    Returns:
        dict: Dictionary containing agent contact information
    """
    driver = None
    try:
        # Setup Selenium
        options = Options()
        if headless:
            options.add_argument("--headless")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        
        driver = webdriver.Chrome(options=options)
        logger.info(f"Navigating to: {url}")
        
        # Load the page
        driver.get(url)
        
        # Wait for the page to load
        WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
        
        logger.info("Page loaded, looking for contact button")
        
        # Targeting the specific button by text content
        button_clicked = False
        
        # First try: Look for the exact button with text "Show contact number"
        try:
            # Find button by XPath with exact text
            show_number_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Show contact number')]"))
            )
            logger.info("Found show contact number button by text content")
            
            # Scroll to the button to make it visible
            driver.execute_script("arguments[0].scrollIntoView(true);", show_number_button)
            time.sleep(1)
            
            # Click the button
            show_number_button.click()
            button_clicked = True
            logger.info("Clicked show contact number button by text content")
            time.sleep(3)  # Wait for popup to appear
        except Exception as e:
            logger.warning(f"Could not find button by text content: {str(e)}")
        
        # Second try: Try to find the button by CSS class pattern if the first attempt failed
        if not button_clicked:
            try:
                # The button has a specific class pattern that includes "btn" and "outline"
                buttons = driver.find_elements(By.CSS_SELECTOR, "button.btn.outline")
                for button in buttons:
                    if "Show contact number" in button.text or "Show number" in button.text:
                        logger.info("Found show contact button by class and text")
                        driver.execute_script("arguments[0].scrollIntoView(true);", button)
                        time.sleep(1)
                        button.click()
                        button_clicked = True
                        logger.info("Clicked show contact button by class and text")
                        time.sleep(3)  # Wait for popup to appear
                        break
            except Exception as e:
                logger.warning(f"Could not find button by class and text: {str(e)}")
                
        # Third try: Look for any phone SVG icon inside buttons
        if not button_clicked:
            try:
                buttons_with_svg = driver.find_elements(By.CSS_SELECTOR, "button svg")
                for svg_element in buttons_with_svg:
                    button = svg_element.find_element(By.XPATH, "./..")
                    if "Show" in button.text and ("contact" in button.text.lower() or "number" in button.text.lower()):
                        logger.info("Found show contact button by SVG icon and text")
                        driver.execute_script("arguments[0].scrollIntoView(true);", button)
                        time.sleep(1)
                        button.click()
                        button_clicked = True
                        logger.info("Clicked show contact button by SVG icon and text")
                        time.sleep(3)  # Wait for popup to appear
                        break
            except Exception as e:
                logger.warning(f"Could not find button by SVG icon: {str(e)}")
        
        # Extract contact information
        contact_info = {
            "url": url,
            "extracted_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "button_clicked": button_clicked
        }
        
        # After clicking the button, wait for contact info to appear in a modal
        if button_clicked:
            # Wait for a few seconds to ensure modal/popup appears
            time.sleep(3)
            
            # Look for phone numbers in the dialog/modal that appeared
            try:
                # First look for a modal dialog that might have appeared
                modals = driver.find_elements(By.CSS_SELECTOR, "dialog[open], .modal--open, .dialog--open, div[role='dialog']")
                if modals:
                    logger.info(f"Found {len(modals)} potential modal dialogs")
                    for modal in modals:
                        modal_text = modal.text
                        logger.info(f"Modal text: {modal_text[:100]}...")  # Log first 100 chars
                        
                        # Extract phone numbers from the modal text
                        phone_matches = re.findall(r'(?:\+\d{1,3}[-\.\s]?)?(?:\(?\d{3}\)?[-\.\s]?){1,2}\d{3,4}[-\.\s]?\d{3,4}', modal_text)
                        if phone_matches:
                            contact_info['phone_numbers'] = phone_matches
                            logger.info(f"Found phone numbers in modal: {phone_matches}")
                else:
                    logger.info("No modal dialog found, looking for phone numbers in page")
            except Exception as e:
                logger.error(f"Error examining modal: {str(e)}")
                
            # As a backup, look for any new elements that might have appeared after clicking
            html_after_click = driver.page_source
            soup_after = BeautifulSoup(html_after_click, 'html.parser')
            
            # Extract any phone numbers that might be visible now
            visible_text = soup_after.get_text()
            phone_pattern = re.compile(r'(?:\+\d{1,3}[-\.\s]?)?(?:\(?\d{3}\)?[-\.\s]?){1,2}\d{3,4}[-\.\s]?\d{3,4}')
            phone_matches = phone_pattern.findall(visible_text)
            
            if phone_matches and 'phone_numbers' not in contact_info:
                # Filter out matches that are likely not phone numbers
                filtered_matches = [p for p in phone_matches if len(re.sub(r'\D', '', p)) >= 9]
                if filtered_matches:
                    contact_info['phone_numbers'] = filtered_matches[:3]  # Take first 3 matches
        
        return contact_info
        
    except Exception as e:
        logger.error(f"Error during extraction: {str(e)}")
        return {"error": str(e), "url": url}
        
    finally:
        if driver:
            driver.quit()

#############################################################################
# SECTION 3: APPWRITE FUNCTION COMPONENTS
# (Main function handling)
#############################################################################

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
    
    # Required for serverless environment functioning
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    
    # Set up path for Chrome binary in serverless
    chrome_binary_location = os.environ.get("CHROME_BINARY_PATH", "/usr/bin/google-chrome")
    if os.path.exists(chrome_binary_location):
        chrome_options.binary_location = chrome_binary_location
    
    return chrome_options

# Main entry point for Appwrite function (expects req, res)
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

# Appwrite expects a single-argument entrypoint: main(context)
def __appwrite_main(context):
    # Appwrite context provides req and res as attributes
    return main(context.req, context.res)

# For Appwrite runtime: set the entrypoint to __appwrite_main
# This ensures Appwrite calls the correct function signature
main = __appwrite_main

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
    
    # Test multiple listings now!
    # req = MockRequest(mode='multiple', url='https://www.privateproperty.co.za/to-rent/western-cape/cape-town/55', num_listings=5)
    # res = MockResponse()
    # main(req, res)
