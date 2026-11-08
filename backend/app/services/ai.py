"""►►► **Das KI-Tor – die einzige Stelle, die die KI aufruft.** ◄◄◄

1. **Zugriff:** Jeder Aufruf nennt den Akteur, in dessen Namen er läuft (Log, Kosten). Was die
   KI zu sehen bekommt, ist über ``services/access`` gefiltert – **mit den Rechten, die jedes
   Personal hat** (``ai_tools.reader``): nie mehr als die Person, nie Privates. Ihr Ergebnis
   (Vorschlag, Hinweis) sehen alle vom Personal.
2. **Aufgabe und Modell** stehen in EINER Tabelle (``TASKS``).
3. **Feste Antwortform:** jede Aufgabe hat ein Pydantic-Schema; die Antwort wird dagegen
   geprüft (structured outputs). Was nicht passt, gilt als Ausfall.
4. **Die KI schreibt nie selbst.** Sie liefert Vorschläge; geschrieben wird über die
   Fachdienste, nach dem Klick eines Menschen.
5. **Deckel und Log:** jeder Aufruf ist ein Ereignis ``ai.call`` im Log (Handelnder ``ai`` im
   Namen der Person) mit Aufgabe, Modell, Tokens und **Kosten in Franken** (``chf``); der
   Tagesdeckel (``AI_DAILY_CAP_CHF``) zählt genau diese.
6. **Lesen mit Werkzeugen** (``converse``): die KI schlägt im ERP nach – über die
   Lese-Werkzeuge in ``services/ai_tools``, mit den Rechten jedes Personals. Auch Bedeutungs-Zahlen
   (``embed``) und das Abschreiben von Gesprochenem (``transcribe``, Phase 4) – beide Vertex AI,
   über EINE Stelle ``_vertex`` – gehen durch diese Tür.

**Ohne Schlüssel, am Deckel oder bei einem Fehler gibt es keinen Vorschlag – sonst nichts.**
Alles geht auch ohne KI: Art und Name tippt der Mensch, gesucht wird in der Datenbank.
**Warum es keinen gab, sagt** ``problem()`` in einem Satz (Schlüssel abgelehnt, Guthaben leer,
Deckel …) – die Oberfläche zeigt ihn, damit ein Ausfall nie stumm bleibt.
"""

from __future__ import annotations

import base64
import json
import re
import time as _time
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime, time, timezone
from html import unescape
from pathlib import Path
from typing import Any, Callable, Optional, TypeVar

from pydantic import BaseModel
from sqlalchemy import Float, cast, func
from sqlalchemy.orm import Session

from ..core import clock, outside
from ..core.config import get_settings
from ..models import Log, UserProfile
from . import log

T = TypeVar("T", bound=BaseModel)

#: Warum der letzte Aufruf in dieser Anfrage keinen Vorschlag brachte – leer, wenn er einen brachte.
_PROBLEM: ContextVar[str] = ContextVar("ai_problem", default="")
#: Bis wann (``time.monotonic``) alle Aufrufe in diesem Ablauf fertig sein müssen – ``ai.until``.
_UNTIL: ContextVar[Optional[float]] = ContextVar("ai_until", default=None)


class until:
    """►► **Eine Zeitgrenze für alles, was in einem Ablauf an die KI geht** – ``with
    ai.until(seconds):``. Eine Anfrage über Firebase Hosting bricht nach 60 s ab, ein Lauf des
    Takts ebenso (Cloud Scheduler); jeder Aufruf darin (Ablegen, Bedeutungs-Zahlen, Folgen)
    bekommt nur noch die Zeit, die bleibt – und **wiederholt nichts selbst** (``_retries``):
    ein zweiter Versuch im SDK bräche die Grenze; wiederholen ist Sache des Takts. ◄◄"""

    def __init__(self, seconds: float):
        self.at = _time.monotonic() + seconds

    def __enter__(self) -> "until":
        current = _UNTIL.get()
        self._token = _UNTIL.set(self.at if current is None else min(current, self.at))
        return self

    def __exit__(self, *exc: Any) -> None:
        _UNTIL.reset(self._token)


def _left(limit: float) -> float:
    """Wie lange ein Aufruf noch dauern darf – seine eigene Grenze oder die des Ablaufs."""
    end = _UNTIL.get()
    return limit if end is None else min(limit, end - _time.monotonic())


