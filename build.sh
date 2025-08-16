#!/usr/bin/env bash
# Build script for Render.com

# Install dependencies
pip install -r requirements.txt

# Create database tables (will run once on first deploy)
python init_prod_db.py
