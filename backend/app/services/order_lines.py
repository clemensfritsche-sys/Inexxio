"""Positionen eines **Mehrpositionen-Auftrags** (``orders.article_id IS NULL``).

Reiner Lese-Helfer – die Anlage lebt in ``routers/orders.py: create_order`` (dort
entsteht die Zeile zusammen mit dem Auftrag und ggf. fixierten Instanzen)."""

from decimal import Decimal

from sqlalchemy.orm import Session

from ..models import Order, OrderLine
from .quantity import qty_sum, to_qty


def lines_for(db: Session, order: Order) -> list[OrderLine]:
    """Aktive Positionen eines Mehrpositionen-Auftrags, in Reihenfolge. Leer für einen
    gewöhnlichen Einzel-Artikel-Auftrag (``order.article_id`` gesetzt)."""
    if order.article_id is not None:
        return []
    return (
        db.query(OrderLine)
        .filter(OrderLine.order_id == order.id, OrderLine.is_active == True)
        .order_by(OrderLine.position, OrderLine.id)
        .all()
    )


def is_multiline(order: Order) -> bool:
    """Mehrpositionen-Auftrag? – erkennbar allein daran, dass ``article_id`` fehlt
    (Anker für den Einzel-Artikel-Fall)."""
    return order.article_id is None


def declared_quantity(db: Session, order: Order) -> Decimal:
    """Die **deklarierte** Menge (``Decimal``): ``order.quantity`` beim Einzel-Artikel-
    Auftrag, sonst die Summe der Positionsmengen. Das ist eine **Aussage über die Anlage**
    des Auftrags – bei einem festen Subjekt die Eröffnungsmenge («auf 4 Stück eröffnet»),
    die auch nach dem Abschluss noch gilt. Wie viel er JETZT bearbeitet, sagt
    ``effective_quantity``."""
    if order.quantity is not None:
        return to_qty(order.quantity)
    return qty_sum(l.quantity for l in lines_for(db, order))


def effective_quantity(db: Session, order: Order) -> Decimal:
    """**Wie viel bearbeitet dieser Auftrag?** – artikelunabhängig, die EINE Antwort.
    Grundlage für Schritte, die auf «der ganzen Menge» arbeiten (Ressourcen-Bedarf und
    -Reservierung, Stichprobenumfang der Datenerfassung, Bereitstellung).

    Die Antwort hängt an derselben Unterscheidung wie die Unterdeckung (ADR 008):

    * **Regulärer Auftrag** → seine **Zusage**. Sie ist eine Entscheidung, darum gespeichert,
      und sie schrumpft nicht, nur weil gerade ein Stück in Klärung ist: die Komponenten
      werden für das Versprochene beschafft, sonst müsste der Auftrag sie ein zweites Mal
      anfordern, sobald die Ausleihe zurückkommt.
    * **Festes Subjekt** (Abweichung · Retoure · Bereitstellung) → seine **Arbeitsmenge**:
      was ihm von seinen Instanzen noch gehört (``subject.held_quantity`` – dieselbe eine
      Antwort, aus der auch der Prüfumfang kommt). Es beschafft nichts und verspricht
      nichts; nimmt ihm ein anderer Auftrag ein Stück weg, hat es schlicht weniger zu tun.

    Ohne Instanzen (Entwurf, Vorschau) bleibt die Deklaration – dort gibt es noch nichts,
    woran sich die Arbeitsmenge ablesen liesse.

    Gemessener Befund davor: eine Abweichung, die auf 4 Stück eröffnet wurde und eines davon
    an ihre eigene Abweichung verloren hat, verlangte weiter Komponenten für 4 (8 statt 6
    Schrauben). Das ist keine Anzeigefrage – der Überschuss war für jeden anderen Auftrag
    gesperrt und erzeugte dort eine Fehlmenge, die es nicht gab.

    *Die bei der **Freigabe** gebuchte Reservierung bleibt unberührt: damals hielt der Auftrag
    die volle Menge, sie war also richtig. Der Überschuss löst sich mit seinem Abschluss.*
    """
    from .subject import is_fixed_subject
    if is_fixed_subject(order):
        from .subject import held_quantity, order_active_instances
        insts = order_active_instances(db, order)
        if insts:
            return qty_sum(held_quantity(order, i) for i in insts)
    return declared_quantity(db, order)
