"""►►► **Wer handelt – die EINE Stelle, die es der Datenbank sagt.** ◄◄◄

Jede Änderung im System schreibt die Datenbank selbst ins Log (``domain/log``), und sie
fragt dafür die Transaktion: ``inexxio.actor``. Gesetzt wird das nur hier, mit ``act``:

* angemeldet → ``core/auth.get_current_user`` (die Person, ``ui``),
* öffentliche Türen → die Abhängigkeit ``public(source)`` an der Route (``external``),
* Start, Jobs, Migration, Skripte → ``act(db, "system", source=…)`` bei der Sitzung.

``act`` merkt sich den Handelnden an der Sitzung (``session.info``) und setzt ihn in der
laufenden **und** in jeder späteren Transaktion dieser Sitzung (``after_begin``) – ``SET
LOCAL`` gilt nur bis zum Commit, und eine Sitzung erlebt mehrere. Eine Sitzung ist eine
Anfrage: alle Einträge einer Anfrage tragen dieselbe ``request_id``.

Fehlt der Handelnde, scheitert jedes Schreiben (``log_actor``) – laut, nie still. Welche
Route ihn setzt, prüft ein Wächter für jede Route (``tests/test_log.py``).
"""

import json
import uuid
from typing import Optional

from fastapi import Depends
from sqlalchemy.orm import Session

from ..domain.log import KINDS, SOURCES
from .database import ACTOR_KEY as _KEY, SET_ACTOR as _SET, SessionLocal, get_db


def act(db: Session, kind: str, actor_id: Optional[int] = None, source: str = "ui") -> None:
    """Ab jetzt handelt ``kind``/``actor_id`` (Objektnummer der Person) in dieser Sitzung."""
    if kind not in KINDS or source not in SOURCES:
        raise ValueError(f"Log: unbekannter Handelnder {kind!r}/{source!r}")
    request = (db.info.get(_KEY) or {}).get("request") or str(uuid.uuid4())
    db.info[_KEY] = {"kind": kind, "id": actor_id, "source": source, "request": request}
    if db.in_transaction():
        db.execute(_SET, {"a": json.dumps(db.info[_KEY])})


def public(source: str):
    """Abhängigkeit für eine **öffentliche** Route: hier handelt jemand von aussen
    (Website, Link, Webhook). Ohne sie scheitert jedes Schreiben dieser Route."""
    if source not in SOURCES:
        raise ValueError(source)

    def outside(db: Session = Depends(get_db)) -> None:
        act(db, "external", None, source)

    outside.log_actor = True        # der Wächter erkennt die Abhängigkeit daran
    return Depends(outside)


def system_session(source: str = "job") -> Session:
    """Eine eigene Sitzung, in der das System handelt (Start, Jobs, Skripte)."""
    db = SessionLocal()
    act(db, "system", None, source)
    return db
