import requests
import json

# Replace <deployment> with your deployment host
url = "https://my-elasticsearch-project-cf6846.kb.us-central1.gcp.elastic.cloud/_gpt/_chat"

headers = {
    "Authorization": "ApiKey MnhnX2pwd0JBSi1hVjVZN3VkWVM6bjVhME5pdHNDT1NSdTdoVHRkXzBEUQ==",
    "Content-Type": "application/json"
}

# Your prompt / chat message
payload = {
    "model": "gpt-4.1",   # Elastic GPT model
    "messages": [
        {"role": "user", "content": "2 + 2 = ?"}
    ]
}

# Send request
response = requests.post(url, headers=headers, json=payload)

# Check status
if response.status_code == 200:
    data = response.json()
    # Extract the model output text
    output_text = data["choices"][0]["message"]["content"]
    print("LLM Output:\n", output_text)
else:
    print("Error:", response.status_code, response.text)