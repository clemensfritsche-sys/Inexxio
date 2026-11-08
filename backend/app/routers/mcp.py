"""►►► **MCP – das ERP für den eigenen Claude der Person** (``services/mcp``, ``docs/konzept/mcp.md``). ◄◄◄

* ``/.well-known/oauth-protected-resource`` · ``/.well-known/oauth-authorization-server`` – wo und
  wie man sich anmeldet (das Hosting leitet ``/.well-known/oauth-*`` hierher).
* ``/api/v1/mcp/oauth/register`` · ``/authorize`` · ``/token`` – OAuth 2.1 für jeden Claude-Client.
* ``/api/v1/mcp/oauth/request`` · ``/approve`` – die Seite «Claude verbinden» im ERP (angemeldet).
* ``/api/v1/mcp`` – das Protokoll (JSON-RPC, ein ``POST``).
* ``/api/v1/auth/me/mcp`` – meine Verbindungen, trennen.
"""

from typing import Any

from fastapi import APIRouter, Body, Depends, Form, Request
from fastapi.responses import JSONResponse, RedirectResponse, Response
from sqlalchemy.orm import Session

from ..core.actor import act, public
from ..core.auth import require_employee
from ..core.database import DB
from ..models import UserProfile
from ..schemas.mcp import ApproveIn, ApproveOut, AskOut, GrantOut
from ..services import mcp

router = APIRouter(tags=["mcp"])

_NO_STORE = {"Cache-Control": "no-store"}


def _problem(p: mcp.Problem) -> JSONResponse:
    headers = dict(_NO_STORE)
    if p.status == 401 and p.error == "invalid_token":
        headers["WWW-Authenticate"] = (f'Bearer resource_metadata="{mcp.resource_metadata_url()}", '
                                       f'error="invalid_token", error_description="{p.description}"')
    return JSONResponse(p.body(), status_code=p.status, headers=headers)


# --- Metadaten (öffentlich, ohne Datenbank) ---------------------------------

@router.get("/.well-known/oauth-protected-resource", include_in_schema=False)
@router.get("/.well-known/oauth-protected-resource/api/v1/mcp", include_in_schema=False)
def protected_resource():
    """Wo man sich für das ERP anmeldet (RFC 9728)."""
    return mcp.protected_resource()


@router.get("/.well-known/oauth-authorization-server", include_in_schema=False)
@router.get("/.well-known/openid-configuration", include_in_schema=False)
def authorization_server():
    """Wie man sich anmeldet (RFC 8414)."""
    return mcp.authorization_server()


# --- OAuth ------------------------------------------------------------------

@router.post("/api/v1/mcp/oauth/register", include_in_schema=False)
async def register(request: Request):
    """Ein Claude-Client meldet sich an (RFC 7591) – nichts wird gespeichert."""
    try:
        data = await request.json()
    except ValueError:
        data = None
    try:
        return JSONResponse(mcp.register(data if isinstance(data, dict) else {}), status_code=201,
                            headers=_NO_STORE)
    except mcp.Problem as p:
        return _problem(p)


@router.get("/api/v1/mcp/oauth/authorize", include_in_schema=False)
def authorize(request: Request):
    """Weiter zur Seite «Claude verbinden» im ERP – oder ein Satz, warum nicht."""
    try:
        return RedirectResponse(mcp.ask(dict(request.query_params)), status_code=302)
    except mcp.Problem as p:
        return _problem(p)


@router.post("/api/v1/mcp/oauth/token", include_in_schema=False, dependencies=[public("mcp")])
def token(grant_type: str = Form(""), code: str = Form(""), client_id: str = Form(""),
          redirect_uri: str = Form(""), code_verifier: str = Form(""), refresh_token: str = Form(""),
          db: Session = DB):
    """Code oder Erneuerung gegen Zugang."""
    form = {"grant_type": grant_type, "code": code, "client_id": client_id,
            "redirect_uri": redirect_uri, "code_verifier": code_verifier,
            "refresh_token": refresh_token}
    try:
        return JSONResponse(mcp.token(db, form), headers=_NO_STORE)
    except mcp.Problem as p:
        return _problem(p)


@router.get("/api/v1/mcp/oauth/request", response_model=AskOut)
def request_of(r: str, user: UserProfile = Depends(require_employee)):
    """Welcher Claude-Client verbunden werden will und wohin er zurückkehrt."""
    try:
        return mcp.describe(r)
    except mcp.Problem as p:
        return _problem(p)


@router.post("/api/v1/mcp/oauth/approve", response_model=ApproveOut)
def approve(data: ApproveIn, user: UserProfile = Depends(require_employee)):
    """Claude verbinden (oder nicht) – die Antwort ist die Adresse zurück zum Client."""
    try:
        return {"redirect": mcp.approve(user, data.r, data.allow)}
    except mcp.Problem as p:
        return _problem(p)


# --- Das Protokoll ----------------------------------------------------------

@router.post("/api/v1/mcp", include_in_schema=False, dependencies=[public("mcp")])
def protocol(request: Request, msg: Any = Body(None), db: Session = DB):
    """JSON-RPC als die Person, deren Zugang mitkommt."""
    try:
        person, grant = mcp.bearer(db, request.headers.get("authorization"))
    except mcp.Problem as p:
        return _problem(p)
    act(db, "person", person.object_id, "mcp")
    out = mcp.handle(db, person, grant, msg)
    return Response(status_code=202) if out is None else JSONResponse(out)


@router.get("/api/v1/mcp", include_in_schema=False)
def protocol_stream():
    """Einen Strom vom Server gibt es nicht (alles kommt als Antwort auf ein ``POST``)."""
    return Response(status_code=405, headers={"Allow": "POST"})


# --- Meine Verbindungen -----------------------------------------------------

@router.get("/api/v1/auth/me/mcp", response_model=list[GrantOut])
def my_grants(db: Session = DB, user: UserProfile = Depends(require_employee)):
    """Meine Verbindungen mit Claude – je erlaubtem Client eine."""
    return mcp.grants(db, user)


@router.post("/api/v1/auth/me/mcp/{grant_id}/revoke", response_model=list[GrantOut])
def revoke(grant_id: int, db: Session = DB, user: UserProfile = Depends(require_employee)):
    """Eine Verbindung mit Claude trennen – ab sofort kommt dieser Client nicht mehr hinein."""
    try:
        mcp.revoke(db, user, grant_id)
    except mcp.Problem as p:
        return _problem(p)
    db.flush()
    return mcp.grants(db, user)
