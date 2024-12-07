from typing import Optional
from fastapi import FastAPI, HTTPException, Form
from fastapi.responses import HTMLResponse
from fastapi.responses import FileResponse
from gtts import gTTS
import openai
from openai import OpenAI
import os
import hashlib
import logging
import asyncio
import datetime

# Initialize FastAPI
app = FastAPI()

# Load OpenAI API key from environment variables
openai.api_key = os.environ.get('OPENAI_API_KEY')


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
    unique_number = f"{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"
    return f"{safe_name}_{unique_number}.{extension}"

def generate_audio_for_form(form: str) -> Optional[str]:
    try:
        client = OpenAI(api_key=os.environ.get('OPENAI_API_KEY'))
        # Log the form being processed
        print(f"Generating audio for form: {form}")

        # Validate the input
        if not form or not isinstance(form, str):
            raise ValueError(f"Invalid form: {form}")

        # Check if the form contains spaces to determine reading mode
        if " " in form:
            # If spaced, interpret each letter separately
            tts_input = " ".join(form.split())
        else:
            # If no spaces, interpret as a normal word
            tts_input = form

        print(f"Input for TTS: {tts_input}")

        # Base URL for the audio files
        file_name = generate_safe_file_name(form)
        speech_file_path = os.path.join(SAVE_PATH, file_name) # env saved file  
        audio_url = f"{BASE_URL}/files/{file_name}" # an accessible path to the voice file


        # Replace this with your TTS client call
        response = client.audio.speech.create(
            model="tts-1",
            voice="alloy",
            input=form
        )

        # Save the MP3 file to the specified path
        with open(speech_file_path, "wb") as f:
            f.write(response.content)

        # Return the audio file's URL
        print(f"Audio successfully generated: {audio_url}")
        return audio_url

    except Exception as e:
        # Log any error and return "null" as a fallback
        print(f"Error generating audio for {form}: {e}")
        return "null"


####### Emg. Abdullah's code -- No changes ########


