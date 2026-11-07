"""Phase 4 · Sprache – Aufnehmen und Abschreiben (nur Personal).

Der Vertrag steht in ``docs/konzept/phase4-bauplan.md`` («API»). Eine Aufnahme gehört der Person,
die aufnimmt: nur sie (und der Admin) sieht sie, Stücke und Stopp schickt nur sie. Abgeschrieben
wird in ``advance`` – hier in der Anfrage, ohne Browser im Takt (``services/tick``).
"""

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.orm import Session

from ..core.auth import require_employee
from ..core.database import get_db
from ..models import UserProfile
from ..schemas.recordings import Recording, RecordingIn, StopIn
from ..services import ai, recordings

router = APIRouter(prefix="/api/v1/erp", tags=["ki"])


@router.post("/recordings", response_model=Recording)
def start(data: RecordingIn, db: Session = Depends(get_db),
          user: UserProfile = Depends(require_employee)):
    """**Eine Aufnahme beginnt** – am offenen Datensatz (Hinweis), sonst an der Person."""
    rec = recordings.start(db, data.hint_object_id, data.mime, user, data.context or "")
    db.commit()
    return recordings.view(db, rec, user)


@router.get("/recordings/open", response_model=list[Recording])
def open_recordings(db: Session = Depends(get_db), user: UserProfile = Depends(require_employee)):
    """Meine Aufnahmen, die nicht fertig sind."""
    return recordings.open_for(db, user)


@router.post("/recordings/{recording_id}/chunks", response_model=Recording)
def chunk(recording_id: int, segment: int = Form(...), seq: int = Form(...),
          file: UploadFile = File(...), db: Session = Depends(get_db),
          user: UserProfile = Depends(require_employee)):
    """**Ein Stück** (alle 30 s) – höchstens 4 MB; dasselbe Stück zweimal ersetzt es."""
    raw = file.file.read(recordings.MAX_CHUNK + 1)
    rec = recordings.add_chunk(db, recording_id, segment, seq, raw, user)
    db.commit()
    return recordings.view(db, rec, user)


@router.post("/recordings/{recording_id}/stop", response_model=Recording)
def stop(recording_id: int, data: StopIn, db: Session = Depends(get_db),
         user: UserProfile = Depends(require_employee)):
    """**Stopp** – mit der Zahl der Abschnitte."""
    rec = recordings.stop(db, recording_id, data.segments, user)
    db.commit()
    return recordings.view(db, rec, user)


@router.post("/recordings/{recording_id}/advance", response_model=Recording)
def advance(recording_id: int, db: Session = Depends(get_db),
            user: UserProfile = Depends(require_employee)):
    """**Weiter abschreiben**, so weit die Zeit reicht (unter den 60 s von Firebase Hosting) –
    die Oberfläche fragt nach, bis ``state`` ``done`` oder ``failed`` ist."""
    recordings.get(db, recording_id, user)
    with ai.until(50):
        trouble = recordings.advance(db, recording_id)
    db.commit()
    return recordings.view(db, recordings.load(db, recording_id), user, problem=trouble)


@router.post("/recordings/{recording_id}/dismiss", response_model=Recording)
def dismiss(recording_id: int, db: Session = Depends(get_db),
            user: UserProfile = Depends(require_employee)):
    """**Verwerfen** – eine gescheiterte Aufnahme verschwindet aus dem «+»."""
    rec = recordings.dismiss(db, recording_id, user)
    db.commit()
    return recordings.view(db, rec, user)
