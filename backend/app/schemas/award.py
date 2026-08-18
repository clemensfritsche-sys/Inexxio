"""Die Vergabe – die API-Form (PROCESS_CORE §15.5, SYSTEM_LOGIC §7.3).

**Der Zustand ist eine Auskunft, kein Eingabefeld.** Geschrieben wird nie ein Zustand,
sondern ein **Vorgang** (anfragen · anbieten · vergeben · abnehmen · ablehnen ·
scheitern); welcher Zustand daraus folgt, entscheidet die Registry. Ein
Status-Dropdown wäre die zweite Stelle, an der die Übergangsmatrix gepflegt wird – und
die vergisst man.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, computed_field

from ..domain import vergabe
from .place import HolderRef


class AwardOfferResponse(BaseModel):
    """Ein Angebot. Je Kanal auf anderem Weg entstanden, hier dieselbe Zeile."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    provider: Optional[HolderRef] = None
    amount: Decimal
    currency: str
    #: Zugesagte Dauer in Tagen. ``None`` = nicht genannt, nicht «sofort».
    days: Optional[int] = None
    label: Optional[str] = None


class AwardResponse(BaseModel):
    """Eine Vergabe mit ihren Angeboten."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    #: Der Anlass – eine blosse Objektnummer (bei einem Transport der Ausgangsort).
    subject_object_id: int
    target: Optional[HolderRef] = None
    state: str
    channel: str
    provider: Optional[HolderRef] = None
    amount: Optional[Decimal] = None
    currency: Optional[str] = None
    due_at: Optional[datetime] = None
    reason: Optional[str] = None
    chosen_offer_id: Optional[int] = None
    offers: list[AwardOfferResponse] = Field(default_factory=list)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def state_label(self) -> str:
        """Wie der Zustand heisst – **aus der Registry**, nicht aus der Oberfläche."""
        return vergabe.STATES[self.state].label if self.state in vergabe.STATES else self.state

    @computed_field  # type: ignore[prop-decorator]
    @property
    def state_tone(self) -> str:
        """Der **Ampelton** – ``pending`` · ``done`` · ``danger``.

        Er reist mit den Daten, statt in der Oberfläche noch einmal zugeordnet zu werden:
        eine zweite Tabelle veraltet beim ersten neuen Zustand, und sie tut es
        **stillschweigend** (die Lehre aus ``ModuleFacts.tone`` – dort gab ein
        vergessener Rückfall jedem Modul die Farbe der Datenerfassung).
        """
        return vergabe.STATES[self.state].tone if self.state in vergabe.STATES else "danger"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def open(self) -> bool:
        """Läuft sie noch? Abgeleitet aus ``terminal`` – keine zweite Liste."""
        return self.state in vergabe.STATES and vergabe.is_open(self.state)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def next_states(self) -> list[str]:
        """Welche Übergänge von hier aus möglich sind.

        Die Oberfläche bietet damit genau das an, was der Dienst annimmt – sie rechnet
        die Matrix nicht nach. Eine Schaltfläche, die scheitert, ist schlimmer als keine.
        """
        return list(vergabe.TRANSITIONS.get(self.state, ()))


class AwardCreate(BaseModel):
    """Eine Vergabe **anfragen** (V1).

    Sie entsteht durch den Klick eines Menschen – das System legt sie nie selbst an
    (PROCESS_CORE §15.7). Genau daran sind die abgeleitete Bereitstellung und die
    Begleit-Bewegungen des Vorgängers gescheitert.
    """

    subject_object_id: int
    target_object_id: Optional[int] = None
    #: plattform | portal | selbst – **die einzige Variable** des Zyklus.
    channel: str = vergabe.PORTAL
    #: Nur bei ``selbst`` sinnvoll: wer die Leistung erbringt, steht dort von Anfang an fest.
    provider_object_id: Optional[int] = None


class OfferCreate(BaseModel):
    """Ein Angebot eintragen (V2) – der Weg des Kanals ``portal``."""

    provider_object_id: int
    amount: Decimal
    currency: str = "CHF"
    days: Optional[int] = None
    label: Optional[str] = None


class GrantInput(BaseModel):
    """**Vergeben** (V3) – die Wahl eines Menschen.

    Bei einem Kanal mit Angeboten ist das gewählte **Angebot** die Grundlage; ein daneben
    getippter Preis wäre eine zweite Wahrheit über dieselbe Vereinbarung. Nur ``selbst``
    nennt Dritten und Preis unmittelbar.
    """

    offer_id: Optional[int] = None
    provider_object_id: Optional[int] = None
    amount: Optional[Decimal] = None
    currency: Optional[str] = None
    due_at: Optional[datetime] = None


class DeliverInput(BaseModel):
    """**Erbracht** (V4) – und erst jetzt entsteht die Ablage.

    ``instance_unit_ids`` sind die Stücke, die angekommen sind. Leer heisst «keine» –
    nicht «alle»: welche es waren, weiss der Mensch am Ziel, und ein geratener Satz wäre
    eine Ablage, die niemand beobachtet hat.
    """

    instance_unit_ids: list[int] = Field(default_factory=list)


class ReasonInput(BaseModel):
    """Ablehnen (V5) oder **Scheitern** (V6). Beim Scheitern ist der Grund **Pflicht** –
    ohne ihn steht später da, dass es nicht geklappt hat, aber nicht warum."""

    reason: str = ""
