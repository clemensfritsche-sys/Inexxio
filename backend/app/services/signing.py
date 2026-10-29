"""►►► **Senden und Unterschreiben – ein Dokument nach aussen.** ◄◄◄

* **Senden** (``send``): je Empfänger ein Link (``document_links``), **ohne Ablauf**, und eine
  Mail im Verlauf der Person – über das Postfach des Betreibers, wie jede Mail des Hauses
  (ohne Postfach wird sie nur erfasst).
* **Unterschreiben** (``sign`` · ``decline``): wer einen Link hat und als Unterzeichner
  verlangt ist, unterschreibt (ein Zug auf dem Bildschirm) oder lehnt ab, mit Grund. Beides
  ist endgültig; **«Abgelehnt» ist das Ende** – danach unterschreibt niemand mehr.
* **Die Unterschrift steht auf dem Papier** (``signed_html``): das eingefrorene Papier trägt
  je Unterzeichner eine Marke; gezeigt wird es mit den Unterschriften darin. Gültig ist erst
  die Fassung, auf der alle stehen (Zustand ``Freigegeben``) – das Papier selbst ändert sich
  nie.
* **Gelöscht** führt ein alter Link auf einen Hinweis (410) – nie auf einen Fehler.
"""

from __future__ import annotations

import base64
import io
import secrets
from datetime import datetime, timezone
from html import escape
from typing import Any, Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..core import clock
from ..core.config import get_settings
from ..domain import communication as dc
from ..domain import documents as dd
from ..models import Document, DocumentLink, DocumentSignature, Message, UserProfile
from . import document, documents, mail_layout, sites
from .admin import log_audit

#: So gross darf ein Unterschriftszug sein (PNG).
MAX_SIGNATURE_BYTES = 400 * 1024


def link_url(token: str) -> str:
    return f"{get_settings().frontend_base_url.rstrip('/')}/dokument?t={token}"


# ---------------------------------------------------------------------------
# Verlangen und senden
# ---------------------------------------------------------------------------

def request(db: Session, doc: Document, person_ids: list[int], actor: UserProfile) -> None:
    """**Wer unterschreiben soll** – bei der Freigabe gesetzt, danach nur ergänzt."""
    have = {s.person_object_id for s in documents.signatures_of(db, [doc.id])[doc.id]}
    for oid in dict.fromkeys(person_ids):
        if oid in have:
            continue
        person = db.query(UserProfile).filter(UserProfile.object_id == oid).first()
        if person is None:
            raise HTTPException(status_code=400, detail=f"Eine Person {oid} gibt es nicht.")
        db.add(DocumentSignature(document_id=doc.id, person_object_id=oid,
                                 name=person.display_name or person.email or str(oid)))
        documents.add_refs(db, doc, [documents.RefIn(object_id=oid)], actor)
    db.flush()


def send(db: Session, doc: Document, person_ids: list[int], note: str,
         actor: UserProfile) -> list[DocumentLink]:
    """►►► **Senden** – je Empfänger ein Link und eine Mail. ◄◄◄"""
    if doc.deleted_at is not None:
        raise HTTPException(status_code=409, detail="Ein gelöschtes Dokument geht nicht hinaus.")
    if not person_ids:
        raise HTTPException(status_code=400, detail="An wen soll es gehen?")
    out = []
    for oid in dict.fromkeys(person_ids):
        person = db.query(UserProfile).filter(UserProfile.object_id == oid).first()
        if person is None or not person.email:
            raise HTTPException(status_code=400, detail=(
                f"{person.display_name if person else oid} hat keine E-Mail – so geht es nicht hinaus."))
        link = DocumentLink(token=secrets.token_urlsafe(24), document_id=doc.id,
                            person_object_id=oid, created_by=actor.id)
        db.add(link)
        db.flush()
        msg = _mail(db, doc, person, link, note, actor)
        link.message_id = msg.id if msg is not None else None
        documents.add_refs(db, doc, [documents.RefIn(object_id=oid)], actor)
        out.append(link)
    db.flush()
    log_audit(db, "documents", "gesendet", ", ".join(str(i) for i in person_ids), actor.id,
              object_id=doc.object_id)
    return out


def _mail(db: Session, doc: Document, person: UserProfile, link: DocumentLink, note: str,
          actor: UserProfile) -> Optional[Message]:
    from . import mailbox
    from .communication import write
    company = sites.find_operator(db)
    if company is None or not company.object_id:
        return None
    channel = dc.company(company.object_id)
    box = mailbox.active(db, channel) if mailbox.ready() else None
    live = box is not None and not box.problem
    asked = any(s.person_object_id == person.object_id and not s.signed_at and not s.declined_at
                for s in documents.signatures_of(db, [doc.id])[doc.id])
    title = dd.title(doc.art, doc.name)
    lead = (f"{dc.greeting(person.display_name or '')}\n\n"
            + (note.strip() + "\n\n" if note.strip() else "")
            + ("Bitte prüfen und unterschreiben Sie das Dokument online." if asked
               else "Sie finden das Dokument online."))
    firm = mail_layout.firm_of(company, box.address if box else (company.email or ""),
                               (box.picture or "") if box else "")
    mail = mail_layout.compose(title, lead, firm, mail_layout.Signer(name=actor.display_name or ""),
                               extra=mail_layout.Extra(action=mail_layout.Action(
                                   title=title, text="", label="Unterschreiben" if asked else "Öffnen",
                                   url=link_url(link.token))))
    msg = Message(sender_object_id=actor.object_id or company.object_id, channel=channel,
                  subject=title, body=mail.body, html=mail.html, at=datetime.now(timezone.utc),
                  created_by=actor.id, outgoing=live)
    write(db, msg, {"to": [person.object_id], "cc": [], "bcc": [], "about": []})
    return msg


