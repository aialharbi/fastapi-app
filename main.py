from typing import Optional
from fastapi import FastAPI, HTTPException, Form
from fastapi.responses import HTMLResponse
from fastapi.responses import FileResponse
from gtts import gTTS
import openai
import os
import hashlib
import logging

# Initialize FastAPI
app = FastAPI()

# Load OpenAI API key from environment variables
openai.api_key = os.environ.get('OPENAI_API_KEY')

def parse_response_to_json(response_text):

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

#######################
#test voice

# Path to save audio files (persistent disk or local directory)
SAVE_PATH = "/var/data"

# Ensure SAVE_PATH exists
os.makedirs(SAVE_PATH, exist_ok=True)


# Base URL for your service (adjust for your deployment environment)
BASE_URL = "https://fastapi-app-gx34.onrender.com"


def generate_safe_file_name(word: str, extension="mp3"):
    """
    Generate a safe, unique file name using a hash.
    """
    hash_object = hashlib.md5(word.encode("utf-8"))
    safe_name = hash_object.hexdigest()
    return f"{safe_name}.{extension}"


def generate_voice(word: str, file_name: str):
    """
    Convert text to speech using gTTS and save the audio file locally.
    """
    file_path = os.path.join(SAVE_PATH, file_name)
    tts = gTTS(word, lang='ar')
    tts.save(file_path)
    logging.info(f"Voice file saved at: {file_path}")
    return file_path

# @app.get("/getVoice")
# async def get_voice(word: str):
#     """
#     Generate and return an accessible path to the voice file.
#     """
#     if not word:
#         raise HTTPException(status_code=400, detail="Word parameter is required.")
#     try:
#         # Generate the voice file
#         file_name = generate_safe_file_name(word)
#         file_path = generate_voice(word, file_name)
#         logging.info(f"File generated successfully: {file_path}")
#         # Return the accessible path
#         accessible_path = f"{BASE_URL}/files/{file_name}"
#         return {"success": True, "file_url": accessible_path}
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"Error generating voice: {str(e)}")


# @app.get("/files/{file_name}")
# async def get_file(file_name: str):
#     """
#     Serve the saved voice file without explicitly decoding the URL.
#     """
#     # Use the file_name directly as provided in the URL
#     file_path = os.path.join(SAVE_PATH, file_name)

#     logging.info(f"Requested file path: {file_path}")

#     # Check if the file exists
#     if os.path.exists(file_path):
#         logging.info(f"File found: {file_path}")
#         return FileResponse(file_path, media_type="audio/mpeg", filename=file_name)
    
#     logging.error(f"File not found: {file_path}")
#     raise HTTPException(status_code=404, detail="File not found")

##########
# second api

def parse_stems_response_with_audio(response_text: str, audio_generator):
    """
    Parses a plain-text response of stems into a JSON-like structure, 
    adding audio links from an external method.
    """
    stems = []
    for line in response_text.strip().split("\n"):
        if not line.strip() or not line.startswith("-"):
            continue  # Skip empty or invalid lines

        # Remove the dash and split the attributes
        parts = line.strip("- ").split(";")
        if len(parts) < 4:
            continue  # Skip malformed lines

        form, phonetic, dialect, root_type = map(str.strip, parts)

        # Generate the audio link using the external method
        audio_link = audio_generator(form)

        stems.append({
            "formRepresentations": {
                "form": form,
                "phonetic": phonetic,
                "dialect": dialect,
                "audio": audio_link  # Add the generated audio link
            },
            "type": root_type
        })

    return {"stems": stems}

# Example external audio generator method
def generate_audio_link(form):
    file_name = generate_safe_file_name(form)
    file_path = generate_voice(form, file_name)
    return f"{BASE_URL}/files/{file_name}"


# Helper function to generate word forms using OpenAI API
async def getStems(word: str):
    prompt = f"""
    Please generate all stems (roots) for the Arabic word: {word}.
    The response should include the following information for each stem:
    - The root written in Arabic (form).
    - The phonetic transcription (phonetic) of the root.
    - The dialect (e.g., "Standard Arabic", "Egyptian Arabic").
    - The type of the root, which should always be "root".

    Provide the output in a plain text list format, where each stem is on a new line and attributes are separated by semicolons (;), as follows:
    <root in Arabic>; <phonetic transcription>; <dialect>; <type>

    Here is an example for the input word "ضرب":
    - ض ر ب; dˤa-ra-ba; Standard Arabic; root
    - ضرب; daraba; Egyptian Arabic; root

    Ensure each attribute is provided for every stem, and ensure there are no missing fields. Do not include JSON formatting in your response.
    """
    try:
        # Request completion from GPT-4
        response = openai.ChatCompletion.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=4000,
            temperature=0,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")



@app.get("/getStems")
async def get_getStems_api_get(word: Optional[str] = None):
    if not word:
        raise HTTPException(status_code=400, detail="Please provide a word as a query parameter")

    # Call the existing logic
    result = await getStems(word)
    # url_audio = generate_audio_link(word)
    url_audio = 'test.mp3'
    stems = parse_stems_response_with_audio(result,url_audio)
    return {"wordForms": stems}