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

# ─── Bereitstellungsort: wohin die Inputs/das Subjekt eines Schritts physisch müssen ──
# «Bewegung wird ABGELEITET, nicht orchestriert»: jeder Schritttyp DEKLARIERT hier seinen
# Bereitstellungsort. Ein einziger Reconciler (``services/provisioning.py``) vergleicht
# Ist-Standort ↔ Soll und erzeugt die minimal nötige Bewegung – **no-op, wenn schon da**.
# Heute laufen Wareneingang/Versand/Kunde über die gesperrten Pflicht-Bewegungen
# (``services/process_steps.py``) und Verbrauch/Betriebsmittel über den Ressourcen-Schritt
# (``services/resource.py``, Komponente → Produkt-Instanz / Werkzeug → Arbeitsplatz).
# **Verschrotten** hat KEINEN Bereitstellungsort: ein verschrottetes Teil verlässt den
# Bestand endgültig – ein Standort ist immer ein realer Halter (Person/Instanz/Unternehmen),
# und einen solchen hat Ausschuss nicht mehr. Der Endzustand ``disposition='scrapped'`` IST
# die «Wo»-Aussage; die Instanz wird beim Verschrotten **standortlos** (siehe services/scrap.py).
PROV_NONE = "none"            # kein fester Ort (frei / self): Datenerfassung, Bewegung, Dokument
PROV_RECEIVING = "receiving"  # Wareneingang            (Beschaffung → danach)
PROV_CUSTOMER = "customer"    # Kunde                   (Verkauf → danach)
PROV_PRODUCT = "product"      # Produkt-Instanz/Montageort (Ressource: Verbrauch; Werkzeug = Arbeitsplatz)
PROV_NOWHERE = "nowhere"      # kein Halter mehr → standortlos (Verschrotten: raus aus dem Bestand)

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
    provisioning: str = PROV_NONE  # Bereitstellungsort: wohin das Subjekt/die Inputs physisch müssen
    # **Woran man dem Fachdatensatz ansieht, dass der Schritt durch ist.** Auch das ist
    # per-Typ-Wissen und gehört damit hierher: ``status_field`` = das Feld auf der Fachzeile
    # (``None`` = die blosse EXISTENZ der Zeile ist die Erledigung, z. B. Bewegung), ``done``/
    # ``failed`` = die Werte, die «erledigt» bzw. «fehlgeschlagen» bedeuten.
    # Vorher stand dieselbe Aussage als if/elif-Kette in ``process._fact_status`` – ein neuer
    # Schritttyp musste an ZWEI Stellen gepflegt werden, und die Kette konnte still von der
    # Registry abweichen.
    status_field: str | None = None
    done: tuple = ()
    failed: tuple = ()
    # **Gibt dieser Schritt die Menge WEITER?** – aus dem Auftrag hinaus (Verkauf → Kunde)
    # oder in das Produkt hinein (Ressource → verbraucht). Nur solche Schritte hält eine
    # Fehlmenge auf: man kann nicht verkaufen oder verbauen, was man nicht hat.
    #
    # Alle anderen arbeiten an dem, was **da ist** – erfassen, aussondern, bewegen. Sie
    # dürfen bei einer Fehlmenge NIE blockieren; gerade dann braucht man sie. Vorher stand
    # hier eine Liste ``SUBJECT_STEP_TYPES`` mit fünf Typen, die alle blockierten: eine
    # Abweichung an EINEM von fünf Teilen legte damit auch die Prüfung der anderen vier
    # still – genau die Pause, die abgeschafft werden sollte, nur unter anderem Namen.
    hands_over: bool = False