def _retries(own: int) -> int:
    """Wie oft ein Aufruf selbst wiederholt – unter einer Zeitgrenze (``until``) nie."""
    return 0 if _UNTIL.get() is not None else own


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
    #: Wie lange auf die Antwort gewartet wird (Sekunden) – bei ``converse`` für ALLE Runden
    #: zusammen.
    timeout: float = 90.0
    #: Wie oft ein Fehler wiederholt wird (die Wartezeit zählt dann doppelt).
    retries: int = 1
    #: Wie viele Runden mit Werkzeugen höchstens (``converse``) – danach muss die Antwort kommen.
    rounds: int = 1
    #: Wie gründlich das Modell denkt (``low`` · ``medium`` · ``high``); leer = Vorgabe des Modells.
    effort: Optional[str] = None


#: ►►► **Die Aufgaben – und welches Modell sie macht.** ◄◄◄ Lesen ist Masse (jede Datei),
#: also das schnelle, günstige Modell; Verfassen schreibt ein Papier von ein paar Seiten –
#: das mittlere Modell reicht dafür, das grösste kostete ein Vielfaches für denselben Brief.
#: Ablegen, Folgen und Hinweise brauchen Urteil (wohin gehört das, was folgt daraus) – das
#: mittlere Modell, mit wenig Nachdenken, damit es schnell bleibt.
#: **Jede Anfrage läuft über Firebase Hosting, und das bricht nach 60 s ab** – was im Weg einer
#: Anfrage läuft (lesen, verfassen, ablegen, Hinweise), bleibt darunter und versucht es nicht
#: ein zweites Mal; der Takt (``follow``) ebenso – auch er hat nur 60 s.
TASKS: dict[str, Task] = {
    # Lesen muss unter der Grenze von Firebase Hosting bleiben (60 s je Anfrage) – sonst bricht
    # der Weg ab, bevor die Antwort kommt: 50 s, kein zweiter Versuch, eine kurze Antwort.
    "read": Task(model="claude-haiku-5-5", max_tokens=6000, timeout=50.0, retries=0),
    # Ein Papier von zwei, drei Seiten – ebenfalls unter den 60 s des Hostings.
    "compose": Task(model="claude-sonnet-5-5", max_tokens=4000, timeout=55.0, retries=0),
    # Ein Zug im Gespräch: nachschlagen, vorbereiten (jeder Handgriff mit Probelauf), antworten.
    # Live gestreamt direkt am Dienst (``talk.stream``), nicht durch das Hosting: begrenzt durch
    # die Schritte, den Deckel und «Stopp» – die Uhr ist nur das äussere Netz (Cloud Run 300 s).
    # Im Takt hält ``until`` ihn kürzer.
    "talk": Task(model="claude-sonnet-5-5", max_tokens=6000, timeout=240.0, retries=0,
                 rounds=10, effort="low"),
    # Was aus einer eingehenden Mail folgt – im Takt, der selbst nach 60 s abbricht: 45 s, kein
    # zweiter Versuch (ein Fehlschlag kommt im nächsten Takt wieder, ``follow.TRIES``).
    "follow": Task(model="claude-sonnet-5-5", max_tokens=4000, timeout=45.0, retries=0,
                   rounds=5, effort="low"),
    # Was an einem Datensatz jetzt wichtig ist (das Wissen im Angehefteten).
    "pin": Task(model="claude-sonnet-5-5", max_tokens=3000, timeout=45.0, retries=0,
                rounds=3, effort="low"),
}

