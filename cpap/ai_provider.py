from __future__ import annotations

import json
import socket
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Iterable


class AIProviderError(RuntimeError):
    def __init__(self, message: str, *, status: int | None = None, transient: bool = False, remote_type: str | None = None, remote_code: str | None = None, remote_detail: str | None = None):
        super().__init__(message)
        self.status = status
        self.transient = transient
        self.remote_type = remote_type
        self.remote_code = remote_code
        self.remote_detail = remote_detail


def _friendly(provider: str, status: int | None, detail: str | None = None) -> str:
    if provider == "Groq" and detail and "error code: 1010" in detail.lower():
        return "Groq: A kapcsolatot a szolgáltató Cloudflare védelme (1010) blokkolta a HTTP kliens azonosítása miatt. A SleepMate a hivatalos Groq SDK-t használja; ellenőrizd, hogy a 'groq' Python csomag telepítve van."
    friendly = {
        400: "A szolgáltató elutasította a kérést. Ellenőrizd a kiválasztott modellt és a beállításokat.",
        401: "Az API-kulcs nem érvényes vagy nem jogosult a szolgáltatás használatára.",
        403: "A kérést a szolgáltató megtagadta. Ellenőrizd a részletes AI naplót; ez nem feltétlenül modelljogosultsági hiba.",
        404: "A beállított AI-modell nem található. Ellenőrizd a modell nevét a Beállításokban.",
        429: "Az AI-szolgáltató ideiglenes kvóta- vagy sebességkorlátot jelzett.",
    }.get(status, "Az AI-szolgáltató hibát jelzett.")
    if detail:
        friendly += f" Részlet: {detail[:500]}"
    return f"{provider}: {friendly}"


def _http_error_message(provider: str, exc: urllib.error.HTTPError) -> AIProviderError:
    raw = ""
    remote_type = None
    remote_code = None
    detail = None
    try:
        raw = exc.read(16000).decode("utf-8", errors="replace")
        obj = json.loads(raw)
        err = obj.get("error", {}) if isinstance(obj, dict) and isinstance(obj.get("error"), dict) else {}
        detail = err.get("message")
        remote_type = err.get("type")
        remote_code = err.get("code")
    except Exception:
        pass
    status = int(getattr(exc, "code", 0) or 0)
    transient = status in {408, 409, 429} or status >= 500
    remote_detail = detail or raw[:1000] or None
    return AIProviderError(_friendly(provider, status, remote_detail), status=status, transient=transient, remote_type=str(remote_type) if remote_type else None, remote_code=str(remote_code) if remote_code else None, remote_detail=remote_detail)


def _url_error_message(provider: str, exc: Exception) -> AIProviderError:
    if isinstance(exc, socket.timeout):
        return AIProviderError(f"{provider}: Az AI-kérés időtúllépés miatt megszakadt.", transient=True)
    return AIProviderError(f"{provider}: Hálózati kapcsolat nem hozható létre az AI-szolgáltatóval.", transient=True)


def _post_sse(url: str, headers: dict[str, str], payload: dict[str, Any], timeout: int = 120):
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {"Accept": "text/event-stream", "User-Agent": "SleepMate/2.7", **headers}
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    return urllib.request.urlopen(req, timeout=timeout)


def groq_transport_name() -> str:
    try:
        import groq  # noqa: F401
        return "official_groq_python_sdk"
    except Exception:
        return "urllib_fallback"


def stream_gemini(api_key: str, model: str, system_prompt: str, user_prompt: str, *, json_mode: bool = True, timeout: int = 120) -> Iterable[str]:
    provider = "Gemini"
    model = model.strip() or "gemini-3.6-flash"
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{urllib.parse.quote(model, safe='-._')}:streamGenerateContent?alt=sse"
    payload: dict[str, Any] = {
        "systemInstruction": {"parts": [{"text": system_prompt}]},
        "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
        "generationConfig": {"temperature": 0.2},
    }
    if json_mode:
        payload["generationConfig"]["responseMimeType"] = "application/json"
    try:
        with _post_sse(url, {"Content-Type": "application/json", "x-goog-api-key": api_key}, payload, timeout) as resp:
            for raw in resp:
                line = raw.decode("utf-8", errors="replace").strip()
                if not line.startswith("data:"):
                    continue
                text = line[5:].strip()
                if not text:
                    continue
                try:
                    obj = json.loads(text)
                except json.JSONDecodeError:
                    continue
                for cand in obj.get("candidates") or []:
                    content = cand.get("content") if isinstance(cand, dict) else None
                    if not isinstance(content, dict):
                        continue
                    for part in content.get("parts") or []:
                        if isinstance(part, dict) and isinstance(part.get("text"), str):
                            yield part["text"]
    except urllib.error.HTTPError as exc:
        raise _http_error_message(provider, exc) from exc
    except (urllib.error.URLError, socket.timeout, TimeoutError) as exc:
        raise _url_error_message(provider, exc) from exc


