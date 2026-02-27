class LocalLLM:
    def __init__(self, pipe, max_tokens=256):
        self.pipe = pipe
        self.max_tokens = max_tokens

    def generate(self, messages):
        """
        messages: list of dicts like [{"role": "user", "content": "..."}]
        """
        # Combine messages into a single prompt
        prompt = "\n".join(m["content"] for m in messages)
        outputs = self.pipe(prompt, max_new_tokens=self.max_tokens)
        # HuggingFace pipeline returns a list of dicts with 'generated_text'
        text = outputs[0]["generated_text"]
        return text

    # Optional: if agent builder expects .invoke()
    def invoke(self, message: str):
        return self.generate([{"role": "user", "content": message}])