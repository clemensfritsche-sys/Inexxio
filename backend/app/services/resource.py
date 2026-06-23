"""Geschäftslogik für den Prozessschritt «Ressource» (Produktion).

Je Schritt eine Liste von Ressourcen-Zeilen (mini-BOM), je Zeile ein Artikel +
Menge (pro Stück Produkt) + Modus:

- **consume** (Verbrauch): Bauteil wird in die Produkt-Instanz **eingebaut** →
  Lagerabgang. Auswahl strikt **FIFO nach Freigabe** (``instances.released_at``).
  Chargen werden bei Bedarf **teilentnommen** (Rest bleibt im Lager).
- **tool** (Betriebsmittel): Werkzeug/Maschine wird nur **genutzt** → kein
  Lagerabgang, kein FIFO; der Verantwortliche wählt eine freigegebene Instanz.

«Eingebaut» = Standortwechsel der Komponente in die Produkt-Instanz
(``location_type='instance'``) – derselbe Mechanismus wie der Bewegungs-Schritt.
Nur **freigegebene** (qc ``passed``) Instanzen sind verbrauchbar/nutzbar.
"""

from fastapi import HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..models import Article, ArticleProcessStep, Instance, Order, ResourceUsage, UserProfile
from ..models.base import utcnow
from ..schemas.resource import (
    ResourceCandidate, ResourceComponentPick, ResourceEmbed, ResourceLineExec,
    ResourcePlanItem, ResourceProductPlan,
)
from . import process
from .admin import log_audit
from .events import emit
from .inventory import allocate, available
from .locations import _obj_nr, location_label, resolve_physical_location
from .objects import next_object_id
from .subject import order_instances


def _current_usage(db: Session, order: Order, step: ArticleProcessStep | None) -> ResourceUsage | None:
    """Ressourcen-Buchung dieses konkreten Schritts (Routing über ``step_id``)."""
    if not step:
        return None
    return process.fact_for_step(db, order, step)


def _article(db: Session, article_db_id: int) -> Article | None:
    return db.query(Article).filter(Article.id == article_db_id).first()


def _user_name(u: UserProfile | None) -> str | None:
    if not u:
        return None
    name = " ".join(p for p in [u.first_name, u.last_name] if p).strip()
    return u.company_name or name or u.email


def fifo_candidates(db: Session, article_db_id: int, for_order_id: int | None = None) -> list[Instance]:
    """Verbrauchbare Instanzen eines Artikels: **freigegeben** (qc passed = Auftrag
    abgeschlossen & ab Lager verfügbar), Restmenge > 0, FIFO nach Freigabe
    (``released_at``, ersatzweise ``created_at``), dann Objektnummer.

    Reservierungen: ``for_order_id=None`` liefert nur **unreservierte** Instanzen
    (Basis für eine neue Reservierung). Mit ``for_order_id`` kommen zusätzlich die
    **für diesen Auftrag reservierten** Instanzen dazu – und werden **zuerst**
    verbraucht (der Auftrag entnimmt erst seine eigene Reservierung).

    Kein Standort-Filter nötig: bereits verbaute Instanzen tragen den Status
    ``consumed`` (nicht ``passed``) und fallen damit automatisch heraus."""
    q = db.query(Instance).filter(
        Instance.article_id == article_db_id,
        Instance.is_active == True,
        Instance.qc_status == "passed",
        Instance.quantity > 0,
    )
    if for_order_id is None:
        q = q.filter(Instance.reserved_for_order_id.is_(None))
    else:
        q = q.filter(or_(Instance.reserved_for_order_id.is_(None),
                         Instance.reserved_for_order_id == for_order_id))
    rows = q.all()
    # Eigene Reservierung zuerst, dann FIFO nach Freigabe, dann Objektnummer.
    rows.sort(key=lambda i: (
        0 if (for_order_id is not None and i.reserved_for_order_id == for_order_id) else 1,
        i.released_at or i.created_at, i.object_id or 0))
    return rows


