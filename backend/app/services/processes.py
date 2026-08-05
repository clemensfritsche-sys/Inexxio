"""Prozess = die geordnete Schrittliste eines **Artikels** (wie etwas entsteht) oder
eines **Auftrags** (individueller Ablauf auf bestehenden Instanzen).

Es gibt KEIN eigenständiges Prozess-Objekt mehr (keine Objektnummer, kein eigener
Lebenszyklus, keine n:m-Verknüpfung). Ein Schritt (``ArticleProcessStep``) hängt
entweder am Artikel (``article_id``) oder am Auftrag (``order_id``).
"""

from sqlalchemy.orm import Session

from ..models import ArticleProcessStep


def article_steps(db: Session, article_id: int | None) -> list[ArticleProcessStep]:
    """Die aktiven Schritte des Artikel-Prozesses (wie der Artikel entsteht)."""
    if not article_id:
        return []
    return (
        db.query(ArticleProcessStep)
        .filter(ArticleProcessStep.article_id == article_id,
                ArticleProcessStep.order_id.is_(None),
                ArticleProcessStep.is_active == True)
        .order_by(ArticleProcessStep.position, ArticleProcessStep.id)
        .all()
    )


def order_custom_steps(db: Session, order_id: int | None) -> list[ArticleProcessStep]:
    """Die aktiven Schritte des individuellen Auftrags-Prozesses (CUSTOM-Modus)."""
    if not order_id:
        return []
    return (
        db.query(ArticleProcessStep)
        .filter(ArticleProcessStep.order_id == order_id,
                ArticleProcessStep.is_active == True)
        .order_by(ArticleProcessStep.position, ArticleProcessStep.id)
        .all()
    )


def has_custom_steps(db: Session, order) -> bool:
    """CUSTOM-Modus? – der Auftrag trägt eigene Prozessschritte (auf vorhandene Instanzen)."""
    return (
        db.query(ArticleProcessStep.id)
        .filter(ArticleProcessStep.order_id == order.id,
                ArticleProcessStep.is_active == True)
        .first()
        is not None
    )


#: Was ein Modul braucht, um im Auftrag überhaupt etwas tun zu können – je Typ EINE
#: Bedingung, hier und nirgends sonst. Ein Modul entsteht **leer** und wird im Fluss
#: konfiguriert (Testnotiz #635); geprüft wird darum bei der **Freigabe**, dem Gate, ab
#: dem der Prozess wirklich läuft.
#:
#: Gefordert wird nur, was WIRKLICH nicht laufen kann. Eine Datenerfassung ohne Maske
#: steht bewusst nicht hier: sie erfasst dann ein synthetisches Gut/Schlecht
#: (``services/inspection.py``) – der Schritt ist also ausführbar, nur karg. Das Formular
#: legt ihn ohnehin mit einem Feld an; ihn hier zu blockieren wäre eine Strenge, die die
#: Engine gar nicht braucht.
_REQUIREMENTS = {
    "resource": (lambda s: bool(s.resource_lines),
                 "Ressource: mindestens eine Zeile"),
}


def incomplete_steps(steps) -> list[str]:
    """**Was fehlt, bevor dieser Prozess laufen kann?** – leere Liste = startklar.

    Sagt es beim Namen, statt nur «nein»: eine Datenerfassung ohne Erfassungsfeld böte im
    Auftrag nichts zu erfassen, ein Ressourcen-Schritt ohne Zeile nichts zu holen – der
    Auftrag käme an genau dieser Stelle nicht weiter.

    Die Bezugsquelle der Beschaffung steht bewusst NICHT hier: sie hängt am Artikel
    (Schritt-Quelle ODER Artikel-Standard) und wird darum dort geprüft, wo der Artikel
    bekannt ist (``purchase.has_source``)."""
    out: list[str] = []
    for s in steps:
        rule = _REQUIREMENTS.get(s.step_type)
        if rule and not rule[0](s):
            out.append(rule[1])
    return sorted(set(out))
