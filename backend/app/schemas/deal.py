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
    #: ►►► **Wann diese Zeile hinausging** (Testnotiz #918). ◄◄◄ Die Chronik des Belegs
    #: fragt «wann wurde offeriert» – und das weiss nur der Moment, in dem es passiert.
    #: Als Datum an der **Zeile**, nicht als Spalte am Vorgang: der Angebotsspiegel ist
    #: eine Liste, und n Zeilen gehen nicht zwingend am selben Tag hinaus.
    sent_on: Optional[date] = None
    #: **Die Positionen dieser Offerte** – nur, wo **wir** den Preis nennen. Dort ist der
    #: Betrag ihre Brutto-Summe und keine zweite, getippte Zahl daneben.
    lines: list[dict[str, Any]] = Field(default_factory=list)


class VatRate(BaseModel):
    """Ein wählbarer Steuersatz – Schlüssel, Zahl, Name und sein Pflichtsatz.

    Ein **Katalog**, keine freie Zahl: ein getippter Satz ist einer, den es nicht gibt,
    und er fällt erst bei der Abrechnung auf.

    ►►► **Der Schlüssel ist die Identität, nicht die Zahl.** ◄◄◄ *Export* und
    *Reverse Charge* tragen beide 0 %, sind aber zwei verschiedene Rechtsgründe mit zwei
    verschiedenen Pflichtsätzen auf dem Beleg.
    """

    #: Die Katalogzeile – das ist der gespeicherte Wert («normal», «export», «reverse»).
    key: str
    #: Als **String** mit zwei Nachkommastellen («8.10») – so, wie auch gerechnet und
    #: verglichen wird; ein `float` wäre an genau dieser Stelle die falsche Zahl.
    rate: str
    label: str
    #: Der Satz, der bei diesem Tatbestand auf dem Beleg **stehen muss** – sonst ``None``.
    #: Er reist mit dem Satz, damit die Oberfläche ihn nicht selbst formuliert.
    note: Optional[str] = None


class IncotermOption(BaseModel):
    """Eine Incoterms-2020-Klausel – Kürzel, Name und der Satz, der sie erklärt.

    **Die Erklärung reist mit**, weil genau hier die Fragen entstehen: es ist die Stelle
    im Beleg, an der ein Kürzel über Tausende Franken entscheidet. Sie in der Oberfläche
    zu formulieren hiesse, sie beim nächsten Umbau ein zweites Mal zu schreiben.
    """

    key: str
    label: str
    hint: str


class CurrencyOption(BaseModel):
    """Eine wählbare Währung – der Code und wie sie heisst.

    Ein **Katalog**, keine freie Eingabe: «CHF» getippt ist noch keine Währung, und ein
    Tippfehler fällt erst auf, wenn jemand eine Summe über zwei Währungen zieht. Die
    Beschriftung trägt den Code selbst, kein Symbol – «$» ist nicht eindeutig.
    """

    code: str
    label: str


class IssuerOption(BaseModel):
    """Eine unserer Gesellschaften – Objektnummer und Name **mit Rechtsform**.

    Der Name kommt aus derselben Stelle wie der im Belegkopf (``sites.legal_name``): eine
    Auswahl, die anders schreibt als der Beleg, den sie erzeugt, ist eine zweite Schreibweise.
    """

    object_id: Optional[int] = None
    name: str = ""


class VatShare(BaseModel):
    """**Ein Steuersatz auf einem Beleg** – Netto und Steuer dazu.

    Gerundet **je Satz auf der Summe**, nie je Position aufsummiert (``domain/deal.
    vat_split``): bei zwölf Zeilen weicht die Summe der gerundeten Einzelbeträge sonst um
    Rappen ab, und eine MWST-Abrechnung kennt keine Rappen-Toleranz.
    """

    #: Die Katalogzeile. Bei einem Beleg von **vor** dieser Runde fehlt sie – dann sagt
    #: ``rate`` allein, was gemeint war (und «0.00» ist dort nicht mehr auflösbar).
    vat: Optional[str] = None
    rate: str
    #: Wie der Satz heisst – **eingefroren mitgeschrieben**, nicht zur Anzeige
    #: nachgeschlagen: ein gebuchter Beleg behält seine Bezeichnung, auch wenn der
    #: Katalog sich ändert.
    label: Optional[str] = None
    #: Der Pflichtsatz dieses Tatbestands, falls einer verlangt ist.
    note: Optional[str] = None
    net: str
    tax: str


