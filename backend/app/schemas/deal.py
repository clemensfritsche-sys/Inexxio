"""**Der Geldvorgang über die API** – die Formen des Moduls «Zahlung».

Eigenständig wie sein Dienst: keine Zeile hiervon hängt an ``schemas/process.
PurchaseEmbed``. Beträge reisen als **String** – wo es auf den Rappen ankommt, wird nicht
durch ``float`` gerechnet, auch nicht auf dem Weg durch JSON.
"""

from datetime import date
from typing import Any, Optional

from pydantic import BaseModel, Field


class DealStage(BaseModel):
    """Eine Stufe – Schlüssel, Beschriftung und das Verb, wenn sie dran ist."""

    key: str
    label: str
    #: Was man **tut**, um diese Stufe zu verlassen. Leer bei der letzten: dort ist man
    #: angekommen, und der Zustand steht schon als Beschriftung da.
    verb: Optional[str] = None
    done: bool = False
    active: bool = False


class DealParty(BaseModel):
    """Eine wählbare Gegenpartei – **Objektnummer und Name**, sonst nichts.

    Dieselbe Form wie jede andere Referenz im Haus (``ObjectSelect``), damit die
    Oberfläche kein zweites Auswahlfeld braucht.
    """

    object_id: int
    name: str = ""


class DealEntryOut(BaseModel):
    """Eine Zeile Geld – eine Forderung oder eine Zahlung.

    ``kind`` sagt, welche Achse. Ein **negativer** Betrag ist keine Ausnahme, sondern die
    Gutschrift bzw. die Erstattung – dafür gibt es keine dritte Art.
    """

    id: int
    #: ``charge`` (Forderung) · ``payment`` (Geld) – ``domain/deal.KINDS``.
    kind: str
    amount: str
    booked_on: Optional[date] = None
    #: Nur bei einer Forderung. ``None`` heisst «steht nicht fest», nicht «heute».
    due_on: Optional[date] = None
    reference: Optional[str] = None
    note: Optional[str] = None
    #: **Fällig UND noch etwas offen** – beides zusammen, sonst nicht. Eine Ableitung
    #: des Servers; eine zweite Formel im Browser wiche ab und sähe trotzdem richtig aus.
    overdue: bool = False


