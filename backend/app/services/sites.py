"""Unternehmen (Gesellschaften) – die EINE Auflösung «welche gibt es, wer vertritt sie».

**Ein gleichrangiger Datensatztyp.** Es gibt genau EINEN Datensatztyp «Unternehmen»
(``company_settings``, Feed-Typ ``organization``). Jede Zeile ist eine **vollständige
juristische Einheit** mit eigener Objektnummer: eigener Name, Anschrift, Rechtsidentität
(UID/EIN/VAT), Bank, MWST. Keine Zeile ist einer anderen untergeordnet – der frühere
«Hauptsitz vs. Standort»-Unterschied (eine Zeile privilegiert, die übrigen kastriert) ist
ersatzlos entfallen.

**Die eine verbleibende Asymmetrie ist KEIN Rang, sondern eine abgeleitete Rolle.**
Genau eine Frage braucht trotz N Gesellschaften **eine** Antwort: *wer vertritt die eine
Website nach aussen* (Impressum, Rechtstexte, Fallback, Systemkonfiguration). Diese Rolle
– der **Betreiber** – wird **abgeleitet, nicht markiert**: es ist das **älteste**
Unternehmen (kleinste ``id`` = Ursprung, existierte vor jeder Aussenstelle). Kein Flag,
kein Unique-Index, kein Badge – nichts, was eine Zeile über eine andere stellt.

**Warum es dieses Modul gibt.** Zehn Stellen im Code holten sich früher «die Firma» selbst
– mal ``id == 1``, mal ein blosses ``.first()``. Bei einer Zeile war beides dasselbe; ab
der zweiten ist ``.first()`` eine **willkürliche Wahl**. Deshalb läuft die Auflösung nur
hier:

  * ``operator(db)`` → der **Betreiber** (Website/Impressum/Systemkonfiguration/Fallback).
    Schreib-Form: legt ihn an, falls die DB leer ist. Alias ``primary`` – dieselbe Sache,
    alter Name, damit die vielen Aufrufer von ``get_or_create_settings`` unverändert bleiben.
  * ``find_operator(db)`` → dieselbe Rolle als **reines Lesen** (Pflicht in fremden
    Transaktionen – Preis-Pipeline, Shop-Konfig, PDF-Briefkopf: ein ``commit`` dort würde
    die halbfertige Arbeit des Aufrufers festschreiben).
  * ``all_companies(db)`` → **alle** Unternehmen, Betreiber (ältestes) zuerst.
  * ``by_object_id(db, oid)`` → **genau dieses** Unternehmen. Für jede Stelle, die schon
    weiss, welche sie meint (Adresse eines Bewegungs-Ziels, Label eines Halters, künftig
    die fakturierende Gesellschaft). Der Unterschied «wohin geht die Ware» ↔ «wer schickt
    sie» ist genau ``by_object_id`` ↔ ``operator``.
"""

from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..models import CompanySettings
from .admin import log_audit
from .objects import next_object_id

# Was JEDE Gesellschaft selbst trägt (eine juristische Einheit, vollständig). Editierbar
# an JEDEM Unternehmens-Datensatz gleich – Rechtsidentität ist hier bewusst dabei, denn die
# US-Gesellschaft hat ihre EIGENE EIN/Steuer/Bank. Feldnamen = DB-Spalten (das Frontend
# bildet ``street_number``→``street_nr`` etc. vor dem Senden ab).
ENTITY_FIELDS = (
    "company_name", "legal_form",
    "street", "street_nr", "zip_code", "city", "country",
    "currency",
    "uid_number", "vat_number", "trade_register_nr", "trade_register_canton", "share_capital",
    "email", "phone", "website",
    "bank", "bic_swift",
    "vat_method", "vat_period", "default_payment_days", "default_skonto_pct", "default_skonto_days",
    "oss_active", "oss_reg_number", "vies_active",
)

# Land → Funktionswährung (Vorbelegung, editierbar). Bewusst klein & offensichtlich; der
# Rest der Welt fällt auf CHF (die Heimatwährung) zurück, bis er gebraucht wird. Verglichen
# wird über ISO-2 (``address.iso2`` toleriert Klarnamen «Schweiz»/«USA» wie ISO «CH»/«US»).
_COUNTRY_CURRENCY = {
    "CH": "CHF", "LI": "CHF",
    "US": "USD",
    "GB": "GBP",
    "DE": "EUR", "AT": "EUR", "FR": "EUR", "IT": "EUR", "ES": "EUR", "NL": "EUR",
    "BE": "EUR", "IE": "EUR", "PT": "EUR", "FI": "EUR", "LU": "EUR",
}


def currency_for_country(country: str | None) -> str:
    """Funktionswährung aus dem Land ableiten (Vorbelegung). Unbekannt → CHF."""
    from . import address
    return _COUNTRY_CURRENCY.get((address.iso2(country) or "").upper(), "CHF")

