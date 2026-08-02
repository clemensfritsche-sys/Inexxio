"""Anteile statt Instanzen: ``orders.pick_sources`` – woher ein Entwurf seine Anteile nimmt.

Eine Instanz ist eine **Menge**, und ihre Menge ist immer vollständig aufgeteilt: jeder
Anteil gehört genau einem Auftrag oder ist frei (``instances.reservations``). Wer einen
Anteil auswählt, wählt damit auch, **wem** er ihn wegnimmt – und genau das fehlte bisher im
Datenmodell.

Ohne die Angabe war die Freigabe nicht entscheidbar: hält eine Charge à 4 Stück zwei
Ansprüche (Hauptauftrag 2, Abweichung 2) und ein dritter Auftrag greift 1 Stück, musste das
System **raten**, wer verliert. Jetzt steht es hier: ``{instanz_objektnr: quell_auftrag_id}``;
fehlt ein Eintrag, war es ein freier Anteil und es verliert niemand etwas.

Neue **Spalte auf bestehender Tabelle** → steht auch im Lifespan-Safety-Net
(``main._COLUMN_SAFETY_NET``, 090-Lehre). **Idempotent.**

Revision ID: 096
Revises: 095
"""

from alembic import op
import sqlalchemy as sa

revision = "096"
down_revision = "095"
branch_labels = None
depends_on = None


def _cols(conn) -> set[str]:
    return {c["name"] for c in sa.inspect(conn).get_columns("orders")}


def upgrade() -> None:
    conn = op.get_bind()
    if "pick_sources" not in _cols(conn):
        op.add_column("orders", sa.Column("pick_sources", sa.dialects.postgresql.JSONB(), nullable=True))


def downgrade() -> None:
    conn = op.get_bind()
    if "pick_sources" in _cols(conn):
        op.drop_column("orders", "pick_sources")
