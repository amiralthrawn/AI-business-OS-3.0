"""Perplexity (Sonar): the best tool for collecting live information from the
web with its sources. The Veilleur's only door to the outside world."""

import re

import httpx

from app.config import get_settings

URL = "https://api.perplexity.ai/v1/agent"


class PerplexityError(RuntimeError):
    pass


def configured() -> bool:
    return bool((get_settings().perplexity_api_key or "").strip())


def _post(body: dict, timeout: float) -> httpx.Response:
    settings = get_settings()
    try:
        return httpx.post(
            URL,
            headers={"Authorization": f"Bearer {settings.perplexity_api_key.strip()}", "Content-Type": "application/json"},
            json=body,
            timeout=timeout,
        )
    except httpx.HTTPError as exc:
        raise PerplexityError(f"Perplexity unreachable: {exc}") from exc


def ask(system: str, user: str, *, timeout: float = 90.0) -> tuple[str, list[str]]:
    """Returns (answer text, source URLs). Raises PerplexityError.

    Uses the Perplexity Agent API (the former Sonar endpoint was retired).
    Without an explicit model ("provider/model") the `fast` effort level is
    used, which searches the web by default."""

    settings = get_settings()
    if not configured():
        raise PerplexityError("PERPLEXITY_API_KEY is not set")
    body: dict = {"instructions": system, "input": user, "tools": [{"type": "web_search"}]}
    model = (settings.perplexity_model or "").strip()
    if "/" in model:
        body["model"] = model
    else:
        body["effort"] = "fast"
    res = _post(body, timeout)
    if res.status_code == 400 and "tools" in body:  # keep working if the tool is implied by the effort level
        res = _post({k: v for k, v in body.items() if k != "tools"}, timeout)
    if res.status_code != 200:
        raise PerplexityError(f"Perplexity answered {res.status_code}: {res.text[:200]}")
    try:
        output = res.json()["output"]
    except (KeyError, TypeError, ValueError) as exc:
        raise PerplexityError("Unexpected Perplexity answer") from exc
    text_parts: list[str] = []
    sources: list[str] = []
    for item in output if isinstance(output, list) else []:
        if not isinstance(item, dict):
            continue
        if item.get("type") == "search_results":
            sources += [r["url"] for r in item.get("results") or [] if isinstance(r, dict) and isinstance(r.get("url"), str)]
        elif item.get("type") == "message":
            text_parts += [c.get("text", "") for c in item.get("content") or [] if isinstance(c, dict) and c.get("type") == "output_text"]
    text = re.sub(r"\s*\[\d+\]", "", "".join(text_parts)).strip()
    if not text:
        raise PerplexityError("Perplexity returned no answer")
    return text, list(dict.fromkeys(sources))
