import os
basedir = os.path.abspath(os.path.dirname(__file__))

class Config(object):
    # Flask settings
    SECRET_KEY = os.getenv('SECRET_KEY')
    
    # Database settings
    SQLALCHEMY_DATABASE_URI = f"mysql+pymysql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST', 'localhost')}/{os.getenv('DB_NAME', 'journal_db')}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_POOL_SIZE = 10
    SQLALCHEMY_POOL_TIMEOUT = 30
    SQLALCHEMY_POOL_RECYCLE = 280
    
    # Session settings
    SESSION_TYPE = "filesystem"
    SESSION_PERMANENT = False
    
    # Hugging Face API Token
    HUGGINGFACE_TOKEN = os.getenv('HUGGINGFACE_TOKEN')