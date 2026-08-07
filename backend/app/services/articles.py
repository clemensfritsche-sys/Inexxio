"""Artikel – Anlage (= Freigabe) und Freigabebedingungen.

**Ein Artikel entsteht erst bei der Freigabe.** Bis dahin lebt der Entwurf im Browser:
keine Zeile, keine Objektnummer, kein Autosave, kein Datensatz «draft». Das ist dieselbe
Regel wie beim Auftrag (``services/orders.py``) und aus demselben Grund – wer ein Fenster
verlässt, lässt keine Spur.

*Vorher war es anders, und das war ein Fehler:* das Formular speicherte per Autosave,
sobald die Pflichtfelder der Spezifikation standen. Damit existierte ein Artikel mit
Objektnummer, der nichts erzeugen konnte, weil sein Prozess leer war – ein Datensatz, der
eine Zusage macht, die er nicht halten kann.

Die Freigabebedingungen stehen **an dieser einen Stelle**. Die Oberfläche fragt sie ab
(``POST /erp/articles/validate``), statt sie nachzuformulieren; sonst gäbe es zwei
Massstäbe für dieselbe Frage, und der schwächere entscheidet, ob der Knopf leuchtet.
"""

from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..domain import statuses as st
from ..models import Article
from . import article_process
from .objects import next_object_id

#: Status eines angelegten Artikels – aus der EINEN Statusliste (``domain/statuses``).
#: Es gibt nur diesen einen Einstieg: **angelegt heisst freigegeben**.
RELEASED = st.FREIGEGEBEN

#: Pflichtfelder der Spezifikation (Feldname → Beschriftung). Sie stehen hier und nicht
#: im Formular: eine deaktivierte Schaltfläche ist keine Absicherung, sondern eine Bitte.
_REQUIRED = (
    ("name", "Artikelname"),
    ("size", "Abmessungen"),
    ("weight_kg", "Gewicht"),
)


def missing_for_release(draft: dict[str, Any]) -> list[str]:
    """Was fehlt diesem Artikel-Entwurf noch zur Freigabe? Leere Liste = freigebbar.

    Beide harten Bedingungen, in **einer** Funktion:

    1. alle Pflichtfelder der Spezifikation,
    2. mindestens ein Prozessschrittmodul im Erzeugungsprozess.

    Namen statt True/False, damit die Oberfläche sagen kann *was* fehlt, statt den Nutzer
    suchen zu lassen.
    """
    # Ausdrücklich auf «nicht gesetzt» geprüft, nicht auf «unwahr»: ein Gewicht von 0 ist
    # ein Wert, den jemand eingetragen hat. Ob er fachlich taugt, entscheidet der
    # Feld-Validator – nicht eine Wahrheitsprüfung, die 0 wie «leer» behandelt.
    missing = [
        label for key, label in _REQUIRED
        if draft.get(key) is None or str(draft.get(key)).strip() == ""
    ]
    if not list(draft.get("steps") or []):
        missing.append("mindestens ein Prozessschrittmodul")
    return missing


def validate_draft(draft: dict[str, Any]) -> list[str]:
    """Wäre dieser Entwurf freigebbar? Prüft **dieselben** Bedingungen wie die Anlage.

    Zusätzlich läuft die Modul-Definition durch ihre echte Prüfung: ein Modul ohne
    Erfassungspunkt oder ein Soll-Ist-Vergleich ohne Sollwert soll auffallen, **bevor**
    jemand auf «Freigeben» drückt – nicht als Fehlermeldung danach.
    """
    missing = missing_for_release(draft)
    if missing:
        return missing
    try:
        _clean_steps(list(draft.get("steps") or []))
    except HTTPException as e:
        return [str(e.detail)]
    return []


def _clean_steps(raw: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Die Modul-Definitionen durch die echte Prüfung schicken, ohne etwas anzulegen.

    Sie ist dieselbe, die ``article_process.create_steps`` benutzt – die Prüfung sitzt im
    Modul (``domain/modules.Module.clean_config``), nicht in einer Kopie davon.
    """
    from ..domain import modules

    for data in raw:
        module = modules.get(data.get("module_type"))
        module.clean_config(data.get("config"))
    return raw


def create_article(db: Session, draft: dict[str, Any], *, actor_id: int | None) -> Article:
    """Aus einem Entwurf einen freigegebenen Artikel machen. **Eine Transaktion.**

    Reihenfolge wie beim Auftrag: erst prüfen, **dann** die Objektnummer ziehen. Eine
    Sequence ist absichtlich nicht transaktional – ein Rollback danach liesse eine Lücke
    im Nummernkreis. Ein abgebrochener Versuch verbraucht darum keine Nummer.
    """
    steps = list(draft.pop("steps", None) or [])
    draft = {k: v for k, v in draft.items() if v is not None}

    missing = missing_for_release({**draft, "steps": steps})
    if missing:
        raise HTTPException(
            status_code=400,
            detail="Der Artikel ist noch nicht freigebbar – es fehlt: " + ", ".join(missing) + ".",
        )
    _clean_steps(steps)

    # ── Ab hier wird eine Nummer vergeben ────────────────────────────────────
    article = Article(object_id=next_object_id(db, "article"), status=RELEASED, **draft)
    db.add(article)
    db.flush()
    article_process.create_steps(db, article, steps)
    return article
