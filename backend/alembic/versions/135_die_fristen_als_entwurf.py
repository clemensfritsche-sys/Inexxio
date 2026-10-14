"""Die Fristen als Entwurf — `vouchers.lead_days` / `vouchers.payment_days`

Testnotiz #985: *«Eingaben in ‹Zahlungsfrist› und ‹Lieferfrist› werden nicht persistiert –
nach einem Reload sind sie wieder weg.»*

Und die Ursache lag **nicht** bei diesen zwei Feldern. Beide Fristen existierten
ausschliesslich an der **Angebotszeile** (`voucher_quotes.lead_days`/`payment_days`), und
die entsteht erst mit dem Anfragen: vorher gab es im ganzen Datenmodell keinen Ort für
sie. Getippt lebten sie darum nur im Browser und reisten allein in der Nutzlast von `ask`
mit – ein Reload verwarf sie, und zwar stillschweigend.

Damit waren sie die **einzige** Angabe des Belegs ohne eigenes Verb: Währung, Aussteller,
Lieferbedingung, Preis, Steuersatz und die beiden Zoll-Angaben werden längst sofort
geschrieben (`currency` · `issuer` · `incoterm` · `price`). Der Fix ist darum kein
Einzelfall-Pflaster, sondern das Schliessen dieser Lücke: **jeder änderbare Wert auf dem
Beleg wird sofort persistiert**, und das neue Verb `terms` ist sein Weg dorthin.

**Die Vereinbarung bleibt, wo sie war.** Diese zwei Spalten sind der *Entwurf*; was
vereinbart wurde, steht weiterhin an der gewählten Angebotszeile (`due_days_of` /
`lead_days_of` lesen sie und fallen auf den Entwurf zurück). Es sind keine zwei Wahrheiten,
sondern zwei **Zeitpunkte** – was wir anbieten wollen, und was zugesagt wurde.

`NULL` heisst «noch nichts gewählt»; die **Null** ist eine Angabe («Sofort» ·
«Vorauszahlung»), darum `Integer` und nicht ein Vorzeichen-Trick.

Revision ID: 135
Revises: 134
"""

from alembic import op
import sqlalchemy as sa

revision = "135"
down_revision = "134"
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
    for name in ("lead_days", "payment_days"):
        if not _has_column("vouchers", name):
            op.add_column("vouchers", sa.Column(name, sa.Integer(), nullable=True))


def downgrade() -> None:
    for name in ("lead_days", "payment_days"):
        if _has_column("vouchers", name):
            op.drop_column("vouchers", name)
