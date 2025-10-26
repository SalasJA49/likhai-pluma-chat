import os
from openai import AzureOpenAI

USE_MOCK = not (os.getenv("AZURE_OPENAI_ENDPOINT") and os.getenv("AZURE_OPENAI_KEY") and os.getenv("AZURE_OPENAI_API_VERSION") and os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT"))

if not USE_MOCK:
    _client = AzureOpenAI(
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
        api_key=os.getenv("AZURE_OPENAI_KEY"),
        api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
    )

def chat(messages, temperature=0.7, response_format="text") -> str:
    if USE_MOCK:
        # simple, deterministic stub so dev keeps moving
        user_last = next((m["content"] for m in reversed(messages) if m["role"]=="user"), "")
        return f"[MOCK LLM] temperature={temperature}\n\n{user_last[:1200]}"
    rsp = _client.chat.completions.create(
        model=os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT"),
        messages=messages,
        temperature=temperature,
        stream=False,
        response_format={"type": response_format},
    )
    return rsp.choices[0].message.content or ""
