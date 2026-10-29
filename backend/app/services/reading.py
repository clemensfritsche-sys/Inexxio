"""►►► **Lesen und zuordnen – der Vorschlag für einen Entwurf.** ◄◄◄

Ein Entwurf wird gelesen, **bevor** etwas gespeichert ist (Regel 2): die KI liest die Datei
und schlägt Art, Name und Referenz vor; der Mensch prüft und gibt frei. Ohne KI (kein
Schlüssel, Deckel, Fehler) bleiben Art und Name leer – die Zuordnung über den Absender geht
trotzdem.

**Regel 5 – die Zuordnung:** ein wartendes Modul geht vor, dann unsere Nummer auf dem Blatt,
dann der Absender, sonst bleibt die Referenz leer. Der erste Treffer gewinnt.

**Die KI liest ab, der Code entscheidet.** Wählt die KI eine Anforderung, vergleicht der
Code die abgelesenen Werte mit dem Modul (Betrag mit Toleranz) und sagt «passt» oder
«weicht ab». Die KI sagt nie selbst «passt».
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Optional

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..models import Document, Order, UserProfile, Voucher, VoucherQuote
from . import ai, objects, records
from .requirements import FIELD_KEYS, Requirement, open_for


class Fact(BaseModel):
    label: str
    value: str


class Read(BaseModel):
    """Die feste Antwortform der Aufgabe «lesen»."""

    art: str = Field(description="Die Art, ein kurzes deutsches Wort, z. B. Lieferantenrechnung")
    name: str = Field(description="Was es von anderen derselben Art unterscheidet")
    text: str = Field(description="Der lesbare Text, wörtlich, höchstens 6000 Zeichen")
    keywords_de: list[str]
    keywords_en: list[str]
    numbers: list[str] = Field(description="Alle Nummern und Referenzen auf dem Blatt")
    facts: list[Fact] = Field(description="Alle Angaben: Bezeichnung und Wert")
    requirement: Optional[int] = Field(description="Nummer der passenden Anforderung, sonst null")
    values: list[Fact] = Field(description="Die Felder der gewählten Anforderung, wie gedruckt")


SYSTEM = (
    "Du liest Dokumente für das ERP eines Schweizer Maschinenbau-KMU: Rechnungen, Lieferscheine, "
    "Zeugnisse, Verträge, Fotos von Bauteilen. Antworte ausschliesslich in der verlangten Form. "
    "Erfinde nichts: was nicht auf dem Dokument steht, lässt du leer."
)


@dataclass
class Ref:
    object_id: int
    label: str
    part: Optional[str] = None
    field: Optional[str] = None


@dataclass
class Proposal:
    art: str = ""
    name: str = ""
    text: str = ""
    keywords: str = ""
    facts: dict = field(default_factory=dict)
    refs: list[Ref] = field(default_factory=list)
    why: str = ""
    read: bool = False                 # hat die KI gelesen?
    values: dict = field(default_factory=dict)
    requirement: Optional[str] = None  # Schlüssel der gewählten Anforderung


def _prompt(reqs: list[Requirement], arts: list[str]) -> str:
    lines = ["Lies dieses Dokument vollständig, auch Stempel, Handschrift und einen QR-Zahlteil.",
             "- art: ein kurzes deutsches Wort. Nimm eine dieser vorhandenen Arten, wenn sie passt: "
             + (", ".join(arts) if arts else "(noch keine)") + ".",
             "- name: Absender und die Nummer des Dokuments, z. B. «Hydro AG RE-26-4471». Bei einem "
             "Foto: was darauf zu sehen ist.",
             "- text: der lesbare Text, wörtlich, höchstens 6000 Zeichen (der Anfang, wenn es mehr ist).",
             "- keywords_de / keywords_en: je 5 bis 15 Stichworte für die Suche.",
             "- numbers: jede Nummer und Referenz (Bestellnummer, Rechnungsnummer, neunstellige "
             "Nummern, Chargen).",
             "- facts: die wichtigsten Angaben (höchstens 30) als Bezeichnung und Wert.",
             "- requirement und values: Passt das Dokument zu einer dieser offenen Anforderungen, "
             "gib ihre Nummer an und lies ihre Felder genau so ab, wie sie gedruckt sind. Sonst null "
             "und leere values."]
    for i, r in enumerate(reqs, 1):
        lines.append(f"  {i}. {r.sentence} Felder: {', '.join(r.fields)}.")
    return "\n".join(lines)


def _amount(text: str) -> Optional[Decimal]:
    raw = re.sub(r"[^\d.,\-]", "", text or "").replace("’", "").replace("'", "")
    if raw.count(",") and raw.count("."):
        raw = raw.replace(",", "")
    raw = raw.replace(",", ".")
    try:
        return Decimal(raw) if raw else None
    except InvalidOperation:
        return None


def check(req: Requirement, values: dict) -> tuple[bool, str]:
    """►►► **Der Code entscheidet, nicht die KI.** ◄◄◄ Passt das Gelesene zur Anforderung?
    Der Betrag darf um höchstens 5 % abweichen (Fracht, Rundung); eine Abweichung ist kein
    Fehler, sie wird beim Buchen mit Grund angenommen."""
    expected = req.expected.get("amount")
    if expected:
        got = next((_amount(v) for k, v in values.items() if "betrag" in k.lower()), None)
        want = Decimal(expected)
        if got is None:
            return False, "Den Gesamtbetrag finde ich auf dem Dokument nicht."
        if want and abs(got - want) > want * Decimal("0.05"):
            return False, f"Der Betrag weicht ab: vereinbart {want:.2f}, auf dem Dokument {got:.2f}."
    missing = [f for f in req.fields if not values.get(f)]
    if missing:
        return True, f"Passt; nicht gefunden: {', '.join(missing)}."
    return True, "Passt: alle Angaben gefunden."


def _by_number(db: Session, numbers: list[str]) -> Optional[tuple[int, str]]:
    """Stufe 2: eine unserer Nummern auf dem Blatt – Objektnummer oder Bestellreferenz."""
    for n in numbers:
        digits = re.sub(r"\D", "", n)
        if len(digits) == 9 and objects.resolve_object_type(db, int(digits)):
            return int(digits), n
    refs = [n.strip() for n in numbers if n.strip()]
    if refs:
        q = (db.query(Order.object_id, VoucherQuote.reference)
             .join(Voucher, Voucher.order_id == Order.id)
             .join(VoucherQuote, VoucherQuote.voucher_id == Voucher.id)
             .filter(VoucherQuote.reference.in_(refs), VoucherQuote.is_active.is_(True)))
        hit = q.first()
        if hit:
            return hit[0], hit[1]
    return None


def _arts(db: Session) -> list[str]:
    """Die Arten, die es schon gibt – damit nicht «Rechnung Lieferant» neben
    «Lieferantenrechnung» steht. Abgeleitet, kein Katalog."""
    rows = (db.query(Document.art).filter(Document.deleted_at.is_(None))
            .group_by(Document.art).limit(80).all())
    return sorted(a for (a,) in rows)


def propose(db: Session, *, raw: bytes, mime: str, actor: UserProfile,
            sender_object_id: Optional[int] = None, hint: Optional[str] = None) -> Proposal:
    """►►► **Der Vorschlag für einen Entwurf** – Lesen (KI) und Zuordnen (Code). ◄◄◄
    ``hint`` ist die Anforderung, aus der der Mensch kam (er öffnete das Feld im Modul): sie
    geht dann vor, ohne dass die KI sie wählen muss."""
    reqs = open_for(db, actor)
    if hint:
        reqs = [r for r in reqs if r.key == hint] + [r for r in reqs if r.key != hint]
    out = Proposal()
    content = ai.content_of(raw, mime)
    found: Optional[Read] = None
    if content is not None:
        found = ai.ask(db, task="read", actor=actor, system=SYSTEM, schema=Read,
                       content=[content, {"type": "text", "text": _prompt(reqs, _arts(db))}])
    if found is not None:
        out.read = True
        out.art, out.name = found.art.strip()[:80], found.name.strip()[:200]
        out.text = found.text[:20000]
        out.keywords = " ".join(dict.fromkeys(found.keywords_de + found.keywords_en))[:4000]
        out.facts = {f.label[:80]: f.value[:300] for f in found.facts[:80]}
    chosen = None
    if found is not None and found.requirement and 1 <= found.requirement <= len(reqs):
        chosen = reqs[found.requirement - 1]
    elif hint and reqs and reqs[0].key == hint:
        chosen = reqs[0]
    if chosen is not None:
        values = {v.label: v.value for v in (found.values if found else [])}
        ok, why = check(chosen, values) if found else (True, "Aus dem Modul geöffnet.")
        label = records.labels(db, [chosen.object_id]).get(chosen.object_id)
        out.refs = [Ref(chosen.object_id, f"{label.label if label else chosen.object_id}"
                        f" · {chosen.label.replace(' fehlt', '')}", chosen.part, chosen.field)]
        out.values = {FIELD_KEYS.get(k, k): v for k, v in values.items()}
        out.requirement = chosen.key
        out.why = f"Das Modul wartet auf genau dieses Dokument. {why}"
        return out
    hit = _by_number(db, found.numbers) if found is not None else None
    if hit is not None:
        rec = records.labels(db, [hit[0]]).get(hit[0])
        out.refs = [Ref(hit[0], rec.label if rec else str(hit[0]))]
        out.why = f"Die Nummer {hit[1]} steht auf dem Dokument."
        return out
    if sender_object_id:
        rec = records.labels(db, [sender_object_id]).get(sender_object_id)
        if rec is not None:
            out.refs = [Ref(sender_object_id, rec.label)]
            out.why = "Der Absender ist bekannt."
    return out
