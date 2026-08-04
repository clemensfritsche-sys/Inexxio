from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import BigInteger, Boolean, Date, DateTime, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ..core.database import Base
from .base import TimestampMixin


class Order(Base, TimestampMixin):
    """Auftrag — interner Bedarf, der einen Artikel-Prozess auslöst.

    Beispiel: «5× Artikel 1003». Wird der Auftrag freigegeben (status=released)
    und besitzt der Artikel einen ``purchase``-Prozessschritt, instanziiert das
    System die zugehörige Bestellung (Purchase Order).

    Statuswerte (`status`): draft → Entwurf | released → Freigegeben | inactive → Inaktiv
    """

    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    object_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, unique=True, nullable=True, index=True
    )

    status: Mapped[str] = mapped_column(String(20), default="draft", nullable=False)
    title: Mapped[Optional[str]] = mapped_column(String(255))

    # Bedarf: welcher Artikel in welcher Menge. Die **Subjektart wird abgeleitet**
    # (kein Modus-Flag, siehe ``services/subject.py``):
    #   produce – ``article_id`` + ``quantity``, KEINE eigenen Schritte → fährt den
    #             **Prozess des Artikels** und ERZEUGT Instanzen (auch jeder Nachschub).
    #   stock   – eigene Schritte (``article_process_steps`` mit ``order_id``) ohne
    #             vorgewählte Instanzen → Subjekt FIFO ab Lager (Verkauf/Entnahme).
    #   chosen  – wirkt auf vorgewählte, vorhandene Instanzen (``instances.subject_of_order_id``).
    article_id: Mapped[Optional[int]] = mapped_column(BigInteger, index=True, nullable=True)
    # Bestellmenge als Dezimalzahl (NUMERIC(14,3)) – ganze Stück ODER Bruchmenge (kg/m²/m³/l).
    quantity: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 3), nullable=True)
    desired_delivery_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    # Stripe-Bezug (Quelle der Wahrheit für Abos): die Stripe-Subscription (Status wird
    # gespiegelt). Die Checkout-Session lebt am ``CheckoutIntent`` (stripe_session_id).
    stripe_subscription_id: Mapped[Optional[str]] = mapped_column(String(80), index=True)

    # Prozess-Eckdaten für die Durchlaufzeit (Freigabe → Abschluss).
    released_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Wiederkehrend (Compliance/Termine + Abos) – direkt am Auftrag, KEIN eigenes
    # Objekt: ist ``recurrence_active``, erzeugt der Auftrag beim **Abschluss**
    # automatisch den nächsten (Entwurf, Termin = ``recurrence_anchor`` + Periode).
    recurrence_active: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False)
    recurrence_interval_days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    recurrence_lead_time_days: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False)
    recurrence_anchor: Mapped[Optional[date]] = mapped_column(Date, nullable=True)  # nächster Soll-/Ablauftermin
    recurring_parent_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True, index=True)  # Auftrag, aus dem dieser entstand
    # Abo-Typ (gespiegelt vom Verkaufspreis): usage = Nutzungsabo | product = Produktabo.
    # Steuert die per-Zyklus-Logik (``invoice.paid``): Produktabo erzeugt je Zyklus ein
    # Folge-Fulfillment, Nutzungsabo nicht (reiner Zugang/Miete, einmalig erfüllt).
    recurrence_kind: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)

    # Ersetzen statt Versionierung: Objektnummer des Nachfolge-Auftrags (alt → neu).
    replaced_by_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True, index=True)

    # **Unter-Auftrag** (``parent_order_id`` = Objektnummer des Eltern-Auftrags). EIN
    # Mechanismus, mehrere Gründe (``reason``):
    #   'deviation'     – Reklamation/Fehler/Nacharbeit/Abbruch-Folgeauftrag: wirkt auf bereits
    #                     vorhandene Instanzen des Eltern-Auftrags. Sie **nimmt ihr Stück heraus**
    #                     statt den Eltern anzuhalten: was in Klärung ist, zählt nicht mehr als
    #                     gesichert (``process.deviated_quantities``) und erscheint als
    #                     Unterdeckung am Schritt, der es braucht.
    #   'supply'        – Nachschub: deckt einen Bedarf (Verkauf/Verbrauch) des Eltern, der nicht
    #                     aus dem Bestand gedeckt war. Produziert/beschafft die Fehlmenge und
    #                     **pinnt** sie bei Abschluss an den Eltern (``process._peg_supply_to_parent``).
    #                     Der betroffene Schritt ist «blockiert», bis der Nachschub liefert
    #                     (abgeleiteter Zustand, kein Auto-Trigger).
    #   'return'        – Retoure/Erstattung: festes Subjekt = **verkaufte** Instanzen,
    #                     ``parent`` = Original-Verkauf (Geld über das ``sale``-Modul im
    #                     Kredit-Modus, Ware über die Bewegung). KEINE Eltern-Pause.
    #   'replenishment' – Auto-Nachbestellung bei unterschrittenem Meldebestand
    #                     (``services/replenishment.py``): eigenständig, OHNE Eltern.
    #   'provisioning'  – Bereitstellung: bringt Instanzen an den Ort, den ein Schritt des
    #                     Eltern-Auftrags verlangt (``services/provisioning.py``). Festes
    #                     Subjekt = genau diese Instanzen; der betroffene Schritt ist
    #                     «blockiert», bis sie da sind (wie Nachschub, keine Eltern-Pause).
    parent_order_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True, index=True)
    # VARCHAR(20): 'replenishment' hat 13 Zeichen – die frühere Breite 12 liess jede
    # Auto-Nachbestellung mit einem Truncation-Fehler scheitern (Migration 060).
    reason: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # deviation | supply | return | replenishment | provisioning

    # **Aus welchem Schritt des Eltern-Auftrags ist dieser Unter-Auftrag hervorgegangen?**
    # Bindet ihn an seinen Auslöser und gibt ihm damit eine Position im Ablauf: die
    # Bereitstellung wartet für genau diesen Schritt, die Abweichung wurde an genau dieser
    # Stelle gemeldet. Früher hiess die Spalte ``provisioning_step_id`` – dieselbe Frage,
    # nur für eine Art (Migration 087).
    origin_step_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True, index=True)

    # **Woher der Entwurf seine Anteile nimmt** – ``{instanz_objektnr: quell_auftrag_db_id}``.
    #
    # Eine Instanz ist eine MENGE, und ihre Menge ist immer vollständig aufgeteilt: jeder
    # Anteil gehört genau einem Auftrag oder ist frei (``instances.reservations``). Wer einen
    # Anteil auswählt, wählt damit auch, WEM er ihn wegnimmt – und genau das steht hier.
    #
    # Ohne diese Notiz wäre die Frage bei der Freigabe nicht beantwortbar: hält eine Charge
    # à 4 Stück zwei Ansprüche (Hauptauftrag 2, Abweichung 2) und ein dritter Auftrag greift
    # 1 Stück, müsste das System raten, wer verliert. Es rät nicht mehr – es liest hier nach.
    # Ein leerer Eintrag heisst «freier Anteil»: dann verliert niemand etwas.
    #
    # Bis zur Freigabe ist es eine Vormerkung; danach ist sie erledigt und wird geleert.
    pick_sources: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # **Abbrechen ist ein Vollzug, kein Antrag** (seit Migration 086): der Auftrag ist im
    # selben Moment inaktiv – endgültig, keine Reaktivierung. ``abort_into_id`` ist nur noch
    # der Zeiger «fortgeführt in …» auf den Abweichungsauftrag, der die Instanzen übernommen
    # hat; die Anzeige macht daraus «Abgebrochen» statt «Inaktiv» (verworfen ≠ fortgeführt).
    abort_into_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True, index=True)

    # **«Die Rückführung ist gekappt»** (Testnotiz #563): was dieser Auftrag übernommen hat,
    # kommt NICHT zurück – er führt es zu Ende, der Verleiher bekommt nichts mehr.
    #
    # Das ist eine **Aussage über die Zukunft**, keine Wahl zwischen zwei Antworten: sie sagt
    # etwas, das das System noch nicht wissen kann. Ohne sie wartet ein Verleiher, dem alles
    # entzogen wurde, bis der Abzweig endet – obwohl längst feststeht, dass nichts
    # zurückkommt. Mit ihr ist er im selben Moment abgebrochen, fortgeführt in diesem Auftrag.
    #
    # **Die Kaskade fällt daraus heraus, sie ist keine zweite Regel:** ein gekappter Auftrag
    # deckt niemanden (``supply.covering_sub_orders``), also entscheidet ``recovery.
    # auto_resolve`` beim Verleiher sofort – und geht, wenn der dadurch abgebrochen wird, eine
    # Ebene höher. So kappt ein Unter-Unter-Auftrag die ganze Kette bis zum Hauptauftrag.
    returns_nothing: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
