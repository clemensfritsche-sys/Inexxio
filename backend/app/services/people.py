"""Personen-Anzeige – **EINE** Stelle für «wie heisst diese Person?».

Die Regel selbst steht am Modell (``UserProfile.display_name``: «Vorname Nachname»
→ Firma → E-Mail, Notiz #291). Was fehlte, war die eine Stelle, die sie *anwendet*: derselbe
Zweizeiler lag sechsmal im Code (``sales._user_name``, ``resource._user_name``,
``document._user_name``, ``orders._supplier_name``, ``article_process._supplier_name``,
``document_files._user_name``, dazu ``locations._user_label``).

Das war nicht nur Wiederholung, sondern eine **Falle**: die Varianten schlugen in
ZWEI verschiedenen Schlüsseln nach – teils über die 9-stellige ``object_id``, teils
über die interne ``id``. Beides sind Ganzzahlen; wer die falsche Variante erwischt,
bekommt lautlos den falschen (oder keinen) Namen. Darum tragen die Funktionen hier
den Schlüssel **im Namen**.
"""

from typing import Any, Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..models import UserProfile
from . import sites
from .admin import log_audit

#: Wer im Haus arbeitet – und damit für **eine** unserer Gesellschaften.
#:
#: ►►► **Das ist die EINE Frage, die die Rolle beantwortet** (Testnotiz #1043). ◄◄◄ Sie
#: hatte einmal vier Werte; «Lieferant» und «Kunde» standen darunter und waren beide eine
#: Aussage über **Vorgänge**, nicht über die Person – wer Partner einer Ausgabe ist, ist
#: dort Lieferant, bei einer Einnahme Kunde, und dieselbe Person kann beides sein. Geblieben
#: sind ``admin`` · ``employee`` · ``user``: *darf ins ERP* ↔ *darf es nicht*.
ROLES = ("admin", "employee", "user")
STAFF_ROLES = ("admin", "employee")

#: ►►► **Was ein Firmenname nach sich zieht** (Testnotiz #1043). ◄◄◄ Die Rechtsform macht
#: aus «Muster» die Rechtsperson «Muster AG» – ohne sie ist ein Beleg keiner (MWSTG
#: Art. 26, dieselbe Angabe, die ``sites.legal_name`` an unserer eigenen Seite anhängt).
#: Die **UID bleibt freiwillig**: nur MWST-pflichtige Firmen haben eine, und ein
#: Pflichtfeld, das die Hälfte der Firmen nicht ausfüllen kann, ist keines.
COMPANY_REQUIRES = (("legal_form", "Rechtsform"),)

#: Die Felder der Rechnungsadresse, die der frühere Schalter als **Kopie** füllte.
_INVOICE_COPY = ("first_name", "last_name", "address_line1", "address_line2",
                 "city", "postal_code", "country")


