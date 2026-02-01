
import time
import json
import os
import threading
import logging
import requests
import sys
import datetime
import re
from flask import Flask, request, jsonify
from flask_cors import CORS

# --- CONFIGURATION ---
ID_INSTANCE = "7103495194"
API_TOKEN = "c01223dea0844ae195759cac8585aaf96f1d1be3dffa47bc83"
API_URL = f"https://7103.api.greenapi.com/waInstance{ID_INSTANCE}"
OWNER_PHONE = "0515642201"

DATA_FILE = 'events.json'
GROUPS_FILE = 'groups.json'
EVENTS_FILE = 'events.json'
CODES_FILE = 'codes.json'
PURCHASES_FILE = 'purchases.json'
STORES_FILE = 'stores.json'
SETTINGS_FILE = 'settings.json'

# Encode for Windows Console
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', stream=sys.stdout)
app = Flask(__name__)
# Enable CORS for all routes
# Enable CORS for all routes
CORS(app)

def load_settings():
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, 'r', encoding='utf-8') as f: return json.load(f)
        except: pass
    return {
        "bot_response": "כרגע אני לא עושה, בהמשך הפיתוח שלי תוכל לעשות הכל דרכי. 🚀",
        "gemini_api_key": "",
        "enable_commands": True,
        "system_instruction": ""
    }

def save_settings(settings):
    with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
        json.dump(settings, f, indent=2, ensure_ascii=False)

def load_codes():
    try:
        if os.path.exists(CODES_FILE):
            with open(CODES_FILE, 'r', encoding='utf-8') as f: return json.load(f)
    except: pass
    return {}


