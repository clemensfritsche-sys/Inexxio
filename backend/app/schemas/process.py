"""Prozessschrittmodule – die API-Form, **einmal** für Artikel und Auftrag.

Es ist derselbe Prozess, nur an zwei Orten (PROCESS_CORE.md §8): am Artikel als Vorlage,
im Auftrag als das, was läuft. Zwei Schemas dafür wären zwei Wahrheiten, die genau so
lange gleich bleiben, bis jemand eines von beiden erweitert.

**Der Übergang steht nicht drin.** Er gehört zum Modultyp (``domain/modules``) und wird
beim Anlegen von dort genommen. Ein Feld dafür wäre eine Eingabe, deren einzige richtige
Antwort schon feststeht – und deren falsche einen Prozess ergäbe, der nicht läuft.
"""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, computed_field

from ..domain import modules


class ModuleFacts(BaseModel):
    """**Was ein gespeicherter Schritt aus der Registry mitbringt** – für beide Orte.

    Beschriftung, Farbfamilie und «ist das ein Ausgang?» hängen ausschliesslich am
    Modultyp (``domain/modules``). Sie stehen darum hier und werden **abgeleitet**, nie
    gespeichert: eine Spalte daneben wäre eine zweite Aussage darüber, was dieses Modul
    ist, und die erste falsche Eingabe liesse beide auseinanderlaufen.

    **Die Farbe reist mit dem Schritt.** Vorher tat sie das nicht: die Oberfläche holte
    sie aus dem Modul-Katalog, und den lädt nur der Editor. Im **freigegebenen** Auftrag
    stand darum keine Farbe zur Verfügung, und ein stiller Rückfall machte jedes Modul zu
    dem Ton, der zufällig der erste in der Liste war – die Aussonderung sah nach dem
    Freigeben aus wie eine Datenerfassung. Als Feld der Antwort kann sie nicht mehr
    fehlen; ein Aufrufer, der sie vergisst, ist nicht mehr möglich.
    """

    model_config = ConfigDict(from_attributes=True)

    module_type: str

    @computed_field  # type: ignore[prop-decorator]
    @property
    def label(self) -> str:
        """Wie das Modul heisst – aus der Registry, nicht aus einer Spalte."""
        return modules.label(self.module_type)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def tone(self) -> str:
        """Die Farbfamilie des Modultyps. Ein Wort; die Werte kennt die Oberfläche."""
        return modules.get(self.module_type).tone

    @computed_field  # type: ignore[prop-decorator]
    @property
    def terminal(self) -> bool:
        """Ist dies ein **Ausgang**? Dann steht dahinter nichts mehr – und kein Ende."""
        return modules.get(self.module_type).terminal

    @computed_field  # type: ignore[prop-decorator]
    @property
    def moves(self) -> bool:
        """**Bringt dieses Modul die Stücke woandershin?** Daraus folgt der Ziel-Scan.

        Vorher beantwortete das eine Liste von Transportarten, indem sie bei jedem
        anderen Modultyp leer war – eine Liste als Bit. Seit «selbst oder eingekauft»
        aus dem Beleg folgt (``buys``), gibt es die Liste nicht mehr, und die Frage steht
        als das da, was sie ist. Sie reist **mit dem Schritt**: den Modul-Katalog lädt
        nur der Editor.
        """
        return modules.get(self.module_type).moves

    @computed_field  # type: ignore[prop-decorator]
    @property
    def buys(self) -> Optional[str]:
        """**Trägt dieses Modul einen Einkaufs-Beleg – und wann?** ``None`` = nie.

        ``if_chosen`` heisst: die Arbeit kann auch selbst erledigt werden, und genau
        darum darf die Oberfläche hier die Wahl anbieten. Sie fragt damit nach der
        Eigenschaft und nie nach dem Modultyp.
        """
        return modules.get(self.module_type).buys


