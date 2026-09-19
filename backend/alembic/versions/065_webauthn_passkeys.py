"""Passkeys (WebAuthn/FIDO2): webauthn_credentials + webauthn_challenges.

* ``webauthn_credentials`` – registrierte Passkeys je Benutzer (Credential-ID,
  öffentlicher Schlüssel, Signaturzähler, RP-ID/Domain, Geräte-Anzeigename).
* ``webauthn_challenges`` – kurzlebige, einmalig verwendbare Challenges einer
  laufenden Register-/Login-Zeremonie (Replay-Schutz, DB-basiert für Cloud Run).

Revision ID: 065
Revises: 064
Create Date: 2026-07-08
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects.postgresql import JSONB

revision = '065'
down_revision = '064'
branch_labels = None
depends_on = None


def upgrade() -> None:
    insp = inspect(op.get_bind())
    tables = set(insp.get_table_names())

    if "webauthn_credentials" not in tables:
        op.create_table(
            "webauthn_credentials",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("user_id", sa.BigInteger(), nullable=False),
            sa.Column("credential_id", sa.String(length=512), nullable=False),
            sa.Column("public_key", sa.LargeBinary(), nullable=False),
            sa.Column("sign_count", sa.BigInteger(), nullable=False, server_default=sa.text("0")),
            sa.Column("rp_id", sa.String(length=255), nullable=False),
            sa.Column("transports", JSONB(), nullable=True),
            sa.Column("device_name", sa.String(length=80), nullable=True),
            sa.Column("device_type", sa.String(length=20), nullable=True),
            sa.Column("backed_up", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                      server_default=sa.text("now()")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                      server_default=sa.text("now()")),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        )
        op.create_index("ix_webauthn_credentials_user_id", "webauthn_credentials", ["user_id"])
        op.create_unique_constraint(
            "uq_webauthn_credentials_credential_id", "webauthn_credentials", ["credential_id"]
        )
        op.create_index(
            "ix_webauthn_credentials_credential_id", "webauthn_credentials", ["credential_id"]
        )

    if "webauthn_challenges" not in tables:
        op.create_table(
            "webauthn_challenges",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("challenge", sa.String(length=255), nullable=False),
            sa.Column("purpose", sa.String(length=16), nullable=False),
            sa.Column("user_id", sa.BigInteger(), nullable=True),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                      server_default=sa.text("now()")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                      server_default=sa.text("now()")),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        )
        op.create_unique_constraint(
            "uq_webauthn_challenges_challenge", "webauthn_challenges", ["challenge"]
        )
        op.create_index("ix_webauthn_challenges_challenge", "webauthn_challenges", ["challenge"])


def downgrade() -> None:
    insp = inspect(op.get_bind())
    tables = set(insp.get_table_names())
    if "webauthn_challenges" in tables:
        op.drop_table("webauthn_challenges")
    if "webauthn_credentials" in tables:
        op.drop_table("webauthn_credentials")
