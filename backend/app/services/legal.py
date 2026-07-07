"""Öffentliche Rechtsdokumente (AGB/Datenschutz/…) – Zeiger auf einen **Artikel** (D).

Am Unternehmen wird je Rechtsdokument-Art (``agb``, ``datenschutz``, …) die **Objektnummer
eines Artikels** hinterlegt (``company_settings.legal_documents``). Die Website zieht daraus
die **erste freigegebene Instanz** dieses Artikels – den offiziellen, ausgestellten Dokument-
Beleg – und rendert dessen Inhalt/Nummer/Datum mit derselben Ansicht wie das PDF (DocumentView).

Eine **neue Fassung** ist – wie bei jedem Artikel – ein **neuer Artikel + «Ersetzen»**
(``replaced_by_id``): sobald der Nachfolge-Artikel selbst einen freigegebenen Bestand trägt,
folgt die Website automatisch der Ersetzungs-Kette auf die neueste Fassung (wie der Shop
kanonisiert). Solange der Nachfolger noch keinen freigegebenen Beleg hat, bleibt die bisherige
Fassung gültig – die alte Instanz bleibt über ihre Objektnummer archiviert (Nachweis im
Streitfall, welche AGB an welchem Tag galt).
"""

from typing import Optional

from sqlalchemy.orm import Session

from ..models import Article, Instance
from .admin import get_or_create_settings
from .document import instance_document_embeds
from .inventory import in_stock_clauses


def pointer(db: Session, kind: str) -> Optional[int]:
    """Objektnummer des hinterlegten Rechtsdokument-**Artikels** für ``kind`` (oder None)."""
    settings = get_or_create_settings(db)
    mapping = settings.legal_documents or {}
    val = mapping.get(kind)
    try:
        return int(val) if val is not None else None
    except (TypeError, ValueError):
        return None


def _replacement_chain(db: Session, article: Article) -> list[Article]:
    """Die Ersetzungs-Kette ``[Start … neuester Nachfolger]`` über ``replaced_by_id``
    (zyklensicher). Folgt dem Pfad ohne ``is_active``-Filter – ein ersetzter Artikel wird
    inaktiv, seine Fassung bleibt aber archiviert und auflösbar (wie ``sales.canonical``)."""
    chain: list[Article] = []
    seen: set[int] = set()
    cur: Optional[Article] = article
    while cur is not None and cur.id not in seen:
        seen.add(cur.id)
        chain.append(cur)
        cur = (
            db.query(Article).filter(Article.object_id == cur.replaced_by_id).first()
            if cur.replaced_by_id else None
        )
    return chain


def _first_released_document(db: Session, article_id: int):
    """Die **erste** (FIFO) freigegebene Instanz des Artikels, die einen ausgestellten
    Dokument-Beleg trägt → ``(Instanz, DocumentEmbed)`` oder ``(None, None)``.

    „Freigegeben" = qc passed UND am Lager (``inventory.in_stock_clauses``); „erste" =
    älteste Freigabe zuerst (``released_at``), dann Objektnummer."""
    insts = (
        db.query(Instance)
        .filter(Instance.article_id == article_id, Instance.is_active == True, *in_stock_clauses())
        .order_by(Instance.released_at, Instance.object_id)
        .all()
    )
    for inst in insts:
        doc = next((e for e in instance_document_embeds(db, inst) if e.content), None)
        if doc is not None:
            return inst, doc
    return None, None


def resolve(db: Session, kind: str) -> Optional[dict]:
    """Gültiges Rechtsdokument für ``kind`` auflösen → ``{kind, object_number,
    document_date, content}`` – oder None (dann fällt die Website auf ihren eingebauten
    Text zurück).

    Zeiger = **Artikel**-Objektnummer. Aufgelöst wird die **neueste Fassung mit
    freigegebenem Beleg**: die Ersetzungs-Kette wird vom Nachfolger her durchsucht und die
    erste (jüngste) Fassung genommen, die einen ausgestellten Dokument-Beleg trägt. So wird
    ein noch belegloser Nachfolger (Entwurf) automatisch übersprungen – die bisherige Fassung
    bleibt gültig, bis die neue tatsächlich einen freigegebenen Bestand hat."""
    art_obj = pointer(db, kind)
    if art_obj is None:
        return None
    start = db.query(Article).filter(Article.object_id == art_obj).first()
    if start is None:
        return None
    for art in reversed(_replacement_chain(db, start)):   # Nachfolger zuerst
        inst, doc = _first_released_document(db, art.id)
        if doc is not None:
            return {
                "kind": kind,
                "object_number": inst.object_id,
                "document_date": inst.released_at,
                "content": doc.content,
            }
    return None
