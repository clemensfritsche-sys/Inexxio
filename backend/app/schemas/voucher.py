"""**Der Beleg über die API** – die Formen des Moduls «Zahlung».

Beträge reisen als **String** – wo es auf den Rappen ankommt, wird nicht durch ``float``
gerechnet, auch nicht auf dem Weg durch JSON.

►►► **Die Tür muss jedes Feld kennen.** ◄◄◄ Pydantic verwirft Unbekanntes
**stillschweigend**: ein Feld, das hier fehlt, kommt nie an, und **kein Dienst-Test findet
das** – die rufen den Dienst direkt.
"""

import datetime as _dt
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
    #: **Wie die Partei auf dem Beleg steht** – Firma zuerst, die Person als «z. H.»
    #: (``people.billing_name``); dieselbe Form wie der Kandidat davor.
    party_name: str = ""
    party_attn: Optional[str] = None
    #: **Was bei ihm zu tun ist** – aus der Definition (``parties[].ref``). Sie gehört der
    #: Paarung Modul × Partner: derselbe Lieferant führt je Teil eine andere Nummer.
    ref: str = ""
    amount: Optional[str] = None
    lead_days: Optional[int] = None
    payment_days: Optional[int] = None
    state: str = "angefragt"
    #: **Seine Referenz** (bei einem Online-Kauf die Bestellnummer) und der Link dazu.
    reference: Optional[str] = None
    link: Optional[str] = None
    #: Der Tag auf dem Papier, an dem sie hinausging.
    sent_on: Optional[date] = None
    #: ►►► **Wann die Zeile hinausging** – der **Moment**, nicht der Tag.
    #:
    #: Er steht ohne eine eigene Spalte da: ``created_at`` der Angebotszeile *ist* dieser
    #: Moment, weil ``_ask`` sie genau dort anlegt. Die Oberfläche macht daraus «vor 3
    #: Tagen offeriert» und nennt im Hover Datum **und** Uhrzeit.
    sent_at: Optional[datetime] = None
    #: ►►► **Wann bei dieser Zeile zugesagt wurde**. ◄◄◄
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

    Sie trägt ihre **Id**: die Oberfläche bepreist damit genau diese Zeile.
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
    #: **Die Leistung** – der Untertitel unter dem Artikel.
    text: Optional[str] = None
    #: **Ware oder Dienstleistung** (am Artikel) – daraus folgen Satz und Lieferbedingung.
    is_service: bool = False
    kind_label: str = "Ware"
    #: **Teilbetrag netto** – ``None`` heisst Vollbetrag.
    part: Optional[str] = None
    #: Der Vollbetrag (Menge × Preis) und der Betrag dieser Rechnung, beide netto.
    full: Optional[str] = None
    net: Optional[str] = None
    weight_kg: Optional[str] = None
    #: **Welche Sätze hier wählbar sind** – die Anschrift entscheidet (Ausland: einer).
    vat_choices: list[str] = Field(default_factory=list)


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
    text: Optional[str] = None
    #: ``null`` (gesendet) heisst «Vollbetrag».
    part: Optional[str] = None
    weight_kg: Optional[str] = None


