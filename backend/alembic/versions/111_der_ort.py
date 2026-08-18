"""Der Ort – eine append-only Beobachtung je Einzelinstanz.

Das System hatte seit dem Basis-Neuaufbau keinen Ortsbegriff: «in welchem Auftrag» und
«vor welchem Modul» waren beantwortet, «wo liegt es» für **freien** Bestand nicht – und
freier Bestand ist der Normalzustand eines Lagers. Diese Tabelle schliesst die Lücke
(PROCESS_CORE §15, SYSTEM_LOGIC §7, ADR 009).

**Warum eine eigene Tabelle und nicht ein Feld an der Einzelinstanz.** Ein Feld trägt nur
den heutigen Wert; die Frage «wo war es» wäre damit unbeantwortbar, und jede Änderung
schriebe die Vergangenheit um. Der Vorgänger hat es mit einem Feld versucht – plus einer
Standort→Menge-Map daneben, plus einem denormalisierten Skalar, plus einem Umschalter
zwischen beiden (ADR 009 §2.2). Hier ist der aktuelle Ort schlicht die letzte Zeile.

**Warum nicht in ``process_events``.** Der Ereignis-Log hängt an ``order_id``/``step_id``;
eine Ablage muss aber auch **ohne Auftrag** möglich sein. Genau diese Unabhängigkeit ist
die Robustheit: der Ort funktioniert, wenn der Prozess stillsteht.

**Kein ``location_type`` neben der Halter-Objektnummer.** Objektnummern sind systemweit
eindeutig, der Typ ist ableitbar. Ein Typfeld hätte eine Whitelist, eine Validierung und
eine «unbekannter Typ»-Fallunterscheidung nach sich gezogen – im Vorgänger musste ein
entfallener Wert tolerant aufgelöst werden, damit er nicht jede Ansicht zerlegte.

Es entsteht **keine neue Spalte auf einer bestehenden Tabelle**; die Ausfallklasse von
Migration 090 (Modell kennt die Spalte, Migration lief nicht) kann hier also nicht
auftreten. Eine fehlende **Tabelle** legt ``create_all()`` im Lifespan an.

Idempotent: die Migration prüft, was es schon gibt, statt es vorauszusetzen.

Revision ID: 111
Revises: 110
"""
import sqlalchemy as sa
from alembic import op

revision = "111"
down_revision = "110"
branch_labels = None
depends_on = None

TABLE = "unit_places"


def _has_table(name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(name)


def _index_names(table: str) -> set[str]:
    return {i["name"] for i in sa.inspect(op.get_bind()).get_indexes(table)}


def upgrade() -> None:
    if not _has_table(TABLE):
        op.create_table(
            TABLE,
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("instance_unit_id", sa.BigInteger(), nullable=False),
            # Der Halter – eine blosse Objektnummer, ohne Typfeld daneben.
            sa.Column("holder_object_id", sa.BigInteger(), nullable=False),
            sa.Column("actor_id", sa.BigInteger(), nullable=True),
            sa.Column("source", sa.String(length=20), nullable=False,
                      server_default="scan"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                      server_default=sa.text("now()")),
        )

    have = _index_names(TABLE)
    # «Wo ist dieses Stück» – die höchste id je Einzelinstanz.
    if "ix_unit_places_unit_id_desc" not in have:
        op.create_index("ix_unit_places_unit_id_desc", TABLE,
                        ["instance_unit_id", "id"])
    # «Was liegt hier» – die Gegenrichtung, dieselbe Tabelle (§15.9).
    if "ix_unit_places_holder" not in have:
        op.create_index("ix_unit_places_holder", TABLE, ["holder_object_id", "id"])


def downgrade() -> None:
    if _has_table(TABLE):
        op.drop_table(TABLE)
