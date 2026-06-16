"""Lebenszyklus-Regeln: Datensätze sind nach der Freigabe gesperrt.

Solange ein Objekt im Status ``draft`` ist, sind alle Felder editierbar. Sobald
es freigegeben (oder später deaktiviert) wurde, dürfen nur noch Status und
``is_active`` geändert werden – Inhalte bleiben unveränderlich (vgl. CLAUDE.md:
„Artikel haben keine Versionierung: Änderung → neuer Artikel").
"""

from fastapi import HTTPException

_LOCKED_ALLOWED = {"status", "is_active"}


def ensure_mutable(current_status: str, payload: dict, entity: str = "Datensatz") -> None:
    """Nur im Entwurf dürfen Inhalte geändert werden; sonst nur Status/is_active."""
    if current_status != "draft":
        changed = set(payload) - _LOCKED_ALLOWED
        if changed:
            raise HTTPException(
                409,
                detail=f"{entity} ist freigegeben und gesperrt – Inhalte können nicht mehr geändert werden",
            )


def ensure_article_draft(article, action: str = "Prozessschritte") -> None:
    """Prozessschritte dürfen nur an einem Artikel im Entwurf geändert werden."""
    if article.status != "draft":
        raise HTTPException(
            409,
            detail=f"Artikel ist freigegeben – {action} können nicht mehr geändert werden",
        )