# Die **Plattform-Konfiguration** – sie gilt für die EINE Website/Integration, nicht je
# Gesellschaft. Sie lebt (vorerst als Spalten auf dem Betreiber-Datensatz) und wird
# ausschliesslich über ``PATCH /admin/settings`` (Systemkonfiguration) gepflegt. ``apply_update``
# schreibt sie NIE, damit ein Nebenstandort keinen Stripe-Key o. ä. setzen kann. Bank-Chiffren
# (``iban``/``qr_iban``) sind Entität, werden aber gesondert behandelt (verschlüsselte Spalte).
PLATFORM_FIELDS = (
    "stripe_publishable_key", "plausible_domain", "hcaptcha_site_key", "google_maps_api_key",
    "shop_currencies", "shop_country_currency", "shop_default_currency", "payments_provider",
    "pricing_zone_factors", "legal_documents", "default_receiving_location_id",
)


def _assign_object_id(db: Session, company: CompanySettings) -> None:
    """Objektnummer lazy vergeben – ohne Nummer wäre die Gesellschaft kein ERP-Datensatz
    (nicht referenzierbar, nicht als Halter verwendbar, nicht im Feed)."""
    if company.object_id is None:
        company.object_id = next_object_id(db, "organization")
        db.commit()
        db.refresh(company)


def find_operator(db: Session) -> CompanySettings | None:
    """Der **Betreiber** als reines Lesen – ``None``, wenn es (noch) keine Gesellschaft gibt.

    Die **gewählte** Gesellschaft (``is_operator=true``, ``sites.set_operator``); tolerant
    fällt sie auf das **älteste** Unternehmen zurück, falls (noch) keine markiert ist (frische
    DB, Migration 091 nicht gelaufen) – so führt eine ausstehende Migration nie zu «kein
    Betreiber», und Belege bekommen immer einen Absender. Committet nie – Pflicht überall,
    wo der Aufruf innerhalb einer fremden Transaktion läuft."""
    chosen = db.query(CompanySettings).filter(CompanySettings.is_operator == True).first()
    if chosen is not None:
        return chosen
    return db.query(CompanySettings).order_by(CompanySettings.id).first()


def operator(db: Session) -> CompanySettings:
    """Der **Betreiber** – «die Firma» fürs Impressum, die Systemkonfiguration und als
    Fallback. **Schreib-Form**: legt ihn an, falls die DB leer ist, und vergibt die
    Objektnummer. Committet daher gegebenenfalls – aber nur einmalig.

    Wer keinesfalls committen darf, nimmt ``find_operator``."""
    company = find_operator(db)
    if company is None:
        # Die erste Gesellschaft ist sofort der Betreiber – sonst fände ``find_operator``
        # zwar über den Alters-Fallback dieselbe Zeile, aber der explizite Marker macht
        # die Wahl sichtbar und stabil (der Fallback ist nur das Sicherheitsnetz).
        company = CompanySettings(id=1, is_operator=True)
        db.add(company)
        db.commit()
        db.refresh(company)
    _assign_object_id(db, company)
    return company


# Rückwärts-kompatible Namen: der halbe Code ruft ``get_or_create_settings`` → das delegiert
# auf ``primary``. Beide meinen jetzt den Betreiber; die Namen bleiben, damit kein Aufrufer
# angefasst werden muss.
primary = operator
find_primary = find_operator


def all_companies(db: Session) -> list[CompanySettings]:
    """Alle Unternehmen, **Betreiber (ältestes) zuerst**, dann nach Alter (``id``).

    Ruft ``operator`` vorab, damit auch eine frische DB mindestens eine Gesellschaft
    liefert (und der Betreiber garantiert eine Objektnummer hat)."""
    operator(db)
    return db.query(CompanySettings).order_by(CompanySettings.id).all()


def by_object_id(db: Session, object_id: int | None) -> CompanySettings | None:
    """**Genau dieses** Unternehmen. ``None``, wenn es das nicht (mehr) gibt – der Aufrufer
    entscheidet, ob das ein Fehler ist oder «kein Standort» bedeutet (tolerantes Lesen,
    wie bei ``locations.location_label``)."""
    if object_id is None:
        return None
    return db.query(CompanySettings).filter(CompanySettings.object_id == object_id).first()


def require(db: Session, object_id: int) -> CompanySettings:
    """Wie ``by_object_id``, aber 404 statt ``None`` – für Schreibpfade."""
    company = by_object_id(db, object_id)
    if company is None:
        raise HTTPException(404, detail="Unternehmen nicht gefunden")
    return company


