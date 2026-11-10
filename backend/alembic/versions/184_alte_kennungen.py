"""Mails, die noch hinaus sollen, tragen ihre Kennung (``messages.rfc_id``).

Seit 183 bekommt jede Mail ihre ``Message-ID`` beim Anlegen. Was davor schon wartete, hat
keine – wurde es schon einmal versucht, trug es die alte Form ``<inexxio-<Nummer>@<Domain
des Postfachs>>``. Genau die bekommt es jetzt fest, damit der Versand Gmail weiterhin danach
fragen kann (nie doppelt); der Code kennt die alte Form danach nicht mehr.

Revision ID: 184
Revises: 183
"""

from alembic import op

revision = "184"
down_revision = "183"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
UPDATE messages m
   SET rfc_id = '<inexxio-' || m.id || '@' || split_part(b.address, '@', 2) || '>'
  FROM mailboxes b
 WHERE m.outgoing AND m.rfc_id IS NULL AND b.channel = m.channel AND b.is_active""")


def downgrade() -> None:
    pass
