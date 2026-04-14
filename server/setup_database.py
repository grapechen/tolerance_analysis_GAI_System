#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
資料庫設定腳本 (Database Setup Script)

此腳本會：
1. 確認 MySQL 連接
2. 建立資料庫 (如果不存在)
3. 建立所有 ORM 表

使用方法:
  python setup_database.py
"""

import os
import sys
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# 載入環境變數
load_dotenv()

# 從環境變數取得資料庫 URL
DATABASE_URL = os.getenv('DATABASE_URL', 'mysql+pymysql://root:password@localhost:3306/tolerance_db')

print("=" * 80)
print("Tolerance Project - Database Setup")
print("=" * 80)
print()

# 解析資料庫 URL
try:
    # URL format: mysql+pymysql://user:password@host:port/database
    url_parts = DATABASE_URL.replace('mysql+pymysql://', '').split('@')
    if len(url_parts) != 2:
        raise ValueError("Invalid DATABASE_URL format")

    user_pass = url_parts[0].split(':')
    host_db = url_parts[1].split('/')

    user = user_pass[0]
    password = user_pass[1] if len(user_pass) > 1 else ''
    host = host_db[0].split(':')[0]
    port = int(host_db[0].split(':')[1]) if ':' in host_db[0] else 3306
    database = host_db[1] if len(host_db) > 1 else 'tolerance_db'

    print(f"[INFO] Database Configuration:")
    print(f"  Host:     {host}:{port}")
    print(f"  User:     {user}")
    print(f"  Database: {database}")
    print()
except Exception as e:
    print(f"[ERROR] Failed to parse DATABASE_URL: {e}")
    print(f"  DATABASE_URL = {DATABASE_URL}")
    print()
    print("Please set DATABASE_URL in .env file:")
    print("  DATABASE_URL=mysql+pymysql://user:password@localhost:3306/tolerance_db")
    sys.exit(1)

# 步驟 1: 測試基本連接 (連接到 MySQL，但不指定資料庫)
print("[STEP 1] Testing MySQL connection...")
root_url = f'mysql+pymysql://{user}:{password}@{host}:{port}/'
try:
    engine = create_engine(root_url, echo=False)
    with engine.connect() as conn:
        result = conn.execute(text('SELECT 1'))
        print("[OK] MySQL connection successful")
except Exception as e:
    print(f"[ERROR] Failed to connect to MySQL: {e}")
    print()
    print("Troubleshooting:")
    print("  1. Ensure MySQL/MariaDB is running")
    print("  2. Verify credentials in .env file")
    print("  3. Check host and port (default: localhost:3306)")
    sys.exit(1)

# 步驟 2: 建立資料庫 (如果不存在)
print()
print("[STEP 2] Creating database (if not exists)...")
try:
    engine = create_engine(root_url, echo=False)
    with engine.connect() as conn:
        conn.execute(text(f"CREATE DATABASE IF NOT EXISTS `{database}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"))
        conn.commit()
        print(f"[OK] Database '{database}' ready")
except Exception as e:
    print(f"[ERROR] Failed to create database: {e}")
    sys.exit(1)

# 步驟 3: 連接到資料庫並建立表
print()
print("[STEP 3] Creating tables from ORM models...")
try:
    # 動態導入 tables 模組 (如果在 server 目錄下)
    sys.path.insert(0, os.path.dirname(__file__))
    from tables import BASE, engine

    # 建立所有表
    BASE.metadata.create_all(engine)

    # 驗證表是否建立
    with engine.connect() as conn:
        result = conn.execute(text("SHOW TABLES"))
        tables = result.fetchall()

        print("[OK] Tables created successfully:")
        for table in tables:
            print(f"  ✓ {table[0]}")

except ImportError as e:
    print(f"[ERROR] Failed to import tables module: {e}")
    print("Make sure you are running this script from the server directory")
    sys.exit(1)
except Exception as e:
    print(f"[ERROR] Failed to create tables: {e}")
    sys.exit(1)

# 步驟 4: 驗證表結構
print()
print("[STEP 4] Verifying table structure...")
try:
    from tables import PmiSession, PmiItem, AssemblyContact

    print("[OK] ORM Models verified:")
    print(f"  ✓ PmiSession - {len(PmiSession.__table__.columns)} columns")
    print(f"  ✓ PmiItem - {len(PmiItem.__table__.columns)} columns")
    print(f"  ✓ AssemblyContact - {len(AssemblyContact.__table__.columns)} columns")

except Exception as e:
    print(f"[ERROR] Failed to verify models: {e}")
    sys.exit(1)

# 完成
print()
print("=" * 80)
print("[SUCCESS] Database setup completed successfully!")
print("=" * 80)
print()
print("Next steps:")
print("  1. Start Flask application: python ai_app.py")
print("  2. Open browser: http://localhost:7011")
print("  3. Upload STEP file to test the system")
print()
