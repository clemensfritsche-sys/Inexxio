"""►►► **Der Takt** – was nicht davon abhängen darf, dass irgendwo ein Browser offen ist. ◄◄◄

Cloud Scheduler ruft alle 5 Minuten, Tag und Nacht, ``POST /api/v1/internal/tick``
(``routers/internal``, Anmeldung ``core/oidc``; eingerichtet im Deploy, ``infra/README.md``).
Was er tut, steht **an dieser einen Stelle**: ``TASKS``, eine Liste von Aufgaben. Für jede gilt:

* **eigene Sitzung, eigene Transaktion** – das System handelt (``system_session("job")``);
* **wiederholbar** – ein zweiter Lauf direkt danach findet nichts mehr zu tun;
* **einzeln gesperrt** – ein Advisory-Lock je Aufgabe (``pg_try_advisory_lock``, auf einer
  eigenen Verbindung, über Commits hinweg): läuft sie gerade anderswo, wird sie
  **übersprungen**, nicht verdoppelt;
* **mit Zeitgrenze** – nach ``START_WITHIN`` Sekunden beginnt keine Aufgabe und kein Schritt
  mehr; ein angefangener Schritt ist durch die Zeitgrenzen seiner Abrufe (höchstens 30 s)
  begrenzt. So bleibt der Lauf unter der Anfrage-Grenze von Cloud Run (60 s);
* **ein Fehlschlag hält die übrigen nicht auf** – er wird gemeldet (Antwort und Cloud
  Logging), die nächste Aufgabe läuft.

**Was eine Aufgabe getan hat, steht im Log** (Ereignis ``tick.<name>`` mit den Zahlen) –
nichts, wenn nichts geschah: 288 Läufe am Tag füllen das Log nicht mit Leerlauf.
"""

import time
import traceback
import zlib
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from sqlalchemy import text

from ..core.actor import system_session

#: Danach beginnt der Takt nichts Neues mehr (Sekunden ab Beginn des Laufs).
START_WITHIN = 20.0
#: Bis dahin muss auch die KI fertig sein (Sekunden ab Beginn) – Cloud Scheduler wartet 60 s.
FINISH_WITHIN = 50.0

#: Der Namensraum der Sperren des Takts (erste Hälfte des Advisory-Locks mit zwei Schlüsseln).
LOCK_SPACE = 778_899


@dataclass(frozen=True)
class Task:
    """Eine Aufgabe: ``run(db, deadline)`` gibt zurück, was sie getan hat (Zahlen für das
    Log) – oder nichts (leer / ``None``), wenn es nichts zu tun gab."""
    name: str
    run: Callable[[Any, float], Optional[dict[str, int]]]


@dataclass
class Outcome:
    name: str
    state: str                          # ok · skipped · failed
    detail: Optional[str] = None
    done: dict[str, int] = field(default_factory=dict)


def _seal(db, deadline: float) -> dict[str, int]:
    """Das Siegel des Logs: jeder abgeschlossene Tag, der noch keins hat."""
    from . import log
    return {"days": log.seal_due(db)}


def _mail(db, deadline: float) -> dict[str, int]:
    """Die Postfächer abgleichen und Fälliges senden (``mailbox.sync_all``) – dasselbe wie
    das offene ERP (``POST /erp/messages/sync``), nur ohne Browser."""
    from . import mailbox
    new, sent = mailbox.sync_all(db, deadline=deadline)
    return {"new": new, "sent": sent}


#: So viele Einträge ohne Bedeutungs-Zahlen holt ein Lauf nach.
MEMORY_PER_RUN = 20


def _ai(db, deadline: float) -> dict[str, int]:
    """**Die KI im Takt** (Phase 5): Gespräche nachholen, auf die sie nicht antwortete · neue
    Mails auf ihre Folgen prüfen (Handgriffe am Datensatz) · fehlende Bedeutungs-Zahlen (Fälle,
    Notizen, Dokumente – «im Wissen suchen»; braucht nur Vertex). Jeder Schritt speichert für
    sich – ein Ausfall der KI nimmt das Getane nicht zurück."""
    import time as _t
    from . import ai
    with ai.until(deadline - _t.monotonic() + FINISH_WITHIN - START_WITHIN):
        return _ai_steps(db, deadline)


def _ai_steps(db, deadline: float) -> dict[str, int]:
    import time as _t
    from . import ai, follow, memory, talk
    done: dict[str, int] = {}
    if ai.available(db) and _t.monotonic() < deadline:
        done["answered"] = talk.catch_up(db, deadline)
    if ai.available(db) and _t.monotonic() < deadline:
        done["mails"], done["handgriffe"] = follow.run(db, deadline)
        db.commit()
    if _t.monotonic() < deadline:          # Bedeutungs-Zahlen brauchen nur Vertex
        done["remembered"] = memory.catch_up(db, deadline, MEMORY_PER_RUN)
    return {k: v for k, v in done.items() if v}


#: So viele Aufnahmen schaut ein Lauf höchstens an (jede nur, solange Zeit ist).
VOICE_PER_RUN = 10


def _voice(db, deadline: float) -> dict[str, int]:
    """**Aufnahmen ohne Browser zu Ende bringen** (Phase 4): zuerst aufräumen (braucht keine KI,
    läuft immer – kein Audio bleibt länger als einen Tag), dann gestoppte oder abgebrochene
    Aufnahmen abschreiben und erfassen, solange Zeit ist (``recordings.advance`` committet je
    Schritt)."""
    import time as _t
    from . import ai, recordings
    done = recordings.sweep(db)
    db.commit()
    with ai.until(deadline - _t.monotonic() + FINISH_WITHIN - START_WITHIN):
        for rid in recordings.due(db, VOICE_PER_RUN):
            if _t.monotonic() >= deadline:
                break
            recordings.advance(db, rid)
            if recordings.load(db, rid).end is not None:
                done["finished"] = done.get("finished", 0) + 1
    return done


