"""**Alembic ist die Schema-Wahrheit — geprüft statt behauptet.**

Die Regel aus Migration 090 hiess: *eine neue Spalte auf einer **bestehenden** Tabelle
ist erst fertig, wenn sie in der Migration UND im Lifespan-Netz steht.* Richtig, aber zu
eng — und genau daran ist Migration `112` vorbeigelaufen: sie legte ``awards`` an und
vergass ``is_active`` (aus ``TimestampMixin``). Ihre eigene Begründung war der Fehler
(«fehlende **Tabellen** legt ``create_all()`` an»):

    ``create_all()`` legt an, was ganz fehlt. Eine Tabelle, die es schon gibt, fasst es
    NIE an — auch dann nicht, wenn ihr eine Spalte fehlt, die das Modell kennt.

Eine **halb** angelegte Tabelle ist damit schlimmer als eine fehlende: sie sieht fertig
aus und hat kein Netz. Gegen eine ``create_all``-Datenbank lief alles grün; gegen ein aus
den Migrationen gebautes Schema endete **jede** Vergabe-Abfrage in einem 500.

Dieser Wächter beantwortet die Frage ein für alle Mal, und zwar **abgeleitet statt
gepflegt**: er baut das Schema in eine Wegwerf-Datenbank von null aus den Migrationen und
hält es gegen ``Base.metadata``. Eine gepflegte Liste erwarteter Tabellen wäre genau die
Form, die beim nächsten Modell vergessen wird.

**Nur diese eine Richtung.** Eine Spalte, die es in der Datenbank gibt und im Modell nicht
mehr, ist der **gewollte** Zwischenzustand eines Folge-Deploys (``_DROP_COLUMN_SAFETY_NET``
— die während des Rollouts noch laufende Vorgänger-Revision mappt sie ja noch).
"""

import os
import subprocess
import sys

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url

from .support import BACKEND

#: Die Wegwerf-Datenbank. Ein eigener Name, damit der Wächter niemals die Datenbank
#: anfasst, gegen die die übrigen Tests laufen.
SCRATCH = "inexxio_migration_check"

#: Tabellen, die **bewusst** allein aus ``create_all()`` entstehen – benannt, mit Grund.
#:
#: Eine fehlende **Tabelle** heilt das Lifespan-Netz wirklich (es legt sie an); eine
#: fehlende **Spalte** darin nie. Darum ist das hier eine Liste und die Spalten-Prüfung
#: ausnahmslos. Still durchwinken wäre die dritte Möglichkeit, und sie läse sich wie
#: Vollständigkeit.
#:
#: Die Liste kann nicht verrotten: steht hier eine Tabelle, die eine Migration inzwischen
#: anlegt, meldet der Wächter das (dann gehört der Eintrag weg).
CREATE_ALL_ONLY: dict[str, str] = {
    "objects": (
        "Registry Objektnummer → Typ, seit jeher ohne Migration; sie wird beim Start "
        "angelegt und von ``services/objects`` gefüllt. Älter als ADR 009 – hier "
        "benannt, nicht nachträglich stillgelegt."
    ),
}


def _server_url():
    """Die Verbindung zum **Server**, nicht zur Datenbank – oder ein Skip mit Grund."""
    sys.path.insert(0, str(BACKEND))
    os.environ.setdefault("FIREBASE_PROJECT_ID", "test")
    from app.core.config import get_settings

    url = make_url(get_settings().database_url)
    try:
        eng = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
        with eng.connect():
            pass
    except Exception as exc:  # pragma: no cover - reine Umgebungsfrage
        pytest.skip(f"Kein PostgreSQL erreichbar ({type(exc).__name__}: {exc}) – "
                    f"DATABASE_URL setzen, damit diese Regel wirklich läuft.")
    return url


def _build_from_migrations(url) -> str:
    """Wegwerf-Datenbank anlegen und ``alembic upgrade head`` fahren. Gibt die URL zurück.

    Als Unterprozess, weil ``alembic/env.py`` seine Verbindung aus ``DATABASE_URL`` liest –
    die Umgebung des laufenden Testprozesses dafür umzubiegen hiesse, seiner eigenen
    Sitzung den Boden wegzuziehen.
    """
    admin = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f'DROP DATABASE IF EXISTS "{SCRATCH}" WITH (FORCE)'))
        conn.execute(text(f'CREATE DATABASE "{SCRATCH}"'))
    admin.dispose()

    target = url.set(database=SCRATCH)
    # ``alembic/env.py`` reicht die URL durch ``set_main_option`` – und die läuft durch
    # ConfigParser-Interpolation. Ein prozentkodiertes Zeichen (der Socket-Pfad einer
    # lokalen Entwicklungsumgebung, ``host=%2Ftmp``) wäre dort ein Interpolations-Ausdruck.
    # Der Socket-Pfad gehört darum in ``PGHOST``, wo libpq ihn ohnehin erwartet.
    env, plain = dict(os.environ), target
    if "host" in target.query:
        env["PGHOST"] = str(target.query["host"])
        plain = target.difference_update_query(["host"])
    done = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=BACKEND, capture_output=True, text=True,
        env={**env, "DATABASE_URL": plain.render_as_string(hide_password=False)},
    )
    assert done.returncode == 0, (
        "Das Schema lässt sich nicht von null aus den Migrationen aufbauen – genau das "
        "prüft die CI vor jedem Deploy:\n" + done.stderr[-3000:])
    return target


