"""►►► **Signierte Links – EINE Stelle** (Newsletter, Rückkehr vom Postfach-Verbinden). ◄◄◄

Ein Link trägt seine Aussage selbst (``payload``), dazu seinen **Zweck** und, wenn er
abläuft, den Zeitpunkt – signiert mit HMAC-SHA256. Es gibt keine Tabelle offener Links.
Ein Link für einen Zweck taugt für keinen anderen.

**Der Schlüssel** ist ``LINK_SECRET`` (Secret Manager). Geprüft wird mit ihm **und** mit dem
früheren Schlüssel (abgeleitet aus der Datenbankverbindung), damit Abmeldelinks ohne Ablauf,
die schon hinausgingen, gültig bleiben. Fehlt ``LINK_SECRET``, signiert der frühere
Schlüssel – mit einer Warnung im Log.
"""

import base64
import hashlib
import hmac
import json
import time
from functools import lru_cache
from typing import Any, Optional

from .config import get_settings

#: Reserviert im signierten Inhalt: der Zweck und der Ablauf.
_PURPOSE, _EXPIRES = "u", "e"


class Invalid(ValueError):
    """Unlesbar, gefälscht, für einen anderen Zweck oder abgelaufen."""


def _legacy_key() -> bytes:
    return hashlib.sha256(f"newsletter:{get_settings().database_url}".encode()).digest()


@lru_cache(maxsize=1)
def _warn_legacy() -> None:
    print("WARNING: LINK_SECRET fehlt – signierte Links nutzen den Schlüssel aus der "
          "Datenbankverbindung (bitte LINK_SECRET setzen).", flush=True)


def _keys() -> list[bytes]:
    """Der Schlüssel, der signiert, zuerst; danach, womit sonst noch geprüft wird."""
    secret = get_settings().link_secret
    if secret:
        return [secret.encode(), _legacy_key()]
    _warn_legacy()
    return [_legacy_key()]


def _mac(key: bytes, raw: str) -> str:
    return hmac.new(key, raw.encode(), hashlib.sha256).hexdigest()[:32]


def sign(payload: dict[str, Any], purpose: str, ttl: Optional[int] = None) -> str:
    """Ein Link-Token für ``purpose``; ``ttl`` in Sekunden (``None`` = ohne Ablauf)."""
    if _PURPOSE in payload or _EXPIRES in payload:
        raise ValueError("«u» und «e» sind im signierten Inhalt reserviert.")
    data = {**payload, _PURPOSE: purpose}
    if ttl:
        data[_EXPIRES] = int(time.time()) + ttl
    raw = base64.urlsafe_b64encode(json.dumps(data, separators=(",", ":")).encode()
                                   ).decode().rstrip("=")
    return f"{raw}.{_mac(_keys()[0], raw)}"


def read(token: str, purpose: str) -> dict[str, Any]:
    """Der Inhalt eines Tokens – oder ``Invalid``."""
    raw, _, sig = (token or "").partition(".")
    if not raw or not any(hmac.compare_digest(sig, _mac(k, raw)) for k in _keys()):
        raise Invalid("Der Link ist ungültig.")
    try:
        data = json.loads(base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4)))
    except ValueError:
        raise Invalid("Der Link ist ungültig.")
    if not isinstance(data, dict) or data.pop(_PURPOSE, None) != purpose:
        raise Invalid("Der Link ist ungültig.")
    expires = data.pop(_EXPIRES, None)
    if expires is not None and expires < time.time():
        raise Invalid("Der Link ist abgelaufen.")
    return data
