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

from typing import Any, Optional

from fastapi import HTTPException

from . import capture_types, sampling, statuses as st

DATENERFASSUNG = "datenerfassung"
AUSSONDERN = "aussondern"
VERBRAUCH = "verbrauch"


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

    def template_problem(self, config: Optional[dict[str, Any]]) -> Optional[str]:
        """Was an dieser Konfiguration gilt **nur im Auftrag**, nicht in der Vorlage?

        Eine Artikel-Vorlage ist zeitlos: sie beschreibt, wie etwas entsteht – für jeden
        künftigen Auftrag, beliebig oft. Eine Angabe, die auf ein **konkretes** Ding
        zeigt, ist dort nach dem ersten Auftrag falsch, und jeder weitere müsste sie
        ignorieren. Dann ist sie keine Angabe, sondern eine Notiz.

        Vorgabe: **alles gilt überall.** Ein neuer Modultyp erbt das, ohne eine Zeile –
        und wer eine solche Angabe einführt, sagt hier, warum sie in der Vorlage nicht
        stehen kann.
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

    #: **Optional: eine ganz bestimmte Einzelinstanz** (Testnotiz #721) – ihre Nummer,
    #: ``<Instanznr>-<Suffix>``. Sie beantwortet den Fall, für den die Stückliste zu grob
    #: ist: *nicht irgendein Rahmen, sondern dieser* – ein Unikat, eine Vorrichtung, eine
    #: Kundenbeistellung.
    #:
    #: **Sie bindet ab der Freigabe**, nicht erst beim Erreichen des Moduls: sonst
    #: könnte sie bis dahin jeder andere Auftrag greifen, und die Vormerkung wäre eine
    #: Absichtserklärung. Gebunden wird dabei über **denselben** Eintritt wie sonst
    #: (``process._enter_at_step``): das Stück ist schlicht ``Im Prozess`` an diesem
    #: Modul, exklusiv über den partiellen Unique-Index. Ein eigener Zustand daneben
    #: entsteht nicht – es gibt genau eine Art, ein Stück zu binden.
    #:
    #: Nur im **Auftrags**-Modul (siehe ``template_problem``) und nur bei ``quantity ==
    #: 1``: eine genannte Einzelinstanz **ist** ein Stück, «4× dieses eine» ist ein
    #: Widerspruch.
    UNIT = "unit"

    #: Höchstmenge je Zeile. Eine Stückliste nennt Stückzahlen, keine Chargen; wer 5000
    #: Schrauben je Produkt braucht, hat einen Tippfehler oder das falsche Modul.
    MAX_PER_UNIT = 1000

    #: Das Verb auf dem Knopf. «Erfassen & bestätigen» wäre hier schlicht falsch – erfasst
    #: wird nichts, der Scan ist die Bestätigung.
    action = "Verbauen"

    def clean_config(self, raw: Optional[dict[str, Any]]) -> dict[str, Any]:
        found = (raw or {}).get(self.LINES) or []
        if not isinstance(found, (list, tuple)):
            raise HTTPException(
                status_code=400,
                detail="«Verbrauch» erwartet eine Liste aus Artikel und Menge.",
            )
        lines: list[dict[str, Any]] = []
        seen: set[int] = set()
        pinned: set[str] = set()
        for row in found:
            article, quantity, unit = self._one(row)
            if unit and unit in pinned:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Einzelinstanz {unit} ist zweimal vorgemerkt. Ein Stück kann "
                        f"nur an einer Stelle verbaut werden."
                    ),
                )
            if unit:
                pinned.add(unit)
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
            lines.append({"article": article, "quantity": quantity}
                        | ({self.UNIT: unit} if unit else {}))
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

    def template_problem(self, config: Optional[dict[str, Any]]) -> Optional[str]:
        """**Eine Vormerkung gibt es nur im Auftrag.**

        Die Artikel-Vorlage läuft beliebig oft. Ein dort genanntes Stück ist nach dem
        ersten Auftrag verbaut, und jeder weitere müsste den Eintrag ignorieren – dann
        ist er keine Angabe, sondern eine Notiz. Im Auftrag dagegen läuft das Modul genau
        einmal, und dort ist «dieses eine Stück» eine Aussage, die trägt.
        """
        pinned = [r for r in (config or {}).get(self.LINES) or [] if r.get(self.UNIT)]
        if not pinned:
            return None
        return (
            "Eine bestimmte Einzelinstanz lässt sich nur im Auftrag vormerken, nicht im "
            "Erzeugungsprozess des Artikels: der läuft für jeden künftigen Auftrag "
            f"erneut, und {pinned[0][self.UNIT]} gibt es nur einmal."
        )

    @staticmethod
    def _one(row: Any) -> tuple[int, int, Optional[str]]:
        """Eine Zeile prüfen: **Artikel + Menge pro Stück**, beide Pflicht.

        Die **Vormerkung** ist optional und nur bei Menge 1 zulässig – eine genannte
        Einzelinstanz ist ein Stück.
        """
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
        unit = str(row.get(Verbrauch.UNIT) or "").strip() or None
        if unit and quantity != 1:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Artikel {article}: {unit} ist **eine** Einzelinstanz – dann ist "
                    f"die Menge 1. «{quantity}× dieses eine Stück» gibt es nicht."
                ),
            )
        return article, quantity, unit

    def exit_status_for(self, config: Optional[dict[str, Any]]) -> Optional[str]:
        """Der Zustand der **Komponenten**, die dieses Modul zieht.

        Nicht der der ankommenden Stücke: die laufen weiter (``status_after``). Das ist
        der ganze Unterschied zum Aussondern – dort ist beides dasselbe, weil dort nichts
        weiterläuft.
        """
        return st.VERBAUT


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


def lines_of(config: Optional[dict[str, Any]]) -> list[dict[str, Any]]:
    """Die **Stückliste** eines Moduls — je Zeile Artikel, Menge pro Stück, Vormerkung.

    Nur der Verbrauch hat eine; überall sonst ist sie leer. Ein Modul, das keine kennt,
    gibt darum nicht ``None`` zurück, sondern nichts – die Aufrufstelle fragt dann gar
    nicht erst nach einer Fallunterscheidung.

    ``unit`` ist die vorgemerkte Einzelinstanz oder ``None`` (Testnotiz #721) – die eine
    Lesestelle, damit «gibt es hier eine Vormerkung?» nicht an fünf Orten aus dem rohen
    Wörterbuch gelesen wird.
    """
    return [
        {
            "article": int(row["article"]),
            "quantity": int(row["quantity"]),
            Verbrauch.UNIT: str(row.get(Verbrauch.UNIT) or "").strip() or None,
        }
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