def _drop(url) -> None:
    admin = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f'DROP DATABASE IF EXISTS "{SCRATCH}" WITH (FORCE)'))
    admin.dispose()


@pytest.fixture(scope="module")
def migrated():
    """Ein Schema, **von null** aus den Migrationen gebaut – einmal je Datei (~4 s)."""
    url = _server_url()
    target = _build_from_migrations(url)
    eng = create_engine(target)
    try:
        yield inspect(eng)
    finally:
        eng.dispose()
        _drop(url)


def test_every_column_comes_from_a_migration_or_the_safety_net(migrated):
    """**Eine Spalte, die das Modell kennt, muss im Betrieb auch existieren.**

    Sie entsteht auf genau zwei Wegen: aus ihrer **Migration** (die Wahrheit) oder aus dem
    **Lifespan-Netz** (der zweite Weg). Steht sie in keinem von beiden, gibt es sie nicht –
    und weil das Modell sie kennt, endet **jede** Abfrage auf ihre Tabelle in einem 500.

    Bug-Form: eine Migration legt eine Tabelle an und vergisst eine Spalte – so geschehen
    mit ``awards.is_active`` (aus ``TimestampMixin``). Gegen eine ``create_all``-Datenbank
    fällt das **nicht** auf, denn ``create_all`` legt an, was ganz fehlt, und fasst eine
    Tabelle, die es schon gibt, nie an. Eine halb angelegte Tabelle ist damit schlimmer als
    eine fehlende: sie sieht fertig aus und hat kein Netz.

    Der zweite Weg allein ist **erlaubt, aber nicht das Ziel** (Lehre aus Migration 090):
    die Migration ist die Wahrheit, das Netz das Netz. Geprüft wird hier, dass mindestens
    einer der beiden trägt – die Erwartung ist ``Base.metadata``, also abgeleitet statt
    gepflegt.
    """
    from app.core.database import Base
    from app.main import _COLUMN_SAFETY_NET
    import app.models  # noqa: F401  – füllt die Metadaten

    netted = {(table, col) for table, col, _ddl in _COLUMN_SAFETY_NET}
    built = set(migrated.get_table_names())
    gaps: dict[str, list[str]] = {}
    for name, table in sorted(Base.metadata.tables.items()):
        if name not in built:
            continue                      # fehlende Tabellen: der Wächter darunter
        have = {col["name"] for col in migrated.get_columns(name)}
        missing = [c.name for c in table.columns
                   if c.name not in have and (name, c.name) not in netted]
        if missing:
            gaps[name] = missing

    assert not gaps, (
        "Diese Spalten kennt das Modell, aber weder die Migration noch das Lifespan-Netz "
        "legt sie an: "
        + "; ".join(f"{n}: {', '.join(cols)}" for n, cols in gaps.items())
        + ". Im Betrieb endet damit jede Abfrage auf diese Tabelle in einem 500.")


def test_only_named_tables_rely_on_create_all(migrated):
    """**Wer ohne Migration auskommt, wird benannt** – und die Liste kann nicht verrotten.

    Bug-Form (in beide Richtungen): eine neue Tabelle entsteht still nur über
    ``create_all`` – dann steht sie in keiner Migration und niemand hat entschieden, dass
    das so sein soll; **oder** ein Eintrag bleibt stehen, nachdem eine Migration die
    Tabelle doch anlegt – dann behauptet die Liste eine Ausnahme, die es nicht gibt.
    """
    from app.core.database import Base
    import app.models  # noqa: F401

    built = set(migrated.get_table_names())
    unnamed = sorted(n for n in Base.metadata.tables
                     if n not in built and n not in CREATE_ALL_ONLY)
    assert not unnamed, (
        f"Diese Tabellen legt keine Migration an und niemand hat es begründet: "
        f"{', '.join(unnamed)}. Alembic ist die Schema-Wahrheit; wer davon abweicht, "
        f"schreibt den Grund in ``CREATE_ALL_ONLY``.")

    stale = sorted(n for n in CREATE_ALL_ONLY if n in built)
    assert not stale, (
        f"Diese Tabellen stehen als Ausnahme in ``CREATE_ALL_ONLY``, werden aber von einer "
        f"Migration angelegt: {', '.join(stale)}. Der Eintrag gehört weg.")