def reserve_resources(db: Session, order: Order, actor_id: int) -> None:
    """Bei Auftragsfreigabe die zu verbrauchenden Komponenten **mengengenau**
    reservieren.

    Über alle ``resource``-Schritte des Artikels werden die consume-Mengen summiert
    und – FIFO aus unreserviertem freigegebenem Bestand – exakt die benötigte Menge
    gesperrt. Deckt eine Charge mehr als den Bedarf, wird sie **geteilt**: der
    reservierte Teil geht an den Auftrag (``reserved_for_order_id``), der Rest bleibt
    frei für andere Aufträge. Committet NICHT (Aufrufer schliesst ab)."""
    if not order.article_id or not order.quantity:
        return
    needs: dict[int, int] = {}
    for d in process.order_step_defs(db, order):
        if d.step_type != "resource":
            continue
        for line in (d.resource_lines or []):
            if line.get("mode", "consume") != "consume":
                continue
            aid = line["article_id"]
            needs[aid] = needs.get(aid, 0) + line.get("quantity", 1) * order.quantity
    for art_id, need in needs.items():
        if art_id == order.article_id:
            continue
        cands = fifo_candidates(db, art_id, for_order_id=None)
        for cand, take in zip(cands, allocate(need, [c.quantity for c in cands])):
            if take <= 0:
                continue
            if take == cand.quantity:
                cand.reserved_for_order_id = order.id           # ganze Instanz reservieren
            else:
                cand.quantity -= take                            # Charge teilen
                db.add(Instance(
                    object_id=next_object_id(db, "instance"), article_id=cand.article_id,
                    order_id=cand.order_id, kind=cand.kind, quantity=take,
                    qc_status="passed", released_at=cand.released_at or cand.created_at,
                    location_type=cand.location_type, location_id=cand.location_id,
                    reserved_for_order_id=order.id,
                ))
                db.flush()
    log_audit(db, "instances", None, "Ressourcen reserviert", actor_id, object_id=order.object_id)


def _tool_candidates(db: Session, article_db_id: int) -> list[Instance]:
    """Wählbare Betriebsmittel: freigegebene Instanzen des Werkzeug-Artikels."""
    return (
        db.query(Instance)
        .filter(
            Instance.article_id == article_db_id,
            Instance.is_active == True,
            Instance.qc_status == "passed",
        )
        .order_by(Instance.object_id)
        .all()
    )


def available_qty(candidates: list[Instance]) -> int:
    return sum(c.quantity for c in candidates)


# ─── Ausführung ───────────────────────────────────────────────────────────────

class _Fifo:
    """Läuft die FIFO-Kandidaten ab; gibt je Zug (Instanz, Menge, ganz?) zurück.

    ``ganz`` = die Instanz wird vollständig verbraucht (umlagern); sonst Charge
    teilentnehmen (Restmenge bleibt im Lager)."""

    def __init__(self, candidates: list[Instance]):
        self.cands = candidates
        self.i = 0

    def take(self, need: int):
        cand = self.cands[self.i]
        avail = cand.quantity
        take = min(avail, need)
        whole = take == avail
        if whole:
            self.i += 1
        return cand, take, whole


def _relocate(db: Session, inst: Instance, product: Instance, actor_id: int) -> None:
    """Komponente in die Produkt-Instanz einbauen (Lagerabgang + Verbrauch)."""
    log_audit(db, "instances", "location", f"instance:{product.object_id}", actor_id,
              object_id=inst.object_id, old_value=f"{inst.location_type}:{inst.location_id}")
    inst.location_type = "instance"
    inst.location_id = product.object_id
    inst.qc_status = "consumed"


def _consume_line(db: Session, order: Order, products: list[Instance],
                  article_db_id: int, per_unit: int, actor_id: int) -> list[dict]:
    """FIFO-Verbrauch eines Komponenten-Artikels in die Produkt-Instanzen."""
    if article_db_id == order.article_id:
        raise HTTPException(400, detail="Ein Artikel kann sich nicht selbst verbrauchen")
    cands = fifo_candidates(db, article_db_id, order.id)
    total_need = sum(per_unit * p.quantity for p in products)
    have = available_qty(cands)
    if have < total_need:
        art = _article(db, article_db_id)
        name = art.name if art else f"#{article_db_id}"
        raise HTTPException(
            409,
            detail=f"Nicht genügend freigegebener Bestand für «{name}»: benötigt {total_need}, verfügbar {have}",
        )

    fifo = _Fifo(cands)
    picks: list[dict] = []
    for product in products:
        need = per_unit * product.quantity
        while need > 0:
            cand, take, whole = fifo.take(need)
            if whole:
                _relocate(db, cand, product, actor_id)
                picks.append({"instance_id": cand.object_id, "quantity": take,
                              "into_instance_id": product.object_id})
            else:
                # Charge teilentnehmen: Rest bleibt im Lager, Teilcharge wandert ins Produkt
                cand.quantity -= take
                sub = Instance(
                    object_id=next_object_id(db, "instance"), article_id=cand.article_id,
                    order_id=cand.order_id, kind="batch", quantity=take,
                    qc_status="consumed", released_at=cand.released_at or cand.created_at,
                    location_type="instance", location_id=product.object_id,
                )
                db.add(sub)
                db.flush()
                log_audit(db, "instances", None,
                          f"Teilcharge {take} aus {cand.object_id} verbaut", actor_id,
                          object_id=sub.object_id)
                picks.append({"instance_id": sub.object_id, "quantity": take,
                              "into_instance_id": product.object_id,
                              "split_from": cand.object_id})
            need -= take
    return picks


