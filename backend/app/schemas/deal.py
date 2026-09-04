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


class DealQuote(BaseModel):
    """**Eine Zeile des Angebotsspiegels** – eine Gegenpartei, ein Preis.

    ``state``: ``angefragt`` · ``offeriert`` · ``abgelehnt`` · ``gewaehlt``. «gewählt»
    entsteht nicht durch Tippen, sondern dadurch, dass bei dieser Zeile zugesagt wurde –
    ein Zustand ist eine Folge.

    **Eine Gegenpartei sieht nur ihre eigene Zeile.** Fremde Preise fallen beim Aufbau
    der Antwort weg, nicht in der Oberfläche.
    """

    party_object_id: int
    party_name: str = ""
    #: ►►► **Was bei IHM zu tun ist** – seine Artikelnummer, sein Shop-Link oder ein
    #: Satz (``config.parties[].ref``, ``deal.TASK``). ◄◄◄
    #:
    #: Eine Eigenschaft der **Paarung** Modul × Partner – derselbe Lieferant führt je Teil
    #: eine andere Nummer –, in **beiden** Richtungen und **Pflicht**.
    ref: str = ""
    #: Als **String** – wo es auf den Rappen ankommt, wird nicht durch ``float`` gerechnet.
    amount: Optional[str] = None
    lead_days: Optional[int] = None
    payment_days: Optional[int] = None
    state: str = "angefragt"
    #: **Die Positionen dieser Offerte** – nur, wo **wir** den Preis nennen. Dort ist der
    #: Betrag ihre Brutto-Summe und keine zweite, getippte Zahl daneben.
    lines: list[dict[str, Any]] = Field(default_factory=list)


class VatRate(BaseModel):
    """Ein wählbarer Steuersatz – der Wert und wie er heisst.

    Ein **Katalog**, keine freie Zahl: ein getippter Satz ist einer, den es nicht gibt,
    und er fällt erst bei der Abrechnung auf.
    """

    #: Als **String** mit zwei Nachkommastellen («8.10») – so, wie er auch gespeichert
    #: und verglichen wird; ein `float` wäre an genau dieser Stelle die falsche Zahl.
    rate: str
    label: str


class CurrencyOption(BaseModel):
    """Eine wählbare Währung – der Code und wie sie heisst.

    Ein **Katalog**, keine freie Eingabe: «CHF» getippt ist noch keine Währung, und ein
    Tippfehler fällt erst auf, wenn jemand eine Summe über zwei Währungen zieht. Die
    Beschriftung trägt den Code selbst, kein Symbol – «$» ist nicht eindeutig.
    """

    code: str
    label: str


class VatShare(BaseModel):
    """**Ein Steuersatz auf einem Beleg** – Netto und Steuer dazu.

    Gerundet **je Satz auf der Summe**, nie je Position aufsummiert (``domain/deal.
    vat_split``): bei zwölf Zeilen weicht die Summe der gerundeten Einzelbeträge sonst um
    Rappen ab, und eine MWST-Abrechnung kennt keine Rappen-Toleranz.
    """

    rate: str
    net: str
    tax: str


class DealLine(BaseModel):
    """**Was gehandelt wird** – abgeleitet aus dem Prozess, nie getippt.

    Je Artikel, dessen Einzelinstanzen im Auftrag stehen, eine Zeile. Mehrere sind der
    Normalfall: EIN Vorgang mit zwei Positionen, wie im echten Leben.

    Die **Spezifikation reist mit** (``services/article_fields``) – sie beschreibt die
    Sache, damit der Partner weiss, worum es geht. Was **daran** zu tun ist, steht bei
    dem Partner, den es betrifft (``DealQuote.ref``).
    """

    #: ``None`` bei einer Zeile **ohne Artikel** – dort, wo es gar keine Stücke gibt
    #: (Miete, Lohn, Gebühr). Derselbe Mechanismus mit einer entarteten Zeile.
    article_id: Optional[int] = None
    article_object_id: Optional[int] = None
    article_name: str = ""
    quantity: int
    spec: list[dict[str, str]] = Field(default_factory=list)
    #: ►►► **Der Einzelpreis – NETTO** (so denkt und rechnet man einen Preis). ◄◄◄
    #: ``None``, solange niemand ihn genannt hat. Als **String**: wo es auf den Rappen
    #: ankommt, wird nicht durch ``float`` gerechnet.
    price: Optional[str] = None
    #: **Der Steuersatz dieser Position** («8.10»). Er hängt an der **Sache**: sechs Wellen
    #: zu 8.1 % und eine Ausfuhr zu 0 % stehen auf demselben Papier.
    vat: str = "8.10"