class DealLine(BaseModel):
    """**Was gehandelt wird** – abgeleitet aus dem Prozess, nie getippt.

    Je Artikel, dessen Einzelinstanzen im Auftrag stehen, eine Zeile. Mehrere sind der
    Normalfall: EIN Vorgang mit zwei Positionen, wie im echten Leben.

    ►►► **Die Spezifikation reist NICHT mehr mit** (Testnotiz #916). ◄◄◄ Sie stand als
    aufklappbares Datenblatt an der Zeile – der Kompromiss «Spezifikation auf Klick».
    Auf einem **Beleg** ist sie das nicht: was der Empfänger braucht, steht in der
    Zeile; was er nicht braucht, gehört nicht auf das Papier. Was **daran** zu tun ist,
    steht bei dem Partner, den es betrifft (``DealQuote.ref``).

    Pflicht bleiben die beiden **Zoll-Angaben** – sie sind keine Beschreibung, sondern
    Voraussetzung der Ausfuhr; sie stehen darum offen an der Zeile (#915).
    """

    #: ``None`` bei einer Zeile **ohne Artikel** – dort, wo es gar keine Stücke gibt
    #: (Miete, Lohn, Gebühr). Derselbe Mechanismus mit einer entarteten Zeile.
    article_id: Optional[int] = None
    article_object_id: Optional[int] = None
    article_name: str = ""
    quantity: int
    #: ►►► **Zolltarifnummer und Ursprungsland – am BELEG, nicht nur am Artikel.** ◄◄◄
    #:
    #: Die Nummer ist eine Eigenschaft der **Sache**; welche auf *diesem* Beleg steht,
    #: ist eine Aussage **dieses Geschäfts** – dieselbe Beziehung wie beim Preis. Der
    #: Artikel liefert die **Vorbelegung**, der Beleg trägt den **Wert**, und mit der
    #: Zusage friert er ein (``agreed_lines``). Zurückgeschrieben wird nichts: ein Beleg
    #: korrigiert keine Stammdaten.
    hs_code: Optional[str] = None
    origin_country: Optional[str] = None
    #: ►►► **Der Einzelpreis – NETTO** (so denkt und rechnet man einen Preis). ◄◄◄
    #: ``None``, solange niemand ihn genannt hat. Als **String**: wo es auf den Rappen
    #: ankommt, wird nicht durch ``float`` gerechnet.
    price: Optional[str] = None
    #: **Der Steuersatz dieser Position** – der **Schlüssel** der Katalogzeile («normal»,
    #: «export»). Er hängt an der **Sache**: sechs Wellen zum Normalsatz und eine Ausfuhr
    #: zu 0 % stehen auf demselben Papier.
    vat: str = "normal"
    #: **Derselbe Satz als Prozentzahl** – damit eine Anzeige nicht «normal %» schreibt,
    #: weil sie den Schlüssel für eine Zahl hält. Eine zweite Auflösung im Browser wäre
    #: genau die Stelle, an der das passiert.
    vat_rate: str = "0.00"
    #: Wie er **heisst** («Normalsatz», «Export») – bei zwei Nullsätzen ist «0 %» keine
    #: Auskunft, sondern ein Rätsel.
    vat_label: str = ""
    #: ►►► **Der Pflichtsatz** dieses Tatbestands (MWSTG Art. 26). ◄◄◄ «Steuerfreie
    #: Ausfuhrlieferung» ↔ «Steuerschuldnerschaft des Leistungsempfängers» – zwei
    #: verschiedene Rechtsgründe, die beide 0 % ergeben; der Empfänger braucht den Grund
    #: für seine eigene Abrechnung. ``None``, wo keiner verlangt ist.
    vat_note: Optional[str] = None


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
    #: **Zoll-Angaben dieser Position** (Testnotiz #915). Leer heisst «nimm die des
    #: Artikels»; ein gesetzter Wert überschreibt ihn **auf diesem Beleg**.
    hs_code: Optional[str] = None
    origin_country: Optional[str] = None


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
    #: ►►► **Welche RECHNUNG diese Zahlung begleicht** (Testnotiz #858). ◄◄◄
    #:
    #: Eine Zahlung gehört zu genau einer Forderung – wer eine Überweisung über zwei
    #: Rechnungen hat, storniert sie und stellt eine gemeinsame. Hier steht nur die **Id**:
    #: die Nummer steht an der Rechnung, und die Karte hat die ganze Liste; sie ein zweites
    #: Mal mitzuschicken wäre dieselbe Angabe doppelt (dieselbe Bauart wie ``reverses``).
    #:
    #: ``None`` bei einer Forderung – und bei den Zahlungen, die es vor dieser Regel gab.
    charge_id: Optional[int] = None
    #: ►►► **Wie bezahlt wurde** – ``cash`` · ``transfer`` · ``card`` (Testnotiz #865).
    #: ``None`` heisst «nicht festgehalten», nicht «bar».
    method: Optional[str] = None
    #: Das Wort dazu – **eine** Auflösung, damit die Karte keine zweite Liste pflegt.
    method_label: Optional[str] = None
    #: ►►► **Wie die Gegenbuchung an DIESER Rechnung heisst** (Testnotiz #860). ◄◄◄
    #:
    #: «Stornieren», solange nichts geflossen ist – **«Gutschrift»**, sobald bezahlt
    #: wurde: *«wenn bezahlt wurde, dann kann ich ja quasi nicht mehr stornieren»*. Es ist
    #: dieselbe Buchung, und darum kein zweites Verb; nur das Wort hängt an der Zahl.
    reverse_word: Optional[str] = None
    #: **Was auf DIESER Rechnung noch offen ist** – nur bei einer Forderung. Die Zahlungen
    #: stehen als Gruppe darunter, und diese Zahl sagt, was davon fehlt.
    open: Optional[str] = None
    #: **Lässt sich diese Zahlung über den Dienst erstatten?** Nur eine Karten-Zahlung:
    #: bar und per Überweisung ist die Erstattung eine gewöhnliche negative Zahlung.
    refundable: bool = False
    #: ►►► **Kann man auf diese Rechnung überweisen?** (Testnotiz #865) ◄◄◄
    #:
    #: Nur, wo das Geld **zu uns** fliesst und noch etwas offen ist: der Einzahlungsschein
    #: trägt **unsere** Bankverbindung, und die eines Lieferanten steht nirgends bei uns.
    #: Die Antwort steht hier, damit die Oberfläche sie nicht aus der Richtung erschliesst –
    #: ein `if direction ===` wäre die erste Zeile, die beim nächsten Fall falsch liegt.
    transferable: bool = False


