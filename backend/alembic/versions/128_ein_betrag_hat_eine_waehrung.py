"""Ein Betrag hat eine Währung — `deals.currency` + Beträge mit vier Nachkommastellen

Ein Betrag ohne Währung ist keine Zahl: «1000» ist tausend Franken oder tausend Yen, und
das sind zwei sehr verschiedene Beträge. Solange nur eine Währung vorkommt, fällt es nicht
auf – und beim ersten EU-Kunden ist es still falsch.

**Eine Währung je Vorgang, nicht je Zeile** (``deals.currency``, ISO 4217): zwei Währungen
auf einem Beleg gibt es nicht, das wären zwei Belege. Vorbelegt ist die Währung des
Betreibers; eingefroren mit der **Zusage** – ab dort liegt draussen eine Zusage über
*diese* Summe in *dieser* Währung.

**Und die Beträge werden breiter** (``NUMERIC(14, 2)`` → ``NUMERIC(18, 4)``). Das ist der
Punkt, den man vergisst: fast alle Währungen haben zwei Nachkommastellen, und darum
schreibt man ``NUMERIC(x, 2)`` und merkt nie, dass es falsch ist. **JPY und KRW haben
null**, **KWD hat drei**. Eine Spalte mit zwei Stellen schneidet einem dreistelligen
Betrag still die letzte ab – in der Richtung, in der die Zahl kleiner wird, ohne dass es
jemand sieht. Vier deckt jede ISO-4217-Währung ab; **gerundet** wird trotzdem je Währung
(``domain/currency.quantum``), die Spalte ist nur der Platz dafür.

Bestehende Zeilen ändern sich nicht: ``12.34`` bleibt ``12.34``, nur mit zwei Nullen mehr
Platz dahinter.

Revision ID: 128
Revises: 127
"""

from alembic import op
import sqlalchemy as sa

revision = "128"
down_revision = "127"
branch_labels = None
depends_on = None

#: Die Betrags-Spalten dieses Moduls – Tabelle und Spalte, sonst nichts.
_AMOUNTS = (("deals", "amount"), ("deal_entries", "amount"))


def _columns(table: str) -> dict[str, sa.engine.interfaces.ReflectedColumn]:
    bind = op.get_bind()
    return {c["name"]: c for c in sa.inspect(bind).get_columns(table)}


def upgrade() -> None:
    # **Geprüft, nicht geglaubt**: die dev-Datenbank kennt kein `alembic upgrade`, dort
    # legen die Netze in `main.py` nach. Diese Migration muss darum idempotent sein –
    # sonst scheitert sie genau auf der Umgebung, die läuft.
    if "currency" not in _columns("deals"):
        op.add_column("deals", sa.Column(
            "currency", sa.String(length=3), nullable=False,
            server_default="CHF",
        ))
    for table, col in _AMOUNTS:
        op.alter_column(table, col, type_=sa.Numeric(18, 4),
                        existing_nullable=_columns(table)[col]["nullable"])


def downgrade() -> None:
    # **Zurück auf zwei Stellen heisst runden**, nicht scheitern: PostgreSQL rundet beim
    # Verengen von selbst. Eine dreistellige Währung verlöre dabei ihre letzte Stelle –
    # genau der Grund, aus dem es die Migration gibt.
    for table, col in _AMOUNTS:
        op.alter_column(table, col, type_=sa.Numeric(14, 2),
                        existing_nullable=_columns(table)[col]["nullable"])
    if "currency" in _columns("deals"):
        op.drop_column("deals", "currency")
