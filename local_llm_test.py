from llama_cpp import Llama

# Path to your GGUF model
model_path = "/Users/laxmikantbhaskarpandhare/Meta-Llama-3.1-8B-Instruct-128k-Q4_0.gguf"

# Load model
llm = Llama(model_path=model_path)

# Generate text
prompt = "Hello, LLaMA 3! Tell me a short joke."
output = llm(prompt, max_tokens=100)
print(output['choices'][0]['text'])