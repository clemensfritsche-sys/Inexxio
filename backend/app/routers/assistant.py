"""Der Assistent – Gespräch, Vorschlag (im Code: Handgriff), «Auf einen Blick» (nur Personal).

Der Vertrag steht in ``docs/konzept/phase5-bauplan.md``. Die KI führt nie etwas aus: sie bereitet
Vorschläge vor; übernommen wird ein Vorschlag nur von der Person, dort, wo er wirkt – im Entwurf
oder am Datensatz, durch die echte Route, mit ihren Rechten (``services/handgriff``). Was hier
steht, ist selbst keine Handlung für die KI.
"""

from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from ..core.auth import require_employee
from ..core.config import get_settings
from ..core.database import DB
from ..models import UserProfile
from ..schemas.assistant import DoneIn, DoorOut, FileRef, HandgriffOut, PinnedOut, RunOut, TalkIn, TalkOut
from ..services import ai, attachments, handgriff, pins, talk
from ..domain.errors import rejected

router = APIRouter(prefix="/api/v1/erp/assistant", tags=["assistent"])


@router.post("/talks", response_class=StreamingResponse,
             responses={200: {"content": {"application/x-ndjson": {}},
                              "description": "Je Zeile ein JSON: {step} je Schritt, am Ende {talk}."}})
def say(data: TalkIn, db: Session = DB, user: UserProfile = Depends(require_employee)):
    """**Dem Assistenten etwas sagen** – die Nachricht ist gespeichert, bevor die Antwort beginnt;
    dann antwortet die KI live (je Zeile: das Gespräch, ein Schritt oder ein Stück Text, am Ende
    das Gespräch mit Antwort und Vorschlägen)."""
    tid = talk.say(db, user, data.text, talk=data.talk, hint=data.hint_object_id,
                   files=data.files, recordings=data.recordings)
    return StreamingResponse(talk.stream(user.id, tid), media_type="application/x-ndjson",
                             headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"})


@router.post("/talks/{talk_id}/stop", status_code=204)
def stop(talk_id: int, db: Session = DB, user: UserProfile = Depends(require_employee)):
    """**Stopp** – die KI hält vor ihrem nächsten Schritt an; was sie vorbereitete, bleibt."""
    talk.stop(db, user, talk_id)


@router.get("/door", response_model=DoorOut)
def door(user: UserProfile = Depends(require_employee)):
    """Wo das Gespräch live läuft – die direkte Adresse des Dienstes (ohne die 60 s des Hostings);
    leer = dieselbe Adresse wie alles andere."""
    return DoorOut(url=get_settings().backend_url.rstrip("/"))


@router.get("/talks/open", response_model=list[TalkOut])
def open_talks(db: Session = DB, user: UserProfile = Depends(require_employee)):
    """Meine offenen Gespräche – die neuesten zuerst (die Zahl am «+»)."""
    return [talk.view(db, t) for t in talk.open_ids(db, user)]


@router.get("/talks/{talk_id}", response_model=TalkOut)
def get_talk(talk_id: int, db: Session = DB, user: UserProfile = Depends(require_employee)):
    """Ein Gespräch – nur, wer es führt, und der Admin."""
    talk.assert_may(db, talk_id, user)
    return talk.view(db, talk_id)


@router.post("/files", response_model=FileRef)
def add_file(file: UploadFile = File(...), db: Session = DB,
             user: UserProfile = Depends(require_employee)):
    """Eine Datei ins Gespräch (Foto, PDF) – sie liegt im Korb, bis sie ein Dokument wird."""
    raw = file.file.read()
    att = attachments.store_raw(db, raw, file.filename, file.content_type or "")
    return FileRef(token=att.token, name=file.filename or "Datei", mime=att.mime)


@router.get("/handgriffe/{handgriff_id}", response_model=HandgriffOut)
def get_handgriff(handgriff_id: int, db: Session = DB,
                  user: UserProfile = Depends(require_employee)):
    """Ein Handgriff, wie die Karte ihn zeigt."""
    return handgriff.view(db, [handgriff.assert_may(db, handgriff_id, user)])[0]


@router.post("/handgriffe/{handgriff_id}/run", response_model=RunOut)
def run(handgriff_id: int, db: Session = DB, user: UserProfile = Depends(require_employee)):
    """**Übernehmen** – am Datensatz, genau einmal, mit meinen Rechten, durch die echte Route. Geht
    es nicht, sagt der Satz der Route warum (409/4xx)."""
    h, out = handgriff.run(db, user, handgriff_id)
    if not out.ok:
        raise rejected(out.status if out.status >= 400 else 409, out.detail or "Das ging nicht.")
    return RunOut(handgriff=handgriff.view(db, [h])[0], data=out.data)


@router.post("/handgriffe/{handgriff_id}/drop", response_model=HandgriffOut)
def drop(handgriff_id: int, db: Session = DB, user: UserProfile = Depends(require_employee)):
    """**Weg** – der Handgriff geschieht nicht."""
    return handgriff.view(db, [handgriff.drop(db, user, handgriff_id)])[0]


@router.post("/handgriffe/{handgriff_id}/done", response_model=HandgriffOut)
def done(handgriff_id: int, data: DoneIn, db: Session = DB,
         user: UserProfile = Depends(require_employee)):
    """**Von Hand erledigt** – ein Handgriff, der nur von Hand ging (Datei, Entwurf), ist getan."""
    return handgriff.view(db, [handgriff.settle(db, user, handgriff_id, data.result)])[0]


@router.get("/pins/{object_id}", response_model=PinnedOut)
def pinned(object_id: int, db: Session = DB, user: UserProfile = Depends(require_employee)):
    """**Das Angeheftete** – offene Handgriffe (zuerst), dann das Wissen; ``stale`` = im Umfeld
    hat sich seit der letzten Wahl etwas geändert."""
    return pins.pinned(db, object_id, user)


@router.post("/pins/{object_id}/refresh", response_model=PinnedOut)
def refresh(object_id: int, db: Session = DB, user: UserProfile = Depends(require_employee)):
    """Das Wissen neu wählen – nur, wenn sich im Umfeld etwas geändert hat (sonst kein Aufruf)."""
    with ai.until(50):
        return pins.refresh(db, object_id, user)
