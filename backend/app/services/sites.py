"""Standorte des Unternehmens – die EINE Auflösung «welche gibt es, welcher ist der Hauptsitz».

**Warum es dieses Modul gibt.** Bis Juli 2026 war ``company_settings`` ein Singleton, und
zehn Stellen im Code holten sich «die Firma» selbst – mal mit ``id == 1``, mal mit einem
blossen ``.first()``. Solange es eine Zeile gab, war beides dasselbe. Ab der zweiten Zeile
ist ``.first()`` eine **willkürliche Wahl**: der Absender auf dem Beleg, die Lieferadresse
für den Lieferanten und der Wareneingangs-Ort hingen plötzlich von der Zeilenreihenfolge
der Datenbank ab. Genau darum liegt die Auflösung jetzt hier – an einer Stelle, benannt,
und mit einer klaren Regel dahinter.

**Die Regel: Standort ≠ Firma.**

  * ``primary(db)`` → der **Hauptsitz**. Er ist «die Firma»: Rechtsidentität (UID, MWST,
    Handelsregister, IBAN, Rechtsform) und Systemkonfiguration (Stripe, Shop, Rechtstexte).
    Jede Stelle, die früher ``get_or_create_settings`` rief, meint genau ihn – deshalb
    ändert sich an diesen Aufrufern kein Zeichen.
  * ``all_sites(db)`` → **alle Standorte**, Hauptsitz zuerst. Für Feed und Auswahl.
  * ``by_object_id(db, oid)`` → **genau dieser** Standort. Für jede Stelle, die schon
    weiss, welchen sie meint (Adresse eines Bewegungs-Ziels, Label eines Halters).

Wer die Anschrift eines *bestimmten* Standorts braucht, nimmt ``by_object_id`` – niemals
``primary``. Das ist der Unterschied zwischen «wohin geht die Ware» und «wer schickt sie».
"""

from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..models import CompanySettings
from .admin import log_audit
from .objects import next_object_id

# Was an JEDEM Standort gilt. Alles Übrige (Rechtsidentität, Systemkonfiguration) gehört
# dem Hauptsitz und ist an einem Nebenstandort weder editierbar noch wirksam – sonst
# stünde dieselbe Angabe an n Stellen. Diese Liste ist die eine Definition davon; das
# Update-Schema (``schemas/admin.SiteUpdate``) wird gegen sie geprüft (test_sites.py).
SITE_FIELDS = (
    "company_name", "street", "street_nr", "zip_code", "city", "country", "email", "phone",
)


def _assign_object_id(db: Session, site: CompanySettings) -> None:
    """Objektnummer lazy vergeben – ein Standort ohne Nummer wäre kein ERP-Datensatz
    (nicht referenzierbar, nicht als Halter verwendbar, nicht im Feed)."""
    if site.object_id is None:
        site.object_id = next_object_id(db, "organization")
        db.commit()
        db.refresh(site)


def find_primary(db: Session) -> CompanySettings | None:
    """Der Hauptsitz als **reines Lesen** – ``None``, wenn es ihn (noch) nicht gibt.

    Gelesen wird **tolerant**: fehlt die Markierung noch (Migration 090 nicht gelaufen,
    Datenbank per ``create_all()`` entstanden), gilt die kleinste ``id`` – historisch war
    das der Singleton ``id = 1``. So kann eine ausstehende Migration nie dazu führen, dass
    das System gar keine Firma findet und Belege ohne Absender schreibt.

    Das ist die **Lese-Form** derselben Regel, die ``primary`` schreibend durchsetzt (wie
    ``inventory.is_in_stock`` neben ``in_stock_clauses``). Sie ist Pflicht überall, wo der
    Aufruf **innerhalb einer fremden Transaktion** läuft – Preis-Pipeline, Shop-Konfig,
    Provider-Wahl, PDF-Briefkopf: ein ``commit`` an diesen Stellen würde die halbfertige
    Arbeit des Aufrufers mit festschreiben."""
    site = db.query(CompanySettings).filter(CompanySettings.is_primary == True).first()
    if site is not None:
        return site
    return db.query(CompanySettings).order_by(CompanySettings.id).first()


