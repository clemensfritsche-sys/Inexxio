"""Das **Subjekt** eines Auftrags – die Instanzen, auf die er wirkt.

Die Subjektart wird aus der **Gestalt des Auftrags abgeleitet** (kein Modus-Flag):

  • **produce** – Artikel + Menge, KEINE eigenen Schritte → der Auftrag fährt den
    Prozess des Artikels und ERZEUGT neue Instanzen.
  • **stock**   – eigene Schritte ohne vorgewählte Instanzen → das Subjekt wird per
    Artikel + Menge **FIFO ab Lager** allokiert (z. B. Verkauf über den Shop).
  • **chosen**  – ausgewählte, vorhandene Instanzen (``subject_of_order_id`` bei der
    Anlage gesetzt) → genau diese sind das Subjekt (Abweichung, gezielter Verkauf).

Das Subjekt wird bei der **Freigabe** hergestellt und – beim Bestands-Zugriff (stock/
chosen) – zugleich für genau diesen Auftrag **reserviert** (kein Doppelverkauf/-verbrauch).
Enthält der Ablauf einen Verkauf, verlassen die Subjekte bei Abschluss den Bestand
(``sold``, siehe ``process._finalize_subjects``); sonst bleibt der Verbleib unverändert.
"""

from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..domain import event_types
from ..models import Instance, InstanceOrderLink, Order
from .admin import log_audit
from .inventory import allocate, fifo_candidates
from .order_lines import lines_for
from .processes import order_custom_steps
from .reservation import free_qty, reserve, reserved_for
from .serialization import create_instances_for_order


def record_link(db: Session, instance_object_id: int | None, order_id: int) -> None:
    """Verarbeitung einer Instanz durch einen Auftrag **dauerhaft** festhalten (idempotent) –
    unabhängig von späteren Bindungen/Reservierungen (siehe ``InstanceOrderLink``)."""
    if not instance_object_id:
        return
    exists = (
        db.query(InstanceOrderLink.id)
        .filter(InstanceOrderLink.instance_object_id == instance_object_id,
                InstanceOrderLink.order_id == order_id)
        .first()
    )
    if not exists:
        db.add(InstanceOrderLink(instance_object_id=instance_object_id, order_id=order_id))


def chosen_subjects(db: Session, order: Order, article_id: int | None = None) -> list[Instance]:
    """Die bei der Anlage ausgewählten Subjekt-Instanzen (Bestands-Auftrag). Mit
    ``article_id`` nur die einer Position eines **Mehrpositionen**-Auftrags (mehrere
    Artikel können unter demselben Auftrag fixiert sein)."""
    q = db.query(Instance).filter(Instance.subject_of_order_id == order.id, Instance.is_active == True)
    if article_id is not None:
        q = q.filter(Instance.article_id == article_id)
    return q.order_by(Instance.object_id).all()


def is_deviation(order: Order) -> bool:
    """Abweichung = Unter-Auftrag mit ``reason='deviation'`` (Reklamation/Fehler/Nacharbeit/
    Abbruch-Folgeauftrag). Wirkt auf bereits «in der Hand» befindliche Instanzen des Eltern-
    Auftrags – ohne Lager-FIFO/-Reservierung. Ein **Nachschub**-Unter-Auftrag (``reason=
    'supply'``) ist KEINE Abweichung: er produziert/beschafft neuen Bestand und läuft wie ein
    ganz normaler Produktionsauftrag (subject_kind ``produce``)."""
    return getattr(order, "reason", None) == "deviation"


def subject_kind(db: Session, order: Order) -> str:
    """Abgeleitete Subjektart (Artikel ist immer der Anker) – KEIN Modus-Flag, KEINE
    Quellen-Übersteuerung:

    ``produce`` – der Auftrag bringt Bestand **herein** und ERZEUGT neue Instanzen. Das
      gilt für KEINE eigenen Schritte (der Auftrag fährt den Artikel-Prozess) **ebenso wie
      für eigene Schritte, die Bestand hereinbringen** – Beschaffung/Ressource haben in der
      Registry die Subjekt-Rolle ``PRODUCE``. Es wird NIE vorhandener Bestand vorausgesetzt.
    ``stock``   – eigene Schritte, die auf **vorhandenen** Bestand zugreifen (Verkauf →
      ``STOCK``) bzw. bestehende Instanzen bearbeiten (Bewegung/Prüfung/Verschrottung →
      ``INSTANCE``): ``quantity`` Stück, FIFO ab Lager, optional durch fixierte Instanzen
      ergänzt. Was fehlt, deckt ein **Nachschub-Unter-Auftrag** (``services/supply.py``) –
      der zugreifende Schritt ist bis dahin blockiert.

    Massgeblich ist die **deklarierte** Subjekt-Rolle der Schritte (REA-Registry,
    ``event_types.derive_subject_mode`` mit ``SUBJECT_PRECEDENCE``) – NICHT die blosse
    Anwesenheit eines Schritts. So kippt ein Schritt, der Bestand HEREINBRINGT (Beschaffung),
    den Auftrag nicht fälschlich in eine Bestands-Operation, die dann still an „kein Bestand"
    scheitert (kein Subjekt, keine Instanz, keine Fehlermeldung). Eine reine (Entwurfs-)Pin-
    Auswahl ohne Schritte kippt den Auftrag ebenfalls NICHT (sonst scheitert die Herstellung)."""
    if is_deviation(order):
        return "deviation"   # wirkt auf bereits vorhandene Instanzen (kein Lager-Zugriff)
    steps = order_custom_steps(db, order.id)
    if not steps:
        return "produce"     # keine eigenen Schritte → Artikel-Prozess, erzeugt Instanzen
    # Eigene Schritte: die Subjektart ist die DEKLARIERTE Rolle (Registry), nicht die
    # Anwesenheit. Bringt der Ablauf Bestand herein (PRODUCE: Beschaffung/Ressource), ERZEUGT
    # der Auftrag – nur ein Zugriff auf vorhandenen Bestand (STOCK/INSTANCE) ist eine
    # Bestands-Operation.
    mode = event_types.derive_subject_mode({s.step_type for s in steps})
    return "produce" if mode == event_types.PRODUCE else "stock"


