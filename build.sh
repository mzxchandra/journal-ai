#!/usr/bin/env bash
# Build script for Render.com

# Exit on error  
set -o errexit

# Upgrade pip to latest version
pip install --upgrade pip

# Install dependencies with verbose output for debugging
pip install -r requirements.txt --verbose

# Create database tables (will run once on first deploy)
python init_prod_db.py
