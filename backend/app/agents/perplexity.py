"""The agents' only door to the live web, with sources.

Two providers behind one `ask()`: Google Gemini with Google Search grounding
(used first when GEMINI_API_KEY is set) or Perplexity's Agent API. The module
keeps its historical name so the agents and the tests did not have to change."""

import re
from contextvars import ContextVar

import httpx

from app.config import get_settings

URL = "https://api.perplexity.ai/v1/agent"


class PerplexityError(RuntimeError):
    pass


# Tokens spent by the calls of the current request/job. `log_run` drains it and
# books the total on the agent that made the calls.
_USAGE: ContextVar[list | None] = ContextVar("agent_usage", default=None)


def _record(model: str, usage: object) -> None:
    if not isinstance(usage, dict):
        return
    def num(*keys: str) -> int:
        for k in keys:
            if isinstance(usage.get(k), (int, float)):
                return int(usage[k])
        return 0
    cost = usage.get("cost")
    entry = {"model": model, "tin": num("prompt_tokens", "input_tokens", "total_input_tokens"), "tout": num("completion_tokens", "output_tokens", "total_output_tokens"), "cost": float(cost) if isinstance(cost, (int, float)) else None}
    bucket = _USAGE.get()
    if bucket is None:
        bucket = []
        _USAGE.set(bucket)
    bucket.append(entry)


def peek_usage() -> list[dict]:
    return list(_USAGE.get() or [])


def drain_usage() -> list[dict]:
    bucket = _USAGE.get() or []
    _USAGE.set([])
    return bucket


GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/interactions"


def _gemini_on() -> bool:
    return bool((get_settings().gemini_api_key or "").strip())


OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


def _openrouter_on() -> bool:
    return bool((get_settings().openrouter_api_key or "").strip())


def configured() -> bool:
    return _openrouter_on() or _gemini_on() or bool((get_settings().perplexity_api_key or "").strip())


def _walk(node: object, texts: list[str], urls: list[str]) -> None:
    """Collects answer text and url citations from an Interactions response,
    whatever its exact nesting (steps, content, annotations)."""

    if isinstance(node, dict):
        if node.get("type") == "text" and isinstance(node.get("text"), str):
            texts.append(node["text"])
        if node.get("type") == "url_citation" and isinstance(node.get("url"), str):
            urls.append(node["url"])
        for value in node.values():
            _walk(value, texts, urls)
    elif isinstance(node, list):
        for value in node:
            _walk(value, texts, urls)


def _ask_openrouter(system: str, user: str, timeout: float, model: str | None = None) -> tuple[str, list[str]]:
    settings = get_settings()
    body = {"model": model or settings.openrouter_model, "temperature": 0.1, "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
    try:
        res = httpx.post(OPENROUTER_URL, headers={"Authorization": f"Bearer {settings.openrouter_api_key.strip()}", "Content-Type": "application/json"}, json=body, timeout=timeout)
    except httpx.HTTPError as exc:
        raise PerplexityError(f"OpenRouter unreachable: {exc}") from exc
    if res.status_code != 200:
        raise PerplexityError(f"OpenRouter answered {res.status_code}: {res.text[:900]}")
    try:
        data = res.json()
        message = data["choices"][0]["message"]
        text = message.get("content") or ""
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise PerplexityError("Unexpected OpenRouter answer") from exc
    _record(model or settings.openrouter_model, data.get("usage"))
    urls: list[str] = [c for c in (data.get("citations") or message.get("citations") or []) if isinstance(c, str)]
    for ann in message.get("annotations") or []:
        if isinstance(ann, dict):
            cite = ann.get("url_citation") or ann
            if isinstance(cite, dict) and isinstance(cite.get("url"), str):
                urls.append(cite["url"])
    text = re.sub(r"\s*\[\d+\]", "", text).strip()
    if not text:
        raise PerplexityError("OpenRouter returned no answer")
    return text, list(dict.fromkeys(urls))


def chat(system: str, user: str, *, model: str | None = None, timeout: float = 120.0) -> str:
    """A plain generative call (no web search) through OpenRouter. Raises PerplexityError."""

    settings = get_settings()
    if not _openrouter_on():
        raise PerplexityError("No language model is configured (OPENROUTER_API_KEY)")
    chosen = model or settings.openrouter_agent_model
    body = {"model": chosen, "temperature": 0.2, "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
    try:
        res = httpx.post(OPENROUTER_URL, headers={"Authorization": f"Bearer {settings.openrouter_api_key.strip()}", "Content-Type": "application/json"}, json=body, timeout=timeout)
    except httpx.HTTPError as exc:
        raise PerplexityError(f"OpenRouter unreachable: {exc}") from exc
    if res.status_code != 200:
        raise PerplexityError(f"OpenRouter answered {res.status_code}: {res.text[:600]}")
    try:
        data = res.json()
        text = data["choices"][0]["message"].get("content") or ""
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise PerplexityError("Unexpected OpenRouter answer") from exc
    _record(chosen, data.get("usage"))
    return text.strip()


def _ask_gemini(system: str, user: str, timeout: float) -> tuple[str, list[str]]:
    settings = get_settings()
    body = {
        "model": settings.gemini_model,
        "input": f"{system}\n\n{user}",
        "tools": [{"type": "google_search"}],
    }
    try:
        res = httpx.post(GEMINI_URL, headers={"x-goog-api-key": settings.gemini_api_key.strip(), "Content-Type": "application/json"}, json=body, timeout=timeout)
    except httpx.HTTPError as exc:
        raise PerplexityError(f"Gemini unreachable: {exc}") from exc
    if res.status_code != 200:
        raise PerplexityError(f"Gemini answered {res.status_code}: {res.text[:900]}")
    try:
        data = res.json()
    except ValueError as exc:
        raise PerplexityError("Unexpected Gemini answer") from exc
    _record(settings.gemini_model, data.get("usage") or data.get("usage_metadata") if isinstance(data, dict) else None)
    # keep only the model's output, not the search-call/result steps
    steps = data.get("steps") if isinstance(data, dict) else None
    outputs = [st for st in steps if isinstance(st, dict) and st.get("type") == "model_output"] if isinstance(steps, list) else [data]
    texts: list[str] = []
    urls: list[str] = []
    _walk(outputs, texts, urls)
    text = re.sub(r"\s*\[\d+\]", "", "".join(texts)).strip()
    if not text:
        raise PerplexityError("Gemini returned no answer")
    return text, list(dict.fromkeys(urls))


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


def ask(system: str, user: str, *, timeout: float = 90.0, model: str | None = None) -> tuple[str, list[str]]:
    """Returns (answer text, source URLs). Raises PerplexityError.

    Uses the Perplexity Agent API (the former Sonar endpoint was retired).
    Without an explicit model ("provider/model") the `fast` effort level is
    used, which searches the web by default."""

    settings = get_settings()
    if not configured():
        raise PerplexityError("No search key is set (GEMINI_API_KEY or PERPLEXITY_API_KEY)")
    if _openrouter_on():
        return _ask_openrouter(system, user, timeout, model)
    if _gemini_on():
        return _ask_gemini(system, user, timeout)
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
        raise PerplexityError(f"Perplexity answered {res.status_code}: {res.text[:900]}")
    try:
        _record(model if "/" in model else "perplexity-agent-fast", res.json().get("usage"))
    except (AttributeError, ValueError):
        pass
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
