"""Die Website-Statistik (``services/site_stats``): die Meldung jeder Seite und die Auswertung."""

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from ..core.actor import public
from ..core.auth import require_employee
from ..core.database import DB
from ..models import UserProfile
from ..schemas.site_stats import SiteStatsOut
from ..services import site_stats, site_stats_view, visitor

router = APIRouter(tags=["site-stats"])

#: Meldungen je Absender und Stunde – grosszügig (eine Seite meldet bis zu sechs Dinge).
PER_SENDER = 600
#: Meldungen insgesamt je Stunde und Instanz.
TOTAL = 30_000


@router.post("/api/v1/public/page", status_code=204, dependencies=[public("web")])
async def page_seen(request: Request, db: Session = DB) -> Response:
    """Eine Seite der Website meldet sich (Ansicht, Lesezeit, Klick, Formular, Ladezeit) – ohne Cookie, die IP wird nicht gespeichert."""
    data = site_stats.parse(await request.body())
    if data is not None and visitor.allow_send("page", request, PER_SENDER, total=TOTAL):
        await run_in_threadpool(site_stats.record, db, site_stats.who(request), data, visitor.country(request))
    return Response(status_code=204, headers={"Cache-Control": "no-store"})


@router.get("/api/v1/erp/site-stats", response_model=SiteStatsOut)
def read_site_stats(days: int = 30, db: Session = DB, _: UserProfile = Depends(require_employee)):
    """Die Statistik der Website für einen Zeitraum (7, 30, 90 oder 365 Tage bis heute): Besuche, Quellen, Seiten, Länder, Formular, Ladezeit, Anfragen."""
    return site_stats_view.view(db, days)
