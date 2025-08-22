from app import app

# Vercel expects a callable named 'app' for Python serverless functions
# Your Flask app is already named 'app' in app.py, so this just exposes it

if __name__ == "__main__":
    app.run()
