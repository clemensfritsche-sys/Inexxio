"""**Die geschlossene Liste der Prozessschrittmodule — die eine Stelle.**

Ein Modul ist kein Freitext: sein Schlüssel steht hier, sein Übergang steht hier, und was
in seiner ``config`` stehen darf, entscheidet ebenfalls diese Datei. Ein Modultyp, den es
hier nicht gibt, ist nicht anlegbar — der Fehler kommt beim **Anlegen**, nicht erst, wenn
zur Laufzeit niemand weiss, was zu tun wäre.

**Der Übergang gehört zum Modul, nicht zum Anwender** (Vorgabe: «fest verdrahtet, nicht
einstellbar»). Ein Datenerfassungs-Modul *misst* – es verändert den Zustand des Stücks
nicht. Es wäre darum falsch, beim Anlegen zwei Status-Auswahlen anzubieten: die einzige
richtige Antwort stünde schon fest, und jede andere wäre ein Prozess, der nicht läuft.
Die Spalten ``status_before``/``status_after`` bleiben (sie sind der Mechanismus, §4) —
sie werden nur nicht mehr **gefragt**, sondern von hier gefüllt.

Das Testmodul ist **ersatzlos entfallen**. Es war ein Testvehikel für den Mechanismus;
den gibt es jetzt echt.
"""

from dataclasses import dataclass
from typing import Any, Optional

from fastapi import HTTPException

from . import capture_types, procurement, sampling, statuses as st

#: Der eine Ortsbedarf, den es heute gibt: **beim Produkt**. Eine geschlossene Liste
#: wie ``Aussondern.MODES`` – ein künftiges Modul («an meinem konfigurierten Ort»)
#: bekommt einen zweiten Wert, keine zweite Mechanik.
AT_PRODUCT = "product"

#: **Wann ein Modul einen Einkaufs-Beleg trägt** (``Module.buys``).
#:
#: ``BUY_ALWAYS``    das Modul existiert, **um** einzukaufen – der Beleg entsteht mit der
#:                   Freigabe und ist von Anfang an da (Beschaffen).
#: ``BUY_IF_CHOSEN`` das Modul kann seine Arbeit auch **selbst** erledigen – der Beleg
#:                   entsteht erst, wenn jemand «eingekauft» wählt (Bewegen). Genau
#:                   deshalb ist «gibt es einen Beleg?» zugleich die Antwort auf «wurde
#:                   das eingekauft?»: zwei Angaben könnten sich widersprechen, eine
#:                   abgeleitete kann es nicht.
BUY_ALWAYS = "always"
BUY_IF_CHOSEN = "if_chosen"

DATENERFASSUNG = "datenerfassung"
AUSSONDERN = "aussondern"
VERBRAUCH = "verbrauch"
BEWEGEN = "bewegen"
BESCHAFFEN = "beschaffen"
VERKAUF = "verkauf"