class DealMethod(BaseModel):
    """**Eine Zahlungsart, die ein Mensch erfassen darf** – Schlüssel und Wort.

    Dieselbe Bauart wie ``vat_rates`` und ``payment_terms``: die Liste kommt vom Server,
    damit die Karte keine zweite pflegt, die beim ersten neuen Weg auseinanderläuft.
    """

    key: str
    label: str


# ►►► **Eine Liste offener Rechnungen gibt es nicht mehr** (Testnotizen #859/#866). ◄◄◄
#
# Sie stand hier als ``DealOpenInvoice`` und füllte ein Auswahlfeld «auf welche Rechnung
# geht diese Zahlung?». Zwei Runden haben ihr den Boden entzogen: seit **#866** lebt je
# Modul höchstens eine Rechnung, und seit **#859** steht der Zahlungs-Knopf **an ihrer
# Zeile** – er nennt sie, statt danach zu fragen. Was auf jeder Rechnung offen ist, sagt
# ``DealEntryOut.open`` an der Zeile selbst.
#
# Ein Feld ohne Leser ist keine Reserve, sondern eine zweite Wahrheit, die niemand
# vergleicht.


class DealTerm(BaseModel):
    """Eine **übliche Frist** – die Zahl und wie sie heisst.

    «Vorauszahlung» ist ein Geschäftsbegriff, «0» eine Ziffer, die man erklären muss. Die
    Liste reist mit dem Vorgang (dieselbe Bauart wie ``vat_rates``), damit die Karte keine
    zweite pflegt.
    """

    days: int
    label: str