def _sdk_error_to_provider_error(exc: Exception) -> AIProviderError:
    """Translate Groq SDK errors without depending on a specific SDK version."""
    status = getattr(exc, "status_code", None)
    response = getattr(exc, "response", None)
    if status is None and response is not None:
        status = getattr(response, "status_code", None)
    try:
        status = int(status) if status is not None else None
    except Exception:
        status = None

    body = getattr(exc, "body", None)
    remote_type = None
    remote_code = None
    detail = None
    if isinstance(body, dict):
        err = body.get("error") if isinstance(body.get("error"), dict) else body
        if isinstance(err, dict):
            detail = err.get("message") or err.get("detail")
            remote_type = err.get("type")
            remote_code = err.get("code")
    if not detail:
        detail = str(exc)
    transient = status in {408, 409, 429} or bool(status and status >= 500) or exc.__class__.__name__ in {"APIConnectionError", "APITimeoutError"}
    return AIProviderError(_friendly("Groq", status, detail), status=status, transient=transient, remote_type=str(remote_type) if remote_type else exc.__class__.__name__, remote_code=str(remote_code) if remote_code else None, remote_detail=str(detail)[:1200] if detail else None)


def _stream_groq_sdk(api_key: str, model: str, system_prompt: str, user_prompt: str, *, json_mode: bool, timeout: int) -> Iterable[str]:
    try:
        from groq import Groq
    except Exception as exc:
        raise ImportError("A hivatalos Groq Python SDK nincs telepítve. Futtasd: python -m pip install groq") from exc

    kwargs: dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.2,
        "stream": True,
    }
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    if model.startswith("openai/gpt-oss-"):
        kwargs["reasoning_effort"] = "medium"

    try:
        client = Groq(api_key=api_key, timeout=timeout)
        stream = client.chat.completions.create(**kwargs)
        for chunk in stream:
            choices = getattr(chunk, "choices", None) or []
            if not choices:
                continue
            delta = getattr(choices[0], "delta", None)
            part = getattr(delta, "content", None) if delta is not None else None
            if isinstance(part, str) and part:
                yield part
    except AIProviderError:
        raise
    except Exception as exc:
        raise _sdk_error_to_provider_error(exc) from exc


def _stream_groq_urllib(api_key: str, model: str, system_prompt: str, user_prompt: str, *, json_mode: bool, timeout: int) -> Iterable[str]:
    """Compatibility fallback only. The official SDK is preferred."""
    provider = "Groq"
    url = "https://api.groq.com/openai/v1/chat/completions"
    payload: dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.2,
        "stream": True,
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}
    if model.startswith("openai/gpt-oss-"):
        payload["reasoning_effort"] = "medium"
    try:
        with _post_sse(url, {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}", "User-Agent": "groq-python/SleepMate-compat"}, payload, timeout) as resp:
            for raw in resp:
                line = raw.decode("utf-8", errors="replace").strip()
                if not line.startswith("data:"):
                    continue
                text = line[5:].strip()
                if text == "[DONE]":
                    break
                if not text:
                    continue
                try:
                    obj = json.loads(text)
                except json.JSONDecodeError:
                    continue
                choices = obj.get("choices") or []
                if choices and isinstance(choices[0], dict):
                    delta = choices[0].get("delta") or {}
                    part = delta.get("content") if isinstance(delta, dict) else None
                    if isinstance(part, str) and part:
                        yield part
    except urllib.error.HTTPError as exc:
        raise _http_error_message(provider, exc) from exc
    except (urllib.error.URLError, socket.timeout, TimeoutError) as exc:
        raise _url_error_message(provider, exc) from exc


def stream_groq(api_key: str, model: str, system_prompt: str, user_prompt: str, *, json_mode: bool = True, timeout: int = 120) -> Iterable[str]:
    model = model.strip() or "openai/gpt-oss-120b"
    # The official SDK is deliberately preferred. This is the exact client path
    # proven to work in the user's CMD test, and avoids Cloudflare 1010 blocks
    # seen with Python urllib's request signature.
    try:
        import groq  # noqa: F401
        return _stream_groq_sdk(api_key, model, system_prompt, user_prompt, json_mode=json_mode, timeout=timeout)
    except ImportError:
        return _stream_groq_urllib(api_key, model, system_prompt, user_prompt, json_mode=json_mode, timeout=timeout)


def stream_provider(provider: str, api_key: str, model: str, system_prompt: str, user_prompt: str, *, json_mode: bool = True, timeout: int = 120) -> Iterable[str]:
    if provider == "gemini":
        return stream_gemini(api_key, model, system_prompt, user_prompt, json_mode=json_mode, timeout=timeout)
    if provider == "groq":
        return stream_groq(api_key, model, system_prompt, user_prompt, json_mode=json_mode, timeout=timeout)
    raise ValueError("Ismeretlen AI szolgáltató.")
