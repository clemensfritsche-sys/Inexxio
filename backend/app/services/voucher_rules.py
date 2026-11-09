"""►►► **Was ein Verb am Beleg voraussetzt – Stammdaten und Regeln in zwei Formen.** ◄◄◄

``REQUIRED_FOR`` (welche Angaben eine Stufe braucht) und ``NEEDS`` (welche Stufen ein Verb
braucht) → ``gaps`` (was fehlt). Eigentum (``ownership_problem`` ↔ ``_assert_ownership_chosen``)
und Anfrage (``ask_problem`` ↔ ``_assert_ask``): Grund und Tor stehen nebeneinander, damit Knopf
und Dienst dasselbe sagen.
"""

from typing import Any, Optional
from sqlalchemy.orm import Session
from ..domain import incoterms as inc
from ..domain import modules
from ..domain import voucher as vo
from ..models import (
    ProcessStep,
    Voucher,
)
from .voucher import (
    lines_of, ownership_of, parties_on,
    party_of, priced_dicts,
)
from .voucher_head import (
    document_head, embed_lines,
    has_goods, is_export, issuer_company,
)
from ..domain.errors import Invalid
from .voucher_input import terms_problem


# ---------------------------------------------------------------------------
# ►►► WAS DIESES MODUL AN STAMMDATEN BRAUCHT ◄◄◄
# ---------------------------------------------------------------------------
#
# **``StepNeed`` für Stammdaten**: je Lücke eine Zeile (wo · was · warum), kein Zustand.
# Durchgesetzt über ``can`` (der Knopf fehlt) und ``assert_allowed`` (dieselbe Liste).
# **Gestaffelt und kumulativ**: eine Anfrage braucht weniger als eine Rechnung.
#
# ``(seite, feld, beschriftung, grund)`` – ``seite`` ist ``us`` oder ``party``.
REQUIRED_FOR: dict[str, tuple[tuple[str, str, str, str], ...]] = {
    "ask": (
        ("us", "name", "Firma und Rechtsform",
         "Ein Beleg nennt die Rechtsperson, die ihn stellt."),
        ("us", "address", "Anschrift",
         "Ohne Sitz ist der Aussteller nicht bestimmbar."),
        ("us", "contact", "E-Mail oder Telefon",
         "Ohne Kontaktweg landet jede Rückfrage im Telefonbuch."),
    ),
    # **Die Gegenpartei steht erst mit der ZUSAGE fest.** Beim Anfragen ist sie noch nicht
    # gewählt, und das ist der Sinn der Stufe: man fragt mehrere.
    "agree": (
        ("party", "name", "Name",
         "Ein Beleg braucht einen Adressaten."),
        ("party", "address", "Anschrift",
         "Eine Zusage bindet eine Rechtsperson – die braucht einen Sitz."),
        ("us", "uid", "UID / MWST-Nummer",
         "Ohne sie kann dem Empfänger der Vorsteuerabzug verweigert werden "
         "(MWSTG Art. 26)."),
    ),
    "bill": (
        ("us", "iban", "IBAN",
         "Auf eine Rechnung gehört, wohin überwiesen wird."),
        ("party", "uid", "UID / MWST-Nummer",
         "Beim Reverse Charge schuldet der Leistungsempfänger die Steuer – ohne seine "
         "Nummer trägt das Verfahren nicht."),
    ),
}


#: ►►► **Welche Stammdaten ein Verb braucht** – kumulativ, Stufen aus ``REQUIRED_FOR``. ◄◄◄
#: ``voucher_actions.VERBS`` liest es hier (``needs=NEEDS[…]``) – EINE Stelle.
NEEDS: dict[str, tuple[str, ...]] = {
    "ask": ("ask",),
    "quote": ("ask",),
    "agree": ("ask", "agree"),
    "bill": ("ask", "agree", "bill"),
}


def ownership_problem(row: Voucher) -> Optional[str]:
    """►►► **Ohne Wahl des Eigentums geht kein Beleg hinaus und keiner wird zugesagt.** ◄◄◄
    Zwei Formen einer Regel: dieser Satz am gesperrten Knopf, ``_assert_ownership_chosen``
    als Tor."""
    if ownership_of(row) is None:
        return (f"Ohne Wahl beim {vo.OWNERSHIP_LABEL} ist offen, wem die Stücke danach "
                f"gehören – «" + "» oder «".join(l for _, l in vo.OWNERSHIP) + "».")
    return None


def _assert_ownership_chosen(row: Voucher) -> None:
    problem = ownership_problem(row)
    if problem:
        raise Invalid(problem)


def _has(side: dict[str, Any], field: str) -> bool:
    """Steht diese Angabe wirklich da? **Leer ist nicht vorhanden.**"""
    if field == "contact":
        return bool(side.get("email") or side.get("phone"))
    return bool(side.get(field))


