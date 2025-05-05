import os
import re
import json
import logging
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

def analyze_html(html_content, output_file=None):
    """Analyze HTML content for potential property patterns"""
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Common property container classes/patterns
    common_patterns = [
        r'property', r'listing', r'real-?estate', r'home', r'house', r'apartment',
        r'result', r'card', r'item', r'product', r'entry'
    ]
    
    # Find all div elements with classes
    potential_containers = []
    divs_with_class = soup.find_all('div', class_=True)
    
    for div in divs_with_class:
        class_names = ' '.join(div.attrs.get('class', []))
        for pattern in common_patterns:
            if re.search(pattern, class_names, re.IGNORECASE):
                children_count = len(div.find_all())
                if children_count > 5:  # Property cards typically have several elements
                    container_info = {
                        'selector': f"div.{'.'.join(div.attrs.get('class', []))}",
                        'children_count': children_count,
                        'text_preview': div.text[:100].strip().replace('\n', ' ')
                    }
                    potential_containers.append(container_info)
    
    # Sort by number of children (more complex elements might be property cards)
    potential_containers.sort(key=lambda x: x['children_count'], reverse=True)
    
    # Save or display results
    if output_file:
        with open(output_file, 'w') as f:
            json.dump(potential_containers[:10], f, indent=2)
    
    logger.info(f"Found {len(potential_containers)} potential property containers")
    for i, container in enumerate(potential_containers[:5]):
        logger.info(f"Potential container {i+1}: {container['selector']} - {container['children_count']} children")
    
    return potential_containers

def find_pagination_patterns(html_content):
    """Find potential pagination elements in HTML"""
    soup = BeautifulSoup(html_content, 'html.parser')
    
    pagination_candidates = []
    
    # Look for common pagination patterns
    pagination_elements = soup.select('.pagination, .pager, nav ul.pages, .page-numbers, .paging')
    
    for element in pagination_elements:
        pagination_candidates.append({
            'selector': get_css_selector(element),
            'html': str(element)[:200]
        })
    
    # Look for anchor tags with page numbers
    number_links = soup.select('a[href*="page="], a[href*="/page/"]')
    if number_links:
        parent_containers = set()
        for link in number_links:
            parent = link.parent
            for i in range(3):  # Check up to 3 levels up
                if parent and parent.name:
                    parent_containers.add(parent)
                    parent = parent.parent
        
        for container in parent_containers:
            pagination_candidates.append({
                'selector': get_css_selector(container),
                'html': str(container)[:200]
            })
    
    return pagination_candidates

def get_css_selector(element):
    """Generate a CSS selector for a BeautifulSoup element"""
    if not element or not element.name:
        return "Unknown"
        
    selector = element.name
    
    if element.get('id'):
        return f"{selector}#{element['id']}"
    
    if element.get('class'):
        classes = '.'.join(element['class'])
        return f"{selector}.{classes}"
    
    return selector

def detect_anti_bot_measures(html_content):
    """Detect potential anti-bot measures in response content"""
    soup = BeautifulSoup(html_content, 'html.parser')
    
    issues = []
    
    # Check for CAPTCHA
    captcha_terms = ['captcha', 'recaptcha', 'hcaptcha', 'security check']
    for term in captcha_terms:
        if term.lower() in html_content.lower():
            issues.append(f"Potential CAPTCHA detected ({term})")
    
    # Check for common robot detection scripts
    bot_scripts = ['botdetect', 'bot-detect', 'detectbot', 'cloudflare', 'distil']
    scripts = soup.find_all('script')
    for script in scripts:
        src = script.get('src', '')
        content = script.text.lower()
        for term in bot_scripts:
            if term in src.lower() or term in content:
                issues.append(f"Bot detection script found ({term})")
    
    # Check for common error messages
    error_terms = ['access denied', 'blocked', '403 forbidden', 'too many requests']
    for term in error_terms:
        if term.lower() in html_content.lower():
            issues.append(f"Access restriction message found ({term})")
    
    return issues

def inspect_website(html_file_path):
    """Main function to analyze a saved HTML file"""
    if not os.path.exists(html_file_path):
        return {"error": "HTML file not found"}
    
    with open(html_file_path, 'r', encoding='utf-8') as f:
        html_content = f.read()
    
    results = {
        "property_containers": analyze_html(html_content),
        "pagination": find_pagination_patterns(html_content),
        "anti_bot_measures": detect_anti_bot_measures(html_content)
    }
    
    return results