class Module:
    """Ein Modultyp. Was ihn ausmacht: sein Übergang und die Form seiner Konfiguration."""

    #: ►►►  OFFENE ENTSCHEIDUNG – Abweichungsauftrag §5  ◄◄◄
    #:
    #: **Darf ein Stück diesen Modultyp verlassen, während davor gearbeitet wird?**
    #:
    #: Eine **globale** Regel wäre entweder zu streng oder zu lasch, denn die Antwort
    #: hängt am Modul: eine **Datenerfassung** ist reversibel (was noch nicht bestätigt
    #: ist, existiert nirgends), ein künftiger **Einkauf** oder **Verkauf** hat
    #: Aussenwirkung – dort liegt eine Bestellung beim Lieferanten bzw. eine Rechnung
    #: beim Kunden, und ein stilles Herausnehmen wäre ein Beleg, der nicht mehr stimmt.
    #: Für solche Module ist das Verlassen kein Nebeneffekt, sondern ein eigener Vorgang
    #: (Storno / Teilstorno).
    #:
    #: Bis das entschieden ist, steht der Wert hier – **an genau einer Stelle** – und
    #: wird von ``process._assert_may_leave`` gelesen. Wer einen Modultyp mit
    #: Aussenwirkung anlegt, setzt ihn auf ``False`` und bekommt die Sperre geschenkt.
    units_may_leave: bool = True

    #: **Muss die Instanz vor der Eingabe verifiziert werden?** (Scan-Pflicht)
    #:
    #: Bevor jemand etwas mit einem Stück tut, muss feststehen, dass er **das richtige
    #: vor sich hat** – das Etikett klebt am physischen Ding. Die Regel ist darum global
    #: und steht hier nur, damit ein künftiger Modultyp ohne physischen Bezug (ein reiner
    #: Rechenschritt, eine Freigabe am Schreibtisch) sie abschalten kann, **ohne** dass
    #: die Ausführungsstelle eine Fallunterscheidung bekommt.
    requires_verification: bool = True

    #: **Wo muss das Material dieses Moduls liegen?** Vorgabe: nirgends.
    #:
    #: Der Ort ist im System ein Zeiger, den keine Regel liest (``services/places``) —
    #: bis ein Modul Material an einem bestimmten Ort *braucht*. Dann wird er zur
    #: **Voraussetzung**, und zwar nur dort.
    #:
    #: Die Antwort ist **abgeleitet, nicht konfiguriert**: ``AT_PRODUCT`` heisst «dort,
    #: wo mein Produkt liegt». Ein eigenes Ortsfeld am Modul wäre eine zweite Ortsangabe
    #: neben dem Ziel des Bewegen-Moduls, und zwei können sich widersprechen; so entsteht
    #: die Anforderung von selbst und niemand muss sie modellieren.
    #:
    #: **Nichtverfügbarkeit bleibt kein Zustand** (§9.6): «am falschen Ort» ist dieselbe
    #: Aussage wie «zu wenig da», eine Spalte weiter in ``StepNeed``. Das Modul ist
    #: schlicht nicht fertig.
    material_place: Optional[str] = None

    #: **Verlassen ALLE ankommenden Stücke den Auftrag hier?** Ein terminales Modul ist
    #: kein Durchgang, sondern ein **Ausgang**.
    #:
    #: Daraus folgt zweierlei, beides ohne Fallunterscheidung im Ablauf: hinter ihm kann
    #: kein Modul mehr stehen (es bekäme nie ein Stück – ``chain.assert_closes`` weist
    #: das bei der Freigabe ab), und es passiert **nicht** das Ende-Objekt (``_finish``),
    #: denn es ist selbst eines. Genau das schneidet auch eine geplante Rückführung ab:
    #: die Rückkehr hängt am Ende-Objekt, und dorthin kommt das Stück nie.
    #:
    #: **Das Wort beantwortet ausdrücklich nur die ALLE-Frage.** Beim Verbrauch geht
    #: nichts von dem hinaus, was **ankommt**: das Produkt läuft weiter, und die
    #: Komponenten kommen gar nicht von oben – sie treten an diesem Modul **ein** und
    #: verlassen es im selben Zug (``process._enter_at_step``). Er ist darum **nicht**
    #: terminal, und hinter ihm darf sehr wohl etwas stehen; die Kettenregel bleibt
    #: unangetastet, ohne eine Ausnahme zu brauchen.
    terminal: bool = False

    #: **Bewegt dieses Modul die Stücke?** Vorgabe: nein.
    #:
    #: Vorher beantwortete das die Transportart-Liste, indem sie bei jedem anderen
    #: Modultyp leer war – eine Liste als Bit. Seit die Transportart abgeleitet ist
    #: (siehe ``buys``), gibt es die Liste nicht mehr, also steht die Frage hier: ehrlich,
    #: als eine Zeile. Die Oberfläche fragt danach und nie nach dem Modultyp.
    moves: bool = False

    #: **Trägt dieses Modul einen Beleg – und wann?** ``None`` = nie.
    #:
    #: Der Beleg (``domain/procurement`` + ``services/purchase``) gehört keinem Modul; er
    #: hängt am **Schritt**. Ein Modul sagt hier nur, ob es einen bekommt. Damit ist eine
    #: Sendung kein zweites Konzept: sie ist derselbe Beleg an einem anderen Modul.
    buys: Optional[str] = None

    #: **In welche Richtung handelt dieses Modul?** ``buy`` · ``sell``
    #: (``domain/procurement.FLOWS``).
    #:
    #: Sie entscheidet, wie die Stufen heissen, wer die Gegenpartei ist und in welche
    #: Richtung das Geld fliesst – und sie wird beim Anlegen des Belegs **an ihn
    #: geschrieben**. Ein laufender Auftrag trägt seinen Prozess eingefroren; läse der
    #: Beleg die Richtung stattdessen bei jeder Anzeige aus dem Modultyp, änderte ein
    #: künftiger Umbau rückwirkend die Bedeutung alter Belege.
    #:
    #: Für ein Modul ohne ``buys`` ist sie bedeutungslos – aber nicht falsch: es fragt
    #: schlicht nie danach.
    direction: str = procurement.BUY

    @property
    def flow(self) -> procurement.Flow:
        """Der Vorgang dieses Moduls – Wörter, Gegenpartei, Verben. Eine Auflösung."""
        return procurement.of(self.direction)

    #: **Ist die Summe dieses Belegs der Preis der WARE?**
    #:
    #: Beim Einkauf ja – auch bei einer Leistung am Teil, denn die erhöht seine Kosten.
    #: Beim **Transport** nein: derselbe Artikel, zweimal verschickt, überschriebe seinen
    #: Einstandspreis mit dem Frachttarif. Das wäre ein stiller Datenfehler, mit dem
    #: danach kalkuliert wird – darum eine Deklaration und kein ``if module_type``.
    landed_cost: bool = False

    def __init__(self, key: str, label: str, status_before: str, status_after: str,
                 tone: str):
        self.key = key
        self.label = label
        self.status_before = status_before
        self.status_after = status_after
        #: **Die Farbfamilie dieses Modultyps** – ein Wort, das das Frontend auf seine
        #: Tokens abbildet (``lib/modules.MODULE_TONE``). Sie steht hier, weil sie zum
        #: Modul gehört und nicht zu einer Komponente: ein neuer Modultyp ist damit ein
        #: Eintrag in dieser Liste, kein Eingriff in die Oberfläche.
        #:
        #: **Getrennt von der Ampel** (grün/orange/rot): ein Modul ist kein Zustand und
        #: darf nicht wie einer aussehen (PROCESS_CORE.md §5.3).
        self.tone = tone

    def clean_config(self, raw: Optional[dict[str, Any]]) -> Optional[dict[str, Any]]:
        """Die Konfiguration prüfen und normalisieren. Ohne Konfiguration: ``None``."""
        return None

    #: Was der Knopf sagt, der dieses Modul ausführt. Ein Verb, kein Modulname – der
    #: steht schon auf der Karte.
    action: str = "Erfassen & bestätigen"

    def action_for(self, config: Optional[dict[str, Any]]) -> str:
        """Wie heisst die Ausführung dieses Moduls? Vorgabe: sein ``action``.

        Wie ``status_after_for`` darf ein Typ dabei seine Konfiguration lesen – beim
        Aussondern heisst der Knopf «Verschrotten» oder «Sperren», je nachdem, was
        passiert. Ein fester Text daneben wäre eine zweite Aussage über dieselbe Sache.
        """
        return self.action

    def status_after_for(self, config: Optional[dict[str, Any]]) -> str:
        """Auf welchen Zustand setzt dieses Modul ein Stück, das **weiterläuft**?

        Der Übergang gehört weiterhin zum Modultyp und nicht zum Anwender (§14) – aber
        der Typ darf seine eigene Konfiguration lesen. Das ist der Unterschied zwischen
        «welchen Status willst du?» (ein Dropdown, das man falsch ausfüllen kann) und
        «was soll passieren?» (eine fachliche Wahl, aus der der Status **folgt**).
        """
        return self.status_after

    def movement_for(self, config: Optional[dict[str, Any]], *,
                     target: Optional[int]) -> Optional["Move"]:
        """**Bringt dieses Modul die Stücke woandershin?** Vorgabe: nein.

        Eine Methode und eine Antwort. Die Ausführungsstelle bekommt damit entweder eine
        vollständige Absicht oder ``None`` – und braucht in keinem Fall zu wissen, welcher
        Modultyp vor ihr steht (dieselbe Bauart wie ``consumption.plan``).

        **Die Transportart ist hier entfallen.** Sie war die zweite Frage an derselben
        Stelle, und sie ist heute keine Eingabe mehr: eingekauft wurde genau dann, wenn
        es einen Beleg gibt (``buys``).
        """
        return None

    # ►►► **Was ein Einkaufs-Beleg beim DEFINIEREN braucht** ◄◄◄
    #
    # Beide Angaben gehören dem **Beleg**, nicht einem Modultyp – seit auch das
    # Bewegen-Modul einen tragen kann, stünden sie an der Beschaffen-Klasse schief. Sie
    # stehen darum hier, und der Unterschied zwischen den Modulen ist **nicht**, ob es
    # die Felder gibt, sondern ob sie **Pflicht** sind (Testnotiz #777).

    #: Der Schlüssel der zugelassenen Lieferanten in der Konfiguration.
    SUPPLIERS = "suppliers"
    #: Der Schlüssel des Auftrags an den Lieferanten.
    INSTRUCTION = "instruction"

    #: Wie lang eine Bestellangabe höchstens ist – eine Nummer oder eine URL.
    MAX_REF = 200
    #: Wie lang der Auftrag an den Lieferanten höchstens ist. Ein Satz, kein
    #: Pflichtenheft – wer mehr braucht, hängt ein Dokument an den Artikel.
    MAX_INSTRUCTION = 400
    #: Wie viele Lieferanten eine Freigabe höchstens nennt. Mehr ist keine Auswahl mehr,
    #: sondern eine Adressliste – und niemand fragt zwanzig Lieferanten je Schraube an.
    MAX_SUPPLIERS = 10

    #: ►►► **Was ein Beleg beim Definieren braucht — EIN Wert, DREI Stufen.** ◄◄◄
    #:
    #: Vorher standen hier zwei Booleans (``suppliers_required`` / ``instruction_
    #: required``). Zwei Booleans für zwei Felder ergeben vier Zustände, und **einer
    #: fehlte**: «es gibt das Feld hier gar nicht». Genau daraus wurde ein Feld, das
    #: freiwillig dastand, weil man es *vielleicht* braucht – mit einer Beschriftung, die
    #: nirgends passt («Auftrag an den Kundeen», Testnotizen #780/#781). Ein Feld als
    #: Vielleicht ist schlimmer als keines: es lädt zu einer Eingabe ein, die niemand
    #: liest.
    #:
    #: ``OFF``       gibt es hier nicht – der Editor rendert es nicht, der Dienst nimmt es
    #:               nicht entgegen.
    #: ``OPTIONAL``  darf stehen, muss nicht.
    #: ``REQUIRED``  ohne sie ist das Modul nicht anlegbar.
    OFF, OPTIONAL, REQUIRED = "off", "optional", "required"

    #: **Die zugelassenen Gegenparteien** (und mit ihnen die Bestellangabe ``ref``).
    #:
    #: ``REQUIRED`` nur dort, wo der Einkauf der **Zweck** ist: die Liste ist dann eine
    #: Freigabeentscheidung, die vorab fällt («für dieses Teil kommen diese drei in
    #: Frage»). Wo der Einkauf eine **Wahl** ist, entscheidet sich erst zur Laufzeit, ob
    #: überhaupt jemand beauftragt wird.
    parties: str = OPTIONAL

    #: **Der Auftrag an die Gegenpartei.**
    #:
    #: ``REQUIRED``, wo **nichts** ableitbar ist (Beschaffen: die Artikel-Spezifikation
    #: beschreibt die Sache, nicht den Auftrag). Wo ein Satz abgeleitet wird
    #: (``derived_instruction``), ist die Eingabe eine **Ergänzung**. Und ``OFF``, wo es
    #: ihn schlicht nicht gibt: ein Kunde tut nichts, er kauft.
    instruction: str = OPTIONAL

    def parties_of(self, config: Optional[dict[str, Any]]) -> list[dict[str, Any]]:
        """**Wer kommt für dieses Modul als Gegenpartei in Frage?** – die EINE Lesestelle.

        Sie hiess ``suppliers_of``, solange es nur den Einkauf gab. Beim **Verkauf** steht
        dort ein Kunde – und ein Name, der die halbe Wahrheit sagt, ist genau die Stelle,
        an der jemand später die falsche Regel schreibt. Der Schlüssel im JSONB heisst
        weiterhin ``supplier``: er steht in laufenden Aufträgen, und eine Umschrift wäre
        ein Risiko ohne einen einzigen neuen Leser (``models/purchase``).

        Sie liest **beide** Formen: die heutige (``{"supplier": …, "ref": …}``) und die
        alte, blosse Objektnummer. Ein Auftrag friert seinen Prozess bei der Freigabe
        ein – die alte Form steht also in laufenden Aufträgen und wird sie überleben.
        Tolerant lesen, streng schreiben.

        **Leer heisst frei, nicht «niemand».** Die Prüfung im Dienst (``_ask``) schränkt
        nur ein, wenn hier etwas steht – sonst wäre ein Modul ohne Liste eines, bei dem
        man nirgends anfragen kann.
        """
        out: list[dict[str, Any]] = []
        for entry in (config or {}).get(self.SUPPLIERS) or []:
            row = entry if isinstance(entry, dict) else {"supplier": entry}
            number = self._object_id(row.get("supplier"))
            if number is None:
                continue
            out.append({"supplier": number, "ref": str(row.get("ref") or "").strip()})
        return out

    def allowed_numbers(self, config: Optional[dict[str, Any]]) -> list[int]:
        """Nur die Objektnummern – dieselbe Liste, andere Form (für die Prüfungen)."""
        return [row["supplier"] for row in self.parties_of(config)]

    def derived_instruction(self, facts: Optional[dict[str, Any]] = None) -> str:
        """**Was weiss der Vorgang selbst schon?** Vorgabe: nichts.

        Beim **Bewegen** ist es «von A nach B» – Herkunft und Ziel stehen bereits fest,
        und wer sie abtippen müsste, könnte sie falsch abtippen. Genau darum bleibt
        dieser Teil abgeleitet und ist **kein** Eingabefeld.

        ``facts`` liefert der Dienst (Herkunft, Ziel); das Modul formuliert daraus. So
        bleibt die Regel im Modul und die Datenbank-Abfrage im Dienst.
        """
        return ""

    def instruction_for(self, config: Optional[dict[str, Any]], *,
                        facts: Optional[dict[str, Any]] = None) -> str:
        """**Was soll der Lieferant tun?** – abgeleitet **plus** das, was nur ein Mensch weiss.

        Beides in dieser Reihenfolge, an dieser einen Stelle. Der abgeleitete Teil sagt,
        *was* der Vorgang ist («Transport von Werk Nord nach Regal B»); die Ergänzung
        sagt, was daran besonders ist («Hebebühne nötig», «nur werktags») – und das kann
        kein System wissen.

        Vorher gab es dafür zwei Fassungen: Beschaffen nahm **nur** den getippten Satz,
        Bewegen **nur** den abgeleiteten und bot gar kein Feld an. Damit war der
        Transport-Beleg vordefiniert und sofort bestätigt, ohne dass jemand etwas
        hinzufügen konnte (Testnotiz #777). Eine Formel, zwei Summanden – wo einer leer
        ist, bleibt der andere übrig.
        """
        derived = self.derived_instruction(facts).strip()
        added = str((config or {}).get(self.INSTRUCTION) or "").strip()
        return " · ".join(part for part in (derived, added) if part)

    def clean_purchase_config(self, data: dict[str, Any]) -> dict[str, Any]:
        """Die beiden Beleg-Angaben prüfen – **einmal**, für jedes Modul, das einkauft.

        Ob es sie überhaupt gibt und ob sie Pflicht sind, sagen die Deklarationen
        (``parties`` / ``instruction``), nicht eine Abfrage nach dem Modultyp. Ein Modul,
        das gar nicht einkauft, ruft das hier nicht auf – und trägt die Felder folglich
        auch nicht mit sich herum.

        **``OFF`` heisst: gibt es hier nicht.** Der Wert wird dann verworfen statt
        gespeichert – ein Feld, das die Oberfläche nicht anbietet, aber der Dienst
        annimmt, wäre eine Hintertür zu einer Angabe, die niemand liest.
        """
        who = self.flow.party_word
        many = self.flow.party_plural
        suppliers = ([] if self.parties == self.OFF
                     else self._suppliers(data.get(self.SUPPLIERS)))
        if self.parties == self.REQUIRED and not suppliers:
            raise HTTPException(
                status_code=400,
                detail=(f"«{self.label}» braucht mindestens einen zugelassenen {many} – "
                        f"mit wem sonst sollte gehandelt werden?"),
            )
        instruction = ("" if self.instruction == self.OFF
                       else str(data.get(self.INSTRUCTION) or "").strip())
        if self.instruction == self.REQUIRED and not instruction:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"«{self.label}» braucht einen Satz, was der {who} tun soll – die "
                    f"Artikel-Spezifikation beschreibt die Sache, nicht den Auftrag "
                    f"(«Härten auf 58 HRC», «gemäss Zeichnung fertigen», «liefern»)."
                ),
            )
        if len(instruction) > self.MAX_INSTRUCTION:
            raise HTTPException(
                status_code=400,
                detail=f"Der Auftrag ist zu lang (max. {self.MAX_INSTRUCTION} Zeichen).",
            )
        return {self.SUPPLIERS: suppliers, self.INSTRUCTION: instruction}

    def _suppliers(self, value: Any) -> list[dict[str, Any]]:
        """Die Freigabe-Liste **streng** prüfen. Leer ist erlaubt – ob sie es sein darf,
        entscheidet ``parties``, nicht diese Funktion."""
        who = self.flow.party_word
        many = self.flow.party_plural
        if value in (None, ""):
            value = []
        if not isinstance(value, (list, tuple)):
            raise HTTPException(
                status_code=400,
                detail=f"«{self.label}» erwartet eine Liste zugelassener {many}.",
            )
        found: list[dict[str, Any]] = []
        for entry in value:
            row = entry if isinstance(entry, dict) else {"supplier": entry}
            number = self._object_id(row.get("supplier"))
            if number is None:
                raise HTTPException(
                    status_code=400,
                    detail=f"«{entry}» ist keine Objektnummer ({who}).",
                )
            if any(r["supplier"] == number for r in found):
                raise HTTPException(
                    status_code=400,
                    detail=(f"{who} {number} steht zweimal in der Freigabe – zweimal "
                            f"derselbe ist keine zweite Wahl."),
                )
            # ►►► **Die Bestellangabe gibt es nur, wo wir BESTELLEN.** ◄◄◄
            #
            # Sie beantwortet «wie bestelle ich bei ihm» – seine Artikelnummer, sein
            # Shop-Link. Beim **Verkauf** liefern wir; es gibt nichts nachzuschlagen, und
            # die Bestellnummer des Kunden entsteht zur Laufzeit, nicht beim Modellieren
            # (Testnotiz #787). Die Angabe hängt darum an der **Richtung**
            # (``Flow.party_ref``) und nicht am Modultyp: jeder künftige Typ derselben
            # Richtung erbt sie, ohne dass jemand hier etwas anfasst.
            #
            # Ein Wert, der ankommt, obwohl es das Feld nicht gibt, wird **verworfen** –
            # ein Feld, das die Oberfläche nicht anbietet, der Dienst aber annimmt, wäre
            # eine Hintertür zu einer Angabe, die niemand liest.
            ref = (str(row.get("ref") or "").strip() if self.flow.party_ref else "")
            # **Wo es sie gibt, ist sie Pflicht** (Testnotiz #756): ohne sie steht beim
            # Bestellen nicht da, unter welcher Nummer bzw. über welchen Link man bei
            # *ihm* bestellt – genau der Grund, warum die Angabe früher am Beleg landete,
            # wo man sie bei jedem Vorgang neu abschreiben musste. Gelesen wird weiterhin
            # tolerant: ein laufender Auftrag trägt seinen Prozess eingefroren.
            if self.flow.party_ref and not ref:
                raise HTTPException(
                    status_code=400,
                    detail=(f"{who} {number} braucht eine Bestellangabe – seine "
                            f"Artikelnummer oder den Link, unter dem man bei ihm "
                            f"bestellt."),
                )
            if len(ref) > self.MAX_REF:
                raise HTTPException(
                    status_code=400,
                    detail=f"Die Bestellangabe ist zu lang (max. {self.MAX_REF} Zeichen).",
                )
            found.append({"supplier": number, "ref": ref})
        if len(found) > self.MAX_SUPPLIERS:
            raise HTTPException(
                status_code=400,
                detail=f"Höchstens {self.MAX_SUPPLIERS} {many} je Modul.",
            )
        return found

    @staticmethod
    def _object_id(value: Any) -> Optional[int]:
        if value in (None, "", 0):
            return None
        try:
            number = int(value)
        except (TypeError, ValueError):
            return None
        return number if number > 0 else None

    def exit_status_for(self, config: Optional[dict[str, Any]]) -> Optional[str]:
        """Auf welchen Zustand setzt dieses Modul ein Stück, das **hier hinausgeht**?

        ``None`` heisst «hier geht niemand hinaus». Bei einem Ausgang ist es derselbe
        Wert wie ``status_after_for`` – dort gibt es kein Weiterlaufen, also auch keine
        zwei Zustände.
        """
        return self.status_after_for(config) if self.terminal else None


