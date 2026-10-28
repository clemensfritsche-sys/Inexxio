"""**Das Schema kommt aus den Migrationen — und zwar vollständig.**

Es gibt genau einen Weg: ``start.sh`` fährt ``alembic upgrade head``, und scheitert das,
startet der Dienst nicht. Kein ``create_all``, kein Spalten-Netz legt nachträglich an, was
eine Migration vergessen hat (die Netze gab es bis Oktober 2026; sie fingen genau diese
Lücke und versteckten sie damit).

Darum **baut** der Wächter das Schema wirklich (eine Wegwerf-Datenbank, ``alembic upgrade
head``) und vergleicht es in beide Richtungen mit den Modellen: jede Tabelle, Spalte,
jeder Index und Fremdschlüssel des Modells steht da – und nichts, was kein Modell kennt.
Ohne PostgreSQL überspringt er sich **mit Grund**.
"""

import os
import pathlib
import subprocess
import sys

import pytest

from tests.runner import no_database

BACKEND = pathlib.Path(__file__).resolve().parents[1]


def _admin_engine():
    """Eine Verbindung zur ``postgres``-Datenbank – zum Anlegen der Wegwerf-Datenbank.

    Die Wegwerf-Datenbank heisst nach der Test-Datenbank (``<name>_schema_check``): zwei
    Läufe gegen denselben Server (zwei Arbeitskopien, zwei Test-Datenbanken) räumten sich
    mit einem festen Namen gegenseitig die Datenbank unter den Füssen weg.
    """
    from sqlalchemy import create_engine
    from app.core.config import get_settings

    url = os.environ.get("DATABASE_URL") or get_settings().database_url
    if not url.startswith("postgresql"):
        no_database(f"{url.split('://')[0]} statt PostgreSQL – die Migrationen bauen "
                    f"PostgreSQL-Schema, gegen SQLite wäre die Aussage eine andere")
    base, _, name = url.rpartition("/")
    scratch = f"{name.split('?')[0]}_schema_check"
    return (create_engine(f"{base}/postgres", isolation_level="AUTOCOMMIT"),
            f"{base}/{scratch}", scratch)


@pytest.fixture(scope="module")
def built():
    """Ein Schema, das **nur** aus den Migrationen kommt – einmal gebaut, von beiden
    Wächtern gelesen (die Inspektion selbst ist billig, ``upgrade head`` nicht)."""
    sys.path.insert(0, str(BACKEND))
    os.environ.setdefault("FIREBASE_PROJECT_ID", "test")
    from sqlalchemy import create_engine, inspect, text
    from sqlalchemy.exc import OperationalError

    # **Nur die Datenbank-Frage darf überspringen.** Ein ImportError ist ein Fehler im
    # Wächter, kein fehlendes PostgreSQL – ihn zum Skip zu machen hiesse, sich selbst
    # stillzulegen (und ein Wächter, der nie anschlägt, ist von einem kaputten nicht zu
    # unterscheiden).
    admin, scratch_url, scratch = _admin_engine()
    try:
        with admin.connect() as con:
            con.execute(text(f'DROP DATABASE IF EXISTS "{scratch}"'))
            con.execute(text(f'CREATE DATABASE "{scratch}"'))
    except OperationalError as exc:  # pragma: no cover – reine Umgebungsfrage
        no_database(exc.__class__.__name__)

    engine = None
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
        engine = create_engine(scratch_url)
        yield inspect(engine)
    finally:
        if engine is not None:
            engine.dispose()
        with admin.connect() as con:
            con.execute(text(f'DROP DATABASE IF EXISTS "{scratch}"'))
        admin.dispose()


def gaps(insp) -> list[str]:
    """Was ein Modell kennt, die Migrationen aber nicht anlegen – als Funktion, damit der
    Gegentest sie gegen die Bug-Form fahren kann."""
    from app.core.database import Base
    import app.models  # noqa: F401 – füllt die Metadaten

    tables = set(insp.get_table_names())
    found: list[str] = []
    for name, table in sorted(Base.metadata.tables.items()):
        if name not in tables:
            found.append(f"Tabelle {name}")
            continue
        have = {c["name"] for c in insp.get_columns(name)}
        found += [f"{name}.{c}" for c in sorted({c.name for c in table.columns} - have)]
        # Ein Index zählt nach seinen **Spalten**, nicht nach seinem Namen – die
        # Migrationen nannten manche anders als ``index=True`` am Modell.
        indexes = {tuple(i["column_names"]) for i in insp.get_indexes(name)} | {
            tuple(u["column_names"]) for u in insp.get_unique_constraints(name)} | {
            tuple(insp.get_pk_constraint(name)["constrained_columns"])}
        found += [f"Index {i.name}" for i in table.indexes
                  if tuple(c.name for c in i.columns) not in indexes]
        fks = {(tuple(f["constrained_columns"]), f["referred_table"])
               for f in insp.get_foreign_keys(name)}
        found += [f"Fremdschlüssel {name}.{fk.parent.name} → {fk.column.table.name}"
                  for fk in table.foreign_keys
                  if ((fk.parent.name,), fk.column.table.name) not in fks]
    return found


