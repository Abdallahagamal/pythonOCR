import json
import re
import base64
import requests
import os

OPENROUTER_API_KEY = "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"

VISION_MODELS = [
    "openrouter/auto",
    "google/gemini-2.0-flash-exp:free",
    "google/gemini-2.5-pro-exp-03-25:free", 
    "meta-llama/llama-4-maverick:free",
    "qwen/qwen2.5-vl-72b-instruct:free",
    "google/gemma-4-26b-a4b-it:free",
]

PROMPT = """This is a Facebook Messenger screenshot from a business gym/fitness inbox.

CONTEXT:
- The business agent (staff) sends messages in BLUE bubbles on the RIGHT side.
- The CLIENT sends messages in GRAY/WHITE bubbles on the LEFT side.
- "Omar Ramzy" or any name appearing above a blue bubble = the AGENT. Ignore them.

YOUR TASKS:

1. CLIENT NAME:
   - Read the bold name in the TOP header bar of the chat (next to the profile picture at the top).
   - This is always the client's name, even if it looks like a fake or unusual name.
   - Do NOT use names from inside message bubbles.

2. CLIENT PHONE NUMBER:
   - Find the phone number sent by the CLIENT (in a gray/white bubble on the LEFT side).
   - IGNORE any phone number inside a BLUE bubble (those are the business's own hotline numbers).
   - Egyptian mobile numbers start with 01 and are exactly 11 digits.
   - Read each digit carefully.

3. GENDER:
   - Infer from the client name only.
   - Arabic female name endings: ة، ى، ين، نور، لين، ريم، سلمى، بسمة، هان
   - Common English female names by knowledge.
   - Return "male", "female", or "unknown".

4. CONTACT METHOD:
   - Did the client mention a preferred contact method?
   - واتساب / واتس اب → "WhatsApp"
   - مكالمة → "Call"
   - If the client just sent their number with no preference stated → "WhatsApp or Call"
5. BRANCH (فرع):
   - Did the client mention which branch they want?
   - Look for branch names like: الشروق، المقطم، مصر الجديدة، or any location name the client mentions.
   - Return the branch name in Arabic as-is.
   - If not mentioned → "unknown"
Return ONLY this JSON, no markdown, no explanation:
{"client_name": "...", "client_phone": "...", "gender": "...", "contact_method": "...", "branch": "..."}"""


class RateLimitError(Exception):
    pass


def encode_image(image_path):
    ext = image_path.lower().split(".")[-1]
    mime = "image/png" if ext == "png" else "image/jpeg"
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8"), mime


def _call_model(model, image_b64, mime, headers):
    payload = {
        "model": model,
        "temperature": 0.1,
        "messages": [{
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:{mime};base64,{image_b64}"}
                },
                {"type": "text", "text": PROMPT}
            ]
        }]
    }

    try:
        r = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers, json=payload, timeout=60
        )
    except requests.exceptions.RequestException as e:
        raise ConnectionError(f"Network error: {e}")

    if r.status_code == 429:
        raise RateLimitError(f"{model} rate limited")

    if r.status_code in (400, 404):
        raise RuntimeError(f"Model unavailable ({r.status_code}): {model}")

    if r.status_code != 200:
        raise RuntimeError(f"API {r.status_code} from {model}: {r.text}")

    data = r.json()
    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError):
        raise RuntimeError(f"Unexpected response: {data}")


def normalize_phone(raw):
    raw = str(raw).translate(str.maketrans('٠١٢٣٤٥٦٧٨٩', '0123456789'))
    raw = re.sub(r'[\s\-]', '', raw)
    m = re.search(r'01[0-9]{9}', raw)
    return m.group() if m else raw


def extract_client(image_path):
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost",
    }

    image_b64, mime = encode_image(image_path)
    last_error = None

    for model in VISION_MODELS:
        try:
            print(f"[model] Trying {model}...")
            raw = _call_model(model, image_b64, mime, headers)
            print(f"[model] Raw: {raw}")

            clean = re.sub(r'```(?:json)?', '', raw).strip().rstrip('`').strip()
            match = re.search(r'\{.*\}', clean, re.DOTALL)
            if not match:
                raise ValueError("No JSON found in response")

            result = json.loads(match.group())

            if result.get("client_phone"):
                result["client_phone"] = normalize_phone(result["client_phone"])

            print(f"[model] Success with {model}")
            return result

        except RateLimitError as e:
            print(f"[model] Rate limited — trying next...")
            last_error = e
        except (ConnectionError, RuntimeError, ValueError, json.JSONDecodeError) as e:
            print(f"[model] Failed: {e} — trying next...")
            last_error = e

    return {"error": f"All models failed. Last: {last_error}"}


if __name__ == "__main__":
    import sys
    image_path = sys.argv[1] if len(sys.argv) > 1 else "test2.jpg"
    result = extract_client(image_path)
    print(json.dumps(result, ensure_ascii=False, indent=2))