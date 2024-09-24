from app import app, db
from dotenv import load_dotenv
import os

load_dotenv()
with app.app_context():
    db.create_all()