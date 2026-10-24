"""Die Firma ist ein Datensatz – für jede Firma, nicht nur für unsere (CRM Schritt 1).

* ``company_settings.is_own`` – «eine unserer Gesellschaften». Jede bestehende Zeile ist
  eine, darum kommt die Spalte mit ``DEFAULT true`` und bekommt danach ``false`` als
  Vorgabe: jede neue Firma ist zuerst fremd.
* Die Firmentexte an der Person (Name, Rechtsform, UID, MWST, Handelsregister, Website)
  werden zu Firmen-Datensätzen (``move_company_texts`` – nur bei eindeutiger Gleichheit
  zusammengelegt) und fallen danach.
* E-Mail klein und Objektnummer für jede Person (``people.repair_sql``).

Die Übernahme der Firmentexte stand bis zum Cleanup Oktober 2026 zusätzlich im
Lifespan-Netz; sie ist selbstbegrenzend und dort auf jeder Datenbank längst gelaufen
(B-23). Seither steht sie nur noch hier – als eingefrorene Fassung, wie eine Migration
sein soll.
"""
import sqlalchemy as sa
from alembic import op

from app.services import sites
from app.services.people import repair_sql

revision = "142"
down_revision = "141"
branch_labels = None
depends_on = None


#: ►►► **Die Firmenangaben, die von der Person zur Firma gewandert sind** (CRM Schritt 1).
MOVED_COLUMNS = ("company_name", "legal_form", "uid_number", "vat_number", "vat_registered",
                 "trade_register_nr", "trade_register_canton", "company_website")


def move_company_texts(conn) -> int:
    """►►► **Aus dem Firmentext an der Person wird ein Firmen-DATENSATZ.** ◄◄◄

    Je Person mit Firmenname und ohne Zuordnung: gleiche UID → dieselbe Firma; sonst exakt
    gleicher Name **und** Rechtsform → dieselbe Firma (``sites.match`` – dieselbe Regel wie
    bei der Eingabe); sonst eine **neue, fremde** Firma. Unscharfes wird nicht
    zusammengeführt. Läuft auf einer rohen Verbindung und ist **selbstbegrenzend**:
    danach fallen die Spalten, und ohne sie gibt es nichts zu tun.
    Gibt die Zahl der verknüpften Personen zurück."""
    cols = {r[0] for r in conn.execute(sa.text(
        "SELECT column_name FROM information_schema.columns WHERE table_name='user_profiles'"))}
    if "company_name" not in cols:
        return 0
    pick = ", ".join(c if c in cols else f"NULL AS {c}"
                     for c in ("company_name", "legal_form", "uid_number", "vat_number"))
    rows = conn.execute(sa.text(
        f"SELECT id, {pick} FROM user_profiles "
        "WHERE coalesce(trim(company_name), '') <> '' AND company_object_id IS NULL")).all()
    registry = conn.execute(sa.text("SELECT to_regclass('public.objects')")).scalar()
    known = [list(r) for r in conn.execute(sa.text(
        "SELECT object_id, company_name, legal_form, uid_number, vat_number "
        "FROM company_settings WHERE is_active AND object_id IS NOT NULL")).all()]
    for pid, name, form, uid_nr, vat in rows:
        key = sites.uid_key_of(uid_nr) or sites.uid_key_of(vat)
        hit = next((k for k in known if key and key in
                    (sites.uid_key_of(k[3]), sites.uid_key_of(k[4]))), None)
        nkey = sites.name_key_of(name, form)
        hit = hit or next((k for k in known if nkey
                           and sites.name_key_of(k[1], k[2]) == nkey), None)
        if hit is None:
            oid = conn.execute(sa.text("SELECT nextval('object_id_seq')")).scalar()
            conn.execute(sa.text(
                "INSERT INTO company_settings (object_id, is_operator, is_active, is_own, "
                "currency, company_name, legal_form, country, uid_number, vat_number, email) "
                "VALUES (:o, false, true, false, 'CHF', :n, :f, '', :u, :v, '')"),
                {"o": oid, "n": name.strip(), "f": (form or "").strip(),
                 "u": uid_nr, "v": vat})
            if registry:    # sonst zieht ``_backfill_object_registry`` sie nach
                conn.execute(sa.text(
                    "INSERT INTO objects (object_id, object_type, created_at) "
                    "VALUES (:o, 'organization', now()) ON CONFLICT DO NOTHING"), {"o": oid})
            hit = [oid, name, form, uid_nr, vat]
            known.append(hit)
        conn.execute(sa.text("UPDATE user_profiles SET company_object_id = :o WHERE id = :i"),
                     {"o": hit[0], "i": pid})
    return len(rows)


def _columns(table: str) -> set[str]:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    if "is_own" not in _columns("company_settings"):
        op.add_column("company_settings", sa.Column(
            "is_own", sa.Boolean(), nullable=False, server_default=sa.text("true")))
    op.alter_column("company_settings", "is_own", server_default=sa.text("false"))
    bind = op.get_bind()
    move_company_texts(bind)
    have = _columns("user_profiles")
    for col in MOVED_COLUMNS:
        if col in have:
            op.drop_column("user_profiles", col)
    for stmt in repair_sql():
        bind.execute(sa.text(stmt))


def downgrade() -> None:
    have = _columns("user_profiles")
    for col in ("company_name", "company_website", "trade_register_nr",
                "trade_register_canton"):
        if col not in have:
            op.add_column("user_profiles", sa.Column(col, sa.String(255)))
    for col in ("legal_form", "uid_number", "vat_number"):
        if col not in have:
            op.add_column("user_profiles", sa.Column(col, sa.String(50)))
    if "vat_registered" not in have:
        op.add_column("user_profiles", sa.Column(
            "vat_registered", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    if "is_own" in _columns("company_settings"):
        op.drop_column("company_settings", "is_own")