class Datenerfassung(Module):
    """Im Prozess laufend Daten erfassen und kontrollieren (Richtung Qualitätssicherung).

    **Durchläufer**: Vorher wie Nachher ``Im Prozess``. Es hält fest, was gemessen wurde,
    und rückt das Stück vor. Was aus einem «nicht bestanden» folgt, ist bewusst noch nicht
    entschieden (PROCESS_CORE.md §12.5) – bis dahin ist das Ergebnis eine **Aussage über
    die Messung**, kein Ereignis im Prozess. Ein erfundener Abzweig wäre schlimmer als
    keiner.
    """

    def clean_config(self, raw: Optional[dict[str, Any]]) -> dict[str, Any]:
        return {
            "points": capture_types.clean_points((raw or {}).get("points")),
            # **Wie viele der wartenden Stücke erfasst werden** (``domain/sampling``).
            # Ohne Angabe: alle. Die Regel steht in der Definition, gezogen wird sie zur
            # Laufzeit – vorher steht die Menge nicht fest.
            "sample": sampling.clean((raw or {}).get("sample")),
        }


class Aussondern(Module):
    """Einzelinstanzen **aus dem Verkehr ziehen** – verschrotten oder sperren.

    **Zwei Fälle, ein Modul.** Sie tun dasselbe: das Stück verlässt den Auftrag, die
    Reise endet hier. Der einzige Unterschied ist der Zielzustand – also ist es ein
    **Parameter**, kein zweites Modul. Zwei Module wären zwei Definitionen, zwei Karten,
    zwei Panels und zwei Stellen, an denen man dieselbe Regel pflegt.

    **Was ankommt, wird ausgesondert** – ohne Auswahl und ohne Stichprobe. Es gibt
    keinen Fall, in dem man «die Hälfte davon» verschrotten will: wer nur einen Teil
    meint, gibt nur diesen Teil in den Auftrag.

    **Der Grund ist Pflicht – und er wird beim MODELLIEREN gegeben**, nicht im laufenden
    Prozess. Warum an dieser Stelle ausgesondert wird, ist eine Eigenschaft des Ablaufs
    («Ausschuss aus der Sichtprüfung»), keine Frage an den Menschen am Band: dort steht
    dasselbe bei jedem Stück, und was jedes Mal gleich lautet, ist keine Erfassung,
    sondern eine Wiederholung. Ohne Grund ist das Modul **nicht anlegbar** – eine
    Aussonderung, deren Anlass in drei Monaten niemand mehr kennt, ist ein Loch im
    Nachweis.

    Er gilt für **beide** Ausprägungen: beim Sperren, weil sonst niemand weiss, ob man
    sie aufheben darf; beim Verschrotten, weil das endgültig ist und die Frage «warum»
    dann gar nicht mehr gestellt werden kann.
    """

    #: Die beiden Ausprägungen – und der Zustand, auf den jede setzt. Die Zuordnung steht
    #: hier und nirgends sonst; die Oberfläche fragt danach, statt sie nachzubauen.
    MODES: dict[str, str] = {"scrap": st.VERSCHROTTET, "block": st.GESPERRT}
    DEFAULT_MODE = "scrap"

    terminal = True

    #: Wie lang der Grund höchstens sein darf. Ein Satz, kein Aufsatz.
    REASON_MAX = 200

    #: Das Verb je Ausprägung – dieselbe Zuordnung wie ``MODES``, andere Spalte.
    ACTIONS: dict[str, str] = {"scrap": "Verschrotten", "block": "Sperren"}

    def clean_config(self, raw: Optional[dict[str, Any]]) -> dict[str, Any]:
        mode = ((raw or {}).get("mode") or self.DEFAULT_MODE)
        if mode not in self.MODES:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"«{mode}» ist keine Aussonderungs-Art. Erlaubt: "
                    + ", ".join(self.MODES) + "."
                ),
            )
        reason = str((raw or {}).get("reason") or "").strip()
        if not reason:
            raise HTTPException(
                status_code=400,
                detail=(
                    "«Aussondern» braucht einen Grund – ohne ihn steht später da, dass "
                    "Stücke ausgesondert wurden, aber nicht warum."
                ),
            )
        if len(reason) > self.REASON_MAX:
            raise HTTPException(
                status_code=400,
                detail=f"Der Grund ist zu lang (max. {self.REASON_MAX} Zeichen).",
            )
        # **Keine Erfassungspunkte.** Was ankommt, wird ausgesondert; der Scan ist die
        # Bestätigung, und der Grund steht bereits in der Definition. Ein Feld, das am
        # Band bei jedem Stück dasselbe aufnimmt, wäre eine Erfassung ohne Erkenntnis.
        return {"mode": mode, "reason": reason, "points": [],
                "sample": dict(sampling.DEFAULT)}

    def _mode(self, config: Optional[dict[str, Any]]) -> str:
        return (config or {}).get("mode") or self.DEFAULT_MODE

    def status_after_for(self, config: Optional[dict[str, Any]]) -> str:
        return self.MODES[self._mode(config)]

    def action_for(self, config: Optional[dict[str, Any]]) -> str:
        return self.ACTIONS[self._mode(config)]


