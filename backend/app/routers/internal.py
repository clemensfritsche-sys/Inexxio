"""Interne Türen – nur für Google, nie für einen Browser. Heute eine: **der Takt**."""

from dataclasses import asdict

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from ..core.oidc import require_tick
from ..schemas.tick import TickOut
from ..services import tick

router = APIRouter(prefix="/api/v1/internal", tags=["internal"])


@router.post("/tick", response_model=TickOut, dependencies=[Depends(require_tick)],
             responses={500: {"model": TickOut, "description": "Eine Aufgabe scheiterte"}})
def run_tick():
    """**Der Takt** (Cloud Scheduler, alle 5 Minuten): jede Aufgabe aus ``tick.TASKS`` einmal
    – je ``ok`` · ``skipped`` (läuft anderswo, keine Zeit mehr) · ``failed``. Scheitert eine,
    antwortet er mit 500, damit Cloud Scheduler den Fehlschlag zählt (Alarm nach mehreren
    hintereinander, ``infra/setup-takt.sh``); die übrigen sind trotzdem gelaufen."""
    out = TickOut(tasks=[asdict(o) for o in tick.run()])
    failed = any(t.state == "failed" for t in out.tasks)
    return JSONResponse(out.model_dump(), status_code=500 if failed else 200)