class Agent:
    def __init__(self):
        self.is_running = True
        self.ensure_data_files()
        self.init_logging_to_list()
        self.sessions = {} # store history per sender: {sender: [ {role: "user/model", text: "..."} ]}
        self.pending_products = {} # sender -> {name, barcode, image_url}

    def init_logging_to_list(self):
        # Keep last 10 activities for remote view
        self.activities = []

    def log_activity(self, text):
        ts = datetime.datetime.now().strftime("%H:%M")
        self.activities.append(f"[{ts}] {text}")
        if len(self.activities) > 10: self.activities.pop(0)

    def is_admin(self, sender):
        clean_owner = "".join(filter(str.isdigit, OWNER_PHONE))
        clean_sender = "".join(filter(str.isdigit, sender))
        return clean_owner in clean_sender or clean_sender in clean_owner
        
    def ensure_data_files(self):
        if not os.path.exists(DATA_FILE):
            with open(DATA_FILE, 'w', encoding='utf-8') as f: json.dump([], f)
            
        # Ensure Groups with Defaults
        defaults = [
            {"id": 101, "name": "משפחה", "members": []},
            {"id": 102, "name": "אחים", "members": []},
            {"id": 103, "name": "קרובים", "members": []},
            {"id": 105, "name": "חברים", "members": []},
            {"id": 106, "name": "עבודה", "members": []}
        ]
        
        groups_data = []
        if os.path.exists(GROUPS_FILE):
            try:
                with open(GROUPS_FILE, 'r', encoding='utf-8') as f: groups_data = json.load(f)
            except: pass
            
        if not groups_data:
            with open(GROUPS_FILE, 'w', encoding='utf-8') as f: 
                json.dump(defaults, f, ensure_ascii=False, indent=2)
        
        if not os.path.exists(PURCHASES_FILE):
             with open(PURCHASES_FILE, 'w', encoding='utf-8') as f: json.dump([], f)

    def load_events(self):
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f: return json.load(f)
        except: return []

    def save_events(self, events):
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(events, f, ensure_ascii=False, indent=2)

    def load_purchases(self):
        try:
            with open(PURCHASES_FILE, 'r', encoding='utf-8') as f: return json.load(f)
        except: return []

    def save_purchases(self, purchases):
        with open(PURCHASES_FILE, 'w', encoding='utf-8') as f:
            json.dump(purchases, f, ensure_ascii=False, indent=2)

    def add_event_internal(self, data):
        events = self.load_events()
        new_event = {
            "id": int(time.time() * 1000),
            "owner": data.get('owner', 'Unknown'),
            # Save Owner Phone for direct blessing
            "owner_phone": data.get('owner_phone', ''), 
            "target_phone": data.get('target_phone', ''),
            "date_type": data.get('date_type', 'gregorian'),
            "gregorian_date": data.get('gregorian_date', ''),
            "hebrew_date": data.get('hebrew_date', ''),
            "msg_template": data.get('msg_template', ''),
            "type": data.get('type', 'general'),
            "group": data.get('group', 'משפחה'),
            "scheduled_time": data.get('scheduled_time', ''), # New field for time scheduling
            "last_sent": ""
        }
        events.append(new_event)
        self.save_events(events)
        return True

    # --- STORE MANAGEMENT ---
    def load_stores(self):
        if os.path.exists(STORES_FILE):
            try:
                with open(STORES_FILE, 'r', encoding='utf-8') as f: return json.load(f)
            except: pass
        return []

    def save_stores(self, stores):
        with open(STORES_FILE, 'w', encoding='utf-8') as f:
            json.dump(stores, f, indent=2, ensure_ascii=False)

    def add_store_product(self, store_id, product_name, price, image="", barcode=""):
        stores = self.load_stores()
        for s in stores:
            if str(s['id']) == str(store_id):
                if 'products' not in s: s['products'] = []
                s['products'].append({
                    "id": int(time.time()),
                    "name": product_name,
                    "price": price,
                    "image": image,
                    "barcode": barcode,
                    "orders": []
                })
                self.save_stores(stores)
                self.add_store_log(store_id, "הוספת מוצר", f"נוסף מוצר בשם {product_name} במחיר {price}")
                return True
        return False

    def update_store_product(self, store_id, product_id, name, price, image, barcode=""):
        stores = self.load_stores()
        for s in stores:
            if str(s['id']) == str(store_id):
                if 'products' in s:
                    for p in s['products']:
                        if str(p['id']) == str(product_id):
                            p['name'] = name
                            p['price'] = price
                            p['image'] = image
                            p['barcode'] = barcode
                            self.save_stores(stores)
                            self.add_store_log(store_id, "עדכון מוצר", f"עודכן מוצר {name} (ID: {product_id})")
                            return True
        return False

    def delete_store_product(self, store_id, product_id):
        stores = self.load_stores()
        for s in stores:
            if str(s['id']) == str(store_id):
                if 'products' in s:
                    original_len = len(s['products'])
                    s['products'] = [p for p in s['products'] if str(p['id']) != str(product_id)]
                    if len(s['products']) < original_len:
                        self.save_stores(stores)
                        self.add_store_log(store_id, "מחיקת מוצר", f"נמחק מוצר ID: {product_id}")
                        return True
        return False
    def add_store_client(self, store_id, client_name, client_phone, product="", notes="", source="manual"):
        stores = self.load_stores()
        for s in stores:
            if str(s['id']) == str(store_id):
                if 'interested_clients' not in s: s['interested_clients'] = []
                # Check duplication
                for c in s['interested_clients']:
                    if c['phone'] == client_phone:
                        # Update existing
                        c['product'] = product
                        c['notes'] = notes
                        c['date'] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M") 
                        self.save_stores(stores)
                        return True

                s['interested_clients'].append({
                    "name": client_name,
                    "phone": client_phone,
                    "product": product,
                    "notes": notes,
                    "date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "source": source
                })
                self.save_stores(stores)
                self.add_store_log(store_id, "הוספת לקוח", f"נוסף לקוח {client_name} ({client_phone})")
                return True
        return False

    def add_store_invoice(self, store_id, client_name, amount, items, date=None):
        stores = self.load_stores()
        for s in stores:
            if str(s['id']) == str(store_id):
                if 'invoices' not in s: s['invoices'] = []
                s['invoices'].append({
                    "id": int(time.time()),
                    "client": client_name,
                    "amount": amount,
                    "items": list(items) if isinstance(items, list) else items,
                    "date": date or datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
                })
                self.save_stores(stores)
                self.add_store_log(store_id, "יצירת חשבונית", f"נוצרה חשבונית ל{client_name} על סך {amount}₪")
                return True
        return False

    def add_store_log(self, store_id, action, details):
        stores = self.load_stores()
        found = False
        for s in stores:
            if str(s['id']) == str(store_id):
                if 'logs' not in s: s['logs'] = []
                s['logs'].append({
                    "id": int(time.time()),
                    "action": action,
                    "details": details,
                    "date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
                })
                if len(s['logs']) > 50: s['logs'] = s['logs'][-50:]
                found = True
                break
        if found:
            self.save_stores(stores)
            return True
        return False
    def delete_event(self, event_id):
        events = self.load_events()
        events = [e for e in events if str(e.get('id')) != str(event_id)]
        self.save_events(events)

    # --- GREEN API LOGIC ---
    def delete_notification(self, receiptId):
        try:
            url = f"{API_URL}/deleteNotification/{API_TOKEN}/{receiptId}"
            resp = requests.delete(url, timeout=10)
            if resp.status_code != 200:
                logging.error(f"❌ Failed to delete notification {receiptId}: {resp.status_code}")
        except Exception as e:
            logging.error(f"❌ Error deleting notification: {e}")

    def start_bot_loop(self):
        t = threading.Thread(target=self.bot_loop, daemon=True)
        t.start()
        print(">>> Bot Listening Loop Started <<<")

    def check_instance_status(self):
        try:
            url = f"{API_URL}/getStateInstance/{API_TOKEN}"
            resp = requests.get(url, timeout=10)
            if resp.status_code == 200:
                print(f"✅ GreenAPI Instance Status: {resp.json().get('stateInstance')}")
            else:
                print(f"❌ GreenAPI Instance Error: {resp.status_code} - {resp.text}")
        except Exception as e:
            print(f"❌ GreenAPI Status Check Fail: {e}")

    def bot_loop(self):
        print(">>> Bot Listening Loop Started <<<")
        self.check_instance_status()
        last_sched = 0
        while self.is_running:
            try:
                # 1. Incoming
                self.check_incoming()
                
                # 2. Scheduler (Every 60s)
                if time.time() - last_sched > 60:
                    self.check_scheduler()
                    last_sched = time.time()
                    
            except Exception as e:
                print(f"Loop error: {e}")
                time.sleep(5)
            time.sleep(0.1)

    def check_scheduler(self):
        """ Checks for today's events and sends to BOTH Target and Owner """
        try:
             events = self.load_events()
             today = datetime.date.today()
             current_year = today.year
             now_time = datetime.datetime.now().strftime("%H:%M")
             
             # Fetch Hebrew Date
             h_date_str = ""
             try:
                 r = requests.get(f"https://www.hebcal.com/converter?cfg=json&gy={today.year}&gm={today.month}&gd={today.day}&g2h=1")
                 if r.status_code == 200: h_date_str = r.json().get('hebrew', '')
             except: pass

             dirty = False
             to_delete = [] # For one-time scheduled broadcasts

             for event in events:
                 try:
                     should_send = False
                     e_type = event.get('type', 'general')
                     evt_group = event.get('group', '')
                     
                     # Check if it's currently at or after the scheduled time (default 09:00 for recurring)
                     target_time = event.get('scheduled_time') or "09:00"
                     
                     if e_type == 'scheduled_broadcast':
                         if target_time != now_time: continue # Exact time for one-off broadcasts
                     else:
                         if now_time < target_time: continue # Wait until the window opens

                     # 1. Handle Scheduled Broadcast (One time)
                     if e_type == 'scheduled_broadcast':
                         if event.get('gregorian_date') == today.strftime("%Y-%m-%d"):
                             print(f"⏰ Scheduled Broadcast triggering now!")
                             self.broadcast_internal(event.get('target_phone', 'all'), event.get('msg_template', ''))
                             to_delete.append(event['id'])
                             dirty = True
                             continue

                     # 2. Handle Recurring Events (Birthdays etc)
                     # Check Hebrew
                     if event.get('date_type') == 'hebrew' and event.get('hebrew_date') and h_date_str:
                         e_h_date = event['hebrew_date'].replace("'","").replace('"',"").strip()
                         api_h_date = h_date_str.replace("'","").replace('"',"").strip()
                         # Match day and month (e.g. "י שבט" in "13 Sh'vat 5786" - wait, Hebcal API can be tricky)
                         # We'll do a simple substring match for now as a fallback
                         if e_h_date in api_h_date:
                             should_send = True
                             
                     # Check Gregorian
                     elif event.get('date_type') == 'gregorian' and event.get('gregorian_date'):
                         edate = event['gregorian_date']
                         # Handle YYYY-MM-DD, MM-DD, DD/MM, etc.
                         match = False
                         if "-" in edate:
                             parts = edate.split("-")
                             if len(parts) == 3: # YYYY-MM-DD
                                 match = (int(parts[1]) == today.month and int(parts[2]) == today.day)
                             elif len(parts) == 2: # MM-DD
                                 match = (int(parts[0]) == today.month and int(parts[1]) == today.day)
                         elif "/" in edate:
                             parts = edate.split("/")
                             if len(parts) == 2: # DD/MM or MM/DD ? Usually dashboard uses MM/DD for birthdays
                                 # We check both to be safe or use a convention. Dashboard used MM/DD in some places.
                                 if (int(parts[0]) == today.month and int(parts[1]) == today.day): match = True
                                 if (int(parts[1]) == today.month and int(parts[0]) == today.day): match = True
                         elif "." in edate:
                             parts = edate.split(".")
                             if len(parts) == 2: # DD.MM
                                 match = (int(parts[0]) == today.day and int(parts[1]) == today.month)

                         if match: should_send = True
                     
                     # Send Logic for recurring
                     if should_send:
                         last = event.get('last_sent_year', 0)
                         if str(last) != str(current_year):
                             msg = event.get('msg_template', 'מזל טוב! 🎉')
                             owner_name = event.get('owner', 'חבר')
                             
                             print(f"🚀 Automated Send Event for {owner_name}...")
                             
                             # 1. Send to Target (Admin/Reminder)
                             t_phone = event.get('target_phone')
                             if t_phone:
                                 remind_msg = f"🔔 תזכורת: היום יש {evt_group or 'שמחה'} ל{owner_name}!"
                                 if e_type == 'birthday': remind_msg = f"🎂 תזכורת: היום יום הולדת ל{owner_name}!"
                                 self.send_whatsapp(t_phone, remind_msg)
                                 
                             # 2. Send to Owner (The celebrant)
                             o_phone = event.get('owner_phone')
                             if o_phone:
                                 self.send_whatsapp(o_phone, msg)
                             elif not t_phone: # Fallback if only one phone is provided in target_phone but it's meant for the owner
                                 # This is a bit risky but common in simple setups
                                 pass

                             event['last_sent_year'] = current_year
                             dirty = True
                 except Exception as ee:
                     print(f"Error processing event {event.get('id')}: {ee}")
             
             if to_delete:
                 events = [e for e in events if e['id'] not in to_delete]
                 
             if dirty: self.save_events(events)
             
        except Exception as e:
             print(f"Scheduler error: {e}")

    def broadcast_internal(self, group_id, msg):
        if not msg: return
        
        phones = set()
        groups = []
        try:
            with open(GROUPS_FILE, 'r', encoding='utf-8') as f: groups = json.load(f)
        except: pass

        if str(group_id) == 'all':
            for g in groups:
                for m in g.get('members', []):
                    if m.get('phone'): phones.add(m['phone'])
            try:
                events = self.load_events()
                for e in events:
                    if e.get('owner_phone'): phones.add(e['owner_phone'])
                    if e.get('target_phone'): phones.add(e['target_phone'])
            except: pass
        else:
            target_group = next((g for g in groups if str(g['id']) == str(group_id)), None)
            if target_group:
                for m in target_group.get('members', []):
                    if m.get('phone'): phones.add(m['phone'])
        
        def run_b():
            for p in phones:
                self.send_whatsapp(p, msg)
                time.sleep(1)
        
        threading.Thread(target=run_b, daemon=True).start()

    def check_incoming(self):
        try:
            url = f"{API_URL}/receiveNotification/{API_TOKEN}"
            resp = requests.get(url, timeout=10) 
            
            if resp.status_code == 404:
                return # No notifications
            
            if resp.status_code != 200:
                logging.error(f"GreenAPI Error: {resp.status_code} - {resp.text}")
                return
            
            data = resp.json()
            if not data: return 
            
            receiptId = data.get('receiptId')
            body = data.get('body', {})
            w_type = body.get('typeWebhook')
            
            logging.info(f"🔔 Notification: {w_type}")
            
            if w_type == 'incomingMessageReceived':
                msg_data = body.get('messageData', {})
                sender_data = body.get('senderData', {})
                sender = sender_data.get('chatId')
                
                text = ""
                type_msg = msg_data.get('typeMessage')
                
                if type_msg == 'textMessage':
                    text = msg_data.get('textMessageData', {}).get('textMessage', '')
                elif type_msg == 'extendedTextMessage':
                    text = msg_data.get('extendedTextMessageData', {}).get('text', '')
                elif type_msg == 'quotedMessage':
                    text = msg_data.get('quotedMessageData', {}).get('text', '')
                
                if text:
                    print(f"📩 Message from {sender}: {text}")
                    # Run command handling in a separate thread to keep polling alive
                    threading.Thread(target=self.handle_command, args=(sender, text), daemon=True).start()
                elif type_msg == 'imageMessage':
                    image_data = msg_data.get('imageMessageData', {})
                    logging.info(f"📸 Image message from {sender}")
                    threading.Thread(target=self.handle_image_message, args=(sender, image_data), daemon=True).start()
                else:
                    logging.info(f"📦 Ignored message type: {type_msg}")
            
            elif w_type in ['stateInstanceChanged', 'outgoingMessageStatus', 'outgoingAPIMessageReceived', 'outgoingMessageReceived']:
                # Silently ignore status updates or instance changes in logs to keep it clean
                pass
            
            else:
                logging.info(f"🔔 Notification: {w_type}")
            
            # MUST Delete notification to clear queue
            if receiptId:
                self.delete_notification(receiptId)
                
        except Exception as e:
            # Only print every 10 errors to avoid spam if it's a persistent network issue
            if not hasattr(self, '_poll_err_count'): self._poll_err_count = 0
            self._poll_err_count += 1
            if self._poll_err_count % 10 == 1:
                print(f"Polling error (attempt {self._poll_err_count}): {e}")

    def handle_command(self, sender, text):
        import random
        settings = load_settings()
        if not settings.get('enable_commands', True) and not self.is_admin(sender):
            logging.info(f"🚫 Commands disabled. Skipping message from {sender}")
            return

        # Check for price reply if there's a pending product
        if sender in self.pending_products:
            price_match = re.fullmatch(r'\d+', text.strip())
            if price_match:
                price = price_match.group(0)
                pending = self.pending_products.pop(sender)
                
                # Save to the first store by default for now, or the most recent
                stores = self.load_stores()
                if stores:
                    store = stores[0] # Default to first store
                    self.add_store_product(store['id'], pending['name'], price, pending.get('image_url', ''), pending.get('barcode', ''))
                    reply = f"✅ מוצר נשמר בהצלחה! \n📦 *{pending['name']}*\n💰 מחיר: {price}₪\n🏪 חנות: {store['name']}"
                    self.send_whatsapp(sender, reply)
                    return
        
        print(f"DEBUG: handle_command start for text '{text}'")
        raw_text = text
        text = text.lower().strip()
        reply = ""

        # --- SMART INTENT RECOGNITION ---
        
        # 1. ADD EVENT Logic (Improved parsing)
        if any(k in text for k in ["הוסף", "תוסיף", "תזמן", "add", "schedule"]):
            try:
                # Remove keywords to get the meat of the message
                clean = text
                for k in ["הוסף", "תוסיף", "תזמן", "תזכורת", "שמחה", "add", "schedule"]:
                    clean = clean.replace(k, "")
                clean = clean.strip()
                
                parts = clean.split()
                if len(parts) >= 2:
                    # Look for date-like pattern (contains digits or Hebrew month)
                    date_idx = -1
                    hebrew_months = ["תשרי", "חשוון", "כסלו", "טבת", "שבט", "אדר", "ניסן", "אייר", "סיוון", "תמוז", "אב", "אלול"]
                    
                    for i, p in enumerate(parts):
                        if any(char.isdigit() for char in p) or any(m in p for m in hebrew_months):
                            date_idx = i
                            break
                    
                    if date_idx != -1:
                        # If date is found, everything before it is name, everything after (and including it) is date
                        name = " ".join(parts[:date_idx])
                        date_str = " ".join(parts[date_idx:])
                        
                        # Validation
                        if not name: name = "אירוע חדש"
                        
                        new_evt = {
                            "owner": name.title(),
                            "target_phone": sender,
                            "owner_phone": "", 
                            "date_type": "gregorian",
                            "msg_template": f"מזל טוב ל{name}! 🎉",
                            "type": "birthday"
                        }
                        
                        if any(m in date_str for m in hebrew_months):
                            new_evt["date_type"] = "hebrew"
                            new_evt["hebrew_date"] = date_str
                        else:
                            new_evt["gregorian_date"] = date_str
                            
                        self.add_event_internal(new_evt)
                        replies = [
                            f"מעולה! רשמתי לי: {name} בתאריך {date_str} ✅",
                            f"בוצע! הוספתי את {name} ללוח השמחות שלי 📅",
                            f"אין בעיה, {name} נשמר במערכת תחת התאריך {date_str} ✨"
                        ]
                        reply = random.choice(replies)
                    else:
                        reply = "אשמח להוסיף, אבל איזה תאריך? (למשל: הוסף יוסי 15/05)"
                else:
                    reply = "כדי להוסיף אירוע, כתוב לי שם ותאריך. דוגמה: *הוסף משה י' בשבט*"
            except Exception as e:
                print(f"Error AI adding event: {e}")
                reply = "משהו השתבש בניסיון לשמור את האירוע... תוכל לנסות שוב?"

        # 1.1 SALES MANAGEMENT Logic
        elif any(k in text for k in ["פתח מכירה", "open sale", "חדש מכירה"]):
            if self.is_admin(sender):
                try:
                    # Example: פתח מכירה: שמן זית, מחיר: 60, מלאי: 20
                    clean = raw_text.split(":", 1)[1].strip()
                    parts = [p.strip() for p in clean.split(",")]
                    name = parts[0]
                    price = parts[1].replace("מחיר", "").replace("price", "").replace(":", "").strip()
                    stock = parts[2].replace("מלאי", "").replace("stock", "").replace(":", "").strip() if len(parts) > 2 else "999"
                    
                    # Enhanced parsing for Sales Window (Name, Product, Email)
                    client_name = "כללי"
                    product_name = name
                    client_email = "לא הוזן"
                    
                    if "," in name:
                        sales_parts = [p.strip() for p in name.split(",")]
                        if len(sales_parts) >= 2:
                            client_name = sales_parts[0]
                            product_name = sales_parts[1]
                            if len(sales_parts) >= 3:
                                client_email = sales_parts[2]

                    new_sale = {
                        "id": int(time.time()),
                        "client_name": client_name,
                        "name": product_name,
                        "client_email": client_email,
                        "price": price,
                        "stock": int(stock),
                        "orders": [],
                        "status": "active",
                        "created_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
                    }
                    purchases.append(new_sale)
                    self.save_purchases(purchases)
                    reply = f"✅ *בוצע! חלון המכירה עודכן* �\n� לקוח: {client_name}\n🎁 מוצר: {product_name}\n� מייל: {client_email}\n💰 מחיר: {price}₪"
                except Exception as e:
                    reply = "❌ שגיאה בפורמט. דוגמה: פתח מכירה: שמן זית, מחיר: 60, מלאי: 20"
            else:
                reply = "מצטער, רק מנהל יכול לפתוח מכירה חדשה. 🔒"

        elif any(k in text for k in ["אני רוצה", "order"]):
            purchases = self.load_purchases()
            active_sale = next((p for p in reversed(purchases) if p['status'] == 'active'), None)
            if not active_sale:
                reply = "אין כרגע מכירה פעילה. חכו להזדמנות הבאה! 🛒"
            else:
                try:
                    # Find number in text
                    import re
                    nums = re.findall(r'\d+', text)
                    amount = int(nums[0]) if nums else 1
                    
                    if active_sale['stock'] < amount:
                        reply = f"❌ מצטער, נשארו רק {active_sale['stock']} יחידות במלאי."
                    else:
                        active_sale['stock'] -= amount
                        # Record order
                        active_sale['orders'].append({
                            "sender": sender,
                            "amount": amount,
                            "time": datetime.datetime.now().strftime("%H:%M")
                        })
                        self.save_purchases(purchases)
                        reply = f"✅ *הזמנה התקבלה!* 📦\nרשמתי לך {amount} יחידות של '{active_sale['name']}'.\nתודה רבה! 🙏"
                except Exception as e:
                    reply = "לא הבנית כמה יחידות תרצו? נא לכתוב מספר (למשל: אני רוצה 2)."

        elif any(k in text for k in ["סיכום מכירה", "sale summary"]):
            purchases = self.load_purchases()
            active_sale = next((p for p in reversed(purchases) if p['status'] == 'active'), None)
            if not active_sale:
                reply = "לא מצאתי מכירה פעילה לסיכום."
            else:
                total_items = sum(o['amount'] for o in active_sale['orders'])
                details = "\n".join([f"• {o['sender'].split('@')[0]}: {o['amount']} יחידות" for o in active_sale['orders']])
                reply = (
                    f"📋 *סיכום מכירה: {active_sale['name']}* 🛒\n"
                    f"📅 נפתח ב: {active_sale['created_at']}\n"
                    f"💰 מחיר יחידה: {active_sale['price']}₪\n"
                    f"📊 הוזמנו סה\"כ: {total_items}\n"
                    f"📉 מלאי נותר: {active_sale['stock']}\n\n"
                    f"*רשימת מזמינים:*\n{details if details else 'אין הזמנות עדיין.'}"
                )

        elif any(k in text for k in ["סגור מכירה", "finish sale"]):
            if self.is_admin(sender):
                purchases = self.load_purchases()
                active_sale = next((p for p in reversed(purchases) if p['status'] == 'active'), None)
                if active_sale:
                    active_sale['status'] = 'closed'
                    self.save_purchases(purchases)
                    reply = f"✅ המכירה של '{active_sale['name']}' נסגרה בהצלחה. לא ניתן לבצע הזמנות נוספות."
                else:
                    reply = "לא מצאתי מכירה פעילה לסגירה."
            else:
                reply = "רק מנהל יכול לסגור מכירה. 🔒"

        # 2. GREETINGS (Varied)
        elif any(k in text for k in ["בוקר טוב", "בוקר אור", "good morning"]):
             reply = random.choice([
                 "בוקר אור! ☀️ איך אפשר לעזור היום?",
                 "בוקר מצוין! אני לשירותך ☕",
                 "בוקר טוב! מקווה שהיום שלך הולך להיות נהדר ✨"
             ])
        
        elif any(k in text for k in ["צהריים טובים", "צהריים טובים"]):
             reply = random.choice([
                 "צהריים טובים! ✨ מה שלומך?",
                 "המשך יום נעים! איך אני יכול לעזור?",
                 "צהריים מצוינים! אני כאן אם צריך משהו 💎"
             ])

        elif any(k in text for k in ["ערב טוב", "לילה טוב"]):
             reply = random.choice([
                 "ערב מצוין! 🌙",
                 "לילה טוב! אני עדיין כאן אם אתה צריך משהו",
                 "ערב טוב ומבורך! ✨"
             ])

        # --- STORE INTEREST COMMANDS ---
        elif text.startswith("מתעניין בחנות:") or text.startswith("interested in store:"):
            try:
                # Assuming sender_name and sender_phone are available in this scope
                # For this example, let's mock them or assume they are passed/derived
                sender_name = sender.split('@')[0] # Example: extract name from JID
                sender_phone = sender.split('@')[0] # Example: use JID as phone for now
                
                store_name = text.split(":")[1].strip()
                stores = self.load_stores()
                found = False
                for s in stores:
                    if store_name in s['name'] or s['name'] in store_name:
                        self.add_store_client(s['id'], sender_name, sender_phone, "whatsapp_user")
                        reply = f"✅ נרשמת בהצלחה כמתעניין בחנות *{s['name']}*! בעל העסק יצור קשר בקרוב."
                        found = True
                        break
                if not found:
                    reply = "❌ לא מצאתי חנות בשם זה. נסה שוב."
            except Exception as e:
                reply = f"❌ שגיאה. נסה: מתעניין בחנות: [שם החנות]. Error: {e}"

        elif text.startswith("הוסף מתעניין:") or text.startswith("add lead:"):
            # Admin command: הוסף מתעניין: משה כובעים, ישראל ישראלי, 0501234567
            # Assuming OWNER_PHONE is defined globally or accessible
            OWNER_PHONE = "972515642201" # Placeholder, replace with actual owner phone logic
            sender_phone = sender.split('@')[0] # Example: use JID as phone for now

            if sender_phone == OWNER_PHONE or sender_phone == "972515642201":
                try:
                    parts = text.split(":")[1].split(",")
                    if len(parts) >= 3:
                        s_name = parts[0].strip()
                        c_name = parts[1].strip()
                        c_phone = parts[2].strip()
                        
                        stores = self.load_stores()
                        store_id = None
                        for s in stores:
                            if s_name in s['name']:
                                store_id = s['id']
                                break
                        
                        if store_id:
                            self.add_store_client(store_id, c_name, c_phone, "whatsapp_admin")
                            reply = f"✅ הלקוח {c_name} נוסף בהצלחה לחנות {s_name}!"
                        else:
                            reply = "❌ חנות לא נמצאה."
                    else:
                        reply = "❌ פורמט שגוי. נסה: הוסף מתעניין: [חנות], [שם], [טלפון]"
                except Exception as e:
                    reply = f"❌ שגיאה בפענוח הפקודה. Error: {e}"
            else:
                reply = "⛔ פקודה זו מיועדת למנהל המערכת בלבד."

        elif any(k in text for k in ["מי הבוס", "who is the boss"]):
             reply = "אתה הבוס! 😎"

        # 2. GREETINGS
        elif any(k in text for k in ["שלום", "היי", "הלו", "מה קורה", "מה שלומך", "מה איתך", "מה נשמע", "hi", "hello", "hey"]):
             if "hi" in text or "hello" in text or "hey" in text:
                 reply = "Hello! I'm SYD-AI, your smart digital assistant 🤖. How can I help you today? ✨"
             else:
                 reply = "שלום! אני SYD-AI, הסוכן הדיגיטלי החכם 🤖. איך אני יכול לעזור לכם היום? ✨"

        # 3. HELP & CAPABILITIES
        elif any(k in text for k in ["מה אתה יודע", "מה אתה עושה", "יכולות", "what do you do", "what can you do", "who are you", "features", "capabilities", "help", "help me"]):
            if any(k in text for k in ["what", "who", "help", "capabilities", "features", "can you"]):
                reply = (
                    "I'm SYD-AI, your Smart Digital Assistant! 🤖💎\n\n"
                    "Here's what I can do:\n"
                    "1️⃣ *Smart AI*: I can answer any question and search the web! 🧠\n"
                    "2️⃣ *Event Management*: I save events and send automatic greetings! 🎂🎉\n"
                    "3️⃣ *Group Buying*: I manage sales and track orders automatically! 🛒💎\n\n"
                    "I'm currently in active development with new features! 🚀\n"
                    "Ask me *'How do I use this?'* for instructions! ✨"
                )
            else:
                reply = (
                    "אני SYD-AI הסוכן הדיגיטלי החכם! 🤖💎\n\n"
                    "הנה מה שאני יודע לעשות:\n"
                    "1️⃣ *מענה חכם*: אני מחובר לבינה מלאכותית ויודע לענות על כל שאלה! 🧠\n"
                    "2️⃣ *ניהול שמחות*: אני שומר אירועים וימי הולדת ושולח ברכות אוטומטיות! 🎂🎉\n"
                    "3️⃣ *ניהול קבוצות רכישה*: אני עוזר למאזן ולנהל קבוצות רכישה בצורה חכמה! 🛒💎\n\n"
                    "אני נמצא כרגע בתהליכי פיתוח מתקדמים ומוסיפים לי פיצ'רים חדשים כל הזמן! 🚀\n\n"
                    "שאלו אותי *'איך אתה עושה את זה?'* כדי לקבל הוראות שימוש! ✨"
                )

        elif any(k in text for k in ["איך אתה עושה", "איך את עושה", "איך עובד", "how to use", "instructions"]):
            if "how" in text or "instructions" in text:
                reply = (
                    "💡 *General Questions*: Just write anything and I'll answer! 🧠\n"
                    "💡 *Events*: Write 'add' + name + date (e.g., 'add John 12/05') 📅\n"
                    "💡 *Group Buying*: \n"
                    "   - *Admin*: 'Open sale: [Product], Price: [X], Stock: [Y]'\n"
                    "   - *Users*: 'Order [number]'\n"
                    "   - *Summary*: 'Sale summary'\n"
                    "I'm here for whatever you need! 🚀"
                )
            else:
                reply = (
                    "הנה הסבר קצר על איך להפעיל אותי: ✨\n\n"
                    "💡 *שאלות כלליות*: פשוט תכתבו לי כל דבר ואני אענה מיד! 🧠\n"
                    "💡 *שמירת אירוע*: כתבו 'תוסיף' + שם + תאריך (למשל: 'תוסיף משה 12/07') 📅\n"
                    "💡 *קבוצת רכישה*: \n"
                    "   - *מנהל*: 'פתח מכירה: [מוצר], מחיר: [X], מלאי: [Y]'\n"
                    "   - *משתמש*: 'אני רוצה [מספר]'\n"
                    "   - *סיכום*: 'סיכום מכירה'\n\n"
                    "אני כאן לכל מה שתצטרכו! 🚀"
                )

        elif text == "עזרה" or text == "תפריט":
            reply = "אני כאן לעזור! 🤖\nתכתבו 'מה אתה עושה' כדי לראות את היכולות שלי, או 'איך אתה עושה' להוראות שימוש. ✨"

        elif text in ["תודה", "סבבה", "מגניב", "thanks", "cool"]:
             reply = random.choice([
                 "בשמחה! SYD-AI תמיד כאן בשבילך 🙏",
                 "בכיף! אל תהסס לבקש עוד משהו מ-SYD-AI 😊",
                 "שמחתי לעזור! ✨"
             ])

        elif text == "סטטוס" or text == "status":
            if self.is_admin(sender):
                reply = "🤖 מערכת SYD-AI הסוכן החכם פועלת כרגיל! ✅\nהכל מחובר והאירועים מתוזמנים 💎"
            else:
                reply = "המערכת שלי מחוברת ופעילה! 🤖 איך אני יכול לעזור לכם היום?"
             
        elif text == "כן" or text == "yes":
             reply = "שבת שלום! 🕯️🕯️ מ-SYD-AI הסוכן החכם 🤖 וצוות המפתחים 🚀"
        
        else:
            # --- SMART AI FALLBACK (Gemini) ---
            settings = load_settings()
            api_key = settings.get("gemini_api_key")
            
            if api_key:
                # Get history for this sender
                if sender not in self.sessions: self.sessions[sender] = []
                history = self.sessions[sender]
                
                logging.info(f"🧠 Asking Gemini for: {text} (Context: {len(history)} msgs)")
                ai_reply = self.call_gemini(api_key, raw_text, history)
                if ai_reply:
                    reply = ai_reply
                    # Add to history
                    history.append({"role": "user", "text": raw_text})
                    history.append({"role": "model", "text": ai_reply})
                    # Keep only last 10 messages (5 turns)
                    if len(history) > 10: self.sessions[sender] = history[-10:]
                else:
                    logging.warning("⚠️ Gemini failed to provide a reply.")
            
            if not reply:
                custom_reply = settings.get("bot_response", "")
                if custom_reply:
                    reply = custom_reply
                else:
                    if getattr(self, '_last_ai_error', None) == 429:
                        reply = "אני קצת עמוס כרגע בבקשות... 🧠☕\nאנא נסה שוב בעוד דקה, אני מיד מתפנה לעזור לך!"
                    else:
                        reply = "משהו קטן השתבש בתוך המנוע החכם שלי... 🧠\nאני נמצא כרגע בתהליכי פיתוח מתקדמים ומוסיפים לי פיצ'רים חדשים כל הזמן! 🚀"

        # --- REMOTE ADMIN CONTROL ---
        if self.is_admin(sender):
            if text == "עזרה למנהל" or text == "admin help":
                reply = (
                    "💎 *לוח בקרה מרחוק - SYD-AI* 🤖\n\n"
                    "📢 *שידור לשלוח [קבוצה] [הודעה]* - שליחה קבוצתית.\n"
                    "📝 *עדכן מענה [טקסט]* - שינוי תשובת ברירת המחדל.\n"
                    "� *פתח מכירה: [שם], מחיר: [X], מלאי: [Y]*\n"
                    "📋 *סיכום מכירה* - מצב הזמנות נוכחי.\n"
                    "✅ *סטטוס* - מצב חיבור ושרת."
                )
            
            elif text.startswith("שידור ") or text.startswith("broadcast "):
                try:
                    parts = raw_text.split(" ", 2)
                    if len(parts) < 3:
                        reply = "שימוש: שידור [שם קבוצה] [הודעה]"
                    else:
                        g_name = parts[1]
                        msg_to_send = parts[2]
                        # Find group ID
                        groups = load_groups()
                        target_g = next((g for g in groups if g['name'] == g_name), None)
                        if target_g:
                            self.broadcast_internal(target_g['id'], msg_to_send)
                            reply = f"🚀 השידור לקבוצת '{g_name}' יצא לדרך!"
                        else:
                            reply = f"❌ לא מצאתי קבוצה בשם '{g_name}'"
                except Exception as e:
                    reply = f"❌ שגיאה בשידור: {e}"

            elif text.startswith("עדכן מענה ") or text.startswith("set response "):
                new_resp = raw_text.split(" ", 2)[-1]
                settings = load_settings()
                settings['bot_response'] = new_resp
                save_settings(settings)
                reply = f"✅ מענה ברירת המחדל עודכן ל: {new_resp}"

            elif text == "קבוצות" or text == "groups":
                groups = load_groups()
                if not groups:
                    reply = "אין קבוצות מוגדרות כרגע."
                else:
                    g_list = "\n".join([f"• {g['name']} ({len(g.get('members', []))} חברים)" for g in groups])
                    reply = f"📋 *קבוצות תפוצה במערכת:*\n\n{g_list}"

            elif text == "יומן" or text == "logs":
                if not self.activities:
                    reply = "אין פעילות מתועדת כרגע."
                else:
                    reply = "🔍 *פעולות אחרונות:*\n\n" + "\n".join(self.activities)

            elif text.startswith("בדוק ai ") or text.startswith("test ai "):
                prompt = raw_text.split(" ", 2)[-1]
                settings = load_settings()
                api_key = settings.get("gemini_api_key")
                if not api_key:
                    reply = "❌ לא מצאתי מפתח Gemini מוגדר."
                else:
                    ai_res = self.call_gemini(api_key, prompt)
                    reply = f"🤖 *תשובת AI:* \n\n{ai_res}"

        if reply:
            self.send_whatsapp(sender, reply)
            self.log_activity(f"Replied to {sender}: {text[:20]}")

    # --- HELPERS ---
    def call_gemini(self, api_key, prompt, history=None):
        """ Call Google Gemini API with multi-turn history support """
        models = [
            "gemini-2.0-flash", 
            "gemini-flash-latest",
            "gemini-2.0-flash-lite", 
            "gemini-pro-latest"
        ]
        
        settings = load_settings()
        user_inst = settings.get("system_instruction", "")
        
        system_instruction = (
            "You are SYD-AI, a smart digital assistant for SAM DAHAN. "
            "You have access to real-time information via Google Search. "
            "IMPORTANT: When replying to users, DO NOT assume their name is Sam or SAM DAHAN. Just be friendly and professional. "
            "If asked who created / developed / programmed you, always state that you were created and developed by SYD-AI (צוות SYD). "
            "LANGUAGE POLICY: Always reply in the SAME LANGUAGE as the user (Hebrew or English). "
            "Your tone should be friendly, helpful, and professional. "
            "Use emojis occasionally. Keep responses concise. "
            "\n\nYOUR CAPABILITIES:\n"
            "1. Smart AI: You answer any question using advanced logic and Google Search.\n"
            "2. Event Management: You save dates (birthdays, weddings) and send automated greetings.\n"
            "3. Group Buying: You help manage and track group purchases and member balances.\n"
            "4. Bilingual Support: You fully support Hebrew and English."
        )
        
        if user_inst:
            system_instruction += f"\n\nADDITIONAL USER INSTRUCTIONS (CRITICAL):\n{user_inst}"

        # Convert simple history format to Gemini API format
        contents = []
        if history:
            for msg in history:
                role = "user" if msg['role'] == "user" else "model"
                contents.append({"role": role, "parts": [{"text": msg['text']}]})
        
        # Add current prompt
        contents.append({"role": "user", "parts": [{"text": prompt}]})

        # Grounding with Google Search only if necessary to save quota
        tools = []
        search_keywords = ["מזג אוויר", "חדשות", "שער", "דולר", "יורו", "היום", "עכשיו", "מחיר", "investing", "news", "weather", "exchange"]
        if any(k in prompt.lower() for k in search_keywords):
            logging.info("🌐 Prompt requires search grounding...")
            tools = [{"google_search": {}}]

        headers = {'Content-Type': 'application/json'}
        payload = {
            "contents": contents,
            "system_instruction": {"parts": [{"text": system_instruction}]}
        }
        if tools:
            payload["tools"] = tools

        for model in models:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
            try:
                logging.info(f"🧠 AI: Trying model {model}...")
                resp = requests.post(url, headers=headers, json=payload, timeout=20)
                if resp.status_code == 200:
                    data = resp.json()
                    if 'candidates' in data and len(data['candidates']) > 0:
                        logging.info(f"✅ AI: Success with {model}")
                        return data['candidates'][0]['content']['parts'][0]['text'].strip()
                elif resp.status_code == 429:
                    self._last_ai_error = 429
                    logging.warning(f"⚠️ Rate Limit (429) for {model}. Waiting 3s...")
                    time.sleep(3)
                    # Try once more with same model after sleep
                    resp = requests.post(url, headers=headers, json=payload, timeout=20)
                    if resp.status_code == 200:
                        data = resp.json()
                        if 'candidates' in data and len(data['candidates']) > 0:
                            self._last_ai_error = None
                            return data['candidates'][0]['content']['parts'][0]['text'].strip()
                elif resp.status_code == 404:
                    logging.info(f"ℹ️ Model {model} not found.")
                else:
                    self._last_ai_error = resp.status_code
                    logging.error(f"❌ Gemini Error ({model}): {resp.status_code} - {resp.text}")
            except Exception as e:
                self._last_ai_error = "exception"
                logging.error(f"❌ Gemini Exception ({model}): {e}")

        # --- LAST RESORT: TRY WITHOUT TOOLS (Search Grounding often hits limits first) ---
        logging.info("🆘 All models failed or limited. Trying without tools...")
        payload_no_tools = {
            "contents": contents,
            "system_instruction": {"parts": [{"text": system_instruction}]}
        }
        for model in ["gemini-1.5-flash", "gemini-2.0-flash"]:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
            try:
                resp = requests.post(url, headers=headers, json=payload_no_tools, timeout=20)
                if resp.status_code == 200:
                    data = resp.json()
                    if 'candidates' in data and len(data['candidates']) > 0:
                        logging.info(f"✅ AI: Success (No Tools) with {model}")
                        return data['candidates'][0]['content']['parts'][0]['text'].strip()
            except: pass
        
        return None

    def handle_image_message(self, sender, image_data):
        import base64
        settings = load_settings()
        api_key = settings.get("gemini_api_key")
        if not api_key:
            return

        url = image_data.get('url')
        caption = image_data.get('caption', '')
        
        logging.info(f"📥 Downloading image from {url}")
        try:
            resp = requests.get(url, timeout=30)
            if resp.status_code == 200:
                img_bytes = resp.content
                
                prompt = """Identify this product. 
                If there is a barcode, find the product name associated with it.
                Return ONLY a JSON object in this format: 
                {"name": "Product Name", "barcode": "BarcodeValue"}
                If no barcode is found, set "barcode" to null.
                Be as accurate as possible with the product name."""
                
                if caption:
                    prompt = f"The user says: '{caption}'. " + prompt

                res_text = self.call_gemini_with_image(api_key, img_bytes, prompt)
                if res_text:
                    try:
                        # Basic cleanup if AI adds markdown
                        cleaned = res_text.replace("```json", "").replace("```", "").strip()
                        data = json.loads(cleaned)
                        
                        name = data.get('name', 'מוצר חדש')
                        barcode = data.get('barcode')
                        
                        # Store as pending
                        self.pending_products[sender] = {
                            "name": name,
                            "barcode": barcode,
                            "image_url": url
                        }
                        
                        reply = f"🔍 זיהיתי את המוצר: *{name}* \n"
                        if barcode: reply += f"🔢 ברקוד: {barcode}\n"
                        reply += "\n*מה המחיר של המוצר?* (שלח רק מספר)"
                        self.send_whatsapp(sender, reply)
                    except:
                        self.send_whatsapp(sender, f"🔍 *SYD-AI Vision:* \n\n{res_text}")
            else:
                logging.error(f"Failed to download image: {resp.status_code}")
        except Exception as e:
            logging.error(f"Error in handle_image_message: {e}")

    def call_gemini_with_image(self, api_key, img_bytes, prompt):
        import base64
        import time
        # Expanded multi-model fallback for higher reliability
        models = [
            "gemini-2.0-flash", 
            "gemini-2.0-flash-exp",
            "gemini-1.5-flash", 
            "gemini-1.5-flash-latest",
            "gemini-1.5-flash-002",
            "gemini-1.5-flash-8b"
        ]
        headers = {'Content-Type': 'application/json'}
        img_b64 = base64.b64encode(img_bytes).decode('utf-8')
        
        payload = {
            "contents": [{
                "parts": [
                    {"text": prompt},
                    {"inline_data": {"mime_type": "image/jpeg", "data": img_b64}}
                ]
            }]
        }
        
        for model in models:
            # Try each model, and if 429, wait and retry once
            for attempt in range(2):
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
                try:
                    logging.info(f"🧠 Trying Vision Model: {model} (Attempt {attempt+1})")
                    resp = requests.post(url, headers=headers, json=payload, timeout=30)
                    
                    if resp.status_code == 200:
                        data = resp.json()
                        if 'candidates' in data and len(data['candidates']) > 0:
                            return data['candidates'][0]['content']['parts'][0]['text'].strip()
                    
                    if resp.status_code == 429:
                        logging.warning(f"⏳ Rate limited (429) on {model}. Waiting 3s...")
                        time.sleep(3)
                        continue # Retry this model
                    
                    logging.warning(f"⚠️ {model} failed: {resp.status_code}")
                    break # Move to next model
                except Exception as e:
                    logging.error(f"❌ {model} exception: {e}")
                    break
        return None

    def send_whatsapp(self, phone, message):
        if not phone: return False
        
        # --- ROBUST CHAT ID RESOLUTION ---
        raw_phone = str(phone).strip()
        
        # Fix reversed chatId if accidentally provided (e.g. c.us@number)
        if raw_phone.startswith("c.us@") or raw_phone.startswith("g.us@"):
            parts = raw_phone.split("@", 1)
            raw_phone = f"{parts[1]}@{parts[0]}"
        
        if "@" in raw_phone:
            chat_id = raw_phone
        else:
            # Reformat digit-only number
            clean_phone = "".join(filter(str.isdigit, raw_phone))
            
            # Smart Israel formatting
            if clean_phone.startswith("05"): 
                chat_id = "972" + clean_phone[1:]
            elif clean_phone.startswith("0"): # Other Israeli numbers or prefixes
                chat_id = "972" + clean_phone[1:]
            elif clean_phone.startswith("00"):
                chat_id = clean_phone[2:]
            else:
                chat_id = clean_phone
            
            if not chat_id.endswith("@c.us") and not chat_id.endswith("@g.us"): 
                chat_id += "@c.us"
        
        logging.info(f"📤 Sending to {chat_id}...")
        url = f"{API_URL}/sendMessage/{API_TOKEN}"
        payload = {"chatId": chat_id, "message": message}
        try:
            resp = requests.post(url, json=payload, timeout=20)
            if resp.status_code == 200:
                return True
            else:
                print(f"❌ שגיאה בשליחה ל-{chat_id}: {resp.text}")
                return False
        except Exception as e:
            print(f"❌ תקלה ברשת בשליחה: {e}")
            return False



