import json
from contextvars import ContextVar
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from fastapi import Depends
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker, DeclarativeBase
from .config import get_settings

settings = get_settings()


def json_safe(value):
    """Einen Wert JSONB-tauglich machen – ``Decimal`` → ``float``, Datum → ISO-String.

    **Warum das hier steht und nicht in der Fachlogik:** ``json.dumps`` kann kein
    ``Decimal``, und das fällt erst beim Schreiben auf – als ``TypeError`` mitten in der
    Transaktion, also als **500 auf dem ganzen Endpunkt**. Die Normalisierung sitzt darum
    an der **Grenze zur Datenbank** statt in jedem Schreiber: jede neue JSONB-Spalte erbt
    den Schutz automatisch.

    Sie ist ein **Netz, kein Vertrag**: wo es auf Exaktheit ankommt (Geld), schreibt der
    Fachcode bewusst **Strings** – dort kommt hier nie ein ``Decimal`` an. Was hier landet,
    ist ein Beobachtungs-Wert (Protokoll, Event-Payload); für den ist ``float`` die
    richtige, JSON-native Form.
    """
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(v) for v in value]
    return value


def _json_serializer(value) -> str:
    """Serializer für ALLE JSON/JSONB-Spalten (an die Engine gehängt)."""
    return json.dumps(json_safe(value))


#: **Klein mit Absicht**: je Worker 5 (+5 in Spitzen) – bei 2 Workern und bis zu 10 Instanzen
#: sind das höchstens 200 Verbindungen statt 600; eine kleine Cloud-SQL-Stufe erlaubt kaum mehr.
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=5,
    echo=settings.debug,
    json_serializer=_json_serializer,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


#: Wer handelt – an der Sitzung gemerkt (``core/actor.act``) und in jede Transaktion getragen.
ACTOR_KEY = "log_actor"
SET_ACTOR = text("SELECT set_config('inexxio.actor', :a, true)")


@event.listens_for(SessionLocal, "after_begin")
def _carry_actor(session, _transaction, connection) -> None:
    """``SET LOCAL`` gilt nur bis zum Commit – jede neue Transaktion der Sitzung bekommt den
    Handelnden wieder (``core/actor``)."""
    actor = session.info.get(ACTOR_KEY)
    if actor:
        connection.execute(SET_ACTOR, {"a": json.dumps(actor)})


class Base(DeclarativeBase):
    pass


#: Die Sitzung, in der gerade ein **Handgriff** läuft (``services/handgriff``): die Route, die er
#: aufruft, arbeitet in ihr, statt eine eigene zu öffnen – gespeichert oder verworfen wird dort.
AMBIENT: ContextVar[Optional[Session]] = ContextVar("ambient_session", default=None)


def get_db():
    """►►► **Eine Anfrage speichert einmal – am Ende.** ◄◄◄ (Projektakte, Phase 5 §6.1)

    Endet die Route ohne Fehler, wird gespeichert; wirft sie, wird alles verworfen – ganz
    oder gar nicht. Kein Router und kein Dienst speichert mittendrin (``db.flush()`` genügt
    für eine Nummer). Was erst nach dem Speichern hinausgehen darf, meldet sich bei
    ``core/outside.after``.

    Eingebunden wird sie **nur** über ``DB`` (``scope="function"``): dann läuft das Speichern,
    bevor die Antwort hinausgeht – scheitert es, ist die Antwort ein Fehler, nie ein «ok» ohne
    Speicherung.

    Läuft ein Handgriff (``AMBIENT``), gibt es dessen Sitzung – ohne zu speichern."""
    shared = AMBIENT.get()
    if shared is not None:
        yield shared
        return
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except BaseException:
        db.rollback()
        raise
    finally:
        db.close()


#: Die Sitzung einer Anfrage – ``db: Session = DB``. Eine Stelle, ein Geltungsbereich.
DB = Depends(get_db, scope="function")
