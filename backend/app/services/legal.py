"""►►► **Die Rechtstexte – AGB, Datenschutz, Impressum: eine Datei je Fassung.** ◄◄◄

``app/assets/legal/<art>/<JJJJ-MM-TT>.md`` – der Dateiname ist das Datum, ab dem die Fassung
gilt. Eine neue Fassung ist eine **neue Datei**; die alte bleibt liegen, damit nachvollziehbar
bleibt, was damals galt. Jedes Dokument eines Belegs hängt **die AGB an, die an seinem Tag
galten**, und friert sie mit ein (``voucher_documents``).

**Ein Text für alle**: es gibt keine Teile für Geschäfts- und Endkunden – wo etwas nur für
eine Seite gilt, sagt es der Satz selbst.

Die Datei ist schlichtes Markdown: ``#`` Titel, Absätze davor sind die Einleitung, ``##`` je
Abschnitt, darin Absätze und ``-`` Aufzählungen. **Werte aus dem ERP** stehen als
``{{schlüssel}}`` (``FIELDS``) und kommen von der Gesellschaft, die das Dokument stellt – sonst
vom Betreiber. Fehlt ein Wert, fällt die Zeile weg; erfunden wird nichts.
"""

import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Optional

from . import address, sites

DIR = Path(__file__).resolve().parent.parent / "assets" / "legal"

#: Die Arten – Schlüssel, das grosse Wort auf dem Papier, der Titel.
KINDS: dict[str, tuple[str, str]] = {
    "agb": ("AGB", "Allgemeine Geschäftsbedingungen"),
    "datenschutz": ("Datenschutz", "Datenschutzerklärung"),
    "impressum": ("Impressum", "Impressum"),
}
AGB = "agb"

#: Was ein Text aus dem ERP einsetzen darf.
FIELDS = ("firma", "strasse", "plz", "ort", "telefon", "email", "uid")

_SLOT = re.compile(r"\{\{\s*([a-z]+)\s*\}\}")


@dataclass
class Section:
    title: str
    blocks: list[tuple[str, str]] = field(default_factory=list)   # ("p"|"li", Text)


@dataclass
class Text:
    """Eine Fassung eines Rechtstexts – Art, Datum, Einleitung, Abschnitte."""
    kind: str
    valid_from: date
    title: str
    intro: list[str] = field(default_factory=list)
    sections: list[Section] = field(default_factory=list)

    @property
    def key(self) -> str:
        return self.valid_from.isoformat()

    @property
    def day(self) -> str:
        """Das Datum, wie es auf dem Papier steht – «01.01.2026»."""
        return self.valid_from.strftime("%d.%m.%Y")

    @property
    def word(self) -> str:
        return KINDS[self.kind][0]

    @property
    def date_label(self) -> str:
        """AGB gelten ab einem Tag; Datenschutz und Impressum haben einen Stand."""
        return "Gültig ab" if self.kind == AGB else "Stand"


def versions(kind: str) -> list[date]:
    """Alle Fassungen einer Art, älteste zuerst."""
    out = []
    for f in (DIR / kind).glob("*.md"):
        try:
            out.append(date.fromisoformat(f.stem))
        except ValueError:
            continue
    return sorted(out)


def current(kind: str = AGB, on: Optional[date] = None,
            values: Optional[dict[str, str]] = None) -> Optional[Text]:
    """**Die Fassung, die an diesem Tag gilt** – die jüngste, die schon begonnen hat."""
    day = on or date.today()
    valid = [d for d in versions(kind) if d <= day]
    if not valid:
        return None
    raw = (DIR / kind / f"{valid[-1].isoformat()}.md").read_text(encoding="utf-8")
    return parse(kind, valid[-1], fill(raw, values or {}))


def fill(text: str, values: dict[str, str]) -> str:
    """Setzt die Werte ein; eine Zeile, der ein Wert fehlt, fällt weg."""
    out = []
    for line in text.splitlines():
        keys = _SLOT.findall(line)
        if any(not (values.get(k) or "").strip() for k in keys):
            continue
        out.append(_SLOT.sub(lambda m: values[m.group(1)].strip(), line))
    return "\n".join(out)


def parse(kind: str, valid_from: date, text: str) -> Text:
    """Markdown in Einleitung und Abschnitte – nur die Formen, die die Dateien kennen."""
    doc = Text(kind=kind, valid_from=valid_from, title=KINDS[kind][1])
    section: Optional[Section] = None
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("## "):
            section = Section(line[3:].strip())
            doc.sections.append(section)
        elif line.startswith("# "):
            doc.title = line[2:].strip()
        elif section is None:
            doc.intro.append(line)
        else:
            section.blocks.append(("li", line[2:].strip()) if line.startswith("- ")
                                  else ("p", line))
    return doc


def values_of(company: Any) -> dict[str, str]:
    """**Die Werte einer Gesellschaft** für ``{{…}}`` – aus dem ERP, eine Stelle."""
    if company is None:
        return {}
    seat = address.of_company(company)

    def clean(v: Any) -> str:
        v = (str(v) if v is not None else "").strip()
        return "" if v == "—" else v

    return {
        "firma": clean(sites.legal_name(company)),
        "strasse": clean(seat.get("street1")),
        "plz": clean(seat.get("zip")),
        "ort": clean(seat.get("city")),
        "telefon": clean(getattr(company, "phone", None)),
        "email": clean(getattr(company, "email", None)),
        "uid": clean(_uid(company)),
    }


def sender_line(values: dict[str, str]) -> str:
    """Der Absender in der Fusszeile – Name, Sitz, MWST-Nummer."""
    place = " ".join(x for x in (values.get("plz"), values.get("ort")) if x)
    return " · ".join(x for x in (values.get("firma"), values.get("strasse"), place,
                                  values.get("uid")) if x)


def of_operator(db) -> dict[str, str]:
    """Die Werte des Betreibers – für die Seiten ``/agb``, ``/datenschutz``, ``/impressum``."""
    return values_of(sites.find_operator(db))


def _uid(company: Any) -> str:
    from . import voucher as voucher_svc
    return voucher_svc._uid(company) or ""

