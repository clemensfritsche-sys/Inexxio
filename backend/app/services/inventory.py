"""Bestandslogik: Verfügbarkeit, **mengengenaue** Reservierung und FIFO-Allokation.

Reservierung ist **mengengenau ohne Teilung der Instanz**: je Komponente wird nur die
benötigte Menge gesperrt (``instances.reservations`` = ``{auftrag: menge}``), die
Objektnummer bleibt erhalten. Eine Charge von 1000 Schrauben mit 30 reservierten Stück
bleibt mit 970 frei verfügbar – es entsteht **keine** zweite Instanz mit eigener Nummer.

Frei verfügbar = ``quantity − reserved_quantity``; ``reserved_quantity`` ist die
denormalisierte Summe der Reservierungen (für die SQL-Verfügbarkeitsfilter).
"""

from decimal import Decimal

from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..models import Instance
from .quantity import ZERO, to_qty
from .reservation import free_qty, reserved_for


def claim_clauses(for_order_id: int | None) -> tuple:
    """Eine Instanz steht für eine Allokation zur Verfügung, wenn sie **freie Restmenge**
    hat (``reserved_quantity < quantity``) – oder bereits eine Reservierung für genau
    diesen Auftrag trägt (``for_order_id``). Reservierung wird **erst bei der Freigabe**
    scharf; eine Entwurfs-Vormerkung (``subject_of_order_id``) blockiert nichts."""
    if for_order_id is None:
        return (Instance.reserved_quantity < Instance.quantity,)
    return (
        or_(Instance.reserved_quantity < Instance.quantity,
            Instance.reservations.has_key(str(for_order_id))),  # noqa: W601 (JSONB ?-Operator)
    )


def fifo_candidates(db: Session, article_db_id: int, for_order_id: int | None = None,
                    lock: bool = False) -> list[Instance]:
    """Verbrauchbare/verkäufliche Instanzen eines Artikels: **freigegeben** (qc passed,
    am Lager), **freie Restmenge** (bzw. für diesen Auftrag reserviert), **FIFO nach
    Freigabe** (``released_at``, ersatzweise ``created_at``), dann Objektnummer.

    Mit ``for_order_id`` werden die für diesen Auftrag reservierten Instanzen **zuerst**
    verbraucht (Reservierung ist „vorgemerkter" Bestand dieses Auftrags).

    ``lock=True`` sperrt die Kandidaten (``SELECT … FOR UPDATE``) – Pflicht in **jedem
    Allokations-Schreibpfad** (Reservieren/Verbrauchen): ohne Sperre ist die Zuteilung
    ein Check-then-Act, bei dem zwei gleichzeitige Checkouts/Freigaben dieselbe letzte
    Instanz doppelt reservieren (Überverkauf). Reine Anzeigen/Previews lesen ohne Lock."""
    q = db.query(Instance).filter(
        Instance.article_id == article_db_id,
        Instance.is_active == True,
        *in_stock_clauses(),
        *claim_clauses(for_order_id),
    )
    if lock:
        q = q.with_for_update()
    rows = q.all()
    rows.sort(key=lambda i: (
        0 if (for_order_id is not None and reserved_for(i, for_order_id) > 0) else 1,
        i.released_at or i.created_at, i.object_id or 0))
    return rows


def avail_amount(inst: Instance, for_order_id: int | None) -> Decimal:
    """Wie viel dieser Instanz für die Allokation zur Verfügung steht: die **freie**
    Restmenge plus die für DIESEN Auftrag bereits reservierte Menge."""
    amt = free_qty(inst)
    if for_order_id is not None:
        amt += reserved_for(inst, for_order_id)
    return amt


def available_qty(candidates: list[Instance], for_order_id: int | None = None) -> Decimal:
    """Summe der **verfügbaren** Mengen einer Kandidatenliste (frei + eigene Reservierung)."""
    total = ZERO
    for c in candidates:
        total += avail_amount(c, for_order_id)
    return total


# ─── Gesperrt: EIN Zustand, EIN Wort ─────────────────────────────────────────────
#
# Eine Instanz ist **gesperrt**, wenn sie vorhanden, aber nicht verwendbar ist. Dafür gab
# es zwei Werte mit derselben Bedeutung: ``failed`` (eine Datenerfassung liess sie
# durchfallen) und ``blocked`` (ein «Sperren»-Schritt hat sie bewusst ausgesetzt). Beide
# hiessen dasselbe, verhielten sich gleich – und trugen doch verschiedene Namen; genau die
# Doppelung, die «eine Sache, eine Stelle» verbietet. Seit Migration ``085`` gibt es nur
# noch **einen** Wert.
#
# GESCHRIEBEN wird ausschliesslich ``blocked``; ``failed`` ist Altbestand und wird nur noch
# tolerant GELESEN (dieselbe Haltung wie beim entfallenen Standort-Typ 'lagerplatz').
BLOCKED = "blocked"
_BLOCKED_VALUES = (BLOCKED, "failed")