# ---------------------------------------------------------------------------
# Die Seite nach aussen
# ---------------------------------------------------------------------------

def by_token(db: Session, token: str) -> DocumentLink:
    link = (db.query(DocumentLink).filter(DocumentLink.token == token, DocumentLink.is_active.is_(True))
            .first() if token and len(token) <= 64 else None)
    if link is None:
        raise HTTPException(status_code=404, detail="Diesen Link gibt es nicht.")
    return link


def doc_of(db: Session, link: DocumentLink) -> Document:
    """Das Dokument hinter dem Link – **gelöscht ist ein Hinweis (410), kein Fehler**."""
    doc = db.query(Document).filter(Document.id == link.document_id).first()
    if doc is None or doc.deleted_at is not None:
        raise HTTPException(status_code=410, detail=(
            "Dieses Dokument ist nicht mehr verfügbar. Bei Fragen antworten Sie bitte auf unsere Mail."))
    return doc


def signed_html(html: str, sigs: list[DocumentSignature]) -> str:
    """►►► **Das Papier mit seinen Unterschriften** – abgeleitet, nie gespeichert. ◄◄◄"""
    for s in sigs:
        mark = document.SIG_MARK.format(s.person_object_id)
        if s.signed_at and s.image:
            day = s.signed_at.astimezone(clock.ZONE).strftime("%d.%m.%Y %H:%M")
            put = (f'<img alt="Unterschrift" src="data:image/png;base64,'
                   f'{base64.b64encode(s.image).decode("ascii")}"><span>{escape(day)}</span>')
        elif s.declined_at:
            put = f'<span class="bad">abgelehnt: {escape(s.reason or "")}</span>'
        else:
            put = ""
        html = html.replace(mark, put)
    return html


def view(db: Session, link: DocumentLink) -> dict[str, Any]:
    """**Was die Seite zeigt** – das Papier (mit Unterschriften), Zustand, was man tun kann."""
    doc = doc_of(db, link)
    sigs = documents.signatures_of(db, [doc.id])[doc.id]
    raw = documents.raw_of(db, doc)
    html = signed_html(raw.decode("utf-8", "replace"), sigs) if raw and doc.mime == "text/html" else None
    mine = next((s for s in sigs if s.person_object_id == link.person_object_id), None)
    over = any(s.declined_at for s in sigs)
    can = ["sign", "decline"] if mine and not mine.signed_at and not mine.declined_at and not over else []
    return {"art": doc.art, "name": doc.name, "status": documents.status_of(doc, sigs),
            "mime": doc.mime, "html": html,
            "url": None if html else documents.file_url(db, doc), "filename": doc.filename,
            "signers": [{"name": s.name, "signed_at": s.signed_at, "declined_at": s.declined_at}
                        for s in sigs],
            "actions": can}


def _mine(db: Session, link: DocumentLink) -> tuple[Document, DocumentSignature]:
    doc = doc_of(db, link)
    if "sign" not in view(db, link)["actions"]:
        raise HTTPException(status_code=409, detail="Hier ist nichts mehr zu unterschreiben – laden Sie die Seite neu.")
    sig = (db.query(DocumentSignature).filter(DocumentSignature.document_id == doc.id,
                                              DocumentSignature.person_object_id == link.person_object_id)
           .with_for_update().first())
    return doc, sig


def sign(db: Session, link: DocumentLink, image_data_url: str) -> None:
    """**Unterschreiben** – ein Zug als PNG; festgehalten mit Zeitpunkt und der Prüfsumme des
    Papiers, das unterschrieben wurde."""
    doc, sig = _mine(db, link)
    image = _png(image_data_url)
    sig.image, sig.signed_at, sig.sha256 = image, datetime.now(timezone.utc), doc.sha256
    db.flush()
    log_audit(db, "documents", "unterschrieben", sig.name, None, object_id=doc.object_id,
              on_behalf="extern")


def decline(db: Session, link: DocumentLink, reason: str) -> None:
    """**Ablehnen** – mit Grund; endgültig, für alle."""
    reason = dd.clean(reason, dd.REASON_MAX)
    if not reason:
        raise HTTPException(status_code=400, detail="Bitte nennen Sie kurz den Grund.")
    doc, sig = _mine(db, link)
    sig.declined_at, sig.reason = datetime.now(timezone.utc), reason
    db.flush()
    log_audit(db, "documents", "abgelehnt", f"{sig.name}: {reason}", None,
              object_id=doc.object_id, on_behalf="extern")


def _png(data_url: str) -> bytes:
    """Ein Unterschriftszug aus der Zeichenfläche – nur ein echtes, kleines PNG."""
    head, _, data = (data_url or "").partition(",")
    if head != "data:image/png;base64" or not data:
        raise HTTPException(status_code=400, detail="Die Unterschrift fehlt.")
    try:
        raw = base64.b64decode(data, validate=True)
        from PIL import Image
        Image.open(io.BytesIO(raw)).verify()
    except Exception:
        raise HTTPException(status_code=400, detail="Die Unterschrift ist kein lesbares Bild.")
    if len(raw) > MAX_SIGNATURE_BYTES:
        raise HTTPException(status_code=413, detail="Die Unterschrift ist zu gross.")
    return raw

