"""
Configuration and defaults for the Reasoning feature.
These are intentionally simple and local to the Django backend.
"""
from dataclasses import dataclass


@dataclass
class ReasoningConfig:
    # Toggle: attempt LLM-backed reasoning if Azure env is configured; else fallback
    use_llm: bool = True

    # System instruction for the LLM. Keep it concise and utility-focused.
    system_prompt: str = (
        "You are an expert analyst. Think step-by-step, but return only the final reasoning in clear, concise markdown.\n"
        "Use short sections, bullets when helpful, and include a brief conclusion."
    )

    # Optional max tokens for the reasoning response
    max_output_tokens: int = 1024

    # Fallback content when LLM isn't available or errors occur
    fallback_markdown: str = (
        "### Reasoning\n\n"
        "- I considered the question, identified key factors, and synthesized a conclusion.\n"
        "- To go deeper, provide more context, constraints, or examples.\n\n"
        "### Conclusion\n\n"
        "This is a concise, static fallback while the full reasoning provider is unavailable."
    )


def get_default_config() -> ReasoningConfig:
    return ReasoningConfig()
