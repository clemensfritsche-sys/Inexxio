"""Pflicht-Bewegungen rund um Beschaffungsschritte (automatisch, nicht löschbar).

Leitprinzip der Modul-Trennung: **Purchase** ist rein kaufmännisch, **Bewegung**
besorgt jeden physischen Transport. Damit eine Beschaffung prozesssicher ist,
flankiert das System jeden ``purchase``-Schritt automatisch mit Pflicht-Bewegungen
(``locked=True``):

- **nach** der Beschaffung immer eine Bewegung (Wareneingang bzw. Rückversand) –
  ihr Ziel ist **konfigurierbar** wie bei einer regulären Bewegung (fester
  Lagerplatz → per Scan erzwungen; leer → frei beim Einlagern),
- **vor** einer Lieferanten-Beschaffung, wenn sie nicht der erste Schritt ist, ein
  **Versand zum Lieferanten** (Stichwort Lohnveredelung) – das Ziel ist **fix der
  Lieferant** der Beschaffung (per Scan erzwungen, nicht editierbar).

Die Pflicht-Bewegungen sind nicht löschbar und werden bei jeder Strukturänderung
neu abgeleitet/positioniert (idempotent, selbstheilend). Unterscheidung der beiden
Rollen über das Ziel: Versand trägt ein **user**-Ziel (Lieferant), Wareneingang ein
**lagerplatz**-Ziel oder keines.
"""

from sqlalchemy.orm import Session

from ..models import ArticleProcessStep, Process, UserProfile


def _plan(steps: list[tuple[str, str | None]]) -> list[str]:
    """Reine Soll-Sequenz aus (Schritttyp, Modus). Markierungen ``"versand"`` /
    ``"wareneingang"`` = Pflicht-Bewegung, sonst der Nutzer-Schritttyp.

    Versand nur vor einer **nicht ersten Lieferanten-Beschaffung**; Wareneingang
    nach jeder Beschaffung. Zwischen zwei aufeinanderfolgenden Beschaffungen genügt
    die eine (Wareneingang)."""
    seq: list[str] = []
    for i, (t, mode) in enumerate(steps):
        if t == "purchase" and mode == "supplier" and i > 0 and (not seq or seq[-1] not in ("versand", "wareneingang")):
            seq.append("versand")
        seq.append(t)
        if t == "purchase":
            seq.append("wareneingang")
    return seq


def _active_steps(db: Session, process_id: int) -> list[ArticleProcessStep]:
    return (
        db.query(ArticleProcessStep)
        .filter(ArticleProcessStep.process_id == process_id, ArticleProcessStep.is_active == True)
        .order_by(ArticleProcessStep.position, ArticleProcessStep.id)
        .all()
    )


def _supplier_object_id(db: Session, supplier_id: int | None) -> int | None:
    if not supplier_id:
        return None
    u = db.query(UserProfile).filter(UserProfile.id == supplier_id).first()
    return u.object_id if u else None


def sync_locked_movements(db: Session, process_id: int) -> None:
    """Pflicht-Bewegungen rund um die Beschaffungsschritte **eines Prozesses**
    herstellen (idempotent).

    Schreibt nur (flush); der Aufrufer committet. Renummeriert die Positionen 1..N.
    Versand-Ziele werden (neu) auf den Lieferanten gesetzt; Wareneingang-Ziele bleiben
    wie vom Nutzer definiert erhalten."""
    proc = db.query(Process).filter(Process.id == process_id).first()
    article_id = proc.article_id if proc else None
    steps = _active_steps(db, process_id)
    user_steps = [s for s in steps if not s.locked]
    locked = [s for s in steps if s.locked]
    if not any(s.step_type == "purchase" for s in user_steps) and not locked:
        return  # häufigster Fall: nichts zu tun

    # Rollen-getrennte Pools (positionsunabhängig): Versand trägt user-Ziel (Lieferant),
    # Wareneingang ein Lagerplatz-Ziel oder keines. So gehen Wareneingang-Ziele beim
    # Re-Sync nicht verloren und Rollen vermischen sich nicht.
    versand_pool = [s for s in locked if s.target_location_type == "user"]
    wareneingang_pool = [s for s in locked if s.target_location_type != "user"]

    plan = _plan([(s.step_type, s.mode) for s in user_steps])
    final: list[list] = []   # [node_or_step, role]
    ui = vi = wi = 0
    for entry in plan:
        if entry == "versand":
            node = versand_pool[vi] if vi < len(versand_pool) else None
            vi += 1
            final.append([node, "versand"])
        elif entry == "wareneingang":
            node = wareneingang_pool[wi] if wi < len(wareneingang_pool) else None
            wi += 1
            final.append([node, "wareneingang"])
        else:
            final.append([user_steps[ui], "user"])
            ui += 1

    for item in final:
        if item[1] != "user" and item[0] is None:
            item[0] = ArticleProcessStep(process_id=process_id, article_id=article_id,
                                         step_type="movement", mode="supplier",
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
        # wareneingang: Ziel unverändert lassen (vom Nutzer gesetzt oder offen)
