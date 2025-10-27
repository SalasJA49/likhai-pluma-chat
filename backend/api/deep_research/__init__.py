"""Deep research pipeline ported from chatui.deep_research.

This package exposes the same functions as the original chainlit-based
implementation but lives inside the Django backend so we don't depend on an
external `chatui` package at runtime.
"""

__all__ = ["pipeline", "formatting", "states", "prompts"]
