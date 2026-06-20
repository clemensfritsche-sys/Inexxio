"""Pflicht-Bewegungen rund um Beschaffungsschritte (automatisch, nicht löschbar).

Leitprinzip der Modul-Trennung: **Purchase** ist rein kaufmännisch, **Bewegung**
besorgt jeden physischen Transport. Damit eine Beschaffung prozesssicher ist,
flankiert das System jeden ``purchase``-Schritt automatisch mit Pflicht-Bewegungen
(``locked=True``):

- **nach** der Beschaffung immer eine Bewegung (Wareneingang bzw. Rückversand),
- **vor** der Beschaffung eine Bewegung, wenn sie nicht der erste Schritt ist
  (Versand zum Lieferanten – Stichwort Lohnveredelung).

Die Pflicht-Bewegungen sind nicht löschbar/editierbar und werden bei jeder
Strukturänderung neu abgeleitet und positioniert (idempotent, selbstheilend).
"""

from sqlalchemy.orm import Session

from ..models import ArticleProcessStep


def _plan(step_types: list[str]) -> list[str | None]:
    """Reine Soll-Sequenz aus den Nutzer-Schritttypen; ``None`` = Pflicht-Bewegung.

    Vor jeder **nicht ersten** Beschaffung (Versand) und nach jeder Beschaffung
    (Wareneingang/Rückversand) eine Bewegung; zwischen zwei aufeinanderfolgenden
    Beschaffungen genügt eine."""
    seq: list[str | None] = []
    for i, t in enumerate(step_types):
        if t == "purchase" and i > 0 and not (seq and seq[-1] is None):
            seq.append(None)
        seq.append(t)
        if t == "purchase":
            seq.append(None)
    return seq


def _active_steps(db: Session, article_id: int) -> list[ArticleProcessStep]:
    return (
        db.query(ArticleProcessStep)
        .filter(ArticleProcessStep.article_id == article_id, ArticleProcessStep.is_active == True)
        .order_by(ArticleProcessStep.position, ArticleProcessStep.id)
        .all()
    )


def sync_locked_movements(db: Session, article_id: int) -> None:
    """Pflicht-Bewegungen rund um die Beschaffungsschritte herstellen (idempotent).

    Schreibt nur (flush); der Aufrufer committet. Renummeriert die Positionen 1..N
    in der Reihenfolge der Nutzer-Schritte mit eingefügten Pflicht-Bewegungen."""
    steps = _active_steps(db, article_id)
    user_steps = [s for s in steps if not s.locked]
    locked_pool = [s for s in steps if s.locked]
    if not any(s.step_type == "purchase" for s in user_steps) and not locked_pool:
        return  # häufigster Fall: nichts zu tun

    plan = _plan([s.step_type for s in user_steps])
    needed = sum(1 for x in plan if x is None)
    reuse = locked_pool[:needed]
    for extra in locked_pool[needed:]:
        extra.is_active = False
    while len(reuse) < needed:
        m = ArticleProcessStep(article_id=article_id, step_type="movement",
                               mode="supplier", locked=True, position=0)
        db.add(m)
        reuse.append(m)
    db.flush()

    ui = li = 0
    for pos, x in enumerate(plan, start=1):
        if x is None:
            node, li = reuse[li], li + 1
        else:
            node, ui = user_steps[ui], ui + 1
        node.position = pos
