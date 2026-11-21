"""►►► **Die Website-Statistik** – was bringt Anfragen? Ohne Cookies, ohne IP, ohne Banner. ◄◄◄

Die Website ist statisch (Firebase Hosting); der Dienst sieht sie nie. Darum meldet jede Seite
sich selbst (``website/src/scripts/stats.ts`` → ``POST /api/v1/public/page``): Ansicht,
Lesezeit, Klick auf Telefon/Mail/Route, die Schritte des Formulars, die Ladezeit. Anfrage und
Newsletter-Anmeldung zählt der Dienst selbst, dort, wo sie entstehen (``convert``).

**Die Regeln** (so steht es in der Datenschutzerklärung):

* Nichts auf dem Gerät – kein Cookie, kein Speicher im Browser.
* **Die IP-Adresse wird nie gespeichert.** Ein Besuch ist ``visitor``: eine Prüfsumme aus dem
  Schlüssel des Tages, der Adresse und dem Browser. Der Schlüssel ist zufällig, steht nur in
  ``site_salts`` und wird gelöscht, sobald der Tag vorbei ist (``prune``, im Takt) – danach
  lässt sich die Kennung keiner Adresse mehr zuordnen, und morgen ist derselbe Mensch ein
  anderer Besuch.
* Eine Anfrage trägt **keine** Kennung, nur Einstieg und Quelle ihres Besuchs – sonst liesse
  sie sich mit dem Rest des Besuchs verbinden.
* Wer im ERP angemeldet ist, zählt nicht (das Skript fragt ``html[data-account="staff"]``),
  Roboter auch nicht (``is_bot``). Aufrufe älter als ``KEEP_DAYS`` gehen weg.

Die Auswertung (``site_stats_view.view``) ist eine Ableitung über diese eine Tabelle; die Quelle benennt
``domain/site_sources`` beim Lesen.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Optional
from urllib.parse import parse_qs, urlsplit

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session
from starlette.requests import Request

from ..core import clock
from ..domain import site_sources as src
from ..models import SiteHit, SiteSalt
from . import geoip

#: Was eine Seite melden darf (``value``: Sekunden · ms · Verschiebung × 1000).
BEACON_KINDS = {"view", "leave", "call", "mail", "route", "form_view", "form_start", "form_step",
                "lcp", "cls"}
#: Was der Dienst selbst zählt, wo es entsteht.
SERVER_KINDS = {"inquiry", "newsletter"}
#: Klicks und Abschlüsse tragen den Einstieg ihres Besuchs.
CONVERSIONS = {"call", "mail", "route", "inquiry", "newsletter"}
#: Obergrenzen der Werte – darüber ist es kein Messwert, sondern ein Fehler.
VALUE_MAX = {"leave": 1800, "lcp": 60_000, "cls": 5_000}
#: Sprachen der Website ausser Deutsch (Präfix der Adresse).
LANGS = ("fr", "en", "it")
#: So lange bleiben Aufrufe (gut zwei Jahre – der Vergleich mit dem Vorjahr).
KEEP_DAYS = 800
#: Erlaubte Zeiträume der Auswertung (Tage).
PERIODS = (7, 30, 90, 365)

_PATH = re.compile(r"^/[\w\-./%~]*$")
_BOT = re.compile(r"bot|crawl|spider|slurp|headless|lighthouse|preview|facebookexternalhit|"
                  r"embedly|curl|wget|python|httpclient|phantom|puppeteer|playwright|monitor",
                  re.IGNORECASE)


@dataclass(frozen=True)
class Who:
    """Wer gerade die Seite meldet – nur für diese Anfrage, nie gespeichert."""
    ip: str
    ua: str


def who(request: Request) -> Who:
    peer = request.client.host if request.client else None
    return Who(ip=geoip.client_ip(request.headers, peer) or "",
               ua=(request.headers.get("user-agent") or "")[:400])


def is_bot(ua: str) -> bool:
    return not ua or bool(_BOT.search(ua))


def device_of(ua: str) -> str:
    if re.search(r"iPad|Tablet|Android(?!.*Mobile)", ua):
        return "tablet"
    if re.search(r"Mobi|iPhone|Android", ua):
        return "mobile"
    return "desktop"


def clean_path(value: Any) -> Optional[str]:
    """Die Seite ohne Adress-Parameter (die können Schlüssel tragen, ``?t=…``) – sonst ``None``."""
    if not isinstance(value, str):
        return None
    p = value.split("?")[0].split("#")[0].strip()
    if len(p) > 1:
        p = p.rstrip("/")
    return p if 0 < len(p) <= 300 and _PATH.match(p) else None


def lang_of(path: str) -> str:
    first = path.strip("/").split("/")[0]
    return first if first in LANGS else "de"


# ------------------------------------------------------------------ der Besuch

_salts: dict[date, bytes] = {}


def _salt(db: Session, day: date) -> bytes:
    """Der Schlüssel des Tages – zufällig, für alle Instanzen derselbe (die Zeile gewinnt)."""
    if day in _salts:
        return _salts[day]
    db.execute(insert(SiteSalt).values(day=day, salt=os.urandom(32), created_at=clock.utcnow(),
                                       updated_at=clock.utcnow()).on_conflict_do_nothing())
    salt = db.execute(select(SiteSalt.salt).where(SiteSalt.day == day)).scalar_one()
    _salts.clear()
    _salts[day] = bytes(salt)
    return _salts[day]


def visitor_key(db: Session, w: Who, day: date) -> str:
    return hashlib.sha256(_salt(db, day) + f"{w.ip}|{w.ua}".encode()).hexdigest()[:16]


def _entry_of(db: Session, day: date, visitor: str) -> Optional[SiteHit]:
    """Der jüngste Einstieg dieses Besuchs heute – woher er kam."""
    return db.execute(select(SiteHit).where(SiteHit.day == day, SiteHit.visitor == visitor,
                                            SiteHit.entry.is_(True))
                      .order_by(SiteHit.id.desc()).limit(1)).scalar_one_or_none()


def _attach_entry(hit: SiteHit, entry: Optional[SiteHit]) -> None:
    if entry is not None:
        hit.entry_path, hit.ref_host = entry.path, entry.ref_host
        hit.utm_source, hit.utm_campaign = entry.utm_source, entry.utm_campaign


def _utm(query: Any) -> tuple[Optional[str], Optional[str]]:
    q = parse_qs(query[1:] if isinstance(query, str) and query.startswith("?") else
                 (query if isinstance(query, str) else ""))
    pick = lambda k: (q.get(k, [""])[0].strip().lower()[:80] or None)   # noqa: E731
    return pick("utm_source"), pick("utm_campaign")


def record(db: Session, w: Who, data: dict, country: Optional[str]) -> bool:
    """►► Eine Meldung der Website – ``False``, wenn sie nichts ist (falsch, Roboter)."""
    kind, path = data.get("k"), clean_path(data.get("p"))
    if kind not in BEACON_KINDS or path is None or is_bot(w.ua):
        return False
    day = clock.today()
    visitor = visitor_key(db, w, day)
    hit = SiteHit(day=day, kind=kind, visitor=visitor, path=path, lang=lang_of(path), entry=False,
                  device=device_of(w.ua), country=country)
    if kind == "view":
        ref, own = src.host_of(data.get("r")), src.host_of(data.get("h"))
        if not ref or ref != own:
            hit.entry, hit.ref_host = True, ref or None
            hit.utm_source, hit.utm_campaign = _utm(data.get("q"))
    elif kind in VALUE_MAX:
        v = data.get("v")
        if not isinstance(v, (int, float)) or not 0 <= v <= VALUE_MAX[kind]:
            return False
        hit.value = int(v)
    if kind in CONVERSIONS:
        _attach_entry(hit, _entry_of(db, day, visitor))
    db.add(hit)
    return True


def convert(db: Session, w: Who, kind: str, page: Optional[str], country: Optional[str],
            message_id: Optional[int] = None) -> None:
    """►► Eine Anfrage oder Newsletter-Anmeldung – mit Einstieg und Quelle ihres Besuchs, aber
    ohne dessen Kennung."""
    assert kind in SERVER_KINDS
    path = clean_path(page) or "/"
    day = clock.today()
    hit = SiteHit(day=day, kind=kind, visitor=None, path=path, lang=lang_of(path), entry=False,
                  device=device_of(w.ua), country=country, message_id=message_id)
    _attach_entry(hit, _entry_of(db, day, visitor_key(db, w, day)))
    db.add(hit)


def page_of(referer: Optional[str]) -> Optional[str]:
    """Die Seite aus dem ``Referer`` einer Anfrage (für Abschlüsse ohne eigene Angabe)."""
    try:
        return clean_path(urlsplit(referer or "").path)
    except ValueError:
        return None


def prune(db: Session) -> dict[str, int]:
    """Im Takt: den Schlüssel vergangener Tage löschen, alte Aufrufe auch."""
    today = clock.today()
    salts = db.execute(delete(SiteSalt).where(SiteSalt.day < today)).rowcount
    hits = db.execute(delete(SiteHit).where(SiteHit.day < today - timedelta(days=KEEP_DAYS))).rowcount
    for d in [d for d in _salts if d < today]:
        _salts.pop(d, None)
    return {"salts": salts or 0, "hits": hits or 0}


def parse(raw: bytes) -> Optional[dict]:
    """Der Rumpf einer Meldung (``sendBeacon`` schickt Text) – höchstens 2 KB JSON-Objekt."""
    if len(raw) > 2048:
        return None
    try:
        data = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return None
    return data if isinstance(data, dict) else None
