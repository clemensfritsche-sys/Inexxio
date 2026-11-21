"""►►► **Eine Abweisung – EINE Art, überall gleich** (Änderungsakte U6). ◄◄◄

Die Fachschicht sagt, **was** nicht geht, in einem Satz, der die Sache nennt – und **welcher
Art** die Abweisung ist. Wie das über das Netz geht, entscheidet EINE Stelle
(``main.rejected_handler``): immer dieselbe Form

    {"detail": "<der Satz>", "code": "<Art oder eigener Code>", "field": "<Feld>"?}

mit dem passenden HTTP-Status. Dienste und Fachschicht kennen kein HTTP; die Oberfläche zeigt
``detail`` und darf auf ``code`` reagieren (z. B. ``pick_stale``).

| Art | Status | wann |
|---|---|---|
| ``Invalid`` | 400 | die Eingabe passt nicht (fehlt, falsches Format, Regel verletzt) |
| ``Unauthorized`` | 401 | nicht angemeldet |
| ``Forbidden`` | 403 | angemeldet, aber nicht erlaubt (``domain/policy``) |
| ``NotFound`` | 404 | gibt es nicht – oder nicht für diese Person |
| ``Conflict`` | 409 | jetzt nicht (Zustand, Reihenfolge, schon erledigt, gleichzeitig) |
| ``Gone`` | 410 | gab es, ist weg (gelöscht, abgelaufen) |
| ``TooLarge`` | 413 | zu gross |
| ``TooMany`` | 429 | zu oft |
| ``Failed`` | 500 | unser Fehler, mit Satz |
| ``Upstream`` | 502 | ein Dienst draussen hat falsch geantwortet |
| ``Unavailable`` | 503 | etwas fehlt gerade (nicht eingerichtet, nicht erreichbar) |
"""

from typing import Optional


class Rejected(Exception):
    """Die Abweisung – nie direkt, immer eine ihrer Arten (oder ``rejected`` mit Status)."""

    status = 400
    code = "invalid"

    def __init__(self, detail: str, *, code: Optional[str] = None, field: Optional[str] = None):
        super().__init__(detail)
        self.detail = str(detail)
        if code is not None:
            self.code = code
        self.field = field

    def body(self) -> dict[str, str]:
        out = {"detail": self.detail, "code": self.code}
        if self.field:
            out["field"] = self.field
        return out


class Invalid(Rejected):
    status, code = 400, "invalid"


class Unauthorized(Rejected):
    status, code = 401, "unauthorized"


class Forbidden(Rejected):
    status, code = 403, "forbidden"


class NotFound(Rejected):
    status, code = 404, "not_found"


class Conflict(Rejected):
    status, code = 409, "conflict"


class Gone(Rejected):
    status, code = 410, "gone"


class TooLarge(Rejected):
    status, code = 413, "too_large"


class TooMany(Rejected):
    status, code = 429, "too_many"


class Failed(Rejected):
    status, code = 500, "failed"


class Upstream(Rejected):
    status, code = 502, "upstream"


class Unavailable(Rejected):
    status, code = 503, "unavailable"


KINDS: dict[int, type[Rejected]] = {k.status: k for k in (
    Invalid, Unauthorized, Forbidden, NotFound, Conflict, Gone, TooLarge, TooMany, Failed,
    Upstream, Unavailable)}


def rejected(status: int, detail: str, **kw) -> Rejected:
    """Die Art zu einem Status – wo eine Regel ihren Status selbst nennt (``(403, "…")``)."""
    return KINDS.get(status, Invalid)(detail, **kw)
