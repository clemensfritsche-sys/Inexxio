"""**Die geschlossene Liste der Erfassungspunkt-Typen — die eine Stelle.**

Wie bei den Statuswerten (``domain/statuses.py``): die Liste ist endlich, sie steht hier,
und ein Modul erfindet keinen eigenen Wert. Anders als dort ist ein Typ aber nicht nur
ein Wort, sondern **Verhalten** – prüfen, bewerten, wissen was fehlt. Darum ist jeder Typ
eine eigene Datei mit einer eigenen Klasse.

**Ein sechster Typ ist eine neue Datei. Sonst nichts.** Die Registry findet ihn selbst
(``pkgutil``); es gibt keine Aufzählung, die man dabei vergessen könnte, und keine
``if type == …``-Kette, in der man eine von drei Stellen übersieht. Das war die Vorgabe,
und sie ist hier wörtlich gebaut.

Diese Modul-Datei enthält daneben genau die zwei Fragen, die der Rest des Systems an die
Typen hat:

* ``clean_points`` – **Definition**: ist diese Punkte-Liste anlegbar?
* ``check_values`` / ``verdict`` – **Laufzeit**: ist erfasst, was Pflicht war, und was
  sagen die bewertbaren Punkte?
"""

from importlib import import_module
from pkgutil import iter_modules
from typing import Any, Optional

from fastapi import HTTPException

from .base import CaptureType, bad

_TYPES: dict[str, CaptureType] = {}


def _discover() -> None:
    """Jede Datei im Paket ist ein Typ (ausser dem Protokoll selbst).

    Auto-Erkennung statt einer Liste: eine Liste wäre die eine Stelle, an der man den
    neuen Typ vergisst – und der Fehler zeigte sich erst, wenn jemand ihn auswählt.
    """
    for module in iter_modules(__path__):
        if module.name == "base":
            continue
        found = getattr(import_module(f"{__name__}.{module.name}"), "TYPE", None)
        if isinstance(found, CaptureType):
            _TYPES[found.key] = found


_discover()

#: Alle Typen in Anzeige-Reihenfolge.
ALL: tuple[CaptureType, ...] = tuple(sorted(_TYPES.values(), key=lambda t: (t.order, t.key)))
KEYS: tuple[str, ...] = tuple(t.key for t in ALL)
LABELS: dict[str, str] = {t.key: t.label for t in ALL}


def get(key: Any) -> CaptureType:
    """Typ zu einem Schlüssel. Unbekannt = harter Fehler, kein Rückfall auf «Text»."""
    found = _TYPES.get(key)
    if found is None:
        raise bad(
            f"«{key}» ist kein Erfassungstyp. Erlaubt: "
            + ", ".join(f"{t.label} ({t.key})" for t in ALL) + "."
        )
    return found


# ---------------------------------------------------------------------------
# Definition
# ---------------------------------------------------------------------------

def _slug(label: str, taken: set[str]) -> str:
    """Ein stabiler Schlüssel aus der Bezeichnung.

    Er ist die Adresse des Wertes in ``captures.values`` und muss darum eindeutig sein –
    zwei Punkte «Länge» wären sonst derselbe Wert. Der Mensch tippt ihn nie; ihn eingeben
    zu lassen wäre ein Feld, dessen Zweck man erklären müsste.
    """
    base = "".join(c if c.isalnum() else "_" for c in label.strip().lower())
    base = "_".join(filter(None, base.split("_")))[:40] or "punkt"
    key, n = base, 2
    while key in taken:
        key, n = f"{base}_{n}", n + 1
    taken.add(key)
    return key


def clean_points(raw: Any) -> list[dict[str, Any]]:
    """Die Erfassungspunkte einer Modul-Definition prüfen und normalisieren.

    Ein Datenerfassungs-Modul **ohne** Punkt ist nicht anlegbar: es stünde im Prozess und
    hätte nichts zu erfassen – genau die halbfertige Definition, die «Hinzufügen» statt
    Auto-Save verhindern soll.
    """
    rows = list(raw or [])
    if not rows:
        raise bad(
            "Eine Datenerfassung ohne Erfassungspunkt erfasst nichts. "
            "Mindestens ein Punkt ist Pflicht."
        )
    out: list[dict[str, Any]] = []
    taken: set[str] = set()
    for position, row in enumerate(rows, start=1):
        label = str((row or {}).get("label") or "").strip()
        if not label:
            # **Hier, nicht im Schema** (#695): der Entwurf legt einen Punkt beim Klick an
            # und füllt ihn beim Tippen. Eine Schema-Pflicht machte daraus bei jedem
            # Tastendruck einen rohen Feldpfad-Fehler; verlangt wird sie darum erst bei der
            # Freigabe – und dann mit einem Satz, der sagt, welcher Punkt gemeint ist.
            raise bad(
                f"Erfassungspunkt {position} braucht noch eine Bezeichnung – sie ist die "
                f"Frage, die im Prozess gestellt wird."
            )
        if len(label) > 120:
            raise bad(f"Die Bezeichnung «{label[:30]}…» ist zu lang (max. 120 Zeichen).")
        kind = get(row.get("type"))
        point: dict[str, Any] = {
            "key": _slug(label, taken),
            "label": label,
            "type": kind.key,
        }
        point.update(kind.clean({**row, "label": label}))
        out.append(point)
    return out


# ---------------------------------------------------------------------------
# Laufzeit
# ---------------------------------------------------------------------------

def check_values(points: list[dict[str, Any]], values: dict[str, Any]) -> None:
    """Ist **alles** erfasst? Sonst ein Fehler, der die offenen Punkte **benennt**.

    «Bestätigen nicht möglich» ohne zu sagen was fehlt, wäre eine Sackgasse mit
    Ausrufezeichen.
    """
    values = values or {}
    known = {p["key"] for p in points}
    unknown = sorted(set(values) - known)
    if unknown:
        raise HTTPException(
            status_code=400,
            detail=(f"Unbekannte Erfassungspunkte: {', '.join(unknown)}. "
                    f"Dieses Modul kennt sie nicht."),
        )
    # **Alles, was angelegt ist, ist Pflicht.** Ein Schalter «Pflicht ja/nein» wäre die
    # Frage, warum man einen Erfassungspunkt anlegt, den niemand ausfüllen muss – und
    # jeder ausgeschaltete Punkt eine Lücke, die erst später auffällt.
    open_points = [
        p["label"] for p in points
        if get(p["type"]).missing(p, values.get(p["key"]))
    ]
    if open_points:
        raise HTTPException(
            status_code=400,
            detail=f"Noch nicht erfasst: {', '.join(open_points)}.",
        )


def verdict(points: list[dict[str, Any]], values: dict[str, Any]) -> Optional[str]:
    """``"passed"`` | ``"failed"`` | ``None`` — das Urteil über die **bewertbaren** Punkte.

    ``None`` heisst «hier war nichts zu beurteilen»: eine reine Text-/Foto-Erfassung hat
    kein Ergebnis, und ein erfundenes «bestanden» wäre eine Aussage, die niemand
    getroffen hat.
    """
    results = [
        get(p["type"]).verdict(p, (values or {}).get(p["key"]))
        for p in points
    ]
    judged = [r for r in results if r is not None]
    if not judged:
        return None
    return "passed" if all(judged) else "failed"


__all__ = [
    "ALL", "KEYS", "LABELS", "CaptureType",
    "get", "clean_points", "check_values", "verdict",
]