class Verbrauch(Module):
    """Einzelinstanzen **in ein anderes Stück einbauen** – der Zwilling des Aussonderns.

    Beide sind Ausgänge aus dem Kreislauf, und sie unterscheiden sich in genau einer
    Sache: **was aus dem Stück geworden ist.** Verschrottet heisst «gibt es nicht mehr»,
    verbaut heisst «steckt jetzt in etwas anderem». Der Mechanismus ist derselbe.

    **Der Unterschied zum Aussondern ist die Herkunft.** Dort geht hinaus, was **ankommt**;
    hier kommt gar nichts an, was ginge: das Produkt läuft weiter, und die Komponenten
    **treten hier ein** (``process._enter_at_step``) und verlassen den Auftrag im selben
    Zug. Darum ist dieses Modul **nicht** ``terminal``: hinter ihm darf etwas stehen, und
    die Kettenregel bleibt unangetastet.

    **Gebunden wird beim Erreichen, nicht bei der Freigabe.** Eine Komponente, die einem
    Auftrag schon bei der Freigabe gehört, ist wochenlang für jeden anderen gesperrt,
    obwohl sie im Regal liegt – und wer sie braucht, sieht einen Bestand, den es
    rechnerisch nicht gibt. Der Statusweg lautet darum
    ``Freigegeben`` → (Scan) → ``Im Prozess`` → (Bestätigen) → ``Verbaut``, und beide
    Übergänge stehen als eigene Einträge im Log.

    **Kein Standort, keine Reservierung, keine Stückliste als Tabelle.** Das
    Vorgängermodul («Ressource») ruhte auf einem Mengenmodell mit Reservierung,
    Teilentnahme und FIFO-mit-Rest; im Einzelinstanz-Modell fällt das alles weg – ein
    Stück ist ein Stück. Aus einer 600er-Charge gehen vier Einzelinstanzen auf
    ``Verbaut``, 596 bleiben stehen.

    **Und die Stückliste ist eine Ableitung** (``services/genealogy``): welche Stücke
    denselben Auftrag als ``Verbaut`` verlassen haben, und laut Log **in welches Stück**.
    Kein Feld, keine Beziehung – und weil sie aus dem Log kommt, überlebt sie eine
    spätere Demontage.
    """

    #: Was die Konfiguration trägt: je Zeile **Artikel + Menge pro Einzelinstanz**. Die
    #: Objektnummer und nicht der interne Schlüssel – es ist dasselbe, was die Oberfläche
    #: zeigt und was über die API reist.
    #:
    #: **Die Menge gilt je Produkt-Stück**, nicht je Auftrag: «4× Schraube M6» heisst vier
    #: Schrauben *pro Getriebe*. Gerechnet wird beim **Erreichen** des Moduls (dort steht
    #: fest, wie viele Stücke davorstehen), nicht beim Definieren – eine Vorlage, die eine
    #: Auftragsmenge nennt, wäre bei der zweiten Menge falsch.
    LINES = "lines"

    #: Höchstmenge je Zeile. Eine Stückliste nennt Stückzahlen, keine Chargen; wer 5000
    #: Schrauben je Produkt braucht, hat einen Tippfehler oder das falsche Modul.
    MAX_PER_UNIT = 1000

    #: Das Verb auf dem Knopf. «Erfassen & bestätigen» wäre hier schlicht falsch – erfasst
    #: wird nichts, der Scan ist die Bestätigung.
    action = "Verbauen"

    #: **Die Komponenten müssen dort liegen, wo das Produkt liegt.** Sonst kann niemand
    #: sie verbauen – und der Prozess arbeitete mit Material, das gar nicht da ist.
    material_place = AT_PRODUCT

    def clean_config(self, raw: Optional[dict[str, Any]]) -> dict[str, Any]:
        found = (raw or {}).get(self.LINES) or []
        if not isinstance(found, (list, tuple)):
            raise HTTPException(
                status_code=400,
                detail="«Verbrauch» erwartet eine Liste aus Artikel und Menge.",
            )
        lines: list[dict[str, int]] = []
        seen: set[int] = set()
        for row in found:
            article, quantity = self._one(row)
            if article in seen:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Artikel {article} steht zweimal in der Stückliste. Zwei Zeilen "
                        f"für denselben Artikel sind eine Menge, die man addieren muss – "
                        f"und zwei Stellen, an denen sie auseinanderlaufen kann."
                    ),
                )
            seen.add(article)
            lines.append({"article": article, "quantity": quantity})
        if not lines:
            raise HTTPException(
                status_code=400,
                detail=(
                    "«Verbrauch» braucht mindestens eine Zeile – sonst gibt es nichts zu "
                    "verbauen, und das Modul wäre ein Durchgang, der so aussieht wie "
                    "eine Montage."
                ),
            )
        # **Keine Erfassungspunkte, keine Stichprobe.** Was gebraucht wird, wird verbaut;
        # der Scan ist die Bestätigung. Eine Stichprobe hiesse «bau die Hälfte ein» – das
        # gibt es nicht.
        return {self.LINES: lines, "points": [], "sample": dict(sampling.DEFAULT)}

    @staticmethod
    def _one(row: Any) -> tuple[int, int]:
        """Eine Zeile prüfen: **Artikel + Menge pro Stück**, beide Pflicht."""
        if not isinstance(row, dict):
            raise HTTPException(
                status_code=400,
                detail=f"«{row}» ist keine Stücklisten-Zeile (Artikel und Menge).",
            )
        try:
            article = int(row.get("article"))
        except (TypeError, ValueError):
            raise HTTPException(
                status_code=400,
                detail=f"«{row.get('article')}» ist keine Artikel-Objektnummer.",
            )
        try:
            quantity = int(row.get("quantity"))
        except (TypeError, ValueError):
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Artikel {article}: die Menge fehlt. Sie gilt **pro Einzelinstanz** – "
                    f"«4» heisst vier Stück je Produkt, nicht vier im ganzen Auftrag."
                ),
            )
        if not 1 <= quantity <= Verbrauch.MAX_PER_UNIT:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Artikel {article}: die Menge muss zwischen 1 und "
                    f"{Verbrauch.MAX_PER_UNIT} liegen."
                ),
            )
        return article, quantity

    def exit_status_for(self, config: Optional[dict[str, Any]]) -> Optional[str]:
        """Der Zustand der **Komponenten**, die dieses Modul zieht.

        Nicht der der ankommenden Stücke: die laufen weiter (``status_after``). Das ist
        der ganze Unterschied zum Aussondern – dort ist beides dasselbe, weil dort nichts
        weiterläuft.
        """
        return st.VERBAUT


