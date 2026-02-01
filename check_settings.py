
import requests
import json
import sys

# Encode for Windows Console
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

ID_INSTANCE = "7103495194"
API_TOKEN = "c01223dea0844ae195759cac8585aaf96f1d1be3dffa47bc83"
API_URL = f"https://7103.api.greenapi.com/waInstance{ID_INSTANCE}"

def get_settings():
    print("--- Getting Settings ---")
    url = f"{API_URL}/getSettings/{API_TOKEN}"
    try:
        resp = requests.get(url)
        print(json.dumps(resp.json(), indent=2))
    except Exception as e:
        print(f"Error: {e}")

def get_last_messages():
    print("\n--- Last 5 Incoming Messages (History) ---")
    url = f"{API_URL}/lastIncomingMessages/{API_TOKEN}" # ?minutes=60 could be added
    try:
        resp = requests.get(url)
        data = resp.json()
        for msg in data[:5]: # Show last 5
             txt = "???"
             if msg.get('typeMessage') == 'textMessage':
                 txt = msg.get('textMessage')
             elif msg.get('typeMessage') == 'extendedTextMessage':
                 txt = msg.get('extendedTextMessageData', {}).get('text')
             
             print(f"[{msg.get('timestamp')}] {msg.get('chatId')}: {txt}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    get_settings()
    get_last_messages()
