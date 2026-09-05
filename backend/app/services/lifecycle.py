"""Optimistic Locking – der eine Schutz gegen das stille Überschreiben.

**Warum hier nur noch eine Funktion steht.** Daneben lebte ``ensure_mutable`` («nur im
Entwurf sind Inhalte änderbar»). Sie hatte **keinen einzigen Aufrufer** und verglich mit
``"draft"`` – einem Wort, das die Statusliste seit dem Basis-Neuaufbau nicht mehr kennt
(``domain/statuses``: ``freigegeben`` ↔ ``inaktiv``). Sie hätte also, sobald jemand sie
gerufen hätte, **jeden** Datensatz für gesperrt gehalten.

Die Regel selbst gibt es weiterhin – nur an ihrer richtigen Stelle: es gibt keinen
Endpunkt, der Spezifikation oder Prozess eines angelegten Artikels ändert. Eingefrorenes
ist kein bewachtes Verbot, sondern eine fehlende Tür.
"""

from datetime import datetime

from fastapi import HTTPException


def ensure_version(record, expected_updated_at: datetime | None) -> None:
    """Optimistic Locking: stimmt der mitgesendete ``updated_at``-Stand nicht mit
    dem aktuellen überein, wurde der Datensatz zwischenzeitlich anderswo geändert
    → 409 (der Aufrufer darf nicht still überschreiben). Ohne Angabe (None) wird
    nicht geprüft (rückwärtskompatibel)."""
    if expected_updated_at is None:
        return
    current = getattr(record, "updated_at", None)
    if current is not None and current != expected_updated_at:
        raise HTTPException(
            409,
            detail="Datensatz wurde zwischenzeitlich an anderer Stelle geändert – bitte neu laden",
        )
