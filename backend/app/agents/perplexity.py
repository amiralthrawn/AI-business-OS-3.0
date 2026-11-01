"""Perplexity (Sonar): the best tool for collecting live information from the
web with its sources. The Veilleur's only door to the outside world."""

import httpx

from app.config import get_settings

URL = "https://api.perplexity.ai/chat/completions"


class PerplexityError(RuntimeError):
    pass


def configured() -> bool:
    return bool((get_settings().perplexity_api_key or "").strip())


def ask(system: str, user: str, *, timeout: float = 90.0) -> tuple[str, list[str]]:
    """Returns (answer text, source URLs). Raises PerplexityError."""

    settings = get_settings()
    if not configured():
        raise PerplexityError("PERPLEXITY_API_KEY is not set")
    try:
        res = httpx.post(
            URL,
            headers={"Authorization": f"Bearer {settings.perplexity_api_key.strip()}", "Content-Type": "application/json"},
            json={
                "model": settings.perplexity_model,
                "temperature": 0.1,
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            },
            timeout=timeout,
        )
    except httpx.HTTPError as exc:
        raise PerplexityError(f"Perplexity unreachable: {exc}") from exc
    if res.status_code != 200:
        raise PerplexityError(f"Perplexity answered {res.status_code}: {res.text[:200]}")
    body = res.json()
    try:
        text = body["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise PerplexityError("Unexpected Perplexity answer") from exc
    citations = body.get("citations") or [r.get("url") for r in body.get("search_results", []) if r.get("url")]
    return text, [c for c in citations if isinstance(c, str)]