class ModuleInput(BaseModel):
    """Ein Prozessschrittmodul, wie es der Entwurf schickt.

    **Keinen Namen.** Wie ein Modul heisst, sagt sein Typ (``domain/modules``) – ein
    Eingabefeld daneben hätte genau eine richtige Antwort und war trotzdem Pflicht
    (Testnotiz #682). Es war zugleich die Quelle der Meldung «String should have at
    least 1 character»: ein leer gelassenes Feld, das der Anwender gar nicht sehen
    wollte (#686).

    Die **Identität** eines Moduls ist seine ``id``, vergeben beim Anlegen (#687) – sie
    steht hier nicht, weil der Entwurf noch keine hat.

    **Die Konfiguration ist bewusst ein freier Satz Werte.** Was darin stehen darf,
    entscheidet der Modultyp (``domain/modules.Module.clean_config``) – und *nur* er.
    Eine Feldliste hier wäre eine zweite Aussage darüber, und sie war es auch: sie kannte
    ``points`` und sonst nichts, also verwarf Pydantic beim Eintreffen stillschweigend
    ``mode`` (Verschrotten ↔ Sperren) und ``sample`` (die Stichprobe). Beide Angaben
    kamen nie an, beide Vorgaben galten immer – ohne eine einzige Fehlermeldung.
    Geprüft wird jetzt dort, wo die Regel steht, mit einem Satz statt einem Feldpfad.
    """

    module_type: str
    config: Optional[dict[str, Any]] = None


class ModuleTypeInfo(BaseModel):
    """Ein wählbarer Modultyp – für die Oberfläche, damit sie die Liste nicht nachbaut.

    ``tone`` ist die **Farbfamilie** des Modultyps (``domain/modules``). Sie kommt mit,
    weil sie zum Modul gehört: ein neuer Typ soll ein Eintrag in der Registry sein und
    kein Eingriff in die Oberfläche.

    ``terminal`` sagt, dass hinter diesem Modul nichts mehr stehen kann – es ist ein
    **Ausgang**, kein Durchgang. Es ist dieselbe Eigenschaft, aus der die Freigabe ihren
    Fehler zieht (``domain/chain``) und das Prozessbild sein Ende; die Oberfläche bietet
    daraufhin gar nicht erst an, etwas dahinter zu setzen. Eine Regel, drei Wirkungen –
    ein neuer Modultyp erbt alle drei, ohne eine Zeile dafür.
    """

    key: str
    label: str
    tone: str
    terminal: bool = False
    status_before: str
    status_after: str
    #: **Trägt dieser Typ einen Einkaufs-Beleg – und wann?** ``None`` = nie.
    #:
    #: Daraus folgt im Editor der Beleg-Block (zugelassene Lieferanten + Auftrag an den
    #: Lieferanten): er hängt an *dieser* Eigenschaft und nicht an einer Liste von
    #: Modultypen in der Oberfläche. Ein neuer einkaufender Modultyp bekommt ihn damit,
    #: ohne dass jemand das Frontend anfasst (Testnotiz #777).
    buys: Optional[str] = None
    #: ►► **Was der Beleg beim Definieren braucht — je Feld EIN Wert, DREI Stufen.** ◄◄
    #:
    #: ``off`` · ``optional`` · ``required`` (``domain/modules.Module``). Vorher waren es
    #: zwei Booleans, und der Zustand «gibt es hier gar nicht» fehlte darin – daraus wurde
    #: ein Feld, das freiwillig dastand, weil man es *vielleicht* braucht (Testnotizen
    #: #780/#781). Der Editor rendert ein Feld genau dann, wenn es hier nicht ``off`` ist.
    parties: str = "optional"
    instruction: str = "optional"
    #: **Welche Rollen kommen als Gegenpartei in Frage? Leer heisst FREI.** Beim Verkauf
    #: ist sie leer: jeder darf bei uns kaufen, auch ein Mitarbeiter (Testnotiz #779).
    #: Die Auswahlliste (``/orders/party-options``) liest dieselbe Angabe.
    party_roles: list[str] = Field(default_factory=list)
    #: **Mit wem handelt dieser Typ?** ``supplier`` · ``customer``
    #: (``domain/procurement.Flow``). Der Editor braucht sie, um die Auswahlliste zu
    #: füllen – dort gibt es noch keinen Beleg, der sie mitbringen könnte, und ein
    #: ``if module_type`` in der Oberfläche wäre die zweite Stelle für dieselbe Regel.
    party_role: str = "supplier"
    #: Wie sie im Feld heisst («Lieferant» ↔ «Kunde») – und im **Plural**. Der wurde
    #: einmal durch Anhängen von «en» gebaut; beim Verkauf kam «Kundeen» heraus
    #: (Testnotiz #787). Deutsche Plurale sind nicht ableitbar.
    party_word: str = "Lieferant"
    party_plural: str = "Lieferanten"
    #: **Gibt es eine Bestellangabe je Gegenpartei?** Nur wo wir bestellen – beim Verkauf
    #: liefern wir, da ist nichts nachzuschlagen.
    party_ref: bool = True
    #: **Steht daneben ein abgeleiteter Satz?** Dann ist die Eingabe eine *Ergänzung*,
    #: und das Feld sagt das auch. Ein Beispiel statt eines Ja/Nein: die Oberfläche zeigt
    #: es als Platzhalter, damit sichtbar ist, was ohnehin schon dasteht.
    derived_instruction: str = ""


