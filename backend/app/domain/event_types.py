"""Deklarativer Katalog der fachlichen Ereignis-/Schritttypen (REA-Kern).

**Eine** Quelle der Wahrheit für jeden Prozessschritt: sein Label, seine **Wirkung
auf den Bestand** (Polarität), sein **Bereitstellungsort** und die **Fachtabelle**,
aus der sein Ausführungsstand abgeleitet wird.

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

# ─── Es gibt hier KEINE «Subjekt-Rolle» mehr (Testnotiz #622) ────────────────────
# Bis Juli 2026 deklarierte jeder Schritttyp zusätzlich, WORAUF der Auftrag wirkt
# (produce | stock | instance), und ``derive_subject_mode`` aggregierte das über eine
# Vorrangordnung zur Subjektart des Auftrags. Das war eine **zweite Aussage über dieselbe
# Sache** – und die unsichtbare gewann: ein order-eigener Beschaffungs-Schritt trug
# ``produce``, also erzeugte ein Auftrag mit «Beschaffen + Datenerfassung» neue Instanzen,
# obwohl der Mensch im Bedarf ausdrücklich «Ab Lager» gewählt hatte.
#
# Die Regel ist heute eine einzige Bedingung und steht dort, wo sie hingehört
# (``subject.subject_kind``): **Instanzen entstehen ausschliesslich aus dem Prozess des
# ARTIKELS** – ein Auftrag mit eigenem Ablauf greift zu, er erzeugt nie. Die Rolle wird
# darum nicht mehr deklariert; sie liesse sich sonst jederzeit wieder zu einer zweiten
# Ableitung zusammensetzen.

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
    # **Arbeitet dieser Schritt AN den Instanzen des Auftrags?** (Testnotiz #652)
    #
    # Nur dann hat er nichts mehr zu tun, wenn dem Auftrag nichts mehr bleibt – und dann
    # ist er **erledigt**: «nichts zu tun» ist nicht dasselbe wie «nicht getan». Ohne die
    # Unterscheidung wäre ein Modul nach dem Aussondern eine Sackgasse (aktiv, aber jede
    # Ausführung wirft «Keine Instanzen vorhanden» – der Auftrag könnte weder abschliessen
    # noch enden). Und ohne die Einschränkung wäre ein reiner Beschaffungsauftrag sofort
    # «fertig», denn er beginnt ja mit nichts: Schritte, die Material **hereinbringen**
    # (Beschaffung, Ressource) oder gar keins brauchen (Dokument), tragen es nicht.
    needs_material: bool = False
    # **Ein Beleg gilt für die Menge, für die er ausgestellt wurde** (Testnotizen #587/#588).
    # Ändert sie sich, fällt er auf seine **erste Stufe** zurück (``reset``); fällt sie auf
    # **null**, auf seine **letzte** (``voided`` – storniert). Das ist EINE Regel mit zwei
    # Enden, kein zweiter Mechanismus: «Menge reduzieren» und «alles entzogen» sind derselbe
    # Vorgang, nur die Stufe ist eine andere – und die steht hier, nicht als if/else im Code.
    #
    # ``reset_fields`` = die Zahlen, die die **Vereinbarung** ausdrücken. Sie gelten für die
    # alte Menge und werden beim Zurückfallen geleert; sonst stünde beim Lieferanten eine
    # Bestellsumme für 3 Stück neben einer Menge von 2.
    #
    # Ein Typ, der nichts davon deklariert, ist **nicht** ausgenommen – er hat schlicht keine
    # Stufen: Bewegung, Ressource und Aussondern schreiben ihre Zeile erst, wenn die Handlung
    # geschehen ist. Sie ist damit Vergangenheit, und die wird nicht umgeschrieben.
    reset: object = None
    reset_fields: tuple = ()
    voided: object = None
    # **Bis zur Zusage entscheidet das System, ab der Zusage entscheidet der Mensch.**
    #
    # ``binding`` nennt die Stufen, ab denen eine **zweite Partei** gebunden ist. Bis dahin
    # ist der Beleg nur unsere Absicht, und das System zieht ihn selbst nach. Ab dort ist er
    # eine Zusage: die Ware ist unterwegs, und man kann sie nicht einseitig zurücknehmen –
    # so wenig, wie man eine Internet-Bestellung eine Sekunde später widerruft.
    #
    # Das System fasst einen solchen Beleg darum NICHT an. Es meldet die Abweichung
    # («bestellt 3 · gebraucht 2») und wartet auf den Menschen, der beim Lieferanten
    # anruft – genau die Ausnahme, die es in der Realität gibt. Erst seine Bestätigung
    # löst dieselbe Änderung aus (``rebase.apply_clarified``): EIN Vorgang, zwei Auslöser.
    #
    # Beim **Verkauf** braucht es die Schwelle nicht: dort ist «bezahlt» ohnehin ``done``,
    # und eine bezahlte Position wird über die Gutschrift korrigiert, nicht über eine
    # Kürzung (``recovery._assert_not_paid``).
    binding: tuple = ()
    # **Kein Flag dafür, wen eine Fehlmenge aufhält.** Hier stand kurzzeitig ``hands_over``
    # («gibt dieser Schritt die Menge weiter?»), damit nur Verkauf und Ressource blockieren.
    # Das ist zurückgenommen: eine Fehlmenge gehört dem **Auftrag**, nicht einem Schritt –
    # fehlt sein Subjekt, ruht er als Ganzes (``process.is_paused``). Ein Schritt hat nur
    # noch seinen **eigenen** Material-Bedarf (Ressource), und den kennt er aus seinen
    # Zeilen. Damit braucht es hier weder ein Flag noch eine Typ-Liste.


# Reihenfolge = natürliche Lese-/Anzeigereihenfolge.
REGISTRY: dict[str, EventType] = {
    # **«Storniert» ist ein bestehendes Wort im Haus** (Verkauf, Sendung, Warenkorb tragen es
    # längst) – die Beschaffung bekommt es dazu, statt ein neues zu erfinden. Es ist NICHT
    # dasselbe wie «Abgelehnt»: abgelehnt heisst, der Besteller sagt zu einer Offerte nein
    # (eine Entscheidung); storniert heisst, der Vorgang hat seinen Gegenstand verloren.
    "purchase":   EventType("purchase",   "Beschaffen",     INCREASE, "PurchaseOrder", PROV_RECEIVING,
                            status_field="status", done=("received",),
                            failed=("rejected", "cancelled"),
                            reset="requested", voided="cancelled",
                            reset_fields=("order_total", "lead_time_days", "payment_terms_days",
                                          "landed_unit_cost"),
                            # Ab «Bestellt» ist der Lieferant gebunden und die Ware in aller
                            # Regel unterwegs. «Offeriert» ist noch keine Zusage von UNS –
                            # dort greift die Automatik weiter.
                            binding=("ordered",)),
    "resource":   EventType("resource",   "Ressource",      INCREASE, "ResourceUsage", PROV_PRODUCT),
    "inspection": EventType("inspection", "Datenerfassung", NEUTRAL,  "Inspection",    PROV_NONE,
                            status_field="result", done=("passed",), failed=("failed",),
                            needs_material=True),
    "movement":   EventType("movement",   "Bewegung",       MOVE,     "Movement",      PROV_NONE,
                            needs_material=True),
    "scrap":      EventType("scrap",      "Aussondern",     DECREASE, "Disposal",      PROV_NOWHERE,
                            needs_material=True),
    # **Sperren** ist das reversible Gegenstück zum Verschrotten: die Instanz bleibt
    # physisch da (Standort unverändert), darf aber vorübergehend nicht verwendet werden –
    # z. B. eine defekte Maschine, die auf Wartung wartet. Umgesetzt auf der **Qualitäts-
    # Achse** (``quality='blocked'``), nicht auf der Verbleibs-Achse: «wo ist es» ändert
    # sich nicht, «darf man es verwenden» schon. Darum NEUTRAL wie die Datenerfassung, die
    # eine Instanz ebenfalls über ``quality`` aus dem Bestand nehmen kann – es wird nichts
    # verbraucht oder vernichtet, nur die Verwendbarkeit ausgesetzt.
    "block":      EventType("block",      "Aussondern",     NEUTRAL,  "Disposal",      PROV_NONE,
                            needs_material=True),
    # **Verkauf UND Gutschrift** laufen über EINEN Schritttyp `sale` (Fachtabelle `Sale`): ein
    # normaler Auftrag verkauft (kind='sale', Bestands-Abgang), eine Retoure (Subjekt = verkaufte
    # Instanzen, `reason='return'`) schreibt gut (kind='credit', Stripe-Refund) – der Modus wird
    # aus dem Subjekt ABGELEITET, kein eigener Schritttyp. Der physische Rückfluss läuft über die
    # **Bewegung** (verkauft ↔ am Lager, je nach Ziel), die Geld-Seite über diesen Schritt.
    "sale":       EventType("sale",       "Verkauf",        DECREASE, "Sale",          PROV_CUSTOMER,
                            status_field="status", done=("paid",), failed=("cancelled",),
                            reset="requested", voided="cancelled",
                            reset_fields=("order_total",), needs_material=True),
    # **Dokument**: der Auftrag erzeugt – wie jeder Erzeugungsauftrag – eine Instanz; das
    # Dokument (Fachtabelle ``Document``) hängt daran (Nummer = Instanz-Objektnummer, Datum =
    # Instanz-Freigabe). Keine Bestandswirkung (NEUTRAL); Subjekt-Rolle PRODUCE → der Auftrag
    # wird als „produce" abgeleitet und greift NIE FIFO auf Lager zu. Der Inhalt wird während
    # der Ausführung verfasst und mit «Ausstellen» festgeschrieben.
    "document":   EventType("document",   "Dokument",       NEUTRAL,  "Document",
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


def needs_material(step_type: str) -> bool:
    """Arbeitet dieser Schritt AN den Instanzen des Auftrags? (Testnotiz #652)"""
    et = REGISTRY.get(step_type)
    return bool(et and et.needs_material)


def provisioning(step_type: str) -> str:
    """Deklarierter Bereitstellungsort eines Schritttyps (wohin sein Subjekt physisch muss)."""
    et = REGISTRY.get(step_type)
    return et.provisioning if et else PROV_NONE


def delta_sign(step_type: str) -> int:
    """+1 / −1 / 0 – Vorzeichen der Bestandswirkung (für Event-Payloads/Ledger)."""
    return _DELTA_SIGN.get(polarity(step_type), 0)


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
