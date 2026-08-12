"""Die Invarianten über den **gesamten** Bestand fahren und den Befund schreiben.

    python -m scripts.invariant_report

Sie sind rein lesend. Was sie melden, ist ein Befund – keine Reparatur.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import os                                                      # noqa: E402

os.environ.setdefault("FIREBASE_PROJECT_ID", "test")

from app.core.database import SessionLocal                     # noqa: E402
from app.services import invariants                            # noqa: E402


def main() -> int:
    if "--populate" in sys.argv:
        # Die Matrix **committen**, damit die Invarianten über einen echten Bestand
        # laufen – Erzeugungen, Abweichungen, Ketten, Aussonderungen, Sackgassen.
        from tests.runner import run_all

        results = run_all(keep=True)
        kept = sum(1 for r in results if r.verdict == "ok")
        print(f"_Bestand aus der Matrix: {kept} von {len(results)} Fällen "
              f"eingespielt._\n")

    db = SessionLocal()
    try:
        findings = invariants.run(db)
        size = invariants.size_of(db)
    finally:
        db.close()
    print(f"_Geprüfter Bestand: {size}._\n")

    print("| # | Invariante | Regel | Verstösse | |")
    print("|---|---|---|---|---|")
    for f in findings:
        n = len(f.violations) + (1 if f.truncated else 0)
        mark = "✅" if f.ok else "❌"
        detail = "–" if f.ok else f"{n}{'+' if f.truncated else ''}"
        print(f"| {f.check.key} | {f.check.title} | {f.check.rule} | {detail} | {mark} |")

    bad = [f for f in findings if not f.ok]
    print()
    print(f"**{len(findings)} Invarianten · {len(findings) - len(bad)} erfüllt · "
          f"{len(bad)} verletzt**")
    for f in bad:
        print(f"\n### {f.check.key} — {f.check.title}")
        for v in f.violations:
            print(f"- ❌ {v}")
        if f.truncated:
            print(f"- … weitere (Deckel bei {invariants.LIMIT})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
