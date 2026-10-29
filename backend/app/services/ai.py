"""►►► **Das KI-Tor – die einzige Stelle, die die KI aufruft.** ◄◄◄

1. **Zugriff:** Jeder Aufruf nennt den Akteur, in dessen Namen er läuft. Was die KI zu sehen
   bekommt, hat der Aufrufer vorher über ``services/access`` gefiltert – sie sieht nie mehr
   als dieser Mensch.
2. **Aufgabe und Modell** stehen in EINER Tabelle (``TASKS``).
3. **Feste Antwortform:** jede Aufgabe hat ein Pydantic-Schema; die Antwort wird dagegen
   geprüft (structured outputs). Was nicht passt, gilt als Ausfall.
4. **Die KI schreibt nie selbst.** Sie liefert Vorschläge; geschrieben wird über die
   Fachdienste, nach dem Klick eines Menschen.
5. **Deckel und Log:** jeder Aufruf ist eine Zeile im ``audit_log`` (``on_behalf = ai``) mit
   Modell und Tokens; der Tagesdeckel zählt genau diese Zeilen.

**Ohne Schlüssel, am Deckel oder bei einem Fehler gibt es keinen Vorschlag – sonst nichts.**
Alles geht auch ohne KI: Art und Name tippt der Mensch, gesucht wird in der Datenbank.
**Warum es keinen gab, sagt** ``problem()`` in einem Satz (Schlüssel abgelehnt, Guthaben leer,
Deckel …) – die Oberfläche zeigt ihn, damit ein Ausfall nie stumm bleibt.
"""

from __future__ import annotations

import base64
import json
import re
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import datetime, time, timezone
from html import unescape
from typing import Optional, TypeVar

from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..core.config import get_settings
from ..models import AuditLog, UserProfile
from .admin import log_audit

T = TypeVar("T", bound=BaseModel)

#: Warum der letzte Aufruf in dieser Anfrage keinen Vorschlag brachte – leer, wenn er einen brachte.
_PROBLEM: ContextVar[str] = ContextVar("ai_problem", default="")


def problem() -> str:
    """**Warum es keinen Vorschlag gab** – ein Satz, oder leer."""
    return _PROBLEM.get()


def problem_of(exc: Exception) -> str:
    """Ein Fehler der Schnittstelle als ein Satz für den Menschen."""
    status = getattr(exc, "status_code", None)
    text = str(getattr(exc, "message", "") or exc)
    if status == 401:
        return "Der KI-Schlüssel wird abgelehnt (ungültig oder gelöscht) – bitte im Secret Manager ersetzen."
    if status == 403:
        return "Der KI-Schlüssel darf dieses Modell nicht nutzen."
    if status == 404:
        return "Das KI-Modell ist unbekannt."
    if status == 400 and "credit" in text.lower():
        return "Das Guthaben beim KI-Anbieter ist aufgebraucht – bitte in der Anthropic Console aufladen."
    if status == 429:
        return "Die KI ist gerade ausgelastet (zu viele Anfragen) – gleich noch einmal."
    if status is not None and status >= 500:
        return "Die KI antwortet gerade nicht – gleich noch einmal."
    if status is not None:
        return f"Die KI weist die Anfrage ab ({status}): {text[:200]}"
    if "timeout" in type(exc).__name__.lower():
        return "Die KI hat zu lange gebraucht – gleich noch einmal."
    return "Die KI ist nicht erreichbar – gleich noch einmal."


@dataclass(frozen=True)
class Task:
    model: str
    max_tokens: int
    #: Wie lange auf die Antwort gewartet wird (Sekunden) – Verfassen schreibt Seiten.
    timeout: float = 90.0
    #: Wie oft ein Fehler wiederholt wird (die Wartezeit zählt dann doppelt).
    retries: int = 1


#: ►►► **Die Aufgaben – und welches Modell sie macht.** ◄◄◄ Lesen ist Masse (jede Datei),
#: also das schnelle, günstige Modell; Verfassen schreibt ein Papier von ein paar Seiten –
#: das mittlere Modell reicht dafür, das grösste kostete ein Vielfaches für denselben Brief.
#: **Jede Anfrage läuft über Firebase Hosting, und das bricht nach 60 s ab** – darum warten
#: beide höchstens knapp darunter und versuchen es nicht ein zweites Mal.
TASKS: dict[str, Task] = {
    # Lesen muss unter der Grenze von Firebase Hosting bleiben (60 s je Anfrage) – sonst bricht
    # der Weg ab, bevor die Antwort kommt: 50 s, kein zweiter Versuch, eine kurze Antwort.
    "read": Task(model="claude-haiku-5-5", max_tokens=6000, timeout=50.0, retries=0),
    # Ein Papier von zwei, drei Seiten – ebenfalls unter den 60 s des Hostings.
    "compose": Task(model="claude-sonnet-5-5", max_tokens=4000, timeout=55.0, retries=0),
}

