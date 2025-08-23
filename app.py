import os
from flask import Flask, render_template, request, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from flask_session import Session
from flask_wtf import CSRFProtect
import requests
from datetime import datetime
from dotenv import load_dotenv
import json
import logging

# Load environment variables
load_dotenv()

# Configuration
DATABASE_URL = os.getenv('DATABASE_URL') or os.getenv('DATABASE_PRIVATE_URL')

# For production, ensure we use psycopg3 dialect and handle both URL formats
if DATABASE_URL:
    # Handle both postgres:// and postgresql:// formats from Supabase
    if DATABASE_URL.startswith('postgres://'):
        DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql+psycopg://', 1)
    elif DATABASE_URL.startswith('postgresql://'):
        DATABASE_URL = DATABASE_URL.replace('postgresql://', 'postgresql+psycopg://', 1)
    
    # Ensure SSL mode for Supabase connections
    if 'supabase.co' in DATABASE_URL and 'sslmode=' not in DATABASE_URL:
        separator = '&' if '?' in DATABASE_URL else '?'
        DATABASE_URL += f'{separator}sslmode=require'
elif not DATABASE_URL:
    DATABASE_URL = 'sqlite:///journal.db'

SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
ENVIRONMENT = os.getenv('ENVIRONMENT', 'development')
INIT_DB_SECRET = os.getenv('INIT_DB_SECRET')

# API Configuration
API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-latest:generateContent?key={GOOGLE_API_KEY}"
headers = {"Content-Type": "application/json"}
max_token_value = 100

# Logging setup
if ENVIRONMENT == 'production':
    logging.basicConfig(level=logging.INFO)
else:
    logging.basicConfig(level=logging.DEBUG)

print(f"Environment: {ENVIRONMENT}")
print(f"Database URL configured: {'Yes' if DATABASE_URL else 'No'}")

app = Flask(__name__)

# App Configuration
app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SESSION_TYPE'] = 'sqlalchemy'
app.config['SESSION_SQLALCHEMY_TABLE'] = 'sessions'
app.config['SESSION_PERMANENT'] = False
app.config['SECRET_KEY'] = SECRET_KEY
app.config['WTF_CSRF_ENABLED'] = True

# Production vs Development settings
if ENVIRONMENT == 'production':
    app.config['DEBUG'] = False
    app.config['SQLALCHEMY_ECHO'] = False
    app.config['SQLALCHEMY_POOL_SIZE'] = 20
    app.config['SQLALCHEMY_POOL_TIMEOUT'] = 30
    app.config['SQLALCHEMY_POOL_RECYCLE'] = 280
else:
    app.config['DEBUG'] = True
    app.config['SQLALCHEMY_ECHO'] = True
    app.config['SQLALCHEMY_POOL_SIZE'] = 10
    app.config['SQLALCHEMY_POOL_TIMEOUT'] = 30
    app.config['SQLALCHEMY_POOL_RECYCLE'] = 280

db = SQLAlchemy(app)

# Configure session after db is initialized
app.config['SESSION_SQLALCHEMY'] = db
Session(app)
csrf = CSRFProtect(app) #https://www.geeksforgeeks.org/csrf-protection-in-flask/

class JournalEntry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(300), nullable=False)
    content = db.Column(db.Text, nullable=False)
    date = db.Column(db.String(50), nullable=False)
    user_email = db.Column(db.String(50), nullable=False)

#https://flask-user.readthedocs.io/en/latest/data_models.html
class User(db.Model):
    email = db.Column(db.String(50), nullable=False, unique=True, primary_key=True) #email is the primary key
    pin = db.Column(db.String(4), nullable=False) #4-digit pin for the user

# Add session table for Flask-Session
class Sessions(db.Model):
    __tablename__ = 'sessions'
    id = db.Column(db.String(255), primary_key=True)
    data = db.Column(db.LargeBinary)
    expiry = db.Column(db.DateTime)

prompt_input = f"""
Generate a thoughtful journaling prompt that encourages reflection on specific life moments. The prompt should help users recall and explore memorable experiences, guiding them to think about how those moments shaped their life, character, or relationships.

Examples of good prompts:
- "Describe a time when you had to make a difficult decision that changed your life. What led to that decision?"
- "Tell me about a moment when you felt truly proud of yourself. What did you accomplish?"
- "Who is someone from your past that you think about often? What made them special to you?"
- "What was the most memorable trip or adventure you ever took? What made it unforgettable?"

Please provide just one clear, engaging question that would inspire meaningful writing. Keep it conversational and warm in tone.
"""

def create_tables():
    """Create database tables in production."""
    if ENVIRONMENT == 'production':
        try:
            db.create_all()
            logging.info("Database tables created successfully")
        except Exception as e:
            logging.error(f"Error creating database tables: {e}")


@app.route('/init-db', methods=['POST'])
def init_db():
    """Endpoint to initialize database tables once in production."""
    secret = request.args.get('secret')
    if INIT_DB_SECRET and secret != INIT_DB_SECRET:
        return {"error": "Unauthorized"}, 403
    create_tables()
    return {"status": "initialized"}, 200

