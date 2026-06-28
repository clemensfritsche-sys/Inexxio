"""Deklarativer Katalog der fachlichen Ereignis-/Schritttypen (REA-Kern).

**Eine** Quelle der Wahrheit für jeden Prozessschritt: sein Label, seine **Wirkung
auf den Bestand** (Polarität), seine **Subjekt-Rolle** (was der Auftrag damit tut)
und die **Fachtabelle**, aus der sein Ausführungsstand abgeleitet wird.

Warum das wichtig ist (Architektur-Review): Bislang wurde die Lager-Richtung eines
Prozesses aus der Kombination seiner Schritte *erraten* (``derive_source`` mit der
versteckten Priorität ``sale > purchase > sonst``). Das war „spukhafte Fernwirkung":
ein hinzugefügter Schritt konnte die Natur **jedes** Auftrags unsichtbar umkippen,
und ein Prozess mit Zu- *und* Abgang liess sich nicht ehrlich beschreiben.

Hier ist die Polarität eine **deklarierte Eigenschaft des Ereignistyps** – sichtbar,
testbar, und über die Schritte **aggregierbar**: ein Prozess mit erhöhenden UND
mindernden Schritten ist ``mixed`` statt fälschlich in einen Topf geworfen.

REA: Resources (Article/Instance) · Events (diese Typen) · Agents (UserProfile).
Jeder Eintrag ist im Grunde ein wirtschaftliches Ereignis mit deklarierter Wirkung
auf eine Ressource – genau das, was ein Event-Log zur ökonomischen Wahrheit macht.
"""

from dataclasses import dataclass

# ─── Bestands-Polarität (REA: Wirkung des Ereignisses auf die Ressource) ─────────
INCREASE = "increase"   # bringt Bestand herein / lässt neuen entstehen (Beschaffung, Produktion)
DECREASE = "decrease"   # mindert Bestand (Verkauf, Entnahme)
MOVE = "move"           # verschiebt nur den Standort (kein Mengeneffekt)
NEUTRAL = "neutral"     # keine Bestandswirkung (Datenerfassung)

# ─── Subjekt-Rolle: worauf der Auftrag wirkt (= bisherige ``source``-Werte) ───────
PRODUCE = "produce"     # erzeugt neue Instanzen
STOCK = "stock"         # greift FIFO auf vorhandenen Bestand zu
INSTANCE = "instance"   # bearbeitet eine konkrete, bestehende Instanz

# Vorrang bei der Ableitung der Auftrags-Subjektart aus mehreren Schritten –
# **deklariert** (statt als if-Kette versteckt): ein mindernder Bestandszugriff
# dominiert eine Produktion, diese eine reine Instanz-Bearbeitung.
SUBJECT_PRECEDENCE = (STOCK, PRODUCE, INSTANCE)

# Vorzeichen der Bestandswirkung – für die Anreicherung der Domain-Events (Ledger).
_DELTA_SIGN = {INCREASE: 1, DECREASE: -1, MOVE: 0, NEUTRAL: 0}


@dataclass(frozen=True)
class EventType:
    """Ein fachlicher Ereignis-/Schritttyp mit deklarierter Semantik."""

    key: str            # Schlüssel (== ``ArticleProcessStep.step_type``)
    label: str          # Anzeigename (DE)
    polarity: str       # Wirkung auf den Bestand: increase | decrease | move | neutral
    subject_role: str   # was der Auftrag mit seinem Subjekt tut: produce | stock | instance
    fact: str           # Name des Fachmodells (Status-/Routing-Ableitung)


# Reihenfolge = natürliche Lese-/Anzeigereihenfolge.
REGISTRY: dict[str, EventType] = {
    "purchase":   EventType("purchase",   "Beschaffung",    INCREASE, PRODUCE,  "PurchaseOrder"),
    "resource":   EventType("resource",   "Ressource",      INCREASE, PRODUCE,  "ResourceUsage"),
    "inspection": EventType("inspection", "Datenerfassung", NEUTRAL,  INSTANCE, "Inspection"),
    "movement":   EventType("movement",   "Bewegung",       MOVE,     INSTANCE, "Movement"),
    "sale":       EventType("sale",       "Verkauf",        DECREASE, STOCK,    "Sale"),
}

