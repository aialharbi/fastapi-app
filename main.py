from typing import Optional
from fastapi import FastAPI, HTTPException, Form
from fastapi.responses import HTMLResponse
from fastapi.responses import FileResponse
from gtts import gTTS
import openai
import os
import hashlib
import logging
import asyncio

# Initialize FastAPI
app = FastAPI()

# Load OpenAI API key from environment variables
openai.api_key = os.environ.get('OPENAI_API_KEY')

#######################
#test voice

# Path to save audio files (persistent disk or local directory)
SAVE_PATH = "/var/data"

# Ensure SAVE_PATH exists
os.makedirs(SAVE_PATH, exist_ok=True)

# Base URL for your service (adjust for your deployment environment)
BASE_URL = "https://fastapi-app-gx34.onrender.com"




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
async def get_word_forms_api(word: str, session: Session = Depends(get_session)):
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

    # Save the parsed response in the database
    save_request(word=word, endpoint="wordForms",
                 response=parsed_response, session=session)

    # Return the parsed response
    return parsed_response


@ app.get("/getDialect")
async def get_dialect_api(word: str, session: Session = Depends(get_session)):
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

    # Save the parsed response in the database
    save_request(word=word, endpoint="dialect",
                 response=parsed_response, session=session)

    # Return the parsed response
    return parsed_response


@ app.get("/getPhonetic")
async def get_phonetic_api(word: str, session: Session = Depends(get_session)):
    """
    Endpoint to get the phonetic representation of the given Arabic word. start with verbs and if the word not a verb return the noun
    """
    if not word:
        raise HTTPException(status_code=400, detail="Please provide a word.")

    prompt = f"""
        Provide the phonetic representation of the Arabic word '{word}'.
         start with verbs phonetics and if the word not a verb return the noun phonetic nothing else 
        Make sure to Give me a very short and simple answer."""
    result = await generate_response_from_gpt(prompt)

    # Parse the OpenAI response
    parsed_response = parse_response_to_json(result, "phonetic")

    # Save the parsed response in the database
    save_request(word=word, endpoint="phonetic",
                 response=parsed_response, session=session)

    # Return the parsed response
    return parsed_response


@ app.get("/getStems")
async def get_stems(word: str, session: Session = Depends(get_session)):
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

    # Save the parsed response in the database
    save_request(word=word, endpoint="stems",
                 response=parsed_response, session=session)

    # Return the parsed response
    return parsed_response


@ app.get("/getDefinition")
async def get_definition(word: str, session: Session = Depends(get_session)):
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

    # Save the parsed response in the database
    save_request(word=word, endpoint="definition",
                 response=parsed_response, session=session)

    # Return the parsed response
    return parsed_response


@app.get("/getSenseTranslation")
async def get_sense_translation(word: str, session: Session = Depends(get_session)):
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

    # Save the parsed response in the database
    save_request(word=word, endpoint="translations",
                 response=parsed_response, session=session)

    # Return the parsed response
    return parsed_response


@app.get("/getExamples")
async def get_examples(word: str, session: Session = Depends(get_session)):
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

    # Save the parsed response in the database
    save_request(word=word, endpoint="examples",
                 response=parsed_response, session=session)

    # Return the parsed response
    return parsed_response


@app.get("/getContexts")
async def get_contexts(word: str, session: Session = Depends(get_session)):
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

    # Save the parsed response in the database
    save_request(word=word, endpoint="contexts",
                 response=parsed_response, session=session)

    # Return the parsed response
    return parsed_response