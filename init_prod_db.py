#!/usr/bin/env python3
"""
Production database initialization script for Railway deployment.
This will be run automatically when the app starts for the first time.
"""

import os
from app import app, db

def init_production_db():
    """Initialize production database with tables."""
    with app.app_context():
        try:
            # Create all tables
            db.create_all()
            print("✅ Production database tables created successfully!")
            return True
        except Exception as e:
            print(f"❌ Error creating database tables: {e}")
            return False

if __name__ == "__main__":
    init_production_db()
