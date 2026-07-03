"""Lebenszyklus-Regeln: Datensätze sind nach der Freigabe gesperrt.

Solange ein Objekt im Status ``draft`` ist, sind alle Felder editierbar. Sobald
es freigegeben (oder später deaktiviert) wurde, dürfen nur noch Status und
``is_active`` geändert werden – Inhalte bleiben unveränderlich (vgl. CLAUDE.md:
„Artikel haben keine Versionierung: Änderung → neuer Artikel").
"""

from datetime import datetime

from fastapi import HTTPException

_LOCKED_ALLOWED = {"status", "is_active"}


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


def ensure_mutable(current_status: str, payload: dict, entity: str = "Datensatz") -> None:
    """Nur im Entwurf dürfen Inhalte geändert werden; sonst nur Status/is_active."""
    if current_status != "draft":
        changed = set(payload) - _LOCKED_ALLOWED
        if changed:
            raise HTTPException(
                409,
                detail=f"{entity} ist freigegeben und gesperrt – Inhalte können nicht mehr geändert werden",
            )
