"""Jede Telefonnummer international («+41 52 378 22 47») – auch die schon gespeicherten.

Neu Eingetipptes schreibt ``services/phone.tidy`` so; diese Migration zieht Personen und eigene
Gesellschaften einmal nach. Die Regel steht hier eingefroren (eine Migration liest keinen Code):
Landesnummer mit führender 0 → Vorwahl des Landes (Person: Land der ersten Anschrift, Gesellschaft:
ihr Land, sonst die Schweiz); gruppiert für CH und LI, sonst die getippten Gruppen nach der Vorwahl.
Was sich nicht erkennen lässt, bleibt, wie es ist.

Revision ID: 190
Revises: 189
"""

from alembic import op
from sqlalchemy import text

revision = "190"
down_revision = "189"
branch_labels = None
depends_on = None

_CALLING = {"CH": "41", "LI": "423", "DE": "49", "AT": "43", "IT": "39", "FR": "33",
            "GB": "44", "US": "1", "NL": "31", "BE": "32", "ES": "34", "LU": "352", "PT": "351"}
_NAMES = {"SCHWEIZ": "CH", "LIECHTENSTEIN": "LI", "DEUTSCHLAND": "DE", "ÖSTERREICH": "AT",
          "ITALIEN": "IT", "FRANKREICH": "FR"}
_GROUPS = {"41": (2, 3, 2, 2), "423": (3, 2, 2)}


def _iso2(country):
    c = (country or "").strip().upper()
    return c if c in _CALLING else _NAMES.get(c, "CH")


def _tidy(raw, country):
    text_ = " ".join((raw or "").split())
    digits = "".join(c for c in text_ if c.isdigit() or c == "+")
    if not digits:
        return raw
    if digits.startswith("00"):
        digits = "+" + digits[2:]
    elif not digits.startswith("+"):
        if not digits.startswith("0"):
            return raw
        digits = f"+{_CALLING[_iso2(country)]}{digits.lstrip('0')}"
    for code, groups in _GROUPS.items():
        rest = digits[1 + len(code):]
        if digits.startswith(f"+{code}") and rest.isdigit() and len(rest) == sum(groups):
            parts, i = [], 0
            for n in groups:
                parts.append(rest[i:i + n])
                i += n
            return f"+{code} " + " ".join(parts)
    if text_.startswith("+"):
        return text_
    if text_.startswith("00"):
        return "+" + text_[2:].strip()
    for code in sorted(set(_CALLING.values()), key=len, reverse=True):
        if digits.startswith(f"+{code}") and text_.startswith("0"):
            return f"+{code} {text_.lstrip('0').strip()}"
    return raw


def upgrade() -> None:
    db = op.get_bind()
    people = db.execute(text(
        "SELECT u.id, u.phone, (SELECT a.country FROM addresses a WHERE a.owner_id = u.id "
        "ORDER BY a.id LIMIT 1) FROM user_profiles u WHERE COALESCE(u.phone, '') <> ''")).fetchall()
    for pid, phone, country in people:
        new = _tidy(phone, country)
        if new != phone:
            db.execute(text("UPDATE user_profiles SET phone = :p WHERE id = :i"), {"p": new[:50], "i": pid})
    firms = db.execute(text(
        "SELECT id, phone, country FROM company_settings WHERE COALESCE(phone, '') <> ''")).fetchall()
    for fid, phone, country in firms:
        new = _tidy(phone, country)
        if new != phone:
            db.execute(text("UPDATE company_settings SET phone = :p WHERE id = :i"), {"p": new[:50], "i": fid})


def downgrade() -> None:
    """Die frühere Schreibweise ist nicht gespeichert – zurück bleibt die internationale."""
