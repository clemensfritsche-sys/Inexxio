"""►►► **Spam aus dem Formular der Website – aussortiert, nicht gelöscht.** ◄◄◄

Jede Anfrage liest zuerst die KI (das schnelle Modell, ``ai.TASKS["screen"]``, Bruchteile eines
Rappens). Hält sie die Anfrage für Spam, entsteht **nichts**: keine Person, keine Nachricht,
keine Bestätigung (sie ginge an eine oft fremde Adresse und schadete dem Ruf des Postfachs). Die
Anfrage steht dann als Ereignis im Log (``inquiry.held``) an der Gesellschaft, die sie bekommen
hätte – dort, in ihrer Kommunikation, unter «Aussortiert», und als Aufgabe («zu tun»), bis ein
Mensch entscheidet:

* **Kein Spam** (``release``) – die Anfrage wird angelegt, als wäre sie eben gekommen
  (``inquiry.record``, dieselbe Stelle), samt Bestätigung → ``inquiry.released``;
* **Spam** (``discard``) → ``inquiry.discarded``.

**Wer schon aussortiert ist, bleibt aussortiert** (``seen``, vor der KI): dieselbe E-Mail oder
derselbe Name mit derselben Firma wie eine aussortierte Anfrage ohne «Kein Spam».

Je aussortierter Anfrage genau ein Entscheid (Sperre + eindeutiger Index
``ix_log_inquiry_decided``). **Im Zweifel kein Spam**: fällt die KI aus, ist der Deckel erreicht
oder ist die Antwort unbrauchbar, geht die Anfrage normal durch – eine echte Anfrage geht nie
verloren. Offen ist abgeleitet (aussortiert, ohne Entscheid), nie gespeichert.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..core import clock, locks, report
from ..domain.errors import Conflict, NotFound
from . import ai, inquiry, log, sites

HELD, RELEASED, DISCARDED = "inquiry.held", "inquiry.released", "inquiry.discarded"

#: ►►► **Die Anleitung der KI** – was Spam ist und was nicht. Im Zweifel: kein Spam. ◄◄◄
SYSTEM = """Du liest eine Anfrage aus dem Kontaktformular der Website von INEXXIO, einem
kleinen Schweizer Unternehmen für Kranbau, Fahrzeugbau, Speziallösungen und Service.

Beurteile als Ganzes – mit allen Angaben (Name, E-Mail, Firma, Telefon, Seite, Sprache,
Nachricht) –, ob hier ein Mensch mit einem echten Anliegen an uns schreibt, oder ob es Spam
ist: Werbung an uns, eine Massen- oder Bot-Nachricht ohne Bezug zu uns.

