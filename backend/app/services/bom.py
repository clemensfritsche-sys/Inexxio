"""**Die geplante Stückliste** — wer nennt wen, und was davon ist ausser Betrieb.

Zwei Fragen über **einen** Graphen: die Kanten sind die Zeilen der Verbrauchsmodule in
den **Artikel-Vorlagen** (``article_process_steps.config.lines``).

``used_in``        aufwärts — welche Artikel nennen mich in ihrer Stückliste?
``retired_inputs`` abwärts — welche **ausser Betrieb genommenen** Artikel stecken in
                   meiner Stückliste, direkt oder über Stufen?

**Bewusst getrennt von ``genealogy``.** Das ist die *tatsächliche* Stückliste – was aus
dem Log hervorgeht, woraus ein konkretes Stück wirklich besteht. Diese hier ist der
**Plan**: was die Vorlage vorsieht. Plan und Tatsache sind zwei Fragen, und ein Modul für
beide wäre die erste Stelle, an der jemand sie verwechselt.

**Nur Vorlagen, nie Auftrags-Schritte.** Der Prozess eines laufenden Auftrags ist eine
eingefrorene Kopie (PROCESS_CORE §6.5); ihn hier mitzulesen hiesse, einen Auftrag von
aussen zu bewerten, dessen Definition längst festgeschrieben ist.

**Es wird gemeldet, nicht verboten.** Ein Artikel, dessen Stückliste einen ausser Betrieb
genommenen nennt, bleibt **erzeugbar**, solange Restbestand da ist – das ist die
Wirklichkeit, und sie zu verbieten wäre eine Regel gegen den Betrieb. ``may_create``
bleibt darum unangetastet; was hier entsteht, ist eine **Auskunft**. Genau dieselbe
Haltung wie bei ``StepNeed``: sagen, was fehlt, und den Menschen entscheiden lassen.

**Zyklensicher.** Der Stücklisten-Graph ist nirgends gegen Kreise geschützt (die einzige
Prüfung, ``process._assert_no_self_consumption``, gilt je Auftrag, nicht über Artikel
hinweg). Beim Lesen darum ``seen`` + Tiefenschranke – dasselbe zweite Netz wie in
``places``: was es nicht gibt, muss man beim Lesen abfangen.
"""

from dataclasses import dataclass
from typing import Iterable, Optional

from sqlalchemy import cast
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Session

from ..domain import modules, statuses as st
from ..models import Article, ArticleProcessStep

#: Wie tief abwärts gelesen wird. Eine echte Stückliste ist drei, vier Stufen tief; wer
#: zehn erreicht, hat einen Kreis, und dann ist eine gekappte Antwort besser als eine
#: Ansicht, die hängt.
MAX_DEPTH = 10


@dataclass(frozen=True)
class ArticleRef:
    """Ein Artikel, wie ihn eine Antwort nennt: Nummer, Name, Zustand."""

    object_id: int
    name: str
    status: str


@dataclass(frozen=True)
class RetiredInput:
    """Ein **ausser Betrieb genommener** Artikel in meiner Stückliste.

    ``via`` ist der Weg dorthin – die Artikel zwischen mir und ihm, von mir aus gesehen.
    Leer heisst: er steht direkt in meiner Stückliste. Ohne diese Angabe wüsste bei einer
    dreistufigen Stückliste niemand, *wo* das Problem sitzt.

    ``replaced_by`` nennt den Nachfolger, wenn es einen gibt – damit steht die **Lösung**
    dort, wo das Problem gemeldet wird.
    """

    article: ArticleRef
    via: tuple[ArticleRef, ...] = ()
    replaced_by: Optional[ArticleRef] = None


def _ref(article: Article) -> ArticleRef:
    return ArticleRef(object_id=article.object_id, name=article.name,
                      status=article.status)


def _lines_of(steps: Iterable[ArticleProcessStep]) -> set[int]:
    """Die Artikel-Objektnummern, die diese Vorlagen-Schritte verbrauchen.

    Gelesen über ``modules.lines_of`` – die eine Lesestelle für eine Stückliste. Ein
    Schritt ohne Stückliste liefert nichts, also braucht es hier keine Frage nach dem
    Modultyp (dieselbe Bauart wie ``consumption.needs``).
    """
    return {row["article"] for step in steps for row in modules.lines_of(step.config)}


def _steps_of(db: Session, article_ids: Iterable[int]) -> dict[int, list[ArticleProcessStep]]:
    """Die Vorlagen-Schritte mehrerer Artikel — **eine** Abfrage, kein N+1."""
    ids = {int(a) for a in article_ids}
    if not ids:
        return {}
    out: dict[int, list[ArticleProcessStep]] = {}
    for step in db.query(ArticleProcessStep).filter(
        ArticleProcessStep.article_id.in_(ids)
    ):
        out.setdefault(step.article_id, []).append(step)
    return out