@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors gracefully."""
    return render_template('base.html'), 404

@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors gracefully."""
    db.session.rollback()
    if ENVIRONMENT == 'production':
        return "Sorry, something went wrong. Please try again later.", 500
    else:
        return str(error), 500

@app.teardown_appcontext
def shutdown_session(exception=None):
    db.session.remove()

# Health check endpoint
@app.route('/health')
def health_check():
    """Health check endpoint for monitoring."""
    try:
        # Test database connection
        from sqlalchemy import text
        db.session.execute(text('SELECT 1'))
        return {"status": "healthy", "database": "connected"}, 200
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}, 500

# https://medium.com/@mosininamdar/how-to-make-a-signup-login-and-logout-route-in-flask-app-in-5-minutes-f5c771f7a8f3
# Route for registering
@app.route("/signup", methods=["POST", "GET"])
def signup():
    if request.method == "POST":
        email = request.form.get("email")
        pin = request.form.get("pin")

        # Validate input
        if not email or not pin:
            print("Missing email or pin")
            return redirect("/signup")

        #check if the user exists
        user = User.query.filter_by(email=email).first()
        if user:
            # flash("User already exists, proceeding to login")
            return redirect("/login")
        
        if len(pin) != 4 or not pin.isdigit():
            print(f"Invalid pin: {pin}")
            # flash('Please enter a 4-digit PIN number')
            return redirect("/signup")

        try:
            new_user = User(email=email, pin=pin)
            db.session.add(new_user)
            db.session.commit()
            return redirect("/login")
        except Exception as e:
            print(f"Error creating user: {e}")
            db.session.rollback()
            return redirect("/signup")
    return render_template("signup.html")

 # Route for logging in
@app.route("/login", methods=["POST", "GET"])
def login():
  # if form is submited
    if request.method == "POST":
        email = request.form.get("email")
        pin = request.form.get("pin")
        # check if the user exists
        user = User.query.filter_by(email=email).first() #querying the supposed user
        if user and user.pin == pin:
            session["email"] = user.email #storing in session
            return redirect("/")
        # redirect to the main page
        return redirect("/")
    return render_template("login.html")

# Route for logging out
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

# Route for landing page
@app.route("/", methods = ['GET', 'POST'])
def index():
    if 'email' not in session:
        return redirect("/login")

    journal_entry = None
    
    if request.method == 'GET':
        try:
            generated_prompt = generate_prompt()
            journal_entry = JournalEntry(
                title=generated_prompt,
                content="",  # Empty content for now
                date=datetime.now().strftime("%B %d, %Y"),
                user_email=session["email"]
            )
            db.session.add(journal_entry)
            db.session.commit()  # Save immediately
        except Exception as e:
            print(f"Error in index GET: {e}")
            # Return a simple fallback if database or API fails
            return render_template("index.html", 
                                 name=session['email'], 
                                 prompt="What's on your mind today?", 
                                 journal_content="", 
                                 entry_id=None)
    
    else:
        try:
            # Get committed ID
            entry_id = request.form.get('entry_id')
            if entry_id:
                journal_entry = JournalEntry.query.get(entry_id)

                #regenerate prompt action
                if request.form.get('action') == "generate":
                    journal_entry.title = generate_prompt()  # Update prompt
                    db.session.commit()  # Save the new prompt
                    return redirect(url_for('edit_entry', id=journal_entry.id))

                # Handle saving the journal entry content
                elif request.form.get('action') == "save":
                    journal_content = request.form.get('journal_entry')
                    if journal_content:
                        journal_entry.content = journal_content  # Update
                        db.session.commit()
        except Exception as e:
            print(f"Error in index POST: {e}")
            return "An error occurred while processing your request.", 500

    return render_template("index.html", 
                         name=session['email'], 
                         prompt=journal_entry.title if journal_entry else "What's on your mind today?", 
                         journal_content=journal_entry.content if journal_entry else "", 
                         entry_id=journal_entry.id if journal_entry else None)


# Route for viewing saved journal entries
@app.route("/entries", methods=['GET'])
def view_entries():
    if 'email' not in session:
        return redirect("/login")
    # Query all saved journal entries from the database
    entries = JournalEntry.query.filter_by(user_email = session['email']).all()
    return render_template("entries.html", entries=entries)

# Route for editing a specific journal entry
@app.route('/edit_entry/<int:id>', methods=['POST', 'GET'])
def edit_entry(id):
    if 'email' not in session:
        return redirect("/login")
    try:
        # Query the journal entry by its ID
        entry = JournalEntry.query.get_or_404(id)
        if request.method == 'POST':
            action = request.form.get('action')

            if action == 'save':
                # Update the entry's title and content
                entry.title = request.form['title']
                entry.content = request.form['journal_entry']
                db.session.commit()  # Save the changes

            elif action == 'generate_followup':
                entry.title = request.form['title']
                entry.content = request.form['journal_entry']
                db.session.commit()  # Save the changes
                followup = generate_followup_question(entry.content)
                return render_template('edit_entry.html', entry = entry, follow_up_question=followup)
        
        return render_template('edit_entry.html', entry = entry, follow_up_question="")
    
    except Exception as e:
        db.session.rollback()
        print(f"Error: {e}")  # Log the error for debugging
        return "An error occurred while processing your request.", 500  # Return an error response