class CaptureTypeInfo(BaseModel):
    """Ein wählbarer Erfassungspunkt-Typ."""

    key: str
    label: str


class ModuleCatalog(BaseModel):
    """Was sich modellieren lässt. **Eine** Antwort für beide Definitionsorte."""

    modules: list[ModuleTypeInfo] = Field(default_factory=list)
    capture_types: list[CaptureTypeInfo] = Field(default_factory=list)


class CapturePoint(BaseModel):
    """Ein gespeicherter Erfassungspunkt, so wie ihn die Laufzeit ausfüllt.

    **Alle sind Pflicht** – bestätigt wird erst, wenn jeder ausgefüllt ist.
    """

    key: str
    label: str
    type: str
    target: Optional[float] = None
    tolerance: Optional[float] = None
    #: **Worin wird gemessen?** (mm · kg · °C …) Ein freies, kurzes Wort – bewusst keine
    #: Liste: die Mengeneinheiten des Artikels beantworten eine andere Frage (siehe
    #: ``domain/capture_types/measure``), und eine zweite Liste wäre endlos.
    unit: Optional[str] = None


class PurchaseQuote(BaseModel):
    """Eine Zeile der Anfrage: **eine Gegenpartei, ein Preis**.

    Der Angebotsspiegel des Einkaufs – zugleich der Tarifvergleich, wenn das Modul einen
    Transport einkauft, und das Angebot an den Kunden, wenn es verkauft. Es ist derselbe
    Vorgang, also dieselbe Zeile.
    """

    supplier_object_id: int
    supplier_name: str = ""
    #: **Wie man bei ihm bestellt** – seine Artikelnummer oder der Shop-Link, aus der
    #: Definition (``Module.parties_of`` → ``ref``). Sie gehört der Paarung
    #: Modul × Gegenpartei, nicht dem einzelnen Beleg.
    ref: str = ""
    #: Netto, für die ganze Menge. ``None``, solange nichts offeriert ist.
    amount: Optional[float] = None
    lead_days: Optional[int] = None
    #: **Die Zahlungsfrist in Tagen** – dieselbe Art Angabe wie die Lieferfrist, nur für
    #: das Geld: aus ihr folgt die Fälligkeit (``payments.due_on``). Freiwillig; ohne sie
    #: gibt es kein Fälligkeitsdatum und damit kein «überfällig», und das ist ehrlicher
    #: als ein geratenes Datum, aus dem gemahnt würde.
    payment_days: Optional[int] = None
    #: ``angefragt`` · ``offeriert`` · ``abgelehnt`` · ``gewaehlt``
    state: str


