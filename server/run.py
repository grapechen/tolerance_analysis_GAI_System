#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Tolerance Project - Application Startup Script

This script starts the Flask application with proper initialization.

Usage:
  python run.py [--host HOST] [--port PORT] [--debug]

Examples:
  python run.py                           # Default: localhost:7011
  python run.py --host 0.0.0.0 --port 7011  # All interfaces
  python run.py --debug                   # Enable Flask debug mode
"""

import os
import sys
import argparse
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def check_dependencies():
    """檢查必需的依賴"""
    print("[CHECK] Verifying dependencies...")

    required_modules = [
        ('flask', 'Flask'),
        ('sqlalchemy', 'SQLAlchemy'),
        ('pymysql', 'PyMySQL'),
    ]

    missing = []
    for module_name, display_name in required_modules:
        try:
            __import__(module_name)
            print(f"  [✓] {display_name}")
        except ImportError:
            print(f"  [✗] {display_name} - NOT INSTALLED")
            missing.append(f"pip install {module_name}")

    if missing:
        print()
        print("[ERROR] Missing dependencies!")
        print("Install them using:")
        for cmd in missing:
            print(f"  {cmd}")
        sys.exit(1)

    print()

def check_database():
    """檢查資料庫連接"""
    print("[CHECK] Testing database connection...")

    try:
        from sqlalchemy import create_engine, text

        DATABASE_URL = os.getenv('DATABASE_URL')
        if not DATABASE_URL:
            print("  [✗] DATABASE_URL not set in .env")
            print("  Please configure .env file first")
            return False

        engine = create_engine(DATABASE_URL, echo=False)
        with engine.connect() as conn:
            result = conn.execute(text('SELECT 1'))
            print("  [✓] Database connection successful")
            return True

    except Exception as e:
        print(f"  [✗] Database connection failed: {e}")
        print()
        print("  To fix:")
        print("    1. Ensure MySQL is running")
        print("    2. Configure DATABASE_URL in .env file")
        print("    3. Run: python setup_database.py")
        return False

def check_tables():
    """檢查資料庫表是否存在"""
    print("[CHECK] Verifying database tables...")

    try:
        from sqlalchemy import inspect
        from tables import engine

        inspector = inspect(engine)
        tables = inspector.get_table_names()

        required_tables = ['pmi_session', 'pmi_item', 'assembly_contact']
        missing_tables = [t for t in required_tables if t not in tables]

        if missing_tables:
            print(f"  [✗] Missing tables: {', '.join(missing_tables)}")
            print("  Run: python setup_database.py")
            return False

        for table in required_tables:
            print(f"  [✓] {table}")
        return True

    except Exception as e:
        print(f"  [✗] Failed to verify tables: {e}")
        return False

def main():
    """主程式入口"""

    # 命令行參數
    parser = argparse.ArgumentParser(description='Tolerance Project - Start Flask Application')
    parser.add_argument('--host', default='127.0.0.1', help='Host to bind to (default: 127.0.0.1)')
    parser.add_argument('--port', type=int, default=7011, help='Port to listen on (default: 7011)')
    parser.add_argument('--debug', action='store_true', help='Enable Flask debug mode')
    parser.add_argument('--skip-checks', action='store_true', help='Skip dependency checks')

    args = parser.parse_args()

    print("=" * 80)
    print("Tolerance Project - Flask Application Startup")
    print("=" * 80)
    print()

    # 檢查依賴（除非跳過）
    if not args.skip_checks:
        check_dependencies()

        if not check_database():
            print()
            print("[ERROR] Database is not accessible. Please configure and run setup_database.py")
            sys.exit(1)
        print()

        if not check_tables():
            print()
            print("[ERROR] Database tables are missing. Please run setup_database.py")
            sys.exit(1)
        print()

    # 啟動 Flask 應用
    print("[STARTUP] Starting Flask application...")
    print(f"  Host: {args.host}")
    print(f"  Port: {args.port}")
    print(f"  Debug: {args.debug}")
    print()
    print("=" * 80)
    print()

    try:
        # Import Flask app
        from ai_app import app

        # Configure app
        app.config['JSON_AS_ASCII'] = False
        app.config['MAX_CONTENT_LENGTH'] = int(os.getenv('MAX_CONTENT_LENGTH', 209715200))

        # Start server
        app.run(
            host=args.host,
            port=args.port,
            debug=args.debug,
            use_reloader=args.debug
        )

    except KeyboardInterrupt:
        print()
        print()
        print("[SHUTDOWN] Server shutting down...")
        sys.exit(0)
    except Exception as e:
        print(f"[ERROR] Failed to start application: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    main()