#: Was die KI lesen kann – Bilder und PDF direkt, Text als Text.
IMAGE_TYPES = ("image/jpeg", "image/png", "image/webp", "image/gif")


def ready() -> bool:
    return bool(get_settings().anthropic_api_key)


def used_today(db: Session) -> int:
    start = datetime.combine(datetime.now(timezone.utc).date(), time.min, tzinfo=timezone.utc)
    return (db.query(AuditLog).filter(AuditLog.table_name == "ai",
                                      AuditLog.changed_at_utc >= start).count())


def available(db: Session) -> bool:
    """Gibt es heute noch eine KI? Ohne Schlüssel nie; am Deckel nicht mehr."""
    if not ready():
        return False
    cap = get_settings().ai_daily_cap
    return cap <= 0 or used_today(db) < cap


def content_of(raw: bytes, mime: str) -> Optional[dict]:
    """**Eine Datei als Eingabe der KI** – oder ``None``, wenn sie diese Sorte nicht liest
    (Video, STEP, Office): dann tippt der Mensch Art und Name selbst."""
    if mime == "application/pdf":
        return {"type": "document", "source": {
            "type": "base64", "media_type": "application/pdf",
            "data": base64.standard_b64encode(raw).decode("ascii")}}
    if mime in IMAGE_TYPES:
        return {"type": "image", "source": {
            "type": "base64", "media_type": mime,
            "data": base64.standard_b64encode(raw).decode("ascii")}}
    if mime.startswith("text/") or mime in ("application/json", "application/xml"):
        text = raw.decode("utf-8", "replace")
        if mime == "text/html":
            text = unescape(re.sub(r"<[^>]+>", " ", re.sub(
                r"<(script|style)[^>]*>.*?</\1>", " ", text, flags=re.S | re.I)))
        return {"type": "text", "text": " ".join(text.split())[:60000]}
    return None


def _client(timeout: float = 90.0, retries: int = 1):
    import anthropic
    return anthropic.Anthropic(api_key=get_settings().anthropic_api_key, max_retries=retries,
                               timeout=timeout)


def ask(db: Session, *, task: str, actor: Optional[UserProfile], system: str,
        content: list[dict], schema: type[T]) -> Optional[T]:
    """►►► **Ein Aufruf durch das Tor.** ◄◄◄ Gibt die geprüfte Antwort zurück – oder ``None``
    (keine KI, Deckel erreicht, abgelehnt, Antwort unbrauchbar, Netz weg). Nie eine Ausnahme:
    ein Ausfall der KI darf nie eine Handlung zerlegen."""
    _PROBLEM.set("")
    if not ready():
        _PROBLEM.set("Kein KI-Schlüssel hinterlegt.")
        return None
    if not available(db):
        _PROBLEM.set("Der Tagesdeckel der KI ist erreicht – morgen wieder.")
        return None
    spec = TASKS[task]
    result: Optional[T] = None
    usage: dict = {}
    try:
        response = _client(spec.timeout, spec.retries).messages.parse(
            model=spec.model, max_tokens=spec.max_tokens, system=system,
            messages=[{"role": "user", "content": content}], output_format=schema)
        usage = {"in": response.usage.input_tokens, "out": response.usage.output_tokens,
                 "stop": response.stop_reason}
        if response.stop_reason not in ("refusal", "max_tokens"):
            result = response.parsed_output
        if result is None:
            _PROBLEM.set("Die KI hat abgelehnt." if response.stop_reason == "refusal"
                         else "Die Antwort der KI war unvollständig.")
    except Exception as exc:                                   # noqa: BLE001
        usage = {"error": type(exc).__name__, "status": getattr(exc, "status_code", None)}
        _PROBLEM.set(problem_of(exc))
        print(f"WARNING: ai.{task} failed: {exc!r}", flush=True)
    log_audit(db, "ai", task, json.dumps({"model": spec.model, **usage}),
              actor.id if actor else None, on_behalf="ai")
    return result
