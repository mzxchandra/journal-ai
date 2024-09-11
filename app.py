from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
import requests
import sys

app = Flask(__name__)
username = sys.argv[1]
password = sys.argv[2]
token = sys.argv[3]
app.config['SQLALCHEMY_DATABASE_URI'] = f"mysql+pymysql://{username}:{password}@localhost/journal_db"
db = SQLAlchemy(app)

class JournalEntry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)

# Create the database and tables if they don't already exist
with app.app_context():
    db.create_all()

API_URL = "https://api-inference.huggingface.co/models/google/gemma-2-2b-it"
headers = {"Authorization": f"Bearer {token}"}

prompt_input = """
    Generate a unique and thoughtful journaling prompt that encourages users to reflect on personal experiences, emotions, or pivotal life moments. The prompt should help them recall and explore past events in detail, guiding them to introspect on how those experiences shaped their life, character, or relationships. The prompt should feel personal and inspiring, not generic. 
    Here are a few examples:
    - "Describe a time when you had to make a difficult decision that changed the course of your life. What led to the decision, and how did it affect you?"
    - "Was there a moment you thought your life was truly in danger? What happened?"
    - "Who is your best friend from highschool? What have you gone through together?"
    Generate a similar journaling prompt to help users reflect on their past.
    """


# Function to query model for a prompt
def query_huggingface_api(payload):
    response = requests.post(API_URL, headers=headers, json=payload)
    return response.json()

# Function to extract the prompt from the generated text
def extract_prompt(generated_text):
    # Check if "**Prompt:**" exists in the generated text
    if prompt_input in generated_text:
        # Split the text and take the part after "**Prompt:**"
        return generated_text.split(prompt_input, 1)[1].strip()
    return generated_text  # Return the full text if "**Prompt:**" is not found

# Route for landing page
@app.route("/", methods = ['GET'])
def index():
    prompt = query_huggingface_api({
    "inputs": prompt_input,
    "parameters": {
        "max_new_tokens": 32,
        "temperature": 0.9,
        "num_return_sequences": 1
    }
})
    generated_prompt = prompt[0]["generated_text"]
    generated_prompt = extract_prompt(generated_prompt)
    
    return render_template("index.html", name = "Marcus", prompt=generated_prompt)

# Route for saving journal entries
@app.route("/save_entry", methods=['POST'])
def save_entry():
    journal_content = request.form['journal_entry']
    if journal_content:
        # Save the journal entry to the database
        new_entry = JournalEntry(content=journal_content)
        db.session.add(new_entry)
        db.session.commit()

    return redirect(url_for('view_entries'))  # Redirect to the entries page after saving

# Route for viewing saved journal entries
@app.route("/entries", methods=['GET'])
def view_entries():
    # Query all saved journal entries from the database
    entries = JournalEntry.query.all()
    return render_template("entries.html", entries=entries)


# # Load the GPT-2 tokenizer and model
# tokenizer = AutoTokenizer.from_pretrained("gpt2")
# model = AutoModelForCausalLM.from_pretrained("gpt2")




if __name__ == '__main__':
    app.run(port=3000, debug=True)
