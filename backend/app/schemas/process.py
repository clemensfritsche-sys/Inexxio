"""Prozessschrittmodule – die API-Form, **einmal** für Artikel und Auftrag.

Es ist derselbe Prozess, nur an zwei Orten (PROCESS_CORE.md §8): am Artikel als Vorlage,
im Auftrag als das, was läuft. Zwei Schemas dafür wären zwei Wahrheiten, die genau so
lange gleich bleiben, bis jemand eines von beiden erweitert.

**Der Übergang steht nicht drin.** Er gehört zum Modultyp (``domain/modules``) und wird
beim Anlegen von dort genommen. Ein Feld dafür wäre eine Eingabe, deren einzige richtige
Antwort schon feststeht – und deren falsche einen Prozess ergäbe, der nicht läuft.
"""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, computed_field

from ..domain import modules


class ModuleFacts(BaseModel):
    """**Was ein gespeicherter Schritt aus der Registry mitbringt** – für beide Orte.

    Beschriftung, Farbfamilie und «ist das ein Ausgang?» hängen ausschliesslich am
    Modultyp (``domain/modules``). Sie stehen darum hier und werden **abgeleitet**, nie
    gespeichert: eine Spalte daneben wäre eine zweite Aussage darüber, was dieses Modul
    ist, und die erste falsche Eingabe liesse beide auseinanderlaufen.

    **Die Farbe reist mit dem Schritt.** Vorher tat sie das nicht: die Oberfläche holte
    sie aus dem Modul-Katalog, und den lädt nur der Editor. Im **freigegebenen** Auftrag
    stand darum keine Farbe zur Verfügung, und ein stiller Rückfall machte jedes Modul zu
    dem Ton, der zufällig der erste in der Liste war – die Aussonderung sah nach dem
    Freigeben aus wie eine Datenerfassung. Als Feld der Antwort kann sie nicht mehr
    fehlen; ein Aufrufer, der sie vergisst, ist nicht mehr möglich.
    """

    model_config = ConfigDict(from_attributes=True)

    module_type: str

    @computed_field  # type: ignore[prop-decorator]
    @property
    def label(self) -> str:
        """Wie das Modul heisst – aus der Registry, nicht aus einer Spalte."""
        return modules.label(self.module_type)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def tone(self) -> str:
        """Die Farbfamilie des Modultyps. Ein Wort; die Werte kennt die Oberfläche."""
        return modules.get(self.module_type).tone

    @computed_field  # type: ignore[prop-decorator]
    @property
    def terminal(self) -> bool:
        """Ist dies ein **Ausgang**? Dann steht dahinter nichts mehr – und kein Ende."""
        return modules.get(self.module_type).terminal


class ModuleInput(BaseModel):
    """Ein Prozessschrittmodul, wie es der Entwurf schickt.

    **Keinen Namen.** Wie ein Modul heisst, sagt sein Typ (``domain/modules``) – ein
    Eingabefeld daneben hätte genau eine richtige Antwort und war trotzdem Pflicht
    (Testnotiz #682). Es war zugleich die Quelle der Meldung «String should have at
    least 1 character»: ein leer gelassenes Feld, das der Anwender gar nicht sehen
    wollte (#686).

    Die **Identität** eines Moduls ist seine ``id``, vergeben beim Anlegen (#687) – sie
    steht hier nicht, weil der Entwurf noch keine hat.

    **Die Konfiguration ist bewusst ein freier Satz Werte.** Was darin stehen darf,
    entscheidet der Modultyp (``domain/modules.Module.clean_config``) – und *nur* er.
    Eine Feldliste hier wäre eine zweite Aussage darüber, und sie war es auch: sie kannte
    ``points`` und sonst nichts, also verwarf Pydantic beim Eintreffen stillschweigend
    ``mode`` (Verschrotten ↔ Sperren) und ``sample`` (die Stichprobe). Beide Angaben
    kamen nie an, beide Vorgaben galten immer – ohne eine einzige Fehlermeldung.
    Geprüft wird jetzt dort, wo die Regel steht, mit einem Satz statt einem Feldpfad.
    """

    module_type: str
    config: Optional[dict[str, Any]] = None


class ModuleTypeInfo(BaseModel):
    """Ein wählbarer Modultyp – für die Oberfläche, damit sie die Liste nicht nachbaut.

    ``tone`` ist die **Farbfamilie** des Modultyps (``domain/modules``). Sie kommt mit,
    weil sie zum Modul gehört: ein neuer Typ soll ein Eintrag in der Registry sein und
    kein Eingriff in die Oberfläche.

    ``terminal`` sagt, dass hinter diesem Modul nichts mehr stehen kann – es ist ein
    **Ausgang**, kein Durchgang. Es ist dieselbe Eigenschaft, aus der die Freigabe ihren
    Fehler zieht (``domain/chain``) und das Prozessbild sein Ende; die Oberfläche bietet
    daraufhin gar nicht erst an, etwas dahinter zu setzen. Eine Regel, drei Wirkungen –
    ein neuer Modultyp erbt alle drei, ohne eine Zeile dafür.
    """

    key: str
    label: str
    tone: str
    terminal: bool = False
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
    #: **Worin wird gemessen?** (mm · kg · °C …) Ein freies, kurzes Wort – bewusst keine
    #: Liste: die Mengeneinheiten des Artikels beantworten eine andere Frage (siehe
    #: ``domain/capture_types/measure``), und eine zweite Liste wäre endlos.
    unit: Optional[str] = None


