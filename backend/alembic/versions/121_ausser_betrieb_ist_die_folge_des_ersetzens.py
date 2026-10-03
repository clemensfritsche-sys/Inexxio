"""«Ausser Betrieb» ist keine eigene Angabe — es ist die Folge des Ersetzens

Testnotiz #773: «soll man das inaktiv setzen gänzlich eleminieren und die inaktivität
indirekt über den ersetzungsartikel steuern?»

Ein Artikel wird nicht versioniert, er wird **ersetzt** – und wer abgelöst ist, erzeugt
nichts Neues mehr. Das ist keine zweite Wirkung des Ersetzens, sondern seine Bedeutung.
``articles.status`` war die zweite Aussage darüber: gesetzt von zwei Stellen (dem Ersetzen
und einem Knopf «Inaktiv setzen»), gelesen von ``may_create``. Der Zustand ist jetzt eine
**Projektion** von ``replaced_by_id`` (``Article.status``), die Spalte verliert ihr
Mapping.

**Zwei Schritte, wie immer bei einer Spalte, die ihr Mapping verliert.** Hier fällt nur
die ``NOT NULL``-Sperre; gedroppt wird im Folge-Deploy, wenn keine Vorgänger-Revision sie
mehr schreibt. (Sie trägt zwar einen Server-Default, ein Insert liefe also auch so – aber
die Regel gilt unabhängig vom Glück im Einzelfall.)

**Nebenbei geschlossen: ``articles.replaced_by_id`` gab es in keiner Migration.** Sie kam
bisher ausschliesslich über das Lifespan-Netz (``main._COLUMN_SAFETY_NET``) – gegen ein
Schema, das nur aus den Migrationen gebaut ist, existierte sie also gar nicht. Das fiel
nie auf, solange niemand sie in SQL las; genau das tut diese Migration. Die Migration ist
die Wahrheit, das Netz der zweite Weg – also legt sie die Spalte an, wenn sie fehlt.

**Und die Altdaten werden geheilt.** Wer von Hand «inaktiv» gesetzt wurde, ohne dass ihn
jemand abgelöst hat, wäre sonst für immer stillgelegt: den Weg zurück gab es nur über
denselben Knopf, und den gibt es nicht mehr. Genau dieselbe Falle wie beim deaktivierten
Benutzer (Migration ``118``) – und dort wie hier ist sie beim Wegnehmen des Schalters zu
schliessen, nicht danach.

Revision ID: 121
Revises: 120
"""
from alembic import op

revision = "121"
down_revision = "120"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE articles ADD COLUMN IF NOT EXISTS replaced_by_id BIGINT"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_articles_replaced_by_id "
        "ON articles (replaced_by_id)"
    )
    # Idempotent und tolerant: läuft das Netz (``main._ensure_columns``) vorher, ist die
    # Sperre schon weg – und eine Datenbank, in der die Spalte gar nicht mehr existiert,
    # ist ebenfalls in Ordnung (der Folge-Deploy dropt sie).
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'articles' AND column_name = 'status'
            ) THEN
                ALTER TABLE articles ALTER COLUMN status DROP NOT NULL;
                UPDATE articles SET status = 'freigegeben'
                 WHERE status <> 'freigegeben' AND replaced_by_id IS NULL;
            END IF;
        END $$;
        """
    )


def downgrade() -> None:
    # **Nicht umkehrbar, und das ist ehrlich:** welcher Artikel einmal von Hand inaktiv
    # gesetzt war, steht im Audit-Log, nicht in dieser Spalte. Ihn hier zu raten wäre
    # schlimmer als nichts zu tun. Die Sperre kommt zurück – sie ist mit dem
    # Server-Default gefahrlos.
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'articles' AND column_name = 'status'
            ) THEN
                UPDATE articles SET status = 'freigegeben' WHERE status IS NULL;
                ALTER TABLE articles ALTER COLUMN status SET NOT NULL;
            END IF;
        END $$;
        """
    )