@dataclass(frozen=True)
class Move:
    """Was ein Modul am Ort ändern will: **wohin**.

    Das «womit» stand hier einmal daneben. Es ist entfallen, weil es keine zweite Angabe
    ist: eingekauft wurde genau dann, wenn es einen Beleg gibt (``Module.buys``).
    """

    target: int


class Bewegen(Module):
    """Einzelinstanzen an einen **Halter** bringen (``services/places``).

    **Ein Durchläufer**: vorher wie nachher ``Im Prozess``. Ein Ort ist kein Zustand – er
    ändert nie den Status und nie die Zugehörigkeit. Genau deshalb muss keine andere Regel
    im System von diesem Modul wissen, und genau deshalb ist es das einfachste von allen.

    **Das Ziel ist optional.** Steht es in der Definition, ist der Ziel-Scan eine
    **Verifikation** dagegen – eine andere Nummer wird abgewiesen, hier und nicht nur im
    Dialog. Fehlt es, wählt der Ausführende zur Laufzeit; das ist der Fall «bring es
    dorthin, wo gerade Platz ist», den eine Vorlage nicht vorwegnehmen kann. Beide Fälle
    sind gültig, aber sie müssen **sichtbar** verschieden sein: ein offenes Ziel darf
    nicht wie ein vergessenes aussehen (``ModuleFacts.target``).

    **Selbst gebracht oder eingekauft – das ist EIN Bit, und es ist abgeleitet.** Beim
    Modellieren weiss niemand, ob das Stück nebenan liegt oder in Werk Nord; die Frage
    gehört darum zur **Laufzeit**. Wer sie mit «eingekauft» beantwortet, bekommt einen
    ganz gewöhnlichen **Einkaufs-Beleg** (``buys = BUY_IF_CHOSEN``) – dieselben drei
    Stufen, dieselben Verben, dieselbe Oberfläche wie beim Beschaffen. Denn eine Sendung
    aufzugeben IST ein Einkauf: der Spediteur ist ein Lieferant, der Tarifvergleich ist
    der Angebotsspiegel, die Sendungsnummer ist ``tracking``.

    Die Antwort auf «wurde das eingekauft?» ist damit **«gibt es einen Beleg?»** – und
    kann der Wirklichkeit nicht widersprechen. Die frühere Liste ``manuell · paket ·
    fracht`` (mit einem ``available``-Flag als Roadmap) ist ersatzlos entfallen: *Paket*
    und *Fracht* sind keine zwei Arten, sondern zwei **Angebote** desselben Einkaufs –
    das entscheidet der Tarif, nicht der Modellierer. Ein Roboter, der es fährt, ist
    «selbst»: unser Gerät, keine Rechnung.

    **Und der Ziel-Scan schliesst den Beleg.** Ankunft und Ablage sind ein Ereignis, also
    eine Bestätigung: ``assert_receivable`` lässt vorher nichts eintreffen, ``note_receipt``
    setzt danach die letzte Stufe. Beide fragen nur, ob es zu diesem Schritt einen Beleg
    gibt – sie mussten dafür **nicht angefasst** werden.

    **Geprüft wird hier nur die FORM** (eine Objektnummer), nicht die Existenz: diese
    Stelle hat keine Datenbanksitzung. Dass es den Halter gibt und dass er keinen Kreis
    bildet, weist ``places.assert_placeable`` bei der Ausführung ab – streng schreiben,
    tolerant lesen.
    """

    #: Der Schlüssel der einen Einstellung. ``None`` heisst «wird beim Ausführen gewählt».
    TARGET = "target"

    #: Es bewegt – daraus folgt in der Oberfläche der Ziel-Scan.
    moves = True

    #: Es **kann** einkaufen: ein Transport wird eingekauft oder selbst erledigt.
    buys = BUY_IF_CHOSEN

    #: Aber sein Preis ist **nicht** der Preis der Ware: derselbe Artikel, zweimal
    #: verschickt, überschriebe seinen Einstandspreis mit dem Frachttarif.
    landed_cost = False

    #: Was der Knopf sagt. **«Bestätigen», nicht «scannen»**: gescannt ist zu diesem
    #: Zeitpunkt längst – Ware und Zielort –, und was der Knopf auslöst, ist die Buchung
    #: der Ablage. Ein Verb, das den vorherigen Schritt benennt, beschreibt nicht, was
    #: passiert (Testnotiz #733).
    action: str = "Bewegung bestätigen"

    def clean_config(self, raw: Optional[dict[str, Any]]) -> dict[str, Any]:
        data = raw or {}
        target = self._as_object_id(data.get(self.TARGET))
        # ►► **Auch dieses Modul kann einkaufen – also trägt es dieselben Beleg-Angaben.**
        #
        # Beide sind hier **freiwillig** (die Deklarationen oben): welcher Spediteur
        # fährt, entscheidet sich zur Laufzeit, und *was* zu tun ist, steht schon im
        # abgeleiteten Satz. Dass die Felder trotzdem da sind, ist der Punkt: «wir fahren
        # nur mit diesen drei Speditionen» und «Hebebühne nötig» sind echte Angaben, und
        # sie gehören dorthin, wo auch das Beschaffen-Modul sie hat (Testnotiz #777).
        #
        # Keine Erfassungspunkte und keine Stichprobe: bewegt wird, was ankommt. Die
        # Felder stehen trotzdem, damit jede Lesestelle dieselbe Form vorfindet.
        return {self.TARGET: target, **self.clean_purchase_config(data),
                "points": [], "sample": dict(sampling.DEFAULT)}

    @staticmethod
    def _as_object_id(value: Any) -> Optional[int]:
        """Eine Objektnummer – oder ``None``. Alles andere ist ein Fehler mit Namen."""
        if value in (None, "", 0):
            return None
        try:
            number = int(value)
        except (TypeError, ValueError):
            raise HTTPException(
                status_code=400,
                detail=(f"«{value}» ist keine Objektnummer. Das Ziel von «Bewegen» ist "
                        f"ein Regal, eine Person oder ein Unternehmen – oder es bleibt "
                        f"leer und wird beim Ausführen gewählt."),
            )
        if number <= 0:
            raise HTTPException(status_code=400, detail="Eine Objektnummer ist positiv.")
        return number

    def movement_for(self, config: Optional[dict[str, Any]], *,
                     target: Optional[int]) -> Move:
        """Wohin geht es – und ist das mit der Definition vereinbar?"""
        planned = (config or {}).get(self.TARGET)
        scanned = self._as_object_id(target)
        if planned and scanned and int(scanned) != int(planned):
            raise HTTPException(
                status_code=400,
                detail=(f"Dieses Modul bringt die Stücke zu {planned}, gescannt wurde "
                        f"{scanned}. Wer woanders hinlegt, ändert den Ablauf – dafür gibt "
                        f"es den Abweichungsauftrag, nicht den Scanner."),
            )
        goal = planned or scanned
        if not goal:
            raise HTTPException(
                status_code=400,
                detail=("Dieses Modul hat kein festes Ziel – ohne gescannten Zielort "
                        "steht nicht fest, wohin die Stücke gebracht wurden."),
            )
        return Move(target=int(goal))

    def derived_instruction(self, facts: Optional[dict[str, Any]] = None) -> str:
        """**«von A nach B»** – abgeleitet, nie getippt.

        Beide Hälften stehen bereits fest: die Herkunft ist der heutige Halter der
        Stücke, das Ziel ist das Ziel dieses Moduls. Ein Eingabefeld **für diesen Satz**
        wäre eine zweite Aussage über dieselbe Sache – und die getippte gewinnt auch
        dann, wenn sie falsch ist. Das bleibt so.

        Was daneben eingegeben werden **darf**, ist etwas anderes: was nur ein Mensch
        weiss («Hebebühne nötig», «nur werktags»). Das hängt der Rahmen an
        (``Module.instruction_for``) – hier steht ausschliesslich das Ableitbare.

        Was nicht bekannt ist, wird **weggelassen** statt geraten: liegen die Stücke
        nirgends (ein frisch erzeugtes Stück liegt nirgends, §9.8), heisst es schlicht
        «Transport nach ‹Ziel›».
        """
        where = (facts or {}).get("from")
        goal = (facts or {}).get("to")
        if not goal:
            return "Transport"
        return f"Transport von {where} nach {goal}" if where else f"Transport nach {goal}"