def _validate_tools(db: Session, article_db_id: int, instance_ids: list[int]) -> list[Instance]:
    if not instance_ids:
        raise HTTPException(400, detail="Bitte ein Betriebsmittel wählen")
    clean: list[Instance] = []
    for iid in instance_ids:
        inst = (
            db.query(Instance)
            .filter(Instance.object_id == iid, Instance.is_active == True)
            .first()
        )
        if not inst or inst.article_id != article_db_id:
            raise HTTPException(400, detail=f"Betriebsmittel {iid} passt nicht zum Artikel")
        if inst.qc_status != "passed":
            raise HTTPException(400, detail="Nur freigegebene Betriebsmittel sind wählbar")
        clean.append(inst)
    return clean


def _use_tool(db: Session, tool: Instance, product: Instance, actor_id: int) -> None:
    """Betriebsmittel an den **physischen Standort der Produkt-Instanz** bringen.

    Es wird nur genutzt (kein Einbau, kein Lagerabgang), wandert aber an den
    Arbeitsort des Produkts – so ist nach dem Schritt sofort ersichtlich, wo das
    Werkzeug/die Maschine zuletzt im Einsatz war."""
    pt, pid = resolve_physical_location(db, product.location_type, product.location_id)
    if pt and pid and (tool.location_type, tool.location_id) != (pt, pid):
        log_audit(db, "instances", "location", f"{pt}:{pid}", actor_id,
                  object_id=tool.object_id, old_value=f"{tool.location_type}:{tool.location_id}")
        tool.location_type = pt
        tool.location_id = pid


def record_resource(db: Session, order: Order, data, actor_id: int) -> ResourceUsage:
    step = process.resolve_exec_step(db, order, "resource", getattr(data, "step_id", None))
    lines = (step.resource_lines if step else None) or []
    if not lines:
        raise HTTPException(400, detail="Für diesen Auftrag sind keine Ressourcen definiert")
    products = order_instances(db, order)
    if not products:
        raise HTTPException(409, detail="Keine Produkt-Instanzen vorhanden")

    tool_picks = {t.article_id: (t.instance_ids or []) for t in (data.tools or [])}
    details: dict = {"consume": [], "tools": []}

    for line in lines:
        art_id = line["article_id"]
        qty = line.get("quantity", 1)
        mode = line.get("mode", "consume")
        if mode == "tool":
            tools = _validate_tools(db, art_id, tool_picks.get(art_id, []))
            for t in tools:
                _use_tool(db, t, products[0], actor_id)
            details["tools"].append({"article_id": art_id, "instance_ids": [t.object_id for t in tools]})
        else:
            picks = _consume_line(db, order, products, art_id, qty, actor_id)
            details["consume"].append({"article_id": art_id, "picks": picks})

    usage = ResourceUsage(
        order_id=order.id, step_id=step.id, used_by_id=actor_id,
        note=(data.note or "").strip() or None, details=details,
    )
    db.add(usage)
    db.flush()
    log_audit(db, "resource_usages", None, "Ressourcen erfasst", actor_id, object_id=order.object_id)
    emit(db, "resource.recorded", object_type="order", object_id=order.object_id, actor_id=actor_id)
    process.recompute_completion(db, order)
    db.commit()
    db.refresh(usage)
    return usage


# ─── Embed (Auftrag-Detail) ───────────────────────────────────────────────────

def _line_view(db: Session, line: dict) -> dict:
    art = _article(db, line["article_id"])
    return {
        "article_id": line["article_id"],
        "quantity": line.get("quantity", 1),
        "mode": line.get("mode", "consume"),
        "article_name": art.name if art else None,
        "article_object_id": art.object_id if art else None,
        "unit": art.unit if art else None,
        "serialization": art.serialization if art else None,
    }


def _preview_consume(db: Session, products: list[Instance], article_db_id: int,
                     per_unit: int, for_order_id: int | None = None) -> dict[int, list[dict]]:
    """FIFO-Vorschau OHNE Mutation: {produkt_obj_id: [{instance_id, quantity, split_from?}]}.

    Bildet ``_consume_line`` nach, damit vorab sichtbar ist, welche Instanz in
    welche Produkt-Instanz wandert."""
    cands = fifo_candidates(db, article_db_id, for_order_id)
    remaining = [[c.object_id or 0, c.quantity] for c in cands]
    out: dict[int, list[dict]] = {}
    idx = 0
    for product in products:
        need = per_unit * product.quantity
        picks: list[dict] = []
        while need > 0 and idx < len(remaining):
            oid, avail = remaining[idx]
            take = min(avail, need)
            whole = take == avail
            picks.append({"instance_id": oid, "quantity": take,
                          "split_from": None if whole else oid})
            if whole:
                idx += 1
            else:
                remaining[idx][1] = avail - take
            need -= take
        out[product.object_id or 0] = picks
    return out