def repair_sql() -> tuple[str, ...]:
    """►►► **Eine Datenänderung braucht IMMER auch ein Netz** (Testnotiz #1043). ◄◄◄

    Die dev-Datenbank fährt kein ``alembic upgrade head`` (#778) – eine Reparatur, die nur
    in einer Migration steht, erreicht sie nie. Beide Anweisungen hier stehen darum **an
    einer** Stelle und werden von der Migration **und** vom Lifespan-Netz gelesen;
    zweimal ausgeschrieben wären es zwei Wahrheiten (dieselbe Bauart wie
    ``domain/voucher.invoice_backfill_sql``).

    **(1) Die Rolle wird zum Zugang.** Wer nicht ins ERP darf, heisst ``user`` – vorher
    ``customer`` bzw. ``supplier``. Das ist nicht Kosmetik: ``Role`` an der Tür kennt die
    Altwerte nicht mehr, also liefe **jedes** Speichern an so einer Zeile in ein 422,
    und zwar an einer Angabe, die niemand angefasst hat.

    **(2) Die kopierte Rechnungsadresse fällt.** «Rechnungsadresse = Lieferadresse» schrieb
    die Hauptadresse in die Rechnungsfelder; ``billing_of`` liest sie seither als *eigene*
    Rechnungsadresse, und der Beleg zeigt dieselbe Anschrift zweimal untereinander. Geräumt
    wird **nur die exakte Kopie** – stimmen alle sieben Felder mit der Hauptadresse
    überein, geht keine Angabe verloren.

    Beide sind **selbstbegrenzend**: nach dem ersten Lauf trifft die Bedingung nicht mehr
    zu. Eine Reparatur mit einer gepflegten Liste veraltet (die Lehre aus Migration
    ``110``) – diese hier kann es nicht, weil die Liste **der Katalog selbst** ist
    (``ROLES``) und weil die zweite ihre eigene Voraussetzung wegnimmt.

    ►►► **Geheilt wird, was der Katalog NICHT kennt.** ◄◄◄ Gemessen, nicht geglaubt: die
    erste Fassung stand auf ``WHERE role NOT IN ('admin','employee')`` – sie schrieb damit
    bei **jedem** Start jede Nicht-Personal-Zeile neu, auch die längst richtigen (gemessen:
    zweiter Lauf 2 statt 0 Zeilen). Dieselbe Fehlerform wie bei der Stück-Reparatur in
    Migration ``110``, nur eine Nummer harmloser.
    """
    roles = ", ".join(f"'{r}'" for r in ROLES)
    same = " AND ".join(
        f"coalesce(invoice_{f}, '') = coalesce({f}, '')" for f in _INVOICE_COPY)
    clear = ", ".join(f"invoice_{f} = NULL" for f in _INVOICE_COPY)
    return (
        f"UPDATE user_profiles SET role = 'user' WHERE role NOT IN ({roles})",
        f"UPDATE user_profiles SET {clear} "
        f"WHERE coalesce(invoice_address_line1, '') <> '' AND {same}",
    )


def name(u: Optional[UserProfile]) -> Optional[str]:
    """Anzeigename einer bereits geladenen Person (``None`` bleibt ``None``)."""
    return u.display_name if u else None


def is_business(u: Optional[UserProfile]) -> bool:
    """►►► **Tritt diese Person als FIRMA auf?** ◄◄◄ Die eine Lesestelle – und die eine
    Regel: *der Firmenname IST die Erklärung.*

    Hier stand einmal ein Kontotyp (*Privat ↔ Geschäft*) mit einer dreistufigen Auflösung
    daneben (Rolle erzwingt → gespeicherter Wert → aus dem Namen abgeleitet). Er sagte,
    was der Name selbst sagt; die Frage hat genau eine Antwort, also auch nur eine Quelle.

    *Jeder Leser fragt diese Funktion* – ein eigenes ``u.company_name and …`` an einer
    Aufrufstelle wäre die Stelle, an der das Trimmen fehlt.
    """
    return u is not None and bool((u.company_name or "").strip())