class StepConfirm(BaseModel):
    """«Bestätigen» an einem Modul — **ein Wertesatz je Einzelinstanz**.

    ``values`` ist zweistufig: **Nummer der Einzelinstanz** → (Punkt-``key`` → Wert).
    Erwartet wird genau ein Satz je **gezogenem** Stück; zu viele oder zu wenige werden
    abgewiesen (``process._captures_for``).

    **Der Scan verifiziert die Instanz, die Erfassung gilt der Einzelinstanz.** Beides
    hier nebeneinander zu haben ist der ganze Punkt: ``instance_object_id`` ist die
    verifizierte Instanz (eine – das Etikett klebt am physischen Ding),
    ``values`` sind ihre n Messungen. Wäre es ein flacher Satz, entstünden aus einer
    Messung n gleiche Zeilen, und der Nachweis behauptete Messungen, die niemand gemacht
    hat.

    Ein Modul ohne Erfassungspunkte (Aussondern) bekommt einen **leeren** Satz – dort ist
    der Scan die Bestätigung, und ein Wert wäre ein Nachweis über nichts.

    ``verification`` sagt **wie** verifiziert wurde – gescannt oder von Hand eingegeben.
    Beides ist eine Bestätigung, und beides steht im Log; ohne den Vermerk wäre die
    Tastatur eine stille Umgehung der Scan-Pflicht statt ihrer Alternative.

    ``sources`` sind die Instanzen, aus denen ein **Verbrauchsmodul** nehmen soll – die
    Kisten, die der Lagerist gescannt hat. Es ist bewusst **keine Mengenangabe**: wie
    viel gebraucht wird, sagt die Stückliste des Moduls, und eine zweite Stelle dafür
    wäre ein zweiter Massstab. Leer heisst «der ganze freie Bestand, älteste zuerst».
    """

    values: dict[str, dict[str, Any]] = Field(default_factory=dict)
    instance_object_id: Optional[int] = None
    verification: Optional[str] = None
    sources: list[int] = Field(default_factory=list)


class StepConfirmResult(BaseModel):
    """Was das Bestätigen bewirkt hat – die Antwort auf «und jetzt?».

    ``held`` ist der Fall, den es vorher nicht gab: erfasst, **nicht bestanden**, nichts
    vorgerückt. Die Zahl daneben ist die Auskunft, dass genau so viele Stücke jetzt an
    diesem Modul warten, bis jemand entscheidet.
    """

    moved: int = 0
    held: int = 0
    result: Optional[str] = None


class RecordValue(BaseModel):
    """Ein erfasster Wert — **mit seiner Frage**, nicht nur mit seinem Schlüssel."""

    key: str
    label: str
    type: str
    value: Any = None
    #: Das Urteil dieses Punktes. ``None`` heisst «hier war nichts zu beurteilen» – ein
    #: Foto belegt, es bewertet nicht.
    ok: Optional[bool] = None


class RecordEntry(BaseModel):
    """Ein Vorgang an einem Modul, an **einer** Einzelinstanz.

    Ein Stück kann dasselbe Modul mehrfach passieren (nach einem «nicht bestanden» wird
    erneut erfasst) – dann stehen hier mehrere Einträge. Zusammengefasst würde die
    Wiederholung die Vergangenheit überschreiben.
    """

    number: str
    at: datetime
    actor: Optional[str] = None
    verification: Optional[str] = None
    #: Der Zustand **nach** dem Vorgang. ``None`` = nichts rückte vor («nicht bestanden»).
    status_after: Optional[str] = None
    result: Optional[str] = None
    #: ``False`` heisst: ausserhalb der Ziehung durchgelaufen, ohne Erfassung.
    sampled: bool = True
    #: Nur beim Verbrauch: die Nummer des Stücks, in das hier verbaut wurde.
    into: Optional[str] = None
    values: list[RecordValue] = Field(default_factory=list)


class StepRecord(BaseModel):
    """**Was an diesem Modul passiert ist** – seitenweise, mit ehrlicher Gesamtzahl."""

    entries: list[RecordEntry] = Field(default_factory=list)
    total: int = 0


class HoldNumbers(BaseModel):
    """Die Nummern einer Entscheidungs-Gruppe – Vorauswahl für einen Auftragsentwurf."""

    numbers: list[str] = Field(default_factory=list)