#: ►►► **Was ein Aufruf kostet** – USD je Million Tokens (Eingabe, Ausgabe), Stand der
#: Preisliste 11/2026. Haiku 5.5 kostet über 100'000 Eingabe-Tokens je Aufruf das Fünffache
#: (``LONG_PROMPT``). Ein Modell, das hier fehlt, zählt zum teuersten Preis – lieber zu früh
#: am Deckel als unbemerkt darüber. ◄◄◄
PRICES: dict[str, tuple[float, float]] = {
    "claude-haiku-5-5": (0.10, 0.50),
    "claude-sonnet-5-5": (2.00, 10.00),
    "gemini-embedding-001": (0.15, 0.0),
    # Abschreiben (Phase 4): Audio-Eingabe ist bei Gemini teurer als Text. Preisliste prüfen –
    # bis dahin bewusst hoch angesetzt (lieber zu früh am Deckel).
    "gemini-3.5-flash": (1.00, 6.00),
}
LONG_PROMPT = {"claude-haiku-5-5": (100_000, (0.50, 2.50))}
#: Franken je US-Dollar – fest; der Deckel ist ein Schutz, keine Buchhaltung.
CHF_PER_USD = 0.80
#: Ab diesem Anteil des Deckels steht ein Hinweis in «zu tun» des Admins.
WARN_AT = 0.8


def cost_chf(model: str, tokens_in: int, tokens_out: int) -> float:
    """Was ein Aufruf in Franken kostet – aus den Tokens, die der Anbieter meldet."""
    price = PRICES.get(model) or max(PRICES.values())
    limit, dearer = LONG_PROMPT.get(model, (None, None))
    if limit is not None and tokens_in > limit:
        price = dearer
    usd = (tokens_in * price[0] + tokens_out * price[1]) / 1_000_000
    return round(usd * CHF_PER_USD, 6)


#: Was die KI lesen kann – Bilder und PDF direkt, Text als Text.
IMAGE_TYPES = ("image/jpeg", "image/png", "image/webp", "image/gif")


def ready() -> bool:
    return bool(get_settings().anthropic_api_key)


def _day_start() -> datetime:
    """Beginn des heutigen Tages in Europe/Zurich – der Deckel gilt je Schweizer Tag."""
    return datetime.combine(clock.today(), time.min, tzinfo=clock.now().tzinfo).astimezone(timezone.utc)


def spent_today(db: Session) -> float:
    """Was die KI heute gekostet hat, in Franken (Summe der ``ai.call``)."""
    total = (db.query(func.coalesce(func.sum(cast(Log.payload["chf"].astext, Float)), 0.0))
             .filter(Log.event == "ai.call", Log.at >= _day_start()).scalar())
    return float(total or 0.0)


def cap_chf() -> float:
    return float(get_settings().ai_daily_cap_chf or 0.0)


def near_cap(db: Session) -> bool:
    """Ist der Deckel zu ``WARN_AT`` erreicht? (Hinweis in «zu tun» des Admins)"""
    cap = cap_chf()
    return cap > 0 and spent_today(db) >= cap * WARN_AT


def available(db: Session) -> bool:
    """Gibt es heute noch eine KI? Ohne Schlüssel nie; am Deckel nicht mehr."""
    if not ready():
        return False
    cap = cap_chf()
    return cap <= 0 or spent_today(db) < cap


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
    outside.now("die KI")
    import anthropic
    return anthropic.Anthropic(api_key=get_settings().anthropic_api_key, max_retries=retries,
                               timeout=timeout)


def _record(db: Session, task: str, model: str, actor: Optional[UserProfile],
            usage: dict[str, Any]) -> None:
    """Ein Aufruf ins Log – mit den Kosten in Franken (der Deckel zählt sie)."""
    billed_in = (int(usage.get("in") or 0) + CACHE_READ * int(usage.get("cache_read") or 0)
                 + CACHE_WRITE * int(usage.get("cache_write") or 0))
    usage = {**usage, "chf": cost_chf(model, round(billed_in), int(usage.get("out") or 0))}
    log.event(db, "ai.call", None, {"task": task, "model": model, **usage},
              kind="ai", actor=actor.object_id if actor else None)


def _gate() -> Optional[str]:
    """Warum es gar keinen Aufruf gibt – oder ``None``."""
    if not ready():
        return "Kein KI-Schlüssel hinterlegt."
    return None


def ask(db: Session, *, task: str, actor: Optional[UserProfile], system: str,
        content: list[dict], schema: type[T]) -> Optional[T]:
    """►►► **Ein Aufruf durch das Tor.** ◄◄◄ Gibt die geprüfte Antwort zurück – oder ``None``
    (keine KI, Deckel erreicht, abgelehnt, Antwort unbrauchbar, Netz weg). Nie eine Ausnahme:
    ein Ausfall der KI darf nie eine Handlung zerlegen."""
    return converse(db, task=task, actor=actor, system=system, content=content, schema=schema)


