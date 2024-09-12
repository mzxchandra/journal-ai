from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
import requests
import sys
from datetime import datetime

app = Flask(__name__)
username = sys.argv[1]
password = sys.argv[2]
token = sys.argv[3]
app.config['SQLALCHEMY_DATABASE_URI'] = f"mysql+pymysql://{username}:{password}@localhost/journal_db"
app.config['SQLALCHEMY_POOL_SIZE'] = 10
app.config['SQLALCHEMY_POOL_TIMEOUT'] = 30
app.config['SQLALCHEMY_POOL_RECYCLE'] = 280
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

class JournalEntry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(300), nullable=False)
    content = db.Column(db.Text, nullable=False)
    date = db.Column(db.String(50), nullable=False)

with app.app_context():
    # db.drop_all()  # Drop all tables, for testing
    db.create_all()  # Recreate them with the current model schema

API_URL = "https://api-inference.huggingface.co/models/google/gemma-2-2b-it"
headers = {"Authorization": f"Bearer {token}"}

prompt_input = """
    Generate a unique and thoughtful journaling prompt that encourages users to reflect on personal experiences, emotions, or pivotal life moments. The prompt should help them recall and explore past events in detail, guiding them to introspect on how those experiences shaped their life, character, or relationships. The prompt should feel personal and inspiring, not generic. 
    Here are a few examples:
    - "Describe a time when you had to make a difficult decision that changed the course of your life. What led to the decision, and how did it affect you?"
    - "Was there a moment you thought your life was truly in danger? What happened?"
    - "Who is your best friend from highschool? What have you gone through together?"
    Generate a similar journaling prompt to help users reflect on their past. Don't include any preamble, just have the response be a clear concise question
    """


# Function to query model for a prompt
def query_huggingface_api(payload):
    response = requests.post(API_URL, headers=headers, json=payload)
    return response.json()

# Function to extract the prompt from the generated text
def extract_prompt(generated_text):
    # Check if prompt exists in the generated text
    if prompt_input in generated_text:
        # Split the text and take the part after "**Prompt:**"
        generated_text = generated_text.split(prompt_input, 1)[1].strip()
    generated_text = generated_text.replace("*", '')
    return generated_text  # Return the full text if "**Prompt:**" is not found


def generate_prompt():
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
    return generated_prompt

def generate_followup_question(content):
    followup_input = f"""
    Generate a follow-up question based on the following journal entry:
    "{content}"
    The follow-up question should encourage the user to delve deeper into the topic, reflect on their emotions, or explore related experiences. It should be open-ended and engaging, prompting the user to write more about the topic.
    """
    # Query the model with the follow-up input
    followup = query_huggingface_api({
        "inputs": followup_input,
        "parameters": {
            "max_new_tokens": 32,
            "temperature": 0.9,
            "num_return_sequences": 1
        }
    })
    generated_followup = followup[0]["generated_text"]
    generated_followup = extract_prompt(generated_followup)
    return generated_followup
    
# Route for landing page
@app.route("/", methods = ['GET'])
def index():
    generated_prompt = generate_prompt()
    return render_template("index.html", name = "Marcus", prompt=generated_prompt)

# Route for saving journal entries
@app.route("/save_entry", methods=['POST'])
def save_entry():
    journal_content = request.form['journal_entry']
    generated_prompt = request.form['generated_prompt']
    if journal_content:
        # Save the journal entry to the database
        new_entry = JournalEntry(title = generated_prompt, content=journal_content, date=datetime.now().strftime("%B %d, %Y"))
        db.session.add(new_entry)
        db.session.commit()
        db.session.close()
    return redirect(url_for('index'))

# Route for viewing saved journal entries
@app.route("/entries", methods=['GET'])
def view_entries():
    # Query all saved journal entries from the database
    entries = JournalEntry.query.all()
    return render_template("entries.html", entries=entries)

# Route for editing a specific journal entry
@app.route('/edit_entry/<int:id>', methods=['POST', 'GET'])
def edit_entry(id):
    try:
        # Query the journal entry by its ID
        entry = JournalEntry.query.get(id)
        if entry:
            if request.method == 'POST':
                action = request.form.get('action')

                if action == 'save':
                    # Update the entry's title and content
                    entry.title = request.form['title']
                    entry.content = request.form['journal_entry']
                    db.session.commit()  # Save the changes
                    return redirect(url_for('view_entries'))

                elif action == 'generate_followup':
                    # Handle generating a follow-up question (define this logic separately)
                    followup_prompt = generate_followup_question(entry.content)
                    return render_template('edit_entry.html', entry=entry, entry_title=entry.title, entry_date=entry.date.strftime("%B %d, %Y"), followup_prompt=followup_prompt)
        return "Journal entry not found.", 404
    except Exception as e:
        db.session.rollback()

# Route for deleting a specific journal entry
@app.route('/delete_entry/<int:id>', methods=['POST', 'GET'])
def delete_entry(id):
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

# Route for deleting all journal entries if necessary
@app.route('/delete_all_entries', methods=['POST', 'GET'])
def delete_all_entries():
    try:
        # This will delete all rows in the journal_entry table
        num_rows_deleted = db.session.query(JournalEntry).delete()
        db.session.commit()
        return f"Deleted {num_rows_deleted} journal entries.", 200
    except Exception as e:
        db.session.rollback()  # Rollback in case of any error
        return f"An error occurred: {str(e)}", 500

# # Load the GPT-2 tokenizer and model
# tokenizer = AutoTokenizer.from_pretrained("gpt2")
# model = AutoModelForCausalLM.from_pretrained("gpt2")


#If we get the following error
#requests.exceptions.ConnectionError: HTTPSConnectionPool(host='api-inference.huggingface.co', port=443): Max retries exceeded with url: /models/google/gemma-2-2b-it (Caused by NameResolutionError("<urllib3.connection.HTTPSConnection object at 0x10972b380>: Failed to resolve 'api-inference.huggingface.co' ([Errno 8] nodename nor servname provided, or not known)"))
# We should have a protocol to use a different model

if __name__ == '__main__':
    app.run(port=3000, debug=True)
