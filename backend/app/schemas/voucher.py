"""**Der Beleg über die API** – die Formen des neu aufgebauten Moduls «Zahlung».

Eigenständig wie sein Dienst: keine Zeile hiervon hängt an ``schemas/deal``. Beträge
reisen als **String** – wo es auf den Rappen ankommt, wird nicht durch ``float``
gerechnet, auch nicht auf dem Weg durch JSON.

►►► **Die Tür muss jedes Feld kennen.** ◄◄◄ Pydantic verwirft Unbekanntes
**stillschweigend**: ein Feld, das hier fehlt, kommt nie an, und **kein Dienst-Test findet
das** – die rufen den Dienst direkt. Genau daran sind schon ``ModuleConfigInput`` und
``DealUpdate`` einmal gescheitert.
"""

from datetime import date, datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class VoucherStage(BaseModel):
    """Eine der **zwei** Stufen – mit ihrem Wort, ihrem Verb und ihrem Zustand."""

    key: str
    label: str
    #: Was man tut, um sie zu verlassen. ``None`` bei einem Ausgang.
    verb: Optional[str] = None
    done: bool = False
    active: bool = False


class VoucherParty(BaseModel):
    """Eine Gegenpartei – Objektnummer und Anzeigename."""

    object_id: int
    name: str = ""


class VoucherQuoteOut(BaseModel):
    """**Eine Angebotszeile** – je angefragter Gegenpartei eine.

    Seit sie eine **Tabelle** ist, trägt sie ihre eigene Id: die Oberfläche adressiert
    damit genau diese Zeile, statt über die Objektnummer der Partei zu gehen.
    """

    id: int
    party_object_id: int
    party_name: str = ""
    #: **Was bei ihm zu tun ist** – aus der Definition (``parties[].ref``). Sie gehört der
    #: Paarung Modul × Partner: derselbe Lieferant führt je Teil eine andere Nummer.
    ref: str = ""
    amount: Optional[str] = None
    lead_days: Optional[int] = None
    payment_days: Optional[int] = None
    state: str = "angefragt"
    #: **Das Datum auf dem Papier** – ein Beleg trägt einen Tag, keine Uhrzeit.
    sent_on: Optional[date] = None
    #: ►►► **Wann die Zeile hinausging** (Testnotiz #968) – der **Moment**, nicht der Tag.
    #:
    #: Er steht ohne eine eigene Spalte da: ``created_at`` der Angebotszeile *ist* dieser
    #: Moment, weil ``_ask`` sie genau dort anlegt. Die Oberfläche macht daraus «vor 3
    #: Tagen offeriert» und nennt im Hover Datum **und** Uhrzeit.
    sent_at: Optional[datetime] = None
    #: ►►► **Wann bei dieser Zeile zugesagt wurde** (Testnotiz #969). ◄◄◄
    #:
    #: ``None`` an jeder Zeile, die den Zuschlag nicht hat. An der gewählten ist es
    #: ``updated_at``: ``_agree`` setzt ``CHOSEN`` in einem Zug mit der Stufe, und danach
    #: fasst kein Verb die Zeile mehr an.
    agreed_at: Optional[datetime] = None


class VatRateOut(BaseModel):
    """Ein Steuersatz des Katalogs.

    **Der Pflichtsatz reist mit dem Satz** (``note``): *Export* und *Reverse Charge* sind
    zwei Rechtsgründe mit zwei Pflichtsätzen und ergeben beide 0 % – ein Beleg, der nur
    «0 %» sagt, nennt den Grund nicht.
    """

    key: str
    rate: str
    label: str
    note: Optional[str] = None


class IncotermOut(BaseModel):
    """Eine Klausel der Incoterms 2020 – mit ihrer Erklärung.

    Sie steht **sichtbar** und nicht nur im Hover: es ist die Stelle im ganzen Beleg, an
    der ein Kürzel über Tausende entscheidet, und wer nicht weiss, dass er fragen müsste,
    findet keinen Hover.
    """

    key: str
    label: str
    hint: str = ""


class CurrencyOut(BaseModel):
    """Eine wählbare Währung – Code und Name."""

    code: str
    label: str


