import os
import json
from bs4 import BeautifulSoup
from html_analyzer import suggest_selectors
from improved_scraper import ImprovedPropertyScraper

def test_with_saved_html(html_file, base_url="https://www.privateproperty.co.za"):
    """
    Test the scraper with a saved HTML file
    
    Args:
        html_file (str): Path to the HTML file
        base_url (str): The base URL to use for the scraper
    """
    print(f"Testing scraper with saved HTML file: {html_file}")
    
    # First, analyze the HTML and suggest selectors
    suggested_selectors = suggest_selectors(html_file)
    
    # Create a scraper instance
    scraper = ImprovedPropertyScraper(base_url)
    
    # If we have suggestions, add them to the scraper's selectors
    if suggested_selectors:
        scraper.property_selectors = suggested_selectors + scraper.property_selectors
        print(f"Added {len(suggested_selectors)} suggested selectors to the scraper")
    
    # Parse the HTML file
    with open(html_file, 'r', encoding='utf-8') as f:
        html_content = f.read()
    
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Try each selector
    properties_found = False
    for selector in scraper.property_selectors:
        try:
            property_elements = soup.select(selector)
            if property_elements:
                print(f"Found {len(property_elements)} properties with selector: {selector}")
                scraper.extract_properties(property_elements)
                properties_found = True
                break
        except Exception as e:
            print(f"Error with selector {selector}: {str(e)}")
    
    if not properties_found:
        print("No properties found with any selector")
        return False
    
    # Save the extracted properties
    if scraper.properties:
        output_file = "test_properties.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(scraper.properties, f, ensure_ascii=False, indent=2)
        print(f"Saved {len(scraper.properties)} properties to {output_file}")
        return True
    else:
        print("No properties were extracted")
        return False

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        html_file = sys.argv[1]
        test_with_saved_html(html_file)
    else:
        # Try to find the most recent selenium HTML file
        files = [f for f in os.listdir('.') if f.startswith('page_') and f.endswith('_selenium.html')]
        if files:
            latest_file = max(files)
            print(f"Found latest Selenium HTML file: {latest_file}")
            test_with_saved_html(latest_file)
        else:
            print("Usage: python test_scraper.py path/to/html_file.html")
            print("No Selenium HTML files found in the current directory")
