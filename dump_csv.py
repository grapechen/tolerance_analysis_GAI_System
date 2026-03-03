import csv
import re
import sys

# Try different encodings
encodings = ['utf-8', 'utf-8-sig', 'big5', 'cp950']
file_path = 'server/data/0213_export.csv'

entities = set()

for enc in encodings:
    try:
        with open(file_path, 'r', encoding=enc) as f:
            reader = csv.reader(f)
            headers = next(reader, None) # Skip header
            for row in reader:
                if not row: continue
                # The CSV seems to have complex string logic, let's just grab the first column which is usually Subject
                subject = row[0]
                
                # Extract the actual name: often it's inside `display: XXX` or just the string itself for the subject
                # e.g. Node(labels=set(), properties={'label': 'http://www.semanticweb.org/user/ontologies/2025/1/untitled-ontology-2#輪廓度', 'display': '輪廓度'})
                
                match = re.search(r"'display':\s*'([^']+)'", subject)
                if match:
                    entities.add(match.group(1))
                else:
                    # Try to get the raw URL fragment if display is missing
                    match2 = re.search(r"#([^']+)'", subject)
                    if match2:
                        entities.add(match2.group(1))
                        
        print(f"Successfully read with encoding: {enc}")
        break  # If successful, stop trying encodings
    except UnicodeDecodeError:
        continue
    except Exception as e:
        print(f"Error {enc}: {e}")

print(f"Found {len(entities)} unique entities.")
print("Sample entities:")
for i, e in enumerate(sorted(entities)):
    print(f"- {e}")
    if i > 50: 
        print("...and more")
        break
