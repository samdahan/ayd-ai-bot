
import time
import json
import os
import datetime
import threading
import logging
import requests

# --- CONFIGURATION ---
ID_INSTANCE = "7103495194"
API_TOKEN = "c01223dea0844ae195759cac8585aaf96f1d1be3dffa47bc83"
API_URL = f"https://7103.api.greenapi.com/waInstance{ID_INSTANCE}"

DATA_FILE = 'events.json'
MANAGERS_FILE = 'managers.json'

# Setup Logging
logging.basicConfig(
    filename='green_bot.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    encoding='utf-8'
)
console = logging.StreamHandler()
console.setLevel(logging.INFO)
logging.getLogger('').addHandler(console)

class GreenBot:
    def __init__(self):
        print(f">>> STARTING GREEN-API BOT (Instance {ID_INSTANCE}) <<<")
        self.is_running = True
        self.last_processed_timestamp = int(time.time()) # Ignore old messages

    def load_data(self):
        if not os.path.exists(DATA_FILE): return []
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f: return json.load(f)
        except: return []

    def save_data(self, data):
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    # --- API METHODS ---
    def send_message(self, phone, message):
        """ Sends a message to a phone number via Green API """
        url = f"{API_URL}/sendMessage/{API_TOKEN}"
        
        # Format phone: must clear symbols and ensure suffix @c.us
        chat_id = "".join(filter(str.isdigit, str(phone)))
        if not chat_id.endswith("@c.us"):
             # Simple heuristic for Israel
             if chat_id.startswith("05"): chat_id = "972" + chat_id[1:]
             elif chat_id.startswith("5"): chat_id = "972" + chat_id
             chat_id = chat_id + "@c.us"

        payload = {
            "chatId": chat_id,
            "message": message
        }
        
        try:
            response = requests.post(url, json=payload)
            if response.status_code == 200:
                logging.info(f"✅ Sent to {chat_id}: {message[:20]}...")
                return True
            else:
                logging.error(f"❌ Failed to send: {response.text}")
                return False
        except Exception as e:
            logging.error(f"Network error in send: {e}")
            return False

    def delete_notification(self, receiptId):
        """ Marks message as processed in GreenAPI queue """
        url = f"{API_URL}/deleteNotification/{API_TOKEN}/{receiptId}"
        try:
            requests.delete(url)
        except: pass

    # --- LOGIC ---
    def check_incoming(self):
        """ Long polling for incoming messages """
        url = f"{API_URL}/receiveNotification/{API_TOKEN}"
        try:
            response = requests.get(url)
            if response.status_code == 200:
                data = response.json()
                if not data: return # Empty queue
                
                receiptId = data['receiptId']
                body = data['body']
                
                # Check if it's an incoming text message
                if body.get('typeWebhook') == 'incomingMessageReceived':
                     sender_data = body.get('senderData', {})
                     message_data = body.get('messageData', {})
                     
                     sender_id = sender_data.get('chatId')
                     text_content = ""
                     
                     if message_data.get('typeMessage') == 'textMessage':
                         text_content = message_data.get('textMessageData', {}).get('textMessage', '')
                     elif message_data.get('typeMessage') == 'extendedTextMessage':
                         text_content = message_data.get('extendedTextMessageData', {}).get('text', '')

                     if text_content:
                         logging.info(f"📩 Received from {sender_id}: {text_content}")
                         self.handle_command(sender_id, text_content)

                # ALWAYS delete notification to unblock queue
                self.delete_notification(receiptId)
                
        except Exception as e:
            logging.error(f"Polling error: {e}")
            time.sleep(5)

    def handle_command(self, sender_id, text):
        text = text.strip()
        reply = ""
        
        # 1. ADD EVENT
        if "הוסף" in text or "הוספה" in text:
             try:
                 clean_text = text.replace("הוסף אירוע", "").replace("הוסף שמחה", "").replace("הוספה", "").replace("הוסף", "").strip()
                 parts = clean_text.split(' ')
                 date_str = parts[-1] 
                 name = " ".join(parts[:-1])

                 # Simple Hebrew Date Detection
                 is_hebrew = any(c in "אבגדהוזחטיכלמנסעפצקרשת" for c in date_str)
                 
                 evt_type = "birthday"
                 if "חתונה" in text: evt_type = "wedding"
                 elif "בר מצווה" in text: evt_type = "bar_mitzvah"
                 
                 db_date = "2026-01-01" # Default dummy for hebrew
                 db_hebrew = ""
                 
                 if is_hebrew:
                     db_hebrew = date_str
                     # If previous word is also hebrew date part (like 'ה באייר') merge them
                     if len(parts) >= 2 and any(c in "אבגדהוזחטיכלמנסעפצקרשת" for c in parts[-2]):
                          db_hebrew = parts[-2] + " " + parts[-1]
                          name = " ".join(parts[:-2])
                 else:
                     # Gregorian
                     if '/' in date_str:
                         d, m = date_str.split('/')[:2]
                         db_date = f"2026-{m.zfill(2)}-{d.zfill(2)}"

                 events = self.load_data()
                 events.append({
                     "id": int(time.time()),
                     "owner": name,
                     "date": db_date,
                     "hebrew_date": db_hebrew,
                     "is_hebrew": bool(db_hebrew),
                     "type": evt_type,
                     "targetPhone": sender_id, # Reply to sender when event happens? or custom?
                     "message": f"מזל טוב ל{name}!" 
                 })
                 self.save_data(events)
                 reply = f"✅ נוסף בהצלחה: {evt_type} ל{name} ({db_hebrew if db_hebrew else db_date})"
                 
             except Exception as e:
                 reply = "שגיאה. נסה: הוסף [שם] [תאריך]"

        # 2. STATUS
        elif "סטטוס" in text or "status" in text.lower():
            reply = "🤖 הבוט פעיל ומחובר דרך Green-API!"

        if reply:
            self.send_message(sender_id, reply)

    def check_scheduler(self):
        """ Checks for today's events """
        try:
             events = self.load_data()
             today = datetime.date.today()
             current_year = today.year
             
             # Fetch Hebrew Date (Online)
             h_date_str = ""
             try:
                 r = requests.get(f"https://www.hebcal.com/converter?cfg=json&gy={today.year}&gm={today.month}&gd={today.day}&g2h=1")
                 if r.status_code == 200: h_date_str = r.json().get('hebrew', '')
             except: pass

             dirty = False
             for event in events:
                 should_send = False
                 
                 # Check Hebrew
                 if event.get('is_hebrew') and event.get('hebrew_date') and h_date_str:
                     target = event['hebrew_date'].replace("'", "").replace('"', "")
                     curr = h_date_str.replace("'", "").replace('"', "")
                     if target in curr: should_send = True
                     
                 # Check Gregorian
                 elif not event.get('is_hebrew'):
                     try:
                         # Compare MM-DD
                         edate = event['date'][5:] # 2026-05-15 -> 05-15
                         tdate = f"{today.month:02d}-{today.day:02d}"
                         if edate == tdate: should_send = True
                     except: pass
                 
                 # Send?
                 if should_send:
                     last = event.get('last_sent_year', 0)
                     if last != current_year:
                         target = event.get('targetPhone')
                         if target:
                             self.send_message(target, event.get('message', 'Mazal Tov!'))
                             event['last_sent_year'] = current_year
                             dirty = True
             
             if dirty: self.save_data(events)
             
        except Exception as e:
             logging.error(f"Scheduler error: {e}")

    def run(self):
        last_sched = 0
        while self.is_running:
            # 1. Check Incoming Messages
            self.check_incoming()
            
            # 2. Daily Scheduler (every 60 sec check)
            if time.time() - last_sched > 60:
                self.check_scheduler()
                last_sched = time.time()
                
            time.sleep(1)

if __name__ == "__main__":
    bot = GreenBot()
    bot.run()
