"""Quer-Referenzen: wer zeigt auf diese Objektnummer?

Der Reiter «Verwendung» beantwortet für **jede** Objektnummer dieselbe Frage, ohne den
Typ zu kennen – darum steht die Auflösung hier und nicht in einem Detailfenster.

Mit der Prozesslogik sind die meisten Verweise entfallen (Aufträge, Bewegungen,
Ressourcen-Nutzung, Standorte). Geblieben ist die eine Beziehung des neuen Datenmodells:
**ein Artikel trägt Instanzen.** Die Einzelinstanzen einer Instanz sind kein Verweis,
sondern ihr Inhalt – sie stehen im Detail, nicht hier.
"""

from sqlalchemy.orm import Session

from ..models import Article, Instance
from .instances import quantities


def object_references(db: Session, object_id: int) -> list[dict]:
    """Verweise auf ``object_id``. Leere Liste heisst: nichts zeigt darauf – das ist
    eine Antwort, kein fehlender Wert."""
    article = db.query(Article).filter(Article.object_id == object_id).first()
    if article is None:
        return []

    rows = (
        db.query(Instance)
        .filter(Instance.article_id == article.id, Instance.is_active.is_(True))
        .order_by(Instance.object_id.desc())
        .all()
    )
    counts = quantities(db, [i.id for i in rows])
    return [
        {
            "kind": "Instanz dieses Artikels",
            "ref_type": "instance",
            "object_id": i.object_id,
            "label": f"{i.kind} · {counts.get(i.id, 0)} Einzelinstanzen",
            "at": i.created_at,
        }
        for i in rows
    ]
