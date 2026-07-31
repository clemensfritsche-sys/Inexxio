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

from ..models import CompanySettings, CompanyTerritory
from . import geography
from .admin import log_audit
from .objects import next_object_id

# Was JEDE Gesellschaft selbst trägt (eine juristische Einheit, vollständig). Editierbar
# an JEDEM Unternehmens-Datensatz gleich – Rechtsidentität ist hier bewusst dabei, denn die
# US-Gesellschaft hat ihre EIGENE EIN/Steuer/Bank. Feldnamen = DB-Spalten (das Frontend
# bildet ``street_number``→``street_nr`` etc. vor dem Senden ab).
#
# **Auf das Minimum reduziert** (Testnotizen #307/#313/#314/#317–#321). Der Massstab war
# nicht «könnte man mal brauchen», sondern: *nennt es jemand auf einem Beleg, im Impressum
# oder in einer Regel?* Übrig bleiben neun Angaben – und weil es neun sind, dürfen sie
# **Pflicht** sein. Entfallen sind Handelsregister-Nr./-Kanton und Aktienkapital (die UID
# identifiziert die Firma im Register; Kapital ist nirgends vorgeschrieben), QR-IBAN/Bank/
# BIC (die IBAN trägt Land, Bank und Konto), MWST-Methode/-Periode (Buchhaltung, Phase 3)
# sowie Zahlungsfrist und Skonto – die gehören in die **Offerte**, wo sie je Geschäft
# verhandelt werden, nicht als stiller Firmen-Default.
#
# ``website`` steht bewusst NICHT hier: die Adresse der Website ist abgeleitet
# (``website_url``), nicht gepflegt.
ENTITY_FIELDS = (
    "company_name", "legal_form",
    "street", "street_nr", "zip_code", "city", "country",
    "currency",
    "uid_number", "vat_number",
    "email", "phone",
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


def website_url() -> str:
    """Die Adresse der Website – **abgeleitet, nicht gepflegt** (Testnotiz #309).

    Unter welcher Adresse diese Installation läuft, weiss das Deployment
    (``FRONTEND_BASE_URL``); ein Eingabefeld daneben wäre eine zweite Wahrheit, die beim
    ersten Domain-Wechsel falsch wird. Genutzt von Impressum, Beleg-Briefkopf und der
    (read-only) Anzeige am Unternehmens-Datensatz – alle lesen diese eine Stelle."""
    from ..core.config import get_settings
    return get_settings().frontend_base_url.rstrip("/")

# Die **Plattform-Konfiguration** – sie gilt für die EINE Website/Integration, nicht je
# Gesellschaft. Sie lebt (vorerst als Spalten auf dem Betreiber-Datensatz) und wird
# ausschliesslich über ``PATCH /admin/settings`` (Systemkonfiguration) gepflegt. ``apply_update``
# schreibt sie NIE, damit ein Nebenstandort keinen Stripe-Key o. ä. setzen kann. Die ``iban``
# ist Entität, wird aber gesondert behandelt (verschlüsselte Spalte).
PLATFORM_FIELDS = (
    "stripe_publishable_key", "plausible_domain", "hcaptcha_site_key", "google_maps_api_key",
    "shop_currencies", "shop_country_currency", "shop_default_currency", "payments_provider",
    "pricing_zone_factors", "legal_documents", "default_receiving_location_id",
    "infra_monthly_chf",
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
    chosen = (
        db.query(CompanySettings)
        .filter(CompanySettings.is_operator == True, CompanySettings.is_active == True)
        .first()
    )
    if chosen is not None:
        return chosen
    return (
        db.query(CompanySettings)
        .filter(CompanySettings.is_active == True)
        .order_by(CompanySettings.id)
        .first()
    )


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
    return (
        db.query(CompanySettings)
        .filter(CompanySettings.is_active == True)
        .order_by(CompanySettings.id)
        .all()
    )


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


def deactivate(db: Session, company: CompanySettings, actor_id: int | None) -> CompanySettings:
    """Ein Unternehmen **schliessen** – Soft-Delete, endgültig (Testnotiz #365).

    Kein «Ersetzen» und **keine Reaktivierung**: der reale Vorgang ist eine Liquidation.
    Wer am selben Ort wieder eröffnet, gründet eine neue Gesellschaft – mit neuer UID/EIN,
    neuem Handelsregister-Datum und neuen Belegkreisen. Sie als dieselbe weiterzuführen
    hiesse, auf ihren Belegen eine Rechtsperson zu nennen, die es so nicht mehr gab. Genau
    wie ein inaktiver Artikel ist das damit endgültig; die Objektnummer bleibt auflösbar
    (sie hält historische Instanzen und steht auf alten Belegen).

    Zwei Dinge dürfen nicht passieren, beide werden geprüft:

    * **Der Betreiber bleibt.** Er ist der Absender der einen Website (Impressum, Rechtstexte,
      Systemkonfiguration) – ohne ihn hätte sie keine Rechtsperson. Erst den Titel weitergeben
      (``set_operator``), dann schliessen.
    * **Die letzte Gesellschaft bleibt.** Ein ERP ohne Unternehmen kennt keinen Absender.

    Ihre **Gebiete** fallen zurück (die Zeilen werden gelöscht): jeder Fleck der Erde gehört
    weiterhin jemandem – ohne Anspruch dem Betreiber (``company_for_country``). Committet."""
    from ..models import CompanyTerritory
    if company.is_operator:
        raise HTTPException(
            409, detail="Der Betreiber der Website kann nicht geschlossen werden – bitte zuerst "
                        "eine andere Gesellschaft zum Betreiber machen.")
    others = (
        db.query(CompanySettings.id)
        .filter(CompanySettings.id != company.id, CompanySettings.is_active == True)
        .count()
    )
    if others == 0:
        raise HTTPException(409, detail="Das letzte Unternehmen kann nicht geschlossen werden")
    db.query(CompanyTerritory).filter(CompanyTerritory.company_id == company.id).delete()
    company.is_active = False
    log_audit(db, "company_settings", "is_active", "false", actor_id, object_id=company.object_id)
    db.commit()
    db.refresh(company)
    return company


# ─── Gebiete: welche Gesellschaft fakturiert welches Kundenland (ADR 006) ─────────

def _claim_owner(db: Session, area: str) -> CompanySettings | None:
    """Besitzer eines **Gebiets-Codes** (Region oder Land) – ``None``, wenn niemand ihn
    beansprucht hat oder die beanspruchende Gesellschaft nicht mehr existiert."""
    row = db.query(CompanyTerritory).filter(CompanyTerritory.region == area).first()
    if row is None:
        return None
    return db.query(CompanySettings).filter(CompanySettings.id == row.company_id).first()


def company_for_country(db: Session, country: str | None) -> CompanySettings | None:
    """Die **fakturierende Gesellschaft** (Seller of Record) für ein Kundenland.

    Vorrang: **Land ≻ Region ≻ Betreiber**. Ein einzelnes Land kann also von seiner Region
    abweichen (Ausnahme: «Europa gehört der GmbH, Liechtenstein aber der Schweizer AG») –
    beides sind Ansprüche in derselben Tabelle (``company_territories``), der Unterschied
    ist aus der Form des Codes abgeleitet (ISO-2 = Land). Rein lesend (kein commit) –
    Pflicht in fremden Transaktionen (Verkauf/Beleg/Versand).

    Ausschlaggebend ist die **Rechnungsadresse** des Kunden (sein rechtlicher Sitz), NICHT die
    Lieferadresse – die richtet nur die Steuer (Stripe Tax). Ein unbekanntes/unzugeordnetes
    Land fällt auf den Betreiber (Totalität: jeder Fleck gehört jemandem)."""
    from . import address
    if not (country or "").strip():
        return find_operator(db)          # kein Land → Betreiber (nicht raten)
    # Klarname → ISO-2 (``address.iso2`` toleriert «Schweiz»/«USA» wie «CH»/«US»).
    code = (address.iso2(country) or "").upper()
    if code:
        company = _claim_owner(db, code)          # Ausnahme auf genau dieses Land
        if company is not None:
            return company
    region = geography.region_of_country(code)
    if region:
        company = _claim_owner(db, region)
        if company is not None:
            return company
    return find_operator(db)


def territory_map(db: Session) -> dict[str, int | None]:
    """``{region_code: company_object_id}`` für ALLE Regionen – nicht zugewiesene füllt der
    **Betreiber** (er besitzt die Welt per Default). Für die Weltkarte im Admin."""
    op = operator(db)
    claims = {r.region: r.company_id for r in db.query(CompanyTerritory).all()}
    by_id = {c.id: c for c in db.query(CompanySettings).all()}
    out: dict[str, int | None] = {}
    for code in geography.REGION_CODES:
        cid = claims.get(code)
        company = by_id.get(cid) if cid is not None else op
        out[code] = (company or op).object_id
    return out


def country_map(db: Session) -> dict[str, int | None]:
    """``{iso2: company_object_id}`` für **jedes bekannte Land** – der *effektive* Besitzer
    (Land-Ausnahme ≻ Region ≻ Betreiber). Dieselbe Vorrangordnung wie
    ``company_for_country``, nur als Batch für die Weltkarte (eine Abfrage statt 240).

    Die Oberfläche leitet daraus ab, welches Land eine **Ausnahme** ist: sein Besitzer weicht
    vom Besitzer seiner Region ab. Kein eigenes Flag – zwei Wahrheiten könnten auseinanderlaufen."""
    regions = territory_map(db)
    claims = {r.region: r.company_id for r in db.query(CompanyTerritory).all()}
    by_id = {c.id: c for c in db.query(CompanySettings).all()}
    out: dict[str, int | None] = {}
    for code, region in geography.COUNTRY_REGION.items():
        cid = claims.get(code)
        company = by_id.get(cid) if cid is not None else None
        out[code] = company.object_id if company is not None else regions.get(region)
    return out


def _default_owner_id(db: Session, area: str) -> int | None:
    """Wem gehört dieses Gebiet **ohne** eigenen Anspruch? Für eine Region der Betreiber, für
    ein Land der Besitzer seiner Region. Grundlage der Aufräum-Regel in ``set_territory``:
    Ein Anspruch, der nichts ändert, ist keine Ausnahme und wird nicht gespeichert."""
    op = operator(db)
    if geography.is_country_code(area):
        region = geography.region_of_country(area)
        owner = _claim_owner(db, region) if region else None
        return (owner or op).id
    return op.id


def set_territory(db: Session, area: str, company_object_id: int | None,
                  actor_id: int | None) -> None:
    """Ein **Gebiet** einer Gesellschaft zuweisen (Weltkarte): eine Region («EUR») oder – als
    Ausnahme – ein einzelnes Land («LI»).

    Die Tabelle hält **nur Abweichungen**: Wird das Gebiet der Gesellschaft zugewiesen, der es
    ohnehin zufiele (Region → Betreiber, Land → Besitzer seiner Region), wird die Zeile
    ENTFERNT statt eine wirkungslose Ausnahme zu speichern. Sonst upsert. Genau EINE
    Gesellschaft je Gebiet (``region`` ist unique)."""
    code = geography.normalize_area(area)
    if code is None:
        raise HTTPException(400, detail="Unbekanntes Gebiet")
    company = by_object_id(db, company_object_id) if company_object_id else None
    row = db.query(CompanyTerritory).filter(CompanyTerritory.region == code).first()
    if company is None or company.id == _default_owner_id(db, code):
        if row is not None:
            db.delete(row)
            log_audit(db, "company_territories", code, "Standard", actor_id)
        db.commit()
        return
    if row is None:
        db.add(CompanyTerritory(region=code, company_id=company.id))
    else:
        row.company_id = company.id
    log_audit(db, "company_territories", code, str(company.object_id),
              actor_id, object_id=company.object_id)
    db.commit()


# ─── Anlegen / Ändern – EIN Feldsatz für JEDE Gesellschaft ────────────────────────

# Spalten, die die Datenbank als NOT NULL führt (Initial-Schema, mit Server-Default).
# Ein leeres Formularfeld schickt ``null`` – das wäre ein **Constraint-Bruch** statt einer
# leeren Angabe: genau so entstand die rohe ``NotNullViolation`` im Formular (Testnotiz
# #338), als jemand die Rechtsform leerte. Leer heisst hier «noch nicht ausgefüllt», nicht
# «kein Wert erlaubt» – also wird ``None`` zu ``""``. Die Pflicht markiert das Formular
# (gelbes Sternchen), erzwungen wird nur der Name (er ist das Halter-Label).
_NOT_NULL_TEXT = ("company_name", "legal_form", "country", "email")
# Die Währung ist die eine Ausnahme: ein leerer ISO-3-Code wäre kein «noch nicht
# ausgefüllt», sondern eine kaputte Angabe (die Preis-Pipeline rechnet damit). Kommt sie
# als ``None``, bleibt der bisherige Wert stehen – das Formular bietet sie ohnehin nur als
# Auswahl an, leeren kann man sie dort gar nicht.
_KEEP_IF_NONE = ("currency",)


def _apply_entity_fields(company: CompanySettings, data: dict, db: Session,
                         actor_id: int | None) -> None:
    """Entitäts-Felder (inkl. Bank-Chiffren) auf die Gesellschaft schreiben + auditieren.
    Plattform-Felder werden bewusst ignoriert – die gehören der einen Website, nicht der
    Gesellschaft, und laufen über die Systemkonfiguration."""
    for key, value in data.items():
        if key == "iban":
            company.iban_encrypted = value
            log_audit(db, "company_settings", key, "[UPDATED]", actor_id, object_id=company.object_id)
        elif key in ENTITY_FIELDS:
            if value is None and key in _KEEP_IF_NONE:
                continue
            if value is None and key in _NOT_NULL_TEXT:
                value = ""
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
    zwei Stellen editierbar ist.

    **Der Name ist hart erforderlich** (Testnotiz #301) – nicht als Formular-Kosmetik,
    sondern weil er zugleich das **Halter-Label** ist: ``locations.location_label`` gibt
    für einen ``company``-Halter genau dieses Feld zurück. Eine namenlose Gesellschaft
    liesse jede Standort-Anzeige leer, die auf sie zeigt."""
    if "company_name" in data and not (data.get("company_name") or "").strip():
        raise HTTPException(400, detail="Name des Unternehmens fehlt")
    _apply_entity_fields(company, data, db, actor_id)
    db.commit()
    db.refresh(company)
    return company