def _loop(db, deadline: float) -> dict[str, int]:
    """**Wiederkehrende Aufträge** (``services/loop``): je fälligem Auftrag ohne Nachfolger den
    Nachfolger anlegen – wenn nichts fehlt; sonst wartet er (der Grund steht in «zu tun»).
    Jeder in eigener Transaktion: eine Kette, die scheitert, hält die anderen nicht auf. Fehlt
    die Zeit, nimmt der nächste Lauf den Rest – keine Periode geht verloren."""
    import time as _t
    from . import loop
    done: dict[str, int] = {}
    for order in loop.due(db):
        if _t.monotonic() >= deadline:
            break
        try:
            if loop.create_next(db, order) is not None:
                done["created"] = done.get("created", 0) + 1
            db.commit()
        except Exception as exc:        # noqa: BLE001 – gemeldet, die nächste Kette läuft
            db.rollback()
            done["failed"] = done.get("failed", 0) + 1
            print(f"ERROR: TICK loop {order.object_id}: {exc!r}", flush=True)
    return done


#: ►► **Die Aufgaben des Takts, in dieser Reihenfolge.** Das Siegel zuerst: es dauert
#:    Millisekunden und darf nie hinter einem langsamen Postfach warten. Dann die
#:    Wiederholungen (``loop``): reine Datenbank-Arbeit, ein Nachfolger ist fällig ab
#:    Tagesbeginn und soll nicht hinter Gmail oder der KI warten. Dann die Aufnahmen
#:    (``voice``): eine eigene Aufgabe mit eigener Sperre – das Aufräumen läuft auch, wenn die KI
#:    scheitert, und ein Mensch wartet auf seinen Text; vor der KI, weil ein langes Ablegen oder
#:    Folgen sonst jeden Lauf die Zeit nähme. Die KI zuletzt: sie braucht am längsten, wartet auf
#:    die Mails, die der Abgleich eben holte, und legt ab, was ``voice`` eben erfasste.
TASKS: tuple[Task, ...] = (
    Task("seal", _seal),
    Task("loop", _loop),
    Task("mail", _mail),
    Task("voice", _voice),
    Task("ai", _ai),
)


def lock_key(name: str) -> int:
    """Der Schlüssel der Sperre einer Aufgabe – aus ihrem Namen, also für immer derselbe."""
    return zlib.crc32(f"tick:{name}".encode()) & 0x7FFF_FFFF


def _acquire(name: str):
    """Die Sperre auf einer **eigenen** Verbindung – ``None``, wenn sie gerade jemand hält.
    (Eine Sitzung gibt ihre Verbindung beim Commit zurück; die Sperre bliebe dann an einer
    fremden Verbindung im Pool hängen.)"""
    from ..core.database import engine
    con = engine.connect()
    try:
        got = con.execute(text("SELECT pg_try_advisory_lock(:s, :k)"),
                          {"s": LOCK_SPACE, "k": lock_key(name)}).scalar()
        con.commit()
    except Exception:
        con.close()
        raise
    if got:
        return con
    con.close()
    return None


def _release(con, name: str) -> None:
    try:
        con.execute(text("SELECT pg_advisory_unlock(:s, :k)"),
                    {"s": LOCK_SPACE, "k": lock_key(name)})
        con.commit()
    except Exception:       # noqa: BLE001 – die Verbindung nie mit der Sperre zurückgeben
        con.invalidate()
    finally:
        con.close()


def _counts(done: Optional[dict[str, Any]]) -> dict[str, int]:
    """Nur, was geschah – Zahlen über null."""
    return {k: int(v) for k, v in (done or {}).items() if v}


def _one(task: Task, deadline: float) -> Outcome:
    """Eine Aufgabe: sperren, in eigener Sitzung laufen, Getanes ins Log, freigeben."""
    con = _acquire(task.name)
    if con is None:
        return Outcome(task.name, "skipped", "Läuft gerade anderswo.")
    db = system_session("job")
    try:
        done = _counts(task.run(db, deadline))
        if done:
            from . import log
            log.event(db, f"tick.{task.name}", None, done)
        db.commit()
        return Outcome(task.name, "ok", done=done)
    except Exception as exc:        # noqa: BLE001 – gemeldet, die nächste Aufgabe läuft
        db.rollback()
        print(f"ERROR: TICK {task.name} failed: {exc!r}\n{traceback.format_exc()}",
              flush=True)
        return Outcome(task.name, "failed", f"{type(exc).__name__}: {exc}"[:300])
    finally:
        db.close()
        _release(con, task.name)


def run(tasks: Optional[tuple[Task, ...]] = None,
        start_within: float = START_WITHIN) -> list[Outcome]:
    """**Ein Lauf des Takts** – jede Aufgabe einmal, keine hält die anderen auf."""
    tasks = TASKS if tasks is None else tasks
    deadline = time.monotonic() + start_within
    out: list[Outcome] = []
    for task in tasks:
        if time.monotonic() >= deadline:
            out.append(Outcome(task.name, "skipped", "Keine Zeit mehr in diesem Lauf."))
            continue
        try:
            out.append(_one(task, deadline))
        except Exception as exc:    # noqa: BLE001 – auch die Sperre selbst kann scheitern
            print(f"ERROR: TICK {task.name} not started: {exc!r}", flush=True)
            out.append(Outcome(task.name, "failed", f"{type(exc).__name__}: {exc}"[:300]))
    return out
