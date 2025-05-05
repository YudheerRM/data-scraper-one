# Property Listing Scraper

A Python scraper to extract property listings from PrivateProperty.co.za.

## Setup

1. Install the required packages:
   ```
   pip install -r requirements.txt
   ```

2. Run the scraper:
   ```
   python property_scraper.py
   ```

## Configuration

You can modify these parameters in the script:
- `BASE_URL`: The starting URL to scrape
- `max_pages`: Maximum number of pages to scrape (set to `None` for unlimited)
- `delay_min` and `delay_max`: Min and max delay between requests (in seconds)

## Output

The scraper will generate:
- `property_listings.csv`: CSV file containing all the scraped property data
- `scraper.log`: Log file with information about the scraping process

## Ethical Considerations

- This scraper is for educational purposes only
- Always respect the website's `robots.txt` file and terms of service
- Use reasonable delays between requests to avoid overloading the server
- Do not use the extracted data for commercial purposes without permission