def parse_response_to_json(response_text, endpoint_type):
    """
    Parses a plain-text response into JSON format based on the endpoint type.
    Ensures consistent formatting by removing unnecessary numbering or extra text.
    """

    print(f"{endpoint_type}_RESPONSE: %s" % response_text)
    if endpoint_type == "wordForms":
        word_forms = []

        for line in response_text.strip().split("\n"):
            parts = line.split(":")
            if len(parts) < 2:  # Skip malformed lines without a colon
                continue

            # Extract the form and remove numbering if present
            form = parts[0].strip("- ").strip()
            if form[0].isdigit() and form[1] in [".", " "]:
                # Remove leading numbers like "1. "
                form = form.split(".", 1)[1].strip()

            attributes = [attr.strip() for attr in parts[1].split(",")]

            # Ensure there are 5 attributes (aspect, gender, number, person, voice)
            if len(attributes) != 5:
                continue

            word_forms.append({
                "formRepresentations": {
                    "form": form,
                    "aspect": attributes[0],          # P, S, or F
                    "gender": attributes[1],         # m or f
                    "numberWordForm": attributes[2],  # 1, 2, or 3
                    "person": attributes[3],         # 1, 2, or 3
                    "voice": attributes[4]           # a or p
                },
            })

        return {"wordForms": word_forms}

    elif endpoint_type == "dialect":
        return {"dialect": response_text.strip()}

    elif endpoint_type == "phonetic":
        return {"phonetic": response_text.strip()}

    elif endpoint_type == "stems":
        stems = []

        for line in response_text.strip().split("\n"):
            # Skip empty or malformed lines
            if not line.strip() or ":" not in line:
                print(f"Skipping line due to missing ':' separator: {line}")
                continue

            try:
                # Split the line into form and attributes
                parts = line.split(":", 1)
                form = parts[0].strip("- ").strip()  # Extract the form

                # Extract attributes using maxsplit to avoid splitting inside the audio URL
                raw_attributes = parts[1].strip()
                attributes = raw_attributes.split(
                    ",", maxsplit=3)  # Limit splitting to 3 parts

                # Debugging attributes
                print(f"Parsing line: {line}")
                print(f"Extracted attributes: {attributes}")

                # Ensure there are at least 3 attributes (phonetic, dialect, type)
                if len(attributes) < 3:
                    print(
                        f"Skipping line due to insufficient attributes: {line}")
                    continue
                audio_url = generate_audio_for_form(form)
                # append attributes into stems
                stems.append({
                    "formRepresentations": {
                        "form": form,
                        "phonetic": attributes[0].strip(),
                        "dialect": attributes[1].strip(),
                        "audio": audio_url
                    },
                    # Type (e.g., stem, derived, inflection)
                    "type": attributes[3].strip()
                })

            except Exception as e:
                # Log the error and skip the malformed line
                print(f"Error processing line: {line} - Error: {e}")
                continue

        return {"stems": stems}

    if endpoint_type == "definition":
        response_text = response_text.replace("،", ",")
        definition = {
            "statement": None,
            "textRepresentations": []
        }

        for line in response_text.strip().split("\n"):
            # Skip empty or malformed lines
            if not line.strip() or ":" not in line:
                print(f"Skipping malformed line: {line}")
                continue

            try:
                # Remove leading '- ' and strip whitespace
                line = line.lstrip("- ").strip()

                # Split into type (Statement or TextRepresentation) and the rest
                type_and_fields = line.split(":", 1)
                if len(type_and_fields) != 2:
                    print(f"Skipping malformed line: {line}")
                    continue

                line_type, fields = type_and_fields[0].strip(
                ), type_and_fields[1].strip()

                # Split fields from the right into 4 parts
                attributes = fields.rsplit(",", 3)
                if len(attributes) != 4:
                    print(
                        f"Skipping malformed line due to insufficient attributes: {line}")
                    continue

                # Extract attributes
                form, dialect, phonetic, audio = map(str.strip, attributes)

                if line_type == "Statement":
                    # Parse the statement
                    definition["statement"] = {
                        "form": form,
                        "dialect": dialect,
                        "phonetic": phonetic,
                        "audio": audio
                    }
                elif line_type == "TextRepresentation":
                    # Parse the text representation
                    definition["textRepresentations"].append({
                        "form": form,
                        "dialect": dialect,
                        "phonetic": phonetic,
                        "audio": audio
                    })

            except Exception as e:
                print(f"Error processing line: {line} - {e}")
                continue

        return {"definition": definition}
    if endpoint_type == "translations":
        translations = []

        for line in response_text.strip().split("\n"):
            # Skip empty or malformed lines
            if not line.strip() or ":" not in line:
                print(f"Skipping malformed line: {line}")
                continue

            try:
                # Remove the leading '- ' if present
                line = line.lstrip("- ").strip()

                # Split into type and fields
                parts = line.split(":", 1)
                if len(parts) != 2:
                    print(f"Skipping malformed line: {line}")
                    continue

                # Extract fields
                language = parts[0].strip()
                fields = parts[1].strip()

                # Split fields from the right into 4 parts
                attributes = fields.rsplit(",", 3)
                if len(attributes) != 4:
                    print(f"Skipping malformed line: {line}")
                    continue

                # Extract attributes
                form, phonetic, dialect, audio = map(str.strip, attributes)
                audio_url = generate_audio_for_form(form)

                # Append the parsed translation
                translations.append({
                    "language": language,
                    "form": form,
                    "phonetic": phonetic,
                    "dialect": dialect,
                    "audio": audio_url
                })

            except Exception as e:
                print(f"Error processing line: {line} - {e}")
                continue

        return {"translations": translations}
    if endpoint_type == "examples":
        examples = []

        for line in response_text.strip().split("\n"):
            # Skip empty or malformed lines
            if not line.strip() or ":" not in line:
                print(f"Skipping malformed line: {line}")
                continue

            try:
                # Remove the leading '- ' if present
                line = line.lstrip("- ").strip()

                # Split into fields
                parts = line.split(":", 1)
                if len(parts) != 2:
                    print(f"Skipping malformed line: {line}")
                    continue

                # Extract fields
                form = parts[0].strip()
                fields = parts[1].strip()

                # Split fields from the right into 5 parts
                attributes = fields.rsplit(",", 5)
                if len(attributes) != 6:
                    print(f"Skipping malformed line: {line}")
                    continue

                # Extract attributes
                phonetic, dialect, audio, example_type, show_in_results, source = map(
                    str.strip, attributes)

                # Convert showInResults to boolean
                show_in_results = show_in_results.lower() == "true"
                audio_url = generate_audio_for_form(form)

                # Append the parsed example
                examples.append({
                    "form": form,
                    "phonetic": phonetic,
                    "dialect": dialect,
                    "audio": audio_url,
                    "exampleType": example_type,
                    "showInResults": show_in_results,
                    "source": source
                })

            except Exception as e:
                print(f"Error processing line: {line} - {e}")
                continue

        return {"examples": examples}
    if endpoint_type == "contexts":
        contexts = []

        for line in response_text.strip().split("\n"):
            # Skip empty or malformed lines
            if not line.strip() or ":" not in line:
                print(f"Skipping malformed line: {line}")
                continue

            try:
                # Remove the leading '- ' if present
                line = line.lstrip("- ").strip()

                # Split into fields
                parts = line.split(":", 1)
                if len(parts) != 2:
                    print(f"Skipping malformed line: {line}")
                    continue

                # Extract fields
                form = parts[0].strip()
                fields = parts[1].strip()

                # Split fields from the right into 5 parts
                attributes = fields.rsplit(",", 5)
                if len(attributes) != 6:
                    print(f"Skipping malformed line: {line}")
                    continue

                # Extract attributes
                phonetic, dialect, audio, index, record_id, show_in_results = map(
                    str.strip, attributes)

                # Convert `index` and `recordId` to integers
                index = int(index)
                record_id = int(record_id)

                # Convert showInResults to boolean
                show_in_results = show_in_results.lower() == "true"
                audio_url = generate_audio_for_form(form)

                # Append the parsed context
                contexts.append({
                    "form": form,
                    "phonetic": phonetic,
                    "dialect": dialect,
                    "audio": audio_url,
                    "index": index,
                    "recordId": record_id,
                    "showInResults": show_in_results
                })

            except Exception as e:
                print(f"Error processing line: {line} - {e}")
                continue

        return {"contexts": contexts}

    else:
        raise ValueError(f"Unknown endpoint type: {endpoint_type}")