_UNSET = object()


def build_resource_embed(db: Session, order: Order, step: ArticleProcessStep,
                         usage=_UNSET) -> ResourceEmbed | None:
    if not step or not step.resource_lines:
        return None
    # ``usage`` kann vom Aufrufer bereits aufgelöst übergeben werden (spart eine Query).
    if usage is _UNSET:
        usage = _current_usage(db, order, step)
    done = usage is not None
    details = usage.details if usage else {}
    consumed_by_art: dict[int, list[int]] = {}
    for c in (details.get("consume", []) if details else []):
        consumed_by_art.setdefault(c["article_id"], []).extend(
            p["instance_id"] for p in c.get("picks", []))
    tools_by_art: dict[int, list[int]] = {
        t["article_id"]: (t.get("instance_ids") or [])
        for t in (details.get("tools", []) if details else [])
    }

    products = order_instances(db, order)
    art_names = {raw["article_id"]: (_article(db, raw["article_id"]) or None)
                 for raw in step.resource_lines}
    # Verbrauch je Produkt-Instanz: aus dem Protokoll (done) oder als FIFO-Vorschau.
    per_product: dict[int, list[ResourceComponentPick]] = {p.object_id or 0: [] for p in products}

    lines: list[ResourceLineExec] = []
    for raw in step.resource_lines:
        view = _line_view(db, raw)
        exec_line = ResourceLineExec(**view)
        art_id = raw["article_id"]
        if view["mode"] == "tool":
            cands = _tool_candidates(db, art_id)
            exec_line.candidates = [
                ResourceCandidate(object_id=c.object_id, label=_obj_nr(c.object_id or 0))
                for c in cands if c.object_id
            ]
            exec_line.picked = tools_by_art.get(art_id, [])
        else:
            need = view["quantity"] * (order.quantity or 0)
            have = available(db, art_id, order.id)   # SQL-Aggregat (kein Laden aller Instanzen)
            exec_line.need = need
            exec_line.available = have
            exec_line.sufficient = have >= need
            exec_line.picked = consumed_by_art.get(art_id, [])
            name = art_names[art_id].name if art_names[art_id] else None
            if done:
                # Tatsächliche Picks aus dem Protokoll (mit Ziel-Produkt-Instanz)
                rec = next((c for c in details.get("consume", []) if c["article_id"] == art_id), None)
                for p in (rec.get("picks", []) if rec else []):
                    tgt = p.get("into_instance_id")
                    if tgt in per_product:
                        per_product[tgt].append(ResourceComponentPick(
                            article_id=art_id, article_name=name,
                            instance_id=p["instance_id"], quantity=p["quantity"],
                            split_from=p.get("split_from")))
                exec_line.plan = [
                    ResourcePlanItem(instance_id=p["instance_id"], quantity=p["quantity"],
                                     into_instance_id=p.get("into_instance_id"),
                                     split_from=p.get("split_from"))
                    for p in (rec.get("picks", []) if rec else [])]
            else:
                preview = _preview_consume(db, products, art_id, view["quantity"], order.id)
                for prod_oid, picks in preview.items():
                    for p in picks:
                        per_product[prod_oid].append(ResourceComponentPick(
                            article_id=art_id, article_name=name,
                            instance_id=p["instance_id"], quantity=p["quantity"],
                            split_from=p.get("split_from")))
                exec_line.plan = [
                    ResourcePlanItem(instance_id=p["instance_id"], quantity=p["quantity"],
                                     into_instance_id=prod_oid, split_from=p.get("split_from"))
                    for prod_oid, picks in preview.items() for p in picks]
        lines.append(exec_line)

    product_plans = [
        ResourceProductPlan(instance_id=p.object_id or 0, kind=p.kind,
                            quantity=p.quantity, components=per_product.get(p.object_id or 0, []))
        for p in products
    ]

    emb = ResourceEmbed(done=done, note=usage.note if usage else None,
                        lines=lines, products=product_plans)
    if usage and usage.used_by_id:
        emb.used_by_name = _user_name(
            db.query(UserProfile).filter(UserProfile.id == usage.used_by_id).first())
    return emb
