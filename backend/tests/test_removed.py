"""**Was entfernt ist, bleibt entfernt** – EINE Liste statt eines Grabsteins je Runde.

Welche fachliche Entscheidung hinter einem Eintrag steckt, steht in ``docs/attic.md``
bzw. ``docs/history/``; hier steht nur, dass es nicht zurückkommt. Ein neuer Eintrag ist
eine Zeile. Gefragt wird nach Wörtern und Namen, nicht nach Dateien: eine gelöschte oder
umbenannte Datei trägt das Wort sicher nicht mehr. Bug-Form: ein Wort im Code oder ein
Name aus der Liste ist wieder da.

Das Frontend steht hier nicht mehr: es ruft nur Routen, die es gibt (``lib/api.ts`` ist gegen
``paths`` getippt), und ein entfernter Schlüssel, Typ oder ein entferntes Feld ist dort ein
Typfehler (generierte ``api.ts``/``vocab.ts``) – die Liste hier sähe nur alte Schreibweisen.
"""

import importlib
import sys

import pathlib
import re as _re

ROOT = pathlib.Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"


def _code(source: str) -> str:
    """Nur der Code — Kommentare und Docstrings raus.

    Ein Waechter, der einen Kommentar liest, prueft die Erklaerung statt der Sache: er
    schlaegt an, weil jemand den Fehler *beschreibt*, den er verhindern soll. Genau das
    ist beim Schreiben dieser Runde passiert.
    """
    # Blockkommentare: /* … */ und JSX {/* … */}, dazu Python-Docstrings.
    without = _re.sub(r"\{?/\*[\s\S]*?\*/\}?", "", source)
    without = _re.sub(r'"""[\s\S]*?"""', "", without)
    # Zeilenkommentare nur am Zeilenanfang – sonst trifft es «https://».
    return "\n".join(
        l for l in without.split("\n")
        if not l.lstrip().startswith(("//", "#", "*"))
    )

# (Datei, nur Code ohne Kommentare?, Wörter, die darin nicht mehr stehen)
GONE_TEXT = (
    *((f"backend/app/services/{f}", False,
       ("Anteil", "Reservierung", "Unterdeckung", "Nachschub"))
      for f in ("process.py", "release.py", "order_state.py")),
    ("backend/app/main.py", True, ("object_refs",)),
    ("backend/app/routers/orders.py", True, ("/deal", "deal-parties", "deal_svc")),
    *((f"backend/app/{f}", True, ("import deal", "from .deal")) for f in (
        "services/process.py", "services/release.py", "services/order_state.py",
        "services/stripe_pay.py", "routers/orders.py",
        "schemas/order.py", "models/__init__.py")),
    # «Antwort auf» in der Kommunikation (Migration 148)
    *((f"backend/app/services/{f}", False, ("MessageReply",)) for f in (
        "communication.py", "mailbox.py", "inquiry.py")),
)

# (Modul, Attribut-Pfad, Name, der darin nicht mehr vorkommt)
GONE_NAMES = (
    ("app.domain.capture_types", "ALL", "object"),
    ("app.domain.modules", "KEYS", "zahlung"),
    ("app.schemas.communication", "MessageIn.model_fields", "reply_to"),
    ("app.schemas.communication", "MessageOut.model_fields", "reply_to"),
    ("app.models", "__dict__", "MessageReply"),
)


def _resolve(module: str, path: str):
    obj = importlib.import_module(module)
    for part in path.split("."):
        obj = getattr(obj, part)
    return obj


def test_removed_stays_removed():
    sys.path.insert(0, str(BACKEND))
    back = []
    for f, code_only, words in GONE_TEXT:
        if not (ROOT / f).exists():
            continue
        src = (ROOT / f).read_text(encoding="utf-8")
        src = _code(src) if code_only else src
        back += [f"«{w}» in {f}" for w in words if w in src]
    back += [f"«{name}» in {module}.{path}" for module, path, name in GONE_NAMES
             if name in _resolve(module, path)]
    assert not back, "Entferntes ist zurück:\n  " + "\n  ".join(back)