class Handel(Module):
    """**Ein Modul, dessen Zweck ein Beleg ist** – die gemeinsame Hälfte von Ein- und Verkauf.

    Beide sind ein **Tor nach draussen**: alle anderen Module tun etwas *mit* der
    Einzelinstanz – sie messen, bewegen, sondern aus, verbauen. Diese hier halten sie auf,
    bis eine zweite Partei ihren Teil getan hat. Und beide erzeugen **nichts**:
    Einzelinstanzen entstehen ausschliesslich bei der Freigabe eines Erzeugungsauftrags.

    Was sie unterscheidet, ist die **Richtung** (``Module.direction``) – und die steht als
    Daten im ``Flow``, nicht als Verzweigung. Was hier steht, gilt darum für beide:

    * Der Beleg entsteht mit der Freigabe (``BUY_ALWAYS``) – er ist der Zweck, keine Option.
    * Der Knopf des Moduls trägt das Verb der **Schwellen-Stufe**: was das Modul
      abschliesst, ist genau das, was der Beleg an seiner zweiten Stufe zu tun hat
      («Wareneingang buchen» ↔ «Lieferung buchen»). Zwei Literale wären zwei Wörter für
      dieselbe Handlung, und das zweite ändert irgendwann jemand allein.
    * Erfasst wird nichts, gezogen wird nichts: der Scan ist die Bestätigung.
    """

    buys = BUY_ALWAYS

    def action_for(self, config: Optional[dict[str, Any]]) -> str:
        return self.flow.stage_verbs[procurement.BINDING]

    def clean_config(self, raw: Optional[dict[str, Any]]) -> dict[str, Any]:
        # Ob die beiden Beleg-Angaben Pflicht sind, sagen die Deklarationen der Unterklasse
        # (``parties`` / ``instruction``), geprüft wird im gemeinsamen
        # Block. Keine Erfassungspunkte und keine Stichprobe: was ankommt, kommt an. Die
        # Felder stehen trotzdem, damit jede Lesestelle dieselbe Form vorfindet.
        return {**self.clean_purchase_config(raw or {}),
                "points": [], "sample": dict(sampling.DEFAULT)}