def billing_name(u: Optional[UserProfile]) -> list[str]:
    """►►► **Wie diese Partei auf einem BELEG steht** – Firma zuerst. ◄◄◄

    ``display_name`` ist bewusst **person-first** («Vorname Nachname → Firma → E-Mail»,
    Notiz #291), und im ERP ist das richtig: man arbeitet mit Menschen.

    Auf einer **Rechnung** ist es falsch. Schuldner ist die *Muster AG*, nicht der
    Einkäufer, der dort arbeitet – und wer den Beleg bezahlt, braucht die Rechtsperson,
    die er in seiner Buchhaltung führt.

    Zurück kommen **Zeilen**, nicht ein Name: die Firma, und darunter die Person als
    «z. H.», wenn beide da sind. Ohne Firma bleibt die Person – das ist der B2C-Fall und
    korrekt.

    ►►► **Und ob eine Firma dasteht, sagt der FIRMENNAME** (Testnotiz #1043). ◄◄◄
    ``B2B und B2C brauchen keinen Schalter`` (#914) gilt damit wieder wörtlich: die
    **Reihenfolge** (Firma zuerst, Person als «z. H.») ist dieselbe, und gefragt wird nur,
    *ob* es eine Firma gibt. Gelesen wird sie über ``is_business`` und nicht roh – dort
    steht das Trimmen.

    Die **Rechtsform** gehört dazu: «Muster AG» ist eine Rechtsperson, «Muster» ist
    keine. Zusammengesetzt wird sie an derselben einen Stelle wie bei unserer eigenen
    Seite (``sites.legal_name``) – auch mit derselben Ausnahme, damit aus «Muster AG» +
    «AG» nicht «Muster AG AG» wird.

    *Zwei Formen einer Regel sind in Ordnung; zwei Regeln nicht – darum steht sie hier
    neben ``display_name`` und nicht im Geldvorgang.*
    """
    if u is None:
        return []
    person = " ".join(p for p in (u.first_name, u.last_name) if p).strip()
    company = sites.legal_name(u) if is_business(u) else ""
    if company and person:
        return [company, f"z. H. {person}"]
    return [company or person or u.email]


def name_by_id(db: Session, user_id: Optional[int]) -> Optional[str]:
    """Anzeigename über die **interne** Primärschlüssel-Id (Fremdschlüssel-Spalten
    wie ``supplier_id``, ``customer_id``, ``inspector_id``, ``uploaded_by``)."""
    if not user_id:
        return None
    return name(db.query(UserProfile).filter(UserProfile.id == user_id).first())


def assert_employment(db: Session, user: UserProfile, fields: dict[str, Any]) -> None:
    """►►► **Wer Mitarbeiter WIRD, gehört zu einer Gesellschaft** (Testnotiz #905). ◄◄◄

    Ohne diese Zuordnung kann ein Beleg nicht sagen, wer ihn stellt – er nähme still den
    Betreiber, also die Gesellschaft, die die Website vertritt, auch wenn eine
    Schwestergesellschaft fakturiert.

    ►►► **Geprüft wird der ÜBERGANG, nicht der Bestand.** ◄◄◄ Das ist die eine
    Feinheit, und sie ist bewusst so: eine Prüfung auf den *Zustand* machte jede
    bestehende Personalzeile ohne Gesellschaft unbearbeitbar – man käme nicht einmal mehr
    dazu, die Gesellschaft nachzutragen, ohne sie im selben Zug mitzuschicken. Die
    Schreibstelle weist darum den **neuen** schlechten Zustand ab; den **bestehenden**
    meldet der Geldvorgang als ``DataGap`` – dieselbe Arbeitsteilung wie überall:
    *streng schreiben, tolerant lesen, Fehlendes benennen.*

    Und die Gesellschaft muss es **geben**: eine Objektnummer, die auf nichts zeigt, ist
    schlimmer als keine – sie sieht aus wie eine Zuordnung.
    """
    company = fields["company_object_id"] if "company_object_id" in fields \
        else user.company_object_id
    if company is not None and sites.by_object_id(db, company) is None:
        raise HTTPException(
            400, detail=f"«{company}» ist keine unserer Gesellschaften.")
    role = fields.get("role", user.role)
    if role in STAFF_ROLES and role != user.role and company is None:
        raise HTTPException(
            400,
            detail=(f"«{user.display_name}» braucht eine Gesellschaft, um als "
                    f"{'Administrator' if role == 'admin' else 'Mitarbeiter'} zu "
                    f"arbeiten – auf einem Beleg steht, wer ihn stellt."),
        )