def is_operator(db: Session, company: CompanySettings) -> bool:
    """Ist diese Gesellschaft der Betreiber? Liest die **effektive** Rolle (inkl. Alters-
    Fallback, falls noch keine markiert ist) – so stimmt die Anzeige mit ``find_operator``
    überein, auch bevor Migration 091 die Markierung gesetzt hat."""
    op = find_operator(db)
    return bool(op and op.id == company.id)


def set_operator(db: Session, company: CompanySettings, actor_id: int | None) -> CompanySettings:
    """Diese Gesellschaft zum **Betreiber** machen – genau EINE trägt den Titel.

    Setzt das Flag hier true und bei ALLEN anderen false (der partielle Unique-Index liesse
    zwei ``true`` gar nicht erst zu; das explizite Löschen macht den Wechsel atomar statt auf
    einen Constraint-Fehler zu laufen). Nur der Betreiber trägt die Plattform-Konfiguration
    – die Angaben ziehen also mit; das ist gewollt (die eine Website hat einen Absender)."""
    db.query(CompanySettings).filter(CompanySettings.id != company.id).update(
        {CompanySettings.is_operator: False})
    company.is_operator = True
    log_audit(db, "company_settings", "is_operator", "true", actor_id, object_id=company.object_id)
    db.commit()
    db.refresh(company)
    return company


# ─── Anlegen / Ändern – EIN Feldsatz für JEDE Gesellschaft ────────────────────────

def _apply_entity_fields(company: CompanySettings, data: dict, db: Session,
                         actor_id: int | None) -> None:
    """Entitäts-Felder (inkl. Bank-Chiffren) auf die Gesellschaft schreiben + auditieren.
    Plattform-Felder werden bewusst ignoriert – die gehören der einen Website, nicht der
    Gesellschaft, und laufen über die Systemkonfiguration."""
    for key, value in data.items():
        if key == "iban":
            company.iban_encrypted = value
            log_audit(db, "company_settings", key, "[UPDATED]", actor_id, object_id=company.object_id)
        elif key == "qr_iban":
            company.qr_iban_encrypted = value
            log_audit(db, "company_settings", key, "[UPDATED]", actor_id, object_id=company.object_id)
        elif key in ENTITY_FIELDS:
            setattr(company, key, value)
            log_audit(db, "company_settings", key, str(value), actor_id, object_id=company.object_id)


def create(db: Session, data: dict, actor_id: int | None) -> CompanySettings:
    """Neue **Gesellschaft** anlegen (nur Admin, siehe Router) – vollwertig, gleichrangig.

    ``company_settings.id`` trägt keine Sequence (die Tabelle war als Singleton angelegt),
    darum wird der Schlüssel hier vergeben. Der Lock auf den Betreiber serialisiert
    gleichzeitige Anlagen – ohne ihn wäre ``max(id) + 1`` ein Check-then-Act und zwei
    Admins bekämen denselben Schlüssel."""
    from sqlalchemy import func

    op = operator(db)
    db.query(CompanySettings).filter(CompanySettings.id == op.id).with_for_update().first()

    name = (data.get("company_name") or "").strip()
    if not name:
        raise HTTPException(400, detail="Name des Unternehmens fehlt")

    next_id = (db.query(func.max(CompanySettings.id)).scalar() or 0) + 1
    company = CompanySettings(id=next_id, company_name=name)
    _apply_entity_fields(company, {k: v for k, v in data.items() if k != "company_name"},
                         db, actor_id)
    # Ohne Land-Angabe das des Betreibers erben: die Adress-Klassifikation vergleicht Länder
    # mit, ein leeres Land liesse einen Inland-Standort wie Ausland aussehen. (Eine US-
    # Gesellschaft setzt ihr Land ohnehin selbst – geerbt wird nur, wenn das Feld leer bleibt.)
    if not company.country:
        company.country = op.country
    # Währung aus dem Land vorbelegen, sofern nicht ausdrücklich gesetzt (US → USD, DE → EUR).
    if "currency" not in data or not (data.get("currency") or "").strip():
        company.currency = currency_for_country(company.country)
    db.add(company)
    db.commit()
    db.refresh(company)
    _assign_object_id(db, company)

    log_audit(db, "company_settings", None, f"Unternehmen «{company.company_name}» angelegt",
              actor_id, object_id=company.object_id)
    db.commit()
    return company


def apply_update(db: Session, company: CompanySettings, data: dict, actor_id: int | None) -> CompanySettings:
    """Entitäts-Felder einer Gesellschaft ändern – **derselbe Pfad für jede** (auch den
    Betreiber). Plattform-Felder (Stripe/Shop/Rechtstexte) werden ignoriert; die laufen
    über ``PATCH /admin/settings`` (Systemkonfiguration), damit dieselbe Angabe nicht an
    zwei Stellen editierbar ist."""
    _apply_entity_fields(company, data, db, actor_id)
    db.commit()
    db.refresh(company)
    return company
