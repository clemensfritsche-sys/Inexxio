"""Der **Erzeugungsprozess** eines Artikels – Vorlage pflegen und kopieren.

Die Vorlage kann nichts ausführen (PROCESS_CORE.md §8.2): es gibt hier keinen Endpunkt,
der ein Stück bewegt, und keine Funktion, die einen Status setzt. Sie beantwortet genau
zwei Fragen – *wie sieht der Prozess dieses Artikels aus* und *wie kommt er in einen
Auftrag*.

**Kopie, nicht Verweis** (Auftragspunkt §6): ``mirror`` liefert die Schritte als Werte
samt Versionsstempel; der Auftrag schreibt sie als eigene Zeilen. Ein Verweis hiesse,
dass eine Artikeländerung laufende Aufträge rückwirkend umschreibt.
"""

from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..domain import statuses as st
from ..models import Article, ArticleProcessStep
from ..models.process_step import MODULE_TYPES


def steps_of(db: Session, article: Article) -> list[ArticleProcessStep]:
    """Die Vorlage des Artikels, in Reihenfolge."""
    return (
        db.query(ArticleProcessStep)
        .filter(
            ArticleProcessStep.article_id == article.id,
            ArticleProcessStep.is_active.is_(True),
        )
        .order_by(ArticleProcessStep.position)
        .all()
    )


def step_counts(db: Session, article_ids: list[int]) -> dict[int, int]:
    """Wie viele Schritte hat die Vorlage je Artikel? **Eine** Abfrage, kein N+1.

    Die Auswahl im Definitionsbereich braucht das für jede Zeile: ohne Vorlage ist
    «Neu» nicht wählbar, und der Grund muss im Klartext dastehen.
    """
    from sqlalchemy import func

    if not article_ids:
        return {}
    rows = (
        db.query(ArticleProcessStep.article_id, func.count(ArticleProcessStep.id))
        .filter(
            ArticleProcessStep.article_id.in_(article_ids),
            ArticleProcessStep.is_active.is_(True),
        )
        .group_by(ArticleProcessStep.article_id)
        .all()
    )
    counts = {int(a): int(n) for a, n in rows}
    return {int(a): counts.get(int(a), 0) for a in article_ids}


def add_step(db: Session, article: Article, data: dict[str, Any]) -> ArticleProcessStep:
    """Ein Modul an die Vorlage anhängen. Hebt den Versionsstempel.

    Wie im Auftrag gilt: **Definitionen rasten ein** (§6.5). Es gibt keinen Pfad, der ein
    bestehendes Modul ändert – nur anlegen und löschen. Darum genügt der Zähler als
    Version: jede Mutation ist eine Anlage oder eine Löschung.
    """
    if article.status != "draft":
        raise HTTPException(
            status_code=409,
            detail=(
                "Der Erzeugungsprozess ist eingefroren – ein freigegebener Artikel wird "
                "nicht mehr umgebaut. Für eine Änderung braucht es einen neuen Artikel."
            ),
        )
    module_type = data.get("module_type")
    if module_type not in MODULE_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unbekannter Modultyp «{module_type}». Erlaubt: {', '.join(MODULE_TYPES)}.",
        )
    name = (data.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Ein Modul braucht einen Namen.")
    before = st.assert_known(data["status_before"], field="Vorher-Status")
    after = st.assert_known(data["status_after"], field="Nachher-Status")

    last = steps_of(db, article)
    step = ArticleProcessStep(
        article_id=article.id,
        position=(last[-1].position + 1) if last else 1,
        module_type=module_type,
        name=name[:120],
        status_before=before,
        status_after=after,
    )
    db.add(step)
    article.process_version = int(article.process_version or 0) + 1
    return step


def delete_step(db: Session, article: Article, step_id: int) -> None:
    """Ein Modul aus der Vorlage entfernen. Hebt den Versionsstempel."""
    if article.status != "draft":
        raise HTTPException(
            status_code=409,
            detail="Der Erzeugungsprozess ist eingefroren – ein freigegebener Artikel wird nicht mehr umgebaut.",
        )
    step = (
        db.query(ArticleProcessStep)
        .filter(
            ArticleProcessStep.article_id == article.id,
            ArticleProcessStep.id == step_id,
            ArticleProcessStep.is_active.is_(True),
        )
        .first()
    )
    if step is None:
        raise HTTPException(status_code=404, detail="Dieses Modul gibt es nicht.")
    step.is_active = False
    article.process_version = int(article.process_version or 0) + 1
    db.flush()
    # Positionen schliessen, damit die Reihenfolge lückenlos bleibt (sie ist die Kante
    # des Prozesses, keine Sortierhilfe).
    for i, row in enumerate(steps_of(db, article), start=1):
        row.position = i


def mirror(db: Session, article: Article) -> list[dict[str, Any]]:
    """Die Vorlage als **Kopie** – Werte, kein Verweis, mit Versionsstempel.

    Das Ergebnis geht unverändert in ``process_steps`` des Auftrags. Ist die Vorlage
    leer, ist das kein leeres Ergebnis, sondern ein Fehler beim Aufrufer: ein
    Erzeugungsauftrag ohne Prozess kann nichts erzeugen.
    """
    version = int(article.process_version or 0)
    return [
        {
            "module_type": s.module_type,
            "name": s.name,
            "status_before": s.status_before,
            "status_after": s.status_after,
            "source_article_id": article.id,
            "source_version": version,
        }
        for s in steps_of(db, article)
    ]
