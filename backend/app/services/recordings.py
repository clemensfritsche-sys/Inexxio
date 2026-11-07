"""►►► **Aufnehmen und Abschreiben** – EINE Stelle (Phase 4 · Sprache,
``docs/konzept/phase4-bauplan.md``). ◄◄◄

Gesprochenes wird Text, der Text wird eine **Erfassung** (``intake``) – danach ist alles wie beim
Schreiben (Phase 3). Vom Gesprochenen bleibt nur der Text.

* ``start`` → ``recording.start`` (am offenen Datensatz, sonst an der Person). Die Nummer der
  Aufnahme ist die Log-Id dieses Ereignisses.
* ``add_chunk`` – ein Stück (alle 30 s; ein **Abschnitt** = 5 Minuten = eine eigene Datei aus
  seinen Stücken in Reihenfolge). Bytes über ``attachments.put_object`` (eigener Bucket der
  Aufnahmen, sonst die Zeile – nie der Datei-Bucket), verzeichnet in ``recording_chunks``;
  dasselbe Stück zweimal ersetzt es.
* ``stop`` → ``recording.stop``. Ohne Stopp gilt eine Aufnahme, deren letztes Stück
  ``QUIET`` alt ist, als **abgebrochen** und wird wie gestoppt behandelt – was da ist, wird
  abgeschrieben.
* ``advance`` – so weit, wie die Zeit reicht (``ai.until``): je Abschnitt ``ai.transcribe`` →
  ``recording.segment``. Was sich nicht abschreiben lässt (kein Stück 0, zu gross, abgelehnt,
  zu oft gescheitert), wird **mit Vermerk übersprungen** – nie endlos versucht, nie still weg;
  ist alles abgeschrieben, **eine** Erfassung mit dem ganzen Text →
  ``recording.done`` → Stücke gelöscht; dann, wenn Zeit bleibt, legt die KI ab. Läuft in der
  Anfrage (die Oberfläche fragt nach) **und** im Takt (``due``).
* ``sweep`` (im Takt) – eine Aufnahme, die nach ``KEEP`` nicht fertig ist, wird mit dem, was
  abgeschrieben ist, die Erfassung (sonst ``recording.failed``); ihre Stücke gehen, und kein
  Stück bleibt länger als ``KEEP``.

**Nur die Person, die aufnimmt** (und der Admin) sieht ihre Aufnahme (``_may``); Stücke und
Stopp schickt nur sie. Die Ereignisse stehen nicht im Verlauf (``history.HIDDEN_EVENTS``).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from fastapi import HTTPException
from sqlalchemy import func, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from ..models import RecordingChunk, UserProfile
from ..schemas.recordings import Recording
from . import ai, attachments, intake, log, records

#: Ein Stück ist höchstens so gross (30 s Opus mit 24 kbit/s sind ~90 KB).
MAX_CHUNK = 4 * 1024 * 1024
#: Höchstens 3 Stunden = 36 Abschnitte à 5 Minuten; je Abschnitt 10 Stücke à 30 s (Luft bis 100).
MAX_SEGMENTS = 36
MAX_SEQ = 100
#: So lang ist ein Stück (``timeslice`` im Browser) und ein Abschnitt (``SEGMENT_MS``) – daraus
#: die ungefähre Länge. 5 Minuten: sicher in der Zeit eines Aufrufs, klein (≤ ~5 MB, auch wenn
#: Safari die Bitrate nicht einhält).
CHUNK_SECONDS = 30
SEGMENT_SECONDS = 300
#: Ohne Stopp und ohne neues Stück so lange → abgebrochen, wie gestoppt. Lang genug, dass ein
#: Netzloch die Aufnahme nicht schliesst, während der Browser noch aufnimmt.
QUIET = timedelta(minutes=30)
#: Spätestens dann ist das Audio weg; was nicht fertig ist, gilt als gescheitert.
KEEP = timedelta(hours=24)
#: Lehnt Gemini einen Abschnitt so oft ab, wird er mit Vermerk übersprungen.
TRIES = 2
#: Scheitert ein Abschnitt so oft ohne Ablehnung (Zeit, 5xx, 429, abgeschnitten), ebenso.
FAULTS = 6
#: Grösser wird ein Abschnitt nie an Gemini geschickt (Vertex nimmt inline höchstens ~20 MB).
MAX_AUDIO = 15 * 1024 * 1024
#: Einen Abschnitt nur beginnen, wenn noch so viele Sekunden bleiben – kein bezahlter Aufruf,
#: der sicher an der Zeitgrenze stirbt.
SEGMENT_LEAST = 40.0
#: Ablegen durch die KI erst, wenn noch so viel Zeit bleibt – sonst holt es der Takt nach.
FILE_LEAST = 20.0
#: «zu tun»: eine fehlgeschlagene Aufnahme steht so lange an der Person.
FAILED_DAYS = 7

NOTHING = "Nichts zu hören."
UNREADABLE = "Die Aufnahme liess sich nicht abschreiben."
TOO_OLD = "Nach einem Tag nicht abgeschrieben – das Audio ist gelöscht."
#: Die Vermerke eines übersprungenen Abschnitts (``recording.segment`` mit ``skipped``).
NO_CHUNKS = "keine Stücke angekommen"
NO_HEAD = "der Anfang fehlt – ohne ihn nicht lesbar"
TOO_BIG = "zu gross zum Abschreiben"
LATE = "nach einem Tag nicht abgeschrieben"
NO_TIME = "Keine Zeit mehr für diesen Abschnitt – es geht gleich weiter."
BUSY = "Diese Aufnahme wird gerade anderswo abgeschrieben – gleich noch einmal."
_END = ("recording.done", "recording.failed")
#: Der Namensraum der Sperre je Aufnahme (Advisory-Lock mit zwei Schlüsseln, wie der Takt).
LOCK_SPACE = 778_900


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ─── Lesen: eine Aufnahme aus dem Log und ihren Stücken ────────────────────────────────

@dataclass
class Rec:
    id: int
    at: datetime
    object_id: int
    actor_id: Optional[int]
    hint: Optional[int]
    mime: str
    #: Wo die Aufnahme ansetzt (die Stecknadel: Seite und Element) – steht vor dem Text.
    context: str = ""
    stop: Optional[dict[str, Any]] = None
    texts: dict[int, dict[str, Any]] = field(default_factory=dict)
    #: Je Abschnitt: wie oft Gemini ablehnte (``failures``) bzw. ohne Ablehnung scheiterte.
    failures: dict[int, int] = field(default_factory=dict)
    faults: dict[int, int] = field(default_factory=dict)
    end: Optional[tuple[str, dict[str, Any]]] = None
    #: Je Abschnitt die Zahl seiner Stücke; ``last`` = jüngstes Stück (oder der Start).
    chunks: dict[int, int] = field(default_factory=dict)
    last: Optional[datetime] = None

    @property
    def segments(self) -> int:
        known = [int((self.stop or {}).get("segments") or 0)]
        known += [s + 1 for s in self.chunks] + [s + 1 for s in self.texts]
        return max(known)

    def finished(self, now: datetime) -> bool:
        """Gestoppt – oder abgebrochen: seit ``QUIET`` kein Stück mehr."""
        return self.stop is not None or now - (self.last or self.at) >= QUIET

    def seconds_of(self, segment: int) -> int:
        if segment in self.texts:
            return int(self.texts[segment].get("seconds") or 0)
        return min(self.chunks.get(segment, 0) * CHUNK_SECONDS, SEGMENT_SECONDS)


_EVENTS = text("""
SELECT event, payload FROM log
 WHERE event IN ('recording.stop', 'recording.segment', 'recording.segment_failed',
                 'recording.done', 'recording.failed')
   AND (payload ->> 'recording')::bigint = :i ORDER BY id""")


def load(db: Session, rec_id: int) -> Rec:
    r = db.execute(text("SELECT id, at, object_id, actor_id, payload FROM log "
                        "WHERE id = :i AND event = 'recording.start'"), {"i": rec_id}).first()
    if r is None:
        raise HTTPException(404, detail=f"Aufnahme «{rec_id}» gibt es nicht.")
    p = r.payload or {}
    rec = Rec(id=r.id, at=r.at, object_id=r.object_id, actor_id=r.actor_id, hint=p.get("hint"),
              mime=str(p.get("mime") or ""), context=str(p.get("context") or ""))
    for e in db.execute(_EVENTS, {"i": rec_id}):
        body = e.payload or {}
        if e.event == "recording.stop" and rec.stop is None:
            rec.stop = body
        elif e.event == "recording.segment":
            rec.texts[int(body["segment"])] = body
        elif e.event == "recording.segment_failed":
            seg = int(body["segment"])
            count = rec.faults if body.get("fault") else rec.failures
            count[seg] = count.get(seg, 0) + 1
        elif e.event in _END:
            rec.end = (e.event, body)
    for seg, n, last in (db.query(RecordingChunk.segment, func.count(),
                                  func.max(RecordingChunk.updated_at))
                         .filter(RecordingChunk.recording == rec_id)
                         .group_by(RecordingChunk.segment)):
        rec.chunks[int(seg)] = int(n)
        rec.last = last if rec.last is None else max(rec.last, last)
    return rec


def _may(rec: Rec, viewer: UserProfile) -> bool:
    return viewer.role == "admin" or (rec.actor_id is not None and rec.actor_id == viewer.object_id)


def get(db: Session, rec_id: int, viewer: UserProfile) -> Rec:
    """Die Aufnahme, wenn ``viewer`` sie sehen darf – sonst gibt es sie für ihn nicht (404)."""
    rec = load(db, rec_id)
    if not _may(rec, viewer):
        raise HTTPException(404, detail=f"Aufnahme «{rec_id}» gibt es nicht.")
    return rec


def _own(db: Session, rec_id: int, actor: UserProfile) -> Rec:
    """Stücke und Stopp schickt nur, wer aufnimmt – auch ein Admin nicht für andere."""
    rec = get(db, rec_id, actor)
    if rec.actor_id != actor.object_id:
        raise HTTPException(403, detail=f"Aufnahme «{rec_id}» nimmt jemand anderes auf.")
    return rec


def state_of(rec: Rec, now: Optional[datetime] = None) -> str:
    if rec.end is not None:
        return "done" if rec.end[0] == "recording.done" else "failed"
    if not rec.finished(now or _now()):
        return "recording"
    return "transcribing" if len(rec.texts) < rec.segments else "filing"


def view(db: Session, rec: Rec, viewer: UserProfile, *, problem: Optional[str] = None) -> Recording:
    """►► **Eine Aufnahme, wie die Oberfläche sie zeigt** (``Recording``). ◄◄"""
    state = state_of(rec)
    found = None
    if rec.end is not None:
        problem = rec.end[1].get("problem") or problem
        iid = rec.end[1].get("intake")
        if iid and intake.may_see(db, int(iid), viewer):
            found = intake.view(db, intake.get(db, int(iid)))
    return Recording(id=rec.id, at=rec.at, hint_object_id=rec.hint, mime=rec.mime, state=state,
                     segments=rec.segments, transcribed=len(rec.texts),
                     seconds=sum(rec.seconds_of(s) for s in range(rec.segments)),
                     intake=found, problem=(problem or None) if state != "done" else None)


#: Ein Ende, das zählt: fertig – oder gescheitert, aber nicht bloss still («Nichts zu hören»,
#: Start und sofort Stopp). Was still endete, ist kein Fehlschlag: nicht in «zu tun», nicht im «+».
_SILENT = "coalesce((e.payload ->> 'silent')::boolean, false)"

_OPEN = text(f"""
SELECT s.id FROM log s
 WHERE s.event = 'recording.start' AND s.actor_id = :me
   AND NOT EXISTS (SELECT 1 FROM log e WHERE (e.payload ->> 'recording')::bigint = s.id
                     AND (e.event IN ('recording.done', 'recording.dismissed')
                          OR (e.event = 'recording.failed' AND (e.at < :since OR {_SILENT}))))
 ORDER BY s.id DESC LIMIT :n""")


def open_for(db: Session, actor: UserProfile, limit: int = 20) -> list[Recording]:
    """►► **Meine Aufnahmen, die nicht fertig sind** – und die in den letzten ``FAILED_DAYS``
    gescheiterten, mit Grund (nie still verloren); die neuesten zuerst. ◄◄"""
    since = _now() - timedelta(days=FAILED_DAYS)
    return [view(db, load(db, r.id), actor)
            for r in db.execute(_OPEN, {"me": actor.object_id, "n": limit, "since": since})]


# ─── Aufnehmen ─────────────────────────────────────────────────────────────────────────

def start(db: Session, hint: Optional[int], mime: str, actor: UserProfile,
          context: str = "") -> Rec:
    """►► **Eine Aufnahme beginnt** – ``recording.start`` am offenen Datensatz, sonst an der
    Person; ``context`` (die Stecknadel) steht später vor dem abgeschriebenen Text. ◄◄"""
    mime = (mime or "").strip()
    if not mime.lower().startswith("audio/"):
        raise HTTPException(400, detail=f"«{mime[:60]}» ist keine Tonaufnahme.")
    if hint is not None and records.labels(db, [hint]).get(hint) is None:
        raise HTTPException(400, detail=f"Datensatz «{hint}» gibt es nicht.")
    payload: dict[str, Any] = {"hint": hint, "mime": mime}
    if intake.clean(context or "").strip():
        payload["context"] = intake.clean(context).strip()
    rid = log.event(db, "recording.start", hint or actor.object_id, payload)
    return load(db, rid)


def dismiss(db: Session, rec_id: int, actor: UserProfile) -> Rec:
    """►► **Eine gescheiterte Aufnahme verwerfen** – sie verschwindet aus dem «+» (``recording.dismissed``);
    das Log behält sie. Nur, was gescheitert ist (was läuft, endet mit Stopp, was fertig ist, ist
    eine Erfassung und wird dort verworfen); zweimal ist einmal. ◄◄"""
    rec = get(db, rec_id, actor)
    if state_of(rec) != "failed":
        raise HTTPException(409, detail=f"Aufnahme «{rec_id}» ist nicht gescheitert – verwerfen geht "
                                        "nur dort.")
    gone = db.execute(text("SELECT 1 FROM log WHERE event = 'recording.dismissed' "
                           "AND (payload ->> 'recording')::bigint = :i"), {"i": rec_id}).first()
    if gone is None:
        log.event(db, "recording.dismissed", rec.object_id, {"recording": rec.id})
    return rec


def _open_for_more(rec: Rec) -> None:
    if rec.end is not None:
        word = "fertig" if rec.end[0] == "recording.done" else "aufgegeben"
        raise HTTPException(409, detail=f"Aufnahme «{rec.id}» ist schon {word}.")


def object_name(rec_id: int, segment: int, seq: int) -> str:
    return f"recordings/{rec_id}/{segment}-{seq}"


def add_chunk(db: Session, rec_id: int, segment: int, seq: int, raw: bytes,
              actor: UserProfile) -> Rec:
    """►► **Ein Stück** – höchstens ``MAX_CHUNK``, nur von der Person, die aufnimmt; dasselbe
    Stück zweimal ersetzt es (eines). Nach ``done``/``failed`` 409. ◄◄"""
    rec = _own(db, rec_id, actor)
    _open_for_more(rec)
    if not raw:
        raise HTTPException(400, detail=f"Stück {segment}-{seq} der Aufnahme «{rec_id}» ist leer.")
    if len(raw) > MAX_CHUNK:
        raise HTTPException(413, detail=f"Stück {segment}-{seq} der Aufnahme «{rec_id}» ist "
                                        f"grösser als 4 MB.")
    if not (0 <= segment < MAX_SEGMENTS and 0 <= seq < MAX_SEQ):
        raise HTTPException(400, detail=f"Stück {segment}-{seq} passt nicht in eine Aufnahme "
                                        f"(höchstens {MAX_SEGMENTS} Abschnitte à {MAX_SEQ} Stücke).")
    if segment in rec.texts:
        raise HTTPException(409, detail=f"Abschnitt {segment} der Aufnahme «{rec_id}» ist schon "
                                        f"abgeschrieben.")
    in_bucket = attachments.put_object(object_name(rec_id, segment, seq), raw, ai.audio_type(rec.mime))
    row = {"recording": rec_id, "segment": segment, "seq": seq, "byte_size": len(raw),
           "data": None if in_bucket else raw, "is_active": True,
           "created_at": _now(), "updated_at": _now()}
    stmt = insert(RecordingChunk).values(**row)
    db.execute(stmt.on_conflict_do_update(
        constraint="uq_recording_chunks_piece",
        set_={"byte_size": stmt.excluded.byte_size, "data": stmt.excluded.data,
              "updated_at": stmt.excluded.updated_at}))
    return load(db, rec_id)


def stop(db: Session, rec_id: int, segments: int, actor: UserProfile) -> Rec:
    """►► **Stopp** – ``recording.stop`` mit der Zahl der Abschnitte; ein zweiter Stopp ändert
    nichts. ◄◄"""
    rec = _own(db, rec_id, actor)
    if rec.end is not None or rec.stop is not None:
        return rec
    if not 0 <= segments <= MAX_SEGMENTS:
        raise HTTPException(400, detail=f"Aufnahme «{rec_id}» kann nicht {segments} Abschnitte haben.")
    log.event(db, "recording.stop", rec.object_id, {"recording": rec_id, "segments": segments})
    return load(db, rec_id)


# ─── Abschreiben ───────────────────────────────────────────────────────────────────────

class _Skip(Exception):
    """Ein Abschnitt, der sich nicht abschreiben lässt – der Grund wird sein Vermerk."""


def _assemble(db: Session, rec_id: int, segment: int) -> bytes:
    """►► **Ein Abschnitt als eine Datei** – seine Stücke in Reihenfolge. Fehlt eines mitten
    drin, wird trotzdem abgeschrieben, was da ist. ``_Skip``, ohne Gemini zu fragen: kein Stück,
    kein Stück 0 (ohne den Kopf ist die Datei nicht lesbar), grösser als ``MAX_AUDIO``. ◄◄"""
    rows = (db.query(RecordingChunk.seq, RecordingChunk.byte_size)
            .filter(RecordingChunk.recording == rec_id, RecordingChunk.segment == segment)
            .order_by(RecordingChunk.seq).all())
    if not rows:
        raise _Skip(NO_CHUNKS)
    if rows[0].seq != 0:
        raise _Skip(NO_HEAD)
    if sum(r.byte_size for r in rows) > MAX_AUDIO:
        raise _Skip(TOO_BIG)
    parts = []
    for seq, data in (db.query(RecordingChunk.seq, RecordingChunk.data)
                      .filter(RecordingChunk.recording == rec_id, RecordingChunk.segment == segment)
                      .order_by(RecordingChunk.seq)):
        raw = bytes(data) if data is not None else attachments.get_object(object_name(rec_id, segment, seq))
        if raw:
            parts.append(raw)
    if not parts:
        raise _Skip(NO_CHUNKS)
    return b"".join(parts)


def _segment(db: Session, rec: Rec, segment: int, payload: dict[str, Any]) -> None:
    log.event(db, "recording.segment", rec.object_id,
              {"recording": rec.id, "segment": segment, "seconds": rec.seconds_of(segment), **payload})


def _transcribe(db: Session, rec: Rec, segment: int, person: UserProfile) -> Optional[str]:
    """Einen Abschnitt abschreiben → ``recording.segment``. Gibt zurück, warum es (noch) nicht
    ging – oder ``None``. Übersprungen mit Vermerk: was ``_assemble`` nicht schickt, was Gemini
    ``TRIES``-mal ablehnt, was ``FAULTS``-mal ohne Ablehnung scheitert (Zeit, 5xx, 429,
    abgeschnitten). Nicht gezählt: Deckel, Einrichtung, keine Zeit – das geht später wieder."""
    try:
        raw = _assemble(db, rec.id, segment)
    except _Skip as skip:
        _segment(db, rec, segment, {"text": "", "skipped": str(skip)})
        return None
    except HTTPException as exc:
        return str(exc.detail)
    spoken = ai.transcribe(db, raw, rec.mime, actor=person, seconds=rec.seconds_of(segment))
    if spoken is not None:
        _segment(db, rec, segment, {"text": spoken})
        return None
    trouble = ai.problem() or UNREADABLE
    fault = ai.faulted()
    if ai.refused() or fault:
        log.event(db, "recording.segment_failed", rec.object_id,
                  {"recording": rec.id, "segment": segment, "problem": trouble, "fault": fault})
        tried, most = (rec.faults, FAULTS) if fault else (rec.failures, TRIES)
        if tried.get(segment, 0) + 1 >= most:
            _segment(db, rec, segment, {"text": "", "skipped": trouble})
            return None
    return trouble


def _end(db: Session, rec: Rec, event: str, payload: dict[str, Any]) -> None:
    """Das Ende einer Aufnahme – und ihre Stücke gehen (Zeilen jetzt, Bucket nach dem Commit)."""
    log.event(db, event, rec.object_id, {"recording": rec.id, **payload})
    db.query(RecordingChunk).filter(RecordingChunk.recording == rec.id).delete(
        synchronize_session=False)
    attachments.drop_objects(db, f"recordings/{rec.id}/")


def _whole(rec: Rec) -> str:
    """Der ganze Text in der Reihenfolge der Abschnitte; **jede Lücke als Vermerk**
    «[Abschnitt n: Grund]» – auch «keine Stücke angekommen»: man sieht, wo etwas fehlt."""
    out = [rec.context] if rec.context else []
    for s in range(rec.segments):
        t = rec.texts.get(s) or {"skipped": NO_CHUNKS}
        if (t.get("text") or "").strip():
            out.append(t["text"].strip())
        elif t.get("skipped"):
            out.append(f"[Abschnitt {s + 1}: {str(t['skipped']).rstrip('.')}]")
    return "\n\n".join(out)


def _finish(db: Session, rec: Rec, person: UserProfile) -> Optional[str]:
    """Alles abgeschrieben → **eine** Erfassung (im Namen der Person) → ``recording.done`` →
    Stücke weg; dann, wenn Zeit bleibt, legt die KI ab (sonst der Takt, ``intake.catch_up``).
    Ohne jeden Text: ``recording.failed`` – war nur nichts zu hören (keine Stücke, Stille), ist
    das ``silent`` und kein Fehlschlag."""
    if not any((t.get("text") or "").strip() for t in rec.texts.values()):
        refused = any(t.get("skipped") and t["skipped"] != NO_CHUNKS for t in rec.texts.values())
        _end(db, rec, "recording.failed",
             {"problem": UNREADABLE} if refused else {"problem": NOTHING, "silent": True})
        db.commit()
        return None
    hint = rec.hint if rec.hint and records.labels(db, [rec.hint]).get(rec.hint) else None
    it = intake.capture(db, _whole(rec), hint, person, recording=rec.id)
    _end(db, rec, "recording.done", {"intake": it.id})
    db.commit()
    if ai.available(db) and ai.remaining(60) >= FILE_LEAST:
        trouble = intake.file_with_ai(db, it, person)
        db.commit()
        return trouble
    return None


def _lock(rec_id: int):
    """Die Sperre je Aufnahme auf einer **eigenen** Verbindung (über Commits hinweg) – ``None``,
    wenn Anfrage oder Takt sie gerade halten."""
    from ..core.database import engine
    con = engine.connect()
    try:
        got = con.execute(text("SELECT pg_try_advisory_lock(:s, :k)"),
                          {"s": LOCK_SPACE, "k": rec_id & 0x7FFF_FFFF}).scalar()
        con.commit()
    except BaseException:
        con.invalidate()             # nie eine Verbindung mit halber Sperre in den Pool
        con.close()
        raise
    if got:
        return con
    con.close()
    return None


def _unlock(con, rec_id: int) -> None:
    try:
        con.execute(text("SELECT pg_advisory_unlock(:s, :k)"),
                    {"s": LOCK_SPACE, "k": rec_id & 0x7FFF_FFFF})
        con.commit()
    except Exception:       # noqa: BLE001 – die Verbindung nie mit der Sperre zurückgeben
        con.invalidate()
    finally:
        con.close()


def advance(db: Session, rec_id: int) -> Optional[str]:
    """►►► **So weit, wie die Zeit reicht** – Abschnitte der Reihe nach abschreiben, dann die
    Erfassung. Gibt zurück, warum es (noch) nicht weitergeht, oder ``None``. Committet je
    Schritt: was abgeschrieben ist, bleibt. Läuft in der Anfrage und im Takt; nie zweimal
    gleichzeitig an derselben Aufnahme (``_lock``). ◄◄◄"""
    con = _lock(rec_id)
    if con is None:
        return BUSY
    try:
        rec = load(db, rec_id)
        if rec.end is not None or not rec.finished(_now()):
            return None
        person = db.query(UserProfile).filter(UserProfile.object_id == rec.actor_id).first()
        if person is None:
            _end(db, rec, "recording.failed", {"problem": "Die Person, die aufnahm, gibt es nicht."})
            db.commit()
            return None
        for segment in range(rec.segments):
            if segment in rec.texts:
                continue
            if ai.remaining(60) < SEGMENT_LEAST:
                return NO_TIME
            trouble = _transcribe(db, rec, segment, person)
            db.commit()
            if trouble:
                return trouble
        return _finish(db, load(db, rec_id), person)
    finally:
        _unlock(con, rec_id)


# ─── Der Takt ──────────────────────────────────────────────────────────────────────────

_DUE = text("""
SELECT s.id FROM log s
 WHERE s.event = 'recording.start' AND s.at >= :since
   AND NOT EXISTS (SELECT 1 FROM log e WHERE e.event IN ('recording.done', 'recording.failed')
                     AND (e.payload ->> 'recording')::bigint = s.id)
   AND (EXISTS (SELECT 1 FROM log t WHERE t.event = 'recording.stop'
                  AND (t.payload ->> 'recording')::bigint = s.id)
        OR greatest(s.at, (SELECT max(c.updated_at) FROM recording_chunks c
                            WHERE c.recording = s.id)) <= :quiet)
 ORDER BY (SELECT max(f.id) FROM log f WHERE f.event = 'recording.segment_failed'
            AND (f.payload ->> 'recording')::bigint = s.id) ASC NULLS FIRST, s.id
 LIMIT :n""")


def due(db: Session, limit: int = 10) -> list[int]:
    """Aufnahmen, die gestoppt oder abgebrochen und nicht fertig sind – die ältesten zuerst;
    wer zuletzt scheiterte, nach hinten (eine schwierige hält die übrigen nicht auf)."""
    now = _now()
    return [r.id for r in db.execute(_DUE, {"since": now - KEEP, "quiet": now - QUIET, "n": limit})]


_STALE = text("""
SELECT s.id FROM log s
 WHERE s.event = 'recording.start' AND s.at < :cut
   AND NOT EXISTS (SELECT 1 FROM log e WHERE e.event IN ('recording.done', 'recording.failed')
                     AND (e.payload ->> 'recording')::bigint = s.id)
 ORDER BY s.id""")


def _rescue(db: Session, rec: Rec) -> bool:
    """►► **Was nach einem Tag schon abgeschrieben ist, geht nicht verloren**: es wird die
    Erfassung, der Rest ein Vermerk «[Abschnitt n: nach einem Tag nicht abgeschrieben]». Ohne jeden Text →
    ``recording.failed``. ``True``, wenn eine Erfassung entstand. ◄◄"""
    if rec.end is not None:
        return True
    person = db.query(UserProfile).filter(UserProfile.object_id == rec.actor_id).first()
    if person is None or not any((t.get("text") or "").strip() for t in rec.texts.values()):
        _end(db, rec, "recording.failed", {"problem": TOO_OLD})
        return False
    for s in range(rec.segments):
        rec.texts.setdefault(s, {"skipped": LATE})
    hint = rec.hint if rec.hint and records.labels(db, [rec.hint]).get(rec.hint) else None
    it = intake.capture(db, _whole(rec), hint, person, recording=rec.id)
    _end(db, rec, "recording.done", {"intake": it.id, "partial": True})
    return True


def sweep(db: Session) -> dict[str, int]:
    """►► **Aufräumen**: eine Aufnahme, die nach ``KEEP`` nicht fertig ist → ``recording.failed``
    mit Grund (ihre Stücke gehen mit); jedes Stück, das älter ist als ``KEEP``, geht auch. ◄◄"""
    cut = _now() - KEEP
    failed = 0
    for r in db.execute(_STALE, {"cut": cut}).all():
        con = _lock(r.id)
        if con is None:
            continue                       # wird gerade abgeschrieben – im nächsten Lauf
        try:
            failed += 0 if _rescue(db, load(db, r.id)) else 1
            db.commit()                    # fest, bevor die Sperre fällt
        except BaseException:
            db.rollback()
            raise
        finally:
            _unlock(con, r.id)
    old = sorted({rid for (rid,) in db.query(RecordingChunk.recording)
                  .filter(RecordingChunk.updated_at < cut).distinct()})
    for rid in old:
        db.query(RecordingChunk).filter(RecordingChunk.recording == rid).delete(
            synchronize_session=False)
        attachments.drop_objects(db, f"recordings/{rid}/")
    db.commit()
    return {"failed": failed, "dropped": len(old)}


# ─── «zu tun» ──────────────────────────────────────────────────────────────────────────