class PaymentLink(BaseModel):
    """**Die Adresse einer Zahlungsaufforderung** – und sonst nichts.

    Kein Beleg-Zustand: der Link ändert am Beleg nichts. Gebucht wird erst, wenn das Geld
    wirklich da ist, und das meldet der Webhook – nicht der Browser des Kunden.
    """

    url: str


class InvoiceEntry(BaseModel):
    """**Eine Forderung** an einem Beleg – die dritte Achse neben Ware und Geld.

    Ein **negativer** Betrag ist eine Gutschrift. Eine eigene Art dafür gibt es nicht:
    dieselbe Zeile, dasselbe Feld, ein anderes Vorzeichen (PROCESS_CORE §9.11).
    """

    id: int
    #: Wie sie gespeichert ist – ``<Auftragsnummer>-<laufend>`` bzw. die der Gegenpartei.
    number: Optional[str] = None
    #: Wie sie **angezeigt** wird: das ``-1`` der ersten fällt weg (``invoices.display``).
    #: Zwei Felder, damit niemand die Nummer im Browser zurechtschneidet.
    number_label: str = ""
    #: **Darf negativ sein** – das ist die Gutschrift.
    amount: float
    issued_on: Optional[str] = None
    #: **Ihre eigene** Fälligkeit. Zwei Rechnungen haben zwei.
    due_on: Optional[str] = None
    note: Optional[str] = None


class PaymentEntry(BaseModel):
    """**Eine Zeile Geld** an einem Beleg.

    Überweisung und Karte sind derselbe Datensatz; wer ihn geschrieben hat (ein Mensch
    oder der Webhook), ändert nichts an dem, was er ist. Eine **Gutschrift** steht hier
    nicht mehr – sie ist eine negative **Rechnung**, denn dabei fliesst kein Geld.
    """

    id: int
    #: **Darf negativ sein** – eine Erstattung ist eine Zahlung rückwärts.
    amount: float
    method: Optional[str] = None
    method_label: str = ""
    reference: Optional[str] = None
    paid_at: Optional[str] = None
    note: Optional[str] = None


class SpecEntry(BaseModel):
    """Eine Zeile der Artikel-Spezifikation – Beschriftung und Wert, sonst nichts.

    Sie **reist mit dem Beleg** (``services/article_fields``) und wird nicht ausgewählt:
    eine Spezifikation, die je nach Empfänger anders lautet, ist keine.
    """

    label: str
    value: str


class PurchaseLine(BaseModel):
    """Eine Position des Belegs: **welcher Artikel, wie viele Stücke, und was er ist.**

    Artikel und Menge sind **abgeleitet** – die Einzelinstanzen vor dem Modul tragen
    ihren Artikel, und ihre Zahl ist die Menge (``purchase.process_lines``). Mit der
    Bestellung frieren sie ein.
    """

    article_object_id: int
    article_name: str = ""
    unit: str = ""
    quantity: float = 0
    #: Die Spezifikation des Artikels – die eine Auskunft, die der Lieferant über die
    #: Sache bekommt.
    spec: list[SpecEntry] = Field(default_factory=list)


class PurchaseStage(BaseModel):
    """Eine Stufe des Belegs – Schlüssel, Beschriftung und das Verb, wenn sie dran ist."""

    key: str
    label: str
    #: Was man **tut**, wenn diese Stufe aktiv ist. Leer bei den übrigen: der Zustand
    #: steht bereits als Beschriftung da (Testnotizen #271/#275).
    verb: str = ""
    done: bool = False
    active: bool = False


