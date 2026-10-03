"""**Das Schema kommt aus den Migrationen — und zwar vollständig.**

Es gibt drei Netze, und sie fangen **verschiedene** Dinge:

* die **Migration** ist die Wahrheit (Leitbild: Alembic ist Schema-SSOT),
* ``create_all`` im Lifespan legt eine fehlende **Tabelle** an — aber nie eine fehlende
  **Spalte** einer vorhandenen,
* ``main._COLUMN_SAFETY_NET`` zieht fehlende **Spalten** nach.

Dazwischen liegt genau eine Lücke: eine Tabelle, die es gibt, der aber eine Spalte des
Modells fehlt. Lokal fällt das **nicht** auf, weil ``create_all`` die Tabelle dort
irgendwann einmal vollständig angelegt hat; gegen eine Datenbank, die nur aus den
Migrationen kommt, endet danach jeder Lesezugriff in einem 500.

Genau so ist ``purchases.is_active`` entstanden (Migration 114, beim Bauen gefunden): das
Modell erbt die Spalte von ``Base``, die Migration nannte sie nicht — 140 Prüfungen fielen
gegen ein frisches Schema aus, während lokal alles grün war. Dieselbe Ausfallklasse wie
Migration 090, nur eine Ebene tiefer.

Der Wächter **baut** das Schema darum wirklich (eine Wegwerf-Datenbank, ``alembic upgrade
head``) statt es zu glauben. Ohne PostgreSQL überspringt er sich **mit Grund**.
"""

import os
import pathlib
import subprocess
import sys

import pytest

BACKEND = pathlib.Path(__file__).resolve().parents[1]
SCRATCH = "schema_check_tmp"


def _admin_engine():
    """Eine Verbindung zur ``postgres``-Datenbank – zum Anlegen der Wegwerf-Datenbank."""
    from sqlalchemy import create_engine
    from app.core.config import get_settings

    url = os.environ.get("DATABASE_URL") or get_settings().database_url
    if not url.startswith("postgresql"):
        pytest.skip(f"Kein PostgreSQL ({url.split('://')[0]}) – die Migrationen bauen "
                    f"PostgreSQL-Schema, gegen SQLite wäre die Aussage eine andere.")
    base, _, _ = url.rpartition("/")
    return create_engine(f"{base}/postgres", isolation_level="AUTOCOMMIT"), f"{base}/{SCRATCH}"


def test_every_model_column_exists_in_a_schema_built_only_from_the_migrations():
    sys.path.insert(0, str(BACKEND))
    os.environ.setdefault("FIREBASE_PROJECT_ID", "test")
    from sqlalchemy import create_engine, inspect, text
    from sqlalchemy.exc import OperationalError

    # **Nur die Datenbank-Frage darf überspringen.** Ein ImportError ist ein Fehler im
    # Wächter, kein fehlendes PostgreSQL – ihn zum Skip zu machen hiesse, sich selbst
    # stillzulegen (und ein Wächter, der nie anschlägt, ist von einem kaputten nicht zu
    # unterscheiden).
    admin, scratch_url = _admin_engine()
    try:
        with admin.connect() as con:
            con.execute(text(f'DROP DATABASE IF EXISTS "{SCRATCH}"'))
            con.execute(text(f'CREATE DATABASE "{SCRATCH}"'))
    except OperationalError as exc:  # pragma: no cover – reine Umgebungsfrage
        pytest.skip(f"PostgreSQL nicht erreichbar ({exc.__class__.__name__}).")

    try:
        run = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            cwd=BACKEND, capture_output=True, text=True,
            env={**os.environ, "DATABASE_URL": scratch_url},
        )
        assert run.returncode == 0, (
            "Die Migrationen bauen das Schema nicht von null auf – und genau das ist "
            f"die Behauptung «Alembic ist die Schema-Wahrheit»:\n{run.stderr[-2000:]}"
        )

        from app.core.database import Base
        import app.models  # noqa: F401 – füllt die Metadaten
        from app.main import _COLUMN_SAFETY_NET

        netted = {(t, c) for t, c, *_ in _COLUMN_SAFETY_NET}
        engine = create_engine(scratch_url)
        insp = inspect(engine)
        built = set(insp.get_table_names())

        gaps: list[str] = []
        for name, table in sorted(Base.metadata.tables.items()):
            # Eine fehlende **Tabelle** legt ``create_all`` im Lifespan an – das ist der
            # dafür vorgesehene zweite Weg, kein Befund.
            if name not in built:
                continue
            have = {c["name"] for c in insp.get_columns(name)}
            for col in sorted({c.name for c in table.columns} - have):
                if (name, col) not in netted:
                    gaps.append(f"{name}.{col}")
        engine.dispose()

        assert not gaps, (
            "Diese Spalten kennt das Modell, aber weder eine Migration noch das "
            f"Lifespan-Netz legt sie an: {', '.join(gaps)}.\n"
            "Lokal fällt das nicht auf (dort hat ``create_all`` die Tabelle einmal "
            "vollständig angelegt) – gegen ein frisches Schema endet danach JEDE "
            "Abfrage auf diese Tabelle in einem 500. Entweder in die Migration "
            "aufnehmen oder in ``main._COLUMN_SAFETY_NET``."
        )
    finally:
        with admin.connect() as con:
            con.execute(text(f'DROP DATABASE IF EXISTS "{SCRATCH}"'))
        admin.dispose()
