"""Prozess = eigenständiges Objekt + Prozessstückliste (n:m) + Artikel-Art.

Frage 1: Jeder Prozess (auch Artikel-Prozesse) bekommt eine Objektnummer und
einen eigenen Lebenszyklus (draft → released → inactive, Ersetzen via
``replaced_by_id``). Artikel referenzieren Prozesse über die neue Tabelle
``article_process_links`` (Prozessstückliste, n:m) – ein Prozess kann bei
mehreren Artikeln hinterlegt sein.

Frage 2: ``articles.kind`` (material | equipment) bestimmt das Verbrauchs-
verhalten (consume vs. tool) – die Wahl pro BOM-Zeile entfällt.

Backfill (idempotent):
- Objektnummern für alle Prozesse ohne Nummer (global eindeutig, Sequence gehoben).
- Links aus bestehenden Artikel-Prozessen (``article_id``) erzeugen.
- Prozess-Status der Artikel-Prozesse = Status ihres (Herkunfts-)Artikels, damit
  Entwürfe editierbar bleiben und freigegebene gesperrt sind (neues Modell).
- ``articles.kind = equipment`` für Artikel, die bislang ausschliesslich als
  Betriebsmittel (``mode='tool'``) in Ressourcen-Zeilen genutzt wurden.

Revision ID: 027
Revises: 026
Create Date: 2026-06-24
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = '027'
down_revision = '026'
branch_labels = None
depends_on = None


def _has_table(insp, name: str) -> bool:
    return name in insp.get_table_names()


def _has_col(insp, table: str, col: str) -> bool:
    return col in {c['name'] for c in insp.get_columns(table)}


def upgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)

    # 1) Ersetzen-Kette am Prozess
    if not _has_col(insp, 'processes', 'replaced_by_id'):
        op.add_column('processes', sa.Column('replaced_by_id', sa.BigInteger(), nullable=True))
        op.create_index('ix_processes_replaced_by', 'processes', ['replaced_by_id'])

    # 2) Prozessstückliste (Artikel ↔ Prozess, n:m, sortiert)
    if not _has_table(insp, 'article_process_links'):
        op.create_table(
            'article_process_links',
            sa.Column('id', sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column('article_id', sa.BigInteger(), nullable=False),
            sa.Column('process_id', sa.BigInteger(), nullable=False),
            sa.Column('position', sa.Integer(), nullable=False, server_default='1'),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        )
        op.create_index('ix_apl_article_id', 'article_process_links', ['article_id'])
        op.create_index('ix_apl_process_id', 'article_process_links', ['process_id'])

    # 3) Artikel-Art (material | equipment) – Frage 2
    if not _has_col(insp, 'articles', 'kind'):
        op.add_column('articles', sa.Column(
            'kind', sa.String(length=20), nullable=False, server_default='material'))

    # 4) Objektnummern für ALLE Prozesse ohne Nummer (strikt über dem globalen Max).
    op.execute(
        """
        WITH mx AS (
            SELECT GREATEST(
                COALESCE((SELECT MAX(object_id) FROM user_profiles), 0),
                COALESCE((SELECT MAX(object_id) FROM articles), 0),
                COALESCE((SELECT MAX(object_id) FROM orders), 0),
                COALESCE((SELECT MAX(object_id) FROM instances), 0),
                COALESCE((SELECT MAX(object_id) FROM storage_locations), 0),
                COALESCE((SELECT MAX(object_id) FROM claims), 0),
                COALESCE((SELECT MAX(object_id) FROM processes), 0),
                100000000
            ) AS m
        ),
        num AS (
            SELECT id, row_number() OVER (ORDER BY article_id NULLS LAST, position, id) AS rn
            FROM processes WHERE object_id IS NULL
        )
        UPDATE processes p SET object_id = mx.m + num.rn
        FROM num, mx WHERE p.id = num.id
        """
    )

    # 5) Sequence auf den neuen Höchststand heben (nie zurückdrehen).
    op.execute(
        """
        DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM pg_class WHERE relkind='S' AND relname='object_id_seq') THEN
                PERFORM setval('object_id_seq', GREATEST(
                    (SELECT last_value FROM object_id_seq),
                    COALESCE((SELECT MAX(object_id) FROM processes), 100000001)
                ), true);
            END IF;
        END $$;
        """
    )

    # 6) Registry (falls vorhanden) – sonst füllt der Startup-Backfill nach.
    op.execute(
        """
        DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name='objects') THEN
                INSERT INTO objects (object_id, object_type, created_at)
                SELECT object_id, 'process', now() FROM processes WHERE object_id IS NOT NULL
                ON CONFLICT (object_id) DO NOTHING;
            END IF;
        END $$;
        """
    )

    # 7) Links aus bestehenden Artikel-Prozessen erzeugen (idempotent).
    op.execute(
        """
        INSERT INTO article_process_links (article_id, process_id, position, is_active, created_at, updated_at)
        SELECT p.article_id, p.id, p.position, true, now(), now()
        FROM processes p
        WHERE p.is_standard = false AND p.article_id IS NOT NULL AND p.is_active = true
          AND NOT EXISTS (
              SELECT 1 FROM article_process_links l
              WHERE l.article_id = p.article_id AND l.process_id = p.id
          )
        """
    )

    # 8) Prozess-Status der Artikel-Prozesse = Status des Herkunfts-Artikels.
    #    (Entwurf → editierbar, freigegeben → gesperrt; neues Pro-Prozess-Modell.)
    op.execute(
        """
        UPDATE processes p SET status = a.status
        FROM articles a
        WHERE p.article_id = a.id AND p.is_standard = false AND p.is_active = true
        """
    )

    # 9) Artikel-Art: equipment für bisher reine Betriebsmittel (tool, nie consume).
    op.execute(
        """
        WITH usage AS (
            SELECT (line->>'article_id')::bigint AS aid,
                   bool_or(COALESCE(line->>'mode','consume') = 'tool') AS any_tool,
                   bool_or(COALESCE(line->>'mode','consume') = 'consume') AS any_consume
            FROM article_process_steps s,
                 LATERAL jsonb_array_elements(COALESCE(s.resource_lines, '[]'::jsonb)) AS line
            WHERE s.is_active = true AND s.step_type = 'resource'
            GROUP BY (line->>'article_id')::bigint
        )
        UPDATE articles a SET kind = 'equipment'
        FROM usage u
        WHERE a.id = u.aid AND u.any_tool = true AND u.any_consume = false
        """
    )


def downgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    if _has_table(insp, 'article_process_links'):
        op.drop_table('article_process_links')
    if _has_col(insp, 'articles', 'kind'):
        op.drop_column('articles', 'kind')
    if _has_col(insp, 'processes', 'replaced_by_id'):
        try:
            op.drop_index('ix_processes_replaced_by', table_name='processes')
        except Exception:
            pass
        op.drop_column('processes', 'replaced_by_id')
