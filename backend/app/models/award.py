from decimal import Decimal
from typing import Optional

from sqlalchemy import BigInteger, DateTime, Index, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ..core.database import Base
from ..domain import vergabe
from .base import TimestampMixin, utcnow


class Award(Base, TimestampMixin):
    """**Eine Vergabe** – ein Dritter erbringt eine Leistung für uns (ADR 009 §3.6/§3.7).

    Heute ein **Transport**, künftig eine **Beschaffung**. Beides ist derselbe Ablauf,
    also **eine** Tabelle: der Zyklus existiert genau einmal, und das Beschaffungs-Modul
    erbt ihn ohne zweite Implementierung.

    **Der Anlass steht als blosse Objektnummer** (``subject_object_id``) – keine
    Fachspalten, keine Fallunterscheidung, keine nullable Sonderfelder. Die Fachdaten
    bleiben dort, wo sie hingehören (die Fuhre bzw. die Bedarfszeile); welcher Typ es
    ist, ist **ableitbar** – dieselbe Regel wie beim Halter (§15.2). Zwei Tabellen wären
    zwei Migrationen, zwei Router und zwei Stellen, an denen derselbe Zyklus gepflegt
    wird.

    **Der Zustand kommt aus der Registry** (``domain/vergabe``), und die Übergänge auch:
    ``vergabe.assert_transition`` ist die eine Prüfstelle. Ein zweiter Schreibweg wäre
    eine zweite Wahrheit.

    **Ab ``vergeben`` ist ein Zweiter gebunden** – das System rührt dann nichts mehr an,
    es **meldet**. Klappt es nicht, wird die Vergabe ``gescheitert`` (mit Pflicht-Grund)
    und die Sache bekommt eine **ganz normale zweite**; zurückgenommen wird nie, denn
    eine Korrektur ist ein neuer Eintrag (G5.1).
    """

    __tablename__ = "awards"
    __table_args__ = (
        # «Welche Vergaben hat dieser Anlass?» – die eine Leserichtung.
        Index("ix_awards_subject", "subject_object_id", "id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    #: **Der Anlass** – eine Objektnummer, mehr nicht (siehe Docstring). Heute die
    #: Instanz, die als Ausgangsort einer Fuhre dient; künftig eine Bedarfszeile.
    subject_object_id: Mapped[int] = mapped_column(BigInteger, nullable=False)

    #: Bei einem Transport: wohin. Für die Beschaffung leer – darum nullable, und das ist
    #: die **eine** Ausnahme von «keine Fachspalten»: ohne sie wäre eine Fuhre nicht von
    #: der nächsten zu unterscheiden, und der Anlass allein sagt nicht, wohin es geht.
    target_object_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)

    state: Mapped[str] = mapped_column(String(20), nullable=False,
                                       default=vergabe.ANGEFRAGT)
    channel: Mapped[str] = mapped_column(String(20), nullable=False)

    #: Der Dritte – als **Objektnummer**, wenn er ein Datensatz ist (Lieferantenportal:
    #: er hat sich angemeldet, um sein Angebot einzutippen). Steht erst mit der Vergabe
    #: fest; bei ``selbst`` schon vorher.
    provider_object_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)

    #: …oder als **Name**, wenn ihn eine Schnittstelle nennt («Swiss Post», «DPD»). Ein
    #: Frachtführer ist kein ERP-Datensatz; einen anzulegen wäre erfundene Daten – und
    #: zwar solche, die jemand später pflegen müsste. Nie beide leer (``awards._who``).
    provider_name: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)

    #: Der **Adapter**, über den gekauft und nachverfolgt wird (``sendcloud``/``shippo``).
    #: Ohne ihn wüsste der Kauf nicht, wen er fragen soll – und Raten wäre eine stille
    #: Ersatzwahl. Leer bei jedem Kanal ohne Schnittstelle.
    carrier: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)

    #: Was der Kauf hervorgebracht hat. Alles drei ist eine **Tatsache über die Sendung**,
    #: keine Absicht – darum steht es hier und nicht am Angebot.
    label_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    tracking_number: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    tracking_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    #: Was der Anbieter braucht, um den Kauf abzuschliessen – vom **Adapter** gefüllt und
    #: vom Aufrufer nur durchgereicht (Shippo legt die Sendung beim Abruf an, Sendcloud
    #: erst beim Kauf; beide Formen passen darum unter dasselbe Feld).
    shipment_ref: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    #: **Die Stücke, die diese Vergabe trägt** (PROCESS_CORE §15.5a). Wer Tarife holt,
    #: beschreibt ein Paket, und ein Paket hat einen Inhalt; vorher steht er nicht fest
    #: (jemand kann noch etwas herausnehmen). Gebraucht genau einmal: beim **Tracking**,
    #: das die Ankunft meldet, ohne dass jemand am Ziel steht.
    unit_ids: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)

    #: Der vereinbarte Preis. Erst mit der Vergabe verbindlich.
    amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2), nullable=True)
    currency: Mapped[Optional[str]] = mapped_column(String(3), nullable=True)

    #: Zugesagter Termin.
    due_at: Mapped[Optional[DateTime]] = mapped_column(DateTime(timezone=True),
                                                       nullable=True)

    #: Warum abgelehnt bzw. **gescheitert**. Pflicht beim Scheitern
    #: (``State.needs_reason``) – ohne ihn steht später da, dass es nicht geklappt hat,
    #: aber nicht warum.
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    #: Das gewählte Angebot (``award_offers.id``). Kein ForeignKey, damit ein Angebot
    #: nie ein Löschhindernis wird – gelöscht wird hier ohnehin nichts.
    chosen_offer_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)

    actor_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)


class AwardOffer(Base):
    """**Ein Angebot zu einer Vergabe** – die n-Seite desselben Vorgangs.

    Kein zweiter Mechanismus: ob ein Mensch es im Portal eintippt oder eine API es in
    zwei Sekunden liefert, ist der **Kanal** – die Zeile sieht gleich aus. Genau das ist
    die Einsicht hinter ADR 009 §3.6: Rate-Shopping IST eine Ausschreibung.

    Append-only wie jede Aufzeichnung: ein Angebot wird nicht geändert, es kommt ein
    neues. Darum ohne ``updated_at`` und ohne ``is_active``.
    """

    __tablename__ = "award_offers"
    __table_args__ = (Index("ix_award_offers_award", "award_id", "id"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    award_id: Mapped[int] = mapped_column(BigInteger, nullable=False)

    #: Wer anbietet – als **Objektnummer** (ein Lieferant, der es selbst eingetippt hat)
    #: oder als **Name** (ein Frachtführer, den die Schnittstelle nennt). Nie beide leer;
    #: geprüft im Dienst, wo der Grund danebensteht, statt als Constraint, der nur
    #: «verletzt» sagt.
    provider_object_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    provider_name: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)

    #: Über welchen **Adapter** dieses Angebot kam – und über welchen es gekauft würde.
    carrier: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)

    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="CHF")

    #: Zugesagte Dauer in Tagen. ``None`` = nicht genannt – kein geratener Wert.
    days: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)

    #: Was der Anbieter selbst dazu sagt (Dienstart, «Economy», …).
    label: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)

    #: Die Referenz beim Dritten – beim Plattform-Kanal die Tarif-Nummer, mit der das
    #: Angebot später gekauft wird. Für die anderen Kanäle leer.
    external_ref: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)

    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False,
    )