@dataclass(frozen=True)
class Tool:
    """**Ein Lese-Werkzeug der KI** – Name, ein Satz, die Form der Eingabe, und was es tut.
    ``run`` bekommt die Eingabe und gibt Text zurück; es liest mit den Rechten des Akteurs
    (``services/ai_tools``) und schreibt nie."""

    name: str
    description: str
    properties: dict[str, Any]
    run: Callable[[dict[str, Any]], str]
    required: tuple[str, ...] = field(default=())
    #: Was die Person live sieht, während das Werkzeug läuft («sucht», «liest») – davor steht
    #: nichts, dahinter der erste Wert der Eingabe.
    doing: str = ""
    #: Welcher Wert der Eingabe dahinter steht – leer: der erste.
    shows: str = ""

    def step(self, args: dict[str, Any]) -> str:
        values = [args.get(self.shows)] if self.shows else list(args.values())
        first = next((str(v) for v in values if isinstance(v, (str, int)) and str(v).strip()), "")
        return " ".join(f"{self.doing or self.name} {first[:80]}".split())

    def spec(self) -> dict[str, Any]:
        return {"name": self.name, "description": self.description, "strict": True,
                "input_schema": {"type": "object", "properties": self.properties,
                                 "required": list(self.required or self.properties),
                                 "additionalProperties": False}}


#: So viel Text gibt ein Werkzeug höchstens zurück.
TOOL_TEXT = 8000
#: Warum keine Antwort kam, wenn die Person «Stopp» drückte.
STOPPED = "Angehalten."


def _ms(began: float) -> int:
    """Wie lange ein Aufruf dauerte – in Millisekunden, für das Log (``ai.call``)."""
    return int((_time.monotonic() - began) * 1000)


def _tokens(usage: Any) -> dict[str, int]:
    """Die Tokens eines Zugs – neu gelesen, aus dem Zwischenspeicher, in ihn geschrieben."""
    return {"in": int(usage.input_tokens or 0), "out": int(usage.output_tokens or 0),
            "cache_read": int(getattr(usage, "cache_read_input_tokens", 0) or 0),
            "cache_write": int(getattr(usage, "cache_creation_input_tokens", 0) or 0)}


#: Was ein Token aus dem Zwischenspeicher kostet (lesen · schreiben), gemessen am vollen Preis.
CACHE_READ, CACHE_WRITE = 0.1, 1.25


def _use(tools: dict[str, Tool], block: Any) -> dict[str, Any]:
    """Ein Werkzeug ausführen – ein Fehler ist eine Antwort an die KI, kein Absturz."""
    tool = tools.get(block.name)
    try:
        if tool is None:
            raise ValueError(f"Unbekanntes Werkzeug {block.name!r}.")
        text, error = tool.run(dict(block.input or {}))[:TOOL_TEXT], False
    except Exception as exc:                                   # noqa: BLE001
        text, error = f"Fehler: {getattr(exc, 'detail', None) or exc}", True
    return {"type": "tool_result", "tool_use_id": block.id, "content": text, "is_error": error}


def _replay(content: list[Any]) -> list[dict[str, Any]]:
    """Die Antwort des Modells, wie sie im nächsten Zug wieder hinein muss – unverändert
    (auch das Nachdenken), ohne die geprüfte Fassung, die nur dieses SDK anhängt."""
    out = []
    for block in content:
        d = block.to_dict()
        d.pop("parsed_output", None)
        out.append(d)
    return out


