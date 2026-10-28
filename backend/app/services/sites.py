"""Unternehmen (Gesellschaften) – die EINE Auflösung «welche gibt es, wer vertritt sie».

**Ein gleichrangiger Datensatztyp.** Es gibt genau EINEN Datensatztyp «Unternehmen»
(``company_settings``, Feed-Typ ``organization``). Jede Zeile ist eine **vollständige
juristische Einheit** mit eigener Objektnummer: eigener Name, Anschrift, Rechtsidentität
(UID/EIN/VAT), Bank, MWST. Keine Zeile ist einer anderen untergeordnet.

**Die eine verbleibende Asymmetrie ist kein Rang, sondern eine Rolle.** Genau eine Frage
braucht trotz N Gesellschaften **eine** Antwort: *wer vertritt die eine Website nach
aussen* (Impressum, Fallback, Plattform-Konfiguration). Diese Rolle – der **Betreiber** –
ist **wählbar** (``is_operator``, partieller Unique-Index: genau eine trägt sie,
``set_operator`` nimmt sie allen anderen ab). Gelesen wird sie **tolerant**: ist keine
markiert (frische Datenbank, Migration 091 noch nicht gelaufen), gilt das **älteste**
Unternehmen – so gibt es nie «keinen Betreiber», und jeder Beleg hat einen Absender.

**Warum es dieses Modul gibt.** «Die Firma» holt sich niemand selbst – bei mehr als einer
Zeile wäre ein blosses ``.first()`` eine **willkürliche Wahl**. Deshalb läuft die
Auflösung nur hier:

  * ``operator(db)`` → der **Betreiber** (Website, Impressum, Plattform-Konfiguration,
    Fallback). Schreib-Form: legt ihn an, falls die Datenbank leer ist.
  * ``find_operator(db)`` → dieselbe Rolle als **reines Lesen** – Pflicht überall, wo
    schon jemand anderes eine Transaktion führt: ein ``commit`` dort schriebe dessen
    halbfertige Arbeit fest.
  * ``all_companies(db)`` → **alle** Unternehmen, Betreiber (ältestes) zuerst.
  * ``by_object_id(db, oid)`` → **genau dieses** Unternehmen. Für jede Stelle, die schon
    weiss, welche sie meint (Adresse eines Bewegungs-Ziels, Label eines Halters, künftig
    die fakturierende Gesellschaft). Der Unterschied «wohin geht die Ware» ↔ «wer schickt
    sie» ist genau ``by_object_id`` ↔ ``operator``.
"""

from typing import Any

from fastapi import HTTPException
from sqlalchemy import false, or_
from sqlalchemy.exc import IntegrityError
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
    "phone",
)
# ``email`` steht bewusst NICHT hier: die Kontakt-E-Mail einer eigenen Gesellschaft IST die
# Adresse ihres Postfachs – gesetzt wird sie allein beim Verbinden, geleert beim Trennen
# (``services/mailbox``). Ein zweiter Schreibweg wäre die Adresse, die nie hinausgeht.

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

# Eine **Plattform-Konfiguration** in der Datenbank gibt es nicht mehr: der einzige Wert, der
# Google-Maps-Schlüssel, kommt aus der Deploy-Konfiguration (``config.google_maps_api_key``).
# Die ``iban`` ist Entität, wird aber gesondert behandelt (verschlüsselte Spalte).


