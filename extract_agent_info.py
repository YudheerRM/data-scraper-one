import sys
import time
import json
import logging
import re
from bs4 import BeautifulSoup  # Add BeautifulSoup import
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
        logging.FileHandler("agent_extraction.log")
    ]
)
logger = logging.getLogger()

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
        driver.save_screenshot("before_click.png")
        
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
            
            # Take screenshot before clicking
            driver.save_screenshot("found_button.png")
            
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
                        driver.save_screenshot("found_button_by_class.png")
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
                        driver.save_screenshot("found_button_by_svg.png")
                        button.click()
                        button_clicked = True
                        logger.info("Clicked show contact button by SVG icon and text")
                        time.sleep(3)  # Wait for popup to appear
                        break
            except Exception as e:
                logger.warning(f"Could not find button by SVG icon: {str(e)}")
        
        # Take screenshot after clicking
        driver.save_screenshot("after_click.png")
        
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
            
            # Take a screenshot to see what appeared
            driver.save_screenshot("after_button_click.png")
            
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
        
        # Save the entire page HTML for analysis
        listing_id = url.split('/')[-1]
        with open(f"contact_page_{listing_id}_after_click.html", "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        
        return contact_info
        
    except Exception as e:
        logger.error(f"Error during extraction: {str(e)}")
        return {"error": str(e), "url": url}
        
    finally:
        if driver:
            driver.quit()

if __name__ == "__main__":
    if len(sys.argv) > 1:
        url = sys.argv[1]
        headless = '--visible' not in sys.argv
    else:
        url = "https://www.privateproperty.co.za/to-rent/western-cape/cape-town/bellville/oakglen/RR4191874"
        headless = False  # Default to visible browser for this tool
    
    print(f"Extracting agent contact information from: {url}")
    print(f"Browser {'hidden' if headless else 'visible'}")
    
    contact_info = extract_agent_contact_info(url, headless=headless)
    
    # Save to file
    listing_id = url.split('/')[-1]
    output_file = f"agent_info_{listing_id}.json"
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(contact_info, f, ensure_ascii=False, indent=2)
    
    print(f"Contact information saved to: {output_file}")
    
    # Print info to console
    print("\nExtracted Information:")
    for key, value in contact_info.items():
        if key not in ["container_html", "container_text", "popup_text"]:
            print(f"  {key}: {value}")