def converse(db: Session, *, task: str, actor: Optional[UserProfile], system: str,
             content: list[dict], schema: type[T], tools: Optional[list[Tool]] = None,
             on_step: Optional[Callable[[str], None]] = None,
             stopped: Optional[Callable[[], bool]] = None) -> Optional[T]:
    """►►► **Ein Gespräch mit Werkzeugen** – die KI darf nachschlagen (höchstens
    ``Task.rounds`` Züge, alle zusammen in ``Task.timeout``), dann kommt die Antwort in fester
    Form. Jeder Zug ist ein ``ai.call`` (mit Dauer ``ms``); vor jedem Zug gilt der Deckel. Nie
    eine Ausnahme – ``problem()`` sagt, warum nichts kam. ``on_step`` hört jeden Schritt (live
    im «+»), ``stopped`` hält vor dem nächsten Zug an (die Person drückte «Stopp»).

    **Zwischenspeicher**: Anleitung und Werkzeuge sind in jedem Zug gleich – der Anbieter merkt
    sie sich (``cache_control``), jeder weitere Zug liest sie schneller und für einen Zehntel. ◄◄◄"""
    _PROBLEM.set("")
    blocked = _gate()
    if blocked:
        _PROBLEM.set(blocked)
        return None
    spec = TASKS[task]
    by_name = {t.name: t for t in tools or []}
    messages: list[dict[str, Any]] = [{"role": "user", "content": content}]
    extra: dict[str, Any] = {}
    if by_name:
        extra["tools"] = [t.spec() for t in by_name.values()]
    if spec.effort:
        extra["output_config"] = {"effort": spec.effort}
    deadline = _time.monotonic() + _left(spec.timeout)
    cached = [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}]
    for turn in range(1, max(1, spec.rounds) + 1):
        if stopped is not None and stopped():
            _PROBLEM.set(STOPPED)
            return None
        if not available(db):
            _PROBLEM.set("Der Tagesdeckel der KI ist erreicht – morgen wieder.")
            return None
        left = deadline - _time.monotonic()
        if left < 3:
            _PROBLEM.set("Die KI hat zu lange gebraucht – gleich noch einmal.")
            return None
        usage: dict[str, Any] = {"turn": turn}
        began = _time.monotonic()
        try:
            response = _client(left, _retries(spec.retries)).messages.parse(
                model=spec.model, max_tokens=spec.max_tokens, system=cached,
                messages=messages, output_format=schema, **extra)
            usage.update({**_tokens(response.usage), "stop": response.stop_reason, "ms": _ms(began)})
        except Exception as exc:                               # noqa: BLE001
            usage.update({"error": type(exc).__name__, "status": getattr(exc, "status_code", None),
                          "ms": _ms(began)})
            _record(db, task, spec.model, actor, usage)
            _PROBLEM.set(problem_of(exc))
            print(f"WARNING: ai.{task} failed: {exc!r}", flush=True)
            return None
        calls = [b for b in getattr(response, "content", None) or [] if getattr(b, "type", "") == "tool_use"]
        usage["tools"] = [b.name for b in calls] or None
        _record(db, task, spec.model, actor, usage)
        if response.stop_reason == "tool_use" and calls:
            messages.append({"role": "assistant", "content": _replay(response.content)})
            results: list[dict[str, Any]] = []
            for b in calls:
                if on_step is not None and b.name in by_name:
                    on_step(by_name[b.name].step(dict(b.input or {})))
                results.append(_use(by_name, b))
            if turn == spec.rounds - 1:
                results.append({"type": "text", "text": "Antworte jetzt – ohne weiteres Nachschlagen."})
            messages.append({"role": "user", "content": results})
            continue
        result = response.parsed_output if response.stop_reason not in ("refusal", "max_tokens") else None
        if result is None:
            _PROBLEM.set("Die KI hat abgelehnt." if response.stop_reason == "refusal"
                         else "Die Antwort der KI war unvollständig.")
        return result
    _PROBLEM.set("Die KI kam zu keinem Ergebnis (zu viel nachgeschlagen).")
    return None


# ─── Vertex AI: Bedeutungs-Zahlen und Abschreiben ────────────────────────────────────────

#: Das Hilfsmodell für Bedeutungs-Zahlen und ihre Länge (``ai_memory.embedding``).
EMBED_MODEL = "gemini-embedding-001"
EMBED_DIMS = 768
#: ►► **Das Modell, das abschreibt** (Phase 4 · Sprache) – an EINER Stelle. Gemini 2.5 ist auf
#:    Vertex seit Oktober 2026 abgeschaltet. ◄◄
TRANSCRIBE_MODEL = "gemini-3.5-flash"
#: Der Auftrag zum Abschreiben – wörtlich, eine Datei.
ABSCHRIFT = (Path(__file__).resolve().parents[1] / "assets" / "ai" / "abschrift.md").read_text("utf-8")


