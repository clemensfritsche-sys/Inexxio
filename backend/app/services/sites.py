"""Unternehmen (Gesellschaften) – die EINE Auflösung «welche gibt es, wer vertritt sie».

Ein Datensatztyp (``company_settings``, Feed-Typ ``organization``); jede Zeile ist eine
vollständige juristische Einheit mit eigener Objektnummer, keine ist einer anderen
untergeordnet. Genau eine Rolle braucht **eine** Antwort: der **Betreiber** der Website
(``is_operator``, partieller Unique-Index); ist keiner markiert, gilt tolerant die älteste.

Nie ein blosses ``.first()`` – die Auflösung läuft nur hier:

  * ``operator(db)`` → der Betreiber; legt ihn an, falls die DB leer ist.
  * ``find_operator(db)`` → dieselbe Rolle, rein lesend (in fremden Transaktionen Pflicht).
  * ``all_companies(db)`` → alle Unternehmen, Betreiber zuerst.
  * ``by_object_id(db, oid)`` → genau dieses Unternehmen («wohin geht die Ware» ↔
    ``operator`` «wer schickt sie»).
"""

from typing import Any

from fastapi import HTTPException
from sqlalchemy import false, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..models import CompanySettings, CompanyTerritory
from . import geography
from .objects import next_object_id

# Was JEDE Gesellschaft selbst trägt (eine juristische Einheit, auch EIN/Steuer/Bank der
# US-Gesellschaft). Feldnamen = DB-Spalten. Nur, was ein Beleg, das Impressum oder eine
# Regel nennt – darum dürfen alle **Pflicht** sein; Zahlungsfrist und Skonto gehören in
# die Offerte. ``website`` ist abgeleitet (``website_url``).
ENTITY_FIELDS = (
    "company_name", "legal_form",
    "street", "street_nr", "zip_code", "city", "country",
    "currency",
    "uid_number", "vat_number",
    "phone",
)
# ``email`` fehlt bewusst: die Kontakt-E-Mail einer eigenen Gesellschaft IST ihr Postfach
# (gesetzt beim Verbinden, geleert beim Trennen, ``services/mailbox``).

# Land (ISO-2, ``address.iso2``) → Funktionswährung (Vorbelegung, editierbar); sonst CHF.
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
    """Die Adresse der Website – **abgeleitet, nicht gepflegt** (``FRONTEND_BASE_URL`` des
    Deployments); Impressum, Briefkopf und Anzeige lesen diese eine Stelle."""
    from ..core.config import get_settings
    return get_settings().frontend_base_url.rstrip("/")

# Eine Plattform-Konfiguration in der Datenbank gibt es nicht: der Google-Maps-Schlüssel
# kommt aus dem Deploy (``config.google_maps_api_key``). Die ``iban`` ist verschlüsselt.


def legal_name(company: Any) -> str:
    """►►► **Der Name der Rechtsperson** – so, wie er auf einen Beleg gehört. ◄◄◄

    Name + Rechtsform, für eine Gesellschaft wie für ein Geschäftskonto (jeder Träger von
    ``company_name`` + ``legal_form``). Die Rechtsform steht **genau einmal** da: ergänzt
    nur, wo sie im Namen fehlt (als ganzes Wort, ohne Gross-/Kleinschreibung) – nie
    «Muster AG AG».
    """
    name = (getattr(company, "company_name", "") or "").strip()
    form = (getattr(company, "legal_form", "") or "").strip()
    if not form or form.casefold() in [w.casefold() for w in name.split()]:
        return name
    return f"{name} {form}".strip()


