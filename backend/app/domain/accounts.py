"""►►► **Der Kontotyp – wer jemand WIRTSCHAFTLICH ist** (Testnotiz #1042). ◄◄◄

*«Trenne zwei Dinge, die heute vermischt sind: **Rolle** (was jemand im System darf) und
**Kontotyp** (wer jemand wirtschaftlich ist).»*

**Rolle ≠ Kontotyp.** Die Rolle ist eine **Berechtigungs**frage (Kunde · Lieferant ·
Mitarbeiter · Admin – was jemand *für uns* tut), der Kontotyp eine **Stammdaten**frage
(Privat ↔ Geschäft – als wer er auf einem Beleg steht). Bis hierher hing die
Sichtbarkeit der Firmenfelder an der Rolle ``supplier``: ein **Geschäftskunde** hatte
damit keinen Firmennamen, und ein Mitarbeiter, der privat eine Schraube kauft, sah die
Firmenfelder seines Arbeitgebers. Beides ist dieselbe Verwechslung.

So macht es jeder grosse Anbieter (Amazon Business, Stripe, Shopify): man wählt beim
Anlegen oder jederzeit später zwischen Privat- und Geschäftskonto, und **erst die Wahl
«Geschäft» blendet die Firmenfelder ein**.

►►► **``NULL`` heisst «noch nicht entschieden» – und dann IST der Firmenname die
Antwort.** ◄◄◄ Das ist der Grund, warum diese Runde **keinen Backfill** braucht: für
Altbestand wird abgeleitet, ab der ersten Wahl steht der Wert. Ein `UPDATE` mit
derselben Bedingung müsste bei jedem Start laufen (die dev-Datenbank fährt kein
``alembic upgrade head``) und flippte damit jeden zurück, der bewusst auf «Privat»
gestellt hat, ohne den Namen zu löschen – also genau gegen die Regel, dass vorhandene
Werte **bleiben**. Dieselbe Bauart wie ``Voucher.issuer_company_id = NULL`` («der
Betreiber»): tolerant lesen, streng schreiben.

**Kein Feld «ist das gesperrt?» daneben:** dass ein Lieferant immer eine Firma ist, sagt
``effective`` – und dieselbe Funktion liest die Oberfläche (über den *effektiven* Wert in
der Antwort) und der Dienst. Zwei Formen einer Regel sind in Ordnung; zwei Regeln nicht.
"""

from dataclasses import dataclass
from typing import Optional

#: Die zwei Kontotypen. Mehr wird es nicht: «Verein» und «Behörde» sind Rechtsformen
#: einer *Firma*, keine dritte Art, wirtschaftlich aufzutreten.
PRIVATE = "private"
BUSINESS = "business"


@dataclass(frozen=True)
class AccountType:
    """Ein Kontotyp: Schlüssel, Beschriftung, und was er bedeutet."""

    key: str
    label: str
    hint: str


#: Reihenfolge = die des Schalters in der Oberfläche.
CATALOG: tuple[AccountType, ...] = (
    AccountType(PRIVATE, "Privat",
                "Eine Privatperson – auf dem Beleg steht ihr Name."),
    AccountType(BUSINESS, "Geschäft",
                "Eine Firma – auf dem Beleg steht die Rechtsperson, "
                "die Person darunter als «z. H.»."),
)
KEYS: tuple[str, ...] = tuple(a.key for a in CATALOG)
LABEL: dict[str, str] = {a.key: a.label for a in CATALOG}

#: ►►► **Rollen, die eine Firma SIND.** ◄◄◄ Ein Lieferant ist immer eine – man bestellt
#: nicht bei einer Privatperson, und seine Rechnung trägt eine Rechtsperson. Darum
#: **erzwingt** die Rolle den Kontotyp, statt ihn nur vorzuschlagen: ein Vorschlag wäre
#: die Stelle, an der ein Lieferant ohne Firmennamen entsteht.
FORCED_BUSINESS: tuple[str, ...] = ("supplier",)

#: ►►► **Was ein Geschäftskonto braucht** – und was nicht. ◄◄◄ Firmenname und Rechtsform
#: sind die **Rechtsperson**; ohne sie ist ein Beleg keiner (MWSTG Art. 26, dieselbe
#: Angabe, die ``sites.legal_name`` an unserer eigenen Seite zusammensetzt).
#: Die **UID bleibt freiwillig**: nur MWST-pflichtige Firmen haben eine, und ein
#: Pflichtfeld, das die Hälfte der Firmen nicht ausfüllen kann, ist keines.
REQUIRED_FIELDS: tuple[tuple[str, str], ...] = (
    ("company_name", "Firmenname"),
    ("legal_form", "Rechtsform"),
)

#: Die Felder, die **nur** ein Geschäftskonto führt – «Privat» blendet sie aus, löscht
#: sie aber nicht. Eine Liste statt einer Bedingungskette, damit ein künftiges Firmenfeld
#: hier eine Zeile ist und nicht ein `if` an drei Stellen.
COMPANY_FIELDS: tuple[str, ...] = ("company_name", "legal_form", "uid_number",
                                   "vat_number", "trade_register_nr",
                                   "trade_register_canton", "company_website")


def effective(role: Optional[str], stored: Optional[str], *,
              company_name: Optional[str] = None) -> str:
    """**Der Kontotyp, der GILT** – die eine Auflösung.

    Drei Stufen, in dieser Reihenfolge: die **Rolle** erzwingt (ein Lieferant ist eine
    Firma) · der **gespeicherte** Wert gilt · sonst wird für Altbestand **abgeleitet**
    (steht ein Firmenname da, war es ein Geschäftskonto).

    Ein unbekannter gespeicherter Wert wird wie ``NULL`` behandelt: tolerant lesen – eine
    Ausnahme wäre eine Ansicht, die an einer alten Zeile abstürzt.
    """
    if role in FORCED_BUSINESS:
        return BUSINESS
    if stored in KEYS:
        return stored  # type: ignore[return-value]
    return BUSINESS if (company_name or "").strip() else PRIVATE


def is_forced(role: Optional[str]) -> bool:
    """Ist der Kontotyp durch die Rolle **festgelegt**? (Dann gibt es nichts zu wählen.)"""
    return role in FORCED_BUSINESS


def missing(values: dict[str, Optional[str]]) -> tuple[str, ...]:
    """Welche Pflichtangaben eines Geschäftskontos **fehlen** – als Beschriftungen.

    Rein rechnend: *welche* Werte gelten, entscheidet der Aufrufer (bei einer Änderung
    ist das der Stand **nach** ihr, nicht der davor).
    """
    return tuple(label for field, label in REQUIRED_FIELDS
                 if not (values.get(field) or "").strip())
