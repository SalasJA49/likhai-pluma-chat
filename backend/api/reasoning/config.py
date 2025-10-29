"""
Configuration and defaults for the Reasoning feature.
These are intentionally simple and local to the Django backend.
"""
from dataclasses import dataclass, field
from typing import Dict, List


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

    # --- Lightweight thinking/plan preview (non-sensitive) ---
    # Whether to emit a brief plan as a 'thinking' event (bulleted outline, no chain-of-thought)
    emit_thinking_plan: bool = True

    # Min length to generate a plan; skip trivial queries
    min_query_len_for_plan: int = 10

    # Skip plan when the query matches these trivial words
    skip_plan_keywords: List[str] = field(default_factory=lambda: ["hi", "hello", "thanks", "ok", "yes", "no"])

    # Max bullets in plan
    plan_max_bullets: int = 3

    # Prompt used to generate a short plan; must avoid exposing chain-of-thought.
    plan_system_prompt: str = (
        "You are an assistant that outlines a brief, high-level plan before answering.\n"
        "Return a very short markdown outline with 2-5 bolded headings. Under each heading, add ONE short sentence\n"
        "that describes the approach at a high level (do not reveal internal reasoning or chain-of-thought). For example:\n"
        "**Understanding the core question**\n"
        "Clarify what is being asked and any constraints.\n"
        "**Gathering relevant context**\n"
        "Identify key factors, sources, or assumptions.\n"
        "**Structuring the explanation**\n"
        "Decide the most concise and clear way to present the answer.\n"
        "Keep everything concise and non-sensitive."
    )

    # Domain-specific plan nudge prompts (optional)
    plan_domain_prompts: Dict[str, str] = field(default_factory=lambda: {
        "code": "Outline a short high-level approach to solve the coding task (e.g., key functions, main steps).",
        "data": "Outline a short high-level analysis plan (e.g., explore, model, evaluate).",
        "creative": "Outline a short structure/approach for the creative request (e.g., tone, sections).",
    })


def get_default_config() -> ReasoningConfig:
    return ReasoningConfig()
