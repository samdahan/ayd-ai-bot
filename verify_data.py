
import json
import sys

# Encode for Windows Console
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

try:
    with open('events.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
        print("Successfully read JSON.")
        print(json.dumps(data, indent=2, ensure_ascii=False))
except Exception as e:
    print(f"Error reading JSON: {e}")