class VoucherInvoice(BaseModel):
    """►►► **DIE Rechnung dieses Belegs — sie IST der Beleg.** ◄◄◄

    **Ein Objekt oder ``None``** – und ``None`` ist die vollständige Antwort auf «gibt es
    hier eine Rechnung?». Zweimal vorkommen kann sie nicht; niemand zählt es, es ist die
    **Struktur**.
    """

    #: ``<Auftragsnummer>-<laufend>``, wo **wir** nummerieren – sonst die seine.
    number: Optional[str] = None
    #: Das Rechnungsdatum. Dass es dasteht, *ist* die Antwort auf «gestellt?».
    billed_on: Optional[date] = None
    #: Fälligkeit = Rechnungsdatum + vereinbarte Zahlungsfrist.
    due_on: Optional[date] = None
    #: Der Betrag **brutto**, eingefroren. Negativ heisst: dieser Beleg **mindert**.
    amount: Optional[str] = None
    #: Die eingefrorene Steuer-Aufteilung. **Nicht nachgerechnet**: ein Beleg behält, was
    #: auf ihm stand – sonst wäre die Vergangenheit eine Funktion der Gegenwart.
    vat: list[VatShare] = Field(default_factory=list)
    #: Wann die Leistung erbracht wurde (MWSTG Art. 26 Abs. 2 Bst. c).
    service_date: Optional[date] = None
    #: **Überfällig ist eine Ableitung, kein Zustand**: fällig *und* noch etwas offen.
    overdue: bool = False
    #: ►►► **Ihr Zustand – Wort und Ampelton vom Server.** ◄◄◄
    #:
    #: *Offen · Teilweise bezahlt · Beglichen · Überfällig · Überzahlt* – abgeleitet aus
    #: Betrag und Rest (``domain/voucher.invoice_state``), inklusive der Rundungstoleranz.
    #: Der Ton ist einer der **drei** des Hauses (``done`` · ``pending`` · ``danger``).
    state: Optional[str] = None
    state_label: Optional[str] = None
    state_tone: Optional[str] = None


class VoucherCorrects(BaseModel):
    """**Welchen Beleg mindert dieser hier?** – der Verweis, der auf das Papier gehört.

    MWSTG Art. 26 verlangt, dass Leistung und Entgelt eindeutig bestimmbar sind; ohne den
    Verweis wäre eine Gutschrift eine zweite Rechnung mit negativem Vorzeichen. Nummer und
    Betrag reisen mit, damit der Satz ohne einen zweiten Aufruf dasteht.
    """

    id: int
    number: Optional[str] = None
    billed_on: Optional[date] = None
    amount: Optional[str] = None


class VoucherCorrectable(BaseModel):
    """**Ein Beleg, den dieser hier mindern könnte** – die Auswahl der Korrektur.

    Er steht in der Regel in einem **anderen Auftrag**; darum reist dessen Objektnummer
    mit, sonst stünden mehrere Zeilen mit derselben Rechnungsnummer-Form nebeneinander
    und niemand wüsste, welche gemeint ist.
    """

    id: int
    number: Optional[str] = None
    billed_on: Optional[date] = None
    amount: Optional[str] = None
    currency: str = "CHF"
    order_object_id: Optional[int] = None


class VoucherEntryOut(BaseModel):
    """**Eine Zahlung** – und nur noch das.

    Die Forderung steht eine Ebene höher (``VoucherEmbed.invoice``): es gibt genau eine,
    und sie *ist* der Beleg.
    """

    id: int
    #: Negativ heisst **Erstattung** – ein Ereignis der Aussenwelt, kein zweites Verb.
    amount: str
    booked_on: Optional[date] = None
    reference: Optional[str] = None
    note: Optional[str] = None
    #: **Wann die Zeile erfasst wurde** – der Moment, nicht der Belegtag. Aus ihm
    #: kommt «vor 5 Minuten»; ein Datum ohne Uhrzeit kann das nicht sagen.
    booked_at: Optional[datetime] = None
    method: Optional[str] = None
    method_label: Optional[str] = None
    #: ``payment`` · ``writeoff`` · ``tip`` – und der Grund einer Ausbuchung.
    kind: str = "payment"
    reason: Optional[str] = None
    reason_label: Optional[str] = None
    #: Die Zeile, die diese hier gegenbucht («falsch erfasst»).
    reverses_id: Optional[int] = None
    iban: Optional[str] = None
    #: Lässt sie sich über den Zahlungsdienst zurückgeben?
    refundable: bool = False
    #: Lässt sie sich als «falsch erfasst» gegenbuchen?
    reversible: bool = False


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


class AddressOption(BaseModel):
    """Eine Anschrift aus dem Adressbuch des Adressaten – Id und eine Zeile Text."""
    id: int
    label: str


