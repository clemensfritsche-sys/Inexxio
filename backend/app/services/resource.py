"""Geschäftslogik für den Prozessschritt «Ressource» (Produktion).

EIN Schritt führt eine Liste von Zeilen (Artikel + Menge pro Stück Produkt); je Zeile
ein **Modus** (``mode``):

- **consume** («Verbrauch»): Bauteil wird in die Produkt-Instanz **eingebaut** →
  Lagerabgang. Auswahl strikt **FIFO nach Freigabe** (``instances.released_at``).
  Chargen werden bei Bedarf **teilentnommen** (Rest bleibt im Lager).
- **tool** («Betriebsmittel»): Werkzeug/Maschine wird nur **genutzt** → kein
  Lagerabgang, kein FIFO; der Verantwortliche wählt eine freigegebene Instanz.

«Eingebaut» = Standortwechsel der Komponente in die Produkt-Instanz
(``location_type='instance'``). Nur **freigegebene** (qc ``passed``) Instanzen sind
verbrauchbar/nutzbar.
"""

from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..domain import event_types
from ..models import Article, ArticleProcessStep, Instance, Order, ResourceUsage, UserProfile
from ..schemas.resource import (
    ResourceCandidate, ResourceComponentPick, ResourceEmbed, ResourceLineExec,
    ResourcePlanItem, ResourceProductPlan,
)
from . import location_split, people, process, provisioning
from .admin import log_audit
from .events import emit
from .inventory import allocate, available, available_qty, avail_amount, fifo_candidates, in_stock_clauses
from .locations import _obj_nr, resolve_physical_location
from .quantity import ZERO, qty_sum, to_qty
from .reservation import consume as consume_qty, free_qty, release, reserve
from .subject import order_active_instances


def _current_usage(db: Session, order: Order, step: ArticleProcessStep | None) -> ResourceUsage | None:
    """Ressourcen-Buchung dieses konkreten Schritts (Routing über ``step_id``)."""
    if not step:
        return None
    return process.fact_for_step(db, order, step)


def _article(db: Session, article_db_id: int) -> Article | None:
    return db.query(Article).filter(Article.id == article_db_id).first()


def _line_mode(line: dict, step: ArticleProcessStep | None = None) -> str:
    """Modus einer Ressourcen-Zeile: ``mode`` der Zeile (consume | tool); Default
    ``consume``. (``step`` wird nicht mehr gebraucht – die Alt-Schritttypen consume/tool
    sind entfernt –, bleibt aber als Parameter für die Aufrufer erhalten.)"""
    m = (line or {}).get("mode")
    return m if m in ("consume", "tool") else "consume"


def reserve_resources(db: Session, order: Order, actor_id: int) -> None:
    """Bei Auftragsfreigabe die zu verbrauchenden Komponenten **mengengenau**
    reservieren.

    Über alle **Verbrauch**-Schritte (``consume``) des Auftrags werden die Mengen
    summiert und – FIFO aus freiem freigegebenem Bestand – exakt die benötigte Menge
    gesperrt. Betriebsmittel-Schritte (``tool``) reservieren nichts. Deckt eine Charge
    mehr als den Bedarf, wird die **Menge mengengenau reserviert** (``reservations``) –
    die Charge wird **nicht geteilt**, die Objektnummer bleibt erhalten. Committet NICHT."""
    from .order_lines import effective_quantity
    qty = to_qty(effective_quantity(db, order))
    if not qty:
        return
    needs: dict[int, Decimal] = {}
    for d in process.order_step_defs(db, order):
        if d.step_type not in process.RESOURCE_STEP_TYPES:
            continue
        for line in (d.resource_lines or []):
            if _line_mode(line, d) != "consume":
                continue
            aid = line["article_id"]
            needs[aid] = needs.get(aid, ZERO) + to_qty(line.get("quantity", 1)) * qty
    for art_id, need in needs.items():
        if art_id == order.article_id:
            continue
        cands = fifo_candidates(db, art_id, for_order_id=None, lock=True)
        for cand, take in zip(cands, allocate(need, [free_qty(c) for c in cands])):
            if take > 0:
                reserve(cand, order.id, take)   # mengengenau, OHNE Teilung
    log_audit(db, "instances", None, "Ressourcen reserviert", actor_id, object_id=order.object_id)


