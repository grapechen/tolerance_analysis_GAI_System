import os

csv_path = r'c:\Tolerance_Project\server\data\0213_export.csv'
temp_path = r'c:\Tolerance_Project\server\data\0213_export_temp.csv'

print(f"Starting encoding conversion for: {csv_path}")

lines_converted = 0
errors = 0

with open(csv_path, 'rb') as f_in:
    with open(temp_path, 'w', encoding='utf-8-sig', newline='') as f_out:
        for line_bytes in f_in:
            decoded = False
            # Try UTF-8-SIG first, then UTF-8, then Big5/CP950
            for enc in ['utf-8-sig', 'utf-8', 'big5', 'cp950']:
                try:
                    line_text = line_bytes.decode(enc)
                    f_out.write(line_text)
                    decoded = True
                    lines_converted += 1
                    break
                except UnicodeDecodeError:
                    continue
            
            if not decoded:
                # Fallback: ignore or replace bad characters if all decodings fail
                f_out.write(line_bytes.decode('utf-8', errors='replace'))
                errors += 1
                lines_converted += 1

print(f"Conversion finished. Total lines: {lines_converted}, decoding fallback used: {errors}")

# Replace original file
if os.path.exists(temp_path):
    if os.path.exists(csv_path):
        os.remove(csv_path)
    os.rename(temp_path, csv_path)
    print(f"Original file replaced with unified UTF-8-SIG version.")
else:
    print("Error: Temporary file was not created.")