def order_instances(db: Session, order: Order) -> list[Instance]:
    """Die Instanzen, auf die der Auftrag wirkt (einheitlich, ohne Modus-Flag):

    Bestands-Auftrag → die von ihm **als Subjekt verarbeiteten** Instanzen. Massgeblich ist
    die **dauerhafte** Verarbeitungs-Historie (``instance_order_links``, bei der Freigabe
    geschrieben), vereinigt mit der aktuellen Bindung (``subject_of_order_id``; deckt den
    Entwurf VOR der Freigabe ab). So bleiben die Instanzen auch **nach Abschluss** sichtbar,
    obwohl die Bindung dann gelöst ist.
    Sonst (produzierender Auftrag) → die **unter ihm erzeugten** Instanzen."""
    oids = {
        row.instance_object_id
        for row in db.query(InstanceOrderLink.instance_object_id)
        .filter(InstanceOrderLink.order_id == order.id, InstanceOrderLink.is_active == True)
        .all()
    }
    oids |= {i.object_id for i in chosen_subjects(db, order)}
    if oids:
        return (
            db.query(Instance)
            .filter(Instance.object_id.in_(oids), Instance.is_active == True)
            .order_by(Instance.object_id)
            .all()
        )
    return (
        db.query(Instance)
        .filter(Instance.order_id == order.id, Instance.is_active == True)
        .order_by(Instance.object_id)
        .all()
    )


# Terminaler Verbleib: das Teil ist aus dem Auftrag «raus» – verschrottet, verkauft oder
# verbaut. Solche Instanzen werden nicht mehr weiterverarbeitet (bewegt/geprüft/bestückt).
TERMINAL_DISPOSITIONS = ("scrapped", "sold", "consumed")


def order_active_instances(db: Session, order: Order) -> list[Instance]:
    """Wie ``order_instances``, aber OHNE Instanzen mit **terminalem Verbleib** (verschrottet/
    verkauft/verbaut). Für die laufende Verarbeitung UND den Abschluss: ein verschrottetes Teil
    soll nicht mehr bewegt/geprüft/bestückt werden – der Auftrag wird mit seinen GUTEN Teilen
    fertig (die volle Liste inkl. terminaler Teile bleibt für die Anzeige via ``order_instances``)."""
    return [i for i in order_instances(db, order)
            if (i.disposition or "") not in TERMINAL_DISPOSITIONS]


def materialize_subject(db: Session, order: Order, actor_id: int) -> None:
    """Bei Freigabe das Subjekt herstellen. Committet NICHT – der Aufrufer schliesst ab.

    stock   → ``quantity`` Instanzen des Artikels binden: zuerst die fixierten (gepinnten)
      Instanzen, den Rest **FIFO ab Lager** auffüllen – alle für diesen Auftrag reserviert.
    produce → neue Bestands-Instanzen erzeugen (Serialisierung aus dem Artikel).

    Entscheidend ist die **deklarierte Subjekt-Rolle** der Schritte (siehe ``subject_kind``);
    eine Pin-Auswahl ohne Schritte erzeugt trotzdem (statt an fehlendem Bestand zu scheitern),
    und ein Schritt, der Bestand hereinbringt (Beschaffung), erzeugt ebenfalls.

    deviation → die (bereits vorhandenen) Subjekt-Instanzen werden nur übernommen, ohne
      Lager-Allokation/-Reservierung (sie sind schon in Arbeit/im Besitz)."""
    if is_deviation(order):
        _bind_deviation_subjects(db, order, actor_id)
        return
    kind = subject_kind(db, order)   # abgeleitet (produce | stock | deviation)
    if kind == "stock":
        if order.article_id is not None:
            _allocate_stock_subject(db, order, actor_id)
        else:
            _allocate_stock_subject_multiline(db, order, actor_id)
        return
    create_instances_for_order(db, order, actor_id)