class DealPrice(BaseModel):
    """►►► **Eine Position, wie sie hereinkommt** – Artikel · Preis · Satz. ◄◄◄

    Die **Menge steht nicht darin**: sie ist die Zahl der Einzelinstanzen, die vor dem
    Modul stehen (``deal._priced`` liest sie aus dem Prozess). Eine getippte Menge wäre
    die zweite Aussage über dieselbe Sache – und die getippte gewinnt, auch wenn sie
    falsch ist.
    """

    #: ``None`` bei einer Zeile **ohne Artikel** – Miete, Lohn, Gebühr.
    article: Optional[int] = None
    #: **Netto**, als String: wo es auf den Rappen ankommt, wird nicht durch ``float``
    #: gerechnet, auch nicht auf dem Weg durch JSON.
    price: str = "0"
    #: Der Steuersatz dieser Position – **streng** geprüft (``deal.assert_vat``).
    vat: Optional[str] = None


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
    #: ►►► **Die eingefrorene Steuer-Aufteilung** dieses Belegs – ``[{rate, net, tax}]``.
    #:
    #: Leer bei einer **Zahlung**: Geld trägt keine Steuer, es begleicht sie. Gespeichert
    #: und nicht gerechnet, weil ein gebuchter Beleg seine Steuerangabe behält.
    vat: list[VatShare] = Field(default_factory=list)
    #: **Wann die Leistung erbracht wurde** (MWSTG Art. 26 Bst. c) – ``None`` = wie gebucht.
    service_date: Optional[date] = None
    #: ►►► **Welche Zeile diese hier storniert** – ``None`` bei einer gewöhnlichen. ◄◄◄
    #:
    #: Eine Stornierung ist eine **Gegenbuchung** (#823/#824): dieselbe Art, der negative
    #: Betrag. Ohne diesen Verweis stünde in der Liste eine zweite Zeile, die aussieht
    #: wie eine Gutschrift – und eine Gutschrift ist etwas ganz anderes als ein Storno.
    reverses: Optional[int] = None
    #: **Ist diese Zeile storniert?** Die Gegenrichtung derselben Angabe. Sie steht hier,
    #: weil die Oberfläche sie sonst über die ganze Liste selbst suchen müsste – und der
    #: Server kennt sie ohnehin, er stellt die Frage bereits für ``can``.
    reversed: bool = False


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
    #: Wie der Vorgang heisst: «Einnahme» ↔ «Ausgabe» (Testnotiz #831). Nicht «Verkauf»/
    #: «Einkauf»: dieses Modul kann auch Miete, Lohn, Gebühr und Spesen – ein Wort, das
    #: einen Kauf behauptet, ist **enger als das Modul**.
    label: str = ""
    #: **Wie der andere im Geschäft heisst** – in beiden Richtungen dasselbe Wort und in
    #: beiden Numeri (``deal.PARTY``). Es reist trotzdem mit, damit die Karte keine eigene
    #: Konstante daneben hält.
    party_word: str = ""
    charge_word: str = ""
    payment_word: str = ""
    open_word: str = "Offen"
    #: **Wie man auf die Gegenpartei zugeht**: «Anfragen» ↔ «Anbieten» – der eine Punkt,
    #: an dem die Richtung eine echte Handlung unterscheidet.
    ask_verb: str = ""
    #: ►►► **Nennen WIR den Preis?** (``Direction.quoted_by``, Testnotiz #837) ◄◄◄
    #:
    #: Daraus folgt die ganze Abfolge, und die Oberfläche braucht dafür kein `if` auf die
    #: Richtung: nennen wir ihn, wird der Betrag **vor** dem Anbieten gefragt und die
    #: Zeile geht als Offerte hinaus; nennt ihn die Gegenpartei, geht sie leer hinaus und
    #: wir warten.
    we_quote: bool = False
    #: ►►► **Wie das Nummernfeld heisst – EINES für Rechnung UND Zahlung** (#840/#850).
    #:
    #: ``None`` heisst «wir nummerieren», und dann gibt es **kein Feld** – an keiner der
    #: beiden Zeilen-Arten. Bei einer Einnahme trägt auch die Zahlung unsere Nummer (sie
    #: referenziert unsere Rechnung); zwei Regeln für dieselbe Frage liefen auseinander.
    ref_label: Optional[str] = None
    #: ►►► **Die Steuersätze, aus denen man wählt** – der Katalog, keine freie Zahl. ◄◄◄
    #:
    #: Ein getippter Satz ist ein Satz, den es nicht gibt, und er fällt erst bei der
    #: Abrechnung auf. Er reist mit, damit die Oberfläche keine zweite Liste pflegt.
    vat_rates: list[VatRate] = Field(default_factory=list)
    #: **Der Satz, mit dem eine neue Position beginnt** – die Vorgabe dieses Moduls.
    vat_rate: str = "8.10"
    #: Wie das Feld heisst, und wie das Leistungsdatum heisst – ein Wort für beide
    #: Richtungen, damit die Karte keine eigene Konstante daneben hält.
    vat_label: str = "MWST"
    service_date_label: str = "Leistungsdatum"
    #: ►►► **Wann die Leistung erbracht wurde – aus dem PROZESS** (Testnotiz #852). ◄◄◄
    #:
    #: Der Tag, an dem die Stücke dieses Modul erreicht haben. Das Rechnungsdatum ist es
    #: **nicht**: eine Rechnung, die zwei Wochen später geschrieben wird, verschöbe damit
    #: die Steuerperiode (MWSTG Art. 26 Bst. c). Es ist die **Vorbelegung** des Feldes,
    #: kein fester Wert – ein Mensch weiss von Teilleistungen, von denen der Log nichts
    #: weiss. ``None`` heisst «noch nichts angekommen»; dann gilt der Buchungstag.
    service_date: Optional[date] = None
    #: ►►► **Nennen WIR den Preis je Position?** ◄◄◄
    #:
    #: Es ist dieselbe Angabe wie ``we_quote`` – und genau darum steht sie nicht zweimal
    #: da: wer den Preis nennt, nennt ihn als **Positionen** (dort hängt der Steuersatz).
    #: Wo die Gegenpartei ihn nennt, steht die Steuer auf **ihrer** Rechnung.
    #: ─ Die drei Zahlen unter dem Strich, aus den Positionen abgeleitet. ─
    net: Optional[str] = None
    tax: Optional[str] = None
    #: Je vorkommendem Satz eine Zeile ``{rate, net, tax}`` – gerundet **je Satz auf der
    #: Summe**, nie je Position aufsummiert.
    vat_split: list[VatShare] = Field(default_factory=list)
    # ─── Die Währung ────────────────────────────────────────────────────────────
    #: ►►► **In welcher Währung?** – ISO 4217, drei Zeichen. ◄◄◄
    #:
    #: **Eine je Vorgang, nicht je Zeile**: zwei Währungen auf einem Beleg gibt es nicht,
    #: das wären zwei Belege. Jeder Betrag dieser Antwort ist in ihr zu lesen – ohne sie
    #: ist «1000» tausend Franken oder tausend Yen, und das sind zwei sehr verschiedene
    #: Beträge.
    currency: str = "CHF"
    #: Wie sie heisst («CHF · Schweizer Franken») – die Oberfläche pflegt keine
    #: zweite Liste.
    currency_label: str = "CHF"
    #: ►►► **Wie viele Nachkommastellen sie hat** (ISO 4217 «minor units»). ◄◄◄
    #:
    #: Fast alle haben zwei – und darum schreibt man `.toFixed(2)` und merkt nie, dass es
    #: falsch ist: **JPY** und **KRW** haben null, **KWD** hat drei. Die Zahl reist mit,
    #: damit die Anzeige nicht rät.
    currency_decimals: int = 2
    #: **Steht sie noch zur Wahl?** Ab der **Zusage** nicht mehr: draussen liegt eine
    #: Zusage über *diese* Summe in *dieser* Währung. Es ist dieselbe Antwort wie
    #: ``"currency" in can`` – hier als Wort, damit die Oberfläche das Feld **anzeigen**
    #: und trotzdem sperren kann, statt es verschwinden zu lassen.
    currency_locked: bool = True
    #: Der Katalog, aus dem gewählt wird. Eine **Aufzählung**, kein Datensatz – ein
    #: natives Auswahlfeld ist hier richtig.
    currencies: list[CurrencyOption] = Field(default_factory=list)
    #: Die Überschrift des Geld-Bereichs – der dritten Zeile der Karte.
    money_label: str = "Rechnung & Zahlung"
    #: Das Wort für die eine Gegenhandlung – oder ``None``, wo sie nicht geht.
    undo: Optional[str] = None

    # ─── Wo er steht, und was man tun darf ───────────────────────────────────────
    stage: str = "offer"
    #: Wie der aktuelle Zustand heisst – auch dort, wo er **keine Stufe** ist
    #: («Erledigt», «Storniert»). Sonst müsste die Oberfläche das Wort erfinden.
    stage_label: str = ""
    #: **Zwei** Stufen: nichts zugesagt · zugesagt. «Erledigt» und «Storniert» sind
    #: Ausgänge, keine Stufen – man kommt dort an, statt hindurchzugehen.
    stages: list[DealStage] = Field(default_factory=list)
    #: ►►► **Was hier JETZT möglich ist** (``services/deal.ACTIONS``). ◄◄◄
    #:
    #: Die Oberfläche rendert eine Aktion genau dann, wenn ihr Verb hier steht – und
    #: **dieselbe** Tabelle weist in ``apply`` ab. Wäre das nur ein Anzeige-Hinweis,
    #: liefen Knopf und Tür beim nächsten Verb auseinander.
    can: list[str] = Field(default_factory=list)

    # ─── Was in der Definition steht ─────────────────────────────────────────────
    #: **Erst weiter, wenn bezahlt?** Der einzige Schalter dieses Moduls.
    prepaid: bool = False
    #: Die **zugelassenen** Gegenparteien. Leer heisst frei – dann wird gesucht.
    allowed: list[DealParty] = Field(default_factory=list)
    #: **Der Angebotsspiegel** – je angefragter Gegenpartei eine Zeile.
    quotes: list[DealQuote] = Field(default_factory=list)
    #: **Worum es geht** – abgeleitet aus den Einzelinstanzen des Auftrags, mit der
    #: Spezifikation des Artikels. Nie getippt.
    lines: list[DealLine] = Field(default_factory=list)

    # ─── Die Zusage ──────────────────────────────────────────────────────────────
    party_object_id: Optional[int] = None
    party_name: Optional[str] = None
    #: **Was vereinbart ist** – nicht was gefordert und nicht was gezahlt ist.
    amount: Optional[str] = None
    due_days: Optional[int] = None
    agreed_on: Optional[date] = None
    #: ►►► **Wann er liefern wollte** – Zusagedatum + Lieferfrist. Eine **Ableitung**,
    #: keine Spalte; ohne vereinbarte Frist gibt es keinen Termin.
    due_date: Optional[date] = None
    #: **Termin vorbei und noch nicht erledigt** – dieselbe Form wie ``overdue`` bei einer
    #: Forderung. Ein Lieferverzug ist kein Zustand, den jemand pflegt.
    late: bool = False

    # ─── Forderung und Geld: lauter Ableitungen, keine Spalte ────────────────────
    charged: Optional[str] = None
    paid: Optional[str] = None
    #: **Forderungen − Zahlungen.** Darf negativ sein: dann schulden **wir**.
    open: Optional[str] = None
    #: **Zugesagt − berechnet** – und damit die Vorgabe der nächsten Rechnung. Die Zahl,
    #: die es ohne die Trennung der beiden Achsen gar nicht geben könnte.
    uncharged: Optional[str] = None
    #: ►►► **Die Vorgaben der nächsten Handlung — und sie sind NIE negativ.** ◄◄◄
    #:
    #: ``uncharged`` und ``open`` dürfen negativ sein (überberechnet bzw. überzahlt) –
    #: das ist eine gültige Aussage. Als **Vorschlag** in einem Eingabefeld ist sie es
    #: nicht: dort stand «−250.00», und niemand stellt eine Rechnung über minus 250
    #: (Testnotiz #795). ``None`` heisst «nichts vorzuschlagen», nicht «null» – und
    #: zugleich: diese Handlung ist gerade nicht die naheliegende.
    next_charge: Optional[str] = None
    next_payment: Optional[str] = None
    #: Ist bezahlt, was zugesagt wurde? Die eine Frage, die ``prepaid`` stellt – und
    #: sie fragt nach der **Zusage**, nicht nach dem offenen Betrag: wer nichts
    #: berechnet hat, hat null offen, und das hiesse sonst «bezahlt».
    settled: bool = False
    entries: list[DealEntryOut] = Field(default_factory=list)


