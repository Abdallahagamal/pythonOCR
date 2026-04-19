import json
import re
import base64
import requests
import os

from ocr import clean_text, extract_header_name, extract_phone, ocr_image

OPENROUTER_API_KEY = "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"

VISION_MODELS = [
    "openrouter/auto",
    "meta-llama/llama-4-maverick:free",
    "qwen/qwen2.5-vl-72b-instruct:free",
    "google/gemma-3-27b-it:free",
    "mistralai/mistral-small-3.1-24b-instruct:free",
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


def infer_gender(name):
    if not name or name == "unknown":
        return "unknown"

    lower_name = name.strip().lower()
    female_suffixes = ("ة", "ى", "ين", "نور", "لين", "ريم", "سلمى", "بسمة", "هان")
    if any(lower_name.endswith(suffix) for suffix in female_suffixes):
        return "female"

    female_names = {
        "maya", "sara", "sarah", "mona", "nour", "noor", "reem", "raneem",
        "fatma", "fatima", "nada", "aya", "yara", "lana", "lina", "leen",
    }
    first_token = re.split(r"\s+", lower_name)[0]
    if first_token in female_names:
        return "female"

    return "male"


def infer_contact_method(text, phone):
    lowered = text.lower()
    if any(keyword in lowered for keyword in ("واتساب", "واتس اب", "whatsapp")):
        return "WhatsApp"
    if any(keyword in lowered for keyword in ("مكالمة", "call")):
        return "Call"
    if phone:
        return "WhatsApp or Call"
    return "unknown"


def infer_branch(text):
    branch_keywords = [
        "الشروق",
        "المقطم",
        "مصر الجديدة",
        "التجمع",
        "مدينة نصر",
        "الشيخ زايد",
        "6 أكتوبر",
        "الرحاب",
        "المعادي",
    ]

    for branch in branch_keywords:
        if branch in text:
            return branch

    return "unknown"


def ocr_fallback(image_path):
    raw_text = clean_text(ocr_image(image_path))
    client_name = extract_header_name(raw_text) or "unknown"
    client_phone = extract_phone(raw_text)
    if client_phone:
        client_phone = normalize_phone(client_phone)

    return {
        "client_name": client_name,
        "client_phone": client_phone or "unknown",
        "gender": infer_gender(client_name),
        "contact_method": infer_contact_method(raw_text, client_phone),
        "branch": infer_branch(raw_text),
    }


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

    print(f"[ocr] Falling back to local OCR after model failures: {last_error}")
    return ocr_fallback(image_path)


if __name__ == "__main__":
    import sys
    image_path = sys.argv[1] if len(sys.argv) > 1 else "test2.jpg"
    result = extract_client(image_path)
    print(json.dumps(result, ensure_ascii=False, indent=2))