async def generate_response_from_gpt(prompt):
    """
    Sends a prompt to GPT-4o and returns the response text.
    """
    try:
        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=4000,
            temperature=0,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error with GPT-4: {str(e)}")


@ app.get("/", response_class=HTMLResponse)
async def read_root():
    """
    Renders the HTML form for word input.
    """
    html_content = """
    <html>
        <head>
            <title>Arabic Word Forms</title>
        </head>
        <body>
            <h1>Arabic Word Forms</h1>
            <form action="/getWordForms" method="post">
                <label for="word">Enter Arabic Word:</label>
                <input type="text" id="word" name="word" required>
                <button type="submit">Submit</button>
            </form>
        </body>
    </html>
    """
    return HTMLResponse(content=html_content)






@app.get("/getAudio/{word}")
async def get_audio(word: str):
    """
    Retrieves or generates an audio file for the given word.

    Args:
        word (str): The word for which the audio URL is requested.

    Returns:
        dict: A dictionary containing the audio URL.
    """
    try:
        # Check for a valid word
        if not word:
            raise HTTPException(
                status_code=400, detail="Please provide a valid word.")

        # Generate audio and retrieve the URL
        audio_url = generate_audio_for_form(word)

        # Return the audio URL
        return {"audio_url": audio_url}

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error generating audio for {word}: {str(e)}")


