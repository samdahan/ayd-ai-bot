import requests
import json

api_key = "AIzaSyC61lCGGbONQDy_5bz5pivFDSv9VbncUlw"
url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"

try:
    resp = requests.get(url)
    if resp.status_code == 200:
        models = resp.json().get('models', [])
        for m in models:
            print(f"- {m['name']}")
    else:
        print(f"Error {resp.status_code}: {resp.text}")
except Exception as e:
    print(f"Exception: {e}")
