from flask import Flask, render_template, request, redirect, url_for, session, abort
from flask_sqlalchemy import SQLAlchemy
from flask_session import Session
from flask_wtf import CSRFProtect
import requests
from datetime import datetime
from dotenv import load_dotenv
import os

load_dotenv()
DATABASE_URL = os.getenv('DATABASE_URL')
SECRET_KEY = os.getenv('SECRET_KEY')
HUGGINGFACE_TOKEN = os.getenv('HUGGINGFACE_TOKEN')


app = Flask(__name__)

app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_POOL_SIZE'] = 10
app.config['SQLALCHEMY_POOL_TIMEOUT'] = 30
app.config['SQLALCHEMY_POOL_RECYCLE'] = 280
# Session settings
app.config['SESSION_TYPE'] = "filesystem"
app.config['SESSION_PERMANENT'] = False
token = HUGGINGFACE_TOKEN

db = SQLAlchemy(app)
Session(app)
#https://www.geeksforgeeks.org/csrf-protection-in-flask/
csrf = CSRFProtect(app)


max_token_value = 75

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

with app.app_context():
    db.create_all()  # Recreate them with the current model schema


API_URL = "https://api-inference.huggingface.co/models/google/gemma-2-2b-it"
headers = {"Authorization": f"Bearer {token}"}

prompt_input = f"""
    Generate a unique journaling prompt that encourages users to reflect on specific life moments. The prompt should help them recall and explore memorable events in detail, guiding them to introspect on how those experiences shaped their life, character, or relationships.
    Here are a few examples:
    - "Describe a time when you had to make a difficult decision that changed the course of your life. What led to the decision, and how did it affect you?"
    - "Was there a moment you thought your life was truly in danger? What happened?"
    - "Who is your best friend from highschool? What have you gone through together?"
    - "What was the most memorable trip you ever took? What made it unforgettable?"
    Have your response just be one clear and concise prompt in question form for the user, max new tokens you're allowed is {max_token_value}.
    """

# https://medium.com/@mosininamdar/how-to-make-a-signup-login-and-logout-route-in-flask-app-in-5-minutes-f5c771f7a8f3
# Route for registering
@app.route("/signup", methods=["POST", "GET"])
def signup():
    if request.method == "POST":
        email = request.form.get("email")
        pin = request.form.get("pin")

        #check if the user exists
        user = User.query.filter_by(email=email).first()
        if user:
            # flash("User already exists, proceeding to login")
            return redirect("/login")
        
        if len(pin) != 4 or not pin.isdigit():
            # flash('Please enter a 4-digit PIN number')
            return redirect(url_for('register'))

        new_user = User(email=email, pin=pin)
        db.session.add(new_user)
        db.session.commit()
        return redirect("/login")
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
    generated_prompt = generate_prompt()
    journal_content = ""

    if request.method == 'POST':
        action = request.form.get('action')
        if action == "generate":
            generated_prompt = generate_prompt()
        else:
            pass

    # Try to retrieve an existing journal entry with the same prompt and date
    existing_entry = JournalEntry.query.filter_by(title=generated_prompt, date=datetime.now().strftime("%B %d, %Y"), user_email = session['email']).first()
    if existing_entry:
    # If an entry exists, pre-fill the content; otherwise, leave it blank
        journal_content = existing_entry.content
    print(generated_prompt)
    return render_template("index.html", name = session['email'], prompt=generated_prompt, journal_content= journal_content)

# Route for saving journal entries
@app.route("/save_entry", methods=['POST'])
def save_entry():
    if 'email' not in session:
        return redirect("/login")
    journal_content = request.form['journal_entry']
    generated_prompt = request.form['generated_prompt']
    if journal_content and generated_prompt:
        # Save the journal entry to the database
        new_entry = JournalEntry(title = generated_prompt, content=journal_content, date=datetime.now().strftime("%B %d, %Y"), user_email=session["email"])
        db.session.add(new_entry)
        db.session.commit()
        entry_id = new_entry.id
        print(entry_id)
        return redirect(url_for('edit_entry', id=entry_id))
    return redirect(url_for('index')) #if content or prompt missing

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

# Function to query model for a prompt
def query_huggingface_api(payload):
    response = requests.post(API_URL, headers=headers, json=payload)
    return response.json()

# Function to extract the prompt from the generated text
def extract_prompt(input: str, response: list[dict])-> str:
    # Check if prompt exists in the generated text
    generated_text = response[0]['generated_text']
    generated_text = generated_text.replace(input, "") if input in generated_text else generated_text
    generated_text = generated_text.strip()
    generated_text = generated_text.replace("\\'", "'")
    return generated_text  # Return the full text if input prompt not found

# Function to generate an initial prompt
def generate_prompt():
    response = query_huggingface_api({
    "inputs": prompt_input,
    "parameters": {
        "max_new_tokens": max_token_value,
        "temperature": 0.9,
        "num_return_sequences": 1,
        "stop_sequences": [".", "?"] #only stop when a sentence ends
    }
})
    generated_prompt = extract_prompt(prompt_input, response)
    print("Generated Prompt:", generated_prompt)
    return generated_prompt
    
# Function to generate a follow-up question based on a journal entry
def generate_followup_question(content):
    followup_input = f"""
    Generate a follow-up question based on the following journal entry:
    "{content}"
    The follow-up question should encourage the user to delve deeper into the topic, reflect on their emotions, or explore related experiences. It should be open-ended and engaging, prompting the user to write more about the topic.
    Response should include one clear concise question, asked in a conversational tone, max new tokens you're allowed is {max_token_value}.
    """
    # Query the model with the follow-up input
    response = query_huggingface_api({
        "inputs": followup_input,
        "parameters": {
            "max_new_tokens": max_token_value,
            "temperature": 0.9,
            "num_return_sequences": 1
        }
    })
    generated_followup = extract_prompt(followup_input, response)
    print(f"Generated Followup: {generated_followup}")
    return generated_followup



# if __name__ == '__main__':
#     app.run(debug=True)
