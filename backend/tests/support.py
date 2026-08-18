"""Gemeinsame Hilfen der Wächter — bewusst winzig, bewusst ohne eigene Regel.

Was hier steht, ist **Bedienung**, keine Fachaussage: die Tests sollen die echten
Dienstpfade rufen, nicht deren Regeln nachbauen.

Zweitens steht hier alles, was **mehr als eine** Wächter-Datei braucht. Zwei Kopien von
``make_units`` wären zwei Aufbauten desselben Zustands – und sobald sie auseinanderlaufen,
prüfen zwei Dateien gegen zwei verschiedene Welten, ohne dass es jemand merkt.
"""

import io
import os
import pathlib
import tokenize
from typing import Any, Optional

import pytest

BACKEND = pathlib.Path(__file__).resolve().parents[1]
APP = BACKEND / "app"


def per_unit(
    db, *, order, step, instance_object_id: int,
    values: Optional[dict[str, Any]] = None,
) -> dict[str, dict[str, Any]]:
    """Ein Wertesatz → **je gezogener Einzelinstanz einer**.

    Genau das tut auch die Oberfläche, nur mit verschiedenen Werten je Stück: sie fragt,
    **welche** Stücke gezogen sind (``group='sample'``), und füllt für jedes ein
    Formular. Hier wird derselbe Satz eingetragen, weil die Tests am Ablauf interessiert
    sind und nicht an den Zahlen darin.

    Die Nummern kommen aus derselben Quelle wie die Erwartung des Servers – ein zweiter
    Weg, sie zu bestimmen, wäre ein zweiter Massstab.
    """
    from app.services import process as proc

    numbers = proc.held_numbers(
        db, order, step, instance_object_id=instance_object_id, group="sample",
    )
    return {n: dict(values or {"ok": True}) for n in numbers}


# ═══════════════════════════════════════════════════════════════════════════════
# Echte Welt: Sitzung, Stücke, Halter, Modul
# ═══════════════════════════════════════════════════════════════════════════════

def session():
    """Eine Sitzung gegen echtes PostgreSQL – oder ein Skip **mit Grund**.

    Ohne Datenbank still durchzuwinken hiesse, dass ein grüner Lauf nichts aussagt; die
    interessanten Fehler entstehen zwischen den Schritten und nicht in einem
    nachgestellten Zustand.
    """
    import sys
    sys.path.insert(0, str(BACKEND))
    os.environ.setdefault("FIREBASE_PROJECT_ID", "test")
    try:
        from app.core.database import Base, SessionLocal, engine
        import app.main as main
        Base.metadata.create_all(engine)
        main._ensure_columns()
        return SessionLocal()
    except Exception as exc:  # pragma: no cover - reine Umgebungsfrage
        pytest.skip(f"Kein PostgreSQL erreichbar ({type(exc).__name__}: {exc}) – "
                    f"DATABASE_URL setzen, damit diese Regeln wirklich laufen.")


def make_units(db, *, quantity: int = 2, serialization: str = "unit"):
    """Echte Einzelinstanzen über den echten Weg: ein freigegebener Erzeugungsauftrag.

    Sie von Hand einzufügen wäre schneller und würde genau die Fehler verstecken, die
    zwischen den Schritten entstehen.
    """
    from app.models import Article, Instance, InstanceUnit, OrderUnit
    from app.services import article_process as tpl, objects as obj, process as proc

    art = Article(object_id=obj.next_object_id(db), name="Ortstück", unit="stk",
                  serialization=serialization)
    db.add(art)
    db.flush()
    # Ein Erzeugungsauftrag fährt die Vorlage des Artikels – ohne sie gibt es keinen
    # Prozess und damit keine Freigabe (§6.2). Das Modul ist hier Beiwerk.
    tpl.create_steps(db, art, [{"module_type": "datenerfassung",
                                "config": {"points": [{"label": "OK", "type": "bool"}]}}])
    db.flush()
    order = proc.release(
        db,
        lines=[{"article_object_id": art.object_id, "quantity": quantity,
                "origin": "neu", "units": []}],
        steps=[], actor_id=None,
    )
    db.flush()
    # Die Stücke des Auftrags über die Zugehörigkeit – Instance kennt den Auftrag nicht.
    units = (db.query(InstanceUnit)
             .join(OrderUnit, OrderUnit.instance_unit_id == InstanceUnit.id)
             .filter(OrderUnit.order_id == order.id)
             .order_by(InstanceUnit.id).all())
    instances = db.query(Instance).filter(
        Instance.id.in_({u.instance_id for u in units})).all()
    return order, instances, units


