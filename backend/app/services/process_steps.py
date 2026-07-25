"""Pflicht-Bewegungen rund um Beschaffungsschritte (automatisch, nicht löschbar).

Leitprinzip der Modul-Trennung: **Purchase** ist rein kaufmännisch, **Bewegung**
besorgt jeden physischen Transport. Damit eine Beschaffung prozesssicher ist,
flankiert das System jeden ``purchase``-Schritt automatisch mit Pflicht-Bewegungen
(``locked=True``):

- **nach** der Beschaffung immer eine Bewegung (Wareneingang bzw. Rückversand) –
  ihr Ziel ist **konfigurierbar** wie bei einer regulären Bewegung (festes Ziel
  → per Scan erzwungen; leer → frei beim Einlagern),
- **vor** einer Lieferanten-Beschaffung, wenn sie nicht der erste Schritt ist, ein
  **Versand zum Lieferanten** (Stichwort Lohnveredelung) – das Ziel ist **fix der
  Lieferant** der Beschaffung (per Scan erzwungen, nicht editierbar).

Die Pflicht-Bewegungen sind nicht löschbar und werden bei jeder Strukturänderung
neu abgeleitet/positioniert (idempotent, selbstheilend). Unterscheidung der beiden
Rollen über das Ziel: Versand trägt ein **user**-Ziel (Lieferant), Wareneingang ein
Ziel anderer Art (Instanz/Unternehmen) oder keines.
"""

from sqlalchemy.orm import Session

from ..models import ArticleProcessStep, Order, UserProfile


def _plan(steps: list[tuple[str, str | None]], skip_customer_shipping: bool = False) -> list[str]:
    """Reine Soll-Sequenz aus (Schritttyp, Modus). Markierungen ``"versand"`` /
    ``"wareneingang"`` / ``"versandkunde"`` = Pflicht-Bewegung, sonst Nutzer-Schritttyp.

    - Versand nur vor einer **nicht ersten Lieferanten-Beschaffung** (Lohnveredelung);
    - Wareneingang **nach** jeder Beschaffung;
    - Versand zum Kunden **nach** jedem Verkauf (irgendwie muss es zum Kunden) – ausser bei
      einer **Retoure**: dort ist der Verkauf eine **Gutschrift** (kein Versand; die Ware kommt
      über den ``return``-Schritt herein), ``skip_customer_shipping`` unterdrückt die Bewegung."""
    seq: list[str] = []
    moves = ("versand", "wareneingang", "versandkunde")
    for i, (t, mode) in enumerate(steps):
        if t == "purchase" and mode == "supplier" and i > 0 and (not seq or seq[-1] not in moves):
            seq.append("versand")
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


def _supplier_object_id(db: Session, supplier_id: int | None) -> int | None:
    if not supplier_id:
        return None
    u = db.query(UserProfile).filter(UserProfile.id == supplier_id).first()
    return u.object_id if u else None


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

    # Rollen-getrennte Pools (positionsunabhängig): Versand-zum-Kunden ist via
    # mode='customer' getaggt; Versand-zum-Lieferanten trägt ein user-Ziel; Wareneingang
    # ein Ziel anderer Art oder keines. So gehen Ziele beim Re-Sync nicht verloren.
    versandkunde_pool = [s for s in locked if s.mode == "customer"]
    versand_pool = [s for s in locked if s.mode != "customer" and s.target_location_type == "user"]
    wareneingang_pool = [s for s in locked if s.mode != "customer" and s.target_location_type != "user"]

    # Retoure-Unter-Auftrag: der Verkauf ist eine Gutschrift → KEIN Pflicht-Versand zum Kunden.
    credit_context = False
    if order_id is not None:
        row = db.query(Order.reason).filter(Order.id == order_id).first()
        credit_context = bool(row and row[0] == "return")
    plan = _plan([(s.step_type, s.mode) for s in user_steps], skip_customer_shipping=credit_context)
    final: list[list] = []   # [node_or_step, role]
    ui = vi = wi = ki = 0
    for entry in plan:
        if entry == "versand":
            node = versand_pool[vi] if vi < len(versand_pool) else None
            vi += 1
            final.append([node, "versand"])
        elif entry == "wareneingang":
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

    for idx, (node, role) in enumerate(final):
        node.position = idx + 1
        if role == "versand":
            purchase = next((it[0] for it in final[idx + 1:] if it[1] == "user"), None)
            oid = _supplier_object_id(db, purchase.supplier_id) if purchase else None
            node.target_location_type = "user" if oid else None
            node.target_location_id = oid
        # wareneingang/versandkunde: Ziel unverändert (vom Nutzer gesetzt bzw. beim Versand)