def _bind_deviation_subjects(db: Session, order: Order, actor_id: int) -> None:
    """Abweichung: die gewählten Instanzen nur **dauerhaft als verarbeitet** vermerken –
    KEINE Lager-Allokation/-Reservierung. Die Instanzen können jeden Verbleib haben
    (in Arbeit, am Lager, …); die Abweichung wirkt direkt auf sie."""
    bound = chosen_subjects(db, order)
    if not bound:
        raise HTTPException(409, detail="Für die Abweichung sind keine Instanzen gewählt")
    for inst in bound:
        record_link(db, inst.object_id, order.id)
    log_audit(db, "instances", None, "Abweichung übernimmt Instanzen", actor_id, object_id=order.object_id)


def _allocate_stock_for(db: Session, order: Order, article_id: int, quantity: int) -> None:
    """Kern der Bestands-Allokation für GENAU einen Artikel + Menge unter einem Auftrag:

    1. die fixierten (gepinnten) Instanzen DIESES Artikels prüfen – sie müssen
       **freigegeben** (qc passed) und am Lager sein, sonst ist die Freigabe nicht
       möglich – und reservieren;
    2. den **Rest FIFO ab Lager** auffüllen.
    Jede gebundene Instanz wird dauerhaft als „von diesem Auftrag verarbeitet" vermerkt.
    Wiederverwendet vom Einzel-Artikel-Auftrag (``order.article_id``) UND – je Position –
    vom Mehrpositionen-Auftrag (``order_lines``)."""
    pinned = chosen_subjects(db, order, article_id=article_id)
    for inst in pinned:                                    # fixierte: erst bei Freigabe „scharf"
        if not (inst.quality == "passed" and inst.disposition == "in_stock"):
            raise HTTPException(
                409, detail=f"Instanz {inst.object_id} ist nicht freigegeben/am Lager – Freigabe nicht möglich")
        need = inst.quantity - reserved_for(inst, order.id)
        if free_qty(inst) < need:                          # von einem anderen Auftrag belegt
            raise HTTPException(
                409, detail=f"Instanz {inst.object_id} ist bereits für einen anderen Auftrag reserviert")
        reserve(inst, order.id, need)                      # ganze Pin-Instanz, OHNE Teilung
        record_link(db, inst.object_id, order.id)
    remaining = quantity - sum(i.quantity for i in pinned)
    if remaining <= 0:
        return                                             # vollständig durch fixierte gedeckt
    cands = fifo_candidates(db, article_id, for_order_id=None)   # freie Restmengen
    # **Partielle Deckung ist erlaubt** (kein Fehler mehr bei Unterdeckung): es wird FIFO
    # reserviert, was am Lager ist; die **Fehlmenge** deckt ein Nachschub-Unter-Auftrag
    # (``services/supply.py``). Der erste auf das Subjekt zugreifende Schritt (Bewegung/…)
    # bleibt so lange **blockiert** (abgeleitet aus dem Bestand), bis der Nachschub liefert.
    for cand, take in zip(cands, allocate(remaining, [free_qty(c) for c in cands])):
        if take <= 0:
            continue
        cand.subject_of_order_id = order.id               # Subjekt-Markierung (ganz/teilweise)
        reserve(cand, order.id, take)                     # mengengenaue Reservierung
        record_link(db, cand.object_id, order.id)


def _allocate_stock_subject(db: Session, order: Order, actor_id: int) -> None:
    """Subjekt eines Einzel-Artikel-Bestands-Auftrags **bei der Freigabe** binden +
    reservieren (siehe ``_allocate_stock_for``)."""
    if not order.article_id or not order.quantity:
        raise HTTPException(400, detail="Artikel und Menge sind für diesen Auftrag erforderlich")
    _allocate_stock_for(db, order, order.article_id, order.quantity)
    log_audit(db, "instances", None, "Bestand für Auftrag reserviert (ggf. teilweise)",
              actor_id, object_id=order.object_id)


def _allocate_stock_subject_multiline(db: Session, order: Order, actor_id: int) -> None:
    """Subjekt eines **Mehrpositionen**-Auftrags (``order_lines``) binden + reservieren:
    je Position dieselbe Logik wie beim Einzel-Artikel-Auftrag (fixiert zuerst, Rest FIFO),
    nur je Artikel/Menge der Position statt ``order.article_id``/``order.quantity``."""
    lines = lines_for(db, order)
    if not lines:
        raise HTTPException(400, detail="Mehrpositionen-Auftrag ohne Positionen")
    for line in lines:
        _allocate_stock_for(db, order, line.article_id, line.quantity)
    log_audit(db, "instances", None,
              f"Bestand für {len(lines)} Position(en) reserviert (ggf. teilweise)",
              actor_id, object_id=order.object_id)
