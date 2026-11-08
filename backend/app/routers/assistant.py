"""Phase 5 · Der Assistent – Gespräch, Handgriff, das Angeheftete (nur Personal).

Der Vertrag steht in ``docs/konzept/phase5-bauplan.md``. Die KI führt hier nichts von sich aus
aus: sie bereitet Handgriffe vor; ausgeführt wird nur, was die Person tippt oder sagt – durch die
echte Route, mit ihren Rechten (``services/handgriff``). Was hier steht, ist selbst kein
Handgriff (der Assistent bereitet nichts an sich selbst vor).
"""

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from ..core.auth import require_employee
from ..core.config import get_settings
from ..core.database import DB
from ..models import UserProfile
from ..schemas.assistant import (DoneIn, DoorOut, FileRef, HandgriffOut, OperationOut, PinnedOut, ProbeOut,
                                 RunIn, RunOut, TalkIn, TalkOut)
from ..services import ai, attachments, handgriff, pins, talk

router = APIRouter(prefix="/api/v1/erp/assistant", tags=["assistent"])


@router.post("/talks", response_class=StreamingResponse,
             responses={200: {"content": {"application/x-ndjson": {}},
                              "description": "Je Zeile ein JSON: {step} je Schritt, am Ende {talk}."}})
def say(data: TalkIn, db: Session = DB, user: UserProfile = Depends(require_employee)):
    """**Dem Assistenten etwas sagen** – die Nachricht ist gespeichert, bevor die Antwort beginnt;
    dann antwortet die KI live (je Zeile ein Schritt, am Ende das Gespräch). Ohne Text, aber mit
    ``talk``: die KI antwortet auf das, was schon dasteht (nach einer Aufnahme)."""
    if data.text.strip() or data.files:
        tid = talk.say(db, user, data.text, talk=data.talk, hint=data.hint_object_id,
                       files=data.files)
    elif data.talk is not None:
        tid = talk.assert_may(db, data.talk, user).id
    else:
        raise HTTPException(400, detail="Eine Nachricht braucht Text oder eine Datei.")
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


@router.get("/handgriffe/{handgriff_id}/operation", response_model=OperationOut)
def operation_of(handgriff_id: int, db: Session = DB,
                 user: UserProfile = Depends(require_employee)):
    """Die Handlung hinter einem Handgriff – ihre Felder für «Ändern» (aus der Route)."""
    h = handgriff.assert_may(db, handgriff_id, user)
    op = handgriff.operation_for(h.payload["method"], handgriff.fill_or_raw(h.payload["path"]))
    if op is None:
        raise HTTPException(410, detail="Diese Handlung gibt es im ERP nicht mehr.")
    return OperationOut(key=op.key, summary=op.summary, admin=op.admin, hand=op.hand, schema=op.schema)


@router.post("/handgriffe/{handgriff_id}/run", response_model=RunOut)
def run(handgriff_id: int, data: RunIn, db: Session = DB,
        user: UserProfile = Depends(require_employee)):
    """**Ausführen** – genau einmal, mit meinen Rechten, durch die echte Route. ``body`` nur, wenn
    ich die Werte geändert habe. Geht es nicht, sagt der Satz der Route warum (409/4xx)."""
    h, out = handgriff.run(db, user, handgriff_id, data.body)
    if not out.ok:
        raise HTTPException(out.status if out.status >= 400 else 409,
                            detail=out.detail or f"Das geht nur von Hand ({out.hand}).")
    return RunOut(handgriff=handgriff.view(db, [h])[0], data=out.data)


@router.post("/handgriffe/{handgriff_id}/probe", response_model=ProbeOut)
def probe(handgriff_id: int, data: RunIn, db: Session = DB,
          user: UserProfile = Depends(require_employee)):
    """Eine geänderte Fassung prüfen («Ändern») – der Probelauf derselben Route, nichts bleibt."""
    out = handgriff.probe(db, user, handgriff_id, data.body)
    return ProbeOut(ok=out.ok, detail=out.detail, hand=out.hand)


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
