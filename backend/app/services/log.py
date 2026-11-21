"""►►► **Das Log aus Sicht der Anwendung.** ◄◄◄

Zeilen-Änderungen schreibt die Datenbank selbst (``domain/log``: ``log_row`` an jeder
Tabelle). Hier stehen nur die Dinge, die keine Zeile ändern:

* ``event`` – ein fachliches Ereignis (Mail gesendet, Datei gelesen, KI aufgerufen …),
* ``process_events`` – die Ereignisse des Prozesses (``process.<art>``; gelesen über die
  Sicht ``process_log`` / ``models.ProcessEvent``),
* ``seal_due`` / ``verify`` – die Versiegelung je Tag,
* ``redact`` – die einzige erlaubte Änderung (Datenschutz), selbst protokolliert.

Wer handelt, sagt ``core/actor.act`` – nie ein Parameter hier, ausser bei Ereignissen, die
ausdrücklich jemand anderes trägt (die KI im Namen einer Person, das System im Prozess).
"""

from typing import Any, Optional

from sqlalchemy import bindparam, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Session

from ..core.database import json_safe

_EVENT = text(
    "SELECT log_event(:name, :object_id, :payload, :tbl, :row_key, :kind, :actor)"
).bindparams(bindparam("payload", type_=JSONB))

_PROCESS = text(
    "SELECT log_process(:rows)"
).bindparams(bindparam("rows", type_=JSONB))


def event(db: Session, name: str, object_id: Optional[int] = None,
          payload: Optional[dict[str, Any]] = None, *, table: Optional[str] = None,
          row: Optional[Any] = None, kind: Optional[str] = None,
          actor: Optional[int] = None) -> int:
    """Ein fachliches Ereignis – in derselben Transaktion wie die Handlung (beides oder
    nichts). ``kind``/``actor`` nur, wenn ausdrücklich jemand anderes handelt (``ai`` im
    Namen von ``actor``)."""
    return db.execute(_EVENT, {
        "name": name, "object_id": object_id,
        "payload": json_safe(payload) if payload is not None else None,
        "tbl": table, "row_key": None if row is None else str(row),
        "kind": kind, "actor": actor,
    }).scalar_one()


def process_events(db: Session, rows: list[dict[str, Any]]) -> None:
    """Die Ereignisse des Prozesses, in dieser Reihenfolge. Je Zeile: ``order_id``,
    ``step_id``, ``instance_unit_id``, ``kind``, ``status_before``, ``status_after``,
    ``payload``, ``actor_id`` (``user_profiles.id``; ``None`` = das System)."""
    if rows:
        db.execute(_PROCESS, {"rows": json_safe(rows)})


def seal_due(db: Session) -> int:
    """Siegelt jeden abgeschlossenen Tag, der noch keins hat (einer zur Zeit)."""
    return int(db.execute(text("SELECT log_seal_due()")).scalar_one())


def verify(db: Session) -> list[dict[str, Any]]:
    """Jeder versiegelte Tag: stimmt die Kette noch? ``redacted``: an dem Tag wurde
    geschwärzt (dann ist ``ok = False`` erklärt, nicht verdächtig)."""
    return [dict(r._mapping) for r in db.execute(text("SELECT * FROM log_verify()"))]


def tampered(db: Session) -> list[str]:
    """Tage, deren Siegel nicht mehr stimmt, ohne dass dort geschwärzt wurde."""
    return [str(r["day"]) for r in verify(db) if not r["ok"] and not r["redacted"]]


def redact(db: Session, object_id: int, reason: str) -> int:
    """Schwärzt Inhalt (Änderungen, Nutzlast) aller Einträge an einem Ding – Datenschutz.
    Die einzige erlaubte Änderung am Log; sie schreibt sich selbst ein (``log.redacted``)."""
    return int(db.execute(text("SELECT log_redact(:o, :r)"),
                          {"o": object_id, "r": reason}).scalar_one())