class VoucherAddressing(BaseModel):
    """**An wen und wohin** – die drei Wahlen am Beleg, mit dem, was gilt."""
    #: Die Firma der Person (Name mit Rechtsform) – ``None``, wo es keine gibt: dann ist
    #: «Firma» keine Möglichkeit, und es gibt nichts umzuschalten.
    company: Optional[str] = None
    #: Die Person – die andere Antwort auf «an wen geht die Rechnung?».
    person: str = ""
    bill_to_company: bool = False
    billing_address_id: Optional[int] = None
    delivery_address_id: Optional[int] = None
    options: list[AddressOption] = Field(default_factory=list)


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
    #: ►►► **Die zweite Anschrift – und es gibt sie IMMER**. ◄◄◄ Ein Beleg
    #: fragt auf jeder Seite dasselbe: *wohin die Rechnung, wohin die Ware.* Steht nur eine
    #: Anschrift da, trägt sie beide Beschriftungen – das ist die Auskunft «an dieselbe».
    #: Leer sind beide nur, wo **gar keine** hinterlegt ist; dann sind auch die
    #: Beschriftungen ``None``, denn dort sagt die Seite, dass sie fehlt.
    shipping: list[str] = Field(default_factory=list)
    address_label: Optional[str] = None
    shipping_label: Optional[str] = None
    uid: Optional[str] = None
    #: ►►► **Was an dieser Seite noch wählbar ist** – nur an der Gegenseite, nur vor der
    #: Zusage und nur für das Personal (``voucher.choices_of``); sonst ``None``. ◄◄◄
    #: Danach steht der Kopf eingefroren da, und eine Auswahl wäre ein Versprechen, das
    #: der Dienst nicht hält.
    choice: Optional[VoucherAddressing] = None


class VoucherState(BaseModel):
    """►►► **Die Leiste der Karte** – Stand, Ton, wer dran ist, die eine nächste Handlung. ◄◄◄

    Nie leer ausser bei *Erledigt* und *Storniert* (``voucher.situation``). Ein Datum setzt
    die Oberfläche selbst zusammen (``date_word`` + ``lib/when.day``).
    """
    key: str
    label: str
    #: ``done`` · ``pending`` · ``danger`` · ``neutral``
    tone: str
    text: str = ""
    #: ``_dt.date`` – der Feldname ``date`` verdeckt sonst den Typ (Pydantic liest ``None``).
    date: Optional[_dt.date] = None
    date_word: Optional[str] = None
    #: Das Verb, das jetzt weiterbringt – oder ``None``.
    primary: Optional[str] = None


class VoucherOption(BaseModel):
    """Eine Wahl mit Schlüssel und Wort (Eigentum, Grund einer Ausbuchung)."""
    key: str
    label: str


class VoucherDocumentOut(BaseModel):
    """**Ein Dokument, so wie es hinausging** – mit dem Link der Partei."""
    id: int
    kind: str
    label: str
    number: Optional[str] = None
    sent_at: Optional[datetime] = None
    url: str