#: Nach einer Abweisung (nicht eingerichtet, kein Recht, Modell unbekannt) wird ein Modell eine
#: Stunde lang nicht mehr gefragt – sonst stünde jeder Takt einen Fehlversuch mehr im Log.
_VERTEX_PAUSE_S = 3600.0
#: Je Modell: bis wann (``time.monotonic``) es nach einer Abweisung ruht.
_vertex_paused: dict[str, float] = {}
#: Hat das Modell beim letzten Abschreiben den Inhalt abgelehnt (nicht: war es nicht erreichbar)?
_REFUSED: ContextVar[bool] = ContextVar("ai_refused", default=False)
#: Wurde beim letzten Abschreiben gefragt, und es kam nichts Brauchbares – Zeit überschritten,
#: 5xx, 429, abgeschnitten (``MAX_TOKENS``)? Ein neuer Versuch kann helfen, aber nicht ewig.
_FAULTED: ContextVar[bool] = ContextVar("ai_faulted", default=False)
#: So viele Tokens zählt Gemini je Sekunde Audio – daraus die geschätzten Kosten eines Aufrufs,
#: dessen Antwort nie kam (die Rechnung kommt trotzdem; der Deckel muss sie sehen).
AUDIO_TOKENS_PER_SECOND = 32


def _vertex_ready(model: str) -> bool:
    return bool(get_settings().vertex_project) and _time.monotonic() >= _vertex_paused.get(model, 0.0)


def embed_ready() -> bool:
    return _vertex_ready(EMBED_MODEL)


def transcribe_ready() -> bool:
    return _vertex_ready(TRANSCRIBE_MODEL)


def refused() -> bool:
    """Hat das Modell beim letzten ``transcribe`` **den Inhalt** abgelehnt (400, blockiert, keine
    Antwort)? Nicht: Deckel, keine Einrichtung, keine Zeit, Netz – das geht später wieder."""
    return _REFUSED.get()


def faulted() -> bool:
    """Wurde beim letzten ``transcribe`` gefragt, ohne brauchbare Antwort (Zeit, 5xx, 429,
    abgeschnitten)? Nicht: abgelehnt (``refused``), nicht gefragt (Deckel, Einrichtung, Pause)."""
    return _FAULTED.get()


def remaining(limit: float) -> float:
    """Wie viele Sekunden ein Aufruf jetzt noch hätte – ``limit`` oder weniger unter ``until``."""
    return _left(limit)


def _vertex_session():
    """Die Sitzung zu Vertex AI – unter einer Zeitgrenze ohne zweiten Versuch (``_retries``)."""
    import google.auth
    from google.auth.transport.requests import AuthorizedSession
    creds, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
    return AuthorizedSession(creds, max_refresh_attempts=_retries(2))


def _vertex_problem(status: Optional[int], text: str, what: str = "Bedeutungs-Zahlen",
                    model: str = "", region: str = "") -> str:
    if status in (401, 403):
        return ("Vertex AI ist nicht eingerichtet oder der Dienst darf es nicht nutzen "
                "(einmal infra/setup-vertex.sh).")
    if status == 404:
        setting = "VERTEX_GEMINI_REGION" if model == TRANSCRIBE_MODEL else "VERTEX_REGION"
        return (f"Das Modell «{model}» für {what} gibt es in der Region «{region}» nicht – "
                f"eine andere Region in {setting} setzen.")
    if status == 429:
        return "Vertex AI ist gerade ausgelastet – gleich noch einmal."
    return f"Vertex AI antwortet nicht ({status or 'kein Netz'}): {text[:160]}"


@dataclass
class _VertexCall:
    """Ein Aufruf an Vertex AI: die Antwort (``data``), was ins ``ai.call`` gehört (``usage``),
    ob überhaupt gefragt wurde (``asked``) und der HTTP-Status einer Abweisung."""
    asked: bool = False
    data: Optional[dict[str, Any]] = None
    usage: dict[str, Any] = field(default_factory=dict)
    status: Optional[int] = None
    #: Keine Antwort in der Zeit – die Anfrage war aber unterwegs (und kostet vermutlich).
    timeout: bool = False