class Beschaffen(Handel):
    """Etwas **einkaufen** – und die Stücke warten, bis es da ist.

    **Ein Tor, kein Vorgang am Stück.** Alle anderen Module tun etwas *mit* der
    Einzelinstanz: sie messen, bewegen, sondern aus, verbauen. Dieses hier tut mit ihr
    gar nichts – es hält sie auf, bis die Ware eingetroffen ist. Darum ist es ein
    **Durchläufer** (``Im Prozess`` → ``Im Prozess``) und braucht keine Zeile in der
    Prozess-Engine.

    **Es erzeugt keine Einzelinstanzen.** Die entstehen ausschliesslich bei der Freigabe
    eines Erzeugungsauftrags (``serialization``); dieses Modul lässt sie passieren. Ein
    Zukaufteil ist deshalb ein ganz gewöhnlicher Erzeugungsauftrag, dessen Prozess aus
    einem Beschaffen-Modul besteht – die Charge steht ab der Freigabe als ``Im Prozess``
    da und wird beim Wareneingang freigegeben.

    **Und eine Leistung taucht nie im Bestand auf** – nicht weil ein Feld sie ausschliesst,
    sondern weil dieses Modul nichts erzeugt. Wer «Härten» bestellt, kauft eine
    Dienstleistung an einem Stück, das es schon gibt; der Artikel steht auf dem Beleg und
    nirgends sonst.

    ## Zwei Angaben, mehr nicht

    ``suppliers``    die **zugelassenen** Lieferanten (mindestens einer), je Eintrag
                     ``{"supplier": <Objektnr>, "ref": "<Artikelnummer oder Link>"}``.
    ``instruction``  **was zu tun ist** – ein Satz, Pflicht.

    **Eine Liste mit einem Eintrag ist der Normalfall** – kein Modus, keine Verzweigung.
    Wer nur bei Würth kauft, hat eine Liste mit Würth; wer vergleichen will, nennt drei.
    Fachlich ist das die **Lieferantenfreigabe**: wer für dieses Teil in Frage kommt.
    Ein Einzelwert hätte den Vergleich zu einem zweiten Mechanismus gemacht.

    **Die Bestellangabe gehört zur PAARUNG, nicht zum Beleg** (``ref``): «wie bestelle ich
    bei *ihm* dieses Teil» – seine Artikelnummer oder der Shop-Link. Sie ist bekannt,
    wenn man festlegt, wer in Frage kommt, und sie ändert sich nicht je Bestellung. Am
    Beleg wäre sie eine Angabe, die man bei jedem Vorgang neu abschreibt; am **Artikel**
    (``supplier_article_number``) ist sie ein einzelner Wert ohne Lieferanten – genau
    darum war sie dort nie brauchbar. Frei und kurz: eine Nummer, eine URL oder beides.

    **Kein Artikelfeld.** *Was* beschafft wird, sagt der **Prozess**: die Einzelinstanzen,
    die vor dem Modul stehen, tragen ihren Artikel – ihn daneben zu tippen wäre eine
    zweite Aussage über dieselbe Sache, und die getippte gewinnt auch dann, wenn sie
    falsch ist. Daraus fällt der Mehrartikel-Fall von selbst heraus: stehen Stücke
    zweier Artikel davor, hat der Beleg **zwei Zeilen** – EINE Bestellung, wie im echten
    Leben (``purchase.process_lines``).

    **Keine Menge in der Konfiguration.** Beim Modellieren steht nicht fest, wie viele
    Stücke ankommen – dieselbe Regel wie beim Verbrauch. Sie ist die Zahl der
    Einzelinstanzen je Zeile und friert mit der Bestellung ein.

    ## Woher der Lieferant weiss, was zu tun ist — drei Schichten, jede an ihrem Ort

    ============ ===================================== ==============================
    Was          Woher                                  Warum dort
    ============ ===================================== ==============================
    Die Sache    Artikel-Spezifikation (eingefroren)    Sie beschreibt das Teil und
                                                        gilt für jeden Lieferanten.
    Der Auftrag  ``instruction`` am Modul               «Härten auf 58 HRC» ist eine
                                                        Eigenschaft dieses Schritts,
                                                        nicht des Artikels – und ein
                                                        Artikel hat mehrere Schritte.
    Die Nummer   Angebotszeile bzw. ``reference``       Eine Bestellnummer gehört dem
                                                        Lieferanten, nicht dem Teil.
    ============ ===================================== ==============================

    Die **Spezifikation reist mit dem Beleg** (``purchase.embed_data``), sie wird nicht
    ausgewählt: eine «welche Felder sieht der Lieferant»-Konfiguration wäre eine vierte
    Stelle für dieselbe Frage – und bei zwei Lieferanten müsste sie zweimal beantwortet
    werden. Der Lieferant sieht die Sache; **was er damit tun soll**, steht in einem Satz
    daneben. Ohne diesen Satz ist das Modul nicht anlegbar: eine Bestellung, aus der
    niemand liest, was verlangt ist, ist keine.

    **Kein Modus «Webshop».** Jeder, bei dem man kauft, *ist* ein Lieferant – ob per
    Shop-Link, Telefon oder Portal, ist eine Eigenschaft **von ihm** und nicht dieser
    Bestellung. Ein zweiter Ablauf für dieselben drei Stufen wäre dieselbe Angabe ein
    zweites Mal, und die zweite läuft irgendwann weg.

    ## Drei Stufen — und sie gehören dem BELEG

    ``Anfrage → Bestellung → Wareneingang``. Die Einzelinstanz trägt davon **nichts**:
    sie ist von der ersten bis zur letzten Stufe ``Im Prozess``. «Preis steht» ist keine
    Stufe, sondern der Inhalt der Anfrage – sie ist fertig, wenn ein Preis angenommen
    ist; beim Shop-Kauf trägt man ihn selbst ein.

    **``storniert`` ist ein Ausgang, keine Stufe.**

    Ab ``BINDING`` ist eine **zweite Partei** gebunden: dort liegt eine Bestellung beim
    Lieferanten. Verliert der Beleg danach seine Grundlage, ändert das System ihn nicht
    still, sondern **meldet** und wartet auf die Bestätigung (``services/purchase``).
    """

    #: **Die Beleg-Angaben stehen nicht mehr hier**, sondern an ``Module`` – seit auch
    #: das Bewegen-Modul einen Beleg tragen kann, beschreiben sie den *Beleg* und nicht
    #: diesen Modultyp. Was diese Klasse dazu sagt, sind die zwei Zeilen darunter: hier
    #: sind **beide Pflicht**, denn es ist nichts ableitbar. Der Artikel beschreibt die
    #: Sache, nicht den Auftrag; und ohne zugelassenen Lieferanten steht beim Ausführen
    #: niemand da, bei dem man bestellen könnte.
    #: **Beides Pflicht.** Beim Beschaffen ist nichts ableitbar: bei wem bestellt wird,
    #: ist eine Freigabeentscheidung, und was zu tun ist, sagt kein Artikel.
    parties = Module.REQUIRED
    instruction = Module.REQUIRED

    #: Wir kaufen: es kommt herein, und wir zahlen.
    direction = procurement.BUY

    #: Und seine Summe **ist** der Preis der Ware – auch bei einer Leistung am Teil.
    landed_cost = True


