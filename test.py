import requests
import os
from dotenv import load_dotenv

load_dotenv()
ELASTIC_HOST = os.environ["ELASTIC_HOST"]
ELASTIC_API_KEY = os.environ["ELASTIC_API_KEY"]

url = f"{ELASTIC_HOST}/s/space/api/agent_builder/agent_1/chat"

headers = {
        "Authorization": f"ApiKey {ELASTIC_API_KEY}",
        "Content-Type": "application/json"
}


payload = {
    "messages": [
        {
            "role": "user",
            "content": "2 + 2 = ?"
        }
    ]
}

r = requests.post(url, headers=headers, json=payload)

print(r.status_code)
print(r.text)   # IMPORTANT for debugging
r.raise_for_status()

data = r.json()
print(data)