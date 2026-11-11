"""Der **Erzeugungsprozess** eines Artikels – Vorlage pflegen und kopieren.

Die Vorlage führt nichts aus (PROCESS_CORE.md §8.2). **Kopie, nicht Verweis** (§6):
``mirror`` liefert die Schritte als Werte samt Versionsstempel; der Auftrag schreibt sie als
eigene Zeilen.
"""

from typing import Any

from sqlalchemy.orm import Session

from ..domain import chain, modules
from ..models import Article, ArticleProcessStep
from ..domain.errors import Invalid


def steps_of(db: Session, article: Article) -> list[ArticleProcessStep]:
    """Die Vorlage des Artikels, in Reihenfolge."""
    return (
        db.query(ArticleProcessStep)
        .filter(
            ArticleProcessStep.article_id == article.id,
        )
        .order_by(ArticleProcessStep.position)
        .all()
    )


def step_counts(db: Session, article_ids: list[int]) -> dict[int, int]:
    """Wie viele Schritte hat die Vorlage je Artikel? **Eine** Abfrage, kein N+1 – ohne
    Vorlage ist «Neu» nicht wählbar."""
    from sqlalchemy import func

    if not article_ids:
        return {}
    rows = (
        db.query(ArticleProcessStep.article_id, func.count(ArticleProcessStep.id))
        .filter(
            ArticleProcessStep.article_id.in_(article_ids),
        )
        .group_by(ArticleProcessStep.article_id)
        .all()
    )
    counts = {int(a): int(n) for a, n in rows}
    return {int(a): counts.get(int(a), 0) for a in article_ids}


def create_steps(db: Session, article: Article, raw: list[dict[str, Any]]) -> list[ArticleProcessStep]:
    """Den Erzeugungsprozess eines Artikels anlegen — **in einem Zug mit dem Artikel**;
    danach ist er eingefroren (§6.5).

    Der Übergang wird vom Modultyp abgeleitet (``domain/modules``); einen Namen hat ein
    Modul nicht – den sagt sein Typ.
    """
    if not raw:
        raise Invalid("Ohne Prozessschrittmodul kann dieser Artikel nichts erzeugen. "
                    "Mindestens eines ist Pflicht.")
    out: list[ArticleProcessStep] = []
    for position, data in enumerate(raw, start=1):
        module = modules.get(data.get("module_type"))
        config = module.clean_step(data.get("config"))
        step = ArticleProcessStep(
            article_id=article.id,
            position=position,
            module_type=module.key,
            config=config,
        )
        db.add(step)
        out.append(step)
    # **Dieselbe Kettenregel wie beim Auftrag** (``domain/chain``) – jetzt, weil die Vorlage
    # danach eingefroren ist.
    chain.assert_closes([{"module_type": s.module_type} for s in out])
    return out


def mirror(db: Session, article: Article) -> list[dict[str, Any]]:
    """Die Vorlage als **Kopie** – Werte, kein Verweis, mit ihrer Herkunft; unverändert für
    ``process_steps`` des Auftrags. Leer ist ein Fehler beim Aufrufer."""
    return [
        {
            "module_type": s.module_type,
            # Die Konfiguration muss mit (z. B. die Erfassungspunkte).
            "config": dict(s.config) if s.config else None,
        }
        for s in steps_of(db, article)
    ]
