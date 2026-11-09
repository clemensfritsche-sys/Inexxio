"""►►► **Wer ruft den Takt? – ein Google-Token, kein Geheimnis.** ◄◄◄

Der Dienst ist öffentlich (Firebase Hosting leitet ``/api/**`` nur an einen öffentlichen
Dienst weiter). Den Takt (``POST /api/v1/internal/tick``) darf darum nur, wer ein **von Google
signiertes ID-Token (OIDC)** mitbringt, ausgestellt für das Dienstkonto des Takts
(``TICK_SERVICE_ACCOUNT``) und für genau diese Umgebung (``aud`` = ``TICK_AUDIENCE``). Cloud
Scheduler holt es bei jedem Aufruf neu (``--oidc-service-account-email`` /
``--oidc-token-audience``, eingerichtet im Deploy).

* ohne beide Einstellungen: **503** «Takt nicht eingerichtet» – nie ein Takt ohne Anmeldung,
* ohne oder mit ungültigem Token (Signatur, Ablauf, Aussteller, Zielgruppe): **401**,
* gültig, aber ein anderes Konto oder eine unbestätigte Adresse: **403**.

Danach handelt **das System** (``act(db, "system", None, "job")``).
"""

from typing import Any, Mapping, Optional

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from .actor import act
from .config import get_settings
from .database import DB
from ..domain.errors import rejected

_bearer = HTTPBearer(auto_error=False)
_request: Any = None


def _transport():
    """Ein HTTP-Transport für Googles öffentliche Schlüssel (einmal je Prozess angelegt; die
    Schlüssel holt er je Takt – alle 5 Minuten ein kleiner Abruf, ohne Zusatzpaket)."""
    global _request
    if _request is None:
        from google.auth.transport.requests import Request
        _request = Request()
    return _request


def verify(token: str, audience: str) -> Mapping[str, Any]:
    """Signatur, Ablauf, Aussteller (``accounts.google.com``) und Zielgruppe – Google's
    eigene Prüfung. Wirft ``ValueError`` bei einem ungültigen Token."""
    from google.oauth2 import id_token
    return id_token.verify_oauth2_token(token, _transport(), audience=audience,
                                        clock_skew_in_seconds=10)


def caller_problem(token: Optional[str]) -> Optional[tuple[int, str]]:
    """**Darf dieser Aufrufer den Takt?** ``None`` = ja; sonst (Status, Satz)."""
    s = get_settings()
    if not (s.tick_audience and s.tick_service_account):
        return 503, "Takt nicht eingerichtet."
    if not token:
        return 401, "Der Takt verlangt ein Google-Token."
    from google.auth import exceptions
    try:
        claims = verify(token, s.tick_audience)
    except exceptions.TransportError:
        return 503, "Die Schlüssel von Google sind gerade nicht erreichbar."
    except (ValueError, exceptions.GoogleAuthError):
        return 401, "Das Google-Token ist ungültig."
    if claims.get("email") != s.tick_service_account or claims.get("email_verified") is not True:
        return 403, f"Das Konto «{claims.get('email') or '?'}» darf den Takt nicht auslösen."
    return None


def require_tick(cred: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
                 db: Session = DB) -> None:
    """Abhängigkeit des Takts: Token prüfen, dann handelt das System (``job``)."""
    problem = caller_problem(cred.credentials if cred else None)
    if problem:
        raise rejected(problem[0], problem[1])
    act(db, "system", None, "job")


require_tick.log_actor = True       # der Wächter (tests/test_log.py) erkennt sie daran