def find_operator(db: Session) -> CompanySettings | None:
    """Der **Betreiber** als reines Lesen – ``None``, wenn es (noch) keine Gesellschaft gibt.

    Die gewählte (``is_operator``), sonst die **älteste** eigene. Committet nie."""
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
    """Der **Betreiber** – Schreib-Form: legt ihn an, falls die DB leer ist, und committet
    dann einmalig. Wer nicht committen darf, nimmt ``find_operator``."""
    company = find_operator(db)
    if company is None:
        # Die erste Gesellschaft ist ausdrücklich Betreiber (der Alters-Fallback ist nur das
        # Netz); die Id kommt aus der Sequenz.
        company = CompanySettings(is_operator=True, is_own=True,
                                  company_name="Inexxio AG", legal_form="AG",
                                  object_id=next_object_id(db, "organization"))
        _rekey(company)
        db.add(company)
        db.flush()
        db.refresh(company)
    return company


def all_companies(db: Session) -> list[CompanySettings]:
    """**Alle** Unternehmen – auch geschlossene –, Betreiber zuerst, dann nach Alter
    (``id``). Für den **Feed**: «geschlossen» ist ein Zustand, kein Verschwinden. Eine
    Auswahl nimmt ``selectable_companies``. Ruft ``operator`` vorab (frische DB)."""
    operator(db)
    return (
        db.query(CompanySettings)
        .order_by(CompanySettings.id)
        .all()
    )


def selectable_companies(db: Session) -> list[CompanySettings]:
    """Die **wählbaren** (aktiven) Unternehmen – wem lässt sich ein Gebiet zuweisen, wer
    kann fakturieren?"""
    return [c for c in all_companies(db) if c.is_active and c.is_own]


def by_object_id(db: Session, object_id: int | None) -> CompanySettings | None:
    """**Genau dieses** Unternehmen, oder ``None`` – ob das ein Fehler ist, entscheidet der
    Aufrufer."""
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

    Wer einen Beleg stellt, Personal beschäftigt, ein Gebiet besitzt oder die Website
    betreibt, ist eine **eigene, offene** Gesellschaft. Der Satz nennt die Nummer."""
    company = by_object_id(db, object_id)
    if company is None or not company.is_own or not company.is_active:
        raise HTTPException(
            400, detail=f"«{object_id}» ist keine unserer Gesellschaften{what}.")
    return company


def is_operator(db: Session, company: CompanySettings) -> bool:
    """Ist diese Gesellschaft der Betreiber? Die **effektive** Rolle, wie ``find_operator``."""
    op = find_operator(db)
    return bool(op and op.id == company.id)


def set_operator(db: Session, company: CompanySettings, actor_id: int | None) -> CompanySettings:
    """Diese Gesellschaft zum **Betreiber** machen – genau EINE trägt den Titel (alle
    anderen werden ausdrücklich false, der Wechsel ist atomar)."""
    require_own(db, company.object_id)
    db.query(CompanySettings).filter(CompanySettings.id != company.id).update(
        {CompanySettings.is_operator: False})
    company.is_operator = True
    db.flush()
    db.refresh(company)
    return company


def deactivate(db: Session, company: CompanySettings, actor_id: int | None) -> CompanySettings:
    """Ein Unternehmen **schliessen** – Soft-Delete, **umkehrbar** (``reopen``).

    Die Objektnummer bleibt auflösbar; geschlossen heisst: in keiner Auswahl mehr. Nie
    der Betreiber (erst ``set_operator``) und nie die letzte eigene Gesellschaft. Ihre
    Gebiete fallen zurück und kommen beim Wiederöffnen nicht von selbst. Committet."""
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
    db.flush()
    db.refresh(company)
    return company



def reopen(db: Session, company: CompanySettings, actor_id: int | None) -> CompanySettings:
    """Ein geschlossenes Unternehmen **wieder öffnen** – die Gegenhandlung zu
    ``deactivate``. Ist inzwischen eine andere Firma mit demselben Schlüssel offen, wird
    sie genannt."""
    _rekey(company)
    _assert_unique(db, company)
    company.is_active = True
    db.flush()
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

    Vorrang **Land ≻ Region ≻ Betreiber** (``company_territories``; ISO-2 = Land). Massgebend
    ist die Rechnungsadresse des Kunden; ein unbekanntes Land fällt auf den Betreiber. Rein
    lesend."""
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
    """``{iso2: company_object_id}`` für **jedes bekannte Land** – der effektive Besitzer,
    gleiche Vorrangordnung wie ``company_for_country``, als Batch für die Weltkarte. Eine
    Ausnahme leitet die Oberfläche ab (Besitzer ≠ Besitzer der Region)."""
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
    """Wem gehört dieses Gebiet **ohne** eigenen Anspruch? Region → Betreiber, Land → Besitzer
    seiner Region (Grundlage der Aufräum-Regel in ``set_territory``)."""
    op = operator(db)
    if geography.is_country_code(area):
        region = geography.region_of_country(area)
        owner = _claim_owner(db, region) if region else None
        return (owner or op).id
    return op.id


