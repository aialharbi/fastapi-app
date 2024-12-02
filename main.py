from typing import Optional
from fastapi import FastAPI, HTTPException, Form
from fastapi.responses import HTMLResponse
import openai
import os

# Initialize FastAPI
app = FastAPI()

# Load OpenAI API key from environment variables
openai.api_key = os.getenv("OPENAI_API_KEY")

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
    """
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",
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
    return {"message": "Welcome to the Arabic Word Forms API!"}

@app.get("/getWordForms")
async def get_word_forms_api_get(word: Optional[str] = None):
    if not word:
        raise HTTPException(status_code=400, detail="Please provide a word as a query parameter")

    # Call the existing logic
    result = await get_word_forms(word)
    return {"wordForms": result}


@app.post("/getWordForms")
async def get_word_forms_api(word: str = Form(...)):
    if not word:
        raise HTTPException(status_code=400, detail="Please provide a word")
    
    # Fetch word forms using the helper function
    result = await get_word_forms(word)
    return {"wordForms": result}