class Verkauf(Handel):
    """Etwas **verkaufen** – und das Stück verlässt hier das Haus.

    Der Zwilling des Beschaffens: dieselben drei Stufen, dieselbe Schwelle, derselbe
    Storno, dieselbe Oberfläche. Der Unterschied ist die **Richtung**, und daraus folgt
    alles Weitere, ohne dass es jemand aufschreibt – die Stufen heissen «Angebot ·
    Zusage · Geliefert», die Gegenpartei ist ein **Kunde**, und den Preis nennen **wir**.

    ## Der eine echte Unterschied: es ist ein AUSGANG

    Der Einkauf endet mit dem Wareneingang und ist darum ein **Durchläufer** – das Stück
    läuft danach weiter. Der Verkauf endet mit der Lieferung, und was geliefert ist, ist
    weg: ``terminal``. Daraus fällt alles Übrige heraus (§4.6) – hinter ihm kann kein
    Modul stehen, es passiert das Ende-Objekt nicht, das Bild endet dort.

    **Der Zustand ist ``Verkauft``, und er ist nicht endgültig.** Eine Retoure ist real:
    ein ganz gewöhnlicher Auftrag darf das Stück greifen – **das Greifen IST die
    Rücknahme**, genau wie beim Sperren und beim Verbauen. Es gibt keinen «Retoure
    annehmen»-Endpunkt, und weil der Start eines solchen Auftrags vom Regelstart abweicht,
    ist er **automatisch** eine dokumentierte Abweichung.

    ## Was in der Definition steht: nichts

    **Der Kunde steht zur Laufzeit fest.** Beim Einkauf ist die Liste eine
    Freigabeentscheidung, die vorab fällt («für dieses Teil kommen diese drei in Frage») –
    beim Verkauf weiss beim Modellieren eines Artikels niemand, wer ihn einmal kauft. Die
    Liste bleibt trotzdem *möglich* (``parties = OPTIONAL``): «diese Charge geht
    ausschliesslich an Meier» ist eine echte Hausregel. Leer heisst frei – und frei heisst
    hier wirklich **jeder**: die Rolle sagt, was jemand *für uns* tut, nicht ob er *bei
    uns* kaufen darf (``Flow.party_roles`` ist beim Verkauf leer, Testnotiz #779).

    **Und einen Auftrag an die Gegenpartei gibt es hier gar nicht** (``instruction =
    OFF``, Testnotizen #780/#781): ein Kunde tut nichts, er kauft. Was er bekommt, sagt
    die Artikel-Spezifikation, die mit dem Beleg reist; ein Lieferhinweis («Anlieferung
    nur werktags») gehört an das **Bewegen**-Modul, das die Lieferung *ist*.

    Es stand einmal als freiwilliges Feld da – «falls jemand es braucht». Genau das ist
    die Form, die eine Beschriftung trägt, die nirgends passt («Auftrag an den Kundeen»),
    und die zu einer Eingabe einlädt, die niemand liest. Ein Feld als Vielleicht ist
    schlimmer als keines.

    ## Und der Preis ist NICHT der Einstandspreis

    ``landed_cost = False``: was ein Kunde zahlt, ist verhandelt und sagt nichts über
    unsere Kosten. Ihn an den Artikel zu schreiben hiesse, mit dem eigenen Verkaufspreis
    zu kalkulieren – derselbe stille Datenfehler wie beim Frachttarif (§9.8), nur teurer.
    """

    #: Wir verkaufen: es geht hinaus, und wir werden bezahlt.
    direction = procurement.SELL

    #: **Ein Ausgang.** Was hier ankommt, verlässt den Auftrag – und das Haus.
    terminal = True

    #: Der Kunde steht zur Laufzeit fest – die Liste bleibt möglich (die Vorgabe von
    #: ``Module``), aber sie ist nie Pflicht.
    #: **Einen Auftrag an ihn gibt es hier gar nicht**: ein Kunde tut nichts, er kauft.
    instruction = Module.OFF

    def status_after_for(self, config: Optional[dict[str, Any]]) -> str:
        """**Verkauft.** Bei einem Ausgang ist das zugleich ``exit_status_for`` – dort
        läuft nichts weiter, also gibt es auch keine zwei Zustände (``Module``)."""
        return st.VERKAUFT


MODULES: dict[str, Module] = {
    m.key: m for m in (
        Beschaffen(
            key=BESCHAFFEN,
            # **Name und Farbe kommen vom Vorgang, nicht von dieser Zeile**
            # (``domain/procurement``). Ein Einkauf sieht überall gleich aus – auch dort,
            # wo ihn ein Bewegen-Modul auslöst; zwei Literale wären zwei Stände.
            label=procurement.of(procurement.BUY).label,
            # Ein Durchläufer: das Modul verändert das Stück nicht, es hält es auf.
            status_before=st.IM_PROZESS,
            status_after=st.IM_PROZESS,
            tone=procurement.of(procurement.BUY).tone,
        ),
        Verkauf(
            key=VERKAUF,
            label=procurement.of(procurement.SELL).label,
            status_before=st.IM_PROZESS,
            # Ein **Ausgang**: das Stück verlässt hier den Auftrag. Der Wert steht
            # zusätzlich in ``status_after_for``, weil jede Lesestelle dort fragt.
            status_after=st.VERKAUFT,
            tone=procurement.of(procurement.SELL).tone,
        ),
        Datenerfassung(
            key=DATENERFASSUNG,
            label="Datenerfassung",
            status_before=st.IM_PROZESS,
            status_after=st.IM_PROZESS,
            tone="slate",
        ),
        Aussondern(
            key=AUSSONDERN,
            label="Aussondern",
            status_before=st.IM_PROZESS,
            # Der Vorgabewert; das gültige Nachher steht in ``status_after_for``, weil es
            # an der Ausprägung hängt.
            status_after=st.VERSCHROTTET,
            tone="clay",
        ),
        Bewegen(
            key=BEWEGEN,
            label="Bewegen",
            # Ein Ort ist kein Zustand: das Stück läuft weiter, wie es angekommen ist.
            status_before=st.IM_PROZESS,
            status_after=st.IM_PROZESS,
            tone="moss",
        ),
        Verbrauch(
            key=VERBRAUCH,
            label="Verbrauch",
            status_before=st.IM_PROZESS,
            # Das Nachher des **Produkts** – es läuft weiter. Was die Komponenten
            # bekommen, steht in ``exit_status_for``; hier stünde es falsch, weil diese
            # Spalte den gespeicherten Übergang des Moduls trägt und der gilt für das,
            # was das Modul passiert.
            status_after=st.IM_PROZESS,
            tone="sand",
        ),
    )
}

KEYS: tuple[str, ...] = tuple(MODULES)

#: **Welche Modultypen einen Einkaufs-Beleg tragen können** – abgeleitet, nie gepflegt.
#: Der Dienst fragt danach statt nach einem Namen; ein neuer Typ mit ``buys`` ist damit
#: eine Zeile in seiner Klasse und kein zweiter Ort, den jemand vergisst.
def buying_types(*, buys: Optional[str] = None) -> list[str]:
    return [key for key, mod in MODULES.items()
            if mod.buys is not None and (buys is None or mod.buys == buys)]


LABELS: dict[str, str] = {k: m.label for k, m in MODULES.items()}
TONES: dict[str, str] = {k: m.tone for k, m in MODULES.items()}


def get(module_type: Any) -> Module:
    """Modul zu einem Schlüssel. Unbekannt = harter Fehler, kein Rückfall."""
    found = MODULES.get(module_type)
    if found is None:
        raise HTTPException(
            status_code=400,
            detail=(
                f"«{module_type}» ist kein Prozessschrittmodul. Erlaubt: "
                + ", ".join(f"{m.label} ({m.key})" for m in MODULES.values()) + "."
            ),
        )
    return found


def points_of(config: Optional[dict[str, Any]]) -> list[dict[str, Any]]:
    """Die Erfassungspunkte einer gespeicherten Definition — die eine Lesestelle."""
    return list((config or {}).get("points") or [])


def reason_of(config: Optional[dict[str, Any]]) -> str:
    """Der in der Definition gegebene Grund — die eine Lesestelle.

    Nur das Aussondern hat einen; überall sonst ist er leer. Ein Modul, das keinen
    kennt, gibt darum nicht ``None`` zurück, sondern nichts – die Anzeige fragt dann gar
    nicht erst nach einer Fallunterscheidung.
    """
    return str((config or {}).get("reason") or "")


def lines_of(config: Optional[dict[str, Any]]) -> list[dict[str, int]]:
    """Die **Stückliste** eines Moduls — je Zeile Artikel und Menge pro Stück.

    Nur der Verbrauch hat eine; überall sonst ist sie leer. Ein Modul, das keine kennt,
    gibt darum nicht ``None`` zurück, sondern nichts – die Aufrufstelle fragt dann gar
    nicht erst nach einer Fallunterscheidung.
    """
    return [
        {"article": int(row["article"]), "quantity": int(row["quantity"])}
        for row in (config or {}).get(Verbrauch.LINES) or []
    ]


def sample_of(config: Optional[dict[str, Any]]) -> dict[str, Any]:
    """Die Stichprobenregel einer gespeicherten Definition — die eine Lesestelle.

    Fehlt sie (Definitionen aus der Zeit vor der Stichprobe), gilt **alle**: das ist,
    was diese Module bisher getan haben, und damit ändert sich an ihnen nichts.
    """
    return (config or {}).get("sample") or dict(sampling.DEFAULT)


def label(module_type: str) -> str:
    """Wie ein Modul heisst. **Abgeleitet aus dem Typ, nie gespeichert** (#682/#687).

    Ein unbekannter Typ wird als roher Wert gemeldet statt schöngefärbt – er dürfte
    nicht existieren, und eine Anzeige, die ihn wie einen normalen Modultyp malt,
    verbirgt genau den Fehler, den man sehen müsste.
    """
    return LABELS.get(module_type, module_type)