Im Zweifel ist es kein Spam – eine echte Anfrage zu verlieren ist schlimmer, als Spam
durchzulassen. Antworte in der verlangten Form; der Grund ist ein kurzer deutscher Satz."""


class Verdict(BaseModel):
    spam: bool = Field(description="Ist die Anfrage Spam? Im Zweifel false.")
    reason: str = Field(default="", description="Ein kurzer deutscher Satz, warum.")


def _prompt(inq: inquiry.Inquiry) -> str:
    lines = [f"Name: {inq.name}", f"E-Mail: {inq.email}", f"Firma: {inq.company or '–'}",
             f"Telefon: {inq.phone or '–'}", f"Seite: {inq.source}", f"Sprache der Seite: {inq.lang}",
             f"Fotos: {len(inq.photos)}", "", "Nachricht:", inq.message]
    return "\n".join(lines)


#: ►►► **Wer schon aussortiert ist, bleibt aussortiert** – dieselbe E-Mail oder (mit Firma)
#: derselbe Name mit derselben Firma wie eine aussortierte Anfrage, über die niemand «Kein Spam»
#: sagte. Eine feste Regel vor der KI: die KI urteilt nicht jedes Mal gleich, und ein Bot schickt
#: dasselbe dutzendfach. Verloren geht nichts – die Anfrage steht unter «Aussortiert». ◄◄◄
_SEEN = f"""SELECT h.at FROM log h
 WHERE h.event = '{HELD}'
   AND (lower(btrim(h.payload ->> 'email')) = :email
        OR (:firm <> '' AND lower(regexp_replace(btrim(h.payload ->> 'company'), '\\s+', ' ', 'g')) = :firm
            AND lower(regexp_replace(btrim(h.payload ->> 'name'), '\\s+', ' ', 'g')) = :name))
   AND NOT EXISTS (SELECT 1 FROM log d WHERE d.event = '{RELEASED}'
                   AND (d.payload ->> 'held')::bigint = h.id)
 ORDER BY h.at DESC LIMIT 1"""


def _key(value: Optional[str]) -> str:
    return " ".join((value or "").split()).lower()


def seen(db: Session, inq: inquiry.Inquiry) -> Optional[str]:
    """►► **Schon einmal aussortiert?** – der Grund, oder ``None`` (``_SEEN``). ◄◄"""
    email = _key(inq.email)
    if not email:
        return None
    at = db.execute(text(_SEEN), {"email": email, "firm": _key(inq.company),
                                  "name": _key(inq.name)}).scalar()
    if at is None:
        return None
    return f"Wie die aussortierte Anfrage vom {clock.day(at)} (gleicher Absender)."


def screen(db: Session, inq: inquiry.Inquiry) -> Optional[str]:
    """►► **Ist das Spam?** – der Grund, oder ``None`` (kein Spam, oder die KI weiss es nicht). ◄◄
    Zuerst die feste Regel (``seen``), dann die KI. Nie eine Ausnahme: ohne KI geht jede Anfrage
    durch, ausser ihr Absender ist schon aussortiert."""
    again = seen(db, inq)
    if again:
        return again
    try:
        found = ai.ask(db, task="screen", actor=None, system=SYSTEM, schema=Verdict,
                       content=[{"type": "text", "text": _prompt(inq)}])
    except Exception:       # die Tür wirft nie – und wenn doch, entscheidet sie nicht über eine Anfrage
        return None
    if found is None or not found.spam:
        return None
    return " ".join((found.reason or "Spam").split())[:300]


def hold(db: Session, inq: inquiry.Inquiry, country: Optional[str], reason: str) -> int:
    """Aussortieren: die Anfrage als Ereignis an der Gesellschaft, die sie bekommen hätte –
    mit allem, was «Kein Spam» braucht (die Fotos liegen schon im Korb)."""
    firm = inquiry.company_for(db, country)
    payload = {"name": inq.name, "email": inq.email, "message": inq.message, "phone": inq.phone,
               "company": inq.company, "source": inq.source, "newsletter": inq.newsletter,
               "lang": inq.lang, "files": inquiry.store_photos(db, inq), "reason": reason}
    return log.event(db, HELD, firm.object_id, payload)


@dataclass(frozen=True)
class Held:
    id: int
    at: datetime
    company: int
    payload: dict[str, Any]


_OPEN = f"""SELECT h.id, h.at, h.object_id, h.payload FROM log h
 WHERE h.event = '{HELD}' {{where}}
   AND NOT EXISTS (SELECT 1 FROM log d WHERE d.event IN ('{RELEASED}', '{DISCARDED}')
                   AND (d.payload ->> 'held')::bigint = h.id)
 ORDER BY h.at DESC, h.id DESC"""


def open_held(db: Session, company: Optional[int] = None) -> list[Held]:
    """►► **Aussortiert, ohne Entscheid** – je Gesellschaft oder alle (für «zu tun»). ◄◄"""
    where = "AND h.object_id = :c" if company is not None else ""
    rows = db.execute(text(_OPEN.format(where=where)), {"c": company}).all()
    return [Held(id=r[0], at=r[1], company=r[2], payload=r[3] or {}) for r in rows]


def _one(db: Session, held_id: int) -> Held:
    locks.xact(db, locks.SPAM, locks.key(held_id))
    row = db.execute(text("SELECT id, at, object_id, payload FROM log WHERE id = :i AND event = :e"),
                     {"i": held_id, "e": HELD}).first()
    if row is None:
        raise NotFound(f"Eine aussortierte Anfrage «{held_id}» gibt es nicht.")
    decided = db.execute(text(
        "SELECT event FROM log WHERE event IN (:r, :d) AND (payload ->> 'held')::bigint = :i"),
        {"r": RELEASED, "d": DISCARDED, "i": held_id}).scalar()
    if decided is not None:
        word = "angelegt" if decided == RELEASED else "als Spam entschieden"
        raise Conflict(f"Die Anfrage «{held_id}» ist schon {word}.")
    return Held(id=row[0], at=row[1], company=row[2], payload=row[3] or {})


def release(db: Session, held_id: int) -> int:
    """►► **Kein Spam** – die Anfrage wird angelegt wie eben gekommen, samt Bestätigung. ◄◄
    Gibt die Nummer der Nachricht zurück."""
    h = _one(db, held_id)
    p = h.payload
    inq = inquiry.Inquiry(name=p.get("name", ""), email=p.get("email", ""),
                          message=p.get("message", ""), phone=p.get("phone", ""),
                          company=p.get("company", ""), source=p.get("source", "/kontakt"),
                          newsletter=bool(p.get("newsletter")), lang=inquiry.lang_of(p.get("lang")))
    firm = sites.by_object_id(db, h.company)
    if firm is None:
        raise Conflict(f"Die Gesellschaft «{h.company}» gibt es nicht mehr – die Anfrage lässt "
                       "sich nicht anlegen.")
    msg = inquiry.record(db, inq, None, files=list(p.get("files") or []), firm=firm)
    try:
        with db.begin_nested():     # die Bestätigung ist Kür: scheitert sie, steht die Anfrage
            inquiry.confirm(db, msg, inq, inquiry.words(inq.lang)["mail"])
    except Exception as exc:
        report.warn(f"INQUIRY released without confirmation held={h.id}: {type(exc).__name__}: {exc}")
    log.event(db, RELEASED, h.company, {"held": h.id, "message": msg.id})
    return msg.id


def discard(db: Session, held_id: int) -> None:
    """►► **Spam** – entschieden; die Anfrage bleibt im Log, sonst entsteht nichts. ◄◄"""
    h = _one(db, held_id)
    log.event(db, DISCARDED, h.company, {"held": h.id})