def _tool_candidates(db: Session, article_db_id: int) -> list[Instance]:
    """Wählbare Betriebsmittel: freigegebene Instanzen des Werkzeug-Artikels."""
    return (
        db.query(Instance)
        .filter(
            Instance.article_id == article_db_id,
            Instance.is_active == True,
            *in_stock_clauses(),
        )
        .order_by(Instance.object_id)
        .all()
    )


# ─── Ausführung ───────────────────────────────────────────────────────────────

class _Fifo:
    """Läuft die FIFO-Kandidaten ab; gibt je Zug (Instanz, Menge, ganz?) zurück.

    ``ganz`` = die **komplette physische Instanz** wandert ins Produkt (umlagern); sonst
    Teilentnahme – die Instanz bleibt mit Restmenge im Lager (**dieselbe Objektnummer**,
    keine Teilung). Entnehmbar je Auftrag ist die freie Restmenge plus die eigene
    Reservierung (``avail_amount``)."""

    def __init__(self, candidates: list[Instance], order_id: int):
        self.cands = candidates
        self.order_id = order_id
        self.i = 0

    def take(self, need):
        cand = self.cands[self.i]
        avail = avail_amount(cand, self.order_id)
        take = min(avail, to_qty(need))
        whole = take == to_qty(cand.quantity)  # die GANZE Instanz geht ins Produkt
        if take >= avail:                      # für diesen Auftrag erschöpft → nächste
            self.i += 1
        return cand, take, whole


def _relocate(db: Session, inst: Instance, product: Instance, actor_id: int) -> None:
    """Komponente in die Produkt-Instanz einbauen (Lagerabgang + Verbrauch)."""
    log_audit(db, "instances", "location", f"instance:{product.object_id}", actor_id,
              object_id=inst.object_id, old_value=f"{inst.location_type}:{inst.location_id}")
    # Über die EINE Schreibstelle setzen: ``set_single`` räumt zusätzlich eine bestehende
    # Verteilungs-Map auf. Direktes Zuweisen liess bei einer zuvor auf mehrere Standorte
    # verteilten Charge die alte Map stehen – die Instanz galt dann als «verbaut» UND
    # gleichzeitig als anteilig woanders liegend.
    location_split.set_single(inst, "instance", product.object_id)
    inst.disposition = "consumed"   # Verbleib: verbaut (Qualität bleibt unverändert)


def _consume_line(db: Session, order: Order, products: list[Instance],
                  article_db_id: int, per_unit, actor_id: int) -> list[dict]:
    """FIFO-Verbrauch eines Komponenten-Artikels in die Produkt-Instanzen."""
    if article_db_id == order.article_id:
        raise HTTPException(400, detail="Ein Artikel kann sich nicht selbst verbrauchen")
    per_unit = to_qty(per_unit)
    cands = fifo_candidates(db, article_db_id, order.id, lock=True)
    total_need = qty_sum(per_unit * to_qty(p.quantity) for p in products)
    have = available_qty(cands, order.id)
    if have < total_need:
        art = _article(db, article_db_id)
        name = art.name if art else f"#{article_db_id}"
        raise HTTPException(
            409,
            detail=f"Nicht genügend freigegebener Bestand für «{name}»: benötigt {total_need}, verfügbar {have}",
        )

    fifo = _Fifo(cands, order.id)
    picks: list[dict] = []
    for product in products:
        need = per_unit * to_qty(product.quantity)
        while need > 0:
            cand, take, whole = fifo.take(need)
            if take <= 0:
                break
            if whole:
                # Die komplette Instanz wandert ins Produkt (Objektnummer bleibt erhalten).
                release(cand, order.id)
                _relocate(db, cand, product, actor_id)
            else:
                # Teilentnahme aus einer Charge: Menge mindern, KEINE neue Instanz/Nummer.
                consume_qty(cand, order.id, take)
                # War die Charge auf mehrere Standorte verteilt, die Verteilung nachziehen
                # (Summe wieder = quantity).
                location_split.reconcile(cand)
                log_audit(db, "instances", "quantity", str(cand.quantity), actor_id,
                          object_id=cand.object_id,
                          old_value=f"{cand.quantity + take} (− {take} verbaut in {product.object_id})")
            picks.append({"instance_id": cand.object_id, "quantity": take,
                          "into_instance_id": product.object_id})
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
        if inst.quality != "passed" or inst.disposition != "in_stock":
            raise HTTPException(400, detail="Nur freigegebene Betriebsmittel sind wählbar")
        clean.append(inst)
    return clean


