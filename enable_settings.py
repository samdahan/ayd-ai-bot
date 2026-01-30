
import requests
import json
import sys

ID_INSTANCE = "7103495194"
API_TOKEN = "c01223dea0844ae195759cac8585aaf96f1d1be3dffa47bc83"
API_URL = f"https://7103.api.greenapi.com/waInstance{ID_INSTANCE}"

def enable_notifs():
    print("--- Enabling Incoming Notifications ---")
    url = f"{API_URL}/setSettings/{API_TOKEN}"
    payload = {
        "incomingWebhook": "yes",
        "outgoingWebhook": "yes",
        "deviceWebhook": "yes",
        "statusInstanceWebhook": "yes",
        "stateWebhook": "yes",
        "enableMessagesHistory": "yes",
        "keepOnlineStatus": "yes",
        "pollMessageWebhook": "yes"
    }
    try:
        resp = requests.post(url, json=payload)
        print(f"Status: {resp.status_code}")
        print(f"Response: {resp.text}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    enable_notifs()
