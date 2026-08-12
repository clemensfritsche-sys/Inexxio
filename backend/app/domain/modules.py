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

    #: **Endet die Reise hier?** Ein terminales Modul ist kein Durchgang, sondern ein
    #: **Ausgang**: das Stück verlässt den Auftrag an dieser Stelle und geht nicht weiter.
    #:
    #: Daraus folgt zweierlei, beides ohne Fallunterscheidung im Ablauf: hinter ihm kann
    #: kein Modul mehr stehen (es bekäme nie ein Stück – ``_assert_chain`` weist das bei
    #: der Freigabe ab), und es passiert **nicht** das Ende-Objekt (``_finish``), denn es
    #: ist selbst eines. Genau das schneidet auch eine geplante Rückführung ab: die
    #: Rückkehr hängt am Ende-Objekt, und dorthin kommt das Stück nie.
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
        """Auf welchen Zustand setzt dieses Modul? Vorgabe: der des **Typs**.

        Der Übergang gehört weiterhin zum Modultyp und nicht zum Anwender (§14) – aber
        der Typ darf seine eigene Konfiguration lesen. Das ist der Unterschied zwischen
        «welchen Status willst du?» (ein Dropdown, das man falsch ausfüllen kann) und
        «was soll passieren?» (eine fachliche Wahl, aus der der Status **folgt**).
        """
        return self.status_after


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
