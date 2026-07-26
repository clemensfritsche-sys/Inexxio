"""Begleit-Bewegungen rund um Beschaffung und Verkauf – **Vorschlag, kein Zwang**.

Leitprinzip der Modul-Trennung: **Purchase** ist rein kaufmännisch, **Sale** ist die
Geld-Seite, **Bewegung** besorgt jeden physischen Transport. Damit nach einer Beschaffung
die Ware ankommt und nach einem Verkauf zum Kunden geht, **sät** das System beim Anlegen
eines ``purchase``- bzw. ``sale``-Schritts EINMAL eine passende Bewegung dahinter.

**Gesät, nicht erzwungen** (Juli 2026): Diese Bewegungen sind ganz normale Schritte –
löschbar, verschiebbar, editierbar wie jeder andere. Wer sie nicht braucht (Abholung
durch den Kunden, Streckengeschäft, digitale Lieferung), löscht sie; sie kommen **nicht**
wieder. Vorher waren sie ``locked`` und wurden bei jeder Strukturänderung neu abgeleitet
und umpositioniert – ein Schritt, den der Prozess-Editor anzeigte, aber niemand bewegen
oder entfernen konnte. Das widersprach dem Grundsatz, dass ein Prozess das abbildet, was
tatsächlich passiert, und nicht das, was das System für zwingend hält.

**Einmalig heisst einmalig:** Gesät wird nur, wenn zu einem Auslöser-Schritt noch NIE eine
Begleit-Bewegung existierte – auch eine vom Nutzer gelöschte (``is_active=False``) zählt
als «gab es schon». So respektiert das System die Entscheidung des Nutzers dauerhaft.

**Die Rolle bleibt, die Sperre fällt.** Aus der früheren Sperr-Spalte ``locked`` ist
``companion`` geworden (Migration 079): sie sagt nur noch «dieser Schritt wurde als
Begleiter eines Handels-Schritts gesät» und trägt zwei echte Fachwirkungen –

* ``mode='customer'`` → Versand zum Kunden: Ziel ist der Kunde des Verkaufs
  (``movement.record_movement``);
* Begleiter sind von der **Fehlmengen-Prüfung ausgenommen** (``process.step_shortfalls``),
  weil sie genau die eben verkaufte bzw. eben beschaffte Ware bewegen und sonst dauerhaft
  «blockiert» wären.

Warum eine eigene Spalte und nicht ``mode``: dessen Default ist ``'supplier'``, jede vom
Nutzer angelegte Bewegung würde sonst fälschlich als Wareneingang gelten.
"""

from sqlalchemy.orm import Session

from ..models import ArticleProcessStep, Order

# Auslöser → Rolle der gesäten Begleit-Bewegung.
#   purchase → Wareneingang danach (die Ware muss ankommen)
#   sale     → Versand zum Kunden danach (die Ware muss zum Kunden)
_COMPANION_MODE = {"purchase": "supplier", "sale": "customer"}

# Rollen-Markierungen, die eine Bewegung als Begleiter eines Handels-Schritts ausweisen.
COMPANION_MODES = ("supplier", "customer")


def is_companion(step) -> bool:
    """Ist dieser Schritt eine gesäte Begleit-Bewegung (Wareneingang / Versand zum Kunden)?

    Die EINE Stelle, die das beantwortet. Sie liest die Spalte ``companion`` – NICHT
    ``mode``: dessen Default ist ``'supplier'``, jede vom Nutzer angelegte Bewegung trüge
    die Rolle sonst fälschlich. Relevant für die Fehlmengen-Prüfung
    (``process.step_shortfalls``) und das feste Versand-Ziel (``movement.record_movement``)."""
    return bool(getattr(step, "companion", False))


def _seeded_modes(db: Session, *, article_id: int | None, order_id: int | None) -> set[str]:
    """Rollen, für die schon einmal eine Begleit-Bewegung gesät wurde – **inklusive der
    vom Nutzer gelöschten** (``is_active=False``). Genau das macht das Säen einmalig:
    ein entfernter Wareneingang wird nicht wieder angelegt."""
    q = db.query(ArticleProcessStep.mode).filter(ArticleProcessStep.companion == True,
                                                 ArticleProcessStep.mode.in_(COMPANION_MODES))
    if order_id is not None:
        q = q.filter(ArticleProcessStep.order_id == order_id)
    else:
        q = q.filter(ArticleProcessStep.article_id == article_id,
                     ArticleProcessStep.order_id.is_(None))
    return {row[0] for row in q.all()}


def seed_companion_movements(db: Session, *, article_id: int | None = None,
                             order_id: int | None = None) -> None:
    """Zu neuen Beschaffungs-/Verkaufs-Schritten **einmalig** eine Begleit-Bewegung anlegen.

    Idempotent, aber NICHT selbstheilend: was der Nutzer gelöscht hat, bleibt gelöscht.
    Positionen bestehender Schritte werden nicht angetastet – die gesäte Bewegung wird
    direkt hinter ihren Auslöser gesetzt (der Editor vergibt Positionen in Zweierschritten,
    also ist dazwischen Platz).

    Schreibt nur (flush); der Aufrufer committet."""
    steps = (
        db.query(ArticleProcessStep)
        .filter(ArticleProcessStep.is_active == True,
                (ArticleProcessStep.order_id == order_id) if order_id is not None
                else ((ArticleProcessStep.article_id == article_id)
                      & (ArticleProcessStep.order_id.is_(None))))
        .order_by(ArticleProcessStep.position, ArticleProcessStep.id)
        .all()
    )

    # Retoure-Unter-Auftrag: der «Verkauf» ist eine Gutschrift – die Ware kommt herein,
    # nicht heraus. Kein Versand zum Kunden säen.
    credit_context = False
    if order_id is not None:
        row = db.query(Order.reason).filter(Order.id == order_id).first()
        credit_context = bool(row and row[0] == "return")

    seeded = _seeded_modes(db, article_id=article_id, order_id=order_id)
    for s in steps:
        mode = _COMPANION_MODE.get(s.step_type)
        if not mode or mode in seeded:
            continue
        if mode == "customer" and credit_context:
            continue
        db.add(ArticleProcessStep(article_id=article_id, order_id=order_id,
                                  step_type="movement", mode=mode, companion=True,
                                  position=(s.position or 0) + 1))
        seeded.add(mode)
    db.flush()