def set_territory(db: Session, area: str, company_object_id: int | None,
                  actor_id: int | None) -> None:
    """Ein **Gebiet** (Region «EUR» oder als Ausnahme ein Land «LI») einer Gesellschaft
    zuweisen. Die Tabelle hält **nur Abweichungen**: fiele es ihr ohnehin zu, wird die
    Zeile entfernt; sonst upsert, genau eine Gesellschaft je Gebiet."""
    code = geography.normalize_area(area)
    if code is None:
        raise HTTPException(400, detail="Unbekanntes Gebiet")
    company = require_own(db, company_object_id) if company_object_id else None
    row = db.query(CompanyTerritory).filter(CompanyTerritory.region == code).first()
    if company is None or company.id == _default_owner_id(db, code):
        if row is not None:
            db.delete(row)
        db.flush()
        return
    if row is None:
        db.add(CompanyTerritory(region=code, company_id=company.id))
    else:
        row.company_id = company.id
    db.flush()


# ─── Anlegen / Ändern – EIN Feldsatz für JEDE Gesellschaft ────────────────────────

# Spalten, die die DB als NOT NULL führt: ein leeres Formularfeld (``None``) wird ``""``
# («noch nicht ausgefüllt»); erzwungen wird nur der Name (das Halter-Label).
_NOT_NULL_TEXT = ("company_name", "legal_form", "country", "email")
# Ausnahme Währung: leer wäre eine kaputte Angabe – ``None`` lässt den bisherigen Wert stehen.
_KEEP_IF_NONE = ("currency",)


def _apply_entity_fields(company: CompanySettings, data: dict, db: Session,
                         actor_id: int | None) -> None:
    """Entitäts-Felder (inkl. IBAN) auf die Gesellschaft schreiben + auditieren; was nicht in
    ``ENTITY_FIELDS`` steht, schreibt diese Stelle nicht."""
    from ..domain import uid
    for key, value in data.items():
        if key == "uid_number":
            # Gespeichert wird die Schreibweise des Belegs (``CHE-123.456.789``); verglichen
            # wird über den Schlüssel.
            value = uid.display(value) or None
        if key == "iban":
            company.iban = value
        elif key in ENTITY_FIELDS:
            if value is None and key in _KEEP_IF_NONE:
                continue
            if value is None and key in _NOT_NULL_TEXT:
                value = ""
            setattr(company, key, value)
    _rekey(company)


#: Angaben, die nur eine **eigene** Gesellschaft trägt (Bank, Funktionswährung).
OWN_FIELDS = ("iban", "currency")

#: ►►► **Was eine FREMDE Firma bei uns ist: ihre Identität, sonst nichts.** ◄◄◄ Name,
#: Rechtsform, UID – die Anschriften gehören den Personen, die für sie bestellen.
EXTERNAL_FIELDS = ("company_name", "legal_form", "uid_number")


# ─── Identität: woran eine Firma erkannt wird ─────────────────────────────────────

def uid_key_of(raw: str | None) -> str | None:
    """Die UID als Schlüssel – ``None``, wo keine steht (``domain/uid.normalize``)."""
    from ..domain import uid
    return uid.normalize(raw) or None


