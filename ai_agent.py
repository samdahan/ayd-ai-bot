
import time
import json
import os
import threading
import logging
import requests
import sys
import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS

# --- CONFIGURATION ---
ID_INSTANCE = "7103495194"
API_TOKEN = "c01223dea0844ae195759cac8585aaf96f1d1be3dffa47bc83"
API_URL = f"https://7103.api.greenapi.com/waInstance{ID_INSTANCE}"
OWNER_PHONE = "0515642201"

DATA_FILE = 'events.json'
GROUPS_FILE = 'groups.json'
CODES_FILE = 'codes.json'

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
        "gemini_api_key": ""
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

    def load_events(self):
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f: return json.load(f)
        except: return []

    def save_events(self, events):
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(events, f, ensure_ascii=False, indent=2)

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
            "scheduled_time": data.get('scheduled_time', ''), # New field for time scheduling
            "last_sent": ""
        }
        events.append(new_event)
        self.save_events(events)
        return True

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
                 should_send = False
                 e_type = event.get('type', 'general')
                 
                 # 1. Handle Scheduled Broadcast (One time)
                 if e_type == 'scheduled_broadcast':
                     # Check date (YYYY-MM-DD) and time (HH:MM)
                     if event.get('gregorian_date') == today.strftime("%Y-%m-%d"):
                         # Check time
                         if event.get('scheduled_time') == now_time:
                             print(f"⏰ Scheduled Broadcast triggering now!")
                             # Send to group/all
                             self.broadcast_internal(event.get('target_phone', 'all'), event.get('msg_template', ''))
                             to_delete.append(event['id'])
                             dirty = True
                             continue

                 # 2. Handle Recurring Events (Birthdays etc)
                 # Check Hebrew
                 if event.get('date_type') == 'hebrew' and event.get('hebrew_date') and h_date_str:
                     # Loose match (contains)
                     if event['hebrew_date'].replace("'","") in h_date_str.replace("'",""):
                         should_send = True
                         
                 # Check Gregorian
                 elif event.get('date_type') == 'gregorian' and event.get('gregorian_date'):
                     try:
                         # Compare MM-DD
                         if event['gregorian_date'][5:] == f"{today.month:02d}-{today.day:02d}":
                             should_send = True
                     except: pass
                 
                 # Send Logic for recurring
                 if should_send:
                     last = event.get('last_sent_year', 0)
                     if str(last) != str(current_year):
                         msg = event.get('msg_template', 'Mazal Tov!')
                         
                         print(f"🚀 Automated Send Event for {event['owner']}...")
                         
                         # 1. Send to Target (User/Admin)
                         t_phone = event.get('target_phone')
                         if t_phone:
                             self.send_whatsapp(t_phone, f"תזכורת: היום יום הולדת ל{event['owner']}!")
                             
                         # 2. Send to Owner (Celebrant/Baal Simcha)
                         o_phone = event.get('owner_phone')
                         if o_phone:
                             self.send_whatsapp(o_phone, msg)

                         event['last_sent_year'] = current_year
                         dirty = True
             
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
                    self.handle_command(sender, text)
                else:
                    print(f"📦 Ignored message type: {type_msg}")
            
            elif w_type == 'stateInstanceChanged':
                print(f"ℹ️ State Instance: {body.get('stateInstance')}")
            
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

        # 2. GREETINGS
        elif any(k in text for k in ["שלום", "היי", "הלו", "מה קורה", "מה שלומך", "מה איתך", "מה נשמע", "hi", "hello"]):
             reply = "שלום! אני SYD-AI, הסוכן הדיגיטלי החכם 🤖. איך אני יכול לעזור לכם היום? ✨"

        # 3. HELP & CAPABILITIES (What I CAN do)
        elif any(k in text for k in ["מה אתה יודע", "מה אתה יודעת", "מה אתה עושה", "מה את עושה", "יכולות", "מה אתה יכול", "מה את יכולה", "help"]):
            reply = (
                "אני SYD-AI הסוכן הדיגיטלי החכם! 🤖💎\n\n"
                "הנה מה שאני יודע לעשות:\n"
                "1️⃣ *מענה חכם*: אני מחובר לבינה מלאכותית ויודע לענות על כל שאלה (כולל נתונים חיים מהאינטרנט)! 🧠\n"
                "2️⃣ *ניהול שמחות*: אני שומר אירועים וימי הולדת ושולח ברכות אוטומטיות לקבוצות! 🎂🎉\n\n"
                "שאלו אותי *'איך אתה עושה את זה?'* כדי לקבל הוראות שימוש! 🚀"
            )

        elif any(k in text for k in ["איך אתה עושה", "איך את עושה", "איך עובד", "איך להשתמש", "הוראות"]):
            reply = (
                "הנה הסבר קצר על איך להפעיל אותי: ✨\n\n"
                "💡 *שאלות כלליות*: פשוט תכתבו לי כל דבר (למשל: 'מי היה הרבי מלובביץ'?' או 'מתכון לעוגה') ואני אענה לכם מיד! 🧠\n"
                "💡 *שמירת אירוע*: כתבו 'תוסיף' + שם + תאריך (למשל: 'תוסיף משה 12/07') ואני אזכור לברך אותו! 📅\n"
                "💡 *בדיקת חיבור*: כתבו 'סטטוס' ואני אגיד לכם אם הכל תקין. 💎\n\n"
                "אני כאן לכל מה שתצטרכו! 🚀"
            )

        elif any(k in text for k in ["עזרה", "תפריט"]):
            reply = "אני כאן לעזור! 🤖\nתכתבו 'מה אתה עושה' כדי לראות את היכולות שלי, או 'איך אתה עושה' להוראות שימוש. ✨"

        elif any(k in text for k in ["תודה", "סבבה", "מגניב", "thanks", "cool"]):
             reply = random.choice([
                 "בשמחה! SYD-AI תמיד כאן בשבילך 🙏",
                 "בכיף! אל תהסס לבקש עוד משהו מ-SYD-AI 😊",
                 "שמחתי לעזור! ✨"
             ])

        elif "סטטוס" in text or "status" in text:
            # ONLY FOR ADMIN
            if OWNER_PHONE in sender or "972" + OWNER_PHONE[1:] in sender:
                reply = "🤖 מערכת SYD-AI הסוכן החכם פועלת כרגיל! ✅\nהכל מחובר והאירועים מתוזמנים 💎"
            else:
                # If not admin, use fallback
                settings = load_settings()
                reply = settings.get("bot_response", "כרגע אני SYD-AI הסוכן החכם 🤖 לא יודע לעשות את זה, אני מאמין שבהמשך הפיתוח אני יוכל לעזור לך. 🚀")

        elif "יוסי" in text:
             reply = "יוסי המלך! 👑"
             
        elif text == "כן" or text == "yes":
             reply = "שבת שלום! 🕯️🕯️ מ-SYD-AI הסוכן החכם 🤖 וצוות המפתחים 🚀"
        
        else:
            # --- SMART AI FALLBACK (Gemini) ---
            settings = load_settings()
            api_key = settings.get("gemini_api_key")
            
            if api_key:
                logging.info(f"🧠 Asking Gemini for: {text}")
                ai_reply = self.call_gemini(api_key, raw_text)
                if ai_reply:
                    reply = ai_reply
                else:
                    logging.warning("⚠️ Gemini failed to provide a reply.")
            
            # If AI failed or no key, use classic dynamic logic
            if not reply:
                custom_reply = settings.get("bot_response", "")
                if custom_reply:
                    reply = custom_reply
                else:
                    # Dynamic identification
                    action = "לעשות את זה"
                    for word in ["לבדוק", "לשלוח", "לעשות", "לקרוא", "לתקן", "לראות", "להראות", "לפתוח"]:
                        if word in text:
                            idx = text.find(word)
                            action = text[idx:].strip()
                            if "?" in action: action = action.split("?")[0]
                            if "." in action: action = action.split(".")[0]
                            break
                    reply = f"כרגע אני SYD-AI הסוכן החכם 🤖 לא יודע {action}, אני מאמין שבהמשך הפיתוח אני יוכל לעזור לך. 🚀"

        # --- REMOTE ADMIN CONTROL ---
        if self.is_admin(sender):
            if text == "עזרה למנהל" or text == "admin help":
                reply = (
                    "💎 *לוח בקרה מרחוק - SYD-AI* 🤖\n\n"
                    "📢 *שידור לשלוח [קבוצה] [הודעה]* - שליחה קבוצתית.\n"
                    "📝 *עדכן מענה [טקסט]* - שינוי תשובת ברירת המחדל.\n"
                    "📋 *קבוצות* - רשימת כל קבוצות התפוצה.\n"
                    "🔍 *יומן* - 10 הפעולות האחרונות של הבוט.\n"
                    "🤖 *בדוק AI [שאלה]* - בדיקה ישירה של המנוע.\n"
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
            # Ensure "Thank you" closing
            if "תודה רבה" not in reply:
                reply += "\nתודה רבה 🙏"
            self.send_whatsapp(sender, reply)
            self.log_activity(f"Replied to {sender}: {text[:20]}")

    # --- HELPERS ---
    def call_gemini(self, api_key, prompt):
        """ Call Google Gemini API with fallback models based on observed availability """
        # Only using models that showed up in the key's listModels output
        models = [
            "gemini-2.0-flash", 
            "gemini-2.0-flash-lite", 
            "gemini-flash-latest",
            "gemini-pro-latest",
            "gemini-1.5-flash", 
            "gemini-1.5-pro"
        ]
        headers = {'Content-Type': 'application/json'}
        full_prompt = (
            "You are SYD-AI, a smart digital assistant for SAM DAHAN. "
            "You have access to real-time information via Google Search. "
            "IMPORTANT: When replying to users, DO NOT assume their name is Sam or SAM DAHAN. Just be friendly and professional. "
            "Reply in Hebrew in a friendly, helpful, and professional tone. "
            "Use emojis occasionally. Keep responses concise. "
            "If asked about current events or data (like exchange rates), use your search capability to provide accurate figures. "
            "The user said: " + prompt
        )
        # Enable Google Search grounding (Correct syntax)
        payload = {
            "contents": [{"parts": [{"text": full_prompt}]}],
            "tools": [{"google_search": {}}]
        }

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
                    logging.warning(f"⚠️ Gemini Rate Limit (429) for {model}.")
                elif resp.status_code == 404:
                    logging.info(f"ℹ️ Gemini Model {model} not found (404).")
                else:
                    logging.error(f"❌ Gemini Error ({model}): {resp.status_code} - {resp.text}")
            except Exception as e:
                logging.error(f"❌ Gemini Exception ({model}): {e}")
        
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
        save_settings(settings)
        return jsonify({"status": "ok"})
    else:
        s = load_settings()
        return jsonify({
            "response": s.get('bot_response'),
            "gemini_api_key": s.get('gemini_api_key')
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

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    print(f"Starting SYD-AI Backend on port {port}...")
    app.run(host='0.0.0.0', port=port)