@ app.get("/getWordForms")
async def get_word_forms_api(word: str):
    """
    Endpoint to generate word forms for the given Arabic word.
    """
    if not word:
        raise HTTPException(status_code=400, detail="Please provide a word.")
    prompt = f"""
        Please generate all word forms for the Arabic word: {word}.
        The response should include variations based on the following criteria:
        - Start with singular (المفرد), followed by dual (التثنية), and then plural (الجمع).
        - For each category (singular, dual, plural), list forms by gender: Masculine (m) first, then Feminine (f).
        - Ensure the forms are arranged logically based on their grammatical output.

        The response should include variations based on the following detailed criteria:
        - Tense: Past (P), Present (S), or Future (F).
        - Gender: Masculine (m) or Feminine (f).
        - Number: Singular (1), Dual (2), or Plural (3).
        - Person: First person (1), Second person (2), or Third person (3).
        - Voice: Active (a) or Passive (p).
        - make sure to Diacritize the words 

        Provide the output in a plain text list format, sorted as described above, with one form per line, as follows:
        - <word>: <tense>, <gender>, <number>, <person>, <voice>

        For example:
        - ضحك: P, m, 1, 3, a
        - ضحكت: P, f, 1, 3, a
        - ضحكا: P, m, 2, 3, a
        - ضحكتا: P, f, 2, 3, a
        - يضحك: S, m, 1, 3, a
        """

    # Request GPT response
    result = await generate_response_from_gpt(prompt)

    # Parse the OpenAI response
    parsed_response = parse_response_to_json(result, "wordForms")


    # Return the parsed response
    return parsed_response


@ app.get("/getDialect")
async def get_dialect_api(word: str):
    """
    Endpoint to get the dialect of the given Arabic word.
    """
    if not word:
        raise HTTPException(status_code=400, detail="Please provide a word.")

    prompt = f"""
        What is the dialect of the Arabic word '{word}'?
        Give me a very short and simple answer in Arabic. 
        make sure if the word is MSA print "فُصحى" but if there is no other choice classify it from the main seven Arab dialects choose it from them and do not only print "عامية"
        Make sure The response should be in one word like: (answer) """
    result = await generate_response_from_gpt(prompt)

    # Parse the OpenAI response
    parsed_response = parse_response_to_json(result, "dialect")


    # Return the parsed response
    return parsed_response


@ app.get("/getPhonetic")
async def get_phonetic_api(word: str):
    """
    Endpoint to get the phonetic representation of the given Arabic word. start with verbs and if the word not a verb return the noun
    """
    if not word:
        raise HTTPException(status_code=400, detail="Please provide a word.")

    prompt = f"""
        Provide the phonetic representation of the Arabic word '{word}'.
         start with verbs phonetics and if the word not a verb return the noun phonetic nothing else 
        Make sure to ONLY Give the phonetic representation"""
    result = await generate_response_from_gpt(prompt)

    # Parse the OpenAI response
    parsed_response = parse_response_to_json(result, "phonetic")


    # Return the parsed response
    return parsed_response


@ app.get("/getStems")
async def get_stems(word: str):
    """
    Endpoint to return a list of stems for the given Arabic word.
    """
    if not word:
        raise HTTPException(
            status_code=400, detail="The 'word' parameter is required.")

    # Prompt to generate stems
    prompt = f"""
        Please generate a list of stems (roots) for the Arabic word: {word}.
        The response should include stems organized in the following format:
        - For each stem, include:
        - The written stem form from the given word and make it complete word not letters eg لعب as a word.
        - Phonetic transcription (phonetic).
        - Dialect (e.g., Standard Arabic, Egyptian Arabic, etc.).
        - Audio pronunciation URL (audio).
        - Type of the root (e.g., root, stem).
        - return one stem and one root

        Provide the output in a plain text list format, one stem per line, as follows:
        - <form>: <phonetic>, <dialect>, <audio>, <type>

        """

    # Request GPT response
    result = await generate_response_from_gpt(prompt)

    # Parse the OpenAI response
    parsed_response = parse_response_to_json(result, "stems")

    # Return the parsed response
    return parsed_response


