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


def test_every_model_column_exists_in_a_schema_built_only_from_the_migrations(built):
    from app.core.database import Base
    import app.models  # noqa: F401 – füllt die Metadaten
    from app.main import _COLUMN_SAFETY_NET

    insp = built
    netted = {(t, c) for t, c, *_ in _COLUMN_SAFETY_NET}
    tables = set(insp.get_table_names())

    gaps: list[str] = []
    for name, table in sorted(Base.metadata.tables.items()):
        # Eine fehlende **Tabelle** legt ``create_all`` im Lifespan an – das ist der
        # dafür vorgesehene zweite Weg, kein Befund.
        if name not in tables:
            continue
        have = {c["name"] for c in insp.get_columns(name)}
        for col in sorted({c.name for c in table.columns} - have):
            if (name, col) not in netted:
                gaps.append(f"{name}.{col}")

    assert not gaps, (
        "Diese Spalten kennt das Modell, aber weder eine Migration noch das "
        f"Lifespan-Netz legt sie an: {', '.join(gaps)}.\n"
        "Lokal fällt das nicht auf (dort hat ``create_all`` die Tabelle einmal "
        "vollständig angelegt) – gegen ein frisches Schema endet danach JEDE "
        "Abfrage auf diese Tabelle in einem 500. Entweder in die Migration "
        "aufnehmen oder in ``main._COLUMN_SAFETY_NET``."
    )


#: Was ohne Modell stehen darf: die Versionstabelle von Alembic. (``objects``, die
#: Nummern-Registry, IST ein Modell – ``ObjectRef``.)
_TABLES_WITHOUT_MODEL = {"alembic_version"}

#: ►► **Zwischen den beiden Schritten der Zwei-Deploy-Regel** steht eine Spalte ohne Mapping
#:    für **einen** Deploy noch da – ihr Drop würde die noch laufende Vorgänger-Revision
#:    treffen (Migration 090). Sie gehört dann **hierher** (``"tabelle.spalte"``) und in
#:    ``docs/backlog.md``; der Eintrag geht mit ihrem Drop. Eine Spalte im
#:    ``_NULLABLE_SAFETY_NET`` gilt von selbst als vorgemerkt.
PENDING_DROP: set[str] = {
    # Migration 153: das Häkchen ist ein Nachweis geworden (``newsletter_consents``).
    "user_profiles.newsletter_opt_in",
    # Migration 154: Eintritt und Pensum stehen im Vertrag der Zeiterfassung.
    "user_profiles.employment_start_date",
    "user_profiles.weekly_hours",
}


def leftovers(insp) -> list[str]:
    """Tabellen und Spalten, die **kein Modell** kennt – die Rückrichtung des Wächters
    darüber, als Funktion, damit der Gegentest sie gegen die Bug-Form fahren kann."""
    from app.core.database import Base
    import app.models  # noqa: F401 – füllt die Metadaten

    from app.main import _NULLABLE_SAFETY_NET

    pending = PENDING_DROP | {f"{t}.{c}" for t, c in _NULLABLE_SAFETY_NET}
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
    der Datenbank, einige seit Monaten, und drei Netze und Reparaturen liefen bei jedem
    Start nur ihretwegen. Eine Spalte ohne Leser kostet nichts, ein Netz für sie schon –
    und es hält sie lebendig.

    *Bewusst behalten (Entscheid E7)* sind ``articles.safety_stock``, ``min_order_qty``,
    ``supplier_article_number``, ``user_profiles.language`` und ``notification_*`` – sie
    sind **gemappt**, also fallen sie hier gar nicht an; verliert eine davon ihr Mapping,
    meldet der Wächter sie, und das ist richtig: dann ist es eine neue Entscheidung.

    Bug-Form (gegengeprüft): ohne Migration 152 meldet er alle 60 Spalten und 17 Tabellen.
    Steht eine Spalte zwischen den beiden Schritten der Zwei-Deploy-Regel, wird sie in
    ``PENDING_DROP`` vorgemerkt – sichtbar, mit Backlog-Eintrag, und nur für einen Deploy.
    """
    found = leftovers(built)
    assert not found, (
        "Diese Tabellen/Spalten kennt kein Modell, und keine Migration droppt sie: "
        f"{', '.join(found)}.\nDroppen – oder, zwischen den beiden Schritten der "
        "Zwei-Deploy-Regel, in ``PENDING_DROP`` vormerken (und in docs/backlog.md). Ein "
        "Netz oder eine Reparatur, die sie anfasst, fällt mit dem Drop."
    )


def test_no_safety_net_names_a_column_no_model_knows():
    """**Ein Netz für eine Spalte, die kein Modell kennt, schützt nichts – es lässt sie
    auferstehen.** ``_COLUMN_SAFETY_NET`` legte ``articles.landed_unit_cost`` bei jedem
    Start wieder an, obwohl das Mapping längst weg war; nach dem Drop (152) wäre die
    Spalte beim nächsten Start zurück gewesen. Bug-Form (gegengeprüft): der Eintrag steht
    wieder im Netz."""
    sys.path.insert(0, str(BACKEND))
    from app.core.database import Base
    import app.models  # noqa: F401
    from app import main

    tables = Base.metadata.tables

    def mapped(t: str, c: str) -> bool:
        return t in tables and c in {x.name for x in tables[t].columns}

    # ``_NULLABLE_SAFETY_NET`` nennt per Definition Spalten **ohne** Mapping (erster Schritt
    # der Zwei-Deploy-Regel) – es steht darum nicht in dieser Liste.
    stray = [f"{t}.{c}" for t, c, *_ in (*main._COLUMN_SAFETY_NET,
                                         *main._NUMERIC_SAFETY_NET)
             if not mapped(t, c)]
    assert not stray, f"Netz-Einträge ohne Modell: {', '.join(stray)}."