class IssuerOut(BaseModel):
    """Eine unserer Gesellschaften, die den Beleg stellen kann."""

    object_id: Optional[int] = None
    name: str = ""


class VatShare(BaseModel):
    """Eine Zeile der Steuer-Aufteilung – **je Katalogzeile**, nicht je Zahl."""

    #: Der Schlüssel der Katalogzeile. ``None`` bei Altbestand, der nur die Zahl trug.
    vat: Optional[str] = None
    rate: str = "0.00"
    #: Der Name des Satzes – er reist mit, damit die Anzeige nicht «normal %» schreibt.
    label: Optional[str] = None
    #: Der Pflichtsatz dieses Tatbestands, sofern einer verlangt ist.
    note: Optional[str] = None
    net: str = "0"
    tax: str = "0"


class VoucherLineOut(BaseModel):
    """**Eine Position** – und es gibt sie in genau dieser einen Form.

    Sie trägt ihre **Id**: die Oberfläche bepreist damit genau diese Zeile. Beim Vorgänger
    gab es dieselbe Sache dreimal (abgeleitet · je Angebot kopiert · eingefroren), und die
    Oberfläche musste über Artikelnummern zuordnen.
    """

    id: int
    article_id: Optional[int] = None
    article_object_id: Optional[int] = None
    article_name: str = ""
    quantity: int = 0
    #: **Zoll** – der Artikel belegt vor, der Beleg trägt den Wert.
    hs_code: Optional[str] = None
    origin_country: Optional[str] = None
    #: Der Einzelpreis, **netto**. ``None`` heisst «noch kein Preis genannt».
    price: Optional[str] = None
    #: Der **Schlüssel** der Katalogzeile – nicht die Zahl.
    vat: str = "normal"
    #: Zahl und Name daneben, damit die Anzeige nichts auflösen muss.
    vat_rate: str = "0.00"
    vat_label: str = ""
    vat_note: Optional[str] = None


class VoucherPrice(BaseModel):
    """Was an **einer** Position geändert wird (``price``).

    Adressiert über die **Id der Zeile**: die Menge kommt aus dem Prozess und steht hier
    bewusst nicht – eine getippte wäre die zweite Aussage über dieselbe Sache.
    """

    id: int
    #: Als **String**, weil es ein Eingabefeld ist: ein halb getipptes Feld hat keine Zahl,
    #: und ein Komma ist ein Dezimaltrennzeichen, kein Fehler.
    price: Optional[str] = None
    vat: Optional[str] = None
    hs_code: Optional[str] = None
    origin_country: Optional[str] = None


class VoucherEntryOut(BaseModel):
    """**Eine Zeile Geld** – eine Forderung oder eine Zahlung."""

    id: int
    kind: str
    amount: str
    booked_on: Optional[date] = None
    due_on: Optional[date] = None
    reference: Optional[str] = None
    note: Optional[str] = None
    #: **Überfällig ist eine Ableitung, kein Zustand**: fällig *und* noch etwas offen.
    overdue: bool = False
    #: Die eingefrorene Steuer-Aufteilung dieses Belegs.
    vat: list[VatShare] = Field(default_factory=list)
    #: Wann die Leistung erbracht wurde (MWSTG Art. 26 Abs. 2 Bst. c).
    service_date: Optional[date] = None
    #: Welche Zeile diese hier storniert …
    reverses: Optional[int] = None
    #: … und ob sie selbst storniert wurde.
    reversed: bool = False
    #: Welche Rechnung diese Zahlung begleicht.
    charge_id: Optional[int] = None
    method: Optional[str] = None
    method_label: Optional[str] = None
    #: **Storno ODER Gutschrift** – das Wort hängt an der Zahl, nicht an einem zweiten Verb.
    reverse_word: Optional[str] = None
    #: Was auf **dieser** Rechnung noch offen ist.
    open: Optional[str] = None
    #: ►►► **Der Zustand dieser Forderung – Wort und Ampelton vom Server** (#991). ◄◄◄
    #:
    #: *Offen · Teilweise bezahlt · Beglichen · Überfällig · Überzahlt · Storniert* –
    #: abgeleitet aus Betrag und Rest (``domain/voucher.charge_state``), inklusive der
    #: Rundungstoleranz. Der Ton ist einer der **drei** des Hauses (``done`` · ``pending``
    #: · ``danger``); die Farbe dazu steht in den Tokens, nicht hier.
    #:
    #: Vorher rechnete die Oberfläche ihn selbst – eine zweite Ableitung derselben Sache,
    #: ohne Toleranz und ohne «teilweise bezahlt». `None` bei einer Zahlung: sie ist ein
    #: Ereignis, kein Beleg mit einem Stand.
    state: Optional[str] = None
    state_label: Optional[str] = None
    state_tone: Optional[str] = None
    #: Lässt sie sich über den Zahlungsdienst zurückgeben?
    refundable: bool = False
    #: ►►► **``transferable`` ist entfallen.** ◄◄◄ Es sagte je Zeile, ob sie einen
    #: Einzahlungsschein trägt – aus der Zeit, als jede Bezahlart ein eigener Knopf an
    #: jeder Rechnung war. Welche Rechnung das Fach «Begleichen» meint, sagt jetzt
    #: ``VoucherEmbed.settle_charge``: **eine** Antwort statt einer je Zeile.


