"""KI-gestützte Aufnahme hochgeladener Fremd-Dokumente (Belege/Anleitungen/Rechnungen).

Ablauf (ADR 004, «Vorschlagen ≠ Ausführen»):
1. ``analyze`` – Datei ablegen, Text extrahieren (PDF-Layer), die KI liest das Dokument
   (PDF-/Bild-Block) und erfasst strukturiert Titel/Typ/Zusammenfassung/Bezugsgrössen.
   Aus den Bezugsgrössen werden **serverseitig** passende ERP-Objekte gematcht (Artikel-
   Fuzzy, Lieferant, Objektnummern). Das Ergebnis wird als ``AiAction``-**Vorschlag**
   angelegt – NICHTS ist damit endgültig.
2. Der Mensch prüft/ändert Name + Objektzuordnung im Frontend und **bestätigt**
   (``routers/document_files``). Erst dann materialisiert ``materialize`` das
   ``DocumentFile`` + die ``DocumentLink``-Zeilen. Ein Dokument OHNE Objekt entsteht nie.

Ohne konfigurierte KI läuft das Modul trotzdem: ``analyze`` legt dann einen Vorschlag mit
Dateiname als Titel an (keine Auto-Zuordnung) – der Mensch benennt/ordnet manuell zu."""

import base64

from sqlalchemy.orm import Session

from ...models import AiAction, Article, DocumentFile, UserProfile
from ..article_names import _similarity
from ..events import emit
from ..objects import resolve_object_type
from ..storage import hash_bytes
from ..storage import store as store_blob
from . import gateway
from .principal import AiPrincipal
from .registry import DOCUMENT_EXTRACT_PROMPT, PROMPT_VERSION, chat_model

DOC_TYPES = (
    "invoice", "delivery_note", "manual", "datasheet",
    "certificate", "contract", "receipt", "other",
)

_MAX_TEXT = 400_000    # gespeicherter Volltext je Dokument (RAG-Basis) – gekappt
_MATCH_MIN = 0.34      # Ähnlichkeits-Schwelle für einen Artikel-/Lieferanten-Treffer
_MAX_LINKS = 8

# Forced-Tool-Schema für die strukturierte Extraktion (der EINE Weg, verlässlich JSON zu bekommen).
EXTRACT_TOOL = {
    "name": "extract_document",
    "description": "Erfasst das analysierte Dokument strukturiert (Titel, Typ, Zusammenfassung, Bezugsgrössen).",
    "input_schema": {
        "type": "object",
        "properties": {
            "title": {"type": "string", "description": "kurzer sprechender Dokumentname (max. 80 Zeichen)"},
            "doc_type": {"type": "string", "enum": list(DOC_TYPES)},
            "summary": {"type": "string"},
            "language": {"type": "string"},
            "entities": {
                "type": "object",
                "properties": {
                    "supplier_name": {"type": "string"},
                    "article_names": {"type": "array", "items": {"type": "string"}},
                    "object_numbers": {"type": "array", "items": {"type": "integer"}},
                    "order_numbers": {"type": "array", "items": {"type": "string"}},
                    "invoice_total": {"type": "string"},
                    "invoice_date": {"type": "string"},
                },
            },
            "suggested_relation": {"type": "string"},
        },
        "required": ["title", "doc_type"],
    },
}


def supported_for_ai(mime: str) -> bool:
    """Von der KI direkt lesbar: PDF + Bilder (Vision). Andere Formate werden gespeichert,
    aber nicht analysiert (Titel = Dateiname, manuelle Zuordnung)."""
    return mime == "application/pdf" or mime.startswith("image/")


def _content_block(data: bytes, mime: str) -> dict:
    b64 = base64.b64encode(data).decode()
    if mime == "application/pdf":
        return {"type": "document", "source": {"type": "base64", "media_type": mime, "data": b64}}
    return {"type": "image", "source": {"type": "base64", "media_type": mime, "data": b64}}


