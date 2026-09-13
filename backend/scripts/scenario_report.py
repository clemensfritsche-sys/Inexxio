"""Die Szenariomatrix fahren und die **Soll/Ist-Tabelle** schreiben.

    python -m scripts.scenario_report            # → TEST_REPORT-Fragment auf stdout
    python -m scripts.scenario_report --only S40,S47

Bewusst kein «alles grün»: jede Zeile nennt Soll **und** Ist, und ein Fall, der nicht
lief, steht als «nicht geprüft» da – nicht als bestanden.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tests.runner import run_all                               # noqa: E402

_MARK = {"ok": "✅", "abweichung": "❌", "fehler": "💥", "unmöglich": "⊘",
         "offen": "🟠", "behoben": "🎉"}


def _short(value, limit: int = 46) -> str:
    text = repr(value)
    return text if len(text) <= limit else text[: limit - 1] + "…"


def main() -> int:
    only = None
    for arg in sys.argv[1:]:
        if arg.startswith("--only"):
            only = set(arg.split("=", 1)[1].split(",")) if "=" in arg else None
    results = run_all(only)

    print("| # | Fall | A · B · C · D · E · F | Soll | Ist | |")
    print("|---|---|---|---|---|---|")
    for r in results:
        a = r.case.axes
        axes = " · ".join(a.get(k, "–") for k in "ABCDEF")
        soll = "<br>".join(f"`{k}` = {_short(v)}" for k, v in r.case.soll.items())
        if r.verdict == "fehler":
            ist = f"**{r.error}**"
        elif r.verdict == "unmöglich":
            ist = f"_{r.case.impossible}_"
        else:
            ist = "<br>".join(
                ("**" if r.ist.get(k, "<fehlt>") != v else "")
                + f"`{k}` = {_short(r.ist.get(k, '<fehlt>'))}"
                + ("**" if r.ist.get(k, "<fehlt>") != v else "")
                for k, v in r.case.soll.items()
            )
        print(f"| {r.case.id} | {r.case.title} | {axes} | {soll} | {ist} | "
              f"{_MARK[r.verdict]} |")

    bad = [r for r in results if r.verdict in ("abweichung", "fehler", "offen",
                                              "behoben")]
    print()
    offen = [r for r in results if r.verdict == "offen"]
    print(f"**{len(results)} Fälle · {len(results) - len(bad)} bestanden · "
          f"{len(offen)} bekannter Befund (🟠, siehe FINDINGS.md) · "
          f"{len(bad) - len(offen)} unerwartet abweichend**")
    for r in bad:
        print(f"\n### {r.case.id} — {r.case.title}")
        if r.case.note:
            print(f"_{r.case.note}_")
        if r.error:
            print(f"- 💥 {r.error}")
        for d in r.diffs:
            print(f"- ❌ {d}")
        # Was der Fall nebenbei gemessen hat – es steht nicht im Soll, hilft aber beim
        # Verstehen (die Meldung selbst, der Verlierer einer Nebenläufigkeit …).
        for k, v in r.ist.items():
            if k not in r.case.soll:
                print(f"- ℹ️ `{k}` = {_short(v, 120)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