class VoucherEmbed(BaseModel):
    """**Der ganze Beleg, wie die Karte ihn braucht.** Sie fragt damit **nie** nach der
    Richtung und **nie** nach dem Modultyp."""

    # ─── Wer und was ────────────────────────────────────────────────────────────
    direction: str = "out"
    label: str = ""
    party_word: str = ""
    #: «Anbieten» · «Anfragen» · «Erneut anbieten».
    ask_verb: str = ""
    #: Warum «Anbieten» gesperrt ist (``voucher.ask_problem``) – oder ``None``.
    ask_problem: Optional[str] = None
    we_quote: bool = False
    ref_label: Optional[str] = None
    #: **Mindert dieser Beleg?** (Gutschrift, ``corrects``).
    minus: bool = False
    # ─── Die Abschnitte ─────────────────────────────────────────────────────────
    parties_title: str = ""
    goods_title: str = ""
    terms_title: str = ""
    quotes_title: str = ""
    invoice_title: str = ""
    docs_title: str = ""
    # ─── Die Leiste ─────────────────────────────────────────────────────────────
    state: Optional[VoucherState] = None
    #: **Die Stücke passen nicht mehr** – der Satz; dann bleibt nur «Stornieren».
    locked: Optional[str] = None
    # ─── Steuer ─────────────────────────────────────────────────────────────────
    vat_rates: list[VatRateOut] = Field(default_factory=list)
    vat_rate: str = "normal"
    vat_label: str = "MWST"
    service_date_label: str = "Leistungsdatum"
    net: Optional[str] = None
    tax: Optional[str] = None
    vat_split: list[VatShare] = Field(default_factory=list)
    #: **Eine Ausfuhr** – Zoll und Ausfuhrnachweis.
    export: bool = False
    # ─── Lieferbedingung ────────────────────────────────────────────────────────
    incoterm: Optional[str] = None
    #: **Abgeleitet**: E/F aus unserer, C/D aus der Lieferadresse.
    incoterm_place: Optional[str] = None
    incoterm_text: Optional[str] = None
    incoterm_label: str = ""
    incoterm_place_label: str = ""
    incoterms: list[IncotermOut] = Field(default_factory=list)
    #: Nur mit Ware – eine Dienstleistung reist nicht.
    incoterm_needed: bool = True
    # ─── Währung und Aussteller ─────────────────────────────────────────────────
    currency: str = "CHF"
    currency_label: str = "CHF"
    currency_decimals: int = 2
    currencies: list[CurrencyOut] = Field(default_factory=list)
    issuer: Optional[int] = None
    issuer_label: str = ""
    issuers: list[IssuerOut] = Field(default_factory=list)
    # ─── Wörter der Handlungen ──────────────────────────────────────────────────
    charge_word: str = ""
    payment_word: str = ""
    sent_word: str = ""
    taken_word: str = ""
    cancelled_word: str = ""
    pay_online_word: str = ""
    refund_online_word: str = ""
    refund_word: str = ""
    tip_word: str = ""
    write_off_word: str = ""
    write_off_reasons: list[VoucherOption] = Field(default_factory=list)
    reverse_word: str = ""
    #: Die nächste Mahnstufe («Zahlungserinnerung» …) und ab wann – oder ``None``.
    remind_word: Optional[str] = None
    remind_from: Optional[date] = None
    #: «Stornieren» – ``None``, wo es für diesen Betrachter nicht geht.
    undo: Optional[str] = None
    stage: str = "offer"
    stages: list[VoucherStage] = Field(default_factory=list)
    #: **Auskunft UND Tor** – dieselbe Liste rendert die Knöpfe und weist ab.
    can: list[str] = Field(default_factory=list)
    #: Die Verben, die ein Papier hinausgeben – die Karte zeigt es vorher und gibt frei.
    paper_verbs: list[str] = Field(default_factory=list)
    #: Das Papier, das jetzt ansteht (``confirmation`` · ``receipt``) – Verb ``release``.
    paper_due: Optional[str] = None
    # ─── Fristen, Gültigkeit, Eigentum ──────────────────────────────────────────
    prepaid: bool = False
    payment_terms: list[VoucherTerm] = Field(default_factory=list)
    lead_terms: list[VoucherTerm] = Field(default_factory=list)
    term_free_min: int = 1
    term_free_label: str = ""
    payment_term_label: str = ""
    lead_term_label: str = ""
    valid_days: Optional[int] = None
    valid_label: str = ""
    valid_until: Optional[date] = None
    expired: bool = False
    #: **Geändert seit dem Anbieten** – die gesendete Offerte ist überholt.
    changed: bool = False
    #: Was das Modul vorgibt (Schlüssel der Felder) – fest, punktiert, Grund im Hover.
    fixed: list[str] = Field(default_factory=list)
    fixed_hint: str = ""
    #: ``party`` · ``us`` – ``None``, solange niemand gewählt hat (Pflicht vor Anbieten/Zusage).
    ownership: Optional[str] = None
    ownership_label: str = ""
    ownership_options: list[VoucherOption] = Field(default_factory=list)
    # ─── Der Beleg selbst ───────────────────────────────────────────────────────
    allowed: list[VoucherParty] = Field(default_factory=list)
    quotes: list[VoucherQuoteOut] = Field(default_factory=list)
    lines: list[VoucherLineOut] = Field(default_factory=list)
    supplier: Optional[VoucherSide] = None
    customer: Optional[VoucherSide] = None
    recipients: list[VoucherSide] = Field(default_factory=list)
    gaps: list[DataGap] = Field(default_factory=list)
    party_object_id: Optional[int] = None
    party_name: Optional[str] = None
    amount: Optional[str] = None
    due_days: Optional[int] = None
    lead_days: Optional[int] = None
    agreed_on: Optional[date] = None
    cancelled_on: Optional[date] = None
    cancel_note: Optional[str] = None
    due_date: Optional[date] = None
    # ─── Rechnung und Geld ──────────────────────────────────────────────────────
    invoice: Optional[VoucherInvoice] = None
    #: Die Nummer der Gutschrift, die ein Storno nach der Rechnung erzeugt hat.
    credit_number: Optional[str] = None
    corrects: Optional[VoucherCorrects] = None
    corrects_label: str = ""
    corrects_hint: str = ""
    #: **Vorgeschlagen aus dem Log der Stücke** – die Rechnungen, über die sie liefen.
    corrects_suggested: list[VoucherCorrectable] = Field(default_factory=list)
    #: Ausgabe: MWST-Nr. und die Lieferantenrechnung (Dokumentnummer), Abweichung und Grund.
    party_uid: Optional[str] = None
    original: Optional[int] = None
    deviation: Optional[str] = None
    deviation_note: Optional[str] = None
    #: Der Ausfuhrnachweis – Nummer der Veranlagungsverfügung und ihr Dokument.
    export_number: Optional[str] = None
    export_photo: Optional[int] = None
    charged: Optional[str] = None
    credited: Optional[str] = None
    paid: Optional[str] = None
    written_off: Optional[str] = None
    tips: Optional[str] = None
    open: Optional[str] = None
    open_state: Optional[str] = None
    open_state_label: Optional[str] = None
    open_state_tone: Optional[str] = None
    next_payment: Optional[str] = None
    settled: bool = False
    #: **Erledigt** – abgeleitet (Saldo null, bei einer Ausfuhr mit Nachweis).
    done: bool = False
    ways: list[VoucherWay] = Field(default_factory=list)
    method_label: str = ""
    entries: list[VoucherEntryOut] = Field(default_factory=list)
    #: **Die Dokumente, so wie sie hinausgingen** – je eines mit Link.
    documents: list[VoucherDocumentOut] = Field(default_factory=list)