def extract_pdf_text(data: bytes) -> tuple[str | None, int | None]:
    """Text-Layer + Seitenzahl aus einem PDF (best-effort, ohne KI/OCR). Ein digitales PDF
    (Rechnung/Manual) trägt den Text bereits – gratis für den späteren KI-Abruf. Ein
    gescanntes Papier-PDF hat keinen Layer → ``None`` (die KI liest es via Vision)."""
    try:
        import io

        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(data))
        pages = len(reader.pages)
        parts = []
        for pg in reader.pages:
            try:
                parts.append(pg.extract_text() or "")
            except Exception:
                continue
        text = "\n".join(parts).strip()
        return (text[:_MAX_TEXT] if text else None), pages
    except Exception:
        return None, None


def _ai_extract(data: bytes, mime: str) -> tuple[dict, str, int, int]:
    """Das Dokument von der KI strukturiert erfassen lassen. Gibt (meta, model, in_tok, out_tok).
    Erzwungenes Tool ``extract_document`` → verlässliches JSON (kein Freitext-Parsing)."""
    messages = [{
        "role": "user",
        "content": [_content_block(data, mime),
                    {"type": "text", "text": "Erfasse dieses Dokument strukturiert über das Werkzeug."}],
    }]
    resp = gateway.complete(
        messages, system=DOCUMENT_EXTRACT_PROMPT,
        tools=[EXTRACT_TOOL], tool_choice={"type": "tool", "name": "extract_document"},
        model=chat_model(), max_tokens=1500,
    )
    meta: dict = {}
    for c in resp.content:
        if getattr(c, "type", None) == "tool_use" and c.name == "extract_document":
            meta = dict(c.input or {})
            break
    in_tok = getattr(resp.usage, "input_tokens", 0) or 0
    out_tok = getattr(resp.usage, "output_tokens", 0) or 0
    return meta, chat_model(), in_tok, out_tok


# ─── Bezugsgrössen → ERP-Objekte matchen (serverseitig, günstig/verlässlich) ──────

def _object_label(db: Session, object_id: int, object_type: str | None) -> str:
    if object_type == "article":
        a = db.query(Article.name).filter(Article.object_id == object_id).first()
        return a[0] if a else "Artikel"
    if object_type == "user":
        u = db.query(UserProfile).filter(UserProfile.object_id == object_id).first()
        if u:
            return u.company_name or u.display_name or u.email or "Benutzer"
        return "Benutzer"
    return {"order": "Auftrag", "instance": "Instanz",
            "organization": "Unternehmen",
            "document": "Dokument"}.get(object_type or "", "Objekt")


def _add_candidate(out: dict, object_id: int, object_type: str | None, label: str,
                   relation: str, score: float) -> None:
    prev = out.get(object_id)
    if prev is None or score > prev["score"]:
        out[object_id] = {"object_id": object_id, "object_type": object_type,
                          "label": label, "relation": relation, "score": round(score, 3)}


def match_candidates(db: Session, entities: dict, context_object_id: int | None,
                     relation: str) -> list[dict]:
    """Aus den erkannten Bezugsgrössen passende ERP-Objektnummern vorschlagen (rangiert)."""
    out: dict[int, dict] = {}
    entities = entities or {}

    # 1) Der Kontext (die Objektseite, von der aus hochgeladen wurde) ist der Top-Vorschlag.
    if context_object_id:
        t = resolve_object_type(db, context_object_id)
        _add_candidate(out, context_object_id, t, _object_label(db, context_object_id, t), relation, 1.0)

    # 2) Explizit im Dokument genannte Objektnummern.
    for raw in (entities.get("object_numbers") or []):
        try:
            oid = int(raw)
        except (TypeError, ValueError):
            continue
        t = resolve_object_type(db, oid)
        if t:
            _add_candidate(out, oid, t, _object_label(db, oid, t), relation, 0.97)

    # 3) Artikel per Fuzzy-Namensabgleich (Trigramm/Wortstamm, wie die Namensvorschläge).
    names = [n for n in (entities.get("article_names") or []) if isinstance(n, str) and n.strip()]
    if names:
        articles = db.query(Article.object_id, Article.name).filter(
            Article.is_active == True, Article.name.isnot(None)).all()
        for oid, aname in articles:
            best = max((_similarity(n, aname) for n in names), default=0.0)
            if best >= _MATCH_MIN:
                _add_candidate(out, oid, "article", aname, relation, min(0.95, best))

    # 4) Lieferant/Firma per Namensabgleich (Lieferanten & Kunden).
    supplier = (entities.get("supplier_name") or "").strip()
    if supplier:
        users = db.query(UserProfile).filter(
            UserProfile.is_active == True,
            UserProfile.role.in_(("supplier", "customer"))).all()
        for u in users:
            hay = " ".join(x for x in [u.company_name, u.display_name, u.email] if x)
            s = _similarity(supplier, hay)
            if s >= _MATCH_MIN:
                _add_candidate(out, u.object_id, "user", u.company_name or u.display_name or u.email,
                               "invoice_for" if relation == "about" else relation, min(0.95, s))

    ranked = sorted(out.values(), key=lambda c: -c["score"])
    return ranked[:_MAX_LINKS]


