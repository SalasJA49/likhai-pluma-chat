import asyncio
import os
from typing import Awaitable, Callable, Dict, Optional, Tuple

from .config import get_default_config

NotifyFn = Callable[[Dict], Awaitable[None]]


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def _strip_thinking_tokens(text: str) -> str:
    # Hide potential model thinking tags
    return text.replace("<think>", "").replace("</think>", "").strip()


# ----------------------- Lightweight plan generation -----------------------
_plan_cache: Dict[str, str] = {}
_PLAN_CACHE_MAX = 128


def _classify_query(query: str) -> str:
    q = query.lower()
    if any(k in q for k in ["code", "function", "bug", "compile", "python", "typescript", "sql", "api"]):
        return "code"
    if any(k in q for k in ["data", "analy", "statistic", "eda", "chart", "model", "regression", "forecast"]):
        return "data"
    if any(k in q for k in ["write", "story", "poem", "blog", "tone", "creative", "outline"]):
        return "creative"
    return "general"


def _make_plan_prompt(cfg, query: str) -> Tuple[str, str]:
    domain = _classify_query(query)
    nudge = cfg.plan_domain_prompts.get(domain, "Outline a short high-level approach.")
    # Suggest example headings depending on domain to steer formatting
    if domain == "data":
        example = (
            "Use headings like: **Understanding the core question**, **Clarifying the time frame and context**, "
            "**Considering the source of data**, **Planning the data retrieval approach**, "
            "**Preparing to verify and present the answer**. Add one short sentence under each heading describing the approach."
        )
    elif domain == "code":
        example = (
            "Use headings like: **Understanding requirements**, **Considering edge cases**, "
            "**Planning the implementation**, **Verifying and testing**. Add one short sentence under each heading."
        )
    elif domain == "creative":
        example = (
            "Use headings like: **Defining the objective and tone**, **Gathering references/context**, "
            "**Outlining the structure**, **Refining and presenting**. Add one short sentence under each heading."
        )
    else:
        example = (
            "Use headings like: **Understanding the question**, **Gathering relevant context**, "
            "**Structuring the explanation**. Add one short sentence under each heading."
        )
    # System + user parts for providers that support role separation
    sys = cfg.plan_system_prompt
    user = (
        f"Task: {query}\n\n{nudge}\n{example}\n"
        f"Return {min(5, max(2, cfg.plan_max_bullets))} short bolded headings, each followed by ONE short sentence on the next line."
    )
    return sys, user


async def _call_foundry_plan(cfg, query: str, *, model_deployment: Optional[str], mode: Optional[str]) -> Optional[str]:
    try:
        from ..analytics.services.foundry_service import FoundryService  # type: ignore

        def _run() -> str:
            svc = FoundryService(model_deployment=model_deployment, mode=(mode or "work"))
            sys, user = _make_plan_prompt(cfg, query)
            prompt = f"[SYSTEM]\n{sys}\n\n[USER]\n{user}\n"
            return svc.complete(prompt)

        return await asyncio.to_thread(_run)
    except Exception:
        return None


async def _call_azure_plan(cfg, query: str) -> Optional[str]:
    endpoint = _env("AZURE_INFERENCE_ENDPOINT")
    deployment = _env("AZURE_DEEPSEEK_DEPLOYMENT") or _env("AZURE_OPENAI_DEPLOYMENT")
    api_key = _env("AZURE_AI_API_KEY") or _env("AZURE_OPENAI_API_KEY")
    if not (endpoint and deployment and api_key):
        return None
    try:
        from langchain_openai import AzureChatOpenAI  # type: ignore
        llm = AzureChatOpenAI(
            azure_endpoint=endpoint,
            deployment_name=deployment,
            api_key=api_key,
            model_kwargs={"response_format": {"type": "text"}},
            temperature=0.1,
            max_tokens=256,
            timeout=30,
        )
        sys, user = _make_plan_prompt(cfg, query)
        messages = [("system", sys), ("user", user)]
        resp = await llm.apredict_messages(messages)
        return _strip_thinking_tokens(str(resp))
    except Exception:
        return None


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

    # Optionally emit a brief, high-level plan (not chain-of-thought)
    if cfg.emit_thinking_plan and len(query.strip()) >= cfg.min_query_len_for_plan:
        lower = query.strip().lower()
        if not any(k == lower for k in cfg.skip_plan_keywords):
            plan: Optional[str] = _plan_cache.get(lower)
            if plan is None and cfg.use_llm:
                if (provider or "").lower() == "foundry":
                    plan = await _call_foundry_plan(cfg, query, model_deployment=model_deployment, mode=mode)
                if not plan:
                    plan = await _call_azure_plan(cfg, query)
            if not plan:
                # Deterministic fallback: structured short headings
                dom = _classify_query(query)
                if dom == "data":
                    plan = "\n".join([
                        "**Understanding the core question**",
                        "Clarify what is being asked, scope, and constraints.",
                        "**Clarifying the time frame and context**",
                        "Establish periods, segments, and any relevant context.",
                        "**Considering the source of data**",
                        "Identify tables/files, fields, and data quality considerations.",
                        "**Planning the data retrieval approach**",
                        "Choose filters/joins/aggregations at a high level.",
                        "**Preparing to verify and present the answer**",
                        "Plan quick checks, visual summary, and a concise explanation.",
                    ])
                elif dom == "code":
                    plan = "\n".join([
                        "**Understanding requirements**",
                        "Confirm inputs, outputs, and constraints.",
                        "**Considering edge cases**",
                        "List tricky inputs, limits, and error modes.",
                        "**Planning the implementation**",
                        "Outline components, data flow, and responsibilities.",
                        "**Verifying and testing**",
                        "Decide minimal tests and validation strategy.",
                    ])
                elif dom == "creative":
                    plan = "\n".join([
                        "**Defining the objective and tone**",
                        "Agree on intent, audience, and voice.",
                        "**Gathering references/context**",
                        "Collect facts, themes, or examples.",
                        "**Outlining the structure**",
                        "Sketch sections and key beats.",
                        "**Refining and presenting**",
                        "Tighten phrasing and finalize the delivery.",
                    ])
                else:
                    plan = "\n".join([
                        "**Understanding the question**",
                        "Clarify the ask and constraints.",
                        "**Gathering relevant context**",
                        "Identify key factors and assumptions.",
                        "**Structuring the explanation**",
                        "Choose a concise, logical presentation.",
                    ])
            # Cache and emit
            if plan:
                if len(_plan_cache) >= _PLAN_CACHE_MAX:
                    try:
                        _plan_cache.pop(next(iter(_plan_cache)))
                    except Exception:
                        _plan_cache.clear()
                _plan_cache[lower] = plan
                # Stream sanitized plan as the 'thinking' preview
                await notify({"event": "thinking", "message": plan})

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
