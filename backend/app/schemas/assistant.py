"""Der Assistent: Gespräch und Vorschlag (im Code: Handgriff) – Anfrage und Antwort."""

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class FileRef(BaseModel):
    """Eine Datei im Gespräch – sie liegt im Korb (``attachments``), bis sie ein Dokument wird."""
    token: str
    name: str
    mime: str


class TalkIn(BaseModel):
    """**Eine Nachricht an den Assistenten.** Ohne ``talk`` beginnt ein neues Gespräch – am
    offenen Datensatz (``hint_object_id``), sonst an der Person."""
    #: Getippt höchstens 20'000 Zeichen; mit einer Aufnahme mehr (``talk.MAX_SPOKEN``).
    text: str = Field("", max_length=200_000)
    talk: Optional[int] = None
    hint_object_id: Optional[int] = None
    files: list[FileRef] = Field(default_factory=list, max_length=10)
    #: Die Aufnahme, deren abgeschriebener Text in dieser Nachricht steht (die Person hat ihn in
    #: der Eingabe ergänzt und selbst geschickt).
    recording: Optional[int] = None


class DoorOut(BaseModel):
    """Die direkte Adresse des Dienstes für das Gespräch live – leer: dieselbe wie sonst."""
    url: str = ""


class Change(BaseModel):
    """Was ein Vorschlag an einem Feld ändert – wie es jetzt ist und wie es würde."""
    field: str
    before: str = ""
    after: str = ""


class HandgriffOut(BaseModel):
    """**Ein Vorschlag, wie die Oberfläche ihn zeigt** – im Gespräch mit «Öffnen», am Datensatz
    mit «Übernehmen» (oder im Entwurf)."""
    id: int
    at: datetime
    object_id: int
    #: Der Name des Datensatzes, den er betrifft (die Nummer ist ``object_id``).
    label: str
    #: Eine Zeile: was geschieht.
    line: str
    method: str
    path: str
    body: Any = None
    #: ``open`` · ``waiting`` (auf einen anderen Handgriff) · ``done`` · ``dropped``.
    state: Literal["open", "waiting", "done", "dropped"]
    #: Was er angelegt hat (bei ``done``), sonst ``None``.
    result: Optional[int] = None
    #: Woher: «Gespräch» oder «Mail von …: Betreff».
    source: str
    talk: Optional[int] = None
    #: Worauf er wartet (Nummern anderer Vorschläge).
    waits_for: list[int] = Field(default_factory=list)
    #: Was die Handlung tut – ihr Satz aus dem ERP.
    summary: str = ""
    #: Ändert er einen Datensatz: je Feld alt → neu, wie es jetzt ist (``handgriff.changes_of``).
    changes: list[Change] = Field(default_factory=list)


class TalkMessage(BaseModel):
    id: int
    at: datetime
    by: Literal["person", "ai"]
    text: str
    files: list[FileRef] = Field(default_factory=list)


class TalkOut(BaseModel):
    """**Ein Gespräch** – seine Nachrichten und Handgriffe, der Reihe nach."""
    id: int
    at: datetime
    hint_object_id: Optional[int] = None
    messages: list[TalkMessage]
    handgriffe: list[HandgriffOut]
    #: Offen: ein Handgriff ist offen, oder die KI hat noch nicht geantwortet.
    open: bool
    #: Die KI hat noch nicht geantwortet (ausgefallen, Deckel) – der Takt holt nach.
    waiting: bool = False
    problem: Optional[str] = None


class RunOut(BaseModel):
    handgriff: HandgriffOut
    #: Die Antwort der Handlung (was sie angelegt oder geändert hat).
    data: Any = None


class DoneIn(BaseModel):
    """Im Entwurf erledigt (freigegeben) – was dabei entstand."""
    result: Optional[int] = None


class KnowledgeOut(BaseModel):
    """Eine Aussage des Wissens am Datensatz – mit Datum und Quelle."""
    text: str
    #: Die Notiz oder das Dokument, auf das sie sich stützt.
    source_object_id: Optional[int] = None
    source_message_id: Optional[int] = None
    at: Optional[datetime] = None


class PinnedOut(BaseModel):
    """**Auf einen Blick** – offene Vorschläge am Datensatz (zuerst), dann das Wissen, das jetzt
    zählt."""
    handgriffe: list[HandgriffOut]
    knowledge: list[KnowledgeOut]
    #: Wann das Wissen gewählt wurde; ``stale`` = im Umfeld hat sich seither etwas geändert –
    #: ``POST …/refresh`` wählt neu (die Oberfläche ruft es von selbst).
    chosen_at: Optional[datetime] = None
    stale: bool = False
    #: Der Stand des Umfelds (die jüngste Änderung, eine Log-Id) – je Stand fragt die Oberfläche
    #: höchstens einmal neu.
    mark: int = 0
    problem: Optional[str] = None