agent = Agent()
# Start the bot background thread immediately
agent.start_bot_loop()

# --- ROUTES ---

@app.route('/api/status', methods=['GET'])
def get_status():
    return jsonify({
        "status": "connected",
        "phone": OWNER_PHONE
    })

@app.route('/')
def index():
    try:
        with open('dashboard.html', 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        return f"Error loading dashboard: {e}"


@app.route('/api/events', methods=['GET'])
def get_events():
    return jsonify(agent.load_events())

@app.route('/api/add_event', methods=['POST'])
def add_event_route():
    agent.add_event_internal(request.json)
    return jsonify({"status": "ok"})

@app.route('/api/delete_event', methods=['POST'])
def delete_event_route():
    data = request.json
    agent.delete_event(data.get('id'))
    return jsonify({"status": "ok"})

@app.route('/api/bot_response', methods=['GET', 'POST'])
def bot_response_settings():
    if request.method == 'POST':
        data = request.json
        settings = load_settings()
        settings['bot_response'] = data.get('response')
        settings['gemini_api_key'] = data.get('gemini_api_key', '')
        settings['enable_commands'] = data.get('enable_commands', True)
        settings['system_instruction'] = data.get('system_instruction', '')
        save_settings(settings)
        return jsonify({"status": "ok"})
    else:
        s = load_settings()
        return jsonify({
            "response": s.get('bot_response'),
            "gemini_api_key": s.get('gemini_api_key'),
            "enable_commands": s.get('enable_commands', True),
            "system_instruction": s.get('system_instruction', '')
        })

# --- BROADCAST ROUTE ---
@app.route('/api/broadcast_group', methods=['POST'])
def broadcast_group():
    data = request.json
    group_id = data.get('group_id')
    msg = data.get('message')
    
    if not msg: return jsonify({"error": "No message"}), 400
    
    phones = set()
    groups = load_groups()
    
    if group_id == 'all':
        # 1. Collect from Groups
        for g in groups:
            for m in g.get('members', []):
                if m.get('phone'): phones.add(m['phone'])
        
        # 2. Collect from Events
        try:
            events = agent.load_events()
            for e in events:
                if e.get('owner_phone'): phones.add(e['owner_phone'])
                if e.get('target_phone'): phones.add(e['target_phone'])
        except: pass
    else:
        # Specific group
        target_group = next((g for g in groups if str(g['id']) == str(group_id)), None)
        if target_group:
            for m in target_group.get('members', []):
                if m.get('phone'): phones.add(m['phone'])
    
    if not phones: 
        return jsonify({"status": "no_targets", "message": "לא נמצאו אנשי קשר בקבוצה זו"})

    print(f"📢 Starting Broadcast of '{msg[:30]}...' to {len(phones)} contacts...")
    
    def do_broadcast():
        count = 0
        for p in phones:
            if agent.send_whatsapp(p, msg):
                count += 1
            time.sleep(1) # Rate limit protection
        print(f"✅ Broadcast finished. Sent to {count} people.")

    # Run in background to not block UI
    threading.Thread(target=do_broadcast, daemon=True).start()
    
    return jsonify({"status": "started", "target_count": len(phones)})

@app.route('/api/broadcast_test', methods=['POST'])
def broadcast_test():
    # Keep old test route for backward compatibility or remove it
    return broadcast_group()

# --- GROUPS ROUTES ---

def load_groups():
    try:
        with open(GROUPS_FILE, 'r', encoding='utf-8') as f: return json.load(f)
    except: return []

def save_groups(groups):
    with open(GROUPS_FILE, 'w', encoding='utf-8') as f:
        json.dump(groups, f, indent=2, ensure_ascii=False)

@app.route('/api/groups', methods=['GET'])
def get_groups():
    return jsonify(load_groups())

@app.route('/api/groups/add', methods=['POST'])
def add_group():
    data = request.json
    name = data.get('name')
    if not name: return jsonify({"error": "No name"}), 400
    
    groups = load_groups()
    if any(g['name'] == name for g in groups):
        return jsonify({"status": "exists"}), 200
        
    new_group = {
        "id": int(time.time()),
        "name": name,
        "members": []
    }
    groups.append(new_group)
    save_groups(groups)
    return jsonify({"status": "ok", "group": new_group})

@app.route('/api/groups/add_member', methods=['POST'])
def add_member():
    data = request.json
    group_id = data.get('group_id')
    name = data.get('name')
    phone = data.get('phone')
    
    groups = load_groups()
    for g in groups:
        if str(g['id']) == str(group_id):
            g['members'].append({"name": name, "phone": phone})
            save_groups(groups)
            return jsonify({"status": "ok"})
            
    return jsonify({"error": "Group not found"}), 404

@app.route('/api/groups/delete_member', methods=['POST'])
def delete_member():
    data = request.json
    group_id = data.get('group_id')
    phone = data.get('phone')
    
    groups = load_groups()
    for g in groups:
        if str(g['id']) == str(group_id):
            g['members'] = [m for m in g['members'] if m.get('phone') != phone]
            save_groups(groups)
            return jsonify({"status": "ok"})
            
    return jsonify({"error": "Group not found"}), 404

@app.route('/api/send_now', methods=['POST'])
def send_now():
    data = request.json
    # Manual trigger
    success = agent.send_whatsapp(data.get('phone'), data.get('msg'))
    return jsonify({"status": "sent" if success else "error"})

@app.route('/verify_code', methods=['POST'])
def verify_code():
    data = request.json
    code = data.get('code')
    codes = load_codes()
    
    if code in codes and codes[code].get('status') == 'active':
        return jsonify({"valid": True, "user": codes[code]})
    return jsonify({"valid": False})

@app.route('/api/test_ai', methods=['POST'])
def test_ai():
    data = request.json
    prompt = data.get('prompt', 'שלום')
    settings = load_settings()
    api_key = settings.get("gemini_api_key")
    if not api_key: return jsonify({"error": "No API Key"}), 400
    
    reply = agent.call_gemini(api_key, prompt)
    if reply:
        return jsonify({"status": "ok", "reply": reply})
    else:
        return jsonify({"status": "error", "msg": "Failed to get reply from AI (check logs)"})

# --- PURCHASES & PROJECTS ROUTES ---
@app.route('/api/purchases', methods=['GET', 'POST'])
def handle_purchases():
    if request.method == 'POST':
        data = request.json
        purchases = agent.load_purchases()
        new_sale = {
            "id": int(time.time()),
            "client_name": data.get('client_name', 'כללי'),
            "name": data.get('product_name', 'מוצר'),
            "client_email": data.get('client_email', ''),
            "price": data.get('price', '0'),
            "stock": 1,
            "orders": [],
            "status": "active",
            "created_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        }
        purchases.append(new_sale)
        agent.save_purchases(purchases)
        return jsonify({"status": "ok", "id": new_sale['id']})
    else:
        return jsonify(agent.load_purchases())

@app.route('/api/purchases/close', methods=['POST'])
def close_sale_api():
    data = request.json
    sale_id = data.get('id')
    purchases = agent.load_purchases()
    for p in purchases:
        if str(p['id']) == str(sale_id):
            p['status'] = 'closed'
            break
    agent.save_purchases(purchases)
    return jsonify({"status": "ok"})

# --- STORES ROUTES ---
@app.route('/api/stores', methods=['GET', 'POST'])
def handle_stores():
    if request.method == 'POST':
        data = request.json
        stores = agent.load_stores()
        new_store = {
            "id": int(time.time()),
            "name": data.get('name', 'חנות ללא שם'),
            "phone": data.get('phone', ''),
            "image": data.get('image', ''),
            "products": [],
            "created_at": datetime.datetime.now().strftime("%Y-%m-%d")
        }
        stores.append(new_store)
        agent.save_stores(stores)
        return jsonify({"status": "ok", "store": new_store})
    else:
        return jsonify(agent.load_stores())

@app.route('/api/stores/client', methods=['POST'])
def add_store_client_api():
    data = request.json
    store_id = data.get('store_id')
    name = data.get('name')
    phone = data.get('phone')
    product = data.get('product', '')
    notes = data.get('notes', '')
    if agent.add_store_client(store_id, name, phone, product, notes, "manual_dashboard"):
        return jsonify({"status": "ok"})
    return jsonify({"error": "Failed"}), 400

@app.route('/api/stores/product', methods=['POST', 'PUT', 'DELETE'])
def manage_store_product():
    data = request.json
    store_id = data.get('store_id')
    
    if request.method == 'POST':
        name = data.get('name')
        price = data.get('price')
        image = data.get('image', '')
        barcode = data.get('barcode', '')
        if agent.add_store_product(store_id, name, price, image, barcode):
            return jsonify({"status": "ok"})
            
    elif request.method == 'PUT':
        product_id = data.get('product_id')
        name = data.get('name')
        price = data.get('price')
        image = data.get('image', '')
        barcode = data.get('barcode', '')
        if agent.update_store_product(store_id, product_id, name, price, image, barcode):
             return jsonify({"status": "ok"})
             
    elif request.method == 'DELETE':
        product_id = data.get('product_id')
        if agent.delete_store_product(store_id, product_id):
             return jsonify({"status": "ok"})

    return jsonify({"error": "Operation failed"}), 400

@app.route('/api/stores/invoice', methods=['POST'])
def add_store_invoice_api():
    data = request.json
    store_id = data.get('store_id')
    client = data.get('client')
    amount = data.get('amount')
    items = data.get('items', '')
    if agent.add_store_invoice(store_id, client, amount, items):
        return jsonify({"status": "ok"})
    return jsonify({"error": "Failed"}), 400

@app.route('/api/stores/logs', methods=['GET'])
def get_store_logs():
    store_id = request.args.get('store_id')
    stores = agent.load_stores()
    for s in stores:
        if str(s['id']) == str(store_id):
            return jsonify(s.get('logs', []))
    return jsonify([])

@app.route('/api/stores/invoices', methods=['GET'])
def get_store_invoices():
    store_id = request.args.get('store_id')
    stores = agent.load_stores()
    for s in stores:
        if str(s['id']) == str(store_id):
            return jsonify(s.get('invoices', []))
    return jsonify([])

@app.route('/api/received_all', methods=['GET'])
def get_received_all():
    # Consolidate all known contacts
    groups = load_groups()
    events = agent.load_events()
    contacts = []
    
    # Track unique phones
    seen = set()
    
    for g in groups:
        for m in g.get('members', []):
            raw = m.get('phone', '')
            phone_clean = "".join(filter(str.isdigit, raw))
            if phone_clean and phone_clean not in seen:
                contacts.append({"name": m['name'], "phone": m['phone'], "source": f"קבוצה: {g['name']}"})
                seen.add(phone_clean)
                
    for e in events:
        phone_raw = e.get('owner_phone') or e.get('target_phone')
        if not phone_raw: continue
        phone_clean = "".join(filter(str.isdigit, phone_raw))
        if phone_clean and phone_clean not in seen:
            contacts.append({"name": e['owner'], "phone": phone_raw, "source": f"אירוע: {e.get('type')}"})
            seen.add(phone_clean)
            
    return jsonify(contacts)

@app.route('/api/ai/identify', methods=['POST'])
def ai_identify():
    data = request.json
    barcode = data.get('barcode')
    image_b64 = data.get('image') # Optional base64
    
    settings = load_settings()
    api_key = settings.get("gemini_api_key")
    if not api_key: return jsonify({"error": "No API Key"}), 400
    
    prompt = "Identify this product name based on the data. Return ONLY the name in Hebrew if possible. "
    models = ["gemini-2.0-flash", "gemini-1.5-flash-latest"]
    
    if barcode:
        prompt += f"Barcode: {barcode}"
    
    if image_b64:
        import base64
        img_bytes = base64.b64decode(image_b64)
        name = agent.call_gemini_with_image(api_key, img_bytes, prompt)
        return jsonify({"name": name})

    # Text-only identification for barcode
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    for model in ["gemini-2.0-flash", "gemini-1.5-flash", "gemini-1.5-flash-latest"]:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        try:
            import time
            resp = requests.post(url, json=payload, timeout=20)
            if resp.status_code == 429:
                time.sleep(2)
                resp = requests.post(url, json=payload, timeout=20)
            
            if resp.status_code == 200:
                res_data = resp.json()
                name = res_data['candidates'][0]['content']['parts'][0]['text'].strip()
                return jsonify({"name": name})
        except: pass
    
    return jsonify({"name": "לא זוהה"})

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    print(f"Starting SYD-AI Backend on port {port}...")
    app.run(host='0.0.0.0', port=port)
