"""
Database migration script: Add nominal_size and it_grade columns to pmi_item table
"""

import sys
import os

# Add server directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tables import engine, BASE, PmiItem
from sqlalchemy import text

def migrate():
    """Execute migration"""

    print("[*] Starting database migration...")

    with engine.connect() as conn:
        # Check if nominal_size column exists
        try:
            conn.execute(text("SELECT nominal_size FROM pmi_item LIMIT 1"))
            print("[OK] nominal_size column already exists, skipping...")
        except Exception as e:
            print("[!] nominal_size column does not exist, adding...")
            try:
                conn.execute(text("""
                    ALTER TABLE pmi_item
                    ADD COLUMN nominal_size VARCHAR(32) NULL
                """))
                conn.commit()
                print("[OK] nominal_size column added successfully")
            except Exception as add_error:
                print(f"[ERROR] Failed to add nominal_size column: {add_error}")

        # Check if it_grade column exists
        try:
            conn.execute(text("SELECT it_grade FROM pmi_item LIMIT 1"))
            print("[OK] it_grade column already exists, skipping...")
        except Exception as e:
            print("[!] it_grade column does not exist, adding...")
            try:
                conn.execute(text("""
                    ALTER TABLE pmi_item
                    ADD COLUMN it_grade VARCHAR(10) NULL
                """))
                conn.commit()
                print("[OK] it_grade column added successfully")
            except Exception as add_error:
                print(f"[ERROR] Failed to add it_grade column: {add_error}")

    print("[DONE] Database migration completed!")

if __name__ == "__main__":
    migrate()