class VoucherWay(BaseModel):
    """►►► **Ein Weg zum Geld – und was er auslöst.** ◄◄◄

    Bar · Überweisung · Karte sind drei Antworten auf **eine** Frage. Jeder Weg trägt
    darum sein eigenes Verb: ``action`` ist die Handlung am Beleg (``pay`` ↔
    ``pay_online``), ``verb`` ihr Wort. **Beide leer** heisst: dieser Weg ist eine reine
    *Auskunft* – so sieht die Gegenpartei die Überweisung, und dort steht kein Knopf, der
    nach Buchung aussieht.
    """

    key: str
    label: str
    action: Optional[str] = None
    verb: Optional[str] = None
    #: **Bringt dieser Weg eine Auskunft mit?** – heute der Einzahlungsschein
    #: (Bankverbindung, Referenz, QR). Sie steht als **Eigenschaft des Weges** da und
    #: nicht als Vergleich auf «transfer»: ein Schlüssel-Vergleich in der Oberfläche wäre
    #: der Spiegel über die API-Grenze, der beim nächsten Weg still falsch wird.
    info: bool = False


class VoucherTerm(BaseModel):
    """Eine übliche Frist mit ihrem **Namen** – «Vorauszahlung» statt «0»."""

    days: int
    label: str


class DataGap(BaseModel):
    """**Eine fehlende Stammdatenangabe** – ``StepNeed`` für Stammdaten.

    Wo sie hingehört (klickbar), was fehlt und **warum dieser Beleg sie braucht**. Kein
    Zustand und kein Pausenwert: das Modul ist schlicht nicht vollständig.
    """

    record_object_id: Optional[int] = None
    record_label: str = ""
    field_label: str = ""
    why: str = ""


class VoucherSide(BaseModel):
    """**Eine Seite des Belegkopfs** – Leistungserbringer bzw. -empfänger.

    Die Begriffe des MWSTG: sie gelten für *jede* Leistung (Ware, Dienstleistung, Miete,
    Lohn, Transport) und passen wörtlich zum Reverse-Charge-Pflichtsatz. Der erklärende
    Satz reist mit – ein Fachbegriff ohne Erklärung ist eine Rückfrage mit Verzögerung.
    """

    label: str = ""
    hint: str = ""
    #: ►►► **Ist das unsere Seite?** ◄◄◄ Welcher Block die Gegenpartei ist, wechselt mit
    #: der Richtung – und die Oberfläche muss es wissen, um beim Umschalten des Empfängers
    #: den richtigen zu tauschen. Ein Vergleich auf «Leistungserbringer» wäre ein Spiegel
    #: über die API-Grenze; dies **ist** die Struktur.
    ours: bool = False
    object_id: Optional[int] = None
    #: Der Name **mit Rechtsform** – auf einem Beleg steht die, die haftet.
    name: str = ""
    #: «z. H. …», wo die Rechtsperson eine Firma ist.
    attn: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    #: Die Anschrift als **Zeilen** – auf einem Dokument ist sie Text in fester
    #: Reihenfolge, und eine zweite Fassung im Browser wäre die Stelle, an der eine Zeile
    #: verrutscht. Leer heisst «nicht hinterlegt»; erfunden wird nichts.
    address: list[str] = Field(default_factory=list)
    #: ►►► **Die zweite Anschrift – und es gibt sie IMMER** (#952/#975). ◄◄◄ Ein Beleg
    #: fragt auf jeder Seite dasselbe: *wohin die Rechnung, wohin die Ware.* Steht nur eine
    #: Anschrift da, trägt sie beide Beschriftungen – das ist die Auskunft «an dieselbe».
    #: Leer sind beide nur, wo **gar keine** hinterlegt ist; dann sind auch die
    #: Beschriftungen ``None``, denn dort sagt die Seite, dass sie fehlt.
    shipping: list[str] = Field(default_factory=list)
    address_label: Optional[str] = None
    shipping_label: Optional[str] = None
    uid: Optional[str] = None


