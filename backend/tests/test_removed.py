"""**Was entfernt ist, bleibt entfernt** – EINE Liste statt eines Grabsteins je Runde.

Welche fachliche Entscheidung hinter einem Eintrag steckt, steht in ``docs/attic.md``
bzw. ``docs/history/``; hier steht nur, dass es nicht zurückkommt. Ein neuer Eintrag ist
eine Zeile. Gefragt wird nach Wörtern und Namen, nicht nach Dateien: eine gelöschte oder
umbenannte Datei trägt das Wort sicher nicht mehr. Bug-Form: ein Wort im Code oder ein
Name aus der Liste ist wieder da.
"""

import importlib
import sys

from tests._source import BACKEND, ROOT, _code

# (Datei, nur Code ohne Kommentare?, Wörter, die darin nicht mehr stehen)
GONE_TEXT = (
    *((f"backend/app/services/{f}", False,
       ("Anteil", "Reservierung", "Unterdeckung", "Nachschub"))
      for f in ("process.py", "release.py", "order_state.py")),
    ("frontend/src/lib/modules.ts", True, ("Objekt scannen",)),
    ("frontend/src/components/erp/capture-form.tsx", True, ("Objekt scannen",)),
    ("frontend/src/components/erp/process-designer.tsx", True, ("Objekt scannen",)),
    ("backend/app/main.py", True, ("object_refs",)),
    ("frontend/src/lib/api.ts", True, ("getObjectReferences",)),
    ("frontend/src/lib/modules.ts", False, (
        "export const FLOW", "export function flowOf", "export const HAULAGE",
        "export const STAGE ", "export const MANUAL_METHODS")),
    ("frontend/src/lib/api.ts", False, (
        "updateDeal", "searchDealParties", "dealTransfer", "preparePayment",
        "refundPayment")),
    ("backend/app/routers/orders.py", True, ("/deal", "deal-parties", "deal_svc")),
    *((f"backend/app/{f}", True, ("import deal", "from .deal")) for f in (
        "services/process.py", "services/release.py", "services/order_state.py",
        "services/stripe_pay.py", "routers/orders.py",
        "schemas/order.py", "models/__init__.py")),
    # Der tote Deaktivieren-Dialog und der Statuswechsel am Artikel (#773)
    ("frontend/src/components/erp/article-detail.tsx", False, (
        "setDialog", "eslint-disable-next-line no-unused-vars", "changeStatus",
        'data-tip="Inaktiv setzen', 'data-tip="Aktiv setzen')),
    # «Antwort auf» in der Kommunikation (Migration 148)
    *((f"backend/app/services/{f}", False, ("MessageReply",)) for f in (
        "communication.py", "mailbox.py", "inquiry.py")),
    *((f"frontend/src/components/erp/{f}", False, (
        "reply_to", "answer_to", "function Quote", "jump(")) for f in (
        "communication.tsx", "communication/timeline.tsx", "communication/composer.tsx")),
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
