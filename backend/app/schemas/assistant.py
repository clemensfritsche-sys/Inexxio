"""Der Assistent (Phase 5): Gespräch und Handgriff – Anfrage und Antwort."""

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
    text: str = Field("", max_length=20000)
    talk: Optional[int] = None
    hint_object_id: Optional[int] = None
    files: list[FileRef] = Field(default_factory=list, max_length=10)


class DoorOut(BaseModel):
    """Die direkte Adresse des Dienstes für das Gespräch live – leer: dieselbe wie sonst."""
    url: str = ""


class HandgriffOut(BaseModel):
    """**Ein Handgriff, wie die Karte ihn zeigt.**"""
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
    #: Geht nur von Hand (Datei, Kamera, Zahlung …) – dann «Öffnen» statt «Ausführen».
    hand: str = ""
    #: Es fehlen Werte, die die Person ergänzt – der Satz der Route; «Ausführen» erst danach
    #: (über «Entwurf öffnen» oder «Ändern»).
    missing: str = ""
    #: Worauf er wartet (Nummern anderer Handgriffe).
    waits_for: list[int] = Field(default_factory=list)
    #: Was die Handlung tut – ihr Satz aus dem ERP.
    summary: str = ""


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


class RunIn(BaseModel):
    """Ausführen – ``body`` nur, wenn die Person die Werte geändert hat («Ändern», Entwurf)."""
    body: Optional[Any] = None


class ProbeOut(BaseModel):
    """Der Probelauf einer geänderten Fassung: geht es – sonst der Satz der Route."""
    ok: bool
    detail: str = ""
    hand: str = ""


class RunOut(BaseModel):
    handgriff: HandgriffOut
    #: Die Antwort der Handlung (was sie angelegt oder geändert hat).
    data: Any = None


class DoneIn(BaseModel):
    """Von Hand erledigt (Entwurf freigegeben, Datei abgelegt) – was dabei entstand."""
    result: Optional[int] = None


class OperationOut(BaseModel):
    """Eine Handlung des ERP – für «Ändern»: ihre Felder (JSON-Schema der Route)."""
    key: str
    summary: str
    admin: bool
    hand: bool
    schema_: dict[str, Any] = Field(default_factory=dict, alias="schema")

    model_config = {"populate_by_name": True}


class KnowledgeOut(BaseModel):
    """Eine Aussage des Wissens am Datensatz – mit Datum und Quelle."""
    text: str
    #: Die Notiz oder das Dokument, auf das sie sich stützt.
    source_object_id: Optional[int] = None
    source_message_id: Optional[int] = None
    at: Optional[datetime] = None


class PinnedOut(BaseModel):
    """**Das Angeheftete** – offene Handgriffe (zuerst), dann das Wissen, das jetzt zählt."""
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
