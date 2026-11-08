"""Phase 3 · KI – Erfassen, Vorschläge, das Angeheftete (nur Personal).

Der Vertrag steht in ``docs/konzept/phase3-bauplan.md`` («API»). Die KI schreibt hier nie selbst:
sie liefert Vorschläge (``proposal``) und Hinweise (``pin``); entschieden und geschrieben wird
nach dem Klick eines Menschen.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..core.auth import require_employee
from ..core.database import DB
from ..models import UserProfile
from ..schemas.proposals import FileIn, IntakeIn, IntakeOut, PinnedOut, AiProposal, SolveIn
from ..services import ai, intake, pins, proposals

router = APIRouter(prefix="/api/v1/erp", tags=["ki"])


@router.post("/intake", response_model=IntakeOut)
def capture(data: IntakeIn, db: Session = DB,
            user: UserProfile = Depends(require_employee)):
    """**Festhalten** – die rohe Eingabe steht sofort im Log (und bleibt, was auch geschieht);
    dann legt die KI ab (höchstens ~45 s, unter der Grenze von Firebase Hosting). Klappt das
    nicht, kommt ein Teil zurück und ``problem`` sagt warum – der Takt holt nach."""
    it = intake.capture(db, data.text, data.hint_object_id, user)
    db.flush()
    with ai.until(50):      # ähnliche Fälle + Ablegen + Bedeutungs-Zahlen: alles unter 60 s
        trouble = intake.file_with_ai(db, it, user)
    db.flush()
    return intake.view(db, it, problem=trouble)


@router.get("/intake/open", response_model=list[IntakeOut])
def open_intakes(db: Session = DB, user: UserProfile = Depends(require_employee)):
    """Meine Erfassungen, die noch nicht abgelegt sind."""
    return intake.open_intakes(db, user)


@router.post("/intake/{intake_id}/file", response_model=IntakeOut)
def file(intake_id: int, data: FileIn, db: Session = DB,
         user: UserProfile = Depends(require_employee)):
    """**«Stimmt so»** – je Teil eine Notiz an seinem Datensatz, dann der Entscheid."""
    it = intake.file(db, intake_id, data.parts, user)
    db.flush()
    return intake.view(db, it)


@router.post("/intake/{intake_id}/discard", response_model=IntakeOut)
def discard(intake_id: int, db: Session = DB,
            user: UserProfile = Depends(require_employee)):
    """**«Verwerfen»** – nicht ablegen; was aus ihr folgte, geht mit."""
    it = intake.discard(db, intake_id, user)
    db.flush()
    return intake.view(db, it)


@router.get("/proposals", response_model=list[AiProposal])
def open_proposals(object_id: int = Query(...), db: Session = DB,
                   user: UserProfile = Depends(require_employee)):
    """Die offenen Vorschläge an diesem Datensatz."""
    return proposals.open_for(db, object_id, user)


@router.post("/proposals/{proposal_id}/reject", response_model=AiProposal)
def reject(proposal_id: int, db: Session = DB,
           user: UserProfile = Depends(require_employee)):
    """✕ – verworfen."""
    p = proposals.reject(db, proposal_id, user)
    db.flush()
    return proposals.out(db, [p])[0]


@router.get("/pins/{object_id}", response_model=PinnedOut)
def pinned(object_id: int, db: Session = DB,
           user: UserProfile = Depends(require_employee)):
    """Das Angeheftete: offene Vorschläge (immer, zuerst), dann die Hinweise der KI."""
    return pins.pinned(db, object_id, user)


@router.post("/pins/{object_id}/refresh", response_model=PinnedOut)
def refresh(object_id: int, db: Session = DB,
            user: UserProfile = Depends(require_employee)):
    """«Neu ansehen» – die KI wählt die Hinweise neu; offene Vorschläge bleiben."""
    with ai.until(50):
        found = pins.refresh(db, object_id, user)
    db.flush()
    return found


@router.post("/pins/{object_id}/solve", response_model=PinnedOut)
def solve(object_id: int, data: SolveIn, db: Session = DB,
          user: UserProfile = Depends(require_employee)):
    """Einen Hinweis lösen."""
    found = pins.solve(db, object_id, data.key, user)
    db.flush()
    return found
