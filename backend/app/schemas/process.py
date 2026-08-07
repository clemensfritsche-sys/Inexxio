"""Prozessschrittmodule – die API-Form, **einmal** für Artikel und Auftrag.

Es ist derselbe Prozess, nur an zwei Orten (PROCESS_CORE.md §8): am Artikel als Vorlage,
im Auftrag als das, was läuft. Zwei Schemas dafür wären zwei Wahrheiten, die genau so
lange gleich bleiben, bis jemand eines von beiden erweitert.

**Der Übergang steht nicht drin.** Er gehört zum Modultyp (``domain/modules``) und wird
beim Anlegen von dort genommen. Ein Feld dafür wäre eine Eingabe, deren einzige richtige
Antwort schon feststeht – und deren falsche einen Prozess ergäbe, der nicht läuft.
"""

from typing import Any, Optional

from pydantic import BaseModel, Field


class CapturePointInput(BaseModel):
    """Ein Erfassungspunkt, wie ihn die Definition schickt.

    ``key`` fehlt hier mit Absicht: er wird serverseitig aus der Bezeichnung abgeleitet
    (``domain/capture_types._slug``). Ihn eingeben zu lassen wäre ein Feld, dessen Zweck
    man erklären müsste – und dessen Kollisionen der Mensch auflösen müsste.

    ``target``/``tolerance`` sind nur für den Soll-Ist-Vergleich gefüllt. Welche
    Zusatzfelder ein Typ braucht, entscheidet der Typ selbst (``CaptureType.clean``);
    dieses Schema ist bewusst die Aussenform und nicht die Regel.

    Ein ``required``-Feld gibt es **nicht**: alles, was angelegt ist, ist Pflicht.

    **Die Bezeichnung ist hier NICHT schema-pflichtig** (Testnotiz #695). Sie ist es
    fachlich sehr wohl – ohne sie steht im Prozess ein Daumen hoch/runter ohne Frage –,
    aber ein `min_length=1` an dieser Stelle ist eine Prüfung zur **falschen Zeit**: der
    Entwurf legt den Punkt beim Klick auf die Palette an und füllt ihn, während man tippt.
    Jeder Tastendruck ging so durch ``/validate`` und kam als rohe 422 zurück
    («Erfassungspunkte → 1 → Bezeichnung: darf nicht leer sein»), statt als «das fehlt
    noch». Es ist derselbe Fehler, den #682/#686 eine Ebene höher am Modulnamen behoben
    haben – nur war er hier nicht mitgeräumt.

    Verlangt wird sie jetzt dort, wo es zählt: bei der **Freigabe**
    (``domain/capture_types.clean_points``), mit einem Satz statt einem Feldpfad.
    """

    label: str = Field(default="", max_length=120)
    type: str
    target: Optional[float] = None
    tolerance: Optional[float] = None


class ModuleConfigInput(BaseModel):
    """Die Konfiguration eines Moduls. Heute genau ein Feld – geprüft wird sie im Modul."""

    points: list[CapturePointInput] = Field(default_factory=list)


class ModuleInput(BaseModel):
    """Ein Prozessschrittmodul, wie es der Entwurf schickt.

    **Keinen Namen.** Wie ein Modul heisst, sagt sein Typ (``domain/modules``) – ein
    Eingabefeld daneben hätte genau eine richtige Antwort und war trotzdem Pflicht
    (Testnotiz #682). Es war zugleich die Quelle der Meldung «String should have at
    least 1 character»: ein leer gelassenes Feld, das der Anwender gar nicht sehen
    wollte (#686).

    Die **Identität** eines Moduls ist seine ``id``, vergeben beim Anlegen (#687) – sie
    steht hier nicht, weil der Entwurf noch keine hat.
    """

    module_type: str
    config: Optional[ModuleConfigInput] = None


class ModuleTypeInfo(BaseModel):
    """Ein wählbarer Modultyp – für die Oberfläche, damit sie die Liste nicht nachbaut.

    ``tone`` ist die **Farbfamilie** des Modultyps (``domain/modules``). Sie kommt mit,
    weil sie zum Modul gehört: ein neuer Typ soll ein Eintrag in der Registry sein und
    kein Eingriff in die Oberfläche.
    """

    key: str
    label: str
    tone: str
    status_before: str
    status_after: str


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


class StepConfirm(BaseModel):
    """«Bestätigen» an einem Modul: die erfassten Werte, geschlüsselt nach Punkt-``key``.

    Ein Modul ohne Erfassungspunkte bekommt einen leeren Satz – erlaubt ist das trotzdem
    nicht, weil es ein solches Modul nicht gibt (``clean_points`` verlangt mindestens
    einen).
    """

    values: dict[str, Any] = Field(default_factory=dict)
