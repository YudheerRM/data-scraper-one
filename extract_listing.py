import requests
import logging
import json
import os
import re
import time
from datetime import datetime
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("property_extraction.log")
    ]
)
logger = logging.getLogger()

class PropertyListingExtractor:
    """Class to extract detailed information from a property listing page"""
    
    def __init__(self, use_selenium=True, headless=True):
        """Initialize the extractor with options"""
        self.use_selenium = use_selenium
        self.headless = headless
    
    def extract_from_url(self, url):
        """Extract property information from a URL"""
        logger.info(f"Extracting property information from: {url}")
        
        if self.use_selenium:
            html_content, driver = self._fetch_with_selenium(url)
            
            if html_content:
                # Save HTML for debugging
                listing_id = url.split('/')[-1]
                self._save_html(html_content, f"listing_{listing_id}_full.html")
                
                # Parse the HTML and get property data
                property_data = self._parse_listing_page(html_content, url)
                
                # Try to extract hidden contact information using the active driver
                if driver:
                    try:
                        contact_info = self._extract_hidden_contact_info(driver)
                        if contact_info:
                            # Add contact info to agent section if it exists
                            if 'agent' not in property_data:
                                property_data['agent'] = {}
                            property_data['agent'].update(contact_info)
                    except Exception as e:
                        logger.error(f"Error extracting hidden contact info: {str(e)}")
                    finally:
                        driver.quit()
                
                return property_data
            else:
                if driver:
                    driver.quit()
                return None
        else:
            html_content = self._fetch_with_requests(url)
            
            if not html_content:
                logger.error("Failed to fetch the property listing page")
                return None
            
            # Save HTML for debugging
            listing_id = url.split('/')[-1]
            self._save_html(html_content, f"listing_{listing_id}_full.html")
            
            # Parse the HTML
            return self._parse_listing_page(html_content, url)
    
    def _fetch_with_requests(self, url):
        """Fetch the listing page using requests"""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Referer': 'https://www.google.com/',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
            }
            
            response = requests.get(url, headers=headers, timeout=20)
            
            if response.status_code != 200:
                logger.error(f"Failed to fetch page: {response.status_code}")
                return None
            
            return response.text
        except Exception as e:
            logger.error(f"Error fetching with requests: {str(e)}")
            return None
    
    def _fetch_with_selenium(self, url):
        """Fetch the listing page using Selenium for JavaScript-heavy content"""
        driver = None
        try:
            options = Options()
            if self.headless:
                options.add_argument("--headless")
            options.add_argument("--disable-gpu")
            options.add_argument("--window-size=1920,1080")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            
            driver = webdriver.Chrome(options=options)
            logger.info(f"Fetching URL with Selenium: {url}")
            
            driver.get(url)
            
            # Wait for page to fully load
            time.sleep(5)
            
            # Wait for the contact form to load
            try:
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CLASS_NAME, "contact-form-container"))
                )
            except Exception:
                logger.warning("Timed out waiting for contact form, continuing anyway")
            
            # Click on "Show more" button if available to expand property description
            try:
                show_more = driver.find_element(By.ID, "show-more-button")
                if show_more and show_more.is_displayed():
                    show_more.click()
                    time.sleep(1)
            except Exception:
                logger.debug("No show more button found or could not click it")
            
            # Save screenshot for debugging
            driver.save_screenshot(f"listing_screenshot_{url.split('/')[-1]}.png")
            
            html = driver.page_source
            return html, driver
            
        except Exception as e:
            logger.error(f"Error fetching with Selenium: {str(e)}")
            if driver:
                driver.quit()
            return None, None
    
    def _extract_hidden_contact_info(self, driver):
        """Extract contact information that requires clicking a button to reveal"""
        contact_info = {}
        
        try:
            # Look for various "show number" or "contact" buttons
            show_number_selectors = [
                "#no-add-message-agent",  # From your HTML this seems to be contact agent button
                ".contact-agent-button",
                ".show-number-button",
                ".listing-contact__show-number",
                "button:contains('Show Number')",
                "a:contains('Show Number')",
                "button:contains('Contact Agent')",
                "a:contains('Contact Agent')",
                ".show-phone",
                "button[data-target='#contactModal']",
                ".listing-details__contact-agent"  # This is identified in the provided HTML
            ]
            
            for selector in show_number_selectors:
                try:
                    # Find and click the button
                    buttons = driver.find_elements(By.CSS_SELECTOR, selector)
                    if len(buttons) > 0:
                        if buttons[0].is_displayed():
                            logger.info(f"Found contact button with selector: {selector}")
                            buttons[0].click()
                            # Wait for contact info to appear
                            time.sleep(3)
                            break
                except NoSuchElementException:
                    continue
                except Exception as e:
                    logger.debug(f"Error clicking button with selector {selector}: {str(e)}")
            
            # Now try to extract contact information which should be visible
            try:
                # Wait for contact modal to appear if it's in a modal
                WebDriverWait(driver, 5).until(
                    EC.visibility_of_element_located((By.CLASS_NAME, "contact-form-container"))
                )
            except:
                logger.debug("Could not wait for contact form container")
            
            # Take a screenshot after clicking the button
            driver.save_screenshot(f"contact_info_{int(time.time())}.png")
            
            # Extract the info from the page
            phone_selectors = [
                ".agent-phone", 
                ".contact-number",
                ".phone-number", 
                ".agent-tel",
                ".listing-contact__phone",
                "[data-agent-phone]",
                ".agent-details__phone"
            ]
            
            email_selectors = [
                ".agent-email",
                ".contact-email",
                ".listing-contact__email",
                "[data-agent-email]",
                ".agent-details__email"
            ]
            
            name_selectors = [
                ".agent-name",
                ".contact-name",
                ".listing-agent-name",
                ".agent-details__name"
            ]
            
            # Try to find phone numbers
            for selector in phone_selectors:
                try:
                    elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    if elements and len(elements) > 0:
                        contact_info['phone'] = elements[0].text.strip()
                        logger.info(f"Found phone: {contact_info['phone']}")
                        break
                except:
                    continue
            
            # Try to find emails
            for selector in email_selectors:
                try:
                    elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    if elements and len(elements) > 0:
                        contact_info['email'] = elements[0].text.strip()
                        logger.info(f"Found email: {contact_info['email']}")
                        break
                except:
                    continue
                    
            # Try to find agent names
            for selector in name_selectors:
                try:
                    elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    if elements and len(elements) > 0:
                        contact_info['name'] = elements[0].text.strip()
                        logger.info(f"Found agent name: {contact_info['name']}")
                        break
                except:
                    continue
            
            # Check if we found any contact info
            if not contact_info:
                # Try to extract directly from the page source
                html = driver.page_source
                soup = BeautifulSoup(html, 'html.parser')
                
                # Look for data attributes that might contain contact info
                contact_div = soup.select_one('#contact-form-container, .contact-form-container')
                if contact_div:
                    for attr in contact_div.attrs:
                        if attr.startswith('data-'):
                            contact_info[attr.replace('data-', '')] = contact_div[attr]
                
                # Check if page source contains phone numbers (simple pattern matching)
                phone_pattern = re.compile(r'(\+\d{1,3}[-\.\s]??)?\(?\d{3}\)?[-\.\s]??\d{3}[-\.\s]??\d{4}')
                email_pattern = re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}')
                
                phone_matches = phone_pattern.findall(html)
                email_matches = email_pattern.findall(html)
                
                if phone_matches and 'phone' not in contact_info:
                    contact_info['possible_phone_numbers'] = phone_matches[:3]  # Limit to first 3 matches
                
                if email_matches and 'email' not in contact_info:
                    contact_info['possible_emails'] = email_matches[:3]  # Limit to first 3 matches
            
        except Exception as e:
            logger.error(f"Error extracting contact information: {str(e)}")
        
        return contact_info

    def _save_html(self, html_content, filename):
        """Save HTML content to a file for debugging"""
        try:
            with open(filename, "w", encoding="utf-8") as f:
                f.write(html_content)
            logger.debug(f"Saved HTML content to {filename}")
        except Exception as e:
            logger.error(f"Error saving HTML content: {str(e)}")
    
    def _parse_listing_page(self, html_content, url):
        """Extract all property information from the HTML content"""
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Initialize the result dictionary
        result = {
            "url": url,
            "extracted_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        
        # Extract basic property information
        result.update(self._extract_basic_info(soup))
        
        # Extract property details
        result.update(self._extract_property_details(soup))
        
        # Extract property features
        result.update(self._extract_features(soup))
        
        # Extract property description
        result.update(self._extract_description(soup))
        
        # Extract images
        result.update(self._extract_images(soup))
        
        # Extract agent information
        result.update(self._extract_agent_info(soup))
        
        # Extract location information
        result.update(self._extract_location_info(soup))
        
        # Extract schema.org structured data
        result.update(self._extract_structured_data(soup))
        
        return result
    
    def _extract_basic_info(self, soup):
        """Extract basic property information such as title, price"""
        result = {}
        
        # Extract title
        title_elem = soup.select_one('.listing-details__title')
        if title_elem:
            result['title'] = title_elem.text.strip()
        
        # Extract price
        price_elem = soup.select_one('.listing-price-display__price')
        if price_elem:
            result['price'] = price_elem.text.strip()
        
        # Extract available from date
        available_from_elem = soup.select_one('.listing-details__badge--available-from span')
        if available_from_elem:
            result['available_from'] = available_from_elem.text.strip()
        
        return result
    
    def _extract_property_details(self, soup):
        """Extract detailed property information"""
        result = {'property_details': {}}
        
        # Extract from property-details section
        detail_items = soup.select('.property-details__list-item')
        for item in detail_items:
            name_elem = item.select_one('.property-details__name-value')
            if name_elem:
                name_text = name_elem.text.strip()
                value_elem = name_elem.select_one('.property-details__value')
                
                if value_elem:
                    key = self._clean_key(name_text.replace(value_elem.text.strip(), '').strip())
                    value = value_elem.text.strip()
                    result['property_details'][key] = value
        
        # Extract main features (bedrooms, bathrooms, etc.)
        main_features = soup.select('.listing-details__main-feature')
        for feature in main_features:
            title = feature.get('title', '')
            if title:
                value = feature.text.strip()
                result[title.lower()] = value
        
        return result
    
    def _extract_features(self, soup):
        """Extract property features"""
        result = {'features': {}}
        
        # Extract from property-features section
        feature_items = soup.select('.property-features__list-item')
        for item in feature_items:
            name_elem = item.select_one('.property-features__name-value')
            if name_elem:
                feature_name = name_elem.contents[0].strip()
                
                # Check if it has a boxed value
                value_elem = item.select_one('.property-features__value--boxed')
                if value_elem:
                    result['features'][feature_name] = value_elem.text.strip()
                # Or if it has a check mark (boolean feature)
                elif item.select_one('.property-features__list-icon-check'):
                    result['features'][feature_name] = True
        
        return result
    
    def _extract_description(self, soup):
        """Extract property description"""
        result = {}
        
        # Extract headline/subtitle
        headline = soup.select_one('.listing-description__headline')
        if headline:
            result['headline'] = headline.text.strip()
        
        # Extract full description
        description = soup.select_one('.listing-description__text')
        if description:
            result['description'] = description.text.strip()
        
        return result
    
    def _extract_images(self, soup):
        """Extract all property images"""
        result = {'images': []}
        
        # Extract from gallery section
        gallery_images = soup.select('.details-page-photogrid__photo')
        for img in gallery_images:
            src = img.get('src')
            if src:
                # Get the high-quality version by replacing _e with _dhd
                hq_src = src.replace('_e.jpg', '_dhd.jpg')
                result['images'].append({
                    'thumbnail': src,
                    'large': hq_src
                })
        
        # If no gallery images found, try banner images
        if not result['images']:
            banner_images = soup.select('.media-container__image')
            for img in banner_images:
                src = img.get('src')
                if src:
                    result['images'].append({
                        'url': src
                    })
        
        return result
    
    def _extract_agent_info(self, soup):
        """Extract agent or agency contact information"""
        result = {'agent': {}}
        
        # Agent info is often loaded dynamically with JavaScript
        # Try to find any visible agent information
        agent_name = soup.select_one('.agent-name, .listing-details__agent-name')
        if agent_name:
            result['agent']['name'] = agent_name.text.strip()
        
        # Try to find agent contact info
        agent_phone = soup.select_one('.agent-phone, .agent-tel')
        if agent_phone:
            result['agent']['phone'] = agent_phone.text.strip()
        
        agent_email = soup.select_one('.agent-email')
        if agent_email:
            result['agent']['email'] = agent_email.text.strip()
        
        # Try to find agency info
        agency = soup.select_one('.agency-name, .agency')
        if agency:
            result['agent']['agency'] = agency.text.strip()
        
        # Check for contact form container which might have hidden agent info in data attributes
        contact_form = soup.select_one('#contact-form-container, .contact-form-container')
        if contact_form:
            for attr in contact_form.attrs:
                if attr.startswith('data-'):
                    if 'agent' in attr or 'contact' in attr:
                        result['agent'][attr] = contact_form[attr]
        
        return result
    
    def _extract_location_info(self, soup):
        """Extract location information"""
        result = {'location': {}}
        
        # Extract from breadcrumbs
        breadcrumbs = soup.select('.breadcrumb__shape-link')
        if breadcrumbs:
            path = []
            for crumb in breadcrumbs:
                path.append(crumb.text.strip())
            result['location']['path'] = path
        
        # Extract address if available
        address = soup.select_one('.listing-details__address')
        if address:
            result['location']['address'] = address.text.strip()
        
        return result
    
    def _extract_structured_data(self, soup):
        """Extract schema.org structured data"""
        result = {'structured_data': {}}
        
        # Look for JSON-LD data
        script_tags = soup.select('script[type="application/ld+json"]')
        for script in script_tags:
            try:
                data = json.loads(script.string)
                # If it's about the property
                if isinstance(data, dict) and data.get('@type') in ['Residence', 'Property', 'Product']:
                    result['structured_data'] = data
            except Exception as e:
                logger.error(f"Error parsing JSON-LD data: {str(e)}")
        
        return result
    
    def _clean_key(self, text):
        """Clean and normalize a key name"""
        # Remove any non-alphanumeric characters except spaces
        text = re.sub(r'[^\w\s]', '', text)
        # Convert to lowercase and replace spaces with underscores
        return text.lower().strip().replace(' ', '_')
    
    def save_to_json(self, data, filename=None):
        """Save the extracted data to a JSON file"""
        if not filename:
            listing_id = data.get('property_details', {}).get('listing_number', 'unknown')
            filename = f"property_{listing_id}.json"
        
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.info(f"Saved property data to {filename}")
            return True
        except Exception as e:
            logger.error(f"Error saving property data: {str(e)}")
            return False

def extract_property_listing(url, use_selenium=True, save_output=True, headless=True):
    """
    Extract information from a property listing URL
    
    Args:
        url (str): The URL of the property listing
        use_selenium (bool): Whether to use Selenium for JavaScript rendering
        save_output (bool): Whether to save the output to a JSON file
        headless (bool): Whether to run Selenium in headless mode
    
    Returns:
        dict: The extracted property information
    """
    extractor = PropertyListingExtractor(use_selenium=use_selenium, headless=headless)
    property_data = extractor.extract_from_url(url)
    
    if property_data and save_output:
        extractor.save_to_json(property_data)
    
    return property_data

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        url = sys.argv[1]
        headless = '--visible' not in sys.argv  # If --visible flag is provided, run with browser visible
    else:
        url = "https://www.privateproperty.co.za/to-rent/western-cape/cape-town/bellville/oakglen/RR4191874"
        headless = True
    
    print(f"Extracting property information from: {url}")
    property_data = extract_property_listing(url, headless=headless)
    
    if property_data:
        print(json.dumps(property_data, indent=2))
        print(f"Total information extracted: {len(property_data)} main fields")
        if 'agent' in property_data:
            print("\nAgent contact information:")
            for key, value in property_data['agent'].items():
                print(f"  {key}: {value}")
    else:
        print("Failed to extract property information")