@ app.get("/getDefinition")
async def get_definition(word: str):
    """
    Endpoint to fetch the definition of a given Arabic word.
    """
    if not word:
        raise HTTPException(status_code=400, detail="Please provide a word.")

    # Generate the OpenAI prompt
    prompt = f"""
        Please generate a definition object for the Arabic word: {word}.
        The response should include:
        1. A single-word statement with:
        - The written word (form).
        - The dialect (e.g., Standard Arabic, Egyptian Arabic, etc.).
        - The phonetic transcription (phonetic).
        - Audio pronunciation URL (audio) as "null".

        2. A list of complete text representations with:
        - The full definition text (form). Ensure the definition is complete and does not end with "...".
        - The dialect (e.g., Standard Arabic, Egyptian Arabic, etc.).
        - Phonetic transcription as "null".
        - Audio pronunciation URL as "null".

        Provide the output in a plain text list format with the following structure:
        - Statement: <form>, <dialect>, <phonetic>, <audio>
        - TextRepresentation: <form>, <dialect>, <phonetic>, <audio>

        For example:
        - Statement: ضريبة, Standard Arabic, /dˤariːba/, null
        - TextRepresentation: (ضَريبةُ) هي مَبالغ تُفرض على الأفراد أو الشركات والتي تشمل ضرائب الدخل والضريبة المضافة، Standard Arabic, null, null
        - TextRepresentation: الضَّريبةُ تُستخدم لتمويل الخدمات العامة والمشاريع الحكومية بشكل كامل، Standard Arabic, null, null
        """

    # Request GPT response
    result = await generate_response_from_gpt(prompt)

    # Parse the OpenAI response
    parsed_response = parse_response_to_json(result, "definition")


    # Return the parsed response
    return parsed_response


@app.get("/getSenseTranslation")
async def get_sense_translation(word: str, session):
    """
    Endpoint to fetch translations for the given Arabic word.
    """
    if not word:
        raise HTTPException(status_code=400, detail="Please provide a word.")

    # Generate the OpenAI prompt
    prompt = f"""
    Please generate a list of translations for the Arabic word: {word}.
    The response should include translations in different languages, with the following details for each translation:
    - Language (e.g., "en" for English, "fr" for French, etc.).
    - Translated text (form).
    - Phonetic transcription (phonetic).
    - Dialect (e.g., "American English", "French", etc.).
    - Audio pronunciation URL (audio)[Leave as null].
    - Targetted languages: english, french, chinese, and russuian

    Provide the output in a plain text list format, one translation per line, as follows:
    - <language>: <form>, <phonetic>, <dialect>, <audio>

    For example:
    - en: Who touches a sensitive spot, hu: ˈtʌʧɪz ə ˈsɛnsɪtɪv spɑːt, American English, https://example.com/audio.mp3
    - fr: Qui touche un point sensible, ki tuʃ œ̃ pwɛ̃ sɑ̃sibl, French, https://example.com/audio_fr.mp3
    """

    # Request GPT response
    result = await generate_response_from_gpt(prompt)

    # Parse the OpenAI response
    parsed_response = parse_response_to_json(result, "translations")


    # Return the parsed response
    return parsed_response


