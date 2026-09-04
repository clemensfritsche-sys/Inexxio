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

from . import capture_types, deal, sampling, statuses as st

#: Der eine Ortsbedarf, den es heute gibt: **beim Produkt**. Eine geschlossene Liste
#: wie ``Aussondern.MODES`` – ein künftiges Modul («an meinem konfigurierten Ort»)
#: bekommt einen zweiten Wert, keine zweite Mechanik.
AT_PRODUCT = "product"

DATENERFASSUNG = "datenerfassung"
AUSSONDERN = "aussondern"
VERBRAUCH = "verbrauch"
BEWEGEN = "bewegen"
ZAHLUNG = "zahlung"


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

    @staticmethod
    def _object_id(value: Any) -> Optional[int]:
        """**Eine Objektnummer lesen** – oder ``None``, wenn dort keine steht.

        Die eine Lesestelle: mehrere Module verweisen auf einen Datensatz (das Ziel des
        Bewegen-Moduls, der Partner des Zahlungs-Moduls), und «was ist eine Objektnummer»
        ist an allen dieselbe Frage. **Was ein fehlender Wert bedeutet, sagt der
        Aufrufer** – beim Ziel heisst leer «wird beim Ausführen gewählt», beim Partner ist
        es ein Fehler; darum meldet diese Funktion nichts, sie liest nur.
        """
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

    **Geprüft wird hier nur die FORM** (eine Objektnummer), nicht die Existenz: diese
    Stelle hat keine Datenbanksitzung. Dass es den Halter gibt und dass er keinen Kreis
    bildet, weist ``places.assert_placeable`` bei der Ausführung ab – streng schreiben,
    tolerant lesen.
    """

    #: Der Schlüssel der einen Einstellung. ``None`` heisst «wird beim Ausführen gewählt».
    TARGET = "target"

    #: Es bewegt – daraus folgt in der Oberfläche der Ziel-Scan.
    moves = True

    #: Was der Knopf sagt. **«Bestätigen», nicht «scannen»**: gescannt ist zu diesem
    #: Zeitpunkt längst – Ware und Zielort –, und was der Knopf auslöst, ist die Buchung
    #: der Ablage. Ein Verb, das den vorherigen Schritt benennt, beschreibt nicht, was
    #: passiert (Testnotiz #733).
    action: str = "Bewegung bestätigen"

    def clean_config(self, raw: Optional[dict[str, Any]]) -> dict[str, Any]:
        data = raw or {}
        target = self._as_object_id(data.get(self.TARGET))
        # **Eine Angabe, und die ist optional.** Keine Erfassungspunkte und keine
        # Stichprobe: bewegt wird, was ankommt. Die Felder stehen trotzdem, damit jede
        # Lesestelle dieselbe Form vorfindet.
        return {self.TARGET: target,
                "points": [], "sample": dict(sampling.DEFAULT)}

    def _as_object_id(self, value: Any) -> Optional[int]:
        """Das **Ziel** – gelesen wie überall, abgewiesen mit dem Satz dieses Moduls.

        Gelesen wird mit ``Module._object_id`` (eine Sache, eine Stelle); was ein
        unlesbarer Wert bedeutet, gehört dagegen hierher: **leer** ist beim Ziel gültig
        und heisst «wird beim Ausführen gewählt», alles andere ist ein Fehler, der sagt,
        was dort hingehört.
        """
        if value in (None, "", 0):
            return None
        if self._object_id(value) is None:
            raise HTTPException(
                status_code=400,
                detail=(f"«{value}» ist keine Objektnummer. Das Ziel von «Bewegen» ist "
                        f"ein Regal, eine Person oder ein Unternehmen – oder es bleibt "
                        f"leer und wird beim Ausführen gewählt."),
            )
        return self._object_id(value)

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


class Zahlung(Module):
    """►►► **Geld mit einer zweiten Partei** – ein Modul für beide Richtungen. ◄◄◄

    Es ist die Antwort auf die Frage, was Einkauf, Verkauf, eine eingekaufte Spedition,
    eine Leistung ohne Artikel und eine Vorauszahlung gemeinsam haben. Nicht die
    **Ware** – die ist in jedem Fall eine andere. Sondern: **es fliesst Geld, und eine
    zweite Partei ist beteiligt.**

    ## Was hier eingestellt wird: vier Dinge

    ``direction``  **Kommt Geld herein oder geht es hinaus?** (``domain/deal``). Daraus
                   folgt jedes Wort – wie die Stufen heissen, wie die Gegenpartei heisst,
                   wer die Rechnung stellt. Als **Daten**, nicht als Verzweigung.
    ``parties``    Die **zugelassenen** Gegenparteien. **Leer heisst frei** – dann wird
                   beim Ausführen gesucht. Eine Liste mit einem Eintrag ist der
                   Normalfall; wer vergleichen will, nennt drei.
    ``prepaid``    **Erst weiter, wenn bezahlt.** Der einzige Schalter – und er schreibt
                   keine Reihenfolge vor, er hält nur an (``deal.Balance.settled``).

    ## Was gehandelt wird, sagt der PROZESS – nicht ein Feld

    Es gibt **keinen Artikel** in der Definition: die Einzelinstanzen, die vor dem Modul
    stehen, tragen ihren Artikel, und der Artikel trägt seine **Spezifikation**. Beides
    reist mit dem Vorgang (``deal.lines_of`` / ``services/article_fields``), damit die
    Gegenpartei weiss, worum es geht. Ein getipptes Artikelfeld daneben wäre eine zweite
    Aussage über dieselbe Sache – und die getippte gewinnt auch dann, wenn sie falsch ist.

    Daraus folgt, warum der Satz **freiwillig** ist: Zeilen und Satz sind zusammen die
    Aussage, und die Zeilen gibt es immer.

    ==========================  ====================================================
    Zeilen **ohne** Satz        wir kaufen bzw. verkaufen **diese Teile**
    Zeilen **mit** Satz         an **diesen Teilen** ist **das** zu tun
    ==========================  ====================================================

    Genau deshalb braucht es **keine Templates** und keinen Modus «Sache ↔ Leistung»: die
    Unterscheidung fällt aus zwei Angaben heraus, die es ohnehin gibt. Ein Template wäre
    ein Konzept für eine Frage, die sich von selbst beantwortet.

    Ebenso gibt es **keine Menge** (die Zahl der Einzelinstanzen) und **keinen Termin**
    (ableitbar aus Bestelldatum und Lieferfrist).

    **Was bei einem Partner zu tun ist, steht dagegen bei IHM** – je zugelassenem Partner
    eine Pflichtangabe (``parties[].ref``, ``deal.TASK``): seine Artikelnummer, sein
    Shop-Link oder ein Satz. Sie ist eine Eigenschaft der **Paarung** Modul × Partner und
    nicht des Partners allein – derselbe Lieferant führt je Teil eine andere Nummer –, und
    sie gehört dorthin, wo man festlegt, wer in Frage kommt. Am **Vorgang** wäre sie eine
    Angabe, die man bei jedem Mal neu abschreibt.

    ## Die eine Regel, die es robust macht: es bewegt keine Stücke

    Ein **Durchläufer** (``Im Prozess`` → ``Im Prozess``), ``terminal = False``,
    ``moves = False``, kein Ortswechsel, kein neuer Status. Es hält die Stücke auf, bis
    die zweite Partei ihren Teil getan hat, und lässt sie dann weiterlaufen.

    Daraus folgt, dass **keine andere Regel im System von diesem Modul wissen muss**:
    keine Kettenregel, keine Statusliste, keine Bestandsansicht, keine Zeile in der
    Prozess-Engine. Was physisch passiert, sagen die Nachbarn – kommissioniert und
    ausgeliefert wird mit «Bewegen», ausgesondert mit «Aussondern».

    *Ein Verkauf besteht damit aus zwei Modulen statt aus einem, und das ist der Preis.
    Er ist der richtige: sobald dieses Modul auch Ware bewegte, bräuchte es für jede
    Kombination aus Geld und Ware wieder einen eigenen Fall.*

    ## Und es trägt bewusst KEINEN ``buys``-Beleg

    ``Module.buys`` bindet ein Modul an ``services/purchase`` – an dieselbe Maschine, aus
    der «Beschaffen» und «Verkauf» bestehen. Dieses Modul hat seine eigene
    (``services/deal``), und zwar vollständig: eigene Tabelle, eigener Dienst, eigene
    Vokabel. Das ist Absicht und keine Doppelung auf Zeit – wer die beiden alten Module
    löscht, soll dabei keine Zeile hier anfassen müssen.
    """

    #: Die vier Schlüssel der Konfiguration – hier und nirgends sonst als Zeichenkette.
    DIRECTION = "direction"
    PARTIES = "parties"
    PREPAID = "prepaid"
    #: ►►► **Der Steuersatz, mit dem eine neue Position beginnt.** ◄◄◄
    #:
    #: Eine Rechnung ohne Steuersatz ist keine (MWSTG Art. 26) – und der Satz hängt an der
    #: **Sache**, nicht am Beleg: sechs Wellen zu 8.1 % und eine Ausfuhr zu 0 % stehen auf
    #: Die beiden Schlüssel **einer Zeile** der Freigabe-Liste.
    PARTY = "party"
    REF = "ref"

    #: Mehr ist keine Auswahl mehr, sondern eine Adressliste.
    MAX_PARTIES = 10
    #: Eine Artikelnummer oder ein Link – kein Bestelltext.
    MAX_REF = 200

    #: ►►► **Kein Scan.** ◄◄◄
    #:
    #: Ein Scan beantwortet «habe ich das richtige physische Ding vor mir» – er verifiziert
    #: das Etikett am Ding, bevor jemand etwas **damit** tut. Dieses Modul tut mit dem
    #: Stück gar nichts: es stellt etwas in Rechnung, mit Referenz auf die Einzelinstanzen.
    #: Ein Etikett zu scannen, um eine Rechnung zu stellen, ist eine Geste ohne Aussage.
    #:
    #: Die Deklaration gibt es im Rahmen genau für diesen Fall («ein reiner Rechenschritt,
    #: eine Freigabe am Schreibtisch»); ``process._verified_instance`` trägt sie seit
    #: jeher, und ohne Instanz bewegt ``confirm_step`` **alles**, was davorsteht – ein
    #: Vorgang statt einer je Instanz. Das ist hier genau richtig: ein Auftrag wird einmal
    #: erledigt, nicht je Kiste.
    requires_verification = False

    #: **Erfasst wird nichts.** Was der Knopf auslöst, ist das Erledigen des Auftrags;
    #: wie es heisst, sagt die Richtung (in beiden dasselbe Wort – siehe ``stage_verbs``).
    def action_for(self, config: Optional[dict[str, Any]]) -> str:
        return deal.of(self.direction_of(config)).stage_verbs[deal.AGREED]

    def direction_of(self, config: Optional[dict[str, Any]]) -> str:
        """**Die Richtung dieses Schritts** – die eine Lesestelle.

        Sie steht in der ``config`` und nicht als zweiter Modul-Schlüssel: es ist EIN
        Modul, und die Richtung ist seine Einstellung. Die ``config`` friert mit der
        Freigabe ein und reist mit dem Schritt – sie ist damit genauso haltbar wie ein
        Schlüssel und kostet keine zweite Kachel in der Palette.

        Tolerant gelesen: ein fehlender Wert ist eine **Ausgabe** (``deal.of``), damit
        eine alte Zeile keine Anzeige zerlegt. Geschrieben wird streng.
        """
        return str((config or {}).get(self.DIRECTION) or deal.OUT)

    def clean_config(self, raw: Optional[dict[str, Any]]) -> dict[str, Any]:
        data = raw or {}
        try:
            direction = deal.assert_direction(data.get(self.DIRECTION))
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        flow = deal.of(direction)
        # **Keine Erfassungspunkte, keine Stichprobe.** Geld ist keine Messung am Stück;
        # die Felder stehen trotzdem, damit jede Lesestelle dieselbe Form vorfindet.
        return {
            self.DIRECTION: direction,
            self.PARTIES: self._parties(data.get(self.PARTIES), flow),
            self.PREPAID: bool(data.get(self.PREPAID)),
            # ►►► **Kein Steuersatz** (Testnotiz #851). ◄◄◄
            #
            # Er stand hier als «Vorgabe jeder neuen Position» und war damit eine
            # Eigenschaft des **Moduls**: eine Vorlage, die für jeden künftigen Auftrag
            # denselben Satz behauptet. Er hängt aber an der **Sache** – sechs Wellen zu
            # 8.1 % und eine Ausfuhr zu 0 % stehen auf demselben Papier –, und die steht
            # erst fest, wenn ein Auftrag läuft. Gefragt wird er darum je Position an der
            # Ausführungsstelle; die Vorbelegung ist der Normalsatz (``deal.DEFAULT_VAT``),
            # und ein Wert, der hier trotzdem ankommt, wird **verworfen**.
            "points": [], "sample": dict(sampling.DEFAULT),
        }

    def _parties(self, value: Any, flow: "deal.Direction") -> list[dict[str, Any]]:
        """Die Freigabe-Liste **streng** prüfen. Leer ist erlaubt und heisst **frei**.

        Je Zeile die Objektnummer und die **Angabe, was bei ihm zu tun ist**
        (``deal.TASK``): seine Artikelnummer, sein Shop-Link oder ein Satz. Sie gehört der
        **Paarung** Modul × Partner, nicht dem Partner allein – derselbe Lieferant führt je
        Teil eine andere Nummer –, und sie gilt in **beiden** Richtungen: beim Einkauf sagt
        sie, wie man bei ihm bestellt, beim Verkauf, was er bekommt.

        **Sie ist Pflicht** (Testnotizen #805/#808). Der frühere freiwillige Satz am
        Vorgang («Was ist daran zu tun?») war ihre optionale Doppelung – und ein Feld, das
        man ausfüllen *kann*, wird an der Hälfte der Stellen leer gelassen; dann sagt seine
        Leere nichts.

        Tolerant **gelesen** wird die alte Form (blosse Objektnummer): ein freigegebener
        Prozess ist eingefroren, sie steht in laufenden Aufträgen und wird sie überleben.
        """
        if value in (None, ""):
            value = []
        if not isinstance(value, (list, tuple)):
            raise HTTPException(
                status_code=400,
                detail=f"«{flow.label}» erwartet eine Liste zugelassener "
                       f"{deal.PARTY}.",
            )
        rows: list[dict[str, Any]] = []
        seen: set[int] = set()
        for entry in value:
            raw = entry.get(self.PARTY) if isinstance(entry, dict) else entry
            number = self._object_id(raw)
            if number is None:
                raise HTTPException(
                    status_code=400,
                    detail=f"«{entry}» ist keine Objektnummer ({deal.PARTY}).",
                )
            if number in seen:
                raise HTTPException(
                    status_code=400,
                    detail=(f"{deal.PARTY} {number} steht zweimal – zweimal "
                            f"derselbe ist keine zweite Wahl."),
                )
            seen.add(number)
            ref = str((entry.get(self.REF) if isinstance(entry, dict) else "") or "").strip()
            if not ref:
                raise HTTPException(
                    status_code=400,
                    detail=(f"{deal.PARTY} {number}: «{deal.TASK}» fehlt – ohne die "
                            f"Angabe weiss er nicht, worum es geht ({deal.TASK_HINT})."),
                )
            if len(ref) > self.MAX_REF:
                raise HTTPException(
                    status_code=400,
                    detail=(f"{deal.PARTY} {number}: «{deal.TASK}» ist zu lang "
                            f"(max. {self.MAX_REF} Zeichen)."),
                )
            rows.append({self.PARTY: number, self.REF: ref})
        if len(rows) > self.MAX_PARTIES:
            raise HTTPException(
                status_code=400,
                detail=f"Höchstens {self.MAX_PARTIES} {deal.PARTY} je Modul.",
            )
        return rows


def parties_of(config: Optional[dict[str, Any]]) -> list[dict[str, Any]]:
    """Die zugelassenen Gegenparteien **mit ihrer Bestellangabe** – die eine Lesestelle.

    **Leer heisst frei, nicht «niemand».** Der Dienst schränkt nur ein, wenn hier etwas
    steht; sonst wäre ein Modul ohne Liste eines, bei dem man mit niemandem handeln kann.

    Tolerant gegen die alte Form (blosse Objektnummer) – sie steht in jedem Auftrag, der
    vor dieser Runde freigegeben wurde, und ein eingefrorener Prozess ändert sich nie.
    """
    rows: list[dict[str, Any]] = []
    for entry in (config or {}).get(Zahlung.PARTIES) or []:
        raw = entry.get(Zahlung.PARTY) if isinstance(entry, dict) else entry
        try:
            number = int(raw)
        except (TypeError, ValueError):
            continue
        ref = str((entry.get(Zahlung.REF) if isinstance(entry, dict) else "") or "")
        rows.append({Zahlung.PARTY: number, Zahlung.REF: ref})
    return rows


def parties_allowed(config: Optional[dict[str, Any]]) -> list[int]:
    """Nur die Nummern – die Form, in der die **Freigabe-Prüfung** sie braucht.

    Zwei Formen einer Regel, ein Namensstamm: ``parties_of`` nennt die ganze Zeile,
    ``parties_allowed`` beantwortet «darf der hier mitspielen». Zwei Lesestellen wären
    zwei Regeln.
    """
    return [int(r[Zahlung.PARTY]) for r in parties_of(config)]


def prepaid(config: Optional[dict[str, Any]]) -> bool:
    """**Erst weiter, wenn bezahlt?** – die eine Lesestelle."""
    return bool((config or {}).get(Zahlung.PREPAID))


MODULES: dict[str, Module] = {
    m.key: m for m in (
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
        Zahlung(
            key=ZAHLUNG,
            label="Zahlung",
            # Ein **Durchläufer**: das Modul hält die Stücke auf, es verändert sie nicht.
            # Genau daraus folgt, dass keine andere Regel im System von ihm wissen muss.
            status_before=st.IM_PROZESS,
            status_after=st.IM_PROZESS,
            # Gedämpftes Altrosa. Die sechs bestehenden Familien sind vergeben (Slate=Blau ·
            # Sand=Gelbbraun · Moss=Grün · Clay=Rotbraun · Plum=Violett · Teal=Blaugrün),
            # und ein Modul, das sich eine teilt, ist im Fluss von seinem Nachbarn nicht
            # zu unterscheiden. Magenta/Rosa ist die einzige unbesetzte Familie – und sie
            # sitzt deutlich pinker als das orange-braune Clay.
            tone="rose",
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