# Erlaubte Schritttypen (Schema-Whitelist) und die Ressourcen-Gruppe (Verbrauch +
# Betriebsmittel laufen über EINEN Typ ``resource``; der Modus lebt auf der Zeile).
STEP_TYPES: tuple[str, ...] = tuple(REGISTRY.keys())
RESOURCE_TYPES: tuple[str, ...] = ("resource",)

# ─── Kompatibilität: welche Schritte in welchem Prozess-Kontext zulässig sind ─────
# Damit Prozessschritte IMMER zueinander passen, wird je Kontext eine Whitelist
# erzwungen. So kann ein Prozess strukturell nicht „mischen" (Zu- UND Abgang) und
# die Subjektart bleibt kohärent:
#   • Artikel-Prozess = HERSTELLUNG (wie etwas entsteht): beschaffen, montieren
#     (Ressource), prüfen, bewegen. KEIN Verkauf (verkauft wird nicht beim Herstellen).
#   • Auftrags-Ablauf  = OPERATION AM BESTAND (vorhandene/FIFO-Instanzen): verkaufen,
#     bewegen, prüfen. KEINE Beschaffung/Ressource (das erzeugt Bestand = Herstellung).
ARTICLE_STEP_TYPES: tuple[str, ...] = ("purchase", "resource", "inspection", "movement")
ORDER_STEP_TYPES: tuple[str, ...] = ("sale", "movement", "inspection")


def allowed_step_types(owner_kind: str) -> tuple[str, ...]:
    """Zulässige Schritttypen je Träger: ``article`` (Herstellung) | ``order`` (Bestand)."""
    return ARTICLE_STEP_TYPES if owner_kind == "article" else ORDER_STEP_TYPES


# ─── Reine Helfer (kein DB-Zugriff – testbar) ────────────────────────────────────

def label(step_type: str) -> str:
    et = REGISTRY.get(step_type)
    return et.label if et else step_type


def polarity(step_type: str) -> str:
    et = REGISTRY.get(step_type)
    return et.polarity if et else NEUTRAL


def subject_role(step_type: str) -> str:
    et = REGISTRY.get(step_type)
    return et.subject_role if et else INSTANCE


def delta_sign(step_type: str) -> int:
    """+1 / −1 / 0 – Vorzeichen der Bestandswirkung (für Event-Payloads/Ledger)."""
    return _DELTA_SIGN.get(polarity(step_type), 0)


def derive_subject_mode(step_types: set[str]) -> str:
    """Subjektart eines Prozesses aus seinen Schritt-Typen – über die **deklarierte**
    Vorrangordnung (``SUBJECT_PRECEDENCE``), nicht über eine versteckte if-Kette.

    Ohne Schritte → ``instance`` (neutral, bearbeitet das bestehende Subjekt)."""
    roles = {subject_role(t) for t in step_types}
    for role in SUBJECT_PRECEDENCE:
        if role in roles:
            return role
    return INSTANCE


def aggregate_stock_effect(step_types: set[str]) -> str:
    """Bestands-Richtung eines Prozesses = **Aggregat der Schritt-Polaritäten**.

    Ehrlich statt vereinfachend: kommen erhöhende UND mindernde Schritte vor, ist das
    Ergebnis ``mixed`` (z. B. Beschaffung **und** Verkauf im selben Prozess). Reine
    Bewegung/Datenerfassung → ``neutral``."""
    pols = {polarity(t) for t in step_types}
    up = INCREASE in pols
    down = DECREASE in pols
    if up and down:
        return "mixed"
    if up:
        return INCREASE
    if down:
        return DECREASE
    return NEUTRAL
