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
from sqlalchemy.orm import Session

from ..models import Article, ArticleProcessStep, Instance, Order, ResourceUsage, UserProfile
from ..models.base import utcnow
from ..schemas.resource import (
    ResourceCandidate, ResourceEmbed, ResourceLineExec, ResourcePlanItem,
)
from . import process
from .admin import log_audit
from .locations import _obj_nr, location_label
from .objects import next_object_id


def _resource_step(db: Session, article_id: int | None) -> ArticleProcessStep | None:
    if not article_id:
        return None
    return (
        db.query(ArticleProcessStep)
        .filter(
            ArticleProcessStep.article_id == article_id,
            ArticleProcessStep.step_type == "resource",
            ArticleProcessStep.is_active == True,
        )
        .order_by(ArticleProcessStep.position, ArticleProcessStep.id)
        .first()
    )


def _current_usage(db: Session, order: Order) -> ResourceUsage | None:
    return (
        db.query(ResourceUsage)
        .filter(ResourceUsage.order_id == order.id, ResourceUsage.is_active == True)
        .first()
    )


def _order_instances(db: Session, order: Order) -> list[Instance]:
    return (
        db.query(Instance)
        .filter(Instance.order_id == order.id, Instance.is_active == True)
        .order_by(Instance.object_id)
        .all()
    )


def _article(db: Session, article_db_id: int) -> Article | None:
    return db.query(Article).filter(Article.id == article_db_id).first()


def _user_name(u: UserProfile | None) -> str | None:
    if not u:
        return None
    name = " ".join(p for p in [u.first_name, u.last_name] if p).strip()
    return u.company_name or name or u.email


def fifo_candidates(db: Session, article_db_id: int) -> list[Instance]:
    """Verbrauchbare Instanzen eines Artikels: freigegeben, im Lager, FIFO nach
    Freigabe (released_at, ersatzweise created_at), dann Objektnummer."""
    rows = (
        db.query(Instance)
        .filter(
            Instance.article_id == article_db_id,
            Instance.is_active == True,
            Instance.qc_status == "passed",
            Instance.location_type == "lagerplatz",
            Instance.quantity > 0,
        )
        .all()
    )
    rows.sort(key=lambda i: (i.released_at or i.created_at, i.object_id or 0))
    return rows


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
    """Komponente in die Produkt-Instanz einbauen (Lagerabgang)."""
    log_audit(db, "instances", "location", f"instance:{product.object_id}", actor_id,
              object_id=inst.object_id, old_value=f"{inst.location_type}:{inst.location_id}")
    inst.location_type = "instance"
    inst.location_id = product.object_id


def _consume_line(db: Session, order: Order, products: list[Instance],
                  article_db_id: int, per_unit: int, actor_id: int) -> list[dict]:
    """FIFO-Verbrauch eines Komponenten-Artikels in die Produkt-Instanzen."""
    if article_db_id == order.article_id:
        raise HTTPException(400, detail="Ein Artikel kann sich nicht selbst verbrauchen")
    cands = fifo_candidates(db, article_db_id)
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
                    object_id=next_object_id(db), article_id=cand.article_id,
                    order_id=cand.order_id, kind="batch", quantity=take,
                    qc_status="passed", released_at=cand.released_at or cand.created_at,
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


def _validate_tools(db: Session, article_db_id: int, instance_ids: list[int]) -> list[int]:
    if not instance_ids:
        raise HTTPException(400, detail="Bitte ein Betriebsmittel wählen")
    clean: list[int] = []
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
        clean.append(iid)
    return clean


def record_resource(db: Session, order: Order, data, actor_id: int) -> ResourceUsage:
    if not process.is_step_active(db, order, "resource"):
        raise HTTPException(409, detail="Ressource ist (noch) nicht an der Reihe")
    step = _resource_step(db, order.article_id)
    lines = (step.resource_lines if step else None) or []
    if not lines:
        raise HTTPException(400, detail="Für diesen Auftrag sind keine Ressourcen definiert")
    products = _order_instances(db, order)
    if not products:
        raise HTTPException(409, detail="Keine Produkt-Instanzen vorhanden")

    tool_picks = {t.article_id: (t.instance_ids or []) for t in (data.tools or [])}
    details: dict = {"consume": [], "tools": []}

    for line in lines:
        art_id = line["article_id"]
        qty = line.get("quantity", 1)
        mode = line.get("mode", "consume")
        if mode == "tool":
            ids = _validate_tools(db, art_id, tool_picks.get(art_id, []))
            details["tools"].append({"article_id": art_id, "instance_ids": ids})
        else:
            picks = _consume_line(db, order, products, art_id, qty, actor_id)
            details["consume"].append({"article_id": art_id, "picks": picks})

    usage = ResourceUsage(
        order_id=order.id, used_by_id=actor_id,
        note=(data.note or "").strip() or None, details=details,
    )
    db.add(usage)
    db.flush()
    log_audit(db, "resource_usages", None, "Ressourcen erfasst", actor_id, object_id=order.object_id)
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


def build_resource_embed(db: Session, order: Order) -> ResourceEmbed | None:
    step = _resource_step(db, order.article_id)
    if not step or not step.resource_lines:
        return None
    usage = _current_usage(db, order)
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

    total_units = order.quantity or 0
    lines: list[ResourceLineExec] = []
    for raw in step.resource_lines:
        view = _line_view(db, raw)
        exec_line = ResourceLineExec(**view)
        if view["mode"] == "tool":
            cands = _tool_candidates(db, raw["article_id"])
            exec_line.candidates = [
                ResourceCandidate(object_id=c.object_id, label=_obj_nr(c.object_id or 0))
                for c in cands if c.object_id
            ]
            exec_line.picked = tools_by_art.get(raw["article_id"], [])
        else:
            need = view["quantity"] * total_units
            cands = fifo_candidates(db, raw["article_id"])
            have = available_qty(cands)
            exec_line.need = need
            exec_line.available = have
            exec_line.sufficient = have >= need
            plan: list[ResourcePlanItem] = []
            rem = need
            for c in cands:
                if rem <= 0:
                    break
                take = min(c.quantity, rem)
                plan.append(ResourcePlanItem(instance_id=c.object_id or 0, quantity=take))
                rem -= take
            exec_line.plan = plan
            exec_line.picked = consumed_by_art.get(raw["article_id"], [])
        lines.append(exec_line)

    emb = ResourceEmbed(done=done, note=usage.note if usage else None, lines=lines)
    if usage and usage.used_by_id:
        emb.used_by_name = _user_name(
            db.query(UserProfile).filter(UserProfile.id == usage.used_by_id).first())
    return emb