class DealEmbed(BaseModel):
    """**Der Geldvorgang**, wie ihn die Ausführungsstelle braucht.

    ``None`` bei jedem anderen Modultyp – die Oberfläche braucht damit keine
    Fallunterscheidung nach dem Modul (wie ``needs`` und ``target``).

    **Alles zum Zeichnen reist mit**: Wörter, Stufen, Verben, Zahlen und was man tun
    darf. Die Oberfläche fragt für kein einziges ``if`` nach der Richtung.
    """

    # ─── Die Richtung, und was aus ihr folgt: lauter Wörter ──────────────────────
    #: ``in`` (Geld kommt) · ``out`` (Geld geht) – ``domain/deal``.
    direction: str = "out"
    #: Wie der Vorgang heisst: «Einnahme» ↔ «Ausgabe».
    label: str = ""
    party_word: str = ""
    party_plural: str = ""
    charge_word: str = ""
    payment_word: str = ""
    open_word: str = "Offen"
    #: Das Wort für die eine Gegenhandlung – oder ``None``, wo sie nicht geht.
    undo: Optional[str] = None

    # ─── Wo er steht, und was man tun darf ───────────────────────────────────────
    stage: str = "offer"
    stages: list[DealStage] = Field(default_factory=list)
    #: ►►► **Was hier JETZT möglich ist** (``services/deal.ACTIONS``). ◄◄◄
    #:
    #: Die Oberfläche rendert eine Aktion genau dann, wenn ihr Verb hier steht – und
    #: **dieselbe** Tabelle weist in ``apply`` ab. Wäre das nur ein Anzeige-Hinweis,
    #: liefen Knopf und Tür beim nächsten Verb auseinander.
    can: list[str] = Field(default_factory=list)

    # ─── Was in der Definition steht ─────────────────────────────────────────────
    #: **Worum es geht** – der Satz aus der Definition, Pflicht beim Modellieren.
    subject: str = ""
    #: **Erst weiter, wenn bezahlt?** Der einzige Schalter dieses Moduls.
    prepaid: bool = False
    #: Die **zugelassenen** Gegenparteien. Leer heisst frei – dann wird gesucht.
    allowed: list[DealParty] = Field(default_factory=list)

    # ─── Die Zusage ──────────────────────────────────────────────────────────────
    party_object_id: Optional[int] = None
    party_name: Optional[str] = None
    #: **Was vereinbart ist** – nicht was gefordert und nicht was gezahlt ist.
    amount: Optional[str] = None
    due_days: Optional[int] = None
    reference: Optional[str] = None
    note: Optional[str] = None
    agreed_on: Optional[date] = None

    # ─── Forderung und Geld: lauter Ableitungen, keine Spalte ────────────────────
    charged: Optional[str] = None
    paid: Optional[str] = None
    #: **Forderungen − Zahlungen.** Darf negativ sein: dann schulden **wir**.
    open: Optional[str] = None
    #: **Zugesagt − berechnet** – und damit die Vorgabe der nächsten Rechnung. Die Zahl,
    #: die es ohne die Trennung der beiden Achsen gar nicht geben könnte.
    uncharged: Optional[str] = None
    #: Ist bezahlt, was zugesagt wurde? Die eine Frage, die ``prepaid`` stellt – und
    #: sie fragt nach der **Zusage**, nicht nach dem offenen Betrag: wer nichts
    #: berechnet hat, hat null offen, und das hiesse sonst «bezahlt».
    settled: bool = False
    entries: list[DealEntryOut] = Field(default_factory=list)


class DealUpdate(BaseModel):
    """Eine Handlung am Geldvorgang – **ein** Endpunkt, sechs Verben.

    ``quote``   die Angaben erfassen (``party``, ``amount``, ``due_days``,
                ``reference``, ``note``) – solange noch nichts zugesagt ist
    ``agree``   zusagen bzw. beauftragen; ``party`` und ``amount`` sind dabei Pflicht
    ``revoke``  stornieren – **die** Gegenhandlung, ab der Schwelle
    ``charge``  eine **Forderung** buchen (``amount`` – Vorgabe *zugesagt − berechnet*;
                ``booked_on``, ``due_on``, ``reference``, ``note``)
    ``pay``     eine **Zahlung** buchen (``amount`` – Vorgabe der offene Betrag)
    ``void``    eine Geld-Zeile zurücknehmen (``entry``)

    **``charge`` und ``pay`` haben keine Stufe** – Geld fliesst, sobald zugesagt ist, und
    auch noch nach einem Storno; eine Anzahlung muss erstattet werden können. Sie stehen
    trotzdem in ``can``: «was darf ich hier tun» ist EINE Frage.

    **Nur gesendete Felder wirken** (``exclude_unset``): ein Feld, das nicht mitkommt,
    bleibt, wie es war. Sonst löschte jeder Aufruf alles, was er nicht ausdrücklich
    wiederholt.
    """

    action: str
    #: Die Objektnummer der Gegenpartei. ``None`` heisst «niemand» – das ist eine Wahl.
    party: Optional[int] = None
    #: Als **String**, weil es ein Eingabefeld ist: ein halb getipptes Feld hat keine
    #: Zahl, und ein Komma ist ein Dezimaltrennzeichen, kein Fehler.
    amount: Optional[str] = None
    due_days: Optional[int] = None
    reference: Optional[str] = None
    note: Optional[str] = None
    booked_on: Optional[date] = None
    due_on: Optional[date] = None
    #: Welche Zeile zurückgenommen wird (``void``).
    entry: Optional[int] = None

    def changes(self) -> dict[str, Any]:
        """Was tatsächlich gesendet wurde – ohne ``action``."""
        return self.model_dump(exclude={"action"}, exclude_unset=True)
