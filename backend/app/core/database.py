import json
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
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


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
