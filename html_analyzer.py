import re
from bs4 import BeautifulSoup
import logging

def analyze_html_structure(html_content):
    """
    Analyzes a webpage's HTML structure to detect potential property listing elements
    and returns suggestions for CSS selectors.
    
    Args:
        html_content (str): The HTML content to analyze
        
    Returns:
        dict: A dictionary containing potential selectors and their frequencies
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    
    logging.info("Analyzing HTML structure to find potential property listing patterns...")
    
    # Look for common property-related classes
    property_related_patterns = [
        r'.*property.*', 
        r'.*listing.*',
        r'.*result.*',
        r'.*featured.*', 
        r'.*card.*', 
        r'.*item.*',
        r'.*house.*',
        r'.*apartment.*',
        r'.*estate.*',
        r'.*real-estate.*'
    ]
    
    # Elements that often contain multiple listings
    container_patterns = [
        r'.*container.*',
        r'.*results.*',
        r'.*listings.*',
        r'.*properties.*',
        r'.*grid.*',
        r'.*list.*'
    ]
    
    # Find potential container elements
    containers = {}
    for tag in soup.find_all(class_=True):
        class_str = ' '.join(tag.get('class', []))
        for pattern in container_patterns:
            if re.match(pattern, class_str, re.IGNORECASE):
                selector = f".{tag.get('class')[0]}"
                if selector in containers:
                    containers[selector] += 1
                else:
                    containers[selector] = 1
    
    # Find potential property elements
    property_elements = {}
    for tag in soup.find_all(class_=True):
        class_str = ' '.join(tag.get('class', []))
        for pattern in property_related_patterns:
            if re.match(pattern, class_str, re.IGNORECASE):
                child_count = len(tag.find_all())
                # Property elements typically have multiple child elements
                if child_count > 5:  
                    selector = f".{tag.get('class')[0]}"
                    if selector in property_elements:
                        property_elements[selector] += 1
                    else:
                        property_elements[selector] = 1
    
    # Check for repeated similar structures (a strong indicator of listings)
    repeated_structures = find_repeated_structures(soup)
    
    # Look for schema.org markup which often indicates property listings
    schema_elements = {}
    for tag in soup.find_all(itemtype=True):
        itemtype = tag.get('itemtype')
        if 'schema.org' in itemtype and ('Product' in itemtype or 'Offer' in itemtype or 'Residence' in itemtype):
            selector = f"[itemtype='{itemtype}']"
            if selector in schema_elements:
                schema_elements[selector] += 1
            else:
                schema_elements[selector] = 1
    
    # Combine and rank the results
    all_selectors = {
        'property_elements': property_elements,
        'containers': containers,
        'repeated_structures': repeated_structures,
        'schema_elements': schema_elements
    }
    
    # Get the top candidates
    top_candidates = get_top_candidates(all_selectors)
    
    return top_candidates

def find_repeated_structures(soup):
    """Find elements that appear multiple times with similar structure"""
    tag_counts = {}
    
    # Count how many times each tag appears with its class
    for tag in soup.find_all(class_=True):
        if len(tag.find_all()) > 3:  # Only consider tags with children
            key = f"{tag.name}.{tag.get('class')[0]}"
            if key in tag_counts:
                tag_counts[key] += 1
            else:
                tag_counts[key] = 1
    
    # Filter to tags that appear multiple times
    repeated = {k: v for k, v in tag_counts.items() if v > 2}
    return repeated

def get_top_candidates(selector_groups):
    """Get the most likely selectors for property listings"""
    top_candidates = []
    
    # First priority: schema.org elements since they're explicitly marked
    for selector, count in selector_groups['schema_elements'].items():
        if count > 1:
            top_candidates.append({
                'selector': selector,
                'count': count,
                'confidence': 'high',
                'type': 'schema.org element'
            })
    
    # Second priority: property elements with high counts
    sorted_property = sorted(selector_groups['property_elements'].items(), 
                            key=lambda x: x[1], reverse=True)
    for selector, count in sorted_property[:5]:  # Top 5 property selectors
        if count > 1:
            top_candidates.append({
                'selector': selector,
                'count': count,
                'confidence': 'medium' if count > 5 else 'low',
                'type': 'property element'
            })
    
    # Third priority: repeated structures
    sorted_repeated = sorted(selector_groups['repeated_structures'].items(), 
                            key=lambda x: x[1], reverse=True)
    for selector, count in sorted_repeated[:5]:  # Top 5 repeated structures
        if count > 2:
            top_candidates.append({
                'selector': selector,
                'count': count,
                'confidence': 'medium' if count > 5 else 'low',
                'type': 'repeated structure'
            })
    
    return top_candidates

def suggest_selectors(html_file_path):
    """
    Analyze an HTML file and suggest CSS selectors for property listings
    
    Args:
        html_file_path (str): Path to the HTML file
        
    Returns:
        list: Suggested CSS selectors
    """
    try:
        with open(html_file_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
        
        candidates = analyze_html_structure(html_content)
        
        # Format the suggestions
        print("\n=== Suggested Property Listing Selectors ===")
        for candidate in candidates:
            confidence_indicator = {
                'high': '✓✓✓',
                'medium': '✓✓',
                'low': '✓'
            }.get(candidate['confidence'], '')
            
            print(f"{confidence_indicator} {candidate['selector']} - Found {candidate['count']} times ({candidate['type']})")
        
        # Return just the selectors for programmatic use
        return [candidate['selector'] for candidate in candidates]
        
    except Exception as e:
        logging.error(f"Error analyzing HTML file: {str(e)}")
        return []

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        html_file = sys.argv[1]
        suggest_selectors(html_file)
    else:
        print("Usage: python html_analyzer.py path/to/html_file.html")
