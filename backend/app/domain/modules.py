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

from . import capture_types, sampling, statuses as st

#: Der eine Ortsbedarf, den es heute gibt: **beim Produkt**. Eine geschlossene Liste
#: wie ``Aussondern.MODES`` – ein künftiges Modul («an meinem konfigurierten Ort»)
#: bekommt einen zweiten Wert, keine zweite Mechanik.
AT_PRODUCT = "product"

DATENERFASSUNG = "datenerfassung"
AUSSONDERN = "aussondern"
VERBRAUCH = "verbrauch"
BEWEGEN = "bewegen"
BESCHAFFEN = "beschaffen"


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
                     target: Optional[int], transport: Optional[str]) -> Optional["Move"]:
        """**Bringt dieses Modul die Stücke woandershin?** Vorgabe: nein.

        Eine Methode und eine Antwort, statt zweier Fragen («hat es ein Ziel?», «welche
        Transportart?») an zwei Stellen. Die Ausführungsstelle bekommt damit entweder
        eine vollständige Absicht oder ``None`` – und braucht in keinem Fall zu wissen,
        welcher Modultyp vor ihr steht (dieselbe Bauart wie ``consumption.plan``).
        """
        return None

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
    """Was ein Modul am Ort ändern will: wohin, und womit gebracht."""

    target: int
    transport: str


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

    **Die Transportart gehört zur LAUFZEIT, nicht in die Definition.** Beim Modellieren
    weiss niemand, ob das Stück nebenan liegt oder in Werk Nord – und ein gespeicherter
    Modus wäre bei der zweiten Ausführung falsch. Heute ist nur ``manuell`` wirksam;
    ``paket`` und ``fracht`` stehen als Liste **mit** ihrer Verfügbarkeit da, damit das
    Freischalten später ein Wert ist und kein Umbau. Der Server weist eine gesperrte Art
    ab – wäre sie nur in der Oberfläche gesperrt, wäre die Sperre eine Bitte.

    **Geprüft wird hier nur die FORM** (eine Objektnummer), nicht die Existenz: diese
    Stelle hat keine Datenbanksitzung. Dass es den Halter gibt und dass er keinen Kreis
    bildet, weist ``places.assert_placeable`` bei der Ausführung ab – streng schreiben,
    tolerant lesen.
    """

    #: Der Schlüssel der einen Einstellung. ``None`` heisst «wird beim Ausführen gewählt».
    TARGET = "target"

    #: Die Transportarten – **Liste mit Verfügbarkeit**, nicht Liste der verfügbaren.
    #: Was es geben wird, steht hier; was heute geht, sagt ``available``. Eine Oberfläche
    #: kann damit die Roadmap zeigen, ohne sie zu erfinden.
    TRANSPORTS: tuple[dict[str, Any], ...] = (
        {"key": "manuell", "label": "Manuell", "available": True,
         "hint": "Jemand bringt es hin – kein Dienstleister, kein Beleg."},
        {"key": "paket", "label": "Paket", "available": False,
         "hint": "Versand als Paket – noch nicht gebaut."},
        {"key": "fracht", "label": "Fracht", "available": False,
         "hint": "Stückgut oder Palette – noch nicht gebaut."},
    )
    DEFAULT_TRANSPORT = "manuell"

    #: Was der Knopf sagt. **«Bestätigen», nicht «scannen»**: gescannt ist zu diesem
    #: Zeitpunkt längst – Ware und Zielort –, und was der Knopf auslöst, ist die Buchung
    #: der Ablage. Ein Verb, das den vorherigen Schritt benennt, beschreibt nicht, was
    #: passiert (Testnotiz #733).
    action: str = "Bewegung bestätigen"

    def clean_config(self, raw: Optional[dict[str, Any]]) -> dict[str, Any]:
        value = (raw or {}).get(self.TARGET)
        target = self._as_object_id(value)
        # Keine Erfassungspunkte und keine Stichprobe: bewegt wird, was ankommt. Die
        # Felder stehen trotzdem, damit jede Lesestelle dieselbe Form vorfindet.
        return {self.TARGET: target, "points": [], "sample": dict(sampling.DEFAULT)}

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
                     target: Optional[int], transport: Optional[str]) -> Move:
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
        return Move(target=int(goal), transport=self._clean_transport(transport))

    def _clean_transport(self, value: Optional[str]) -> str:
        key = (value or self.DEFAULT_TRANSPORT).strip()
        known = {t["key"]: t for t in self.TRANSPORTS}
        if key not in known:
            raise HTTPException(
                status_code=400,
                detail=f"«{key}» ist keine Transportart. Bekannt: "
                       + ", ".join(known) + ".",
            )
        if not known[key]["available"]:
            raise HTTPException(
                status_code=400,
                detail=(f"«{known[key]['label']}» ist noch nicht gebaut – heute wird "
                        f"manuell bewegt."),
            )
        return key


class Beschaffen(Module):
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

    ``suppliers``    die **zugelassenen** Lieferanten (mindestens einer).
    ``instruction``  **was zu tun ist** – ein Satz, Pflicht.

    **Eine Liste mit einem Eintrag ist der Normalfall** – kein Modus, keine Verzweigung.
    Wer nur bei Würth kauft, hat eine Liste mit Würth; wer vergleichen will, nennt drei.
    Fachlich ist das die **Lieferantenfreigabe**: wer für dieses Teil in Frage kommt.
    Ein Einzelwert hätte den Vergleich zu einem zweiten Mechanismus gemacht.

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

    SUPPLIERS = "suppliers"
    INSTRUCTION = "instruction"

    #: Wie lang der Auftrag an den Lieferanten höchstens ist. Ein Satz, kein Pflichtenheft
    #: – wer mehr braucht, hängt ein Dokument an den Artikel.
    MAX_INSTRUCTION = 400

    #: Wie viele Lieferanten eine Freigabe höchstens nennt. Mehr ist keine Auswahl mehr,
    #: sondern eine Adressliste – und niemand fragt zwanzig Lieferanten je Schraube an.
    MAX_SUPPLIERS = 10

    #: **Die drei Stufen, in ihrer Reihenfolge.** Sie stehen hier, weil sie zum Modultyp
    #: gehören: die Oberfläche fragt danach, statt sie nachzubauen.
    STAGES: tuple[str, ...] = ("anfrage", "bestellung", "wareneingang")

    #: Der Ausgang. Keine Stufe – man kommt dort an, statt hindurchzugehen.
    CANCELLED = "storniert"

    #: **Ab hier ist eine zweite Partei gebunden.** Vor dieser Stufe darf das System die
    #: Grundlage still nachziehen; ab ihr liegt eine Bestellung beim Lieferanten, und
    #: eine stille Änderung wäre ein Beleg, der nicht mehr stimmt.
    BINDING = "bestellung"

    STAGE_LABELS: dict[str, str] = {
        "anfrage": "Anfrage", "bestellung": "Bestellung",
        "wareneingang": "Wareneingang", CANCELLED: "Storniert",
    }

    #: Das Verb der **aktiven** Stufe – was man dort tut, nicht wie sie heisst
    #: (Testnotizen #271/#275). Die letzte Stufe löst ``confirm_step`` aus und trägt
    #: darum ``action``.
    STAGE_VERBS: dict[str, str] = {"anfrage": "Bestellen", "bestellung": "Wareneingang buchen"}

    #: Was der Knopf sagt, der das Modul abschliesst. Erfasst wird nichts – der Scan ist
    #: die Bestätigung, dass genau diese Ware angekommen ist.
    action = "Wareneingang buchen"

    def clean_config(self, raw: Optional[dict[str, Any]]) -> dict[str, Any]:
        data = raw or {}
        suppliers = self._suppliers(data.get(self.SUPPLIERS))
        instruction = str(data.get(self.INSTRUCTION) or "").strip()
        if not instruction:
            raise HTTPException(
                status_code=400,
                detail=(
                    "«Beschaffen» braucht einen Satz, was der Lieferant tun soll – die "
                    "Artikel-Spezifikation beschreibt die Sache, nicht den Auftrag "
                    "(«Härten auf 58 HRC», «gemäss Zeichnung fertigen», «liefern»)."
                ),
            )
        if len(instruction) > self.MAX_INSTRUCTION:
            raise HTTPException(
                status_code=400,
                detail=f"Der Auftrag ist zu lang (max. {self.MAX_INSTRUCTION} Zeichen).",
            )
        # Keine Erfassungspunkte und keine Stichprobe: was ankommt, kommt an. Die Felder
        # stehen trotzdem, damit jede Lesestelle dieselbe Form vorfindet.
        return {self.SUPPLIERS: suppliers, self.INSTRUCTION: instruction,
                "points": [], "sample": dict(sampling.DEFAULT)}

    def _suppliers(self, value: Any) -> list[int]:
        if value in (None, ""):
            value = []
        if not isinstance(value, (list, tuple)):
            raise HTTPException(
                status_code=400,
                detail="«Beschaffen» erwartet eine Liste zugelassener Lieferanten.",
            )
        found: list[int] = []
        for entry in value:
            number = self._object_id(entry)
            if number is None:
                raise HTTPException(
                    status_code=400,
                    detail=f"«{entry}» ist keine Lieferanten-Objektnummer.",
                )
            if number in found:
                raise HTTPException(
                    status_code=400,
                    detail=(f"Lieferant {number} steht zweimal in der Freigabe – zweimal "
                            f"derselbe ist keine zweite Wahl."),
                )
            found.append(number)
        if not found:
            raise HTTPException(
                status_code=400,
                detail=(
                    "«Beschaffen» braucht mindestens einen zugelassenen Lieferanten – "
                    "ohne ihn steht beim Ausführen niemand da, bei dem man bestellen "
                    "könnte."
                ),
            )
        if len(found) > self.MAX_SUPPLIERS:
            raise HTTPException(
                status_code=400,
                detail=f"Höchstens {self.MAX_SUPPLIERS} Lieferanten je Modul.",
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


MODULES: dict[str, Module] = {
    m.key: m for m in (
        Beschaffen(
            key=BESCHAFFEN,
            label="Beschaffen",
            # Ein Durchläufer: das Modul verändert das Stück nicht, es hält es auf.
            status_before=st.IM_PROZESS,
            status_after=st.IM_PROZESS,
            tone="plum",
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
