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

from ..domain import chain, modules
from ..models import Article, ArticleProcessStep


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


def create_steps(db: Session, article: Article, raw: list[dict[str, Any]]) -> list[ArticleProcessStep]:
    """Den Erzeugungsprozess eines Artikels anlegen — **in einem Zug mit dem Artikel**.

    Es gibt keinen Pfad, der ihn danach ändert: der Artikel entsteht erst mit seiner
    Freigabe, und ab da ist er eingefroren (§6.5). Ein «Modul nachträglich hinzufügen»
    wäre eine Tür in einen Datensatz, der schon Aufträge speisen kann.

    Der **Übergang wird nicht übernommen, sondern abgeleitet**: er gehört zum Modultyp
    (``domain/modules``). Was der Entwurf schickt, ist Typ und Konfiguration – einen
    **Namen** gibt es nicht mehr (Testnotiz #682): wie ein Modul heisst, sagt sein Typ.
    """
    if not raw:
        raise HTTPException(
            status_code=400,
            detail=("Ohne Prozessschrittmodul kann dieser Artikel nichts erzeugen. "
                    "Mindestens eines ist Pflicht."),
        )
    out: list[ArticleProcessStep] = []
    for position, data in enumerate(raw, start=1):
        module = modules.get(data.get("module_type"))
        config = module.clean_config(data.get("config"))
        # **Was nur im Auftrag gilt, gilt hier nicht** (``Module.template_problem``): eine
        # Vorlage ist zeitlos, und eine Angabe, die auf ein konkretes Ding zeigt, ist beim
        # zweiten Auftrag falsch. Die Vorgabe ist «alles gilt überall» – ein neuer
        # Modultyp erbt sie, ohne eine Zeile dafür.
        problem = module.template_problem(config)
        if problem:
            raise HTTPException(status_code=400, detail=problem)
        step = ArticleProcessStep(
            article_id=article.id,
            position=position,
            module_type=module.key,
            status_before=module.status_before,
            # Erst prüfen, dann ableiten: beim Aussondern hängt das Nachher an der
            # Ausprägung (``Module.status_after_for``).
            status_after=module.status_after_for(config),
            config=config,
        )
        db.add(step)
        out.append(step)
    # **Dieselbe Kettenregel wie beim Auftrag** (``domain/chain``). Sie hier zu prüfen ist
    # kein Extra, sondern der richtige Zeitpunkt: der Artikel entsteht mit seiner Freigabe
    # und ist danach eingefroren – eine Vorlage, deren Kette nicht schliesst, wäre erst
    # beim ersten Auftrag aufgefallen, und dann liesse sie sich nicht mehr reparieren.
    chain.assert_closes([
        {"module_type": s.module_type, "status_before": s.status_before,
         "status_after": s.status_after}
        for s in out
    ])
    # Der Stempel zählt die Fassungen der Vorlage. Sie entsteht genau einmal – die 1 ist
    # damit keine Zählung, sondern die Aussage «erste und einzige Fassung».
    article.process_version = 1
    return out


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
            "status_before": s.status_before,
            "status_after": s.status_after,
            # **Die Konfiguration muss mit.** Ohne sie käme ein Datenerfassungs-Modul
            # ohne seine Erfassungspunkte im Auftrag an – es stünde im Prozess und hätte
            # nichts zu erfassen. Eine Kopie, die das Wesentliche weglässt, ist keine.
            "config": dict(s.config) if s.config else None,
            "source_article_id": article.id,
            "source_version": version,
        }
        for s in steps_of(db, article)
    ]
