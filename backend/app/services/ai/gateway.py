"""AI-Gateway / Provider-Adapter (ADR 004, Anforderung 2).

Die EINE Stelle, an der Modell und Anbieter gewechselt werden – die Fachlogik sieht
nur ``complete(...)`` / ``edit_image(...)``:

* ``vertex``    → Claude über Google Vertex AI (EU-Region, GCP-ADC-Auth, kein API-Key) – Default
* ``anthropic`` → Claude direkt über die Anthropic-API (``ANTHROPIC_API_KEY``)
* Bild         → Gemini («Nano Banana») über Vertex-REST im selben GCP-Projekt

Ohne Konfiguration (kein Projekt/Key) ist die KI **inaktiv statt kaputt**: alle
Aufrufe werfen ``AiUnavailable`` → die Router antworten 503, das ERP läuft normal
(analog ``payments_provider='manual'`` als Fallback beim Shop)."""

import base64
from functools import lru_cache
from typing import Any, Optional

import httpx

from ...core.config import get_settings

settings = get_settings()


class AiUnavailable(Exception):
    """KI nicht konfiguriert/erreichbar – Aufrufer antworten 503, kein Crash."""


def _provider_detail(msg: str, e: Exception) -> str:
    """Ausserhalb der Produktion die echte Provider-Ursache anhängen (Diagnose ohne
    Log-Zugriff: z. B. 403 Rechte, 404 Modell/Region)."""
    if settings.app_env.lower() != "production":
        return f"{msg} ({type(e).__name__}: {str(e)[:400]})"
    return msg


# ── Verfügbarkeit ─────────────────────────────────────────────────────────────────

def is_enabled() -> bool:
    """Text-KI (Claude) nutzbar? Entscheidet über Anzeige des Assistenten im Frontend."""
    if settings.ai_provider == "anthropic":
        return bool(settings.anthropic_api_key)
    if settings.ai_provider == "vertex":
        return bool(settings.vertex_project_id)
    return False


def image_enabled() -> bool:
    """Bild-KI (Gemini via Vertex) nutzbar? Läuft immer über das Vertex-Projekt."""
    return bool(settings.vertex_project_id)


# ── Claude (Text / Tool-Use) ──────────────────────────────────────────────────────

@lru_cache
def _claude_client():
    """Provider-Client lazy & einmalig bauen. Import erst hier, damit ein fehlendes
    Paket die App nie am Start hindert."""
    try:
        import anthropic
    except Exception as e:  # pragma: no cover
        raise AiUnavailable(f"anthropic SDK fehlt: {e}")

    if settings.ai_provider == "anthropic":
        if not settings.anthropic_api_key:
            raise AiUnavailable("ANTHROPIC_API_KEY nicht gesetzt")
        return anthropic.Anthropic(
            api_key=settings.anthropic_api_key, timeout=settings.ai_request_timeout
        )
    if settings.ai_provider == "vertex":
        if not settings.vertex_project_id:
            raise AiUnavailable("VERTEX_PROJECT_ID nicht gesetzt")
        return anthropic.AnthropicVertex(
            project_id=settings.vertex_project_id,
            region=settings.vertex_region,
            timeout=settings.ai_request_timeout,
        )
    raise AiUnavailable(f"KI-Provider '{settings.ai_provider}' inaktiv")


def complete(
    messages: list[dict],
    *,
    system: str,
    tools: Optional[list[dict]] = None,
    tool_choice: Optional[dict] = None,
    model: Optional[str] = None,
    max_tokens: Optional[int] = None,
) -> Any:
    """EIN provider-agnostischer Modell-Aufruf (Messages-API-Form). Gibt das rohe
    Message-Objekt zurück (content-Blöcke ``text`` / ``tool_use``, ``usage``)."""
    client = _claude_client()
    from .registry import chat_model
    kwargs: dict[str, Any] = {
        "model": model or chat_model(),
        "max_tokens": max_tokens or settings.ai_max_output_tokens,
        "system": system,
        "messages": messages,
    }
    if tools:
        kwargs["tools"] = tools
    if tool_choice:
        kwargs["tool_choice"] = tool_choice
    try:
        return client.messages.create(**kwargs)
    except AiUnavailable:
        raise
    except Exception as e:
        # Provider-Fehler (Quota, Netz, Region, Modell/Rechte) → «nicht verfügbar».
        # Voller Fehler ins Log; ausserhalb der Produktion zusätzlich in die Meldung.
        print(f"WARNING: AI completion failed: {type(e).__name__}: {e}", flush=True)
        raise AiUnavailable(_provider_detail("KI-Dienst derzeit nicht verfügbar", e))


# ── Gemini-Bild («Nano Banana», Shop-Bildbearbeitung) ─────────────────────────────

def _gcp_token() -> str:
    try:
        import google.auth
        from google.auth.transport.requests import Request as GARequest
        creds, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
        creds.refresh(GARequest())
        return creds.token
    except Exception as e:
        raise AiUnavailable(f"GCP-Auth für Bild-KI fehlgeschlagen: {e}")


def edit_image(image_bytes: bytes, mime: str, instruction: str) -> tuple[bytes, str]:
    """Bild mit Gemini bearbeiten (Instruktion + Ausgangsbild → neues Bild).

    Bewusst per Vertex-REST + ``google-auth`` (bereits Dependency) statt eines
    zusätzlichen SDKs – derselbe Vertrag/dieselbe Region wie Claude-on-Vertex."""
    if not image_enabled():
        raise AiUnavailable("Bild-KI nicht konfiguriert (VERTEX_PROJECT_ID fehlt)")
    from .registry import image_model
    region = settings.vertex_region
    # Host wie beim Anthropic-SDK: 'global' → ohne Regions-Präfix; 'eu'/feste Region →
    # '{region}-aiplatform...'. Der Standort im Pfad ist stets die konfigurierte Region.
    host = "aiplatform.googleapis.com" if region == "global" else f"{region}-aiplatform.googleapis.com"
    url = (
        f"https://{host}/v1/projects/{settings.vertex_project_id}"
        f"/locations/{region}/publishers/google/models/{image_model()}:generateContent"
    )
    body = {
        "contents": [{
            "role": "user",
            "parts": [
                {"inlineData": {"mimeType": mime, "data": base64.b64encode(image_bytes).decode()}},
                {"text": instruction},
            ],
        }],
        "generationConfig": {"responseModalities": ["IMAGE", "TEXT"]},
    }
    try:
        resp = httpx.post(
            url,
            json=body,
            headers={"Authorization": f"Bearer {_gcp_token()}"},
            timeout=settings.ai_request_timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        for cand in data.get("candidates", []):
            for part in (cand.get("content") or {}).get("parts", []):
                inline = part.get("inlineData") or part.get("inline_data")
                if inline and inline.get("data"):
                    out_mime = inline.get("mimeType") or inline.get("mime_type") or "image/png"
                    return base64.b64decode(inline["data"]), out_mime
        raise AiUnavailable("Bild-KI hat kein Bild geliefert")
    except AiUnavailable:
        raise
    except Exception as e:
        print(f"WARNING: AI image edit failed: {type(e).__name__}: {e}", flush=True)
        raise AiUnavailable(_provider_detail("Bild-KI derzeit nicht verfügbar", e))