def legal_name(company: Any) -> str:
    """►►► **Der Name der Rechtsperson** – so, wie er auf einen Beleg gehört. ◄◄◄

    «Inexxio» ist keine Rechtsperson, «Inexxio AG» ist eine, und auf einer Rechnung
    steht die, die haftet. Beide Angaben liegen längst am Unternehmen; hier werden sie
    zu **einem** Namen.

    ►►► **Und es ist dieselbe Frage bei einem GESCHÄFTSKONTO** (Testnotiz #1042). ◄◄◄
    Seit der Benutzer-Datensatz eine ``legal_form`` trägt, gilt die Zusammensetzung für
    beide Seiten des Belegs – darum nimmt sie jeden Träger von ``company_name`` +
    ``legal_form`` (``getattr`` mit Vorgabe, wie von Anfang an). Eine zweite Fassung für
    die Gegenpartei wäre genau die Stelle, an der «Muster AG AG» wieder entsteht.

    ►►► **Und die Rechtsform steht GENAU EINMAL da.** ◄◄◄ Fast jeder trägt sie schon im
    Firmennamen («Muster AG»), und stumpf angehängt käme «Muster AG AG» heraus – gemessen
    am ersten Wächter, der es versuchte. Sie wird darum nur ergänzt, wo sie **fehlt**.

    *Gross-/Kleinschreibung zählt dabei nicht, und es wird auf ein ganzes Wort geprüft:
    sonst schluckte «Sagex» die Form «AG» nicht, aber «Maschinenbau» das «au».*
    """
    name = (getattr(company, "company_name", "") or "").strip()
    form = (getattr(company, "legal_form", "") or "").strip()
    if not form or form.casefold() in [w.casefold() for w in name.split()]:
        return name
    return f"{name} {form}".strip()


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
        .filter(CompanySettings.is_operator == True, CompanySettings.is_active == True,
                CompanySettings.is_own == True)
        .first()
    )
    if chosen is not None:
        return chosen
    return (
        db.query(CompanySettings)
        .filter(CompanySettings.is_active == True, CompanySettings.is_own == True)
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
        # Die Id kommt aus der Sequenz – eine fest gesetzte 1 liesse sie stehen, und der
        # nächste Einfüger bekäme sie ein zweites Mal.
        company = CompanySettings(is_operator=True, is_own=True,
                                  company_name="Inexxio AG", legal_form="AG")
        _rekey(company)
        db.add(company)
        db.commit()
        db.refresh(company)
    _assign_object_id(db, company)
    return company


def all_companies(db: Session) -> list[CompanySettings]:
    """**Alle** Unternehmen – auch geschlossene –, Betreiber (ältestes) zuerst, dann nach
    Alter (``id``). Für den **Feed**: «geschlossen» ist ein Zustand, kein Verschwinden.
    Vorher fiel eine geschlossene Gesellschaft ersatzlos aus dem ERP – ihre Historie war
    danach über keine Oberfläche mehr erreichbar (Runde 25 hatte das Schliessen eingeführt,
    ohne die Ansicht mitzuziehen).

    Wer eine **Auswahl** braucht (wem lässt sich ein Gebiet zuweisen?), nimmt
    ``selectable_companies`` – einer geschlossenen Gesellschaft weist man nichts mehr zu.

    Ruft ``operator`` vorab, damit auch eine frische DB mindestens eine Gesellschaft
    liefert (und der Betreiber garantiert eine Objektnummer hat)."""
    operator(db)
    return (
        db.query(CompanySettings)
        .order_by(CompanySettings.id)
        .all()
    )


def selectable_companies(db: Session) -> list[CompanySettings]:
    """Die **wählbaren** Unternehmen (aktiv) – wem lässt sich ein Gebiet zuweisen, wer kann
    fakturieren? Einer geschlossenen Gesellschaft weist man nichts mehr zu; sie erscheint
    weiterhin im Feed (``all_companies``), aber nicht mehr in einer Auswahl."""
    return [c for c in all_companies(db) if c.is_active and c.is_own]


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


def require_own(db: Session, object_id: int | None, *, what: str = "") -> CompanySettings:
    """►►► **Genau diese Gesellschaft – und sie muss eine UNSERER sein.** ◄◄◄

    Seit dieselbe Tabelle jede Firma trägt (CRM Schritt 1), ist «gibt es sie?» nicht mehr
    dieselbe Frage wie «ist sie unsere?». Wer einen Beleg stellt, Personal beschäftigt,
    ein Gebiet besitzt oder die Website betreibt, muss eine **eigene** und **offene**
    Gesellschaft sein – sonst stünde die IBAN eines Kunden im Einzahlungsschein. Die eine
    Prüfung dafür; der Satz nennt die Nummer."""
    company = by_object_id(db, object_id)
    if company is None or not company.is_own or not company.is_active:
        raise HTTPException(
            400, detail=f"«{object_id}» ist keine unserer Gesellschaften{what}.")
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
    require_own(db, company.object_id)
    db.query(CompanySettings).filter(CompanySettings.id != company.id).update(
        {CompanySettings.is_operator: False})
    company.is_operator = True
    log_audit(db, "company_settings", "is_operator", "true", actor_id, object_id=company.object_id)
    db.commit()
    db.refresh(company)
    return company


def deactivate(db: Session, company: CompanySettings, actor_id: int | None) -> CompanySettings:
    """Ein Unternehmen **schliessen** – Soft-Delete, **umkehrbar** (``reopen``).

    Die Objektnummer bleibt auflösbar (sie hält historische Instanzen und steht auf alten
    Belegen); geschlossen heisst nur: in keiner Auswahl mehr.

    Zwei Dinge dürfen nicht passieren, beide werden geprüft:

    * **Der Betreiber bleibt.** Er ist der Absender der einen Website – erst den Titel
      weitergeben (``set_operator``), dann schliessen.
    * **Die letzte eigene Gesellschaft bleibt.** Ein ERP ohne Unternehmen kennt keinen
      Absender.

    Ihre **Gebiete** fallen zurück (die Zeilen werden gelöscht) und kommen beim
    Wiederöffnen **nicht** von selbst zurück – wer fakturiert, entscheidet die Karte.
    Committet."""
    from ..models import CompanyTerritory
    if company.is_operator:
        raise HTTPException(
            409, detail="Der Betreiber der Website kann nicht geschlossen werden – bitte zuerst "
                        "eine andere Gesellschaft zum Betreiber machen.")
    others = (
        db.query(CompanySettings.id)
        .filter(CompanySettings.id != company.id, CompanySettings.is_active == True,
                CompanySettings.is_own == True)
        .count()
    )
    if others == 0 and company.is_own:
        raise HTTPException(409, detail="Das letzte Unternehmen kann nicht geschlossen werden")
    db.query(CompanyTerritory).filter(CompanyTerritory.company_id == company.id).delete()
    company.is_active = False
    log_audit(db, "company_settings", "is_active", "false", actor_id, object_id=company.object_id)
    db.commit()
    db.refresh(company)
    return company



def reopen(db: Session, company: CompanySettings, actor_id: int | None) -> CompanySettings:
    """Ein geschlossenes Unternehmen **wieder öffnen** – die Gegenhandlung zu
    ``deactivate``. **Eine Regel gilt doch**: ist inzwischen eine andere Firma mit
    derselben UID (bzw. demselben Namen und derselben Rechtsform) offen, wird sie genannt
    – zwei offene Datensätze für eine Firma lässt die Datenbank ohnehin nicht zu."""
    _rekey(company)
    _assert_unique(db, company)
    company.is_active = True
    log_audit(db, "company_settings", "is_active", "true", actor_id, object_id=company.object_id)
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
    Pflicht überall, wo schon jemand anderes eine Transaktion führt.

    Ausschlaggebend ist die **Rechnungsadresse** des Kunden (sein rechtlicher Sitz), nicht
    die Lieferadresse – die richtet die Steuer. Ein unbekanntes/unzugeordnetes Land fällt
    auf den Betreiber (Totalität: jeder Fleck gehört jemandem)."""
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
    company = require_own(db, company_object_id) if company_object_id else None
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
    from ..domain import uid
    for key, value in data.items():
        if key == "uid_number":
            # **Gespeichert wird die Schreibweise des Belegs** (``CHE-123.456.789``) –
            # verglichen wird über den Schlüssel, also ist die Form nur noch Anzeige.
            value = uid.display(value) or None
        if key == "iban":
            company.iban = value
            log_audit(db, "company_settings", key, "[UPDATED]", actor_id, object_id=company.object_id)
        elif key in ENTITY_FIELDS:
            if value is None and key in _KEEP_IF_NONE:
                continue
            if value is None and key in _NOT_NULL_TEXT:
                value = ""
            setattr(company, key, value)
            log_audit(db, "company_settings", key, str(value), actor_id, object_id=company.object_id)
    _rekey(company)


#: Angaben, die nur eine **eigene** Gesellschaft trägt – eine fremde Firma hat bei uns
#: keine Bankverbindung, auf die wir Rechnungen ausstellen, und keine Funktionswährung.
OWN_FIELDS = ("iban", "currency")

#: ►►► **Was eine FREMDE Firma bei uns ist: ihre Identität, sonst nichts.** ◄◄◄
#:
#: Name, Rechtsform, UID. **Keine Anschrift, kein Telefon, keine E-Mail**: die Adressen
#: gehören den **Personen**, die für sie bestellen (ihr Adressbuch) – eine Firma hat viele
#: Standorte, und welcher auf *diesem* Beleg steht, entscheidet die Bestellung, nicht der
#: Firmendatensatz. Eine zweite Anschrift an der Firma wäre die Stelle, an der die
#: Rechnung still an die falsche geht.
EXTERNAL_FIELDS = ("company_name", "legal_form", "uid_number")


# ─── Identität: woran eine Firma erkannt wird ─────────────────────────────────────

def uid_key_of(raw: str | None) -> str | None:
    """Die UID als Schlüssel – ``None``, wo keine steht (``domain/uid.normalize``)."""
    from ..domain import uid
    return uid.normalize(raw) or None


def name_key_of(name: str | None, form: str | None) -> str | None:
    """**Name und Rechtsform als Schlüssel** – ohne Gross-/Kleinschreibung, Satzzeichen
    und doppelte Leerzeichen, die Rechtsform nur einmal: «Muster» + «AG» · «Muster AG» +
    «AG» · «muster  a.g.» + «A.G.» sind eine Firma.

    Unscharfes bleibt getrennt: «Muster AG» ↔ «Muster Aktiengesellschaft» zusammenzulegen
    hiesse, zwei Rechtspersonen zu einer zu machen, wenn man sich irrt – zwei Datensätze
    für eine sind der harmlosere Fehler, und die UID führt sie zusammen."""
    def norm(value: str | None) -> str:
        # Punkte fallen ersatzlos weg («A.G.» = «AG»), alles andere trennt Wörter.
        text = (value or "").replace(".", "")
        kept = "".join(ch if (ch.isalnum() or ch == "&") else " " for ch in text)
        return " ".join(kept.casefold().split())
    f = "".join(norm(form).split())
    # **Die Rechtsform zählt einmal** – «Muster AG» mit Rechtsform «AG» ist dieselbe Firma
    # wie «Muster» mit «AG» (dieselbe Ausnahme wie in ``legal_name``).
    n = " ".join(w for w in norm(name).split() if w != f)
    return f"{n}|{f}" if n and f else None


def _rekey(company: CompanySettings) -> None:
    """Die beiden Schlüssel nachziehen – **die eine Schreibstelle** dafür."""
    company.uid_key = uid_key_of(company.uid_number)
    company.name_key = name_key_of(company.company_name, company.legal_form)


def _active(db: Session):
    return db.query(CompanySettings).filter(CompanySettings.is_active == True)  # noqa: E712


def by_uid(db: Session, raw: str | None) -> CompanySettings | None:
    """Die Firma zu dieser UID – oder ``None``. **Gleiche Nummer, gleiche Firma.**"""
    key = uid_key_of(raw)
    return _active(db).filter(CompanySettings.uid_key == key).first() if key else None


def by_name(db: Session, name: str | None, form: str | None) -> CompanySettings | None:
    """Die Firma zu Name und Rechtsform – die ohne UID zuerst, sonst die älteste."""
    key = name_key_of(name, form)
    if key is None:
        return None
    return (_active(db).filter(CompanySettings.name_key == key)
            .order_by(CompanySettings.uid_key.isnot(None), CompanySettings.id).first())


def _assert_unique(db: Session, company: CompanySettings,
                   changes: dict | None = None) -> None:
    """Gibt es **eine andere** Firma mit diesem Schlüssel? – dann mit Nummer und Namen.

    Die Datenbank wiese es ohnehin ab (Unique-Index); hier bekommt die Abweisung einen
    Satz, der sagt, **wo** die Firma schon steht – «Wert bereits vergeben» schickt
    jemanden auf die Suche."""
    changes = changes or {}
    uid_key = uid_key_of(changes.get("uid_number", company.uid_number))
    name_key = name_key_of(changes.get("company_name", company.company_name),
                           changes.get("legal_form", company.legal_form))
    query = _active(db).filter(CompanySettings.id != company.id) if company.id \
        else _active(db)
    # **Ohne Autoflush** – sonst schriebe die Abfrage die geänderte Zeile zuerst, und der
    # Index wiese sie ab, bevor dieser Satz entstehen kann.
    with db.no_autoflush:
        if uid_key:
            other = query.filter(CompanySettings.uid_key == uid_key).first()
        elif name_key:
            other = query.filter(CompanySettings.uid_key.is_(None),
                                 CompanySettings.name_key == name_key).first()
        else:
            other = None
    if other is not None:
        raise HTTPException(409, detail=(
            f"Diese Firma gibt es schon: {other.object_id} «{legal_name(other)}»"
            + (f" mit der UID {other.uid_number}." if uid_key else
               " – gleicher Name und gleiche Rechtsform.")))


def _assert_uid(raw: str | None) -> None:
    from ..domain import uid
    trouble = uid.problem(raw)
    if trouble:
        raise HTTPException(400, detail=trouble)


#: **Eine Firma gibt es einmal** – als Index in der Datenbank (Migration ``143`` und
#: Lifespan-Netz lesen dieselbe Liste). Dieselbe Bedingung wie am Modell.
KEY_INDEXES = (
    "CREATE UNIQUE INDEX IF NOT EXISTS uq_company_settings_uid_key "
    "ON company_settings (uid_key) WHERE is_active AND uid_key IS NOT NULL",
    "CREATE UNIQUE INDEX IF NOT EXISTS uq_company_settings_name_key "
    "ON company_settings (name_key) "
    "WHERE is_active AND uid_key IS NULL AND name_key IS NOT NULL",
)


def backfill_keys(conn) -> int:
    """►►► **Die Schlüssel für den Bestand** (Migration ``143`` **und** Lifespan-Netz). ◄◄◄

    Auf einer rohen Verbindung, weil beide Wege eine haben; die Ableitung ist dieselbe wie
    beim Schreiben (``uid_key_of`` · ``name_key_of``) – eine zweite in SQL hätte bei einem
    Sonderzeichen anders entschieden als die Eingabe danach.

    **Eine Alt-Dublette bleibt getrennt** – zusammengelegt wird beim Lesen nichts, das ist
    eine Entscheidung mit Folgen für Belege. Die ältere behält den Schlüssel, die jüngere
    bekommt ihn mit ihrer Id markiert (``…#17``): so trifft sie keine Eingabe mehr, die
    Unique-Indizes halten, und der Lauf ist **selbstbegrenzend** – er nimmt nur Zeilen
    ohne ``name_key``. Gibt die Zahl der bearbeiteten Zeilen zurück."""
    from sqlalchemy import text
    rows = conn.execute(text(
        "SELECT id, company_name, legal_form, uid_number, is_active FROM company_settings "
        "WHERE name_key IS NULL ORDER BY id")).all()
    if not rows:
        return 0
    taken = conn.execute(text(
        "SELECT uid_key, name_key FROM company_settings "
        "WHERE is_active AND name_key IS NOT NULL")).all()
    uids = {u for u, _ in taken if u}
    names = {n for u, n in taken if not u and n}
    for cid, name, form, raw_uid, active in rows:
        ukey = uid_key_of(raw_uid)
        nkey = name_key_of(name, form) or f"#{cid}"
        if active and ukey in uids:
            ukey = None
        if active and ukey is None and nkey in names:
            nkey = f"{nkey}#{cid}"
        if active:
            (uids.add(ukey) if ukey else names.add(nkey))
        conn.execute(text("UPDATE company_settings SET uid_key = :u, name_key = :n "
                          "WHERE id = :i"), {"u": ukey, "n": nkey, "i": cid})
    return len(rows)


def search(db: Session, query: str, limit: int = 8) -> list[CompanySettings]:
    """Firmen für die Vorschlagsliste – Nummer, Name **oder** UID, nur offene.

    **Nur für das Personal** (Router): wer eine Firma sucht, sieht, welche es gibt – und
    die Kundenliste ist nichts, was ein Kunde durchblättern darf. Eine Person nennt ihre
    Firma (``resolve``), sie sucht sie nicht."""
    from . import lookup
    key = uid_key_of(query)
    return (
        _active(db)
        .filter(CompanySettings.object_id.isnot(None),
                or_(lookup.matches(query, CompanySettings.object_id,
                                   CompanySettings.company_name, CompanySettings.uid_number),
                    CompanySettings.uid_key == key if key else false()))
        .order_by(CompanySettings.is_own.desc(), CompanySettings.company_name)
        .limit(limit)
        .all()
    )


def _new(db: Session, data: dict, actor_id: int | None, *, own: bool) -> CompanySettings:
    """Eine Firma anlegen – **ohne** zu committen (der Aufrufer führt die Transaktion).

    **Name und Rechtsform sind Pflicht**: «Muster» ist keine Rechtsperson, «Muster AG» ist
    eine, und auf einem Beleg steht die, die haftet. **Eine fremde Firma ist ihre
    Identität** (``EXTERNAL_FIELDS``) – sie erbt nichts von uns und trägt keine Anschrift."""
    name = (data.get("company_name") or "").strip()
    form = (data.get("legal_form") or "").strip()
    if not name:
        raise HTTPException(400, detail="Name des Unternehmens fehlt")
    if not form:
        raise HTTPException(
            400, detail=f"«{name}» braucht eine Rechtsform – auf einem Beleg steht die "
                        f"Rechtsperson, nicht ihr Name allein.")
    _assert_uid(data.get("uid_number"))
    if not own:
        _assert_external(data)
    company = CompanySettings(company_name=name, legal_form=form, is_own=own,
                              email="", country="")
    _apply_entity_fields(company, {k: v for k, v in data.items()
                                   if k not in ("company_name", "legal_form")},
                         db, actor_id)
    if own:
        op = find_operator(db)
        if not company.country and op is not None:
            company.country = op.country
        if not (data.get("currency") or "").strip():
            company.currency = currency_for_country(company.country)
    _assert_unique(db, company)
    company.object_id = next_object_id(db, "organization")
    db.add(company)
    db.flush()
    log_audit(db, "company_settings", None, f"Unternehmen «{legal_name(company)}» angelegt",
              actor_id, object_id=company.object_id)
    return company


def _assert_external(data: dict) -> None:
    """Eine fremde Firma trägt ihre Identität und sonst nichts (``EXTERNAL_FIELDS``)."""
    extra = [k for k, v in data.items()
             if k not in (*EXTERNAL_FIELDS, "is_own") and v not in (None, "")]
    if extra:
        raise HTTPException(400, detail=(
            "Eine fremde Firma trägt bei uns nur Name, Rechtsform und UID – Anschriften "
            "gehören den Personen, die für sie bestellen."))


def create(db: Session, data: dict, actor_id: int | None, *,
           own: bool = False) -> CompanySettings:
    """Neue Firma anlegen und festschreiben. ``own`` setzt nur ein Admin (Router).

    ►►► **Die Id kommt aus der Sequenz** – nie ``max(id) + 1``. Der Lock auf den
    Betreiber serialisiert die **Betreiber-Wahl**, nicht die Nummernvergabe."""
    op = operator(db)
    db.query(CompanySettings).filter(CompanySettings.id == op.id).with_for_update().first()
    company = _new(db, data, actor_id, own=own)
    db.commit()
    db.refresh(company)
    return company


def resolve(db: Session, data: dict, actor_id: int | None, *,
            allow_own: bool) -> CompanySettings:
    """►►► **Die Firma, die eine Person nennt** – erkannt oder neu angelegt. ◄◄◄

    *Jeder darf eine Firma anlegen* – das ist der Punkt eines CRM, das sich selbst füllt.
    Damit daraus kein Durcheinander wird, entscheidet **der Schlüssel**, nie ein Mensch:

    * **mit UID**: gleiche UID → dieselbe Firma (der getippte Name zählt dann nicht – die
      Firma heisst, wie sie heisst). Kennen wir sie nicht, aber eine Firma **ohne** UID mit
      gleichem Namen und gleicher Rechtsform, bekommt diese die UID (sie *war* es). Sonst
      entsteht sie neu – dafür braucht es Name und Rechtsform.
    * **ohne UID**: gleicher Name **und** gleiche Rechtsform → dieselbe Firma; sonst neu.

    **Eine unserer Gesellschaften nennt nur das Personal** (``allow_own``): eine Kundin,
    die unsere UID eintippt, wird nicht unsere Mitarbeiterin.

    **Gleichzeitig ist kein Sonderfall**: zwei Menschen, die dieselbe neue Firma im selben
    Moment nennen, laufen in den Unique-Index – der zweite findet danach die erste.
    Committet nicht."""
    _assert_uid(data.get("uid_number"))
    name = (data.get("company_name") or "").strip()
    form = (data.get("legal_form") or "").strip()
    for attempt in (1, 2):
        found = _recognize(db, data.get("uid_number"), name, form, actor_id)
        if found is not None:
            if found.is_own and not allow_own:
                raise HTTPException(400, detail=(
                    f"«{legal_name(found)}» ist eine unserer Gesellschaften – die "
                    f"Zuordnung dazu nimmt das Personal vor."))
            return found
        if uid_key_of(data.get("uid_number")) and not (name and form):
            raise HTTPException(400, detail=(
                f"Die UID «{data.get('uid_number')}» kennen wir noch nicht – bitte "
                f"Firmenname und Rechtsform dazu angeben."))
        try:
            with db.begin_nested():
                return _new(db, {"company_name": name, "legal_form": form,
                                 "uid_number": data.get("uid_number") or None},
                            actor_id, own=False)
        except IntegrityError:
            if attempt == 2:
                raise
    raise HTTPException(409, detail="Die Firma liess sich nicht anlegen.")


def _recognize(db: Session, raw_uid: str | None, name: str, form: str,
               actor_id: int | None) -> CompanySettings | None:
    """Die bekannte Firma zu dieser Angabe – UID zuerst, dann Name und Rechtsform."""
    from ..domain import uid
    if uid_key_of(raw_uid):
        hit = by_uid(db, raw_uid)
        if hit is not None:
            return hit
        same = by_name(db, name, form)
        if same is not None and same.uid_key is None:
            same.uid_number = uid.display(raw_uid)
            _rekey(same)
            log_audit(db, "company_settings", "uid_number", same.uid_number, actor_id,
                      object_id=same.object_id)
            db.flush()
            return same
        return None
    return by_name(db, name, form)


def apply_update(db: Session, company: CompanySettings, data: dict, actor_id: int | None,
                 *, admin: bool) -> CompanySettings:
    """Felder einer Firma ändern – **derselbe Pfad für jede**.

    * **Plattform-Felder werden ignoriert** – sie laufen über ``PATCH /admin/settings``.
    * **Eine eigene Gesellschaft ändert nur ein Admin** (Bank, Rechtsidentität eines
      Belegstellers); eine fremde Firma pflegt jeder Mitarbeiter – und an ihr gibt es
      nur ihre Identität (``EXTERNAL_FIELDS``).
    * **«Eigenes Unternehmen» setzt nur ein Admin** – und nimmt es nur weg, wo nichts
      daran hängt: nicht beim Betreiber, nicht bei einer Gesellschaft mit Personal. Ihre
      Gebiete fallen dabei an den Betreiber zurück (wie beim Schliessen).
    * **Der Name ist Pflicht** (zugleich das Halter-Label, #301).
    * **Die Schlüssel ziehen nach** – und eine zweite Firma mit derselben UID bzw.
      demselben Namen und derselben Rechtsform wird mit Nummer genannt statt angelegt."""
    if (company.is_own or "is_own" in data) and not admin:
        raise HTTPException(403, detail=f"«{legal_name(company)}» ist eine unserer "
                                        f"Gesellschaften – ändern darf sie nur ein Admin.")
    if "company_name" in data and not (data.get("company_name") or "").strip():
        raise HTTPException(400, detail="Name des Unternehmens fehlt")
    if "legal_form" in data and not (data.get("legal_form") or "").strip():
        raise HTTPException(400, detail=f"«{legal_name(company)}» braucht eine Rechtsform.")
    if "uid_number" in data:
        _assert_uid(data.get("uid_number"))
    own = bool(data.get("is_own", company.is_own))
    if not own and any(data.get(k) for k in OWN_FIELDS):
        raise HTTPException(400, detail="Bankverbindung und Währung gibt es nur bei "
                                        "einer unserer Gesellschaften.")
    if not own:
        _assert_external(data)
    if company.is_own and not own:
        _assert_may_leave(db, company)
    # **Geprüft, bevor etwas geschrieben ist** – eine abgewiesene Änderung hinterlässt
    # keine halb geänderte Zeile in der Sitzung.
    _assert_unique(db, company, data)
    if own != company.is_own:
        company.is_own = own
        log_audit(db, "company_settings", "is_own", str(own).lower(), actor_id,
                  object_id=company.object_id)
    _apply_entity_fields(company, data, db, actor_id)
    db.commit()
    db.refresh(company)
    return company


def _assert_may_leave(db: Session, company: CompanySettings) -> None:
    """Eine Gesellschaft hört auf, unsere zu sein – nur, wenn nichts daran hängt."""
    from ..models import UserProfile
    from .people import STAFF_ROLES
    if is_operator(db, company):
        raise HTTPException(409, detail=f"«{legal_name(company)}» betreibt die Website – "
                                        f"zuerst eine andere Gesellschaft zum Betreiber machen.")
    staff = (db.query(UserProfile)
             .filter(UserProfile.company_object_id == company.object_id,
                     UserProfile.role.in_(STAFF_ROLES))
             .count())
    if staff:
        raise HTTPException(409, detail=f"Bei «{legal_name(company)}» arbeiten {staff} "
                                        f"Personen – sie brauchen zuerst eine andere "
                                        f"unserer Gesellschaften.")
    db.query(CompanyTerritory).filter(CompanyTerritory.company_id == company.id).delete()
    company.iban = None
