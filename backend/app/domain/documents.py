"""►►► **Das Dokument als Regel – ohne Datenbank.** ◄◄◄

Neun Regeln tragen alles (``docs/dokumente.md``). Hier steht, was davon ohne Datenbank
gilt: woher ein Dokument kommen kann, welche Pflichtfelder es gibt, wie ein Teil eines
Datensatzes heisst und wie der Zustand aus den Fakten folgt.

**An der Art hängt nichts.** Sie ist freier Text; keine Regel fragt sie ab.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from . import statuses as st

#: Woher ein Dokument kam – nur Auskunft. Jede Quelle endet in derselben Freigabe.
SOURCES: dict[str, str] = {
    "file": "Datei",
    "scan": "Scan",
    "compose": "Verfasst",
    "mail": "Mail",
    "form": "Kontaktformular",
    "capture": "Datenerfassung",
    "voucher": "Beleg",
}

#: ►►► **Die Pflichtfelder** – eine Referenz, die ihr Datensatz braucht. ◄◄◄ Sie hat auf der
#: Dokumentseite ein Schloss statt ×: geändert wird sie nur dort, wo das Feld steht, und
#: leer wird sie nie (Regel 6). Schlüssel → was auf dem Schloss steht.
FIELDS: dict[str, str] = {
    "voucher.original": "Originalbeleg im Zahlungsmodul",
    "voucher.export": "Ausfuhrnachweis im Zahlungsmodul",
    "voucher.doc": "Beleg des Zahlungsmoduls",
    "time.proof": "Nachweis einer Absenz",
    "capture.photo": "Bild der Datenerfassung",
    "company.agb": "AGB der Gesellschaft",
    "company.privacy": "Datenschutzerklärung der Gesellschaft",
}

#: Ein Teil ohne eigene Seite: ``step:<id>`` (Modul im Auftrag) · ``time:<id>`` (Absenz) ·
#: ``unit:<Nummer>`` (Stück, z. B. ``unit:100000027-3``).
PART = re.compile(r"^(step|time|unit):[0-9A-Za-z\-]{1,48}$")

#: Teile, die nur die Person selbst und der Admin sehen (``services/access``).
PRIVATE_PARTS = ("time",)

ART_MAX, NAME_MAX, REASON_MAX = 80, 200, 300


def clean(value: object, limit: int) -> str:
    """Ein Feld, wie es gespeichert wird: getrimmt, ohne Zeilenumbruch, gekürzt."""
    return " ".join(str(value or "").split())[:limit]


def part_kind(part: str | None) -> str | None:
    return part.split(":", 1)[0] if part else None


def title(art: str, name: str) -> str:
    """Der Titel ist immer «Art · Name»."""
    return f"{art} · {name}" if name else art


@dataclass(frozen=True)
class Facts:
    """Was den Zustand bestimmt – mehr nicht."""

    deleted: bool
    requested: int     # verlangte Unterschriften
    signed: int
    declined: int


def status(f: Facts) -> str:
    """►►► **Der Zustand – abgeleitet, nie gespeichert.** ◄◄◄ Freigegeben ist ein Dokument erst,
    wenn alle verlangten Unterschriften da sind (Regel 7)."""
    if f.deleted:
        return st.GELOESCHT
    if f.declined:
        return st.ABGELEHNT
    if f.signed < f.requested:
        return st.UNTERSCHRIFT_ANGEFRAGT
    return st.FREIGEGEBEN