class VoucherUpdate(BaseModel):
    """**Eine Handlung am Beleg** – ein Endpunkt, eine Tabelle (``services/voucher.VERBS``).

    ``price``    die Positionen bepreisen (``lines``) – **gespeichert, nicht abgeschickt**
    ``party``    die Gegenpartei **wählen** (``party``) – wo die Definition niemanden
                 nennt; **nicht** dasselbe wie ``ask``
    ``ask``      anfragen bzw. anbieten (``parties`` – leer heisst: alle zugelassenen)
    ``unask``    eine Anfrage **zurückziehen** (``party``) – die Gegenhandlung zu ``ask``
    ``quote``    einen Preis an EINER Angebotszeile – auch von der Gegenpartei
    ``decline``  eine Angebotszeile absagen – auch von der Gegenpartei
    ``agree``    den **Zuschlag** geben (``party``)
    ``revoke``   stornieren – die eine Gegenhandlung
    ``correct``  sagen, **welchen Beleg dieser hier mindert** (``corrects``)
    ``bill``     **die** Rechnung stellen bzw. erfassen – es gibt genau eine
    ``accept``   eine abweichende Lieferantenrechnung **so annehmen** (``note``)
    ``pay``      eine **Zahlung** erfassen · ``refund`` erstatten · ``writeoff`` ausbuchen
                 (``reason``) · ``tip`` als Trinkgeld behalten · ``reverse`` falsch erfasst
                 (``entry``) · ``remind`` mahnen · ``export`` Ausfuhrnachweis
    ``release``  ein anstehendes Papier freigeben (``kind``)
    ``ownership`` Eigentum danach · ``terms`` Fristen und Gültigkeit
    ``currency`` · ``issuer`` · ``incoterm`` – nur vor der Zusage

    **Eine Gegenpartei trifft ausschliesslich ihre eigene Zeile**: ``party`` wird bei ihr
    **verworfen** und aus dem angemeldeten Benutzer gelesen. Wer die Regel erst an der Tür
    formulierte, hätte sie beim zweiten Aufrufer nicht.

    **Nur gesendete Felder wirken** (``exclude_unset``): ein Feld, das nicht mitkommt,
    bleibt, wie es war.
    """

    action: str
    #: ``release``: welches anstehende Papier (``confirmation`` · ``receipt``).
    kind: Optional[str] = None
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
    #: Welche **Karten-Zahlung** erstattet wird (``refund_online``).
    entry: Optional[int] = None
    #: Das **Rechnungsdatum** (``bill``) – vorbelegt mit heute.
    billed_on: Optional[date] = None
    #: ►►► **Welchen Beleg dieser hier mindert** (``correct``). ◄◄◄ Die **Id** eines
    #: Belegs, und er darf in einem **anderen Auftrag** stehen: die Gutschrift gehört
    #: dorthin, wo die Ware zurückkommt. ``null`` nimmt den Verweis zurück.
    corrects: Optional[int] = None
    #: **Die Positionen** (``price``) – je Zeile ihre Id und was sich ändert.
    lines: Optional[list[VoucherPrice]] = None
    #: **Der Steuersatz einer Forderung**, wo es keine bepreisten Positionen gibt (eine
    #: *Ausgabe*: die Steuer steht auf **seiner** Rechnung, und wir schreiben sie ab).
    vat: Optional[str] = None
    currency: Optional[str] = None
    method: Optional[str] = None
    #: Die Klausel der Lieferbedingung – der Ort folgt aus ihr und den Anschriften.
    incoterm: Optional[str] = None
    issuer: Optional[int] = None
    #: **An wen und wohin** (``address``) – nur Gesendetes wirkt; ``null`` heisst «der
    #: Standard» bzw. «die Vorgabe».
    bill_to_company: Optional[bool] = None
    billing_address: Optional[int] = None
    delivery_address: Optional[int] = None
    #: **Gültigkeit der Offerte** in Tagen (``terms``).
    valid_days: Optional[int] = None
    #: **Eigentum danach** (``ownership``): ``party`` · ``us``.
    ownership: Optional[str] = None
    #: Grund eines Stornos, einer angenommenen Abweichung (``revoke`` · ``accept``).
    #: (``note`` steht oben und trägt auch den Vermerk einer Zahlung.)
    #: Grund einer Ausbuchung (``writeoff``).
    reason: Optional[str] = None
    #: Die Geld-Zeile, die gegengebucht wird (``reverse``) – wie ``entry``.
    iban: Optional[str] = None
    #: **Das Dokument** (Dokumentnummer) – Lieferantenrechnung (``bill``) bzw.
    #: Ausfuhrnachweis (``export``).
    original: Optional[int] = None
    #: Ausgabe: die MWST-Nummer auf der Lieferantenrechnung (``bill``).
    party_uid: Optional[str] = None
    #: Der Link zur Bestellung (``quote``).
    link: Optional[str] = None

    def changes(self) -> dict[str, Any]:
        """Was tatsächlich gesendet wurde – ohne ``action``."""
        return self.model_dump(exclude={"action"}, exclude_unset=True)


class PaperOut(BaseModel):
    """Ein Papier, wie es hinausginge – Wort, Nummer, A4-HTML."""
    word: str
    number: Optional[str] = None
    html: str


class PapersOut(BaseModel):
    """Was eine Handlung hinausgäbe – leer, wenn sie kein Papier erzeugt."""
    papers: list[PaperOut] = Field(default_factory=list)