def test_everything_a_model_knows_is_built_by_the_migrations(built):
    """Bug-Form (gegengeprüft): eine neue Spalte am Modell ohne Migration, eine Tabelle
    ohne Migration – beides wird gemeldet."""
    found = gaps(built)
    assert not found, (
        "Das kennt ein Modell, aber keine Migration legt es an: "
        f"{', '.join(found)}.\nOhne Migration fehlt es auf jeder Umgebung – und jede "
        "Abfrage darauf endet in einem 500. Eine Migration schreiben."
    )


#: Was ohne Modell stehen darf: die Versionstabelle von Alembic. (``objects``, die
#: Nummern-Registry, IST ein Modell – ``ObjectRef``.)
_TABLES_WITHOUT_MODEL = {"alembic_version"}

#: ►► **Zwischen den beiden Schritten der Zwei-Deploy-Regel** steht eine Spalte ohne Mapping
#:    für **einen** Deploy noch da – ihr Drop würde die noch laufende Vorgänger-Revision
#:    treffen (Migration 090). Sie gehört dann **hierher** (``"tabelle.spalte"``) und in
#:    ``docs/backlog.md``; der Eintrag geht mit ihrem Drop.
PENDING_DROP: set[str] = set()


def leftovers(insp) -> list[str]:
    """Tabellen und Spalten, die **kein Modell** kennt – die Rückrichtung des Wächters
    darüber, als Funktion, damit der Gegentest sie gegen die Bug-Form fahren kann."""
    from app.core.database import Base
    import app.models  # noqa: F401 – füllt die Metadaten

    pending = PENDING_DROP
    tables = Base.metadata.tables
    found: list[str] = []
    for name in sorted(set(insp.get_table_names()) - set(tables) - _TABLES_WITHOUT_MODEL):
        found.append(name)
    for name in sorted(set(insp.get_table_names()) & set(tables)):
        mapped = {c.name for c in tables[name].columns}
        found += [f"{name}.{c['name']}" for c in insp.get_columns(name)
                  if c["name"] not in mapped and f"{name}.{c['name']}" not in pending]
    return found


def test_nothing_is_left_that_no_model_knows(built):
    """►►► **Die Rückrichtung: nach ``upgrade head`` steht nichts, was kein Modell kennt**
    (Cleanup Paket F/G, Migration 152). ◄◄◄

    Die Zwei-Deploy-Regel hat zwei Schritte – Mapping weg, dann Drop –, und zwischen ihnen
    lag bis hierher nur ein Backlog-Eintrag: 60 Spalten und 17 Tabellen standen still in
    der Datenbank, einige seit Monaten.

    *Bewusst behalten (Entscheid E7)* sind ``articles.safety_stock``, ``min_order_qty``,
    ``supplier_article_number``, ``user_profiles.language`` und ``notification_*`` – sie
    sind **gemappt**, also fallen sie hier gar nicht an; verliert eine davon ihr Mapping,
    meldet der Wächter sie, und das ist richtig: dann ist es eine neue Entscheidung.

    Bug-Form (gegengeprüft): ohne die Drops von Migration 152 meldete er 60 Spalten und
    17 Tabellen.
    Steht eine Spalte zwischen den beiden Schritten der Zwei-Deploy-Regel, wird sie in
    ``PENDING_DROP`` vorgemerkt – sichtbar, mit Backlog-Eintrag, und nur für einen Deploy.
    """
    found = leftovers(built)
    assert not found, (
        "Diese Tabellen/Spalten kennt kein Modell, und keine Migration droppt sie: "
        f"{', '.join(found)}.\nDroppen – oder, zwischen den beiden Schritten der "
        "Zwei-Deploy-Regel, in ``PENDING_DROP`` vormerken (und in docs/backlog.md)."
    )
