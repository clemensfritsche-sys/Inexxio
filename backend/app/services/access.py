"""►►► **Wer was sieht – EINE Regeltabelle, zwei Funktionen.** ◄◄◄

``may`` prüft ein einzelnes Dokument, ``visible`` filtert eine Abfrage. Seiten, Suche,
Downloads, Links und die KI fragen nur diese beiden; niemand entscheidet selbst. Was nicht
erlaubt ist, ist verboten.

**Regel 9: Wer die Referenz sehen darf, sieht das Dokument.** Es gibt kein Merkmal
«vertraulich». Ein Arztzeugnis hängt am Nachweis einer Absenz (``time:<id>``); die
Zeiterfassung sehen nur die Person selbst und der Admin (``timekeeping.may_see``) – also
auch das Zeugnis. Hat ein Dokument mehrere Referenzen, muss man alle sehen dürfen. Ohne
Referenz sieht es das ganze Personal.

Die KI fragt mit dem Akteur, für den sie arbeitet – sie sieht nie mehr als er.
"""

from __future__ import annotations

from typing import Callable

from sqlalchemy import and_, exists, or_
from sqlalchemy.orm import Query, aliased

from ..domain import documents as dd
from ..models import Document, DocumentRef, UserProfile
from .people import STAFF_ROLES


def _own_or_admin(viewer: UserProfile, ref: DocumentRef) -> bool:
    return viewer.role == "admin" or viewer.object_id == ref.object_id


#: ►►► **Die Regeltabelle.** Art des Teils → wer die Referenz sehen darf. Ein Teil, der hier
#: nicht steht, gehört zu einem Datensatz, den jedes Personal sieht. ◄◄◄
RULES: dict[str, Callable[[UserProfile, DocumentRef], bool]] = {
    kind: _own_or_admin for kind in dd.PRIVATE_PARTS
}


def is_staff(viewer: UserProfile | None) -> bool:
    return viewer is not None and viewer.role in STAFF_ROLES


def may(viewer: UserProfile | None, refs: list[DocumentRef]) -> bool:
    """Darf ``viewer`` ein Dokument mit diesen (aktiven) Referenzen sehen?"""
    if not is_staff(viewer):
        return False
    for ref in refs:
        rule = RULES.get(dd.part_kind(ref.part) or "")
        if rule is not None and not rule(viewer, ref):
            return False
    return True


def visible(query: Query, viewer: UserProfile | None) -> Query:
    """Dieselbe Regel als Filter einer Abfrage auf ``Document`` – in der Datenbank, nicht
    nachträglich: eine Liste zeigt nie, was ``may`` verbieten würde."""
    if not is_staff(viewer):
        return query.filter(False)
    if viewer.role == "admin":
        return query
    ref = aliased(DocumentRef)
    forbidden = exists().where(and_(
        ref.document_id == Document.id,
        ref.is_active.is_(True),
        or_(*[ref.part.like(f"{kind}:%") for kind in RULES]),
        ref.object_id != (viewer.object_id or 0),
    )).correlate(Document)
    return query.filter(~forbidden)
