
import requests

ID_INSTANCE = "7103495194"
API_TOKEN = "c01223dea0844ae195759cac8585aaf96f1d1be3dffa47bc83"
API_URL = f"https://7103.api.greenapi.com/waInstance{ID_INSTANCE}"
TEST_PHONE = "972542470052" # The number seen in logs

def check_status():
    print("--- Checking Status ---")
    url = f"{API_URL}/getStateInstance/{API_TOKEN}"
    try:
        resp = requests.get(url)
        print(f"Status Code: {resp.status_code}")
        print(f"Response: {resp.text}")
    except Exception as e:
        print(f"Error: {e}")

def try_send():
    print("\n--- Trying to Send ---")
    url = f"{API_URL}/sendMessage/{API_TOKEN}"
    payload = {
        "chatId": f"{TEST_PHONE}@c.us",
        "message": "בדיקת מערכת - האם זה מגיע?"
    }
    try:
        resp = requests.post(url, json=payload)
        print(f"Send Status: {resp.status_code}")
        print(f"Send Response: {resp.text}")
    except Exception as e:
        print(f"Send Error: {e}")

if __name__ == "__main__":
    check_status()
    try_send()
