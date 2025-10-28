import asyncio
import os
from typing import Awaitable, Callable, Dict, Optional

from .config import get_default_config

NotifyFn = Callable[[Dict], Awaitable[None]]


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def _strip_thinking_tokens(text: str) -> str:
    # Hide potential model thinking tags
    return text.replace("<think>", "").replace("</think>", "").strip()


async def _call_azure_reasoning(prompt: str, query: str, max_tokens: int) -> Optional[str]:
    """Call Azure AI Chat Completions if configured. Returns markdown or None on failure."""
    endpoint = _env("AZURE_INFERENCE_ENDPOINT")
    deployment = _env("AZURE_DEEPSEEK_DEPLOYMENT") or _env("AZURE_OPENAI_DEPLOYMENT")
    api_key = _env("AZURE_AI_API_KEY") or _env("AZURE_OPENAI_API_KEY")

    if not (endpoint and deployment and api_key):
        return None

    try:
        # Import locally to avoid hard dependency when not configured
        from langchain_openai import AzureChatOpenAI  # type: ignore

        llm = AzureChatOpenAI(
            azure_endpoint=endpoint,
            deployment_name=deployment,
            api_key=api_key,
            model_kwargs={"response_format": {"type": "text"}},
            temperature=0.2,
            max_tokens=max_tokens,
            timeout=60,
        )
        messages = [
            ("system", prompt),
            ("user", f"Question:\n{query}\n\nRespond in well-structured markdown."),
        ]
        resp = await llm.apredict_messages(messages)  # returns a string content
        return _strip_thinking_tokens(str(resp))
    except Exception:
        return None


async def _call_foundry_reasoning(system_prompt: str, query: str, max_tokens: int, *, model_deployment: Optional[str], mode: Optional[str]) -> Optional[str]:
    """Use Foundry Agents (via FoundryService) to get a markdown reasoning response.
    Returns None if unavailable or on error.
    """
    try:
        # Import lazily and construct a blocking client; run in thread to avoid blocking loop
        from ..analytics.services.foundry_service import FoundryService  # type: ignore

        def _run() -> str:
            svc = FoundryService(model_deployment=model_deployment, mode=(mode or "work"))
            prompt = (
                f"[SYSTEM]\n{system_prompt.strip()}\n\n"
                f"[TASK]\nAnswer the user's question with clear, concise markdown. Max ~{max_tokens} tokens.\n\n"
                f"[QUESTION]\n{query.strip()}\n"
            )
            return svc.complete(prompt)

        import asyncio
        return await asyncio.to_thread(_run)
    except Exception:
        return None


async def run_reasoning(query: str, notify: NotifyFn, *, provider: Optional[str] = None, model_deployment: Optional[str] = None, mode: Optional[str] = None) -> str:
    """
    Generate markdown reasoning for the user's query.

    - Streams minimal status updates via `notify`.
    - Returns the final markdown string.
    """
    cfg = get_default_config()

    await notify({"event": "ready"})
    await notify({"event": "thinking", "message": "Analyzing request and planning reasoning…"})

    # Try LLM-backed reasoning if configured
    markdown: Optional[str] = None
    if cfg.use_llm:
        # If provider is explicitly Foundry, try that first using the selected deployment/mode
        if (provider or "").lower() == "foundry":
            markdown = await _call_foundry_reasoning(cfg.system_prompt, query, cfg.max_output_tokens, model_deployment=model_deployment, mode=mode)
        # Fallback to Azure Chat Completions env path
        if not markdown:
            markdown = await _call_azure_reasoning(cfg.system_prompt, query, cfg.max_output_tokens)

    if not markdown:
        # Fallback deterministic content
        await notify({"event": "fallback", "message": "LLM unavailable; using static reasoning."})
        markdown = cfg.fallback_markdown

    await notify({"event": "finalize", "message": "Formatting reasoning output."})
    return markdown
