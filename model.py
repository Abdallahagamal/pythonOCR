import requests

OPENROUTER_API_KEY = "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"  # replace with your key


# Fallback chain — tried in order if rate-limited or unavailable
MODELS = [
    "meta-llama/llama-3.3-70b-instruct:free",   # best free, strong Arabic
    "mistralai/mistral-7b-instruct:free",         # reliable fallback
    "microsoft/phi-3-mini-128k-instruct:free",    # lightweight last resort
]


class RateLimitError(Exception):
    pass


def _call_model(model, messages, headers):
    url = "https://openrouter.ai/api/v1/chat/completions"
    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.1,
    }
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=30)
    except requests.exceptions.RequestException as e:
        raise ConnectionError(f"Network error: {e}")

    if response.status_code == 429:
        raise RateLimitError(f"Rate limited on {model}")

    if response.status_code != 200:
        raise RuntimeError(f"API error {response.status_code} on {model}: {response.text}")

    data = response.json()
    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as e:
        raise RuntimeError(f"Unexpected response shape from {model}: {e} — {data}")

    if not isinstance(content, str):
        raise RuntimeError(f"Non-string content from {model}: {type(content)}")

    return content


def ask_model(user_text, system_prompt=None):
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost",
    }

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": user_text})

    last_error = None
    for model in MODELS:
        try:
            print(f"[model] Trying {model}...")
            content = _call_model(model, messages, headers)
            print(f"[model] Success with {model}")
            return content
        except RateLimitError as e:
            print(f"[model] {e} — trying next...")
            last_error = e
        except (ConnectionError, RuntimeError) as e:
            print(f"[model] Error: {e} — trying next...")
            last_error = e

    raise RuntimeError(f"All models failed. Last error: {last_error}")