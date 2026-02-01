
import requests
import time
import sys

# Encode for Windows Console
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

ID_INSTANCE = "7103495194"
API_TOKEN = "c01223dea0844ae195759cac8585aaf96f1d1be3dffa47bc83"
API_URL = f"https://7103.api.greenapi.com/waInstance{ID_INSTANCE}"

print(f"--- Starting Receiver Debug for {ID_INSTANCE} ---")
print("Waiting for incoming messages (Queue)...")

while True:
    try:
        url = f"{API_URL}/receiveNotification/{API_TOKEN}"
        resp = requests.get(url) # This waits potentially for long polling
        
        if resp.status_code == 200:
            data = resp.json()
            if data:
                print(f"\n[Raw Data]: {data}\n")
                
                receiptId = data.get('receiptId')
                body = data.get('body', {})
                sender = body.get('senderData', {}).get('chatId')
                
                # Try to extract text
                msg = body.get('messageData', {})
                text = msg.get('textMessageData', {}).get('textMessage') or \
                       msg.get('extendedTextMessageData', {}).get('text')
                       
                if text:
                    print(f"✅ RECEIVED MESSAGE: '{text}' from {sender}")
                else:
                    print(f"ℹ️ Received non-text notification type: {body.get('typeWebhook')}")

                # Delete to clear queue
                if receiptId:
                    del_url = f"{API_URL}/deleteNotification/{API_TOKEN}/{receiptId}"
                    requests.delete(del_url)
                    print(f"Deleted notification {receiptId}")
            else:
                # Null means timeout with no messages
                print(".", end="", flush=True)
        else:
            print(f"Error {resp.status_code}: {resp.text}")
            time.sleep(5)
            
    except Exception as e:
        print(f"Exception: {e}")
        time.sleep(5)
