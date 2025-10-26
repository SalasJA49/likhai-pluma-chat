from typing import List, Dict
from .llm import chat as aoai_chat

DEFAULT_SYSTEM = (
    "You are BSP AI Assistant. Be professional, concise, and helpful. "
    "If unsure, say so and suggest where to verify."
)

def run_chat(messages: List[Dict], temperature: float = 0.7) -> str:
    """
    messages: OpenAI-style list:
      [{"role":"system","content":"..."},{"role":"user","content":"..."}...]
    """
    # Ensure there's at least one system message
    has_system = any(m.get("role") == "system" for m in messages)
    if not has_system:
        messages = [{"role": "system", "content": DEFAULT_SYSTEM}] + messages

    return aoai_chat(messages, temperature=temperature, response_format="text")