class VoucherEmbed(BaseModel):
    """**Der ganze Beleg, wie die Ausführungsstelle ihn braucht.**

    Alles, was die Oberfläche zum Zeichnen braucht, reist mit: Wörter, Stufen, Verben,
    Zahlen und was man tun darf. Sie fragt damit **nie** nach der Richtung und **nie** nach
    dem Modultyp.
    """

    # ─── Wer und was ────────────────────────────────────────────────────────────
    direction: str = "out"
    label: str = ""
    party_word: str = ""
    ask_verb: str = ""
    #: **Wer den Preis nennt** – daraus folgt die ganze Abfolge.
    we_quote: bool = False
    #: Wie das Nummernfeld heisst. ``None`` = **wir** nummerieren, also kein Feld.
    ref_label: Optional[str] = None
    # ─── Die Überschriften des Belegs ───────────────────────────────────────────
    goods_title: str = ""
    quotes_title: str = ""
    #: ►►► **Zwei Fächer statt eines Titels über allem** («Rechnung & Zahlung»). ◄◄◄
    #: *Was schuldet uns jemand* und *wie kommt das Geld hierher* sind zwei Fragen, und
    #: jede gehört genau einer Seite: die erste uns, die zweite dem Zahlenden.
    claim_title: str = ""
    settle_title: str = ""
    #: **Was ist zu tun?** – der Satz am **Modul**, und wie er heisst. Leer heisst «gemäss
    #: Spezifikation»: der Beleg sagt über seine Positionen längst, *was* es ist.
    task_label: str = ""
    task: str = ""
    #: **Wie bestellen?** – die Beschriftung der Angabe an **einer Partner-Zeile**. Sie
    #: steht auch, wo es die Angabe nicht gibt: was der Beleg **anbietet**, entscheidet
    #: das Feld selbst (``quotes[].ref``), nicht eine zweite Bedingung daneben.
    order_label: str = ""
    # ─── Steuer ─────────────────────────────────────────────────────────────────
    vat_rates: list[VatRateOut] = Field(default_factory=list)
    vat_rate: str = "normal"
    vat_label: str = "MWST"
    service_date_label: str = "Leistungsdatum"
    #: Netto und Steuer sind **Ableitungen** der Positionen – null Spalten.
    net: Optional[str] = None
    tax: Optional[str] = None
    vat_split: list[VatShare] = Field(default_factory=list)
    # ─── Währung ────────────────────────────────────────────────────────────────
    currency: str = "CHF"
    currency_label: str = "CHF"
    #: Die Nachkommastellen **dieser** Währung – JPY hat null, KWD drei.
    currency_decimals: int = 2
    currencies: list[CurrencyOut] = Field(default_factory=list)
    # ─── Aussteller ─────────────────────────────────────────────────────────────
    issuer: Optional[int] = None
    issuer_label: str = ""
    issuers: list[IssuerOut] = Field(default_factory=list)
    # ─── Lieferbedingung ────────────────────────────────────────────────────────
    incoterm: Optional[str] = None
    incoterm_place: Optional[str] = None
    #: Der fertige Satz – im Browser zusammengesetzt wäre er die zweite Schreibweise.
    incoterm_text: Optional[str] = None
    incoterm_label: str = ""
    incoterm_place_label: str = ""
    incoterm_place_hint: str = ""
    incoterms: list[IncotermOut] = Field(default_factory=list)
    # ─── Stufen und Handlungen ──────────────────────────────────────────────────
    stage: str = "offer"
    #: ►►► **Kein `stage_label`** (Testnotizen #974/#977). ◄◄◄ Der Belegkopf nannte damit
    #: die Belegart – zweimal abgelehnt, und sie sagt nichts, was die Punkte an den
    #: Abschnitten und der Knopf darunter nicht schon sagen.
    stages: list[VoucherStage] = Field(default_factory=list)
    #: **Auskunft UND Tor** – dieselbe Liste rendert die Knöpfe und weist in
    #: ``assert_allowed`` ab.
    can: list[str] = Field(default_factory=list)
    #: Das Wort der Gegenhandlung – ``None``, wo es sie für diesen Betrachter nicht gibt.
    undo: Optional[str] = None
    #: **«Rechnung stellen» ↔ «Rechnung erfassen»** – im einen Fall entsteht der Beleg
    #: hier, im anderen schreiben wir einen fremden ab (``Direction.charge_verb``).
    charge_word: str = ""
    payment_word: str = ""
    pay_online_word: str = ""
    open_word: str = "Offen"
    refund_online_word: str = ""
    # ─── Fristen ────────────────────────────────────────────────────────────────
    #: **Eine Ableitung der Zahlungsfrist**, keine Einstellung: null Tage ab Zusage *ist*
    #: die Vorauszahlung.
    prepaid: bool = False
    payment_terms: list[VoucherTerm] = Field(default_factory=list)
    lead_terms: list[VoucherTerm] = Field(default_factory=list)
    term_free_min: int = 1
    term_free_label: str = ""
    payment_term_label: str = ""
    lead_term_label: str = ""
    # ─── Die Wege zum Geld ──────────────────────────────────────────────────────
    #: **Eine Frage, mehrere Antworten** – leer heisst «hier ist gerade nichts zu
    #: begleichen» (keine offene Forderung). Der frühere ``methods`` war die halbe Liste:
    #: er kannte nur die beiden Arten, die ein Mensch **erfasst**, und die Karte und die
    #: Überweisungs-Auskunft standen daneben als eigene Knöpfe.
    ways: list[VoucherWay] = Field(default_factory=list)
    #: **Welche Rechnung die Wege meinen** – je Modul lebt höchstens eine offene (#866),
    #: die Frage hat also genau eine Antwort, und sie gehört dem Dienst.
    settle_charge: Optional[int] = None
    method_label: str = ""
    # ─── Der Beleg selbst ───────────────────────────────────────────────────────
    allowed: list[VoucherParty] = Field(default_factory=list)
    quotes: list[VoucherQuoteOut] = Field(default_factory=list)
    lines: list[VoucherLineOut] = Field(default_factory=list)
    supplier: Optional[VoucherSide] = None
    customer: Optional[VoucherSide] = None
    #: Je **angefragtem** Empfänger eine ganze Seite – der Kopf zeigt einen, die Oberfläche
    #: schaltet um (#951). Leer für eine Gegenpartei: das ist die Konkurrenzliste.
    recipients: list[VoucherSide] = Field(default_factory=list)
    gaps: list[DataGap] = Field(default_factory=list)
    # ─── Die Ableitungen der gewählten Angebotszeile ────────────────────────────
    #: *mit wem · was vereinbart ist · welche Fristen* – sie stehen an der **gewählten
    #: Zeile** und nicht als Spalten daneben. Damit kann derselbe Beleg nicht zwei Dinge
    #: sagen.
    party_object_id: Optional[int] = None
    party_name: Optional[str] = None
    amount: Optional[str] = None
    due_days: Optional[int] = None
    lead_days: Optional[int] = None
    agreed_on: Optional[date] = None
    cancelled_on: Optional[date] = None
    #: Liefertermin und Verzug – zwei Ableitungen, null Spalten.
    due_date: Optional[date] = None
    late: bool = False
    # ─── Geld ───────────────────────────────────────────────────────────────────
    charged: Optional[str] = None
    paid: Optional[str] = None
    open: Optional[str] = None
    #: *zugesagt − berechnet* – die Zahl, die es ohne die Trennung von Forderung und Geld
    #: gar nicht geben könnte.
    uncharged: Optional[str] = None
    #: **Eine Rechnung je Modul**: steht sie, bleibt nur die Gutschrift.
    credit_only: bool = False
    next_charge: Optional[str] = None
    next_payment: Optional[str] = None
    settled: bool = False
    entries: list[VoucherEntryOut] = Field(default_factory=list)