# Route for deleting a specific journal entry
@app.route('/delete_entry/<int:id>', methods=['POST', 'GET'])
def delete_entry(id):
    if 'email' not in session:
        return redirect("/login")
    try:
        # Query the journal entry by its ID
        entry = JournalEntry.query.get(id)
        if entry:
            db.session.delete(entry)
            db.session.commit()
            return redirect(url_for('view_entries'))
        return "Journal entry not found.", 404
    except Exception as e:
        db.session.rollback()  # Rollback in case of any error

# # Route for deleting all journal entries if necessary
# @app.route('/delete_all_entries', methods=['POST', 'GET'])
# def delete_all_entries():
#     try:
#         # This will delete all rows in the journal_entry table
#         num_rows_deleted = db.session.query(JournalEntry).delete()
#         db.session.commit()
#         return f"Deleted {num_rows_deleted} journal entries.", 200
#     except Exception as e:
#         db.session.rollback()  # Rollback in case of any error
#         return f"An error occurred: {str(e)}", 500


# # Load the GPT-2 tokenizer and model
# tokenizer = AutoTokenizer.from_pretrained("gpt2")
# model = AutoModelForCausalLM.from_pretrained("gpt2")


#If we get the following error
#requests.exceptions.ConnectionError: HTTPSConnectionPool(host='api-inference.huggingface.co', port=443): Max retries exceeded with url: /models/google/gemma-2-2b-it (Caused by NameResolutionError("<urllib3.connection.HTTPSConnection object at 0x10972b380>: Failed to resolve 'api-inference.huggingface.co' ([Errno 8] nodename nor servname provided, or not known)"))
# We should have a protocol to use a different model

# Function to query Google Gemini API
def query_google_gemini_api(prompt_text):
    payload = {
        "contents": [{
            "parts": [{
                "text": prompt_text
            }]
        }],
        "generationConfig": {
            "temperature": 0.9,
            "topK": 1,
            "topP": 1,
            "maxOutputTokens": max_token_value,
            "stopSequences": []
        },
        "safetySettings": [
            {
                "category": "HARM_CATEGORY_HARASSMENT",
                "threshold": "BLOCK_MEDIUM_AND_ABOVE"
            },
            {
                "category": "HARM_CATEGORY_HATE_SPEECH",
                "threshold": "BLOCK_MEDIUM_AND_ABOVE"
            },
            {
                "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                "threshold": "BLOCK_MEDIUM_AND_ABOVE"
            },
            {
                "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                "threshold": "BLOCK_MEDIUM_AND_ABOVE"
            }
        ]
    }
    
    try:
        response = requests.post(API_URL, headers=headers, json=payload)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error calling Google Gemini API: {e}")
        return None

# Function to extract the response text from Google Gemini API response
def extract_gemini_response(response_data):
    if response_data and 'candidates' in response_data:
        if len(response_data['candidates']) > 0:
            candidate = response_data['candidates'][0]
            if 'content' in candidate and 'parts' in candidate['content']:
                if len(candidate['content']['parts']) > 0:
                    return candidate['content']['parts'][0]['text'].strip()
    return "Sorry, I couldn't generate a response at the moment."

# Function to generate an initial prompt
def generate_prompt():
    response_data = query_google_gemini_api(prompt_input)
    if response_data:
        generated_prompt = extract_gemini_response(response_data)
        print("Generated Prompt:", generated_prompt)
        return generated_prompt
    else:
        # Fallback prompt if API fails
        fallback_prompts = [
            "What was the most meaningful conversation you had this week?",
            "Describe a moment today when you felt truly grateful.",
            "What's one thing you learned about yourself recently?",
            "Tell me about a person who has had a positive impact on your life.",
            "What's a small victory you experienced recently?"
        ]
        import random
        return random.choice(fallback_prompts)
    
# Function to generate a follow-up question based on a journal entry
def generate_followup_question(content):
    followup_input = f"""
    Generate a follow-up question based on the following journal entry:
    "{content}"
    The follow-up question should encourage the user to delve deeper into the topic, reflect on their emotions, or explore related experiences. It should be open-ended and engaging, prompting the user to write more about the topic.
    Response should include one clear concise question, asked in a conversational tone, maximum {max_token_value} tokens.
    """
    
    response_data = query_google_gemini_api(followup_input)
    if response_data:
        generated_followup = extract_gemini_response(response_data)
        print(f"Generated Followup: {generated_followup}")
        return generated_followup
    else:
        # Fallback questions if API fails
        fallback_questions = [
            "How did this experience change your perspective?",
            "What emotions were you feeling during this time?",
            "What would you tell someone else going through something similar?",
            "How does this memory make you feel now when you look back on it?",
            "What did you learn about yourself from this experience?"
        ]
        import random
        return random.choice(fallback_questions)