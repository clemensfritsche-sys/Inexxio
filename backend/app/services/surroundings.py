"""►►► **Das Umfeld eines Datensatzes – abgeleitet, nie gepflegt.** ◄◄◄ (Phase 5 §8.1)

Was zu einem Ding gehört, steht schon im Log, das die Datenbank selbst schreibt: was **in
derselben Handlung** mit ihm geschah (ein Auftrag und seine Stücke, eine Notiz und ihr
Datensatz, eine Person und ihre Firma beim Anlegen), und auf welche Datensätze seine eigenen
Zeilen zeigen (``…object_id`` in den geänderten Werten). Das ist **eine Stufe** – keine Liste von
Beziehungen, die jemand pflegt; kommt eine Tabelle dazu, gehört sie von selbst dazu.

* ``of`` – die Nummern des Umfelds (mit dem Datensatz selbst), die jüngsten zuerst, höchstens
  ``LIMIT``.
* ``mark`` – die jüngste Änderung im Umfeld (eine Log-Id): **hat sich etwas geändert?** ist ein
  Vergleich mit der Marke vom letzten Mal – eine Abfrage über den Index ``ix_log_object_at``.
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

#: So viele Nachbarn höchstens – nicht ausufern, nicht zu klein.
LIMIT = 50
#: So viele Handlungen am Datensatz werden angesehen (die jüngsten).
HANDLINGS = 200
#: Ereignisse, die keine Änderung am Ding sind (Lesen, die KI selbst, Gespräche).
QUIET = ("pin", "ai.call", "talk", "talk.failed", "handgriff", "handgriff.done",
         "handgriff.dropped", "document.read", "document.viewed", "voucher.viewed")

_OF = text("""
WITH mine AS (
    SELECT request_id, changes FROM log WHERE object_id = :o ORDER BY id DESC LIMIT :h
), together AS (
    SELECT l.object_id, max(l.id) AS last FROM log l
     WHERE l.request_id IN (SELECT request_id FROM mine)
       AND l.object_id IS NOT NULL AND l.object_id <> :o
     GROUP BY l.object_id
), pointed AS (
    SELECT DISTINCT (regexp_matches(e.value, '[0-9]{9}', 'g'))[1]::bigint AS object_id
      FROM mine m, jsonb_each_text(coalesce(m.changes, '{}'::jsonb)) e
     WHERE e.key LIKE '%object_id'
)
SELECT object_id FROM (
    SELECT object_id, last FROM together
    UNION
    SELECT p.object_id, 0 FROM pointed p WHERE p.object_id <> :o
       AND EXISTS (SELECT 1 FROM objects x WHERE x.object_id = p.object_id)
) u
 GROUP BY object_id ORDER BY max(last) DESC LIMIT :n""")

_MARK = text("""
SELECT coalesce(max(id), 0) FROM log
 WHERE object_id = ANY(:ids) AND NOT (coalesce(event, '') = ANY(:quiet))""")


def of(db: Session, object_id: int, limit: int = LIMIT) -> list[int]:
    """Der Datensatz und sein Umfeld (eine Stufe), die jüngsten zuerst."""
    near = [int(r.object_id) for r in db.execute(_OF, {"o": object_id, "h": HANDLINGS,
                                                         "n": limit})]
    return [object_id, *near]


def mark(db: Session, ids: list[int]) -> int:
    """Die jüngste Änderung im Umfeld – größer als beim letzten Mal heisst: geändert."""
    return int(db.execute(_MARK, {"ids": ids, "quiet": list(QUIET)}).scalar() or 0)