def assert_company(user: UserProfile, fields: dict[str, Any]) -> None:
    """►►► **Wer eine Firma nennt, nennt ihre Rechtsform** (Testnotiz #1043). ◄◄◄

    Das ist die **ganze** Regel, die vom Kontotyp übrig bleibt – und sie ist dieselbe wie
    vorher, nur ohne den Schalter davor: «Muster» ist keine Rechtsperson, «Muster AG» ist
    eine, und auf einem Beleg steht die, die haftet (MWSTG Art. 26). Geprüft
    **serverseitig**, nicht nur am Feld: die Oberfläche ist die freundliche Hälfte, und sie
    ist nicht der einzige Aufrufer (Konto, ERP, künftig ein Shop-Checkout schreiben
    denselben Datensatz).

    ►►► **Geprüft wird der ÜBERGANG, nicht der Bestand** – wie bei ``assert_employment``,
    und aus demselben Grund: ◄◄◄ eine Prüfung auf den *Zustand* machte jede bestehende
    Zeile ohne Rechtsform unbearbeitbar – man käme nicht einmal dazu, sie nachzutragen,
    ohne sie im selben Zug mitzuschicken. Abgewiesen wird darum, wer den **neuen**
    schlechten Zustand herstellt: wer einen Firmennamen *setzt* oder eine Pflichtangabe
    *leert*. Den bestehenden meldet der Beleg als ``DataGap`` – *streng schreiben,
    tolerant lesen, Fehlendes benennen.*

    **Den Namen zu leeren ist erlaubt**: das heisst «ist keine Firma mehr», und dann gibt
    es nichts zu verlangen. Genau das ersetzt den Schalter.
    """
    after = {f: fields[f] if f in fields else getattr(user, f)
             for f in ("company_name",) + tuple(f for f, _ in COMPANY_REQUIRES)}
    if not (after["company_name"] or "").strip():
        return
    naming = ("company_name" in fields
              and (fields["company_name"] or "").strip() != (user.company_name or "").strip())
    emptying = any(f in fields and not (fields[f] or "").strip()
                   for f, _ in COMPANY_REQUIRES)
    if not (naming or emptying):
        return
    gaps = tuple(label for f, label in COMPANY_REQUIRES if not (after[f] or "").strip())
    if gaps:
        raise HTTPException(
            400,
            detail=(f"«{after['company_name']}» ist ein Firmenname – "
                    f"{' und '.join(gaps)} {'fehlen' if len(gaps) > 1 else 'fehlt'}: "
                    f"auf einem Beleg steht die Rechtsperson, nicht ihr Vertreter."),
        )


def apply_profile_update(db: Session, user: UserProfile, data, actor_id: int) -> UserProfile:
    """Profil-Felder schreiben – **EIN** Pfad für beide Oberflächen.

    Denselben Datensatz beschreiben zwei Wege: der ERP-Benutzer-Datensatz (Personal)
    und die Selbstbedienung im Konto (die Person auf ihre eigenen Daten). Das ist so
    gewollt – beides ist derselbe Datensatz, keine zweite Wahrheit. Nur **protokolliert**
    hat es bisher allein der ERP-Weg: eine im Konto geänderte IBAN hinterliess keine
    Spur im Audit-Log, eine im ERP geänderte schon.

    Diese Stelle vereint beides: gleiche Zuweisung, gleiche Protokollierung, egal von
    welcher Oberfläche. Committet NICHT (der Aufrufer entscheidet).

    **Die Anstellungsregel steht hier und nicht im Router** (``assert_employment``): die
    Tür ist nicht der einzige Aufrufer, und zwei Oberflächen schreiben denselben
    Datensatz. **Dasselbe gilt für die Rechtsperson** (``assert_company``)."""
    fields = data.model_dump(exclude_unset=True)
    assert_employment(db, user, fields)
    assert_company(user, fields)
    for key, value in fields.items():
        old_val = getattr(user, key, None)
        old_str = str(old_val) if old_val is not None else None
        new_str = str(value) if value is not None else None
        if old_str != new_str:
            log_audit(db, "user_profiles", key, new_str, actor_id,
                      object_id=user.object_id, old_value=old_str)
        setattr(user, key, value)
    return user
