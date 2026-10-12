"""Firma = Identität, Adressen = Adressbuch der Person, der Beleg friert mit der Zusage ein.

* ``company_settings.uid_key`` / ``name_key`` – woran eine Firma erkannt wird (gleiche UID,
  ohne UID gleicher Name und gleiche Rechtsform), mit **partiellen Unique-Indizes**: eine
  Dublette ist nicht verboten, sondern unmöglich (``sites.backfill_keys``, ``KEY_INDEXES``).
* ``addresses`` – das Adressbuch: beliebig viele Anschriften je Person, je eine
  Standard-Liefer- und Standard-Rechnungsadresse. Die Felder ``address_*``/``invoice_*`` am
  Benutzer ziehen hinein (``address_book.migrate_sql``) und werden geleert; gedroppt wird
  im Folge-Deploy.
* ``vouchers.bill_to_company`` · ``billing_address_id`` · ``delivery_address_id`` – an wen
  und wohin, gewählt bis zur Zusage; ``vouchers.head`` – der Belegkopf, eingefroren mit ihr.

Dieselben Schritte stehen im Lifespan-Netz (``main._ensure_columns``) – die dev-Datenbank
fährt kein ``alembic upgrade head`` (#778).
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

from app.services.address_book import migrate_sql
from app.services.sites import KEY_INDEXES, backfill_keys

revision = "143"
down_revision = "142"
branch_labels = None
depends_on = None


def _columns(table: str) -> set[str]:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def upgrade() -> None:
    bind = op.get_bind()
    have = _columns("company_settings")
    if "uid_key" not in have:
        op.add_column("company_settings", sa.Column("uid_key", sa.String(20)))
    if "name_key" not in have:
        op.add_column("company_settings", sa.Column("name_key", sa.String(320)))
    backfill_keys(bind)
    for stmt in KEY_INDEXES:
        bind.execute(sa.text(stmt))

    if "addresses" not in _tables():
        op.create_table(
            "addresses",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("owner_id", sa.BigInteger(), sa.ForeignKey("user_profiles.id"),
                      nullable=False, index=True),
            sa.Column("street1", sa.String(255), nullable=False, server_default=""),
            sa.Column("street2", sa.String(255)),
            sa.Column("zip", sa.String(20), nullable=False, server_default=""),
            sa.Column("city", sa.String(100), nullable=False, server_default=""),
            sa.Column("region", sa.String(100)),
            sa.Column("country", sa.String(2), nullable=False, server_default="CH"),
            sa.Column("email", sa.String(255)),
            sa.Column("is_default_delivery", sa.Boolean(), nullable=False,
                      server_default=sa.text("false")),
            sa.Column("is_default_billing", sa.Boolean(), nullable=False,
                      server_default=sa.text("false")),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                      server_default=sa.text("now()")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                      server_default=sa.text("now()")),
            sa.Column("is_active", sa.Boolean(), nullable=False,
                      server_default=sa.text("true")),
        )
    bind.execute(sa.text(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_addresses_default_delivery "
        "ON addresses (owner_id) WHERE is_active AND is_default_delivery"))
    bind.execute(sa.text(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_addresses_default_billing "
        "ON addresses (owner_id) WHERE is_active AND is_default_billing"))
    users = _columns("user_profiles")
    if "address_line1" in users:
        for stmt in migrate_sql():
            bind.execute(sa.text(stmt))
    if "country" in users:
        op.alter_column("user_profiles", "country", nullable=True)

    v = _columns("vouchers")
    for name, kind in (("bill_to_company", sa.Boolean()),
                       ("billing_address_id", sa.BigInteger()),
                       ("delivery_address_id", sa.BigInteger()),
                       ("head", JSONB())):
        if name not in v:
            op.add_column("vouchers", sa.Column(name, kind, nullable=True))


def downgrade() -> None:
    v = _columns("vouchers")
    for name in ("head", "delivery_address_id", "billing_address_id", "bill_to_company"):
        if name in v:
            op.drop_column("vouchers", name)
    if "addresses" in _tables():
        op.drop_table("addresses")
    bind = op.get_bind()
    bind.execute(sa.text("DROP INDEX IF EXISTS uq_company_settings_uid_key"))
    bind.execute(sa.text("DROP INDEX IF EXISTS uq_company_settings_name_key"))
    have = _columns("company_settings")
    for name in ("name_key", "uid_key"):
        if name in have:
            op.drop_column("company_settings", name)