class PurchaseEmbed(BaseModel):
    """**Der Beschaffungs-Beleg**, wie ihn die Ausführungsstelle braucht.

    **Der Beleg gehört keinem Modul** (``domain/procurement``): er hängt am Schritt, und
    welches Modul einen bekommt, sagt dessen ``buys``. Ein **Bewegen**-Modul, bei dem
    jemand «eingekauft» gewählt hat, trägt darum buchstäblich denselben – dieselben
    Stufen, dieselben Verben, dieselbe Komponente. Leer, wo keiner existiert; die
    Oberfläche braucht damit keine Fallunterscheidung nach dem Modul (wie ``needs``).

    **Ein Lieferant sieht nur seine eigene Zeile.** Fremde Preise sind kein Nebeneffekt
    einer Ansicht; gefiltert wird beim Aufbau der Antwort, nicht in der Oberfläche.
    """

    #: ``anfrage`` · ``bestellung`` · ``wareneingang`` · ``storniert``
    stage: str
    #: ►►► **Wie der Vorgang heisst und wie er aussieht** (``domain/procurement``). ◄◄◄
    #:
    #: Ein Einkauf sieht überall gleich aus – auch dort, wo ihn ein **Bewegen**-Modul
    #: auslöst. Er trägt darum seine Identität mit sich, wie ein Modul seine Farbe
    #: (``ModuleFacts.tone``): die Ausführungsstelle schlägt sie nicht in einem Katalog
    #: nach, den nur der Editor lädt, und sie borgt sie sich auch nicht bei einem
    #: Modultyp, der hier gar nicht steht.
    label: str = ""
    tone: str = ""
    #: **Das Wort für die eine Gegenhandlung** (``revoke``) – oder ``None``, wenn sie an
    #: dieser Stufe nicht geht. «Doch selbst erledigen» · «Anfrage zurückziehen» ·
    #: «Bestellung stornieren»: dieselbe Handlung, und was sie bewirkt, sagt die Stufe.
    #: Es steht neben der Wirkung und nicht in der Oberfläche – sonst stünde beim nächsten
    #: Fall ein Satz da, den keine Regel deckt.
    undo: Optional[str] = None
    #: Die drei Stufen in ihrer Reihenfolge, mit Beschriftung – die Oberfläche zeichnet
    #: sie, sie erfindet sie nicht (``Beschaffen.STAGES``).
    stages: list["PurchaseStage"] = Field(default_factory=list)
    #: ►►► **Was DIESER Betrachter hier tun darf** (``purchase._can``). ◄◄◄
    #:
    #: Die Oberfläche rendert eine Aktion genau dann, wenn ihr Verb hier steht – sie
    #: fragt nicht nach der Rolle. Eine Rollenabfrage dort wäre die zweite Stelle, an der
    #: dieselbe Regel steht, und ein Knopf, der nie etwas tun kann, ist kein Angebot.
    can: list[str] = Field(default_factory=list)
    #: **Was beschafft wird – abgeleitet, nicht getippt.** Je Artikel, dessen
    #: Einzelinstanzen vor dem Modul stehen, eine Zeile. Mehrere sind der Normalfall:
    #: EINE Bestellung mit zwei Positionen, wie im echten Leben.
    lines: list["PurchaseLine"] = Field(default_factory=list)
    #: **Was zu tun ist** – der Satz aus der Definition. Die Spezifikation beschreibt die
    #: Sache, dieser Satz den Auftrag («Härten auf 58 HRC»).
    instruction: str = ""
    #: Die **zugelassenen** Lieferanten dieses Moduls (aus der Definition).
    allowed: list["PurchaseQuote"] = Field(default_factory=list)
    quotes: list[PurchaseQuote] = Field(default_factory=list)
    supplier_object_id: Optional[int] = None
    supplier_name: Optional[str] = None
    amount: Optional[float] = None
    currency: str = "CHF"
    #: Die **Sendungsnummer** – sie entsteht erst nach der Bestellung. Wo man bei einem
    #: Lieferanten bestellt, steht dagegen an seiner Zeile (``PurchaseQuote.ref``).
    tracking: Optional[str] = None
    #: **Womit gerechnet wurde ↔ was heute gilt.** Gesetzt, wenn der Beleg seine Grundlage
    #: verloren hat und eine zweite Partei bereits gebunden ist: dann ändert das System
    #: nichts, sondern wartet auf die Bestätigung des Menschen.
    clarify_quantity: Optional[float] = None

    # ─── Die Richtung, und was aus ihr folgt ─────────────────────────────────────
    #: ``buy`` · ``sell`` (``domain/procurement``). Die Oberfläche braucht sie für kein
    #: einziges ``if`` – Wörter, Verben und Zustände reisen fertig mit. Sie steht hier,
    #: damit eine **Liste** von Belegen sortiert werden kann, ohne jeden zu befragen.
    direction: str = "buy"
    #: Welche Rolle die Auswahl anbieten darf (``/orders/party-options``) und wie sie im
    #: Satz heisst. Beides kommt aus derselben Regel, die ``apply`` durchsetzt.
    party_role: str = "supplier"
    party_word: str = "Lieferant"

    # ─── Forderung und Geld: lauter Ableitungen, keine Spalte ────────────────────
    #: Was tatsächlich geflossen ist (netto – Erstattungen zählen negativ).
    paid: Optional[float] = None
    #: Was **gefordert** wird – die Summe der Rechnungen. Gutschriften zählen negativ,
    #: weil sie negative Rechnungen sind.
    charged: Optional[float] = None
    #: **Zugesagt, noch nicht berechnet** – und damit die Vorgabe für die nächste
    #: Rechnung. Die Zahl, die es vor der dritten Achse gar nicht geben konnte.
    uncharged: Optional[float] = None
    #: **Forderungen − Zahlungen.** Darf negativ sein: dann schulden **wir**.
    #: ``None``, solange keine Summe zugesagt ist – dort gibt es nichts zu rechnen.
    open: Optional[float] = None
    #: Die **früheste offene** Fälligkeit unter den Rechnungen. ``None`` heisst «steht
    #: nicht fest», nicht «heute». Sie war einmal ``Zusagedatum + Frist`` – das konnte nur
    #: den Fall «eine Rechnung» und wurde bei einer Anzahlung stillschweigend falsch.
    due_on: Optional[str] = None
    #: Fällig **und** noch etwas offen. Beides zusammen, sonst nicht.
    overdue: bool = False
    entries: list["PaymentEntry"] = Field(default_factory=list)
    #: Die **Rechnungen** – die dritte Achse. Eine mit negativem Betrag ist eine
    #: Gutschrift; eine eigene Art dafür gibt es nicht.
    invoices: list["InvoiceEntry"] = Field(default_factory=list)
    #: Die Vorgabe für die nächste Nummer (``<Auftragsnummer>-<laufend>``) – oder ``None``
    #: beim Einkauf: dort nummeriert die Gegenpartei, und eine erfundene Vorgabe wäre eine
    #: Behauptung über ein fremdes Dokument.
    next_invoice_number: Optional[str] = None
    #: Das Wort auf dem Knopf: «Rechnung stellen» ↔ «Rechnung erfassen». Wie jedes Verb
    #: kommt es vom Server – ein Literal in der Oberfläche wäre die zweite Aussage darüber,
    #: in welche Richtung dieser Beleg zeigt.
    invoice_verb: str = "Rechnung stellen"


