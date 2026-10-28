"""**Die alte ``documents``-Tabelle weicht der neuen** (Migration ``157``).

Auf dev stand die Tabelle des früheren Dokumentmoduls (ohne ``object_id``, von einem alten
``create_all`` wieder angelegt); ``157`` brach an ihr ab (Index auf ``object_id``), die Kette
blieb bei ``156`` stehen, und das Start-Netz legte die neuen Nebentabellen auf die alte
Tabelle zeigend an. Genau so nachgestellt, dann ``upgrade head`` – danach muss die neue Form
stehen, samt den Verweisen darauf.
"""

import os
import subprocess
import sys

from sqlalchemy import create_engine, inspect, text

from tests.test_schema_is_built_by_the_migrations import BACKEND, _admin_engine


def _alembic(url: str, *args: str) -> None:
    run = subprocess.run([sys.executable, "-m", "alembic", *args], cwd=BACKEND,
                         capture_output=True, text=True, env={**os.environ, "DATABASE_URL": url})
    assert run.returncode == 0, run.stderr[-2000:]


def test_the_old_documents_table_gives_way_to_the_new_one():
    admin, url, name = _admin_engine()
    url, name = url + "_old", name + "_old"
    with admin.connect() as con:
        con.execute(text(f'DROP DATABASE IF EXISTS "{name}"'))
        con.execute(text(f'CREATE DATABASE "{name}"'))
    engine = None
    try:
        _alembic(url, "upgrade", "156")
        engine = create_engine(url)
        with engine.begin() as con:
            con.execute(text("CREATE TABLE documents (id BIGSERIAL PRIMARY KEY, order_id BIGINT NOT NULL, "
                             "content JSONB, created_at TIMESTAMPTZ, updated_at TIMESTAMPTZ, "
                             "is_active BOOLEAN)"))
            con.execute(text("INSERT INTO documents (order_id) VALUES (1)"))
            # was das Start-Netz (create_all, Spalten-Netz) daneben schon angelegt hatte
            con.execute(text("CREATE TABLE document_refs (id BIGSERIAL PRIMARY KEY, "
                             "document_id BIGINT NOT NULL REFERENCES documents (id), object_id BIGINT)"))
            con.execute(text("ALTER TABLE voucher_documents ADD COLUMN document_id BIGINT "
                             "REFERENCES documents (id)"))
            con.execute(text("UPDATE voucher_documents SET document_id = 1"))
        _alembic(url, "upgrade", "head")
        insp = inspect(engine)
        cols = {c["name"] for c in insp.get_columns("documents")}
        assert {"object_id", "art", "sha256"} <= cols and "order_id" not in cols
        for t in ("document_refs", "document_signatures", "document_links"):
            assert t in insp.get_table_names()
        fks = [fk["referred_table"] for fk in insp.get_foreign_keys("voucher_documents")]
        assert "documents" in fks, "voucher_documents.document_id zeigt wieder auf documents"
        assert {c["name"] for c in insp.get_columns("document_refs")} >= {"part", "field"}
    finally:
        if engine is not None:
            engine.dispose()
        with admin.connect() as con:
            con.execute(text(f'DROP DATABASE IF EXISTS "{name}"'))
        admin.dispose()
