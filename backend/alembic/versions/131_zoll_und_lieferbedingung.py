"""Zoll und Lieferbedingung — `articles.hs_code`/`origin_country`, `deals.incoterm`

Vier Spalten aus einer Frage: **was muss auf dem Beleg stehen, damit niemand zurückfragt?**

**`articles.hs_code`** — die Zolltarifnummer. Ihre ersten **sechs Stellen sind weltweit
identisch** (Harmonisiertes System der Weltzollorganisation, rund 200 Länder); darüber
hinaus ist sie national (EU 8/10, CH 8, US 10). Gespeichert werden darum 6 bis 8 – das
Importland hängt seine eigene Verlängerung ohnehin selbst an.

**`articles.origin_country`** — das Ursprungsland (ISO-2). Es ist **nicht** aus dem
HS-Code ableitbar und **nicht** das Versandland: eine eigene Angabe.

Beide sitzen am **Artikel**, weil sie Eigenschaften der *Sache* sind – und damit reisen
sie über die Spezifikation von selbst auf jede Offerte und jede Rechnung, ohne dass der
Geldvorgang von ihnen weiss.

**`deals.incoterm` + `incoterm_place`** — wer Fracht, Versicherung und Zoll trägt
(Incoterms 2020). Sie gehören an den **Vorgang**, nicht an das Bewegen-Modul: ein
Incoterm ist eine *Vereinbarung* zwischen zwei Parteien, kein physischer Vorgang – das
Bewegen-Modul führt aus, was hier vereinbart wurde. Eingefroren mit der Zusage wie die
Währung.

Revision ID: 131
Revises: 130
"""

from alembic import op
import sqlalchemy as sa

revision = "131"
down_revision = "130"
branch_labels = None
depends_on = None


def _has_column(table: str, name: str) -> bool:
    bind = op.get_bind()
    return any(c["name"] == name for c in sa.inspect(bind).get_columns(table))


def upgrade() -> None:
    # **Idempotent JE SPALTE** – die dev-Datenbank kennt kein `alembic upgrade`, dort legt
    # das Spalten-Netz in `main.py` nach. Ein `if irgendetwas da: return` hiesse, dass die
    # letzte Spalte genau dort nie ankommt (die Lehre aus Migration 129).
    if not _has_column("articles", "hs_code"):
        op.add_column("articles", sa.Column("hs_code", sa.String(12), nullable=True))
    if not _has_column("articles", "origin_country"):
        op.add_column("articles",
                      sa.Column("origin_country", sa.String(2), nullable=True))
    if not _has_column("deals", "incoterm"):
        op.add_column("deals", sa.Column("incoterm", sa.String(3), nullable=True))
    if not _has_column("deals", "incoterm_place"):
        op.add_column("deals",
                      sa.Column("incoterm_place", sa.String(120), nullable=True))


def downgrade() -> None:
    for table, name in (("deals", "incoterm_place"), ("deals", "incoterm"),
                        ("articles", "origin_country"), ("articles", "hs_code")):
        if _has_column(table, name):
            op.drop_column(table, name)
