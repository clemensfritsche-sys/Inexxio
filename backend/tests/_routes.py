"""**Alle Routen der App** – Pfad und Methoden, auch aus eingebundenen Routern.

Seit FastAPI 0.13x hängen eingebundene Router als ``_IncludedRouter`` in ``app.routes``;
die einzelnen Routen liefert erst ``fastapi.routing.iter_route_contexts``. Eine Stelle für
alle Wächter, die Routen zählen oder suchen.
"""

from fastapi.routing import iter_route_contexts


def api_routes(app) -> list[tuple[str, set[str]]]:
    return [(c.path, set(c.methods or ())) for c in iter_route_contexts(app.routes)]