def is_blocked(inst) -> bool:
    """«Gesperrt» auf einem geladenen Objekt – Gegenstück zu ``blocked_clauses``."""
    return (inst.quality or "") in _BLOCKED_VALUES


def blocked_clauses() -> tuple:
    """SQLAlchemy-Bedingung für „gesperrt" (nicht verwendbar)."""
    return (Instance.quality.in_(_BLOCKED_VALUES),)


def unblocked_clauses() -> tuple:
    """SQLAlchemy-Bedingung für „nicht gesperrt"."""
    return (Instance.quality.notin_(_BLOCKED_VALUES),)


def rest_owner(inst) -> int | None:
    """**Wem gehört der unbeanspruchte Rest einer Instanz?** – die EINE Antwort.

    Am Lager: niemandem, er ist frei. Solange die Instanz aber noch in ihrem Erzeugungs-
    auftrag steckt (in Arbeit, gesperrt), gehört der Rest IHM – er hat ihn hervorgebracht.
    Sonst stünde an einem Stück mitten im Prozess «frei», und niemand würde gefragt, wenn
    es jemand nimmt.

    Zwei Leser teilen sich die Regel: die **Anteile** (``shares``, Menge je Halter) und die
    **Stücke** (``units.rows``, welche Nummer wem gehört). Vorher stand sie nur bei den
    Anteilen – das Instanz-Detail meldete dieselben drei Stück einmal als «Auftrag …003»
    und einmal als «frei»."""
    return None if is_in_stock(inst) or not inst.order_id else inst.order_id


def is_in_stock(inst) -> bool:
    """Dieselbe Regel wie ``in_stock_clauses`` – nur auf einem **geladenen** Objekt
    statt als Query-Bedingung.

    Beide Formen brauchte es schon immer (einmal fürs SQL, einmal für eine Instanz in
    der Hand), aber nur die SQL-Form war zentral. Die Objekt-Form lag viermal einzeln
    ausgeschrieben im Code (subject, recovery, routers/orders 2×) und in ``process``
    sogar in ZWEI Varianten: ``quality != 'failed'`` an der einen, ``quality ==
    'passed'`` an der nächsten Stelle. Beide meinten dasselbe – aber wer das liest,
    muss erst prüfen, ob der Unterschied Absicht ist. Jetzt gibt es eine Regel in
    zwei Formen, nicht zwei Regeln.

    Eine **gesperrte** Instanz fällt hier automatisch heraus (``quality != 'passed'``) –
    darum kostet das Sperren keine einzige zusätzliche Abfrage."""
    return (
        inst.quality == "passed"
        and inst.disposition == "in_stock"
        and to_qty(inst.quantity) > 0
    )


def in_stock_clauses() -> tuple:
    """SQLAlchemy-Bedingungen für „physisch am Lager" – qualitativ freigegeben
    (``quality=passed``) UND dispositiv am Lager (``disposition=in_stock``), Menge > 0."""
    return (
        Instance.quality == "passed",
        Instance.disposition == "in_stock",
        Instance.quantity > 0,
    )


def allocate(need, quantities: list) -> list[Decimal]:
    """FIFO-Allokation (rein/testbar): wie viel je Kandidat (in Reihenfolge) belegt
    wird, bis ``need`` gedeckt ist. Summe ≤ need; nie mehr als der Kandidat hat.
    Bruchmengen-fähig (``Decimal``): ``need``/``quantities`` dürfen Nachkommastellen haben."""
    out: list[Decimal] = []
    remaining = to_qty(need)
    for q in quantities:
        qd = to_qty(q)
        take = min(remaining, qd) if remaining > 0 else ZERO
        out.append(take)
        remaining -= take
    return out


def available(db: Session, article_db_id: int, for_order_id: int | None = None) -> Decimal:
    """Verfügbare (allozierbare) Menge eines Artikels: freie Restmenge plus – mit
    ``for_order_id`` – die für diesen Auftrag bereits reservierte Menge."""
    return available_qty(fifo_candidates(db, article_db_id, for_order_id), for_order_id)
