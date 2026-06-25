"""Aufsummiertes Gewicht eines gefertigten Artikels (read-only).

Hat ein Artikel in seiner Prozessdefinition einen ``resource``-Schritt mit zu
**verbauenden** Komponenten (mode ``consume``), ergibt sich sein Gewicht
**automatisch** aus der Summe der Komponenten-Gewichte × Menge je Stück. Das gilt
**über mehrere Ebenen**: Ist eine Komponente selbst gefertigt, zählt ihr
aufsummiertes Gewicht (Rekursion mit Memoisierung + Zyklenschutz).

Betriebsmittel (mode ``tool``) werden nur genutzt, nicht verbaut – sie tragen
**nicht** zum Gewicht bei.

Reine Roh-/Kaufartikel (kein consume) haben kein berechnetes Gewicht; für sie
gilt weiter das manuell erfasste ``weight_kg``.
"""

from decimal import Decimal

from sqlalchemy.orm import Session

from ..models import Article, ArticleProcessStep, Process

_Q = Decimal("0.001")  # 3 Nachkommastellen wie weight_kg (Numeric(12,3))


def _graph(db: Session) -> tuple[dict[int, Decimal], dict[int, list[tuple[int, Decimal]]]]:
    """(weight_map, consume_map) über alle aktiven Artikel/Ressourcen-Schritte.

    consume_map[article_id] = [(component_article_id, menge_pro_stück), …]."""
    from . import processes as processes_svc
    weights: dict[int, Decimal] = {}
    for aid, w in db.query(Article.id, Article.weight_kg).filter(Article.is_active == True).all():
        weights[aid] = w if w is not None else Decimal(0)
    consume: dict[int, list[tuple[int, Decimal]]] = {}
    # Nur die **Produktions**-Rezeptur (Prozess-Quelle ``produce``) bestimmt das
    # Gewicht – über die **Verbrauch**-Zeilen (``mode='consume'``) der Ressourcen-Schritte.
    # Betriebsmittel-Zeilen (``mode='tool'``) zählen NICHT. Der/die Produkt-Artikel sind
    # die Artikel, die den Prozess in ihrer Stückliste führen (n:m).
    steps = (
        db.query(ArticleProcessStep)
        .join(Process, Process.id == ArticleProcessStep.process_id)
        .filter(ArticleProcessStep.step_type.in_(("resource", "consume", "tool")),
                ArticleProcessStep.is_active == True,
                Process.source == "produce", Process.is_active == True)
        .all()
    )
    parents_cache: dict[int, list[int]] = {}
    for s in steps:
        if s.process_id not in parents_cache:
            parents_cache[s.process_id] = processes_svc.linked_article_ids(db, s.process_id)
        parents = parents_cache[s.process_id]
        if not parents:
            continue
        for line in (s.resource_lines or []):
            comp = line.get("article_id")
            mode = line.get("mode") or ("tool" if s.step_type == "tool" else "consume")
            if comp is None or mode != "consume":
                continue
            qty = Decimal(str(line.get("quantity", 1)))
            for parent in parents:
                consume.setdefault(parent, []).append((comp, qty))
    return weights, consume


def _eff(aid: int, weights: dict, consume: dict, memo: dict, stack: set) -> Decimal:
    """Effektives Gewicht eines Artikels (rekursiv); fällt bei Roh-Artikeln und im
    Zyklusfall auf das manuelle ``weight_kg`` zurück."""
    if aid in memo:
        return memo[aid]
    lines = consume.get(aid)
    if not lines or aid in stack:
        return weights.get(aid, Decimal(0))
    stack.add(aid)
    total = Decimal(0)
    for comp, qty in lines:
        total += _eff(comp, weights, consume, memo, stack) * qty
    stack.discard(aid)
    memo[aid] = total
    return total


def computed_weights(db: Session, article_ids: list[int] | None = None) -> dict[int, Decimal]:
    """Aufsummiertes Gewicht je Artikel **mit** consume-Ressourcen (sonst nicht
    enthalten – dort gilt das manuelle Gewicht). Auf 3 Nachkommastellen gerundet."""
    weights, consume = _graph(db)
    memo: dict[int, Decimal] = {}
    ids = article_ids if article_ids is not None else list(consume.keys())
    out: dict[int, Decimal] = {}
    for aid in ids:
        if aid in consume:
            out[aid] = _eff(aid, weights, consume, memo, set()).quantize(_Q)
    return out
