import requests
import xml.etree.ElementTree as ET
import csv
from datetime import datetime, timedelta
import re
import os
import io

# List of URLs to process.
URLS = [
    {'country_name': 'Bulgaaria', 'url': 'https://www.teztour.ee/bestoffers/minprices.ee.html?departureCityId=3746&countryId=158976'},
    {'country_name': 'Тürgi', 'url': 'https://www.teztour.ee/bestoffers/minprices.ee.html?departureCityId=3746&countryId=1104'},
    {'country_name': 'Kreeka', 'url': 'https://www.teztour.ee/bestoffers/minprices.ee.html?departureCityId=3746&countryId=7067498'},
    {'country_name': 'Еgiptus', 'url': 'https://www.teztour.ee/bestoffers/minprices.ee.html?departureCityId=3746&countryId=5732'},
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
}

# The meta headings for the final CSV file
CSV_HEADERS = [
    'hotel_id',
    'star_rating', 'name', 'description', 'brand',
    'address.addr1', 'address.city', 'address.region', 'address.country',
    'address.postal_code', 'latitude', 'longitude', 'neighborhood[0]',
    'base_price', 'image[0].url', 'url'
]

def sanitize_string(s):
    """
    Sanitizes a string to contain only standard printable characters,
    preventing CSV/XML parsing errors.
    """
    if not s:
        return ""
    
    s = s.strip()
    s = s.replace('\n', ' ').replace('\r', ' ')
    s = re.sub(r'[^\w\s\-\.\,\/\&\?\!\#\(\)\%\:äöüõÄÖÜÕ]', '', s)
    
    return s

def sanitize_filename(name, extension):
    """Sanitizes a string to be used as a filename."""
    name = name.lower()
    name = re.sub(r'\s+', '_', name)
    name = re.sub(r'[^a-z0-9_.-]', '', name)
    name = name.strip('_')
    if name == 'kreeka':
        return f'greece{extension}'
    return f"{name}{extension}"

def fetch_hotel_ids_from_sheet(sheet_url):
    """Fetches hotel IDs from a public Google Sheet converted to a CSV URL."""
    try:
        response = requests.get(sheet_url)
        response.raise_for_status()
        csv_data = response.text
        
        # Use io.StringIO to treat the string as a file
        csv_file = io.StringIO(csv_data)
        reader = csv.reader(csv_file)
        
        # Skip header and get the hotel IDs from the first column
        next(reader, None)  # Skip header row
        hotel_ids = {row[0].strip() for row in reader if row}
        
        print(f"Successfully fetched {len(hotel_ids)} hotel IDs from the Google Sheet.")
        return hotel_ids
    except requests.exceptions.RequestException as e:
        print(f"Error fetching Google Sheet data: {e}")
        return set()
    except Exception as e:
        print(f"Error parsing Google Sheet CSV: {e}")
        return set()

