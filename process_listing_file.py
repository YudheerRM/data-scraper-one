import json
import sys
import os
from extract_listing import PropertyListingExtractor

def process_listing_html_file(html_file_path):
    """
    Process an HTML file containing a property listing
    
    Args:
        html_file_path (str): Path to the HTML file
    
    Returns:
        dict: The extracted property information
    """
    try:
        listing_id = os.path.basename(html_file_path).split('_')[1].split('.')[0]
        
        # Read HTML file
        with open(html_file_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
        
        # Create extractor and parse the HTML
        extractor = PropertyListingExtractor(use_selenium=False)
        url = f"https://www.privateproperty.co.za/to-rent/western-cape/cape-town/bellville/oakglen/{listing_id}"
        
        # Use internal parse method since we already have the HTML
        property_data = extractor._parse_listing_page(html_content, url)
        
        # Add a note about missing contact info
        if 'agent' not in property_data:
            property_data['agent'] = {}
        property_data['agent']['note'] = "Contact information may be incomplete as it requires browser interaction to reveal hidden contact details"
        
        # Save to JSON
        output_file = f"property_{listing_id}.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(property_data, f, ensure_ascii=False, indent=2)
        
        print(f"Successfully extracted property information to {output_file}")
        print(f"NOTE: To get complete contact information, use extract_listing.py with --visible flag")
        return property_data
        
    except Exception as e:
        print(f"Error processing HTML file: {e}")
        return None

if __name__ == "__main__":
    if len(sys.argv) > 1:
        html_file = sys.argv[1]
    else:
        html_file = "listing_RR4191874.html"
    
    if not os.path.exists(html_file):
        print(f"Error: File {html_file} not found")
        sys.exit(1)
    
    print(f"Processing property listing from file: {html_file}")
    property_data = process_listing_html_file(html_file)
    
    if property_data:
        print("\nExtracted property information:")
        for key in property_data:
            if key != 'structured_data':  # Skip the large structured data
                print(f"{key}: {property_data[key]}")
