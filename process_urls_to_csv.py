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
]

# Static data for country coordinates, using the exact names found in the XML
country_coords = {
    "Bulgaaria": {"lat": 42.7339, "lon": 25.4858},
    "Тürgi": {"lat": 38.96, "lon": 35.25}, # Cyrillic T
    "Kreeka": {"lat": 39.00, "lon": 22.00},
    "Rhodos": {"lat": 39.00, "lon": 22.00},
    "Kreeta": {"lat": 39.00, "lon": 22.00},
    "Еgiptus": {"lat": 25.00, "lon": 31.00}, # Cyrillic E
}

# Mapping to convert Cyrillic country names to Latin
country_name_mapping = {
    "Тürgi": "Türgi",
    "Еgiptus": "Egiptus",
    # Add other mappings if needed
}

# The meta headings for the final CSV file
HEADERS = [
    'hotel_id',
    'star_rating', 'name', 'description', 'brand',
    'address.addr1', 'address.city', 'address.region', 'address.country',
    'address.postal_code', 'latitude', 'longitude', 'neighborhood[0]',
    'base_price', 'image[0].url', 'url'
]

def sanitize_string(s):
    """Sanitizes a string to contain only printable characters."""
    if not s:
        return ""
    # Ensure no extra newlines or quotes that would break the CSV
    return s.strip().replace('\n', ' ').replace('\r', ' ')

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
        star_rating = star_rating_raw.split()[0] if star_rating_raw else ""
        
        if not star_rating.isdigit() or not (1 <= int(star_rating) <= 5):
            print(f"Skipping hotel with invalid star rating: {star_rating_raw}")
            continue

        hotel_id_raw = item.find('id').text.strip() if item.find('id') is not None and item.find('id').text else ""
        hotel_id_clean = ''.join(c for c in hotel_id_raw if c.isdigit())
        
        if not hotel_id_clean:
            print(f"Warning: Skipping an item due to missing hotel ID.")
            continue

        name = item.find('name').text.strip() if item.find('name') is not None and item.find('name').text else ""
        region = item.find('region').text.strip() if item.find('region') is not None and item.find('region').text else ""
        country_xml = item.find('country').text.strip() if item.find('country') is not None and item.find('country').text else ""

        price = item.find('price').text.strip() if item.find('price') is not None and item.find('price').text else ""
        photo_url = item.find('photo').text.strip() if item.find('photo') is not None and item.find('photo').text else ""
        original_url = item.find('url').text.strip() if item.find('url') is not None and item.find('url').text else ""

        if country_from_feed is None and country_xml:
            country_from_feed = country_xml

        coords = country_coords.get(country_xml, {"lat": "", "lon": ""})
        lat = coords.get("lat")
        lon = coords.get("lon")
        
        if not lat or not lon:
            print(f"Warning: No coordinates found for country '{country_xml}'.")
            
        country_latin = country_name_mapping.get(country_xml, country_xml)
        
        hotel_id = hotel_id_clean
        updated_url = original_url
        if original_url:
            updated_url = re.sub(r'after/\d{2}\.\d{2}\.\d{4}', f'after/{today_str}', original_url)
            updated_url = re.sub(r'before/\d{2}\.\d{2}\.\d{4}', f'before/{seven_days_later_str}', updated_url)

        new_item = {
            'hotel_id': sanitize_string(hotel_id),
            'star_rating': sanitize_string(star_rating),
            'name': sanitize_string(name),
            'description': sanitize_string(name),
            'brand': sanitize_string(name),
            'address.addr1': sanitize_string(region),
            'address.city': sanitize_string(region),
            'address.region': sanitize_string(region),
            'address.country': sanitize_string(country_latin),
            'address.postal_code': sanitize_string('00000'),
            'latitude': lat,
            'longitude': lon,
            'neighborhood[0]': sanitize_string(region),
            'base_price': sanitize_string(price),
            'image[0].url': sanitize_string(photo_url),
            'url': sanitize_string(updated_url)
        }
        processed_data.append(new_item)
    
    print(f"Found {len(processed_data)} valid hotels in the XML feed.")
    return country_from_feed, processed_data

def write_to_csv(data, filename):
    """Writes a list of dictionaries to a CSV file using a robust method."""
    if not data:
        print(f"No data to write to {filename}.")
        return

    try:
        with open(filename, 'w', newline='', encoding='utf-8-sig') as csvfile:
            # Use the csv.writer with a comma delimiter
            writer = csv.writer(csvfile, delimiter=',')
            # Write the header row
            writer.writerow(HEADERS)
            # Write the data rows
            for item in data:
                row = [item.get(header, '') for header in HEADERS]
                writer.writerow(row)
        print(f"Successfully created {filename} with {len(data)} rows.")
    except Exception as e:
        print(f"Error writing to CSV file {filename}: {e}")

if __name__ == "__main__":
    for i, url in enumerate(URLS):
        print(f"\n--- Starting processing for URL {i+1} ---")
        country_name_xml, processed_items = process_single_url(url)
        
        if processed_items:
            country_name_latin = country_name_mapping.get(country_name_xml, country_name_xml)
            if country_name_latin:
                filename = f"{sanitize_filename(country_name_latin)}.csv"
                print(f"Generated filename: {filename}")
                write_to_csv(processed_items, filename)
            else:
                filename = f"catalogue_unknown_country_{i+1}.csv"
                print(f"Warning: Could not determine country name. Generated filename: {filename}")
                write_to_csv(processed_items, filename)
        else:
            print("No items to process from this URL.")
            
    print("\n--- Processing finished ---")
