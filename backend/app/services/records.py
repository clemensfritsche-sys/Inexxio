"""**Was ist diese Objektnummer, und wie heisst sie?** – für Referenzen.

Eine Referenz zeigt auf eine Objektnummer; gezeigt wird sie als «Typ · Name» mit Nummer.
Gesucht wird mit derselben Bedingung wie überall (``lookup.matches``: Nummer ODER Name).
Ein Datensatz, der keine eigene Seite hat, ist hier nicht wählbar.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from sqlalchemy.orm import Session

from ..models import Article, CompanySettings, Document, Instance, Order, UserProfile
from . import lookup, sites
from .objects import obj_nr

#: Das Wort je Typ – dasselbe wie im Feed (``lib/erp-record.ts``).
TYPE_WORDS = {
    "user": "Benutzer", "article": "Artikel", "order": "Auftrag",
    "instance": "Instanz", "organization": "Unternehmen", "document": "Dokument",
}


@dataclass(frozen=True)
class Record:
    object_id: int
    type: str
    name: str

    @property
    def label(self) -> str:
        return f"{TYPE_WORDS.get(self.type, self.type)} · {self.name}" if self.name else \
            TYPE_WORDS.get(self.type, self.type)


def _articles(db: Session, ids: Iterable[int]) -> dict[int, str]:
    rows = db.query(Article.id, Article.name).filter(Article.id.in_(set(ids))).all()
    return {i: n for i, n in rows}


def labels(db: Session, object_ids: Iterable[int]) -> dict[int, Record]:
    """Name und Typ zu jeder Nummer – eine Abfrage je Typ, nicht je Nummer."""
    ids = {int(i) for i in object_ids if i}
    out: dict[int, Record] = {}
    if not ids:
        return out
    for u in db.query(UserProfile).filter(UserProfile.object_id.in_(ids)).all():
        out[u.object_id] = Record(u.object_id, "user", u.display_name or u.email or "")
    for c in db.query(CompanySettings).filter(CompanySettings.object_id.in_(ids)).all():
        out[c.object_id] = Record(c.object_id, "organization", sites.legal_name(c) or "")
    for o in db.query(Order).filter(Order.object_id.in_(ids)).all():
        out[o.object_id] = Record(o.object_id, "order", o.name or obj_nr(o.object_id))
    for a in db.query(Article).filter(Article.object_id.in_(ids)).all():
        out[a.object_id] = Record(a.object_id, "article", a.name or "")
    insts = db.query(Instance).filter(Instance.object_id.in_(ids)).all()
    names = _articles(db, (i.article_id for i in insts))
    for i in insts:
        out[i.object_id] = Record(i.object_id, "instance", names.get(i.article_id) or "")
    for d in db.query(Document).filter(Document.object_id.in_(ids)).all():
        out[d.object_id] = Record(d.object_id, "document", f"{d.art} · {d.name}")
    return out


SEARCH_LIMIT = 8


def search(db: Session, q: str, *, limit: int = SEARCH_LIMIT) -> list[Record]:
    """**Ein Datensatz für eine Referenz** – Personen, Firmen, Artikel, Aufträge, Instanzen.
    Ohne Eingabe nichts: eine Referenz wählt man, man blättert sie nicht durch."""
    q = (q or "").strip()
    if not q:
        return []
    found: list[Record] = []
    people = (db.query(UserProfile).filter(lookup.matches(
        q, UserProfile.object_id, UserProfile.first_name, UserProfile.last_name,
        UserProfile.email)).limit(limit).all())
    found += [Record(u.object_id, "user", u.display_name or u.email or "") for u in people
              if u.object_id]
    firms = (db.query(CompanySettings).filter(CompanySettings.is_active.is_(True), lookup.matches(
        q, CompanySettings.object_id, CompanySettings.company_name)).limit(limit).all())
    found += [Record(c.object_id, "organization", sites.legal_name(c) or "") for c in firms
              if c.object_id]
    orders = db.query(Order).filter(lookup.matches(q, Order.object_id, Order.name)).limit(limit).all()
    found += [Record(o.object_id, "order", o.name or "") for o in orders]
    arts = (db.query(Article).filter(Article.object_id.isnot(None), lookup.matches(
        q, Article.object_id, Article.name)).limit(limit).all())
    found += [Record(a.object_id, "article", a.name or "") for a in arts]
    insts = (db.query(Instance).join(Article, Article.id == Instance.article_id)
             .filter(lookup.matches(q, Instance.object_id, Article.name)).limit(limit).all())
    names = _articles(db, (i.article_id for i in insts))
    found += [Record(i.object_id, "instance", names.get(i.article_id) or "") for i in insts]
    exact = [r for r in found if str(r.object_id) == q]
    return (exact + [r for r in found if r not in exact])[: limit * 2]
