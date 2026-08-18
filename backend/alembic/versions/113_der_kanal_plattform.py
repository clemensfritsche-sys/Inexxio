"""Der Kanal «Plattform»: Etikett, Sendungsnummer – und der Anbieter darf ein NAME sein.

**Ein Frachtführer ist kein ERP-Datensatz.** «Swiss Post» oder «DPD» meldet die
Schnittstelle; einen Lieferanten dafür anzulegen wäre erfundene Daten – und zwar solche,
die jemand später pflegen müsste. Ein Angebot nennt darum seinen Anbieter, und **ob er
ein Datensatz ist, entscheidet, woher es kommt**: im Lieferantenportal ist er einer (er
hat sich angemeldet, um es einzutippen), über die Plattform ist er ein Name.

Darum wird ``provider_object_id`` **nullable** und bekommt ``provider_name`` daneben –
zwei Formen derselben Angabe, nie beide leer (die Prüfung steht im Dienst, wo sie den
Grund nennen kann, statt als Constraint, der nur «verletzt» sagt).

``carrier`` ist der **Adapter**-Schlüssel (``sendcloud``/``shippo``): ohne ihn wüsste der
Kauf nicht, wen er fragen soll – und Raten wäre eine stille Ersatzwahl.

``unit_ids`` hält die **Stücke, die diese Vergabe trägt** (PROCESS_CORE §15.5a): wer
Tarife holt, beschreibt ein Paket, und ein Paket hat einen Inhalt. Gebraucht wird er
genau einmal – beim **Tracking**, das die Ankunft meldet, ohne dass jemand am Ziel steht.

Alles hier sind **neue Spalten auf bestehenden Tabellen** – also die Ausfallklasse von
Migration 090. Sie stehen darum zusätzlich im Lifespan-Sicherheitsnetz
(``main._COLUMN_SAFETY_NET``): die Migration ist die Wahrheit, das Netz der zweite Weg,
und beim Ausfall zählt nur der zweite.

Idempotent: die Migration prüft, was es schon gibt, statt es vorauszusetzen.

Revision ID: 113
Revises: 112
"""
import sqlalchemy as sa
from alembic import op

revision = "113"
down_revision = "112"
branch_labels = None
depends_on = None

#: (Tabelle, Spalte, Typ) – dieselbe Form wie das Sicherheitsnetz, damit ein Vergleich
#: der beiden Listen möglich ist statt einer Behauptung darüber.
COLUMNS = (
    ("awards", "provider_name", sa.String(length=160)),
    ("awards", "carrier", sa.String(length=40)),
    ("awards", "label_url", sa.String(length=500)),
    ("awards", "tracking_number", sa.String(length=120)),
    ("awards", "tracking_url", sa.String(length=500)),
    ("awards", "shipment_ref", sa.Text()),
    ("awards", "unit_ids", sa.dialects.postgresql.JSONB()),
    ("award_offers", "provider_name", sa.String(length=160)),
    ("award_offers", "carrier", sa.String(length=40)),
)


def _cols(table: str) -> set[str]:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    for table in ("awards", "award_offers"):
        have = _cols(table)
        for t, name, type_ in COLUMNS:
            if t == table and name not in have:
                op.add_column(table, sa.Column(name, type_, nullable=True))

    # Der Anbieter darf ein Name sein – also darf die Objektnummer fehlen.
    if "provider_object_id" in _cols("award_offers"):
        op.alter_column("award_offers", "provider_object_id",
                        existing_type=sa.BigInteger(), nullable=True)


def downgrade() -> None:
    for table in ("awards", "award_offers"):
        have = _cols(table)
        for t, name, _type in COLUMNS:
            if t == table and name in have:
                op.drop_column(table, name)
    if "provider_object_id" in _cols("award_offers"):
        op.alter_column("award_offers", "provider_object_id",
                        existing_type=sa.BigInteger(), nullable=False)
