from typing import Optional
from fastapi import FastAPI, HTTPException, Form
from fastapi.responses import HTMLResponse
import openai
import os

# Initialize FastAPI
app = FastAPI()

# Load OpenAI API key from environment variables
openai.api_key = os.environ.get('OPENAI_API_KEY')

def parse_response_to_json(response_text):
    """
    Parses a plain-text response to create a JSON structure that adheres to the client's format.
    Handles the corrected structure where 'wordForms' contains an array of objects.
    """
    word_forms = []

    for line in response_text.strip().split("\n"):
        parts = line.split(":")
        if len(parts) < 2:  # Skip malformed lines without a colon
            continue

        form = parts[0].strip("- ").strip()  # Extract the form
        attributes = [attr.strip() for attr in parts[1].split(",")]

        # Ensure there are 5 attributes (aspect, gender, number, person, voice)
        if len(attributes) != 5:
            continue

        word_forms.append({
            "formRepresentations": [
                {"form": form}
            ],
            "aspect": attributes[0],          # P, S, or F
            "gender": attributes[1],         # m or f
            "numberWordForm": attributes[2], # 1, 2, or 3
            "person": attributes[3],         # 1, 2, or 3
            "voice": attributes[4]           # a or p
        })

    return {"wordForms": word_forms}


# Helper function to generate word forms using OpenAI API
async def get_word_forms(word: str):
    prompt = f"""
    Please generate all word forms for the Arabic word: {word}.
    The response should include variations based on the following criteria:
    - Tense: Past (P), Present (S), or Future (F).
    - Gender: Masculine (m) or Feminine (f).
    - Number: Singular (1), Dual (2), or Plural (3).
    - Person: First person (1), Second person (2), or Third person (3).
    - Voice: Active (a) or Passive (p).

    Provide the output in a plain text list format, one form per line, as follows:
    - <word>: <tense>, <gender>, <number>, <person>, <voice>

    For example:
    - ضحك: P, m, 1, 3, a
    - ضحكت: P, f, 1, 3, a
    - يضحك: S, m, 1, 3, a
        """
    try:
        # Request completion from GPT-4
        response = openai.ChatCompletion.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=4000,
            temperature=0,
        )
        return response.choices[0].message['content']
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

# API Endpoints
@app.get("/")
async def root():
    return {
        "message": [
            "Welcome to the Arabic Word Forms API!",
            "Use /getWordForms?word=word to get word forms.",
            "Use /getStems?word=word to get stems."
        ]
    }

@app.get("/getWordForms")
async def get_word_forms_api_get(word: Optional[str] = None):
    if not word:
        raise HTTPException(status_code=400, detail="Please provide a word as a query parameter")

    # Call the existing logic
    result = await get_word_forms(word)
    word_forms = parse_response_to_json(result)
    return {"wordForms": word_forms}


@app.post("/getWordForms")
async def get_word_forms_api(word: str = Form(...)):
    if not word:
        raise HTTPException(status_code=400, detail="Please provide a word")
    
    # Fetch word forms using the helper function
    result = await get_word_forms(word)
    word_forms = parse_response_to_json(result)
    return {"wordForms": word_forms}