def process_single_url(url_info, turkey_hotels_from_sheet):
    """Downloads XML from a URL, processes it, and returns a tuple (country_name, list_of_dictionaries)."""
    print(f"Attempting to download XML for {url_info['country_name']} from: {url_info['url']}")
    
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
    
    try:
        response = requests.get(url_info['url'], headers=headers)
        response.raise_for_status()
        root = ET.fromstring(response.content)
        print("Download successful.")
    except (requests.exceptions.RequestException, ET.ParseError) as e:
        print(f"Error fetching or parsing XML from {url_info['url']}: {e}")
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

        price_text = item.find('price').text.strip() if item.find('price') is not None and item.find('price').text else ""
        photo_url = item.find('photo').text.strip() if item.find('photo') is not None and item.find('photo').text else ""
        original_url = item.find('url').text.strip() if item.find('url') is not None and item.find('url').text else ""

        if ',' in photo_url:
            print(f"Warning: Skipping hotel {hotel_id_clean} due to a comma in the image URL.")
            continue

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
        
        # Extract currency from price string
        currency = re.search(r'[A-Z]{3}', price_text)
        currency_code = currency.group(0) if currency else 'EUR'
        price = re.sub(r'[^\d.]', '', price_text) + ' ' + currency_code

        # --- NEW LOGIC: Check for hotel ID and set country accordingly ---
        final_country = country_latin
        if country_xml == "Тürgi":
            if hotel_id in turkey_hotels_from_sheet:
                final_country = "Turkey"
            else:
                final_country = "Türgi"
        
        new_item = {
            'hotel_id': sanitize_string(hotel_id),
            'star_rating': sanitize_string(star_rating),
            'name': sanitize_string(name),
            'description': sanitize_string(name),
            'brand': sanitize_string(name),
            'address.addr1': sanitize_string(region),
            'address.city': sanitize_string(region),
            'address.region': sanitize_string(region),
            'address.country': sanitize_string(final_country),
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
    """Writes a list of dictionaries to a CSV file."""
    if not data:
        print(f"No data to write to {filename}.")
        return

    try:
        with open(filename, 'w', newline='', encoding='utf-8-sig') as csvfile:
            writer = csv.writer(csvfile, delimiter=',')
            writer.writerow(CSV_HEADERS)
            for item in data:
                row = [item.get(header, '') for header in CSV_HEADERS]
                writer.writerow(row)
        print(f"Successfully created CSV file: {filename} with {len(data)} rows.")
    except Exception as e:
        print(f"Error writing to CSV file {filename}: {e}")

def write_to_xml(data, filename):
    """
    Writes a list of dictionaries to a new XML file with the provided Meta format,
    while keeping the original field names.
    """
    if not data:
        print(f"No data to write to {filename}.")
        return

    try:
        # Create the RSS and Channel structure
        rss = ET.Element('rss', {
            'xmlns:g': 'http://base.google.com/ns/1.0',
            'version': '2.0'
        })
        channel = ET.SubElement(rss, 'channel')
        
        # Add static channel info
        ET.SubElement(channel, 'title').text = 'TezTour Hotel Catalog'
        ET.SubElement(channel, 'link').text = 'https://www.teztour.ee'
        ET.SubElement(channel, 'description').text = 'Hotel catalog for TezTour destinations'

        # Map and add each item to the channel
        for item_data in data:
            item = ET.SubElement(channel, 'item')
            
            # Map internal dictionary keys to desired XML tag names
            field_map = {
                'hotel_id': 'hotel_id',
                'star_rating': 'star_rating',
                'name': 'name',
                'description': 'description',
                'brand': 'brand',
                'address.addr1': 'address_addr1',
                'address.city': 'address_city',
                'address.region': 'address_region',
                'address.country': 'address_country',
                'address.postal_code': 'address_postal_code',
                'latitude': 'latitude',
                'longitude': 'longitude',
                'neighborhood[0]': 'neighborhood',
                'base_price': 'price',
                'image[0].url': 'image_link',
                'url': 'link'
            }

            for key, tag_name in field_map.items():
                element = ET.SubElement(item, tag_name)
                element.text = str(item_data.get(key, ''))
        
        # Write the tree to a file with a clean format
        tree = ET.ElementTree(rss)
        tree.write(filename, encoding='utf-8', xml_declaration=True)
        
        print(f"Successfully created XML file: {filename} with {len(data)} hotels in new format.")
    except Exception as e:
        print(f"Error writing to XML file {filename}: {e}")

if __name__ == "__main__":
    # URL for the Google Sheet's CSV export
    GOOGLE_SHEET_URL = "https://docs.google.com/spreadsheets/d/1VTHXw3LJqOt-H1T3wSVcMmyNxPnX6Ihidx8ptHdfL_0/export?format=csv&gid=930911573"
    turkey_hotels_from_sheet = fetch_hotel_ids_from_sheet(GOOGLE_SHEET_URL)

    for url_info in URLS:
        country_name_xml, processed_items = process_single_url(url_info, turkey_hotels_from_sheet)
        
        if processed_items:
            country_name_latin = country_name_mapping.get(country_name_xml, country_name_xml)
            if country_name_latin:
                csv_filename = sanitize_filename(country_name_latin, '.csv')
                xml_filename = sanitize_filename(country_name_latin, '.xml')
                
                print(f"Processing for {country_name_latin}...")
                write_to_csv(processed_items, csv_filename)
                write_to_xml(processed_items, xml_filename)
            else:
                print("Warning: Could not determine country name from feed.")
        else:
            print(f"No items to process from {url_info['country_name']} URL.")
            
    print("\n--- Processing finished ---")