def name_key_of(name: str | None, form: str | None) -> str | None:
    """**Name und Rechtsform als Schlüssel** – ohne Gross-/Kleinschreibung, Satzzeichen
    und doppelte Leerzeichen, die Rechtsform nur einmal. Unscharfes («AG» ↔
    «Aktiengesellschaft») bleibt getrennt; die UID führt zusammen."""
    def norm(value: str | None) -> str:
        # Punkte fallen ersatzlos weg («A.G.» = «AG»), alles andere trennt Wörter.
        text = (value or "").replace(".", "")
        kept = "".join(ch if (ch.isalnum() or ch == "&") else " " for ch in text)
        return " ".join(kept.casefold().split())
    f = "".join(norm(form).split())
    # Die Rechtsform zählt einmal (wie in ``legal_name``).
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
    """Gibt es **eine andere** Firma mit diesem Schlüssel? – dann mit Nummer und Namen, damit
    die Abweisung sagt, **wo** sie schon steht."""
    changes = changes or {}
    uid_key = uid_key_of(changes.get("uid_number", company.uid_number))
    name_key = name_key_of(changes.get("company_name", company.company_name),
                           changes.get("legal_form", company.legal_form))
    query = _active(db).filter(CompanySettings.id != company.id) if company.id \
        else _active(db)
    # Ohne Autoflush – sonst wiese der Index die geänderte Zeile ab, bevor der Satz entsteht.
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


def search(db: Session, query: str, limit: int = 8) -> list[CompanySettings]:
    """Firmen für die Vorschlagsliste – Nummer, Name **oder** UID, nur offene. **Nur für das
    Personal** (Router); eine Person nennt ihre Firma (``resolve``)."""
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
    """Eine Firma anlegen – **ohne** zu committen. **Name und Rechtsform sind Pflicht**; eine
    fremde Firma ist nur ihre Identität (``EXTERNAL_FIELDS``)."""
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
    """Neue Firma anlegen und festschreiben. ``own`` setzt nur ein Admin (Router). Die Id
    kommt aus der Sequenz, nie ``max(id) + 1``."""
    op = operator(db)
    db.query(CompanySettings).filter(CompanySettings.id == op.id).with_for_update().first()
    company = _new(db, data, actor_id, own=own)
    db.flush()
    db.refresh(company)
    return company


def resolve(db: Session, data: dict, actor_id: int | None, *,
            allow_own: bool) -> CompanySettings:
    """►►► **Die Firma, die eine Person nennt** – erkannt oder neu angelegt. ◄◄◄

    Jeder darf eine Firma anlegen; **der Schlüssel entscheidet**, nie ein Mensch:

    * **mit UID**: gleiche UID → dieselbe Firma (der getippte Name zählt nicht); sonst
      bekommt eine Firma ohne UID mit gleichem Namen + Rechtsform die UID; sonst neu.
    * **ohne UID**: gleicher Name **und** gleiche Rechtsform → dieselbe Firma; sonst neu.

    Eine **eigene** Gesellschaft nennt nur das Personal (``allow_own``). Gleichzeitiges
    Anlegen löst der Unique-Index. Committet nicht."""
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
            db.flush()
            return same
        return None
    return by_name(db, name, form)


def apply_update(db: Session, company: CompanySettings, data: dict, actor_id: int | None,
                 *, admin: bool) -> CompanySettings:
    """Felder einer Firma ändern – **derselbe Pfad für jede**.

    * Eine eigene Gesellschaft ändert nur ein Admin; eine fremde jeder Mitarbeiter (nur
      ``EXTERNAL_FIELDS``).
    * «Eigenes Unternehmen» setzt nur ein Admin und nimmt es nur weg, wo nichts daran
      hängt (Betreiber, Personal); die Gebiete fallen an den Betreiber zurück.
    * Der Name ist Pflicht (das Halter-Label); die Schlüssel ziehen nach, eine Dublette
      wird mit Nummer genannt."""
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
    # Geprüft, bevor etwas geschrieben ist.
    _assert_unique(db, company, data)
    if own != company.is_own:
        company.is_own = own
    _apply_entity_fields(company, data, db, actor_id)
    db.flush()
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
