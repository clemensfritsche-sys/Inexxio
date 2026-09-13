import json
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from .config import get_settings

settings = get_settings()


def json_safe(value):
    """Einen Wert JSONB-tauglich machen – ``Decimal`` → ``float``, Datum → ISO-String.

    **Warum das hier steht und nicht in der Fachlogik:** seit den Bruchmengen (Migration
    ``055``) ist jede Menge im System ein ``Decimal``. ``json.dumps`` kann das nicht, und
    das fällt erst beim Schreiben auf – als ``TypeError`` mitten in der Transaktion, also
    als **500 auf dem ganzen Endpunkt**. Genau so war der Prozessschritt «Ressource»
    unbenutzbar: ``resource_usages.details`` bekam die entnommene Menge als ``Decimal``,
    und JEDE Verbuchung eines Verbrauchs brach ab (der Event-Strom hatte seine eigene
    Normalisierung, die anderen JSONB-Spalten nicht).

    Deshalb sitzt die Normalisierung an der **Grenze zur Datenbank** statt in jedem
    Schreiber: es gibt zwölf JSONB-Spalten, und jede neue erbt den Schutz automatisch.

    Sie ist ein **Netz, kein Vertrag**: wo es auf Exaktheit ankommt (Geld, reservierte
    Mengen, Standort-Teilmengen), schreibt der Fachcode bewusst **Strings**
    (``reservation``, ``location_split``, ``selling._resolve_line``) – dort kommt hier nie
    ein ``Decimal`` an. Was hier landet, ist ein Beobachtungs-Wert (Protokoll, Event-
    Payload); für den ist ``float`` die richtige, JSON-native Form.
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


engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
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
