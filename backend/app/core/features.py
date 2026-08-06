"""Der EINE Schalter: was ist erreichbar und was ist abgeschaltet.

Der Basis-Neuaufbau legt die Prozesslogik still. Damit das nicht als verstreutes
Auskommentieren endet, steht die Entscheidung an genau EINER Stelle – ``ACTIVE``.
Alles, was dort nicht steht, ist abgeschaltet.

**Abgeschaltet heisst nicht «nicht vorhanden».** Ein 404 sieht aus wie ein Tippfehler
in der URL; ein abgeschaltetes Modul muss sagen, dass es abgeschaltet ist. Darum
mountet ``main.py`` für jedes inaktive Modul einen Stub unter seinem Prefix, der mit
``503`` und ``code="MODULE_DISABLED"`` antwortet. Der Aufrufer erfährt so den Grund
statt einer Sackgasse.

Das Frontend spiegelt diese Datei (``frontend/src/lib/features.ts``); der Abgleich
ist getestet (``tests/test_frontend_mirrors.py``), damit die beiden Seiten nicht
auseinanderlaufen können.
"""

from fastapi import APIRouter, HTTPException, Request

# ---------------------------------------------------------------------------
# Die Module. Name → (Anzeigename, Prefixe, die das Modul allein besitzt)
#
# Die Prefixe sind das, was der Stub übernehmen kann: Pfade, die ausschliesslich
# diesem Modul gehören. Endpunkte, die unter einem Prefix eines AKTIVEN Moduls
# lagen (z. B. die Prozessschritte unter /api/v1/erp/articles/{id}/steps), sind
# mit ihrem Router ersatzlos verschwunden und antworten schlicht 404 – dort würde
# ein Stub den aktiven Nachbarn verdecken.
# ---------------------------------------------------------------------------
MODULES: dict[str, tuple[str, tuple[str, ...]]] = {
    "core": ("Anmeldung, Benutzer, Unternehmen, Feed, Objektnummern", ()),
    "catalog": ("Artikel, Aufträge, Instanzen, Einzelinstanzen", ()),
    "capture": ("Datenerfassung", ()),
    # Der DATENSATZTYP «Auftrag» (/api/v1/erp/orders) ist aktiv und gehört zu ``catalog``.
    # Abgeschaltet ist die PROZESSLOGIK darin – sie hat heute keinen eigenen Pfad mehr,
    # also auch keinen Stub. Der Eintrag bleibt, weil der Schalter die Liste der Module
    # führt, nicht nur die der Prefixe.
    "process": ("Prozesslogik im Auftrag", (
        "/api/v1/erp/maintenance",
    )),
    "sales": ("Verkauf und Shop", (
        "/api/v1/shop",
    )),
    "documents": ("Dokumente, Belege, Rechtstexte, Einwilligungen", (
        "/api/v1/legal",
        "/api/v1/consent",
    )),
    "ai": ("KI-Assistent", (
        "/api/v1/ai",
    )),
}

# ---------------------------------------------------------------------------
# DIE Entscheidung. Genau hier wird ein Modul zu- oder abgeschaltet.
# ---------------------------------------------------------------------------
ACTIVE: frozenset[str] = frozenset({"core", "catalog", "capture"})


def is_active(module: str) -> bool:
    """Läuft dieses Modul? Ein unbekannter Name ist ein Programmierfehler, kein
    stilles «nein» – sonst schaltet sich ein Modul durch einen Tippfehler ab."""
    if module not in MODULES:
        raise KeyError(f"Unbekanntes Modul '{module}'. Bekannt: {sorted(MODULES)}")
    return module in ACTIVE


def label(module: str) -> str:
    return MODULES[module][0]


def disabled() -> list[str]:
    """Die abgeschalteten Module, in der Reihenfolge von ``MODULES``."""
    return [m for m in MODULES if m not in ACTIVE]


def require(module: str) -> None:
    """Wächter für einzelne Endpunkte, die in einem aktiven Router liegen, aber zu
    einem abgeschalteten Modul gehören."""
    if not is_active(module):
        raise HTTPException(status_code=503, detail=_message(module))


def _message(module: str) -> str:
    return (
        f"Das Modul «{label(module)}» ist abgeschaltet. Der Basis-Neuaufbau auf das "
        f"Einzelinstanz-Modell hat die Prozesslogik entfernt; dieses Modul wird erst "
        f"wieder aufgebaut, wenn das Fundament steht. Umgelegt wird der Schalter in "
        f"backend/app/core/features.py (ACTIVE)."
    )


def stub_router(module: str) -> APIRouter:
    """Ein Router, der jeden Pfad unter den Prefixen des Moduls beantwortet – mit
    dem Grund, nicht mit Schweigen."""
    router = APIRouter(tags=[f"disabled:{module}"])

    async def answer(request: Request, path: str = ""):
        raise HTTPException(status_code=503, detail=_message(module))

    for prefix in MODULES[module][1]:
        for route in (prefix, prefix + "/{path:path}"):
            router.add_api_route(
                route, answer,
                methods=["GET", "POST", "PATCH", "PUT", "DELETE"],
                include_in_schema=False,
            )
    return router


def stub_routers() -> list[APIRouter]:
    """Alle Stubs für abgeschaltete Module, die eigene Prefixe besitzen."""
    return [stub_router(m) for m in disabled() if MODULES[m][1]]
