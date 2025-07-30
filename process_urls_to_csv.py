import requests
import xml.etree.ElementTree as ET
import csv
from datetime import datetime, timedelta
import re

# List of URLs to process. You can add more URLs here.
URLS = [
    'https://www.teztour.ee/bestoffers/minprices.ee.html?departureCityId=3746&countryId=158976',
    # Add your other 4-5 URLs here
    # 'https://example.com/another_feed.xml',
]

# Static data for country coordinates, using Estonian names
country_coords = {
    "Bulgaaria": {"lat": 42.7339, "lon": 25.4858},
    "Türgi": {"lat": 38.96, "lon": 35.25},
    "Kreeka": {"lat": 39.00, "lon": 22.00},
    "Rhodos": {"lat": 39.00, "lon": 22.00},
    "Kreeta": {"lat": 39.00, "lon": 22.00},
    "Egiptus": {"lat": 25.00, "lon": 31.00},
}

# The meta headings for the final CSV file
HEADERS = [
    'hotel_id',
    'star_rating',
    'name',
    'description',
    'brand',
    'address.addr1',
    'address.city',
    'address.region',
    'address.country',
    'address.postal_code',
    'latitude',
    'longitude',
    'neighborhood[0]',
    'base_price',
    'image[0].url',
    'url'
]

def process_single_url(url):
    """Downloads XML from a URL, processes it, and returns a list of dictionaries."""
    try:
        response = requests.get(url)
        response.raise_for_status()  # Raise an HTTPError for bad responses (4xx or 5xx)
        root = ET.fromstring(response.content)
    except (requests.exceptions.RequestException, ET.ParseError) as e:
        print(f"Error processing URL {url}: {e}")
        return None

    processed_data = []

    # Define dynamic dates in the correct 'dd.mm.yyyy' format
    today = datetime.now()
    seven_days_later = today + timedelta(days=7)
    
    today_str = today.strftime('%d.%m.%Y')
    seven_days_later_str = seven_days_later.strftime('%d.%m.%Y')

    for item in root.findall('item'):
        # Extract and clean data
        hotel_id = item.find('id').text if item.find('id') is not None else ""
        star_rating = item.find('stars').text.split()[0] if item.find('stars') is not None else ""
        name = item.find('name').text if item.find('name') is not None else ""
        region = item.find('region').text if item.find('region') is not None else ""
        country = item.find('country').text if item.find('country') is not None else ""
        price = item.find('price').text if item.find('price') is not None else ""
        photo_url = item.find('photo').text if item.find('photo') is not None else ""
        original_url = item.find('url').text if item.find('url') is not None else ""

        # Get coordinates from lookup, defaulting to empty if not found
        coords = country_coords.get(country, {"lat": "", "lon": ""})
        lat = coords.get("lat")
        lon = coords.get("lon")

        # Dynamically update the URL with the correct date format
        updated_url = original_url
        if original_url:
            updated_url = re.sub(r'after/\d{2}\.\d{2}\.\d{4}', f'after/{today_str}', original_url)
            updated_url = re.sub(r'before/\d{2}\.\d{2}\.\d{4}', f'before/{seven_days_later_str}', updated_url)

        # Create a dictionary for the new catalogue item
        new_item = {
            'hotel_id': hotel_id,
            'star_rating': star_rating,
            'name': name,
            'description': name,
            'brand': name,
            'address.addr1': region,
            'address.city': region,
            'address.region': region,
            'address.country': country,
            'address.postal_code': '00000',
            'latitude': lat,
            'longitude': lon,
            'neighborhood[0]': region,
            'base_price': price,
            'image[0].url': photo_url,
            'url': updated_url
        }
        processed_data.append(new_item)

    return processed_data

def write_to_csv(data, filename):
    """Writes a list of dictionaries to a CSV file."""
    if not data:
        print(f"No data to write for {filename}.")
        return

    with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=HEADERS)
        writer.writeheader()
        writer.writerows(data)
    print(f"Successfully created {filename} with {len(data)} rows.")

if __name__ == "__main__":
    for i, url in enumerate(URLS):
        print(f"Processing URL {i+1}/{len(URLS)}: {url}")
        processed_items = process_single_url(url)
        if processed_items:
            # Create a unique filename for each URL
            filename = f"catalogue_{i+1}.csv"
            write_to_csv(processed_items, filename)