class DataGap(BaseModel):
    """►►► **Eine Angabe, die dieses Modul braucht und nicht findet.** ◄◄◄

    **Dieselbe Form wie ``StepNeed``, nur über einen anderen Gegenstand.** Der Verbrauch
    meldet fehlendes *Material*, hier fehlen *Stammdaten* – und die Regel ist dieselbe:
    es ist **kein Zustand**. Es gibt keinen Pausenwert und keine Sperre mit Schlüssel;
    das Modul ist schlicht nicht fertig, und diese Zeile sagt in Klartext, woran es liegt.

    **Was daraus folgt, entscheidet ein Mensch**: hingehen und eintragen. Darum trägt sie
    die **Objektnummer** des Datensatzes – die Zeile ist der Weg dorthin, nicht nur eine
    Meldung.

    Durchgesetzt wird sie über ``can``: fehlt etwas, führt es das Verb nicht, also gibt
    es den Knopf gar nicht – und die Tür weist an derselben Liste ab.
    """

    #: Wo die Angabe hingehört – klickbar. ``None``, wenn der Datensatz selbst fehlt.
    record_object_id: Optional[int] = None
    #: Wessen Angabe es ist: «Inexxio AG» · «Monika Fritsche».
    record_label: str = ""
    #: Was fehlt: «UID / MWST-Nummer» · «Anschrift» · «IBAN».
    field_label: str = ""
    #: **Ein Satz, warum dieser Beleg sie braucht.** Ohne ihn ist es eine Forderung ohne
    #: Grund, und der Mensch trägt irgendetwas ein, um weiterzukommen.
    why: str = ""


