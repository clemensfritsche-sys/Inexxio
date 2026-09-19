"""Wem gehört das Stück — `instance_units.owner_object_id`

►►► **Besitz ist ein ZEIGER, kein Status.** ◄◄◄

Ein Stück beantwortet bisher zwei Fragen: *was passiert damit* (``status``) und *wo liegt
es* (``place_*``). Die dritte fehlte — *wem gehört es* —, und der naheliegende Weg, sie in
den Status zu legen («Verkauft»), scheitert am Prozessmodell: solange ein Auftrag läuft,
steht dort ``Im Prozess``, und das ist richtig. Ein Feld mit **zwei Chefs** verliert immer
gegen den, der jede Sekunde schreibt.

Die beiden Achsen sind wirklich unabhängig, und genau das ist der Grund für die Spalte:

    gehört uns  + liegt bei uns   → Lager
    gehört uns  + liegt bei ihm   → Muster · Leihgabe · Konsignation
    gehört ihm  + liegt bei uns   → Beistellung
    gehört ihm  + liegt bei ihm   → verkauft

**``NULL`` ist regulär und heisst «uns».** Alles, was wir erzeugen, gehört uns, bis
jemand es verkauft — der Bestand ändert sich durch diese Migration also **nicht**, und
ein Backfill wäre eine Behauptung über Vergangenes, für die es keine Quelle gibt.

**Sonst die Objektnummer einer Rechtsperson** (Benutzer oder Unternehmen). Kein Typfeld
daneben: Objektnummern sind systemweit eindeutig, der Typ ist ableitbar — dieselbe Regel
wie beim Halter, und der Vorgänger des Ortes hat mit ``location_type`` teuer bezahlt, was
man daraus lernt.

Geschrieben wird sie an genau einer Stelle (``services/owners.transfer``), ausgelöst vom
**Zahlungsmodul**: ein Eigentumsübergang ist die Folge eines Geschäfts.

Revision ID: 138
Revises: 137
"""

from alembic import op
import sqlalchemy as sa

revision = "138"
down_revision = "137"
branch_labels = None
depends_on = None


def _has_table(name: str) -> bool:
    return name in sa.inspect(op.get_bind()).get_table_names()


def _has_column(table: str, name: str) -> bool:
    if not _has_table(table):
        return False
    return any(c["name"] == name for c in sa.inspect(op.get_bind()).get_columns(table))


def _has_index(table: str, name: str) -> bool:
    if not _has_table(table):
        return False
    return any(i["name"] == name for i in sa.inspect(op.get_bind()).get_indexes(table))


def upgrade() -> None:
    # **Idempotent je Objekt, nicht je Tabelle** (die Lehre aus Migration 129): auf dev
    # legt das Spalten-Netz die Spalte an und sonst nichts — ein Wächter der Form
    # «Spalte da → fertig» liesse den Index dort für immer fehlen.
    if not _has_column("instance_units", "owner_object_id"):
        op.add_column("instance_units",
                      sa.Column("owner_object_id", sa.BigInteger(), nullable=True))

    # **Der Index trägt die Frage, die die Bestandsansicht stellt**: «wem gehören die
    # Stücke dieses Artikels». Ohne ihn ist jede Eigentums-Aufstellung ein Full Scan über
    # alle Einzelinstanzen des Hauses.
    if _has_table("instance_units") and not _has_index(
            "instance_units", "ix_instance_units_owner_object_id"):
        op.create_index("ix_instance_units_owner_object_id",
                        "instance_units", ["owner_object_id"])


def downgrade() -> None:
    if _has_index("instance_units", "ix_instance_units_owner_object_id"):
        op.drop_index("ix_instance_units_owner_object_id", table_name="instance_units")
    if _has_column("instance_units", "owner_object_id"):
        op.drop_column("instance_units", "owner_object_id")