class VoucherUpdate(BaseModel):
    """**Eine Handlung am Beleg** – ein Endpunkt, eine Tabelle (``services/voucher.VERBS``).

    ``price``    die Positionen bepreisen (``lines``) – **gespeichert, nicht abgeschickt**
    ``ask``      anfragen bzw. anbieten (``parties`` – leer heisst: alle zugelassenen)
    ``unask``    eine Anfrage **zurückziehen** (``party``) – die Gegenhandlung zu ``ask``
    ``quote``    einen Preis an EINER Angebotszeile – auch von der Gegenpartei
    ``decline``  eine Angebotszeile absagen – auch von der Gegenpartei
    ``agree``    den **Zuschlag** geben (``party``)
    ``revoke``   stornieren – die eine Gegenhandlung
    ``charge``   eine **Forderung** buchen (negativ = Gutschrift)
    ``pay``      eine **Zahlung** buchen (negativ = Erstattung)
    ``reverse``  eine Geld-Zeile stornieren – als **Gegenbuchung**, nie als Löschung
    ``currency`` · ``issuer`` · ``incoterm`` – nur vor der Zusage

    **Eine Gegenpartei trifft ausschliesslich ihre eigene Zeile**: ``party`` wird bei ihr
    **verworfen** und aus dem angemeldeten Benutzer gelesen. Wer die Regel erst an der Tür
    formulierte, hätte sie beim zweiten Aufrufer nicht.

    **Nur gesendete Felder wirken** (``exclude_unset``): ein Feld, das nicht mitkommt,
    bleibt, wie es war.
    """

    action: str
    #: Die Objektnummer der Gegenpartei, deren Zeile gemeint ist.
    party: Optional[int] = None
    #: Wen anfragen (``ask``). Leer heisst: **alle zugelassenen**.
    parties: list[int] = Field(default_factory=list)
    lead_days: Optional[int] = None
    payment_days: Optional[int] = None
    #: Als **String**, weil es ein Eingabefeld ist.
    amount: Optional[str] = None
    reference: Optional[str] = None
    note: Optional[str] = None
    booked_on: Optional[date] = None
    due_on: Optional[date] = None
    #: Welche Zeile storniert wird (``reverse``).
    entry: Optional[int] = None
    #: Welche Rechnung eine Zahlung begleicht (``pay``).
    charge_id: Optional[int] = None
    #: **Die Positionen** (``price``) – je Zeile ihre Id und was sich ändert.
    lines: Optional[list[VoucherPrice]] = None
    #: **Der Steuersatz einer Forderung**, wo es keine bepreisten Positionen gibt (eine
    #: *Ausgabe*: die Steuer steht auf **seiner** Rechnung, und wir schreiben sie ab).
    vat: Optional[str] = None
    currency: Optional[str] = None
    method: Optional[str] = None
    #: Klausel **und** benannter Ort – sie sind **eine** Vereinbarung: eine Klausel ohne
    #: Ort ist keine, ein Ort ohne Klausel sagt nichts.
    incoterm: Optional[str] = None
    incoterm_place: Optional[str] = None
    issuer: Optional[int] = None

    def changes(self) -> dict[str, Any]:
        """Was tatsächlich gesendet wurde – ohne ``action``."""
        return self.model_dump(exclude={"action"}, exclude_unset=True)