@app.get("/getExamples")
async def get_examples(word: str):
    """
    Endpoint to fetch examples for the given Arabic word.
    """
    if not word:
        raise HTTPException(status_code=400, detail="Please provide a word.")

    # Generate the OpenAI prompt
    prompt = f"""
    Please generate a list of examples for the Arabic word: {word}.
    The response should include examples demonstrating the usage of the word, with the following details for each example:
    - The example text (form).
    - Phonetic transcription (phonetic).
    - Dialect (e.g., "Standard Arabic", "Quranic Arabic", etc.).
    - Audio pronunciation URL (audio)[Leave as null].
    - Example type (exampleType) such as "saying", "proverb", "quranic", etc.
    - Whether to show this example in results (showInResults) as true or false.
    - The source of the example (source), such as an author, a proverb, or "Quran".
    - for the "Quran" and poems example, make sure to 100% accurate results.

    Provide the output in a plain text list format, one example per line, as follows:
    - <form>: <phonetic>, <dialect>, <audio>, <exampleType>, <showInResults>, <source>

    For example:
    - أَحِنُّ إِلى ضَربِ السُيوفِ القَواضِبِ...: ʔaˈħinnu ʔilaː ðˤarb as-suyuf..., Standard Arabic, https://example.com/audio1.mp3, saying, true, عنترة بن شداد
    - الضَربُ لا يُعَلِّمُ الحكمةَ...: aḍ-ḍarb lā yuʿallimu al-ḥikma..., Standard Arabic, https://example.com/audio2.mp3, proverb, true, قول مأثور
    - وَإِذا ضُرِبَ بِالمِعْوَلِ فِي الأرض...: wa ʔiða ḍuriba bil-miʿwal fiː al-ʔardˤ..., Quranic Arabic, https://example.com/audio3.mp3, quranic, true, القرآن الكريم
    """

    # Request GPT response
    result = await generate_response_from_gpt(prompt)

    # Parse the OpenAI response
    parsed_response = parse_response_to_json(result, "examples")


    # Return the parsed response
    return parsed_response


@app.get("/getContexts")
async def get_contexts(word: str):
    """
    Endpoint to fetch contexts where the given Arabic word is used.
    """
    if not word:
        raise HTTPException(status_code=400, detail="Please provide a word.")

    # Generate the OpenAI prompt
    prompt = f"""
    Please generate a list of contexts where the Arabic word: {word} shows how it is used in a sentence.
    The response should include the following details for each context:
    - The context text (form).
    - Phonetic transcription (phonetic).
    - Dialect (e.g., "Standard Arabic", "Egyptian Arabic", etc.).
    - Audio pronunciation URL (audio)[Leave as null].
    - Context index (index), starting from 1 and incrementing for each context.
    - Record ID (recordId) for the context, [Leave as 0].
    - Whether to show this context in results (showInResults) as true.

    Provide the output in a plain text list format, one context per line, as follows:
    - <form>: <phonetic>, <dialect>, <audio>, <index>, <recordId>, <showInResults>

    For example:
    - تُستخدم الكلمة عند الحديث عن الضرائب.: tuʔstamalu al-kalimatu ʕinda al-ħadiθ ʕan aḍ-ḍaraːʔib, Standard Arabic, https://example.com/audio_tax.mp3, 1, 1001, true
    - الكلمة تُشير إلى نوع من الهجوم بالسيف.: al-kalimatu tuʃiːru ʔilaː nauʕ min al-hujum bi-s-sayf, Standard Arabic, https://example.com/audio_sword.mp3, 2, 1002, true
    """

    # Request GPT response
    result = await generate_response_from_gpt(prompt)

    # Parse the OpenAI response
    parsed_response = parse_response_to_json(result, "contexts")


    # Return the parsed response
    return parsed_response





############ Need to get the file from render ########



@app.get("/files/{file_name}")
async def get_file(file_name: str):
    """
    Serve the saved voice file without explicitly decoding the URL.
    """
    # Use the file_name directly as provided in the URL
    file_path = os.path.join(SAVE_PATH, file_name)

    logging.info(f"Requested file path: {file_path}")

    # Check if the file exists
    if os.path.exists(file_path):
        logging.info(f"File found: {file_path}")
        return FileResponse(file_path, media_type="audio/mpeg", filename=file_name)
    
    logging.error(f"File not found: {file_path}")
    raise HTTPException(status_code=404, detail="File not found")