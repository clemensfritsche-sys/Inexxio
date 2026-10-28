"""►►► **Die Übernahme in die eine Ablage** – was vor den Dokumenten entstand. ◄◄◄

Läuft bei jedem Start (``main._adopt_documents``) und ist **selbstbegrenzend**: was übernommen
ist, trägt danach seine Dokumentnummer und wird nie wieder angefasst. Nichts wird gelöscht –
die Datei bleibt im Korb, das Dokument zeigt nur auf sie.

* Papiere der Belege (``voucher_documents.html``) → Dokument im Feld ``voucher.doc``.
* Lieferantenrechnung und Ausfuhrnachweis (``attachments.id`` in ``vouchers``) → Dokument im
  Feld ``voucher.original`` bzw. ``voucher.export``.
* AGB und Datenschutz: bis heute galt die Vorlage für jede Gesellschaft – sie wird das
  Dokument jeder eigenen Gesellschaft, **einmal**: gibt es irgendwo schon ein Rechtstext-Feld,
  legt der Start nie wieder eines an (eine neue Gesellschaft wählt es selbst, «zu tun»).
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from ..models import (Attachment, CompanySettings, DocumentRef, Order, Voucher,
                      VoucherDocument)
from . import documents, legal, voucher_docs

#: Unter dieser Zahl ist eine Nummer im Feld noch die Zeile im Korb (``attachments.id``) –
#: Dokumentnummern beginnen beim Nummernkreis.
FIRST_OBJECT_ID = 100_000_001


def run(db: Session) -> dict[str, int]:
    """Alles übernehmen, was noch nicht übernommen ist – gibt zurück, wie viel es war."""
    done = {"papers": _papers(db), "files": _files(db), "legal": _legal(db)}
    db.flush()
    return done


def _papers(db: Session) -> int:
    count = 0
    for rec in (db.query(VoucherDocument).filter(VoucherDocument.document_id.is_(None),
                                                  VoucherDocument.html.isnot(None)).all()):
        row = db.query(Voucher).filter(Voucher.id == rec.voucher_id).first()
        order = db.query(Order).filter(Order.id == row.order_id).first() if row else None
        if order is None:
            continue
        word = voucher_docs.word_of(rec.kind, rec.level)
        refs = [documents.RefIn(object_id=order.object_id, part=f"step:{row.step_id}",
                                field="voucher.doc")]
        if rec.party_id:
            refs.append(documents.RefIn(object_id=rec.party_id))
        doc, existed = documents.file(
            db, raw=rec.html.encode("utf-8"), filename=f"{word} {rec.number or ''}.html".strip(),
            mime="text/html", art=word, name=rec.number or word, source="voucher", refs=refs,
            actor=None, facts={"kind": rec.kind, "number": rec.number})
        if existed:
            documents.add_refs(db, doc, refs, None)
        rec.document_id, rec.html = doc.id, None
        count += 1
    return count


#: Spalte am Beleg → Pflichtfeld und Art.
FILES = (("original_id", "voucher.original", "Lieferantenrechnung"),
         ("export_photo_id", "voucher.export", "Ausfuhrnachweis"))


def _files(db: Session) -> int:
    count = 0
    for column, field, art in FILES:
        attr = getattr(Voucher, column)
        for row in db.query(Voucher).filter(attr.isnot(None), attr < FIRST_OBJECT_ID).all():
            att = db.query(Attachment).filter(Attachment.id == getattr(row, column)).first()
            order = db.query(Order).filter(Order.id == row.order_id).first()
            if att is None or order is None:
                continue
            part = f"step:{row.step_id}"
            doc, _ = documents.file(
                db, raw=bytes(att.data), filename=att.filename, mime=att.mime, art=art,
                name=" · ".join(x for x in (row.number, row.export_number) if x) or art,
                source="file", refs=[], actor=None, stored=att)
            documents.set_field(db, document_object_id=doc.object_id,
                                object_id=order.object_id, part=part, field=field, actor=None)
            setattr(row, column, doc.object_id)
            count += 1
    return count


def _legal(db: Session) -> int:
    if (db.query(DocumentRef.id).filter(DocumentRef.field.in_(tuple(legal.FIELD_OF.values())))
            .first() is not None):
        return 0
    count = 0
    own = (db.query(CompanySettings).filter(CompanySettings.is_own.is_(True),
                                            CompanySettings.is_active.is_(True)).all())
    for kind, field in legal.FIELD_OF.items():
        found = legal.template(kind)
        if found is None:
            continue
        for company in own:
            if not company.object_id:
                continue
            doc = legal._file_template(db, company, kind, found, found[0], None)
            documents.set_field(db, document_object_id=doc.object_id,
                                object_id=company.object_id, part=None, field=field,
                                actor=None)
            count += 1
    return count
