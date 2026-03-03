import csv
import os

# Smart Fit Recommendation Module
# Loads data from ansi_fits.csv (User provided User Data)

# Get the directory of the current file
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(BASE_DIR, 'ansi_fits.csv')

def load_fits_from_csv():
    """
    Load fits from CSV file.
    Expected columns: type, ansi, ANSI_Standard_Name, shaft, hole, Engineering_Purpose
    """
    database = []
    if not os.path.exists(CSV_PATH):
        print(f"Warning: CSV file not found at {CSV_PATH}")
        return []
        
    try:
        with open(CSV_PATH, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Map CSV columns to internal schema
                # CSV: type, ansi, ANSI_Standard_Name, shaft, hole, Engineering_Purpose
                # Internal: type, function, shaft, hole, ansi, note
                
                # Use function column as function
                # Use note column as note
                
                item = {
                    'type': row.get('type', ''),
                    'function': row.get('function', ''),
                    'shaft': row.get('shaft', ''),
                    'hole': row.get('hole', ''),
                    'ansi': row.get('ansi', ''),
                    'note': row.get('note', '')
                }
                database.append(item)
    except Exception as e:
        print(f"Error loading fits CSV: {e}")
        
    return database

# Load data on module import
fits_database = load_fits_from_csv()

def search_fits(keywords):
    """
    Search for fits matching all keywords.
    """
    results = []
    # Normalize keywords to list if string
    if isinstance(keywords, str):
        keywords = keywords.split()
    
    # Ensure all keywords are valid strings
    keywords = [str(k).strip() for k in keywords if str(k).strip()]

    if not keywords:
        return []

    for item in fits_database:
        # Create a search string containing all relevant fields
        row_text = f"{item['type']} {item['function']} {item['note']} {item['ansi']}"
        
        # AND logic: all keywords must be present
        if all(k in row_text for k in keywords):
            results.append(item)
            
    return results

def get_all_tags():
    """
    Helper to extract unique tags/keywords for frontend suggestions.
    """
    tags = set()
    for item in fits_database:
        # Split function and note by space to get potential tags
        words = item['function'].split() + item['note'].split() + [item['type']]
        # Use Jieba or simple split? Simple split for now as data has spaces
        # But Chinese text might not have spaces. 
        # For now, just add full phrases or specific known tags if need be.
        # Let's just return a static list of common tags for now to avoid clutter,
        # or extract from type/ansi.
        tags.add(item['type'])
        if '轉動' in item['function']: tags.add('轉動')
        if '定位' in item['function']: tags.add('定位')
        if '滑動' in item['function']: tags.add('滑動')
        if '裝拆' in item['function']: tags.add('裝拆')
        if '高速' in item['function']: tags.add('高速')
        if '重壓' in item['function']: tags.add('重壓')
            
    return sorted(list(tags))
