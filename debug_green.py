import requests
import json
import time

# DETAILS
ID = "7103495194"
TOKEN = "c01223dea0844ae195759cac8585aaf96f1d1be3dffa47bc83"
URL = f"https://7103.api.greenapi.com/waInstance{ID}"
TEST_PHONE = "972515642201" # Your phone from config

print(">>> STATRING DIAGNOSITCS <<<")

# 1. CHECK CONNECTION
print("\n1. Checking connection to Green API...")
try:
    r = requests.get(f"{URL}/getStateInstance/{TOKEN}")
    print(f"Status Code: {r.status_code}")
    print(f"Response: {r.text}")
except Exception as e:
    print(f"ERROR: {e}")

# 2. CHECK SETTINGS
print("\n2. Checking settings...")
try:
    r = requests.get(f"{URL}/getSettings/{TOKEN}")
    print(f"Response: {r.text}")
except Exception as e:
    print(f"ERROR: {e}")

# 3. CHECK LAST MESSAGES
print("\n3. Checking last incoming messages...")
try:
    r = requests.get(f"{URL}/lastIncomingMessages/{TOKEN}")
    data = r.json()
    print(f"Found {len(data)} messages.")
    if len(data) > 0:
        last = data[0]
        print(f"Last Msg Time: {last.get('timestamp')}")
        print(f"Last Msg Content: {last}")
except Exception as e:
    print(f"ERROR: {e}")

# 4. SEND TEST MESSAGE
print("\n4. Sending TEST message to self...")
try:
    chatId = f"{TEST_PHONE}@c.us"
    payload = {"chatId": chatId, "message": "Test Message from Diagnostics Bot 🤖"}
    r = requests.post(f"{URL}/sendMessage/{TOKEN}", json=payload)
    print(f"Send status: {r.status_code}")
    print(f"Send response: {r.text}")
except Exception as e:
    print(f"ERROR: {e}")

print("\n>>> DIAGNOSTICS COMPLETE <<<")
print("Press ENTER to exit...")
input()
