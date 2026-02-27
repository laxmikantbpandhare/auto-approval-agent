import os
from openai import OpenAI
from dotenv import load_dotenv
load_dotenv()
# Load API key (ensure XAI_API_KEY is set in env)
api_key = os.environ["XAI_API_KEY"]

client = OpenAI(
    api_key=api_key,
    base_url="https://api.x.ai/v1",  # xAI endpoint for Grok
)

# Chat messages
messages = [
    {"role": "system", "content": "You are Grok, a helpful assistant."},
    {"role": "user", "content": "Hello! How does Grok differ from other LLMs?"}
]

# Create chat completion
response = client.chat.completions.create(
    model="grok-4-1-fast-reasoning",  # or any available Grok model
    messages=messages
)

print(response.choices[0].message["content"])