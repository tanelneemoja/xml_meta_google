import requests
import xml.etree.ElementTree as ET
import csv
from datetime import datetime, timedelta
import re
import os

# List of URLs to process.
URLS = [
    'https://www.teztour.ee/bestoffers/minprices.ee.html?departureCityId=3746&countryId=158976',
    'https://www.teztour.ee/bestoffers/minprices.ee.html?departureCityId=3746&countryId=1104',
    'https://www.teztour.ee/bestoffers/minprices.ee.html?departureCityId=3746&countryId=7067498',
    'https://www.teztour.ee/bestoffers/minprices.ee.html?departureCityId=3746&countryId=5732',
    # Add your other 4-5 URLs here.
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
    'hotel_id', 'star_rating', 'name', 'description', 'brand',
    'address.addr1', 'address.city', 'address.region', 'address.country',
    'address.postal_code', 'latitude', 'longitude', 'neighborhood[0]',
    'base_price', 'image[0].url', 'url'
]

def sanitize_filename(name):
    """Sanitizes a string to be used as a filename."""
    name = name.lower()
    name = re.sub(r'\s+', '_', name)
    name = re.sub(r'[^a-z0-9_.-]', '', name)
    name = name.strip('_')
    return name

def process_single_url(url):
    """Downloads XML from a URL, processes it, and returns a tuple (country_name, list_of_dictionaries)."""
    print(f"Attempting to download XML from: {url}")
    
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        root = ET.fromstring(response.content)
        print("Download successful.")
    except (requests.exceptions.RequestException, ET.ParseError) as e:
        print(f"Error fetching or parsing XML from {url}: {e}")
        return None, None

    processed_data = []
    country_from_feed = None
    
    today = datetime.now()
    seven_days_later = today + timedelta(days=7)
    today_str = today.strftime('%d.%m.%Y')
    seven_days_later_str = seven_days_later.strftime('%d.%m.%Y')

    for item in root.findall('.//item'):
        star_rating_raw = item.find('stars').text if item.find('stars') is not None else ""
        
        # --- NEW FILTERING LOGIC ---
        # Extract the number from the star rating string
        star_rating = star_rating_raw.split()[0] if star_rating_raw else ""
        
        # Check if the rating is a digit and between 1 and 5
        if not star_rating.isdigit() or not (1 <= int(star_rating) <= 5):
            print(f"Skipping hotel with invalid star rating: {star_rating_raw}")
            continue # Skip to the next item in the XML feed
        
        # --- END OF NEW FILTERING LOGIC ---

        hotel_id = item.find('id').text if item.find('id') is not None else ""
        name = item.find('name').text if item.find('name') is not None else ""
        region = item.find('region').text if item.find('region') is not None else ""
        country = item.find('country').text if item.find('country') is not None else ""
        price = item.find('price').text if item.find('price') is not None else ""
        photo_url = item.find('photo').text if item.find('photo') is not None else ""
        original_url = item.find('url').text if item.find('url') is not None else ""

        if country_from_feed is None and country:
            country_from_feed = country

        coords = country_coords.get(country, {"lat": "", "lon": ""})
        lat = coords.get("lat")
        lon = coords.get("lon")

        updated_url = original_url
        if original_url:
            updated_url = re.sub(r'after/\d{2}\.\d{2}\.\d{4}', f'after/{today_str}', original_url)
            updated_url = re.sub(r'before/\d{2}\.\d{2}\.\d{4}', f'before/{seven_days_later_str}', updated_url)

        new_item = {
            'hotel_id': hotel_id, 'star_rating': star_rating, 'name': name, 'description': name,
            'brand': name, 'address.addr1': region, 'address.city': region, 'address.region': region,
            'address.country': country, 'address.postal_code': '00000', 'latitude': lat,
            'longitude': lon, 'neighborhood[0]': region, 'base_price': price,
            'image[0].url': photo_url, 'url': updated_url
        }
        processed_data.append(new_item)
    
    print(f"Found {len(processed_data)} valid hotels in the XML feed.")
    return country_from_feed, processed_data

def write_to_csv(data, filename):
    """Writes a list of dictionaries to a CSV file."""
    if not data:
        print(f"No data to write to {filename}.")
        return

    try:
        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=HEADERS)
            writer.writeheader()
            writer.writerows(data)
        print(f"Successfully created {filename} with {len(data)} rows.")
    except Exception as e:
        print(f"Error writing to CSV file {filename}: {e}")

if __name__ == "__main__":
    for i, url in enumerate(URLS):
        print(f"\n--- Starting processing for URL {i+1} ---")
        country_name, processed_items = process_single_url(url)
        
        if processed_items:
            if country_name:
                filename = f"{sanitize_filename(country_name)}.csv"
                print(f"Generated filename: {filename}")
                write_to_csv(processed_items, filename)
            else:
                filename = f"catalogue_unknown_country_{i+1}.csv"
                print(f"Warning: Could not determine country name. Generated filename: {filename}")
                write_to_csv(processed_items, filename)
        else:
            print("No items to process from this URL.")
            
    print("\n--- Processing finished ---")