class DealUpdate(BaseModel):
    """Eine Handlung am Geldvorgang – **ein** Endpunkt, neun Verben.

    ``ask``     die zugelassenen Gegenparteien anfragen bzw. ihnen anbieten
                (``parties`` – ohne Angabe **alle** zugelassenen)
    ``quote``   einen Preis an EINER Angebotszeile (``party``, ``amount``,
                ``lead_days``, ``payment_days``) – auch von der Gegenpartei
    ``decline`` eine Angebotszeile absagen (``party``) – auch von der Gegenpartei
    ``agree``   den **Zuschlag** geben (``party``; ``amount`` übersteuert die Offerte)
    ``revoke``  stornieren – **die** Gegenhandlung, ab der Schwelle
    ``charge``  eine **Forderung** buchen (``amount`` – Vorgabe ``next_charge``;
                ``booked_on``, ``due_on``, ``reference``, ``note``)
    ``pay``     eine **Zahlung** buchen (``amount`` – Vorgabe ``next_payment``)
    ``currency`` die **Währung** setzen (``currency``) – nur vor der Zusage
    ``reverse`` eine Geld-Zeile **stornieren** (``entry``) – als **Gegenbuchung**, nie
                als Löschung: dieselbe Art, der negative Betrag, ``reverses_id`` auf die
                stornierte Zeile. Beide bleiben stehen (Testnotizen #823/#824).

    **``charge`` und ``pay`` haben keine Stufe** – Geld fliesst, sobald zugesagt ist, und
    auch noch nach einem Storno; eine Anzahlung muss erstattet werden können. Sie stehen
    trotzdem in ``can``: «was darf ich hier tun» ist EINE Frage.

    **Eine Gegenpartei trifft ausschliesslich ihre eigene Zeile**: ``party`` wird bei ihr
    **verworfen** und aus dem angemeldeten Benutzer gelesen (``deal._target``). Wer die
    Regel erst an der Tür formulierte, hätte sie beim zweiten Aufrufer nicht.

    **Nur gesendete Felder wirken** (``exclude_unset``): ein Feld, das nicht mitkommt,
    bleibt, wie es war. Sonst löschte jeder Aufruf alles, was er nicht ausdrücklich
    wiederholt.
    """

    action: str
    #: Die Objektnummer der Gegenpartei, deren Zeile gemeint ist.
    party: Optional[int] = None
    #: Wen anfragen (``ask``). Leer heisst: **alle zugelassenen**.
    parties: list[int] = Field(default_factory=list)
    #: Die Lieferfrist einer Offerte – wie lange **er** braucht.
    lead_days: Optional[int] = None
    #: Die Zahlungsfrist einer Offerte – daraus kommt die Fälligkeit der Rechnung.
    payment_days: Optional[int] = None
    #: Als **String**, weil es ein Eingabefeld ist: ein halb getipptes Feld hat keine
    #: Zahl, und ein Komma ist ein Dezimaltrennzeichen, kein Fehler.
    amount: Optional[str] = None
    reference: Optional[str] = None
    note: Optional[str] = None
    booked_on: Optional[date] = None
    due_on: Optional[date] = None
    #: Welche Zeile storniert wird (``reverse``).
    entry: Optional[int] = None
    #: ►►► **Die Positionen eines Angebots** (``ask``/``quote``, nur wo **wir** den Preis
    #: nennen): je Zeile Preis und Steuersatz. Der Betrag ist ihre **Brutto-Summe** – eine
    #: getippte Zahl daneben wäre die zweite Aussage über dieselbe Sache.
    lines: Optional[list[DealPrice]] = None
    #: **Der Steuersatz einer Forderung**, wo es keine Positionen gibt (eine *Ausgabe*:
    #: die Steuer steht auf **seiner** Rechnung, und wir schreiben sie ab). Wo wir die
    #: Positionen preisen, kommt die Aufteilung aus ihnen und dieses Feld ist nichts.
    vat: Optional[str] = None
    #: ►►► **Wann die Leistung erbracht wurde** (MWSTG Art. 26 Bst. c). ◄◄◄ ``None``
    #: heisst «wie gebucht» – das ist der Normalfall und keine fehlende Angabe.
    service_date: Optional[date] = None
    #: ►►► **Die Währung des Vorgangs** (``currency``) – ISO 4217, drei Zeichen. ◄◄◄
    #: Nur **vor der Zusage**; danach führt ``can`` das Verb nicht mehr, und ``apply``
    #: weist es ab.
    currency: Optional[str] = None

    def changes(self) -> dict[str, Any]:
        """Was tatsächlich gesendet wurde – ohne ``action``."""
        return self.model_dump(exclude={"action"}, exclude_unset=True)