class DealSide(BaseModel):
    """**Eine Partei des Belegs** – so, wie sie auf einer Rechnung stehen muss.

    Name und Ort, wie im Geschäftsverkehr aufgetreten, und beim Aussteller die **UID mit
    dem Zusatz MWST** (MWSTG Art. 26): ohne sie kann dem Empfänger der Vorsteuerabzug
    verweigert werden.

    **Die Rolle steht im Wort, nicht in der Position**: `label` sagt «Lieferant» bzw.
    «Kunde», damit die Oberfläche für kein `if` nach der Richtung fragt. Welche Seite
    welche Rolle trägt, entscheidet `deal.document_head` an der einen Stelle, an der die
    Richtung ohnehin gelesen wird.

    **Fehlendes bleibt leer** – eine Anschrift, die es nicht gibt, ist `None`. Eine
    erfundene Zeile wäre auf einem Beleg schlimmer als eine leere; die Oberfläche sagt an
    der Stelle klein, was fehlt.
    """

    label: str
    #: ►►► **Was die Rolle bedeutet – in einem Satz.** ◄◄◄ «Leistungserbringer» und
    #: «Leistungsempfänger» sind die Begriffe des MWSTG und darum richtig; sie sind auch
    #: sperrig, und ein Fachbegriff ohne Erklärung ist eine Rückfrage mit Verzögerung.
    #: Er reist mit dem Wort, damit die Karte ihn nicht zum zweiten Mal formuliert.
    hint: str = ""
    #: Die Objektnummer – beim Partner die des Benutzers, bei uns die der Gesellschaft.
    object_id: Optional[int] = None
    name: str = ""
    #: ►►► **«z. H. …»** – die Person, an die der Beleg im Haus geht. ◄◄◄ Auf einer
    #: Rechnung ist der Schuldner die *Muster AG*; wer sie dort öffnet, steht darunter.
    #: ``None``, wo nur eines von beiden hinterlegt ist (der B2C-Fall).
    attn: Optional[str] = None
    #: ►►► **Ein Beleg ohne Kontaktweg löst die Rückfrage per Telefonbuch aus.** ◄◄◄
    #: Beides steht am Datensatz; es fehlte allein die Zeile auf dem Beleg.
    email: Optional[str] = None
    phone: Optional[str] = None
    #: Die Anschrift **als Zeilen**, wie sie auf dem Beleg steht (`address.lines`) – leer,
    #: wenn keine hinterlegt ist. Ein Satz Felder wäre hier eine zweite Adressenlogik im
    #: Browser; die Reihenfolge gehört dorthin, wo Adressen ohnehin gebaut werden.
    address: list[str] = Field(default_factory=list)
    #: ►►► **Beide Seiten können eine tragen** (Arbeitsauftrag §1.1). ◄◄◄ Hier stand
    #: «nur beim Aussteller – eine UID der Gegenpartei führt das System nicht», und das
    #: war schlicht falsch: ``uid_number``/``vat_number`` stehen seit dem Fundament am
    #: Benutzer. **Verlangt** ist sie beim Reverse Charge – ohne die Nummer des
    #: Leistungsempfängers trägt das Verfahren nicht.
    #:
    #: **Die Bankverbindung steht bewusst nicht daneben**: wohin überwiesen wird, sagt
    #: ``transfer_info`` an der Rechnung, die bezahlt werden soll – zusammen mit
    #: Referenz und QR-Code. Hier wäre sie dieselbe Angabe ein zweites Mal.
    uid: Optional[str] = None


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
    #: ►►► **Steht die eine Rechnung dieses Moduls schon?** (Testnotiz #866) ◄◄◄
    #:
    #: Dann ist die nächste Forderung nur noch eine **Gutschrift** – ``charge_word`` sagt
    #: es im Wort, dieses Feld sagt es der Oberfläche: der Knopf bleibt, er ist nur nicht
    #: mehr der Vorschlag. Zwei Formen einer Regel, gerechnet an **einer** Stelle
    #: (``deal.live_charge``); im Browser gerechnet wäre es die zweite Formel.
    credit_only: bool = False
    #: **Das dritte Geld-Wort**: «erfassen» heisst aufschreiben, was geschehen ist – dieses
    #: hier lässt es geschehen (``pay_online``). Ein Wort für beide wäre ein Knopf, dessen
    #: Wirkung man ihm nicht ansieht.
    pay_online_word: str = ""
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
    #: *Die **Vorbelegung** des früheren Eingabefeldes stand hier und ist mit ihm
    #: entfallen (Testnotiz #919). Das Leistungsdatum steht auf dem Beleg, wo es
    #: rechtlich zählt: an der **gebuchten Rechnung** (``DealEntryOut.service_date``).*
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
    # ►►► **Ein zweites Feld «gesperrt?» gibt es nicht** (Testnotizen #864/#866). ◄◄◄
    #
    # Hier stand ``currency_locked``, und daneben sollte ``share_locked`` entstehen: die
    # Frage «darf man das noch ändern?» ein zweites Mal, neben ``can``. Beide sind
    # entfallen – ``can`` ist **Auskunft und Tor**, und ein zweiter Wert daneben ist die
    # Stelle, an der Knopf und Tür beim nächsten Verb auseinanderlaufen.
    #
    # *Gemessen war es schon falsch: ``currency_locked`` hatte **keinen** Leser (die
    # Oberfläche fragte längst ``can``), und ``share_locked`` gab einer **Gegenpartei**
    # ein Eingabefeld für eine Zahl, die der Dienst ihr nie abnimmt.*
    #: Der Katalog, aus dem gewählt wird. Eine **Aufzählung**, kein Datensatz – ein
    #: natives Auswahlfeld ist hier richtig.
    currencies: list[CurrencyOption] = Field(default_factory=list)

    # ─── Wer den Beleg stellt (Testnotiz #905) ───────────────────────────────────
    #: Die Objektnummer **unserer** Gesellschaft – vorgewählt aus der des freigebenden
    #: Mitarbeiters, eingefroren am Vorgang. Sie steht auch im Belegkopf; hier steht sie
    #: als **Wahl**, damit die Oberfläche sie nicht aus dem Kopf zurückrechnet.
    issuer: Optional[int] = None
    issuer_label: str = ""
    #: Woraus gewählt wird – **nur für das Personal**: eine Gegenpartei wählt nicht aus,
    #: wer ihr eine Rechnung stellt.
    issuers: list[IssuerOption] = Field(default_factory=list)
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
    #: ►►► **Erst weiter, wenn bezahlt?** – eine ABLEITUNG, kein Schalter (#854). ◄◄◄
    #:
    #: Sie stand als dritte Angabe in der Modul-Definition und sagte, was die vereinbarte
    #: **Zahlungsfrist** ohnehin sagt: «zahlbar in null Tagen ab Zusage» *ist* die
    #: Vorauszahlung (``domain/deal.prepaid``). Zwei Angaben über eine Sache, an zwei Orten
    #: und zu zwei Zeitpunkten – und beim Widerspruch gewann der Schalter, obwohl auf dem
    #: Angebot die Frist steht.
    prepaid: bool = False
    #: ►►► **Die üblichen Fristen mit ihren Namen** (#854/#855/#856). ◄◄◄
    #:
    #: Eine Frist ist **eine Zahl in Tagen** – aber ihre zwei, drei üblichen Werte trägt
    #: niemand als Zahl im Kopf. Ein Schieberegler wäre hier falsch: eine Zahlungsfrist ist
    #: keine stufenlose Grösse, sondern eine Aufzählung mit einem freien Rest.
    payment_terms: list[DealTerm] = Field(default_factory=list)
    lead_terms: list[DealTerm] = Field(default_factory=list)
    #: Ab hier beginnt die freie Eingabe – **nicht bei 0**: die Null hat einen Namen, und
    #: zwei Wege zu einem Wert wären zwei Bedeutungen, von denen eine niemand kennt.
    term_free_min: int = 1
    term_free_label: str = ""
    payment_term_label: str = ""
    lead_term_label: str = ""
    #: Die **zugelassenen** Gegenparteien. Leer heisst frei – dann wird gesucht.
    allowed: list[DealParty] = Field(default_factory=list)
    #: **Der Angebotsspiegel** – je angefragter Gegenpartei eine Zeile.
    quotes: list[DealQuote] = Field(default_factory=list)
    #: **Worum es geht** – abgeleitet aus den Einzelinstanzen des Auftrags, mit der
    #: Spezifikation des Artikels. Nie getippt.
    lines: list[DealLine] = Field(default_factory=list)

    # ─── Der Belegkopf: die beiden Parteien ──────────────────────────────────────
    # ─── Die Lieferbedingung ─────────────────────────────────────────────────────
    #: Die gewählte Klausel («FCA») – ``None``, solange keine vereinbart ist.
    incoterm: Optional[str] = None
    #: Der benannte Ort. **Ohne ihn ist die Klausel keine Vereinbarung** – bei ``FCA``
    #: entscheidet genau er, wo das Risiko übergeht.
    incoterm_place: Optional[str] = None
    #: Der fertige Satz für den Beleg – «FCA Rorschach (Incoterms 2020)». **Vom Server**,
    #: damit er nicht im Browser ein zweites Mal zusammengesetzt wird.
    incoterm_text: Optional[str] = None
    incoterm_label: str = ""
    incoterm_place_label: str = ""
    incoterm_place_hint: str = ""
    #: Alle elf Klauseln mit ihrer Erklärung.
    incoterms: list[IncotermOption] = Field(default_factory=list)

    #: ►►► **Wer stellt den Beleg, und wer bekommt ihn** (MWSTG Art. 26). ◄◄◄
    #:
    #: Beide Seiten sind eine **Ableitung** aus Angaben, die es längst gibt (uns kennt
    #: `sites.find_operator`, den Partner `deal.billing_of`) – neu ist allein, welche
    #: Seite welche **Rolle** trägt, und das sagt die Richtung (`collects`). Sie stehen
    #: im Kopf des Belegs und werden von keiner Schicht wiederholt.
    supplier: Optional[DealSide] = None
    customer: Optional[DealSide] = None

    # ─── Was fehlt, um weiterzukommen ────────────────────────────────────────────
    #: ►►► **Die Lücken, die die nächste Handlung verhindern.** ◄◄◄
    #:
    #: Leer heisst: nichts fehlt. Sie stehen **neben** dem Weg nach vorn, nicht statt
    #: seiner – und sie erklären, warum ein Knopf nicht da ist. Ein fehlender Knopf ohne
    #: Grund ist die unangenehmste Form einer Regel.
    gaps: list[DataGap] = Field(default_factory=list)

    # ─── Die Zusage ──────────────────────────────────────────────────────────────
    party_object_id: Optional[int] = None
    party_name: Optional[str] = None
    #: **Was vereinbart ist** – nicht was gefordert und nicht was gezahlt ist.
    amount: Optional[str] = None
    due_days: Optional[int] = None
    agreed_on: Optional[date] = None
    #: ►►► **Wann storniert wurde** (Testnotiz #918). ◄◄◄ ``stage`` sagt **dass**, die
    #: Chronik des Belegs fragt nach dem **wann**. ``None`` heisst «nicht storniert».
    cancelled_on: Optional[date] = None
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
    # ─── Die Zahlungsarten und die dritte Bezahlart ──────────────────────────────
    # ►►► **Einen «Anteil» gibt es nicht** (Testnotiz #867). ◄◄◄ Hier standen ``share``,
    # ``share_label`` und ``share_hint`` – der Prozentsatz, den ein Vorgang von den
    # Positionen abrechnet. Er war als Komfort für die Anzahlung gedacht und war ein
    # Begriff zu viel; gebraucht wird er nicht: **wer den Preis nennt, nennt ihn je
    # Position**, und ein zweites Modul trägt schlicht seine eigenen Preise.
    #: **Womit ein Mensch bezahlen kann** – bar · Überweisung. Die Karte steht nicht darin:
    #: sie kommt über den Webhook, und von Hand wäre sie eine Behauptung ohne Beleg.
    methods: list[DealMethod] = Field(default_factory=list)
    method_label: str = ""
    #: Die drei Wörter der Geld-Zeile, die es vorher nicht gab.
    transfer_word: str = ""
    refund_word: str = ""
    refund_online_word: str = ""
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
    #: ►►► **Welche Rechnung eine Zahlung begleicht** (``pay``, Testnotiz #858). ◄◄◄
    #:
    #: Ohne Angabe: die **eine** offene Rechnung. Stehen mehrere offen, ist die Angabe
    #: Pflicht – eine Zahlung gehört zu genau einer, und wer eine Überweisung über zwei
    #: hat, storniert sie und stellt eine gemeinsame.
    charge_id: Optional[int] = None
    #: ►►► **Die Positionen eines Angebots** (``ask``/``quote``, nur wo **wir** den Preis
    #: nennen): je Zeile Preis und Steuersatz. Der Betrag ist ihre **Brutto-Summe** – eine
    #: getippte Zahl daneben wäre die zweite Aussage über dieselbe Sache.
    lines: Optional[list[DealPrice]] = None
    #: **Der Steuersatz einer Forderung**, wo es keine Positionen gibt (eine *Ausgabe*:
    #: die Steuer steht auf **seiner** Rechnung, und wir schreiben sie ab). Wo wir die
    #: Positionen preisen, kommt die Aufteilung aus ihnen und dieses Feld ist nichts.
    vat: Optional[str] = None
    #: *Das **Leistungsdatum** stand hier und ist entfallen (Testnotiz #919): es kommt
    #: aus dem Prozess (``deal.service_day``), und eine Eingabe daneben war die zweite
    #: Aussage über dieselbe Sache. Es steht weiterhin auf dem Beleg – als **Auskunft an
    #: der gebuchten Rechnung**, wo es rechtlich zählt.*
    #: ►►► **Die Währung des Vorgangs** (``currency``) – ISO 4217, drei Zeichen. ◄◄◄
    #: Nur **vor der Zusage**; danach führt ``can`` das Verb nicht mehr, und ``apply``
    #: weist es ab.
    currency: Optional[str] = None
    #: ►►► **Wie bezahlt wurde** (``pay``) – bar · Überweisung (Testnotiz #865). ◄◄◄ Die
    #: **Karte** weist der Dienst ab: sie entsteht beim Zahlungsdienst und kommt über den
    #: Webhook; von Hand erfasst wäre sie eine Behauptung ohne Beleg.
    method: Optional[str] = None
    #: ►►► **Die Lieferbedingung** (``incoterm``) – Klausel und benannter Ort. ◄◄◄
    #:
    #: Beide stehen hier, weil sie **eine** Vereinbarung sind: eine Klausel ohne Ort ist
    #: keine, und ein Ort ohne Klausel sagt nichts. *Und sie stehen hier überhaupt, weil
    #: Pydantic Unbekanntes **stillschweigend verwirft* – ein Feld, das die Tür nicht
    #: kennt, kommt nie an, und kein Dienst-Test findet das (die rufen ``apply`` direkt).
    incoterm: Optional[str] = None
    incoterm_place: Optional[str] = None
    #: ►►► **Welche unserer Gesellschaften den Beleg stellt** (``issuer``, #905). ◄◄◄
    #: Die Objektnummer; ``None`` heisst «der Betreiber». Nur vor der Zusage – danach
    #: führt ``can`` das Verb nicht mehr.
    issuer: Optional[int] = None

    def changes(self) -> dict[str, Any]:
        """Was tatsächlich gesendet wurde – ohne ``action``."""
        return self.model_dump(exclude={"action"}, exclude_unset=True)