def _vertex(db: Session, *, model: str, method: str, body: dict[str, Any], limit: float,
            least: float, what: str, region: str = "") -> _VertexCall:
    """►►► **Ein Aufruf an Vertex AI** (Region ``region``, sonst ``VERTEX_REGION``) – EINE Stelle für Bedeutungs-
    Zahlen und Abschreiben: Einrichtung, Pause nach Abweisung, Deckel, Zeitgrenze (``until``, kein
    zweiter Versuch), Fehler als ein Satz in ``problem()``. Ins Log schreibt der Aufrufer
    (``_record``), denn nur er kennt die Tokens. ◄◄◄"""
    outside.now("die KI")
    settings = get_settings()
    if not settings.vertex_project:
        _PROBLEM.set(f"{what} ist nicht eingerichtet (VERTEX_PROJECT fehlt).")
        return _VertexCall()
    if not _vertex_ready(model):
        _PROBLEM.set("Vertex AI hat eben abgewiesen – in einer Stunde wieder (infra/setup-vertex.sh).")
        return _VertexCall()
    cap = cap_chf()
    if cap > 0 and spent_today(db) >= cap:
        _PROBLEM.set("Der Tagesdeckel der KI ist erreicht – morgen wieder.")
        return _VertexCall()
    wait = _left(limit)
    if wait < least:
        _PROBLEM.set(f"Keine Zeit mehr für {what} – der Takt holt es nach.")
        return _VertexCall()
    region = region or settings.vertex_region
    url = (f"https://{region}-aiplatform.googleapis.com/v1/projects/{settings.vertex_project}"
           f"/locations/{region}/publishers/google/models/{model}:{method}")
    out = _VertexCall(asked=True)
    try:
        r = _vertex_session().post(url, data=json.dumps(body), timeout=wait,
                                   headers={"Content-Type": "application/json"})
        if r.status_code != 200:
            out.usage, out.status = {"error": "http", "status": r.status_code}, r.status_code
            _PROBLEM.set(_vertex_problem(r.status_code, r.text, what, model, region))
            if r.status_code in (401, 403, 404):
                _vertex_paused[model] = _time.monotonic() + _VERTEX_PAUSE_S
        else:
            out.data = r.json()
    except Exception as exc:                                   # noqa: BLE001
        name = type(exc).__name__
        out.usage = {"error": name}
        out.timeout = "timeout" in name.lower() and "connect" not in name.lower()
        _PROBLEM.set(_vertex_problem(None, str(exc), what))
        print(f"WARNING: ai.{method} ({model}) failed: {exc!r}", flush=True)
    return out


