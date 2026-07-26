"""Pflicht-Bewegungen rund um Beschaffungsschritte (automatisch, nicht löschbar).

Leitprinzip der Modul-Trennung: **Purchase** ist rein kaufmännisch, **Bewegung**
besorgt jeden physischen Transport. Damit eine Beschaffung prozesssicher ist,
flankiert das System jeden ``purchase``-Schritt automatisch mit Pflicht-Bewegungen
(``locked=True``):

- **nach** der Beschaffung ein **Wareneingang** – sein Ziel ist **konfigurierbar** wie
  bei einer regulären Bewegung (festes Ziel → per Scan erzwungen; leer → frei beim
  Einlagern),
- **nach** einem Verkauf ein **Versand zum Kunden** (Ziel = Kunde des Verkaufs) – ausser
  bei einer Retoure (dort ist der Verkauf eine Gutschrift).

**Jedes Modul steht für sich:** ein Schritt verhält sich an jeder Position gleich. Die
frühere positionsabhängige Regel («Versand zum Lieferanten» vor einer nicht-ersten
Lieferanten-Beschaffung) ist entfallen – Materialtransport zum Lieferanten bildet man mit
einem normalen **Bewegungs**-Schritt ab (sichtbar, verschiebbar, löschbar). Alt-Bestand
solcher gesperrten Schritte wird beim nächsten Sync automatisch deaktiviert.

Die Pflicht-Bewegungen sind nicht löschbar und werden bei jeder Strukturänderung
neu abgeleitet/positioniert (idempotent, selbstheilend).
"""

from sqlalchemy.orm import Session

from ..models import ArticleProcessStep, Order


def _plan(steps: list[tuple[str, str | None]], skip_customer_shipping: bool = False) -> list[str]:
    """Reine Soll-Sequenz aus (Schritttyp, Modus). Markierungen ``"wareneingang"`` /
    ``"versandkunde"`` = Pflicht-Bewegung, sonst Nutzer-Schritttyp.

    **Jedes Modul steht für sich** – ein Schritt verhält sich an jeder Position gleich.
    Nur die zwei **physisch zwingenden** Bewegungen werden ergänzt:

    - Wareneingang **nach** jeder Beschaffung (die Ware muss ankommen);
    - Versand zum Kunden **nach** jedem Verkauf (die Ware muss zum Kunden) – ausser bei einer
      **Retoure**: dort ist der Verkauf eine **Gutschrift** (kein Versand; die Ware kommt über
      den ``return``-Schritt herein), ``skip_customer_shipping`` unterdrückt die Bewegung.

    *Entfallen (Juli 2026):* der Pflicht-«Versand zum Lieferanten» vor einer **nicht ersten**
    Lieferanten-Beschaffung. Er war die einzige **positionsabhängige** Regel im System – dieselbe
    Beschaffung erzeugte an Position 1 keinen, ab Position 2 einen Zusatzschritt – und liess sich
    zudem nicht durch eine selbst angelegte Bewegung ersetzen (die Unterdrückung prüfte nur die
    Pflicht-Marker, nie einen echten ``movement``-Schritt → zwei Bewegungen hintereinander).
    Wer Material zum Lieferanten schickt (Lohnveredelung), legt dafür einen normalen
    **Bewegungs**-Schritt an – sichtbar, verschiebbar, löschbar."""
    seq: list[str] = []
    for t, _mode in steps:
        seq.append(t)
        if t == "purchase":
            seq.append("wareneingang")
        if t == "sale" and not skip_customer_shipping:
            seq.append("versandkunde")
    return seq


def _active_steps(db: Session, *, article_id: int | None, order_id: int | None) -> list[ArticleProcessStep]:
    q = db.query(ArticleProcessStep).filter(ArticleProcessStep.is_active == True)
    if order_id is not None:
        q = q.filter(ArticleProcessStep.order_id == order_id)
    else:
        q = q.filter(ArticleProcessStep.article_id == article_id,
                     ArticleProcessStep.order_id.is_(None))
    return q.order_by(ArticleProcessStep.position, ArticleProcessStep.id).all()


def sync_locked_movements(db: Session, *, article_id: int | None = None,
                          order_id: int | None = None) -> None:
    """Pflicht-Bewegungen rund um die Beschaffungsschritte eines Prozesses (Artikel-
    oder Auftrags-Prozess) herstellen (idempotent).

    Schreibt nur (flush); der Aufrufer committet. Renummeriert die Positionen 1..N.
    Versand-Ziele werden (neu) auf den Lieferanten gesetzt; Wareneingang-Ziele bleiben
    wie vom Nutzer definiert erhalten."""
    steps = _active_steps(db, article_id=article_id, order_id=order_id)
    user_steps = [s for s in steps if not s.locked]
    locked = [s for s in steps if s.locked]
    if not any(s.step_type in ("purchase", "sale") for s in user_steps) and not locked:
        return  # häufigster Fall: nichts zu tun

    # Rollen-getrennte Pools (positionsunabhängig): Versand-zum-Kunden ist via mode='customer'
    # getaggt, alles übrige Gesperrte ist ein Wareneingang. So gehen Ziele beim Re-Sync nicht
    # verloren. Alt-Bestand «Versand zum Lieferanten» (trug ein user-Ziel) wird von keinem
    # Plan-Eintrag mehr belegt und darum unten automatisch deaktiviert.
    versandkunde_pool = [s for s in locked if s.mode == "customer"]
    wareneingang_pool = [s for s in locked if s.mode != "customer" and s.target_location_type != "user"]

    # Retoure-Unter-Auftrag: der Verkauf ist eine Gutschrift → KEIN Pflicht-Versand zum Kunden.
    credit_context = False
    if order_id is not None:
        row = db.query(Order.reason).filter(Order.id == order_id).first()
        credit_context = bool(row and row[0] == "return")
    plan = _plan([(s.step_type, s.mode) for s in user_steps], skip_customer_shipping=credit_context)
    final: list[list] = []   # [node_or_step, role]
    ui = wi = ki = 0
    for entry in plan:
        if entry == "wareneingang":
            node = wareneingang_pool[wi] if wi < len(wareneingang_pool) else None
            wi += 1
            final.append([node, "wareneingang"])
        elif entry == "versandkunde":
            node = versandkunde_pool[ki] if ki < len(versandkunde_pool) else None
            ki += 1
            final.append([node, "versandkunde"])
        else:
            final.append([user_steps[ui], "user"])
            ui += 1

    for item in final:
        if item[1] != "user" and item[0] is None:
            item[0] = ArticleProcessStep(
                article_id=article_id, order_id=order_id, step_type="movement",
                mode="customer" if item[1] == "versandkunde" else "supplier",
                locked=True, position=0)
            db.add(item[0])
    db.flush()

    used = {item[0].id for item in final if item[1] != "user"}
    for s in locked:
        if s.id not in used:
            s.is_active = False

    for idx, (node, _role) in enumerate(final):
        node.position = idx + 1
        # Ziele bleiben unverändert: Wareneingang vom Nutzer gesetzt, Versand zum Kunden
        # beim Versand aus dem Verkauf abgeleitet.
