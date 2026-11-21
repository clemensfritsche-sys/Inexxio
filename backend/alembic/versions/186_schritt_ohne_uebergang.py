"""Ein Prozessschritt speichert keinen Übergang mehr.

Jedes Modul lässt weiterlaufende Stücke «Im Prozess»; was beim Hinausgehen geschieht, sagt
der Modultyp (``Module.exit_status_for``). ``status_before``/``status_after`` an
``process_steps`` und ``article_process_steps`` waren eine gespeicherte Kopie einer
Konstanten – sie gehen in einem Zug mit dem Code (Entscheid des Inhabers: nicht
rückwärtskompatibel). Die Ereignisse im Log behalten ihr Vorher/Nachher: das sind Tatsachen.

Revision ID: 186
Revises: 185
"""

from alembic import op

revision = "186"
down_revision = "185"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for table in ("process_steps", "article_process_steps"):
        op.execute(f"ALTER TABLE {table} DROP COLUMN status_before, DROP COLUMN status_after")


def downgrade() -> None:
    for table in ("process_steps", "article_process_steps"):
        op.execute(f"ALTER TABLE {table} ADD COLUMN status_before varchar(30) NOT NULL "
                   f"DEFAULT 'im_prozess', ADD COLUMN status_after varchar(30) NOT NULL "
                   f"DEFAULT 'im_prozess'")
