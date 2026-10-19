"""Firma = Identität, Adressen = Adressbuch der Person, der Beleg friert mit der Zusage ein.

* ``company_settings.uid_key`` / ``name_key`` – woran eine Firma erkannt wird (gleiche UID,
  ohne UID gleicher Name und gleiche Rechtsform), mit **partiellen Unique-Indizes**: eine
  Dublette ist nicht verboten, sondern unmöglich (``sites.backfill_keys``, ``KEY_INDEXES``).
* ``addresses`` – die Anschriften einer Person in **zwei Konten** (privat · Geschäftskonto),
  je Konto eine Standard-Liefer- und Standard-Rechnungsadresse, optional weitere
  Lieferadressen; die Rechnungs-E-Mail nur im Geschäftskonto. Die Anschrift einer fremden
  Firma wird die des Geschäftskontos ihrer Personen (``address_book.business_sql``).
  Die Felder ``address_*``/``invoice_*`` am
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

from app.services.sites import KEY_INDEXES, backfill_keys

revision = "143"
down_revision = "142"
branch_labels = None
depends_on = None

# ►► **Die Übernahme der Anschriften stand bis Migration 152 in ``services/address_book``**
#    und lief auch im Lifespan-Netz. Mit dem Drop der alten Felder (152) ist das Netz
#    entfallen; die Anweisungen stehen seither hier, damit ``alembic upgrade head`` von
#    null weiter läuft.

#: Je Konto genau ein Standard – die frühere Fassung ohne Konto fällt weg.
ADDRESS_INDEXES = (
    "DROP INDEX IF EXISTS uq_addresses_default_delivery",
    "DROP INDEX IF EXISTS uq_addresses_default_billing",
    "CREATE UNIQUE INDEX IF NOT EXISTS uq_addresses_default_delivery_account "
    "ON addresses (owner_id, account) WHERE is_active AND is_default_delivery",
    "CREATE UNIQUE INDEX IF NOT EXISTS uq_addresses_default_billing_account "
    "ON addresses (owner_id, account) WHERE is_active AND is_default_billing",
)

#: Die Felder am Benutzer, die das Adressbuch ablöst – sie verlieren ihr Mapping und
#: fallen im Folge-Deploy.
OLD_COLUMNS = ("address_line1", "address_line2", "city", "postal_code", "state_region",
               "country", "invoice_first_name", "invoice_last_name",
               "invoice_address_line1", "invoice_address_line2", "invoice_city",
               "invoice_postal_code", "invoice_country", "invoice_email")


def migrate_sql() -> tuple[str, ...]:
    """►►► **Die beiden Anschriften am Benutzer werden Einträge im Adressbuch.** ◄◄◄

    * die **Hauptadresse** → Standard-Lieferadresse des **Privatkontos**;
      Standard-Rechnungsadresse auch, wenn keine eigene Rechnungsadresse dasteht;
    * eine **eigene Rechnungsadresse** → zweiter Eintrag, Standard-Rechnungsadresse –
      **ausser sie ist eine Kopie der Hauptadresse** (das schrieb der frühere Schalter).

    Die frühere Rechnungs-E-Mail geht **nicht** mit: privat geht die Rechnung an die
    E-Mail der Person.

    Danach werden die Felder **geleert** – das macht den Lauf **selbstbegrenzend**:
    der zweite findet nichts mehr, auch wenn jemand später alle Anschriften entfernt.
    Der Name einer abweichenden Rechnungsadresse geht nicht mit: Empfänger ist die Person
    (bzw. ihre Firma), nicht ein dritter Name an einer Anschrift.

    Dieselbe Liste lesen Migration und Lifespan-Netz (für eine Datenbank, auf der
    ``alembic upgrade head`` beim Start scheitert, #778)."""
    iso = ("CASE WHEN length(trim(coalesce({c}, ''))) = 2 THEN upper(trim({c})) "
           "ELSE 'CH' END")
    has_main = ("(coalesce(trim(address_line1), '') <> '' "
                "OR coalesce(trim(city), '') <> '')")
    copy = ("(coalesce(invoice_address_line1, '') = coalesce(address_line1, '') "
            "AND coalesce(invoice_postal_code, '') = coalesce(postal_code, '') "
            "AND coalesce(invoice_city, '') = coalesce(city, ''))")
    own_bill = f"(coalesce(trim(invoice_address_line1), '') <> '' AND NOT {copy})"
    cols = ("owner_id, account, street1, street2, zip, city, region, country, email, "
            "is_default_delivery, is_default_billing, is_active, created_at, updated_at")
    return (
        f"INSERT INTO addresses ({cols}) "
        f"SELECT id, 'private', coalesce(address_line1, ''), nullif(address_line2, ''), "
        f"coalesce(postal_code, ''), coalesce(city, ''), nullif(state_region, ''), "
        f"{iso.format(c='country')}, NULL, "
        f"true, NOT {own_bill}, true, now(), now() "
        f"FROM user_profiles WHERE {has_main}",
        f"INSERT INTO addresses ({cols}) "
        f"SELECT id, 'private', coalesce(invoice_address_line1, ''), "
        f"nullif(invoice_address_line2, ''), "
        f"coalesce(invoice_postal_code, ''), coalesce(invoice_city, ''), NULL, "
        f"{iso.format(c='invoice_country')}, NULL, "
        f"NOT {has_main}, true, true, now(), now() "
        f"FROM user_profiles WHERE {own_bill}",
        "UPDATE user_profiles SET " + ", ".join(
            f"{c} = NULL" for c in OLD_COLUMNS if c != "country")
        + f" WHERE {has_main} OR coalesce(trim(invoice_address_line1), '') <> '' "
        f"OR coalesce(invoice_email, '') <> ''",
    )


def business_sql() -> tuple[str, ...]:
    """►►► **Die Anschrift einer fremden Firma wird die des Geschäftskontos.** ◄◄◄

    Vor ``143`` stand die Anschrift an der **Firma** – seither gehört sie der Person, die
    für die Firma bestellt (die Firma trägt nur ihre Identität). Wer einer fremden Firma
    zugeordnet ist und noch **kein** Geschäftskonto-Eintrag hat, bekommt ihre Anschrift
    als Haupt- und Rechnungsadresse. Selbstbegrenzend: wer einen hat, wird übersprungen.
    Die E-Mail der Firma geht nicht mit – leer heisst «die E-Mail der Person»."""
    country = ("CASE WHEN length(trim(coalesce(c.country, ''))) = 2 "
               "THEN upper(trim(c.country)) "
               "WHEN lower(trim(c.country)) = 'deutschland' THEN 'DE' "
               "WHEN lower(trim(c.country)) = 'österreich' THEN 'AT' "
               "WHEN lower(trim(c.country)) = 'frankreich' THEN 'FR' "
               "WHEN lower(trim(c.country)) = 'italien' THEN 'IT' "
               "WHEN lower(trim(c.country)) = 'liechtenstein' THEN 'LI' ELSE 'CH' END")
    return (
        "INSERT INTO addresses (owner_id, account, street1, zip, city, country, "
        "is_default_delivery, is_default_billing, is_active, created_at, updated_at) "
        "SELECT u.id, 'business', trim(concat_ws(' ', c.street, c.street_nr)), "
        "coalesce(c.zip_code, ''), coalesce(c.city, ''), " + country + ", "
        "true, true, true, now(), now() "
        "FROM user_profiles u JOIN company_settings c ON c.object_id = u.company_object_id "
        "WHERE c.is_own IS NOT TRUE AND coalesce(trim(c.city), '') <> '' "
        "AND coalesce(trim(c.street), '') <> '' "
        "AND NOT EXISTS (SELECT 1 FROM addresses a WHERE a.owner_id = u.id "
        "AND a.account = 'business')",
    )


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
            sa.Column("account", sa.String(10), nullable=False, server_default="private"),
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
    for stmt in ADDRESS_INDEXES:
        bind.execute(sa.text(stmt))
    users = _columns("user_profiles")
    if "address_line1" in users:
        for stmt in migrate_sql():
            bind.execute(sa.text(stmt))
    if "company_object_id" in users:
        for stmt in business_sql():
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
