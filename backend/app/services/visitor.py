"""►►► **Der Besucher einer öffentlichen Tür** – wer sendet, wie oft, aus welchem Land. ◄◄◄

EINE Stelle für alle Türen ohne Anmeldung (Anfrage, Newsletter, Passkey-Anmeldung):

* ``sender_key`` – wer sendet, so weit man es weiss (die letzten ``TRUSTED_HOPS`` Einträge
  von ``X-Forwarded-For``; die vorderen setzt der Absender selbst).
* ``allow_send`` – höchstens ``limit`` je Absender und Stunde **und** ``GLOBAL_LIMIT``
  insgesamt je Tür und Instanz (die Grenze, die sich nicht umgehen lässt). Nur im
  Arbeitsspeicher dieser Instanz.
* ``country`` – das Land des Besuchers (``geoip``), für die Gesellschaft, die ihm antwortet.
"""

from __future__ import annotations

import time
from collections import deque
from threading import Lock
from typing import Optional

from starlette.requests import Request

from . import geoip

WINDOW_SECONDS = 3600
#: Sendungen **insgesamt** je Tür, Stunde und Instanz.
GLOBAL_LIMIT = 60
#: So viele Einträge hängen die Proxys vor uns an ``X-Forwarded-For`` an (Firebase Hosting
#: zwei, dazu Cloud Run) – nur sie sind nicht vom Absender gesetzt.
TRUSTED_HOPS = 3

_hits: dict[str, deque[float]] = {}
_hits_lock = Lock()


def reset() -> None:
    """Für Tests: Zähler leeren."""
    with _hits_lock:
        _hits.clear()


def _allow(key: str, limit: int) -> bool:
    now = time.monotonic()
    with _hits_lock:
        q = _hits.setdefault(key, deque())
        while q and now - q[0] > WINDOW_SECONDS:
            q.popleft()
        if len(q) >= limit:
            return False
        q.append(now)
        if len(_hits) > 10_000:  # Speicher begrenzen: leere Einträge verwerfen
            for k in [k for k, v in _hits.items() if not v][:5_000]:
                _hits.pop(k, None)
        return True


def _peer(request: Request) -> Optional[str]:
    return request.client.host if request.client else None


def sender_key(request: Request) -> str:
    """Wer sendet – ohne Proxy (lokal) die Gegenstelle."""
    chain = [p.strip() for p in request.headers.get("x-forwarded-for", "").split(",") if p.strip()]
    return ",".join(chain[-TRUSTED_HOPS:]) if chain else (_peer(request) or "unbekannt")


def allow_send(kind: str, request: Request, limit: int) -> bool:
    """Je Absender ``limit`` je Stunde **und** insgesamt ``GLOBAL_LIMIT`` – beides muss passen."""
    return _allow(f"{kind}:{sender_key(request)}", limit) and _allow(f"{kind}:all", GLOBAL_LIMIT)


def country(request: Request) -> Optional[str]:
    """Das Land des Besuchers (ISO-2) – ``None``, wenn unbekannt."""
    return geoip.country_of(geoip.client_ip(request.headers, _peer(request)))
