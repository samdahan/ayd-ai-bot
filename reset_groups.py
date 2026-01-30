
import json
import os
import sys

# Encode for Windows Console
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

GROUPS_FILE = 'groups.json'

# User requested: משפחה 2 אחים 3 קרובים 5 חברים 6 עבודה
defaults = [
    {"id": 1, "name": "משפחה", "members": []},
    {"id": 2, "name": "אחים", "members": []},
    {"id": 3, "name": "קרובים", "members": []},
    {"id": 5, "name": "חברים", "members": []},
    {"id": 6, "name": "עבודה", "members": []}
]

try:
    with open(GROUPS_FILE, 'w', encoding='utf-8') as f:
        json.dump(defaults, f, ensure_ascii=False, indent=2)
    print("✅ Groups list updated successfully.")
except Exception as e:
    print(f"❌ Error updating groups: {e}")