# Reihenfolge = natürliche Lese-/Anzeigereihenfolge.
REGISTRY: dict[str, EventType] = {
    "purchase":   EventType("purchase",   "Beschaffen",     INCREASE, PRODUCE,  "PurchaseOrder", PROV_RECEIVING,
                            status_field="status", done=("received",), failed=("rejected",)),
    "resource":   EventType("resource",   "Ressource",      INCREASE, PRODUCE,  "ResourceUsage", PROV_PRODUCT,
                            hands_over=True),
    "inspection": EventType("inspection", "Datenerfassung", NEUTRAL,  INSTANCE, "Inspection",    PROV_NONE,
                            status_field="result", done=("passed",), failed=("failed",)),
    "movement":   EventType("movement",   "Bewegung",       MOVE,     INSTANCE, "Movement",      PROV_NONE),
    "scrap":      EventType("scrap",      "Aussondern",     DECREASE, INSTANCE, "Disposal",      PROV_NOWHERE),
    # **Sperren** ist das reversible Gegenstück zum Verschrotten: die Instanz bleibt
    # physisch da (Standort unverändert), darf aber vorübergehend nicht verwendet werden –
    # z. B. eine defekte Maschine, die auf Wartung wartet. Umgesetzt auf der **Qualitäts-
    # Achse** (``quality='blocked'``), nicht auf der Verbleibs-Achse: «wo ist es» ändert
    # sich nicht, «darf man es verwenden» schon. Darum NEUTRAL wie die Datenerfassung, die
    # eine Instanz ebenfalls über ``quality`` aus dem Bestand nehmen kann – es wird nichts
    # verbraucht oder vernichtet, nur die Verwendbarkeit ausgesetzt.
    "block":      EventType("block",      "Aussondern",     NEUTRAL,  INSTANCE, "Disposal",      PROV_NONE),
    # **Verkauf UND Gutschrift** laufen über EINEN Schritttyp `sale` (Fachtabelle `Sale`): ein
    # normaler Auftrag verkauft (kind='sale', Bestands-Abgang), eine Retoure (Subjekt = verkaufte
    # Instanzen, `reason='return'`) schreibt gut (kind='credit', Stripe-Refund) – der Modus wird
    # aus dem Subjekt ABGELEITET, kein eigener Schritttyp. Der physische Rückfluss läuft über die
    # **Bewegung** (verkauft ↔ am Lager, je nach Ziel), die Geld-Seite über diesen Schritt.
    "sale":       EventType("sale",       "Verkauf",        DECREASE, STOCK,    "Sale",          PROV_CUSTOMER,
                            status_field="status", done=("paid",), failed=("cancelled",),
                            hands_over=True),
    # **Dokument**: der Auftrag erzeugt – wie jeder Erzeugungsauftrag – eine Instanz; das
    # Dokument (Fachtabelle ``Document``) hängt daran (Nummer = Instanz-Objektnummer, Datum =
    # Instanz-Freigabe). Keine Bestandswirkung (NEUTRAL); Subjekt-Rolle PRODUCE → der Auftrag
    # wird als „produce" abgeleitet und greift NIE FIFO auf Lager zu. Der Inhalt wird während
    # der Ausführung verfasst und mit «Ausstellen» festgeschrieben.
    "document":   EventType("document",   "Dokument",       NEUTRAL,  PRODUCE,  "Document",
                            status_field="done", done=(True,)),
}

# Erlaubte Schritttypen (Schema-Whitelist) und die Ressourcen-Gruppe (Verbrauch +
# Betriebsmittel laufen über EINEN Typ ``resource``; der Modus lebt auf der Zeile).
STEP_TYPES: tuple[str, ...] = tuple(REGISTRY.keys())
RESOURCE_TYPES: tuple[str, ...] = ("resource",)

# ─── Kompatibilität: welche Schritte in welchem Prozess-Kontext zulässig sind ─────
# Alles ist instanzbasiert: ein Auftrag wirkt auf Instanzen eines Artikels (neu erzeugt
# bei „Herstellung", vorhandene/FIFO bei einer „Bestands-Operation"). Daher sind im
# **Auftrags-Ablauf alle Schritttypen** sinnvoll und zulässig – z. B. Wartung mit
# Verbrauchsmaterial/Betriebsmitteln (resource) oder auswärtiger Vergabe (purchase).
#
# **Jedes Prozessschrittmodul ist universell einsetzbar** – am Artikel wie am Auftrag
# (Testnotiz #246). Früher waren Verkauf/Verschrotten/Sperren im Artikel-Prozess gesperrt,
# weil sie „auf vorhandenen Bestand wirken". Das stimmt, ist aber kein Grund für ein Verbot:
# ein Artikel-Prozess läuft immer IN einem Auftrag, und dessen Instanzen existieren, sobald
# der Schritt an der Reihe ist. Eine Sperre, die nur selten sinnvolle Kombinationen
# verhindert, kostet mehr (der Nutzer stösst an eine Wand) als sie nützt – wer einen
# unsinnigen Ablauf modelliert, sieht das am Ergebnis.
STEP_TYPES_BY_OWNER: tuple[str, ...] = (
    "purchase", "resource", "inspection", "movement", "scrap", "block", "sale", "document",
)
ARTICLE_STEP_TYPES = STEP_TYPES_BY_OWNER
ORDER_STEP_TYPES = STEP_TYPES_BY_OWNER


def allowed_step_types(owner_kind: str) -> tuple[str, ...]:  # noqa: ARG001 - Signatur bleibt
    """Zulässige Schritttypen je Träger – **dieselben für Artikel und Auftrag**."""
    return STEP_TYPES_BY_OWNER


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


def provisioning(step_type: str) -> str:
    """Deklarierter Bereitstellungsort eines Schritttyps (wohin sein Subjekt physisch muss)."""
    et = REGISTRY.get(step_type)
    return et.provisioning if et else PROV_NONE


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