def embed(db: Session, text: str, *, actor: Optional[UserProfile], query: bool = False
          ) -> Optional[list[float]]:
    """►►► **Die Bedeutungs-Zahlen eines Textes** (Vertex AI, Region ``VERTEX_REGION``) – oder
    ``None`` (nicht eingerichtet, Deckel, Fehler; ``problem()`` sagt warum). ``query``: der Text
    sucht (die Frage), sonst wird er gefunden (der Fall). Ein ``ai.call`` wie jeder Aufruf. ◄◄◄"""
    _PROBLEM.set("")
    body = {"instances": [{"content": text[:8000],
                           "task_type": "RETRIEVAL_QUERY" if query else "RETRIEVAL_DOCUMENT"}],
            "parameters": {"outputDimensionality": EMBED_DIMS, "autoTruncate": True}}
    call = _vertex(db, model=EMBED_MODEL, method="predict", body=body, limit=20.0, least=2.0,
                   what="Bedeutungs-Zahlen")
    if not call.asked:
        return None
    values: Optional[list[float]] = None
    usage = call.usage
    if call.data is not None:
        try:
            pred = call.data["predictions"][0]["embeddings"]
            values = [float(v) for v in pred["values"]]
            usage = {"in": int(pred.get("statistics", {}).get("token_count") or len(text) // 4)}
            if len(values) != EMBED_DIMS:
                values = None
                _PROBLEM.set("Vertex AI lieferte Zahlen in der falschen Länge.")
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            usage = {"error": type(exc).__name__}
            _PROBLEM.set("Vertex AI lieferte keine Bedeutungs-Zahlen.")
    _record(db, "embed", EMBED_MODEL, actor, usage)
    return values


#: Was Gemini als Audio annimmt – ohne Zusätze wie ``;codecs=opus``.
def audio_type(mime: str) -> str:
    return (mime or "").split(";", 1)[0].strip().lower() or "audio/webm"


#: Ein Ende, das keinen Text bringt: Gemini hat den Inhalt abgelehnt.
_BLOCKED = frozenset({"SAFETY", "RECITATION", "BLOCKLIST", "PROHIBITED_CONTENT", "SPII",
                      "IMAGE_SAFETY", "OTHER"})


def _transcript(data: dict[str, Any]) -> tuple[Optional[str], dict[str, Any]]:
    """Der Text und die Tokens aus der Antwort von ``generateContent`` – ``None``: abgelehnt."""
    meta = data.get("usageMetadata") or {}
    usage = {"in": int(meta.get("promptTokenCount") or 0),
             "out": int(meta.get("candidatesTokenCount") or 0) + int(meta.get("thoughtsTokenCount") or 0)}
    candidates = data.get("candidates") or []
    if (data.get("promptFeedback") or {}).get("blockReason") or not candidates:
        return None, {**usage, "stop": (data.get("promptFeedback") or {}).get("blockReason") or "none"}
    first = candidates[0]
    usage["stop"] = first.get("finishReason")
    if first.get("finishReason") in _BLOCKED or first.get("finishReason") == "MAX_TOKENS":
        return None, usage            # abgelehnt – oder abgeschnitten: nie still übernehmen
    parts = (first.get("content") or {}).get("parts") or []
    text = "".join(str(p.get("text") or "") for p in parts if not p.get("thought"))
    return text.strip(), usage


def transcribe(db: Session, raw: bytes, mime: str, *, actor: Optional[UserProfile],
               seconds: float = 0.0) -> Optional[str]:
    """►►► **Gesprochenes abschreiben** (Phase 4, Gemini über Vertex AI, Region
    ``VERTEX_GEMINI_REGION`` – leer: ``VERTEX_REGION``) – der Text (leer bei Stille) oder
    ``None``: ``problem()`` sagt warum, ``refused()`` ob Gemini **den Inhalt** ablehnte (dann
    hilft kein zweiter Versuch), ``faulted()`` ob gefragt wurde, ohne brauchbare Antwort (Zeit,
    5xx, 429, abgeschnitten – ein neuer Versuch kann helfen). Durch dieselbe Tür wie jeder
    Aufruf: Deckel, ``until`` (keine Wiederholung), Pause nach Abweisung, ein ``ai.call`` mit
    Kosten – kam keine Antwort, mit den **geschätzten** Kosten aus ``seconds`` Audio. ◄◄◄"""
    _PROBLEM.set("")
    _REFUSED.set(False)
    _FAULTED.set(False)
    settings = get_settings()
    body = {"systemInstruction": {"parts": [{"text": ABSCHRIFT.strip()}]},
            "contents": [{"role": "user", "parts": [
                {"inlineData": {"mimeType": audio_type(mime),
                                "data": base64.standard_b64encode(raw).decode("ascii")}},
                {"text": "Schreibe diese Aufnahme ab."}]}],
            "generationConfig": {"maxOutputTokens": 16384}}
    began = _time.monotonic()
    call = _vertex(db, model=TRANSCRIBE_MODEL, method="generateContent", body=body, limit=55.0,
                   least=10.0, what="Abschreiben",
                   region=settings.vertex_gemini_region or settings.vertex_region)
    if not call.asked:
        return None
    text: Optional[str] = None
    usage = call.usage
    if call.data is not None:
        text, usage = _transcript(call.data)
        if text is None:
            _REFUSED.set(usage.get("stop") != "MAX_TOKENS")
            _FAULTED.set(usage.get("stop") == "MAX_TOKENS")
            _PROBLEM.set(f"Gemini hat die Aufnahme nicht abgeschrieben ({usage.get('stop')}).")
    elif call.status == 400:
        _REFUSED.set(True)
    elif call.status not in (401, 403, 404):
        _FAULTED.set(True)                        # Zeit, 5xx, 429, Netz
        if call.timeout:
            usage = {**usage, "in": int(seconds * AUDIO_TOKENS_PER_SECOND), "estimated": True}
    _record(db, "transcribe", TRANSCRIBE_MODEL, actor, {**usage, "ms": _ms(began)})
    return text