def used_in(db: Session, article: Article) -> list[ArticleRef]:
    """**Wer nennt mich in seiner Stückliste?** — aufsteigend nach Objektnummer.

    Die Antwort auf «was mache ich kaputt, wenn ich diesen Artikel ausser Betrieb
    nehme» – und sie steht am Datensatz, nicht in einem Dialog: ein Dialog zeigt sie
    einmal, dem, der klickt; der Datensatz zeigt sie immer, allen.

    **Gefiltert wird in der Datenbank** (JSONB-Containment ``@>``), nicht im Python:
    sonst müsste jede Anzeige eines Artikels sämtliche Vorlagen des Hauses laden, um
    danach fast alle wegzuwerfen.
    """
    mine = article.object_id
    rows = (
        db.query(Article)
        .join(ArticleProcessStep, ArticleProcessStep.article_id == Article.id)
        .filter(
            Article.is_active.is_(True),
            Article.object_id != mine,   # wer sich selbst nennt, ist kein Verwender
            ArticleProcessStep.config.contains(
                cast({modules.Verbrauch.LINES: [{"article": mine}]}, JSONB)
            ),
        )
        .all()
    )
    # Ein Artikel kann mich in **mehreren** Modulen nennen; genannt wird er einmal.
    found = {a.object_id: a for a in rows}
    return [_ref(found[nr]) for nr in sorted(found)]


def _walk_down(db: Session, article: Article) -> dict[int, tuple[Article, tuple[ArticleRef, ...]]]:
    """Die ganze Stückliste abwärts — je Artikel **einmal**, auf dem kürzesten Weg.

    Breite zuerst: zweimal dieselbe Schraube über zwei Pfade ist eine Aussage, keine
    zwei, und der kürzeste Weg ist der, den ein Mensch sucht.
    """
    out: dict[int, tuple[Article, tuple[ArticleRef, ...]]] = {}
    seen: set[int] = {article.object_id}
    # Je Ebene: die Artikel, deren Stückliste noch zu lesen ist, mit dem Weg dorthin.
    frontier: list[tuple[Article, tuple[ArticleRef, ...]]] = [(article, ())]

    for _ in range(MAX_DEPTH):
        if not frontier:
            break
        steps = _steps_of(db, [a.id for a, _ in frontier])
        paths: dict[int, tuple[ArticleRef, ...]] = {}
        for owner, path in frontier:
            for number in _lines_of(steps.get(owner.id, [])):
                if number not in seen:
                    paths.setdefault(number, path)
        if not paths:
            break
        seen |= set(paths)
        rows = sorted(
            db.query(Article).filter(Article.object_id.in_(set(paths))).all(),
            key=lambda a: a.object_id,
        )
        for found in rows:
            out[found.object_id] = (found, paths[found.object_id])
        # **Auch unter einem ausser Betrieb genommenen wird weitergelesen**: seine eigene
        # Stückliste kann eine zweite Lücke enthalten, und die verschwindet nicht dadurch,
        # dass eine Stufe darüber schon eine gemeldet ist.
        frontier = [(a, paths[a.object_id] + (_ref(a),)) for a in rows]
    return out


def retired_inputs(db: Session, article: Article) -> list[RetiredInput]:
    """**Welche ausser Betrieb genommenen Artikel stecken in meiner Stückliste?**

    Transitiv: nennt meine Stückliste ein Getriebe und dessen Stückliste eine ausser
    Betrieb genommene Schraube, ist das **meine** Auskunft – der Weg dorthin steht in
    ``via``. Die Kaskade entsteht damit beim **Lesen** und reicht genau so weit, wie
    jemand hinschaut; markiert oder gespeichert wird nichts.
    """
    below = _walk_down(db, article)
    retired = {
        nr: (found, path) for nr, (found, path) in below.items()
        if found.status != st.FREIGEGEBEN
    }
    if not retired:
        return []

    # Die Nachfolger in **einer** Abfrage – sie stehen erst fest, wenn klar ist, wer
    # überhaupt gemeldet wird; ein Nachfolger kann selbst ausserhalb der Stückliste liegen.
    wanted = {found.replaced_by_id for found, _ in retired.values() if found.replaced_by_id}
    successors = {
        a.object_id: _ref(a)
        for a in db.query(Article).filter(Article.object_id.in_(wanted)).all()
    } if wanted else {}

    return [
        RetiredInput(
            article=_ref(found),
            via=path,
            replaced_by=successors.get(found.replaced_by_id or 0),
        )
        for _, (found, path) in sorted(retired.items())
    ]