# ─── Analyse → Vorschlag (AiAction) ───────────────────────────────────────────────

def analyze(db: Session, principal: AiPrincipal, data: bytes, filename: str | None,
            mime: str, context_object_id: int | None) -> dict:
    """Datei ablegen, (soweit möglich) KI-analysieren und einen ``link_document``-Vorschlag
    anlegen. Rückgabe = Proposal-Detail fürs Frontend (bearbeitbar vor der Bestätigung)."""
    digest = hash_bytes(data)

    # Dubletten-Erkennung: dasselbe Dokument schon (aktiv) abgelegt? → Hinweis, kein Zweit-Upload.
    dup = (db.query(DocumentFile)
           .filter(DocumentFile.sha256 == digest, DocumentFile.is_active == True)
           .first())
    if dup:
        return {"duplicate": True, "duplicate_object_id": dup.object_id, "title": dup.title}

    stored = store_blob(db, data, mime, filename)   # flush (kein commit)

    extracted_text, page_count = (None, None)
    if mime == "application/pdf":
        extracted_text, page_count = extract_pdf_text(data)
    elif mime.startswith("image/"):
        page_count = 1

    meta: dict = {}
    model = None
    ai_analyzed = False
    if gateway.is_enabled() and supported_for_ai(mime):
        try:
            meta, model, in_tok, out_tok = _ai_extract(data, mime)
            ai_analyzed = True
            emit(db, "ai.document_analyzed", object_type="ai", object_id=None,
                 payload={"model": model, "prompt_version": PROMPT_VERSION,
                          "input_tokens": in_tok, "output_tokens": out_tok,
                          "doc_type": meta.get("doc_type"), "on_behalf_of": principal.effective.id},
                 actor_id=principal.actor.id)
        except gateway.AiUnavailable:
            meta = {}   # KI transient nicht verfügbar → manueller Weg (Titel = Dateiname)

    entities = meta.get("entities") or {}
    relation = (meta.get("suggested_relation") or "about").strip() or "about"
    title = (meta.get("title") or "").strip() or _fallback_title(filename)
    doc_type = meta.get("doc_type") if meta.get("doc_type") in DOC_TYPES else "other"
    suggested = match_candidates(db, entities, context_object_id, relation)

    payload = {
        "storage_key": stored["storage_key"], "storage_backend": stored["storage_backend"],
        "sha256": digest, "mime": mime, "filename": filename, "byte_size": stored["byte_size"],
        "page_count": page_count, "title": title, "doc_type": doc_type,
        "summary": (meta.get("summary") or "").strip() or None,
        "language": meta.get("language"), "extracted_text": extracted_text,
        "extracted_data": _invoice_data(entities), "entities": entities,
        "suggested_links": suggested, "ai_model": model, "ai_prompt_version": PROMPT_VERSION,
        "ai_analyzed": ai_analyzed, "source": "upload",
    }
    action = AiAction(
        action_type="link_document",
        summary=f"Dokument «{title[:120]}» ablegen und zuordnen",
        payload=payload, status="proposed",
        proposed_by_ai_id=principal.actor.id,
        requested_by_id=principal.effective.id,
        target_object_id=context_object_id,
    )
    db.add(action)
    db.flush()
    db.commit()
    db.refresh(action)
    return {
        "action_id": action.id, "title": title, "doc_type": doc_type,
        "summary": payload["summary"], "language": payload["language"],
        "filename": filename, "mime": mime, "byte_size": stored["byte_size"],
        "page_count": page_count, "ai_analyzed": ai_analyzed,
        "extracted_data": payload["extracted_data"],
        "suggested_links": suggested, "duplicate": False,
    }