class PurchaseUpdate(BaseModel):
    """Eine Handlung am Beleg – **ein** Endpunkt, in beide Richtungen dieselben Verben.

    ``ask``       mit wem gehandelt wird (``suppliers``) – anfragen bzw. anbieten
    ``quote``     ein Preis kommt herein (``supplier``, ``amount``, ``lead_days`` – Pflicht;
                  ``payment_days`` freiwillig)
    ``decline``   die Gegenpartei sagt ab (``supplier``)
    ``order``     zusagen (``supplier``, ``amount``)
    ``note``      die **Sendungsnummer** nachtragen (``tracking``) – auch vom Lieferanten
    ``revoke``    **die** Gegenhandlung – vor der Zusage zurückziehen, danach stornieren
    ``clarified`` die Gegenpartei hat der geänderten Menge zugestimmt
    ``buy``       «das kaufe ich ein» – legt den Beleg an (nur wo er eine Wahl ist)
    ``pay``       **eine Zeile Geld** (``amount``, ``kind``, ``method``, ``reference``,
                  ``paid_at``, ``note_text``)

    ``buy`` und ``pay`` stehen bewusst **nicht** in ``STAGE_ACTIONS``: sie haben keine
    Stufe. Der eine kommt davor (er legt den Beleg an), der andere läuft daneben – Geld
    fliesst auch noch, wenn längst geliefert oder storniert ist. Ihr Tor ist darum ein
    anderes (``Module.buys`` bzw. ``payments.assert_payable``), aber der **Weg** ist
    derselbe: ein zweiter Endpunkt wäre ein zweiter Weg zu einer Sache, die dieser Beleg
    verwaltet.
    """

    action: str
    suppliers: list[int] = Field(default_factory=list)
    supplier: Optional[int] = None
    amount: Optional[float] = None
    lead_days: Optional[int] = None
    #: Die Zahlungsfrist in Tagen (bei ``quote``) – freiwillig.
    payment_days: Optional[int] = None
    tracking: Optional[str] = None

    # ─── nur für ``pay`` ─────────────────────────────────────────────────────────
    #: ``payment`` (Geld ist geflossen) · ``credit`` (die Forderung wird gemindert).
    kind: Optional[str] = None
    #: ``transfer`` · ``card`` · ``cash`` – Pflicht bei einer Zahlung, **verboten** bei
    #: einer Gutschrift: dort fliesst kein Geld.
    method: Optional[str] = None
    #: Zahlungszweck, Bankbeleg – oder die Id des Zahlungsdienstes. **Dieselbe Referenz
    #: ist dieselbe Zahlung**: ein zweiter Aufruf gibt die bereits gebuchte Zeile zurück.
    reference: Optional[str] = None
    #: Wann das Geld geflossen ist (``YYYY-MM-DD``). Ohne Angabe: heute.
    paid_at: Optional[str] = None
    #: Ein Satz dazu. Heisst nicht ``note`` – das ist bereits ein **Verb** dieses Belegs.
    note_text: Optional[str] = None


