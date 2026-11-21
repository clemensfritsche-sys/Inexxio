"""►►► **Die Tür nach aussen – erst nach dem Speichern.** ◄◄◄ (Projektakte, Phase 5 §6.2)

Was das ERP nach aussen tut (Mail, Zahlung, Datei im Speicher, KI), darf nie geschehen sein,
wenn die Handlung danach verworfen wird. Zwei Wörter, eine Stelle:

* ``after(db, fn)`` – ``fn()`` läuft, **nachdem** diese Sitzung gespeichert hat (Ereignis
  ``after_commit``); wird verworfen, läuft sie nie. So gehen Mails hinaus
  (``mailbox.send_after``).
* ``now(was)`` – für das, was sofort eine Antwort von aussen braucht. Gewöhnlich geschieht
  nichts; in einem **Probelauf** (``probing``) gibt es ``NeedsHand``: diese Handlung braucht
  die Hand der Person, die KI bringt sie nur hin.

Dazu der Riegel: in einem Probelauf speichert keine Sitzung – wer es versucht, bekommt
ebenfalls ``NeedsHand`` (ein Arbeitsschritt, der zwischendurch festschreibt, ist kein
Handgriff).
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Callable, Iterator

from sqlalchemy import event
from sqlalchemy.orm import Session

from .database import SessionLocal

log = logging.getLogger(__name__)

_PROBING: ContextVar[bool] = ContextVar("probing", default=False)
_AFTER = "outside_after"


class NeedsHand(Exception):
    """Im Probelauf: diese Handlung geht nach aussen oder speichert zwischendurch – sie braucht
    die Person selbst."""

    def __init__(self, what: str):
        super().__init__(what)
        self.what = what


def probing() -> bool:
    """Läuft gerade ein Probelauf?"""
    return _PROBING.get()


@contextmanager
def probe() -> Iterator[None]:
    """Für die Dauer des Blocks ist es ein Probelauf (nur ``services/handgriff``)."""
    token = _PROBING.set(True)
    try:
        yield
    finally:
        _PROBING.reset(token)


def now(what: str) -> None:
    """Gleich geht etwas nach aussen (``what``: in Worten der Oberfläche). Im Probelauf nicht."""
    if _PROBING.get():
        raise NeedsHand(what)


def after(db: Session, fn: Callable[[], None]) -> None:
    """``fn()`` nach dem nächsten Speichern dieser Sitzung – nie, wenn verworfen wird (auch nicht,
    wenn nur der Sicherungspunkt verworfen wird, in dem sie angemeldet wurde). Dieselbe Funktion
    zweimal angemeldet läuft einmal."""
    if db.get_transaction() is None:
        db.connection()                 # die Transaktion beginnt jetzt – an sie hängt sich fn
    where = db.get_nested_transaction() or db.get_transaction()
    waiting = db.info.setdefault(_AFTER, [])
    if all(f is not fn for _, f in waiting):
        waiting.append((where, fn))


def _within(tx, gone) -> bool:
    """Gehört ``tx`` zu ``gone`` (oder darunter)?"""
    while tx is not None:
        if tx is gone:
            return True
        tx = tx.parent
    return False


@event.listens_for(SessionLocal, "before_commit")
def _no_commit_in_probe(session: Session) -> None:
    if _PROBING.get():
        raise NeedsHand("speichert zwischendurch")


@event.listens_for(SessionLocal, "after_commit")
def _run_after(session: Session) -> None:
    if session.in_nested_transaction():
        return      # nur ein Sicherungspunkt – gespeichert ist erst die ganze Transaktion
    for _, fn in session.info.pop(_AFTER, []):
        try:
            fn()
        except Exception as exc:        # noqa: BLE001 – gespeichert ist gespeichert
            log.warning("Nach dem Speichern gescheitert (%s): %r",
                        getattr(fn, "__name__", fn), exc)


@event.listens_for(SessionLocal, "after_soft_rollback")
def _drop_after(session: Session, previous_transaction) -> None:
    """Verworfen wird nur, was in der verworfenen Transaktion (oder ihrem Sicherungspunkt)
    angemeldet wurde – ein Sicherungspunkt nimmt nicht die Mails der ganzen Anfrage mit."""
    waiting = session.info.get(_AFTER)
    if waiting:
        session.info[_AFTER] = [(tx, fn) for tx, fn in waiting if not _within(tx, previous_transaction)]
