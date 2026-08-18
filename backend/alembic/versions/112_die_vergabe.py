"""Die Vergabe – EIN Zyklus für Transport und (künftig) Beschaffung.

Eine Vergabe ist der Vorgang «ein Dritter erbringt eine Leistung für uns». Transport und
Beschaffung sind derselbe Ablauf – anfragen, Angebote bekommen, vergeben, abnehmen –,
also **eine** Tabelle: der Zyklus existiert genau einmal, und das künftige
Beschaffungs-Modul erbt ihn ohne zweite Implementierung (ADR 009 §3.6/§3.7).

**Der Anlass steht als blosse Objektnummer.** Keine Fachspalten, keine
Fallunterscheidung, keine nullable Sonderfelder je Modul: die Fachdaten bleiben dort, wo
sie hingehören, und welcher Typ der Anlass ist, ist ableitbar – dieselbe Regel wie beim
Halter (Migration 111).

``award_offers`` ist die **n-Seite desselben Vorgangs**, kein zweiter Mechanismus: ob ein
Mensch das Angebot im Portal eintippt oder eine API es in zwei Sekunden liefert, ist der
**Kanal**; die Zeile sieht gleich aus. Genau das ist die Einsicht von ADR 009 –
Rate-Shopping IST eine Ausschreibung, sie dauert nur kürzer.

Es entsteht **keine neue Spalte auf einer bestehenden Tabelle**; die Ausfallklasse von
Migration 090 kann hier also nicht auftreten. Fehlende **Tabellen** legt ``create_all()``
im Lifespan an.

Idempotent: die Migration prüft, was es schon gibt, statt es vorauszusetzen.

Revision ID: 112
Revises: 111
"""
import sqlalchemy as sa
from alembic import op

revision = "112"
down_revision = "111"
branch_labels = None
depends_on = None

AWARDS = "awards"
OFFERS = "award_offers"


def _has_table(name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(name)


def _index_names(table: str) -> set[str]:
    return {i["name"] for i in sa.inspect(op.get_bind()).get_indexes(table)}


def upgrade() -> None:
    if not _has_table(AWARDS):
        op.create_table(
            AWARDS,
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            # Der Anlass – eine blosse Objektnummer, ohne Typfeld daneben.
            sa.Column("subject_object_id", sa.BigInteger(), nullable=False),
            # Beim Transport: wohin. Die eine Ausnahme von «keine Fachspalten» – ohne sie
            # wäre eine Fuhre nicht von der nächsten zu unterscheiden.
            sa.Column("target_object_id", sa.BigInteger(), nullable=True),
            sa.Column("state", sa.String(length=20), nullable=False,
                      server_default="angefragt"),
            sa.Column("channel", sa.String(length=20), nullable=False),
            sa.Column("provider_object_id", sa.BigInteger(), nullable=True),
            sa.Column("amount", sa.Numeric(14, 2), nullable=True),
            sa.Column("currency", sa.String(length=3), nullable=True),
            sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("reason", sa.Text(), nullable=True),
            sa.Column("chosen_offer_id", sa.BigInteger(), nullable=True),
            sa.Column("actor_id", sa.BigInteger(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                      server_default=sa.text("now()")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                      server_default=sa.text("now()")),
        )
    if "ix_awards_subject" not in _index_names(AWARDS):
        op.create_index("ix_awards_subject", AWARDS, ["subject_object_id", "id"])

    if not _has_table(OFFERS):
        op.create_table(
            OFFERS,
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("award_id", sa.BigInteger(), nullable=False),
            sa.Column("provider_object_id", sa.BigInteger(), nullable=False),
            sa.Column("amount", sa.Numeric(14, 2), nullable=False),
            sa.Column("currency", sa.String(length=3), nullable=False,
                      server_default="CHF"),
            sa.Column("days", sa.BigInteger(), nullable=True),
            sa.Column("label", sa.String(length=120), nullable=True),
            sa.Column("external_ref", sa.String(length=120), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                      server_default=sa.text("now()")),
        )
    if "ix_award_offers_award" not in _index_names(OFFERS):
        op.create_index("ix_award_offers_award", OFFERS, ["award_id", "id"])


def downgrade() -> None:
    for name in (OFFERS, AWARDS):
        if _has_table(name):
            op.drop_table(name)