class StepConfirm(BaseModel):
    """«Bestätigen» an einem Modul — **ein Wertesatz je Einzelinstanz**.

    ``values`` ist zweistufig: **Nummer der Einzelinstanz** → (Punkt-``key`` → Wert).
    Erwartet wird genau ein Satz je **gezogenem** Stück; zu viele oder zu wenige werden
    abgewiesen (``process._captures_for``).

    **Der Scan verifiziert die Instanz, die Erfassung gilt der Einzelinstanz.** Beides
    hier nebeneinander zu haben ist der ganze Punkt: ``instance_object_id`` ist die
    verifizierte Instanz (eine – das Etikett klebt am physischen Ding),
    ``values`` sind ihre n Messungen. Wäre es ein flacher Satz, entstünden aus einer
    Messung n gleiche Zeilen, und der Nachweis behauptete Messungen, die niemand gemacht
    hat.

    Ein Modul ohne Erfassungspunkte (Aussondern) bekommt einen **leeren** Satz – dort ist
    der Scan die Bestätigung, und ein Wert wäre ein Nachweis über nichts.

    ``verification`` sagt **wie** verifiziert wurde – gescannt oder von Hand eingegeben.
    Beides ist eine Bestätigung, und beides steht im Log; ohne den Vermerk wäre die
    Tastatur eine stille Umgehung der Scan-Pflicht statt ihrer Alternative.

    ``sources`` sind die Instanzen, aus denen ein **Verbrauchsmodul** nehmen soll – die
    Kisten, die der Lagerist gescannt hat. Es ist bewusst **keine Mengenangabe**: wie
    viel gebraucht wird, sagt die Stückliste des Moduls, und eine zweite Stelle dafür
    wäre ein zweiter Massstab. Leer heisst «der ganze freie Bestand, älteste zuerst».
    """

    values: dict[str, dict[str, Any]] = Field(default_factory=dict)
    instance_object_id: Optional[int] = None
    verification: Optional[str] = None
    sources: list[int] = Field(default_factory=list)
    #: **Der gescannte Zielort** eines Bewegungsmoduls – die Objektnummer des Halters.
    #: Steht in der Definition bereits ein Ziel, ist dieser Scan die **Verifikation**
    #: dagegen: eine andere Nummer wird abgewiesen (``Bewegen.movement_for``), hier und
    #: nicht nur im Dialog. Steht dort keines, ist er die **Wahl** – und dann Pflicht,
    #: denn ohne ihn wüsste niemand, wohin die Stücke gebracht wurden.
    place: Optional[int] = None
    # **Kein «womit».** Ob eingekauft wurde, sagt der Beleg (``Module.buys``) – eine
    # Eingabe daneben wäre eine zweite Angabe über dieselbe Sache, und die getippte
    # gewänne auch dann, wenn niemand eine Spedition beauftragt hat.


