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

from ..domain import accounts
from ..models import UserProfile
from . import sites
from .admin import log_audit

#: Wer im Haus arbeitet – und damit für **eine** unserer Gesellschaften.
STAFF_ROLES = ("admin", "employee")


def name(u: Optional[UserProfile]) -> Optional[str]:
    """Anzeigename einer bereits geladenen Person (``None`` bleibt ``None``)."""
    return u.display_name if u else None


def account_type(u: UserProfile) -> str:
    """►►► **Welcher Kontotyp GILT für diese Person?** ◄◄◄ Die eine Lesestelle.

    Die Regel steht in ``domain/accounts`` (Rolle erzwingt → gespeichert → abgeleitet);
    hier wird sie auf einen geladenen Datensatz angewandt. Jeder Leser fragt **diese**
    Funktion – ein eigenes ``u.account_type or …`` an einer Aufrufstelle wäre die Stelle,
    an der die Ableitung für Altbestand fehlt.
    """
    return accounts.effective(u.role, u.account_type, company_name=u.company_name)


def is_business(u: Optional[UserProfile]) -> bool:
    """Tritt diese Person als **Firma** auf? (Der Kontotyp, nicht die Rolle.)"""
    return u is not None and account_type(u) == accounts.BUSINESS


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

    ►►► **Und ob eine Firma dasteht, sagt der KONTOTYP** (Testnotiz #1042) ◄◄◄ – nicht
    das blosse Vorhandensein des Feldes: wer auf «Privat» wechselt, behält seinen
    Firmennamen in der Zeile, und er darf danach nicht mehr auf dem Beleg stehen.
    ``B2B und B2C brauchen keinen Schalter`` (#914) gilt unverändert: die **Reihenfolge**
    (Firma zuerst, Person als «z. H.») ist dieselbe – gefragt wird nur, *ob* es eine
    Firma gibt, und das ist genau die Frage, die der Kontotyp beantwortet.

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


def assert_account(user: UserProfile, fields: dict[str, Any]) -> None:
    """►►► **Ein Geschäftskonto nennt seine Rechtsperson** (Testnotiz #1042). ◄◄◄

    *«Kontotyp ‹Geschäft› macht Firmenname und Rechtsform zu Pflichtfeldern, UID
    optional.»* – Geprüft **serverseitig**, nicht nur am Feld: die Oberfläche ist die
    freundliche Hälfte derselben Regel, und sie ist nicht der einzige Aufrufer (Konto,
    ERP, künftig ein Shop-Checkout schreiben denselben Datensatz).

    ►►► **Geprüft wird der ÜBERGANG, nicht der Bestand** – wie bei
    ``assert_employment``, und aus demselben Grund: ◄◄◄ eine Prüfung auf den *Zustand*
    machte jeden bestehenden Lieferanten ohne Rechtsform unbearbeitbar – man käme nicht
    einmal dazu, sie nachzutragen, ohne sie im selben Zug mitzuschicken. Abgewiesen wird
    darum, wer den **neuen** schlechten Zustand herstellt: wer auf «Geschäft»
    *umschaltet* oder eine Pflichtangabe *leert*. Den bestehenden meldet der Beleg als
    ``DataGap`` – *streng schreiben, tolerant lesen, Fehlendes benennen.*
    """
    if "account_type" in fields and fields["account_type"] not in accounts.KEYS:
        raise HTTPException(
            400, detail=f"«{fields['account_type']}» ist kein Kontotyp.")
    after = {f: fields[f] if f in fields else getattr(user, f)
             for f, _ in accounts.REQUIRED_FIELDS}
    role = fields.get("role", user.role)
    stored = fields.get("account_type", user.account_type)
    if accounts.effective(role, stored, company_name=after["company_name"]) \
            != accounts.BUSINESS:
        return
    # Nur den Übergang: entweder wird gerade umgeschaltet (Kontotyp bzw. Rolle), oder eine
    # Pflichtangabe wird gerade geleert. Ein Datensatz, der schon so dasteht, bleibt
    # editierbar.
    switching = (fields.get("account_type", user.account_type) != user.account_type
                 or role != user.role)
    emptying = any(f in fields and not (fields[f] or "").strip()
                   for f, _ in accounts.REQUIRED_FIELDS)
    if not (switching or emptying):
        return
    gaps = accounts.missing(after)
    if gaps:
        raise HTTPException(
            400,
            detail=(f"«{user.display_name}» ist ein Geschäftskonto – "
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
    Datensatz. **Dasselbe gilt für den Kontotyp** (``assert_account``)."""
    fields = data.model_dump(exclude_unset=True)
    assert_employment(db, user, fields)
    assert_account(user, fields)
    for key, value in fields.items():
        old_val = getattr(user, key, None)
        old_str = str(old_val) if old_val is not None else None
        new_str = str(value) if value is not None else None
        if old_str != new_str:
            log_audit(db, "user_profiles", key, new_str, actor_id,
                      object_id=user.object_id, old_value=old_str)
        setattr(user, key, value)
    return user