def make_company(db, name: str, **address):
    """Eine Gesellschaft – **ohne Commit**, damit der Test sauber zurückrollt.

    ``company_settings.id`` trägt keine Sequence (die Tabelle war einmal ein Singleton)
    und hat den Vorgabewert 1; der Schlüssel wird darum wie in ``sites.create`` vergeben.
    ``sites.create`` selbst committet – hier wäre das ein Rest, der die nächste Prüfung
    beeinflusst.
    """
    from sqlalchemy import func
    from app.models import CompanySettings
    from app.services import objects as obj

    next_id = (db.query(func.max(CompanySettings.id)).scalar() or 0) + 1
    company = CompanySettings(id=next_id, object_id=obj.next_object_id(db),
                              company_name=name, **address)
    db.add(company)
    db.flush()
    return company


def make_move_step(db, order, target_object_id: int):
    """Ein **Bewegen**-Modul an einem laufenden Auftrag – über den echten Anlege-Pfad.

    Es wird ans Ende gehängt; für die Fuhren-Vorschau zählt allein seine Konfiguration,
    nicht seine Position.
    """
    from app.models import ProcessStep
    from app.domain import modules

    last = (db.query(ProcessStep).filter(ProcessStep.order_id == order.id)
            .order_by(ProcessStep.position.desc()).first())
    mod = modules.get(modules.BEWEGEN)
    step = ProcessStep(
        order_id=order.id, position=(last.position if last else 0) + 1,
        module_type=modules.BEWEGEN,
        config=mod.clean_config({"target": target_object_id}),
        status_before=mod.status_before, status_after=mod.status_after,
    )
    db.add(step)
    db.flush()
    return step


# ═══════════════════════════════════════════════════════════════════════════════
# Aussagen über den Quelltext
# ═══════════════════════════════════════════════════════════════════════════════

def source(rel: str) -> str:
    return (APP / rel).read_text(encoding="utf-8")


def code_only(src: str) -> str:
    """Nur der **ausgeführte** Quelltext – ohne Kommentare und ohne Zeichenketten.

    Verbotene Formen sind Aussagen über **Code**. Ein roher Textvergleich verböte dem
    Projekt, seine eigene Historie zu dokumentieren: ADR 009 nennt ``location_split`` und
    ``movable_instances`` beim Namen, und mehrere Docstrings verweisen zu Recht darauf,
    was es einmal gab. Ein Wächter, der daran anschlägt, erzieht zum Verschweigen – und
    das ist die teurere Sorte Fehler.
    """
    out = []
    try:
        for tok in tokenize.generate_tokens(io.StringIO(src).readline):
            if tok.type in (tokenize.COMMENT, tokenize.STRING):
                continue
            out.append(tok.string)
    except tokenize.TokenError:  # pragma: no cover - defekte Datei wäre ein anderer Test
        return src
    return " ".join(out)


def live_sources() -> list[tuple[str, str]]:
    """Der **aktive** Quelltext. Abgeschaltete Module (`core/features.py`) bleiben als
    Historie liegen und dürfen die Aussage nicht verfälschen."""
    from app.core import features  # noqa: F401  (nur zur Existenzprüfung)
    disabled = ("services/ai/", "services/payments/", "services/shipping/",
                "services/sale.py", "services/selling.py", "services/refund.py",
                "services/customer_returns.py", "services/pricing.py", "services/tax.py",
                "services/fx.py", "services/operating_costs.py", "services/document",
                "services/consent.py", "services/legal.py",
                "routers/sales.py", "routers/shop.py", "routers/document",
                "routers/ai.py", "routers/consent.py", "routers/legal.py",
                "schemas/sale", "schemas/shop.py", "schemas/document",
                "schemas/consent.py", "schemas/ai.py")
    out = []
    for p in APP.rglob("*.py"):
        rel = p.relative_to(APP).as_posix()
        if any(rel.startswith(d) for d in disabled):
            continue
        out.append((rel, p.read_text(encoding="utf-8")))
    return out