def _fallback_title(filename: str | None) -> str:
    if filename:
        base = filename.rsplit(".", 1)[0].replace("_", " ").replace("-", " ").strip()
        if base:
            return base[:120]
    return "Dokument"


def _invoice_data(entities: dict) -> dict | None:
    """Nur die belegrelevanten Kennzahlen als strukturierte Daten festhalten (Rechnung)."""
    keep = {k: entities.get(k) for k in ("invoice_total", "invoice_date", "order_numbers")
            if entities.get(k)}
    return keep or None


# ─── Materialisierung (nach menschlicher Bestätigung) ─────────────────────────────

def materialize(db: Session, action: AiAction, ai_actor_id: int) -> int | None:
    """Aus dem bestätigten Vorschlag das ``DocumentFile`` + die ``DocumentLink``-Zeilen
    anlegen. Erwartet, dass der Confirm-Router die finalen ``links`` in ``payload`` gesetzt
    hat (mindestens einer). Gibt die primäre Objektnummer zurück (Audit-Ziel)."""
    from fastapi import HTTPException

    from ..objects import next_object_id

    p = action.payload or {}
    links = p.get("links") or []
    if not links:
        raise HTTPException(400, detail="Ein Dokument muss mindestens einem Objekt zugeordnet werden")

    doc = DocumentFile(
        object_id=next_object_id(db, "document"),
        title=(p.get("final_title") or p.get("title") or "Dokument")[:200],
        doc_type=(p.get("final_doc_type") or p.get("doc_type") or "other"),
        summary=p.get("summary"),
        extracted_text=p.get("extracted_text"),
        extracted_data=p.get("extracted_data"),
        mime=p.get("mime") or "application/octet-stream",
        filename=p.get("filename"),
        byte_size=p.get("byte_size"),
        page_count=p.get("page_count"),
        storage_key=p["storage_key"],
        storage_backend=p.get("storage_backend") or "db",
        sha256=p.get("sha256"),
        source=p.get("source") or "upload",
        ai_model=p.get("ai_model"),
        ai_prompt_version=p.get("ai_prompt_version"),
        created_by=action.requested_by_id or ai_actor_id,
    )
    db.add(doc)
    db.flush()

    primary_oid = None
    for i, link in enumerate(links):
        try:
            oid = int(link.get("object_id"))
        except (TypeError, ValueError, AttributeError):
            continue
        is_primary = bool(link.get("primary")) or i == 0
        if is_primary and primary_oid is None:
            primary_oid = oid
        db.add(_link_row(db, doc.id, oid, link.get("relation") or "about", is_primary,
                         action.requested_by_id or ai_actor_id))
    db.flush()

    emit(db, "document.ingested", object_type="document", object_id=doc.object_id,
         payload={"doc_type": doc.doc_type, "title": doc.title,
                  "links": [int(l["object_id"]) for l in links if l.get("object_id")],
                  "on_behalf_of": action.requested_by_id}, actor_id=ai_actor_id)
    return primary_oid


def _link_row(db: Session, document_id: int, object_id: int, relation: str,
              is_primary: bool, actor_id: int | None):
    from ...models import DocumentLink
    return DocumentLink(
        document_id=document_id, object_id=object_id,
        object_type=resolve_object_type(db, object_id),
        relation=relation[:30], is_primary=is_primary, created_by=actor_id,
    )