def gaps(db: Session, row: Voucher, *, action: str,
         party_id: Optional[int] = None) -> list[dict[str, Any]]:
    """►►► **Welche Angaben fehlen, um DIESE Handlung zu tun?** ◄◄◄

    Je Lücke eine Zeile mit dem **Datensatz** (klickbar), dem **Feld** und einem Satz, der
    sagt, **warum dieser Beleg sie braucht** – wie bei ``StepNeed``.

    **Gestaffelt und kumulativ** (``Verb.needs``): ``charge`` verlangt auch, was ``ask``
    und ``agree`` verlangen. Die **IBAN** verlangt nur, wer einzieht; die **UID des
    Empfängers** nur ein Beleg mit *Reverse Charge*.
    """
    # **Geprüft wird die Partei, um die es GEHT** (beim Zuschlag aus der Nutzlast); steht
    # noch keine fest (Anfragen), wird die Gegenseite nicht geprüft.
    look = party_id if party_id is not None else party_of(db, row)
    head = document_head(db, row, won=True, party_id=look)
    flow = vo.of(row.direction)
    us, party = ((head["supplier"], head["customer"]) if flow.collects
                 else (head["customer"], head["supplier"]))
    sides = {"us": us, "party": party}
    known = look is not None
    # **Reverse Charge steht an der POSITION** – und nur eine gebuchte Zeile verlangt die
    # Nummer; vor der Zusage gibt es noch nichts, wofür sie zählte.
    reverse = any(ln.vat == "reverse" for ln in lines_of(db, row))
    out: list[dict[str, Any]] = []
    for stage in NEEDS.get(action, ()):
        for side, field, label, why in REQUIRED_FOR[stage]:
            if field == "iban" and not flow.collects:
                continue
            if side == "party" and not known:
                continue
            if field == "uid" and side == "party" and not reverse:
                continue
            if field == "iban":
                # **Die IBAN der Gesellschaft, die den Beleg stellt** – nicht die des
                # Betreibers: überwiesen wird an den Aussteller.
                if getattr(issuer_company(db, row), "iban", None):
                    continue
                out.append(_gap(sides["us"], label, why))
                continue
            if not _has(sides[side], field):
                out.append(_gap(sides[side], label, why))
    return out


def _gap(side: dict[str, Any], label: str, why: str) -> dict[str, Any]:
    """Eine Lücke als Zeile – **wo** sie hingehört, **was** fehlt, **warum**."""
    return {
        "record_object_id": side.get("object_id"),
        "record_label": side.get("name") or side.get("label") or "",
        "field_label": label,
        "why": why,
    }


def ask_problem(db: Session, row: Voucher, step: ProcessStep,
                parties: Optional[list[int]] = None,
                lines: Optional[list[dict[str, Any]]] = None) -> Optional[str]:
    """►►► **Was fehlt noch, damit dieser Beleg HINAUSGEHEN kann?** ◄◄◄ – oder ``None``.

    Zwei Formen einer Regel: der Satz reist mit (``VoucherEmbed.ask_problem``, der Knopf
    steht gesperrt da und sagt im Hover, was fehlt), ``_assert_ask`` wirft ihn. Pflicht ist,
    was auf dem Beleg steht – Preis je Position, bei einer Ausfuhr die Zoll-Angaben, bei Ware
    die Lieferbedingung, beide Fristen, das Eigentum –, gelesen wie es dasteht
    (``embed_lines``). Alles Fehlende auf einmal, je Position benannt. ``parties``/``lines``
    gibt der Aufrufer mit, wo er sie schon hat.
    """
    flow = vo.of(row.direction)
    # **Ohne Gegenpartei gibt es nichts anzufragen** – zwei Quellen, dieselben wie in
    # ``_ask``: was die Definition zulässt und wen der Beleg selbst schon trägt.
    if parties is None:
        parties = modules.Beleg.parties_allowed(step.config) or parties_on(row)
    if not parties:
        return (f"Ohne {vo.PARTY} gibt es nichts anzufragen – dieses Modul lässt "
                f"jeden zu, also muss hier stehen, wen es betrifft.")
    found: list[str] = []
    priced = flow.quoted_by == vo.BY_US
    # ►►► **Zoll nur bei einer Ausfuhr** – Tarif, Ursprung und Gewicht braucht der Zoll,
    # im Inland niemand. ◄◄◄
    export = is_export(db, row)
    for ln in (lines if lines is not None else embed_lines(db, row)):
        what = f"Position «{ln['article_name'] or ln['id']}»"
        if priced and ln["price"] is None:
            found.append(f"{what}: ohne Preis gibt es nichts anzubieten.")
        if not export or ln.get("is_service"):
            continue
        gaps = [label for key, label in (("hs_code", vo.HS_CODE_LABEL),
                                         ("origin_country", vo.ORIGIN_LABEL),
                                         ("weight_kg", vo.WEIGHT_LABEL))
                if not str(ln.get(key) or "").strip()]
        if gaps:
            found.append(f"{what}: {' · '.join(f'«{g}»' for g in gaps)} fehlt – eine "
                         f"Ausfuhr braucht es. Am Artikel hinterlegt, steht es auf jedem "
                         f"Beleg von selbst; hier eingetragen, gilt es für diesen Beleg.")
    # **Eine Lieferbedingung gibt es nur bei Ware** – eine Dienstleistung reist nicht.
    if not row.incoterm and has_goods(db, row):
        found.append(f"Ohne {inc.LABEL} ist nicht vereinbart, wer Fracht, Versicherung "
                     f"und Zoll trägt – und genau darüber wird sonst gestritten.")
    if priced:
        if not priced_dicts(db, row) and not any("Preis" in f for f in found):
            found.append(f"Ohne Preis gibt es nichts anzubieten – bei einer {flow.label} "
                         f"nennen wir ihn, nicht der {vo.PARTY}.")
        found.append(terms_problem(row.lead_days, row.payment_days) or "")
    # **Zuletzt das Eigentum** – bewusst gewählt, ohne Vorbelegung.
    found.append(ownership_problem(row) or "")
    found = [f for f in found if f]
    if len(found) < 2:
        return found[0] if found else None
    return "\n".join(f"– {f}" for f in found)


def _assert_ask(db: Session, row: Voucher, step: ProcessStep,
                parties: list[int]) -> None:
    """Das Tor zu ``ask_problem`` – **derselbe Satz**, nur geworfen."""
    problem = ask_problem(db, row, step, parties=parties)
    if problem:
        raise Invalid(problem)
