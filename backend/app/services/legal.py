"""►►► **Die Rechtstexte – AGB und Datenschutz sind Dokumente der Gesellschaft.** ◄◄◄

**AGB und Datenschutz** sind Pflichtfelder jeder eigenen Gesellschaft (``company.agb`` ·
``company.privacy``): je ein Dokument in der einen Ablage, geändert wird durch ein neues
Dokument im Feld, nie leer. Die Fassung gilt ab ``facts.valid_from`` (sonst ab der
Freigabe). Jedes Papier eines Belegs hängt **die AGB der stellenden Gesellschaft an**, und
friert sie mit ein. Die Website zeigt die AGB der Gesellschaft zum Land des Besuchers, den
Datenschutz und das Impressum des Betreibers.

``app/assets/legal/<art>/<JJJJ-MM-TT>.md`` ist die **Vorlage**: «Aus Vorlage» an der
Gesellschaft legt daraus ein Dokument an (ein Mensch entscheidet, nie von selbst); das
**Impressum** ist kein Dokument, sondern die Angaben des Betreibers in dieser Vorlage.

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

from ..core import clock
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
    day = on or clock.today()
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
    from . import voucher_head
    return voucher_head.uid_of(company) or ""



# ---------------------------------------------------------------------------
# Die Dokumente einer Gesellschaft
# ---------------------------------------------------------------------------

#: Welche Art in welchem Pflichtfeld der Gesellschaft steht. Das Impressum hat keins.
FIELD_OF = {AGB: "company.agb", "datenschutz": "company.privacy"}
MARKDOWN = "text/markdown"


def document_of(db, company: Any, kind: str):
    """Das Dokument im Pflichtfeld einer Gesellschaft – oder ``None``."""
    from . import documents
    if company is None or kind not in FIELD_OF or not getattr(company, "object_id", None):
        return None
    return documents.field_document(db, company.object_id, FIELD_OF[kind])


def valid_from_of(doc: Any) -> date:
    """Ab wann eine Fassung gilt – so, wie sie freigegeben wurde."""
    try:
        return date.fromisoformat(str((doc.facts or {}).get("valid_from")))
    except ValueError:
        return doc.created_at.date()


def text_of(db, company: Any, kind: str = AGB) -> Optional[Text]:
    """►►► **Der Rechtstext einer Gesellschaft** – mit ihren Werten eingesetzt. ◄◄◄

    Ein Text aus der Vorlage (Markdown) wird Seite für Seite gesetzt; eine andere Datei (ein
    PDF) nennt sich mit ihrer Nummer – angehängt wird, was sich setzen lässt."""
    from . import documents, objects
    doc = document_of(db, company, kind)
    if doc is None:
        return None
    day = valid_from_of(doc)
    raw = documents.raw_of(db, doc)
    if doc.mime == MARKDOWN and raw is not None:
        return parse(kind, day, fill(raw.decode("utf-8", "replace"), values_of(company)))
    text = Text(kind=kind, valid_from=day, title=KINDS[kind][1])
    text.intro.append(f"Es gilt das Dokument {objects.obj_nr(doc.object_id)} "
                      f"«{doc.name}» in der Fassung vom {text.day}.")
    return text


def from_template(db, company: Any, kind: str, actor: Any):
    """**«Aus Vorlage»** – ein Mensch übernimmt die Vorlage als Dokument seiner Gesellschaft
    (``company.agb`` · ``company.privacy``). Gilt ab heute."""
    from fastapi import HTTPException
    from . import fields
    if kind not in FIELD_OF:
        raise HTTPException(status_code=400, detail=f"Eine Vorlage «{kind}» gibt es nicht.")
    found = template(kind)
    if found is None:
        raise HTTPException(status_code=404, detail=f"Die Vorlage «{kind}» ist nicht hinterlegt.")
    doc = _file_template(db, company, kind, found, clock.today(), actor)
    return fields.apply(db, actor=actor, doc=doc, object_id=company.object_id, part=None,
                        field=FIELD_OF[kind])


def template(kind: str, on: Optional[date] = None) -> Optional[tuple[date, str]]:
    """Die Vorlage, wie sie an einem Tag gilt – Datum und roher Text (mit ``{{…}}``)."""
    day = on or clock.today()
    valid = [d for d in versions(kind) if d <= day]
    if not valid:
        return None
    return valid[-1], (DIR / kind / f"{valid[-1].isoformat()}.md").read_text(encoding="utf-8")


def _file_template(db, company: Any, kind: str, found: tuple[date, str], valid: date,
                   actor: Any):
    """Die Vorlage als Dokument – dieselbe Vorlage ist dasselbe Dokument (Regel 1), auch für
    zwei Gesellschaften; die Werte setzt erst das Papier ein."""
    from . import documents
    word = KINDS[kind][0]
    doc, _ = documents.file(
        db, raw=found[1].encode("utf-8"), filename=f"{word}.md", mime=MARKDOWN, art=word,
        name=f"Vorlage vom {found[0].strftime('%d.%m.%Y')}", source="compose", refs=[],
        actor=actor, facts={"kind": kind, "valid_from": valid.isoformat(),
                            "template": found[0].isoformat()})
    return doc


def for_visitor(db, kind: str, country: Optional[str]) -> tuple[Optional[Text], Optional[str], dict[str, str]]:
    """►►► **Was die Website zeigt** – ``(Text, Datei-Link, Werte)``. ◄◄◄ Die AGB der
    Gesellschaft zum Land des Besuchers (``sites.company_for_country``), Datenschutz und
    Impressum des Betreibers. Ein Text aus der Vorlage wird gesetzt; eine andere Datei (PDF)
    zeigt die Seite, wie sie ist."""
    from . import documents
    company = (sites.company_for_country(db, country) if kind == AGB
               else sites.find_operator(db))
    values = values_of(company)
    if kind not in FIELD_OF:
        return current(kind, values=values), None, values
    owner = company if document_of(db, company, kind) is not None else sites.find_operator(db)
    doc = document_of(db, owner, kind)
    if doc is None:
        return None, None, values
    if doc.mime == MARKDOWN:
        return text_of(db, owner, kind), None, values_of(owner)
    return None, documents.file_url(db, doc), values


def adopt_templates(db) -> int:
    """►►► **Die Vorlagen einmal als Dokumente** – beim Start (``main.lifespan``). ◄◄◄ Gibt es
    noch nirgends ein Rechtstext-Feld (eine frische Datenbank), wird die Vorlage das Dokument
    jeder eigenen Gesellschaft; danach nie wieder (eine neue Gesellschaft wählt selbst,
    «Aus Vorlage»). Gibt zurück, wie viele Felder gesetzt wurden."""
    from ..models import CompanySettings, DocumentRef
    from . import documents
    if (db.query(DocumentRef.id).filter(DocumentRef.field.in_(tuple(FIELD_OF.values())))
            .first() is not None):
        return 0
    own = (db.query(CompanySettings).filter(CompanySettings.is_own.is_(True),
                                            CompanySettings.is_active.is_(True)).all())
    count = 0
    for kind, field_key in FIELD_OF.items():
        found = template(kind)
        if found is None:
            continue
        for company in own:
            if not company.object_id:
                continue
            doc = _file_template(db, company, kind, found, found[0], None)
            documents.set_field(db, document_object_id=doc.object_id,
                                object_id=company.object_id, part=None, field=field_key,
                                actor=None)
            count += 1
    db.flush()
    return count
