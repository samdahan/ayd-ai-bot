
import requests
import json
import logging

logging.basicConfig(level=logging.INFO)

def call_gemini(api_key, prompt):
    models = [
        "gemini-2.0-flash", 
        "gemini-2.0-flash-lite", 
        "gemini-flash-latest",
        "gemini-pro-latest",
        "gemini-1.5-flash", 
        "gemini-1.5-pro"
    ]
    headers = {'Content-Type': 'application/json'}
    payload = {
        "contents": [{"parts": [{"text": prompt}]}]
    }

    for model in models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        try:
            print(f"Trying model {model}...")
            resp = requests.post(url, headers=headers, json=payload, timeout=20)
            print(f"Status Code: {resp.status_code}")
            if resp.status_code == 200:
                data = resp.json()
                if 'candidates' in data and len(data['candidates']) > 0:
                    return data['candidates'][0]['content']['parts'][0]['text'].strip()
            else:
                print(f"Error: {resp.text}")
        except Exception as e:
            print(f"Exception: {e}")
    return None

if __name__ == "__main__":
    with open('settings.json', 'r', encoding='utf-8') as f:
        settings = json.load(f)
    key = settings.get('gemini_api_key')
    print(f"Using key: {key}")
    res = call_gemini(key, "Hello, are you working?")
    print(f"Result: {res}")