def _use_tool(db: Session, tool: Instance, product: Instance, actor_id: int) -> None:
    """Betriebsmittel an den **physischen Standort der Produkt-Instanz** bringen.

    Es wird nur genutzt (kein Einbau, kein Lagerabgang), wandert aber an den
    Arbeitsort des Produkts – so ist nach dem Schritt sofort ersichtlich, wo das
    Werkzeug/die Maschine zuletzt im Einsatz war. Bereitstellungsort «Arbeitsplatz»:
    der EINE Reconciler bringt es dorthin – **no-op, wenn schon da** (der häufige Fall)."""
    pt, pid = resolve_physical_location(db, product.location_type, product.location_id)
    if pt and pid:
        old = f"{tool.location_type}:{tool.location_id}"
        if provisioning.reconcile_to(tool, pt, pid):
            log_audit(db, "instances", "location", f"{pt}:{pid}", actor_id,
                      object_id=tool.object_id, old_value=old)


def record_resource(db: Session, order: Order, data, actor_id: int) -> ResourceUsage:
    step = process.resolve_resource_step(db, order, getattr(data, "step_id", None))
    lines = (step.resource_lines if step else None) or []
    if not lines:
        raise HTTPException(400, detail="Für diesen Schritt sind keine Zeilen definiert")
    products = order_active_instances(db, order)
    if not products:
        raise HTTPException(409, detail="Keine Produkt-Instanzen vorhanden")

    tool_picks = {t.article_id: (t.instance_ids or []) for t in (data.tools or [])}
    details: dict = {"consume": [], "tools": []}

    for line in lines:
        art_id = line["article_id"]
        qty = line.get("quantity", 1)
        if _line_mode(line, step) == "tool":
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
    # Verbrauch (Lagerabgang) als Domain-Event mit DEKLARIERTER Polarität – Gegenstück
    # zum Bestands-Zugang; macht den Event-Strom zur ökonomischen Wahrheit.
    consumed = [{"article_id": c["article_id"],
                 "quantity": sum(p.get("quantity", 0) for p in c.get("picks", []))}
                for c in details.get("consume", [])]
    log_audit(db, "resource_usages", None, "Ressourcen erfasst", actor_id, object_id=order.object_id)
    emit(db, "resource.recorded", object_type="order", object_id=order.object_id, actor_id=actor_id,
         payload={"consumed": consumed, "polarity": event_types.DECREASE} if consumed else None)
    process.recompute_completion(db, order)
    db.commit()
    db.refresh(usage)
    return usage


# ─── Embed (Auftrag-Detail) ───────────────────────────────────────────────────

def _line_view(db: Session, line: dict, step: ArticleProcessStep | None = None) -> dict:
    art = _article(db, line["article_id"])
    return {
        "article_id": line["article_id"],
        "quantity": line.get("quantity", 1),
        "mode": _line_mode(line, step),
        "article_name": art.name if art else None,
        "article_object_id": art.object_id if art else None,
        "unit": art.unit if art else None,
        "serialization": art.serialization if art else None,
    }


def _preview_consume(db: Session, products: list[Instance], article_db_id: int,
                     per_unit, for_order_id: int | None = None) -> dict[int, list[dict]]:
    """FIFO-Vorschau OHNE Mutation: {produkt_obj_id: [{instance_id, quantity, split_from?}]}.

    Bildet ``_consume_line`` nach, damit vorab sichtbar ist, welche Instanz in
    welche Produkt-Instanz wandert."""
    per_unit = to_qty(per_unit)
    cands = fifo_candidates(db, article_db_id, for_order_id)
    remaining = [[c.object_id or 0, avail_amount(c, for_order_id)] for c in cands]
    out: dict[int, list[dict]] = {}
    idx = 0
    for product in products:
        need = per_unit * to_qty(product.quantity)
        picks: list[dict] = []
        while need > 0 and idx < len(remaining):
            oid, avail = remaining[idx]
            take = min(avail, need)
            # Kein Teilen mehr: die Charge bleibt EINE Instanz; der Pick nennt die Charge
            # direkt mit der entnommenen Menge (split_from entfällt).
            picks.append({"instance_id": oid, "quantity": take, "split_from": None})
            if take >= avail:
                idx += 1
            else:
                remaining[idx][1] = avail - take
            need -= take
        out[product.object_id or 0] = picks
    return out