class RecordValue(BaseModel):
    """Ein erfasster Wert — **mit seiner Frage**, nicht nur mit seinem Schlüssel."""

    key: str
    label: str
    type: str
    value: Any = None
    #: Das Urteil dieses Punktes. ``None`` heisst «hier war nichts zu beurteilen» – ein
    #: Foto belegt, es bewertet nicht.
    ok: Optional[bool] = None


class RecordEntry(BaseModel):
    """Ein Vorgang an einem Modul, an **einer** Einzelinstanz.

    Ein Stück kann dasselbe Modul mehrfach passieren (nach einem «nicht bestanden» wird
    erneut erfasst) – dann stehen hier mehrere Einträge. Zusammengefasst würde die
    Wiederholung die Vergangenheit überschreiben.
    """

    number: str
    at: datetime
    actor: Optional[str] = None
    verification: Optional[str] = None
    #: Der Zustand **nach** dem Vorgang. ``None`` = nichts rückte vor («nicht bestanden»).
    status_after: Optional[str] = None
    #: Der Zustand **vor** dem Vorgang – erst mit ihm ist ablesbar, ob sich etwas geändert
    #: hat. Ein Durchläufer führt ``Im Prozess`` → ``Im Prozess``; ihn anzuzeigen hiesse,
    #: in jeder Zeile dasselbe Wort zu wiederholen (Testnotiz #726).
    status_before: Optional[str] = None
    result: Optional[str] = None
    #: ``False`` heisst: ausserhalb der Ziehung durchgelaufen, ohne Erfassung.
    sampled: bool = True
    #: Nur beim Verbrauch: die Nummer des Stücks, in das hier verbaut wurde.
    into: Optional[str] = None
    values: list[RecordValue] = Field(default_factory=list)


class StepRecord(BaseModel):
    """**Was an diesem Modul passiert ist** – seitenweise, mit ehrlicher Gesamtzahl."""

    entries: list[RecordEntry] = Field(default_factory=list)
    total: int = 0


class HoldNumbers(BaseModel):
    """Die Nummern einer Entscheidungs-Gruppe – Vorauswahl für einen Auftragsentwurf."""

    numbers: list[str] = Field(default_factory=list)