def primary(db: Session) -> CompanySettings:
    """Der **Hauptsitz** – «die Firma». **Schreib-Form**: legt ihn an, falls die Datenbank
    leer ist, zieht eine fehlende Markierung nach und vergibt die Objektnummer.

    Committet daher gegebenenfalls – aber nur einmalig; steht der Hauptsitz samt Nummer,
    ist der Aufruf ein reines Lesen. Wer keinesfalls committen darf, nimmt
    ``find_primary``."""
    site = find_primary(db)
    if site is not None and not site.is_primary:
        site.is_primary = True
        db.commit()
        db.refresh(site)
    if site is None:
        site = CompanySettings(id=1, is_primary=True)
        db.add(site)
        db.commit()
        db.refresh(site)
    _assign_object_id(db, site)
    return site


def all_sites(db: Session) -> list[CompanySettings]:
    """Alle Standorte, **Hauptsitz zuerst**, danach nach Objektnummer.

    Ruft ``primary`` vorab, damit auch eine frische Datenbank mindestens einen Standort
    liefert (und der Hauptsitz garantiert eine Objektnummer hat)."""
    primary(db)
    return (
        db.query(CompanySettings)
        .order_by(CompanySettings.is_primary.desc(), CompanySettings.object_id)
        .all()
    )


def by_object_id(db: Session, object_id: int | None) -> CompanySettings | None:
    """**Genau dieser** Standort. ``None``, wenn es ihn nicht (mehr) gibt – der Aufrufer
    entscheidet, ob das ein Fehler ist oder «kein Standort» bedeutet (tolerantes Lesen,
    wie bei ``locations.location_label``)."""
    if object_id is None:
        return None
    return db.query(CompanySettings).filter(CompanySettings.object_id == object_id).first()


def require(db: Session, object_id: int) -> CompanySettings:
    """Wie ``by_object_id``, aber 404 statt ``None`` – für Schreibpfade."""
    site = by_object_id(db, object_id)
    if site is None:
        raise HTTPException(404, detail="Standort nicht gefunden")
    return site


def create(db: Session, data: dict, actor_id: int | None) -> CompanySettings:
    """Neuen **Nebenstandort** anlegen (nur Admin, siehe Router).

    Nimmt ausschliesslich Standortfelder entgegen; Rechtsidentität und
    Systemkonfiguration bleiben am Hauptsitz.

    ``company_settings.id`` trägt keine Sequence (die Tabelle war als Singleton angelegt),
    darum wird der Schlüssel hier vergeben. Der Lock auf den Hauptsitz serialisiert
    gleichzeitige Anlagen – ohne ihn wäre ``max(id) + 1`` ein Check-then-Act und zwei
    Admins bekämen denselben Schlüssel."""
    from sqlalchemy import func

    head = primary(db)
    db.query(CompanySettings).filter(CompanySettings.id == head.id).with_for_update().first()

    name = (data.get("company_name") or "").strip()
    if not name:
        raise HTTPException(400, detail="Standortname fehlt")

    next_id = (db.query(func.max(CompanySettings.id)).scalar() or 0) + 1
    site = CompanySettings(id=next_id, is_primary=False, company_name=name)
    for key, value in data.items():
        if key in SITE_FIELDS and key != "company_name":
            setattr(site, key, value)
    # Ohne Land-Angabe das des Hauptsitzes erben: die Adress-Klassifikation vergleicht
    # Länder mit, ein leeres Land liesse einen Inlandstandort wie Ausland aussehen.
    if not site.country:
        site.country = head.country
    db.add(site)
    db.commit()
    db.refresh(site)
    _assign_object_id(db, site)

    log_audit(db, "company_settings", None, f"Standort «{site.company_name}» angelegt",
              actor_id, object_id=site.object_id)
    db.commit()
    return site


def apply_update(db: Session, site: CompanySettings, data: dict, actor_id: int | None) -> CompanySettings:
    """Standortfelder eines Standorts ändern – dieselbe Zuweisung und dasselbe Audit-Log
    für Hauptsitz wie Nebenstandort.

    (Die Rechtsidentität und die Systemkonfiguration des Hauptsitzes laufen weiterhin über
    ``PATCH /admin/settings`` – dort sitzt die IBAN-Sonderbehandlung.)"""
    for key, value in data.items():
        if key not in SITE_FIELDS:
            continue
        setattr(site, key, value)
        log_audit(db, "company_settings", key, str(value), actor_id, object_id=site.object_id)
    db.commit()
    db.refresh(site)
    return site
