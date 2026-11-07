"""►►► **Vorschläge – die EINE Stelle** (Projektakte §4.3, Bauplan Phase 3, Schritt 3.4). ◄◄◄

Ein Vorschlag ist ein **Ereignis im Log** (``proposal``), sein Entscheid auch
(``proposal.decided``) – keine Tabelle. Die KI schlägt vor, ein Mensch entscheidet:

* ``change`` – ein Feld ändern (``FIELDS``: nur Spalten der eigenen Zeile, die das ERP auch per
  PATCH ändert). **Übernehmen = Tippen**: die Oberfläche schreibt den Wert über dasselbe Feld;
  der Vorschlag ist danach von selbst zu – das Log zeigt die Änderung genau dieses Feldes an genau
  diesem Datensatz (``accepted``, wenn der neue Wert dem Vorschlag gleicht, sonst ``changed``).
  Wer selbst tippt, erledigt ihn ebenso. Ist der Datensatz weg: ``gone``.
* ``create`` – etwas anlegen (``draft``); zu, sobald ein Datensatz dieses Typs mit diesen Werten
  entstanden ist (``accepted``).
* ``file`` – eine Erfassung ablegen (``parts``); entschieden nur durch den Menschen
  («Stimmt so» → ``services/intake.file``, oder ✕).

**Offen wird abgeleitet** (``outcome``): ein Entscheid wird nie «gesetzt», ausser ✕
(``reject``) und «Stimmt so». Der Takt schreibt die abgeleiteten Entscheide fest (``settle``,
Handelnder System, einmal je Vorschlag) – so wird jeder Vorschlag ein **Fall**, aus dem gelernt
wird (``services/memory``).

Zwei Formen einer Regel in diesem Modul: ``problem`` (warum es diesen Vorschlag nicht gibt) ↔
``propose`` (legt nur an, was ``problem`` durchlässt); ``decision_problem`` ↔ ``_assert_open``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Iterable, Optional

from fastapi import HTTPException
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from ..models import CompanySettings, UserProfile
from ..schemas.proposals import DraftOut, IntakePart, ProposalOut, ProposalSource
from . import log, records

#: ►►► **Was ein ``change`` ändern darf – je Typ die Felder und ihr Wort.** ◄◄◄ Nur Spalten der
#: eigenen Zeile, die das ERP auch per PATCH ändert (Person: ``ErpAdminUpdate``, Firma:
#: ``CompanySettingsUpdate``) und die in der Oberfläche als Feld mit genau diesem ``name``
#: stehen (``user-detail.tsx`` · ``organization-detail.tsx``). Die IBAN fehlt mit Absicht: ihre
#: Spalte heisst anders (``iban_encrypted``) und steht verschlüsselt im Log – ein Vergleich wäre
#: dort blind. Ein Wächter prüft jedes Feld (``tests/test_proposals.py``).
FIELDS: dict[str, dict[str, str]] = {
    "user": {"first_name": "Vorname", "last_name": "Nachname", "phone": "Telefon",
             "date_of_birth": "Geburtsdatum"},
    "organization": {"company_name": "Unternehmensname", "legal_form": "Rechtsform",
                     "uid_number": "UID", "vat_number": "MWST-Nummer", "currency": "Währung",
                     "phone": "Telefon"},
}

#: Was ein ``create`` vorausfüllen darf – die Felder des Entwurfs («Neue Person», «Neue Firma»).
CREATE_FIELDS: dict[str, tuple[str, ...]] = {
    "user": ("first_name", "last_name", "email", "phone"),
    "organization": ("company_name", "legal_form", "uid_number", "phone", "email"),
}
CREATE_WORDS = {"user": "Neue Person", "organization": "Neue Firma"}
FILE_WORD = "Ablegen"

#: Die Zeile, die die Nummer trägt, und ihre Tabelle (so steht sie im Log).
MODELS: dict[str, Any] = {"user": UserProfile, "organization": CompanySettings}
TABLES = {"user": "user_profiles", "organization": "company_settings"}

#: Die Entscheide: übernommen · selbst geändert · verworfen · erledigt sich.
OUTCOMES = ("accepted", "changed", "rejected", "gone")


@dataclass(frozen=True)
class Proposal:
    """Ein Vorschlag, wie er im Log steht."""
    id: int
    at: datetime
    object_id: int
    actor_id: Optional[int]
    payload: dict[str, Any]

    @property
    def kind(self) -> str:
        return str(self.payload.get("kind") or "")

    @property
    def source(self) -> dict[str, Any]:
        return self.payload.get("source") or {}


# ─── Werte ─────────────────────────────────────────────────────────────────────────────

def _plain(v: Any) -> str:
    return " ".join(str(v or "").split())


def same(a: Any, b: Any) -> bool:
    """Gleicher Wert – ohne Rücksicht auf Leerraum und Gross-/Kleinschreibung."""
    return _plain(a).casefold() == _plain(b).casefold()


def _row(db: Session, typ: str, object_id: int) -> Any:
    model = MODELS[typ]
    return db.query(model).filter(model.object_id == object_id).first()


def current(row: Any, field: str) -> Optional[str]:
    """Der heutige Wert eines Feldes, als Text."""
    v = getattr(row, field, None)
    if v is None or v == "":
        return None
    return v.isoformat() if isinstance(v, (date, datetime)) else str(v)


def _date(value: str) -> str:
    m = re.fullmatch(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", value)
    d = date(int(m[3]), int(m[2]), int(m[1])) if m else date.fromisoformat(value)
    return d.isoformat()


def tidy(row: Any, typ: str, field: str, value: Any) -> str:
    """►►► **Der Wert, wie das Feld ihn speichert** – dieselbe Schreibweise wie beim Tippen
    (Telefon lesbar, UID gegliedert, Datum ISO). So vergleicht «übernommen?» Gleiches mit
    Gleichem. ``ValueError``, wenn der Wert in dieses Feld nicht passt. ◄◄◄"""
    from ..domain import currency, uid
    from .people import tidy_phone
    v = _plain(value)
    if not v:
        raise ValueError("leer")
    if typ == "user" and field == "phone":
        return tidy_phone(row, v)
    if field == "date_of_birth":
        return _date(v)
    if field == "uid_number":
        if uid.problem(v):
            raise ValueError(uid.problem(v))
        return uid.display(v)
    if field == "currency":
        return currency.assert_code(v)
    return v


# ─── Die Regel: gibt es diesen Vorschlag? ─────────────────────────────────────────────

def _change_problem(db: Session, object_id: int, field: Optional[str], value: Any
                    ) -> tuple[Optional[str], Optional[str]]:
    """(Grund, gespeicherter Wert) für einen ``change``."""
    found = records.labels(db, [object_id]).get(object_id)
    if found is None:
        return f"Datensatz «{object_id}» gibt es nicht.", None
    allowed = FIELDS.get(found.type, {})
    if field not in allowed:
        return f"Das Feld «{field}» lässt sich an «{found.label}» nicht vorschlagen.", None
    row = _row(db, found.type, object_id)
    if row is None or not row.is_active:
        return f"«{found.label}» gibt es nicht mehr.", None
    if found.type == "organization" and not row.is_own:
        from .sites import EXTERNAL_FIELDS
        if field not in EXTERNAL_FIELDS:
            return f"«{allowed[field]}» gibt es an einer fremden Firma nicht.", None
    try:
        stored = tidy(row, found.type, field, value)
    except ValueError as exc:
        return f"«{_plain(value)}» passt nicht ins Feld «{allowed[field]}» ({exc}).", None
    if same(stored, current(row, field)):
        return f"«{allowed[field]}» an «{found.label}» ist schon «{stored}».", None
    return None, stored


def _draft(draft: Any) -> Optional[dict[str, Any]]:
    """Der Entwurf, nur mit den Feldern, die er vorausfüllen darf."""
    if not isinstance(draft, dict) or draft.get("type") not in CREATE_FIELDS:
        return None
    keep = CREATE_FIELDS[draft["type"]]
    values = {k: _plain(v) for k, v in (draft.get("values") or {}).items()
              if k in keep and _plain(v)}
    return {"type": draft["type"], "values": values} if values else None


def _create_problem(db: Session, draft: Optional[dict[str, Any]]) -> Optional[str]:
    if draft is None:
        return "Ein Entwurf braucht einen Typ (Person, Firma) und Werte."
    v = draft["values"]
    if draft["type"] == "user":
        from .people import by_email
        if not (v.get("email") or (v.get("first_name") and v.get("last_name"))):
            return "Eine neue Person braucht E-Mail oder Vor- und Nachname."
        if v.get("email") and by_email(db, v["email"]) is not None:
            return f"Eine Person mit «{v['email']}» gibt es schon."
        return None
    from .sites import by_name, by_uid
    if not v.get("company_name"):
        return "Eine neue Firma braucht einen Namen."
    if (v.get("uid_number") and by_uid(db, v["uid_number"])) or by_name(
            db, v["company_name"], v.get("legal_form") or ""):
        return f"Die Firma «{v['company_name']}» gibt es schon."
    return None


def problem(db: Session, *, object_id: int, kind: str, field: Optional[str] = None,
            value: Any = None, draft: Any = None) -> Optional[str]:
    """►►► **Warum es diesen Vorschlag nicht gibt** – ein Satz, oder ``None``. ◄◄◄
    Feld erlaubt, Wert passt und ist nicht der heutige, Datensatz existiert; ein Entwurf hat
    Werte und legt nichts doppelt an. Dieselbe Regel, die ``propose`` anwendet."""
    if kind == "change":
        return _change_problem(db, object_id, field, value)[0]
    if kind == "create":
        if records.labels(db, [object_id]).get(object_id) is None:
            return f"Datensatz «{object_id}» gibt es nicht."
        return _create_problem(db, _draft(draft))
    if kind == "file":
        return None
    return f"Einen Vorschlag «{kind}» gibt es nicht."


# ─── Lesen ─────────────────────────────────────────────────────────────────────────────

_COLS = "id, at, object_id, actor_id, payload"


def _of(rows: Iterable[Any]) -> list[Proposal]:
    return [Proposal(r.id, r.at, r.object_id, r.actor_id, r.payload or {}) for r in rows]


def load(db: Session, ids: Iterable[int]) -> list[Proposal]:
    ids = sorted({int(i) for i in ids})
    if not ids:
        return []
    return _of(db.execute(text(f"SELECT {_COLS} FROM log WHERE event = 'proposal' "
                               "AND id = ANY(:i) ORDER BY id"), {"i": ids}))


def get(db: Session, proposal_id: int) -> Proposal:
    found = load(db, [proposal_id])
    if not found:
        raise HTTPException(404, detail=f"Vorschlag «{proposal_id}» gibt es nicht.")
    return found[0]


def of_intake(db: Session, intake_id: int, kind: Optional[str] = None) -> list[Proposal]:
    """Die Vorschläge, die aus einer Erfassung kamen (``source.intake``)."""
    rows = _of(db.execute(text(
        f"SELECT {_COLS} FROM log WHERE event = 'proposal' AND id > :i "
        "AND at >= (SELECT at FROM log WHERE id = :i) "
        "AND (payload -> 'source' ->> 'intake')::bigint = :i ORDER BY id"), {"i": intake_id}))
    return [p for p in rows if kind is None or p.kind == kind]


_DECIDED = text("""
SELECT DISTINCT ON ((payload ->> 'proposal')::bigint)
       (payload ->> 'proposal')::bigint AS proposal, payload
  FROM log WHERE event = 'proposal.decided' AND (payload ->> 'proposal')::bigint = ANY(:i)
 ORDER BY (payload ->> 'proposal')::bigint, id DESC""")


def decided(db: Session, ids: Iterable[int]) -> dict[int, dict[str, Any]]:
    """Der festgeschriebene Entscheid je Vorschlag (``proposal.decided``)."""
    ids = sorted({int(i) for i in ids})
    if not ids:
        return {}
    return {r.proposal: r.payload or {} for r in db.execute(_DECIDED, {"i": ids})}


_UNDECIDED = text(f"""
SELECT {_COLS} FROM log p
 WHERE p.event = 'proposal' AND (CAST(:o AS bigint) IS NULL OR p.object_id = :o)
   AND NOT EXISTS (SELECT 1 FROM log d WHERE d.event = 'proposal.decided'
                     AND (d.payload ->> 'proposal')::bigint = p.id)
 ORDER BY p.id LIMIT :n""")


def undecided(db: Session, object_id: Optional[int] = None, limit: int = 1000
              ) -> list[Proposal]:
    """Vorschläge ohne festgeschriebenen Entscheid – die ältesten zuerst."""
    return _of(db.execute(_UNDECIDED, {"o": object_id, "n": limit}))


# ─── Offen? – abgeleitet ───────────────────────────────────────────────────────────────

_CHANGED = text("""
SELECT changes -> :f AS v, action
  FROM log
 WHERE object_id = :o AND table_name = :t AND action IN ('insert', 'update')
   AND changes -> :f IS NOT NULL AND id > :p
 ORDER BY id LIMIT 1""")


def _derive_change(db: Session, p: Proposal) -> Optional[tuple[str, Optional[str]]]:
    found = records.labels(db, [p.object_id]).get(p.object_id)
    if found is None or found.type not in MODELS:
        return "gone", None
    row = _row(db, found.type, p.object_id)
    if row is None or not row.is_active:
        return "gone", None
    field = p.payload.get("field")
    hit = db.execute(_CHANGED, {"f": field, "o": p.object_id, "t": TABLES[found.type],
                                "p": p.id}).first()
    if hit is None:
        return None
    new = hit.v[1] if hit.action == "update" and isinstance(hit.v, list) else hit.v
    new = None if new is None else str(new)
    return ("accepted" if same(new, p.payload.get("value")) else "changed"), new


def _derive_create(db: Session, p: Proposal) -> Optional[tuple[str, Optional[str]]]:
    draft = p.payload.get("draft") or {}
    v = draft.get("values") or {}
    if draft.get("type") == "user":
        q = db.query(UserProfile.object_id).filter(UserProfile.created_at >= p.at)
        if v.get("email"):
            q = q.filter(func.lower(UserProfile.email) == _plain(v["email"]).lower())
        else:
            q = q.filter(func.lower(UserProfile.first_name) == _plain(v.get("first_name")).lower(),
                         func.lower(UserProfile.last_name) == _plain(v.get("last_name")).lower())
    else:
        from .sites import name_key_of, uid_key_of
        key = uid_key_of(v.get("uid_number")) if v.get("uid_number") else None
        q = db.query(CompanySettings.object_id).filter(CompanySettings.created_at >= p.at)
        q = q.filter(CompanySettings.uid_key == key) if key else q.filter(
            CompanySettings.name_key == name_key_of(v.get("company_name"), v.get("legal_form") or ""))
    made = q.first()
    return ("accepted", str(made[0])) if made else None


def derive(db: Session, p: Proposal) -> Optional[tuple[str, Optional[str]]]:
    """►►► **Was der heutige Stand über einen Vorschlag sagt** – (Entscheid, Wert) oder
    ``None`` (offen). Ein ``file`` entscheidet nur der Mensch. ◄◄◄"""
    if p.kind == "change":
        return _derive_change(db, p)
    if p.kind == "create":
        return _derive_create(db, p)
    return None


def outcome(db: Session, p: Proposal) -> Optional[tuple[str, Optional[str]]]:
    """Der Entscheid eines Vorschlags: festgeschrieben, sonst abgeleitet – ``None`` = offen."""
    done = decided(db, [p.id]).get(p.id)
    if done is not None:
        return str(done.get("outcome")), done.get("value")
    return derive(db, p)


def open_list(db: Session, object_id: Optional[int] = None) -> list[Proposal]:
    """Die offenen Vorschläge – an einem Datensatz oder überall."""
    return [p for p in undecided(db, object_id) if derive(db, p) is None]


def open_counts(db: Session) -> dict[int, int]:
    """Je Datensatz, wie viele ``change``/``create`` offen sind (``file`` zählt als Erfassung
    bei der Person, die erfasst hat)."""
    out: dict[int, int] = {}
    for p in open_list(db):
        if p.kind != "file":
            out[p.object_id] = out.get(p.object_id, 0) + 1
    return out


# ─── Schreiben ─────────────────────────────────────────────────────────────────────────

def _open_twin(db: Session, object_id: int, payload: dict[str, Any]) -> Optional[int]:
    """Ein offener Vorschlag, der dasselbe sagt (Feld + Wert bzw. derselbe Entwurf)."""
    for p in open_list(db, object_id):
        if p.kind != payload["kind"]:
            continue
        if p.kind == "change" and p.payload.get("field") == payload["field"] \
                and same(p.payload.get("value"), payload["value"]):
            return p.id
        if p.kind == "create" and p.payload.get("draft") == payload["draft"]:
            return p.id
    return None


def _remember(db: Session, pid: int, payload: dict[str, Any], actor: Optional[int]) -> None:
    """Die Bedeutungs-Zahlen gleich mitnehmen – scheitert still (der Takt holt nach)."""
    from . import memory
    try:
        person = db.query(UserProfile).filter(UserProfile.object_id == actor).first() if actor else None
        with db.begin_nested():
            memory.remember(db, pid, payload, actor=person)
    except Exception as exc:                                   # noqa: BLE001
        print(f"WARNING: memory.remember({pid}) failed: {exc!r}", flush=True)


def propose(db: Session, *, object_id: int, kind: str, source: dict[str, Any],
            actor: Optional[int], field: Optional[str] = None, value: Any = None,
            draft: Any = None, parts: Optional[list[dict[str, Any]]] = None,
            ai: bool = True, remember: bool = True) -> Optional[int]:
    """►►► **Einen Vorschlag festhalten** – oder keinen (``problem`` sagt warum; die KI liefert
    nur Daten, ungültige verwirft der Code). Ein offener Zwilling (gleiches Feld, gleicher Wert)
    ist derselbe Vorschlag: es gibt keinen zweiten. Handelnder ist die KI im Namen von
    ``actor`` (``ai=False``: wer gerade handelt). Gibt die Nummer des Ereignisses zurück. ◄◄◄"""
    payload: dict[str, Any] = {"kind": kind, "source": {k: v for k, v in source.items()
                                                         if v is not None}}
    if kind == "change":
        trouble, stored = _change_problem(db, object_id, field, value)
        if trouble:
            return None
        found = records.labels(db, [object_id])[object_id]
        payload |= {"field": field, "value": stored, "label": FIELDS[found.type][str(field)]}
    elif kind == "create":
        clean = _draft(draft)
        if problem(db, object_id=object_id, kind=kind, draft=clean):
            return None
        payload |= {"draft": clean, "label": CREATE_WORDS[clean["type"]]}
    elif kind == "file":
        payload |= {"parts": parts or [], "label": FILE_WORD}
    else:
        return None
    twin = _open_twin(db, object_id, payload) if kind != "file" else None
    if twin is not None:
        return twin
    pid = log.event(db, "proposal", object_id, payload,
                    **({"kind": "ai", "actor": actor} if ai else {}))
    if remember:
        _remember(db, pid, payload, actor)
    return pid


def decision_problem(db: Session, p: Proposal) -> Optional[str]:
    """Warum über diesen Vorschlag nicht (mehr) entschieden werden kann – oder ``None``."""
    if outcome(db, p) is not None:
        return f"Über den Vorschlag «{p.id}» ist schon entschieden."
    return None


def _assert_open(db: Session, p: Proposal) -> None:
    trouble = decision_problem(db, p)
    if trouble:
        raise HTTPException(409, detail=trouble)


def decide(db: Session, p: Proposal, result: str, value: Optional[str] = None,
           **extra: Any) -> int:
    """Einen Entscheid festschreiben (wer handelt, sagt die Sitzung)."""
    payload = {"proposal": p.id, "outcome": result, **({"value": value} if value is not None else {}),
               **extra}
    return log.event(db, "proposal.decided", p.object_id, payload)


def reject(db: Session, proposal_id: int, actor: UserProfile) -> Proposal:
    """►►► **✕ – verworfen.** Der einzige Entscheid, den ein Mensch über einen ``change`` oder
    ``create`` «setzt»; einen ``file`` verwirft er ebenso. ◄◄◄"""
    p = get(db, proposal_id)
    if p.kind == "file":
        from .intake import assert_may
        assert_may(db, int(p.source.get("intake") or 0), actor)
    _assert_open(db, p)
    decide(db, p, "rejected")
    return p


def settle(db: Session, limit: int = 200) -> int:
    """►►► **Die abgeleiteten Entscheide festschreiben** (der Takt, Handelnder System) – je
    Vorschlag einmal; was noch offen ist, bleibt offen. Gibt zurück, wie viele es waren. ◄◄◄"""
    n = 0
    for p in undecided(db, limit=limit):
        found = derive(db, p)
        if found is not None:
            decide(db, p, found[0], found[1])
            n += 1
    return n


# ─── Die Antwort ───────────────────────────────────────────────────────────────────────

def part_out(p: dict[str, Any], names: dict[int, Any]) -> IntakePart:
    oid = int(p.get("object_id") or 0)
    found = names.get(oid)
    return IntakePart(object_id=oid, label=found.label if found else str(oid),
                      text=str(p.get("text") or ""), subject=str(p.get("subject") or ""))


def out(db: Session, found: list[Proposal]) -> list[ProposalOut]:
    """Die Vorschläge, wie die Oberfläche sie zeigt – mit Namen und heutigem Wert."""
    ids = {p.object_id for p in found}
    for p in found:
        ids |= {int(x.get("object_id") or 0) for x in p.payload.get("parts") or []}
    names = records.labels(db, ids)
    result = []
    for p in found:
        name = names.get(p.object_id)
        row = _row(db, name.type, p.object_id) if name and name.type in MODELS else None
        field = p.payload.get("field")
        src = p.source
        draft = p.payload.get("draft")
        parts = p.payload.get("parts")
        result.append(ProposalOut(
            id=p.id, at=p.at, object_id=p.object_id, object_label=name.label if name else "",
            kind=p.kind, field=field, label=str(p.payload.get("label") or ""),
            value=p.payload.get("value"),
            current=current(row, field) if row is not None and field else None,
            draft=DraftOut(**draft) if draft else None,
            parts=[part_out(x, names) for x in parts] if parts is not None else None,
            source=ProposalSource(text=str(src.get("text") or ""), object_id=src.get("object_id"),
                                  intake=src.get("intake"), at=src.get("at") or p.at)))
    return result


def visible(db: Session, found: list[Proposal], viewer: UserProfile) -> list[Proposal]:
    """Ein ``file`` sieht nur, wer erfasst hat (oder ein Admin) – alle anderen jeder vom Personal."""
    from .intake import may_see
    return [p for p in found if p.kind != "file"
            or may_see(db, int(p.source.get("intake") or 0), viewer)]


def open_for(db: Session, object_id: int, viewer: UserProfile) -> list[ProposalOut]:
    """►►► **Die offenen Vorschläge an einem Datensatz** – für Feld, Angeheftetes, «zu tun». ◄◄◄"""
    return out(db, visible(db, open_list(db, object_id), viewer))
