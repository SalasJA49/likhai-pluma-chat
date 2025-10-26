from .llm import chat
from .config import LLM_LOCALS

def extract_style_prompt(combined_text: str) -> list[dict]:
    """
    Recreates your old extract_style() message stack that used:
    st.session_state.locals["llm_instructions"], ["training_content"], ["training_output"]
    """
    return [
        {"role": "system",    "content": LLM_LOCALS.get("llm_instructions", "")},
        {"role": "user",      "content": LLM_LOCALS.get("training_content", "")},
        {"role": "assistant", "content": LLM_LOCALS.get("training_output", "")},
        {"role": "user",      "content": combined_text},
    ]

def rewrite_prompt(content_all: str, style: str, guidelines: str, example: str) -> list[dict]:
    system = "\n".join([
        "You are an expert writer assistant. Rewrite the user input based on the following writing style, writing guidelines and writing example.\n",
        f"<writingStyle>{style}</writingStyle>\n",
        f"<writingGuidelines>{guidelines}</writingGuidelines>\n",
        f"<writingExample>{example}</writingExample>\n",
        "Make sure to emulate the writing style, guidelines and example provided above.",
    ])
    return [
        {"role": "system", "content": system},
        {"role": "user",   "content": content_all},
    ]

def extract_style(combined_text: str, temperature: float = 0.0) -> str:
    return chat(extract_style_prompt(combined_text), temperature=temperature)

def rewrite_content(content_all: str, style: str, guidelines: str, example: str, temperature: float = 0.7) -> str:
    return chat(rewrite_prompt(content_all, style, guidelines, example), temperature=temperature)