_UNSET = object()


def _fill_consume_line(db: Session, order: Order, exec_line, view: dict, products: list,
                       per_product: dict, *, art_name: str | None, order_qty,
                       logged: dict | None) -> None:
    """Eine **Verbrauchs-Zeile** mit Bedarf/Verfügbarkeit und dem Verbrauch **je Produkt-
    Instanz** füllen.

    ``logged`` = das Protokoll dieses Artikels, wenn der Schritt bereits ausgeführt ist –
    dann zeigt das Panel die **tatsächlichen** Picks. Sonst wird der FIFO-Plan als Vorschau
    berechnet. Beides schreibt in dieselbe Struktur (``exec_line.plan`` + ``per_product``),
    damit die Anzeige vor und nach der Ausführung identisch aufgebaut ist."""
    art_id = view["article_id"]
    need = to_qty(view["quantity"]) * order_qty
    have = available(db, art_id, order.id)   # SQL-Aggregat (kein Laden aller Instanzen)
    exec_line.need = need
    exec_line.available = have
    exec_line.sufficient = have >= need

    def _pick(p, into):
        if into in per_product:
            per_product[into].append(ResourceComponentPick(
                article_id=art_id, article_name=art_name, instance_id=p["instance_id"],
                quantity=p["quantity"], split_from=p.get("split_from")))

    if logged is not None:
        picks = logged.get("picks", [])
        for p in picks:
            _pick(p, p.get("into_instance_id"))
        exec_line.plan = [
            ResourcePlanItem(instance_id=p["instance_id"], quantity=p["quantity"],
                             into_instance_id=p.get("into_instance_id"),
                             split_from=p.get("split_from"))
            for p in picks]
        return

    preview = _preview_consume(db, products, art_id, view["quantity"], order.id)
    for prod_oid, picks in preview.items():
        for p in picks:
            _pick(p, prod_oid)
    exec_line.plan = [
        ResourcePlanItem(instance_id=p["instance_id"], quantity=p["quantity"],
                         into_instance_id=prod_oid, split_from=p.get("split_from"))
        for prod_oid, picks in preview.items() for p in picks]


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

    from .order_lines import effective_quantity
    order_qty = to_qty(effective_quantity(db, order))
    products = order_active_instances(db, order)
    art_names = {raw["article_id"]: (_article(db, raw["article_id"]) or None)
                 for raw in step.resource_lines}
    # Verbrauch je Produkt-Instanz: aus dem Protokoll (done) oder als FIFO-Vorschau.
    per_product: dict[int, list[ResourceComponentPick]] = {p.object_id or 0: [] for p in products}

    lines: list[ResourceLineExec] = []
    for raw in step.resource_lines:
        view = _line_view(db, raw, step)
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
            exec_line.picked = consumed_by_art.get(art_id, [])
            _fill_consume_line(db, order, exec_line, view, products, per_product,
                               art_name=art_names[art_id].name if art_names[art_id] else None,
                               order_qty=order_qty,
                               logged=next((c for c in details.get("consume", [])
                                            if c["article_id"] == art_id), None) if done else None)
        lines.append(exec_line)

    product_plans = [
        ResourceProductPlan(instance_id=p.object_id or 0, kind=p.kind,
                            quantity=p.quantity, components=per_product.get(p.object_id or 0, []))
        for p in products
    ]

    emb = ResourceEmbed(done=done, note=usage.note if usage else None,
                        lines=lines, products=product_plans)
    if usage and usage.used_by_id:
        emb.used_by_name = people.name(
            db.query(UserProfile).filter(UserProfile.id == usage.used_by_id).first())
    return emb
