"""Wen der Beleg betrifft — `vouchers.parties`

Testnotiz #1000: *«Wurde beim Anlegen des Zahlungsmoduls kein Partner vorgewählt, lässt er
sich nachträglich nicht mehr setzen. Die Auswahl wird korrekt angezeigt, aber nicht
übernommen/persistiert.»*

**Nachgestellt über die echten Dienstpfade, und die Ursache ist strukturell.** Die Wahl im
freien Feld löste sofort `ask` aus – und `ask` ist die Handlung, mit der der Beleg **nach
aussen** geht: sie verlangt einen vollständigen Beleg (Preis, beide Fristen,
Lieferbedingung, #964/#985). An einem frischen Modul fehlt davon naturgemäss alles, der
Dienst wies mit einem Satz ab, und die getroffene Wahl war weg. Gemessen:

    [ohne alles]  ask 400: Ohne Lieferbedingung ist nicht vereinbart, wer Fracht …
    [bepreist]    ask 400: Ohne Lieferfrist ist es kein Angebot …
    [mit Fristen] ask OK

Damit war *«wen meine ich»* die letzte Angabe des Belegs **ohne eigenes Verb** – dieselbe
Lücke wie bei den Fristen (#985, Migration 135), nur eine Runde später. Die Regel gilt
unverändert: **jeder änderbare Wert des Belegs wird sofort persistiert**, und was nach
aussen geht, ist eine eigene, ausdrückliche Handlung.

**Warum eine Liste und keine Tabelle.** `config.parties` am Modul ist eine *Vorlage* und
sagt, wer in Frage kommt; lässt sie jeden zu, gehört dieselbe Aussage an *diesen* Beleg –
also in derselben Form: eine Liste von Objektnummern, ohne Eigenschaften und ohne
Zustand. Was **hinausgegangen** ist, bleibt eine Zeile (`voucher_quotes`) mit Betrag,
Fristen, Zustand und Datum. Genau diese Trennung war der Grund des Neuaufbaus, und sie
bleibt gewahrt.

`NOT NULL` mit `'[]'`: «keine gewählt» ist eine leere Liste, kein `NULL` – sonst gäbe es
zwei Schreibweisen für dasselbe, und jede Lesestelle müsste beide kennen.

Revision ID: 136
Revises: 135
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "136"
down_revision = "135"
branch_labels = None
depends_on = None


def _has_column(table: str, name: str) -> bool:
    bind = op.get_bind()
    if table not in sa.inspect(bind).get_table_names():
        return False
    return any(c["name"] == name for c in sa.inspect(bind).get_columns(table))


def upgrade() -> None:
    # **Idempotent je Spalte** – die dev-Datenbank kennt kein `alembic upgrade`, dort legt
    # das Spalten-Netz in `main.py` nach (die Lehre aus Migration 129).
    if not _has_column("vouchers", "parties"):
        op.add_column("vouchers", sa.Column(
            "parties", postgresql.JSONB(astext_type=sa.Text()),
            nullable=False, server_default=sa.text("'[]'::jsonb")))


def downgrade() -> None:
    if _has_column("vouchers", "parties"):
        op.drop_column("vouchers", "parties")
