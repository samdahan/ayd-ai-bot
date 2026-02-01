
import requests

ID = "7103495194"
TOKEN = "c01223dea0844ae195759cac8585aaf96f1d1be3dffa47bc83"
URL = f"https://7103.api.greenapi.com/waInstance{ID}/sendMessage/{TOKEN}"

# נסה לשלוח לטלפון שלך (אני מניח שזה המספר שמקושר, אז זו שליחה לעצמי)
# או נסה לשלוח למספר הניהול אם קיים
payload = {
    "chatId": "972524247005@c.us", 
    "message": "👋 שלום! זו בדיקת תקשורת מהבוט החדש."
}

try:
    print("Testing send...")
    r = requests.post(URL, json=payload)
    print(f"Status: {r.status_code}")
    print(f"Response: {r.text}")
except Exception as e:
    print(e)
