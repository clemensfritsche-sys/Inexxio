"""**Was ist diese Objektnummer, und wie heisst sie?** – für Referenzen.

Eine Referenz zeigt auf eine Objektnummer; gezeigt wird sie als «Typ · Name» mit Nummer.
Gesucht wird mit derselben Bedingung wie überall (``lookup.matches``: Nummer ODER Name).
Ein Datensatz, der keine eigene Seite hat, ist hier nicht wählbar.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable

from sqlalchemy.orm import Session

from ..models import Article, CompanySettings, Document, Instance, Order, UserProfile
from . import lookup, objects, sites
from .objects import obj_nr

@dataclass(frozen=True)
class Record:
    object_id: int
    type: str
    name: str

    @property
    def label(self) -> str:
        """«Typ · Name» – ausser der Name beginnt schon mit dem Typ («Auftrag 100000029»)."""
        kind = objects.TYPES.get(self.type)
        word = kind.word if kind else self.type
        if not self.name:
            return word
        return self.name if self.name.startswith(word) else f"{word} · {self.name}"


def _articles(db: Session, ids: Iterable[int]) -> dict[int, str]:
    rows = db.query(Article.id, Article.name).filter(Article.id.in_(set(ids))).all()
    return {i: n for i, n in rows}


def _instance_names(db: Session, ids: set[int]) -> dict[int, str]:
    insts = db.query(Instance.object_id, Instance.article_id).filter(Instance.object_id.in_(ids)).all()
    names = _articles(db, (a for _, a in insts))
    return {oid: names.get(aid) or "" for oid, aid in insts}


#: Je Typ: der Name seiner Nummern (eine Abfrage für alle Nummern dieses Typs).
_NAMES: dict[str, Callable[[Session, set[int]], dict[int, str]]] = {
    "user": lambda db, ids: {u.object_id: u.display_name or u.email or "" for u in
                             db.query(UserProfile).filter(UserProfile.object_id.in_(ids))},
    "organization": lambda db, ids: {c.object_id: sites.legal_name(c) or "" for c in
                                     db.query(CompanySettings).filter(CompanySettings.object_id.in_(ids))},
    "order": lambda db, ids: {o.object_id: o.name or obj_nr(o.object_id) for o in
                              db.query(Order).filter(Order.object_id.in_(ids))},
    "article": lambda db, ids: {a: n or "" for a, n in
                                db.query(Article.object_id, Article.name).filter(Article.object_id.in_(ids))},
    "instance": _instance_names,
    "document": lambda db, ids: {d: f"{art} · {name}" for d, art, name in
                                 db.query(Document.object_id, Document.art, Document.name)
                                 .filter(Document.object_id.in_(ids))},
}


def labels(db: Session, object_ids: Iterable[int]) -> dict[int, Record]:
    """Name und Typ zu jeder Nummer – der Typ aus der Registry, dann eine Abfrage je
    vorkommendem Typ (nie je Nummer, nie über alle Tabellen)."""
    by_type: dict[str, set[int]] = {}
    for oid, t in objects.types_of(db, object_ids).items():
        by_type.setdefault(t, set()).add(oid)
    out: dict[int, Record] = {}
    for t, ids in by_type.items():
        out.update({oid: Record(oid, t, name) for oid, name in _NAMES[t](db, ids).items()})
    return out


SEARCH_LIMIT = 8


def search(db: Session, q: str, *, limit: int = SEARCH_LIMIT) -> list[Record]:
    """**Ein Datensatz für eine Referenz** – Personen und Firmen über ihre eine Suche
    (``people.search`` · ``sites.search``, nur aktive), dazu Artikel, Aufträge, Instanzen.
    Ohne Eingabe nichts: eine Referenz wählt man, man blättert sie nicht durch."""
    q = (q or "").strip()
    if not q:
        return []
    from . import people
    found: list[Record] = [Record(u.object_id, "user", u.display_name or u.email or "")
                           for u in people.search(db, q, limit=limit)]
    found += [Record(c.object_id, "organization", sites.legal_name(c) or "")
              for c in sites.search(db, q, limit=limit)]
    orders = db.query(Order).filter(lookup.matches(q, Order.object_id)).limit(limit).all()
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
