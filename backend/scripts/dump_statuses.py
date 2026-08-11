"""**Der Status-Katalog für das Frontend — generiert, nicht gespiegelt.**

Die Statusliste stand bisher zweimal da: in ``domain/statuses.py`` und, von Hand
nachgepflegt, in ``lib/process-status.ts``. Ein Test verglich beide – er fand ein
Auseinanderlaufen, verhinderte es aber nicht: ein neuer Status kostete zwei Einträge,
und wer den zweiten vergass, sah es erst in der CI.

Jetzt wird die eine Quelle **ausgeschrieben**, genau wie ``api.ts`` aus dem
OpenAPI-Schema entsteht. Ein neuer Status ist eine Zeile in ``CATALOG``; Beschriftung,
Ampelton, Achsen und Bestands-Zugehörigkeit landen hier ohne weiteres Zutun. Die CI
prüft, dass die Datei aktuell ist (derselbe Vergleich wie bei den Typen).

    cd backend && python -m scripts.dump_statuses
"""

import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from app.domain import statuses as st  # noqa: E402

OUT = pathlib.Path(__file__).resolve().parents[2] / "frontend" / "src" / "lib" / "status-catalog.ts"

HEAD = '''// ⚠ GENERIERT aus backend/app/domain/statuses.py – NICHT EDITIEREN.
//   Neu erzeugen: cd backend && python -m scripts.dump_statuses
//
// **Die Statusliste ist eine Quelle, kein Spiegel.** Was hier steht, steht dort – ein
// neuer Status wird ausschliesslich im Backend ergänzt, und Beschriftung, Ampelton,
// Achsen und Bestands-Zugehörigkeit kommen von selbst hier an. Die Symbole liegen
// daneben (`lib/process-status.ts`): ein Symbol ist eine Gestaltungsfrage und kann nicht
// aus dem Fachmodell kommen; fehlt es, greift ein Standard – kein Grund für einen Fehler.

/** Ampelton eines Status. Die konkreten Farbwerte stehen in den Design-Tokens. */
export type StatusTone = 'done' | 'pending' | 'danger';

/** Zählt ein Stück in diesem Zustand zum aktuellen Bestand oder zur Historie? */
export type StockKind = 'live' | 'history';

export interface StatusEntry {
  value: string;
  label: string;
  tone: StatusTone;
  /** Welche Achsen ihn tragen können: unit | order | article. */
  axes: readonly string[];
  /** Nur für Zustände, die ein Stück tragen kann – sonst `null`. */
  stock: StockKind | null;
  /** Darf ein Auftrag ein Stück in diesem Zustand greifen? «Gibt es einen Weg zurück?» */
  selectable: boolean;
}

'''


def _ts(value: object) -> str:
    return json.dumps(value, ensure_ascii=False)


def build() -> str:
    lines = [HEAD]

    lines.append("/** Die Werte – einzeln benannt, damit der Code sie nicht als Text führt. */")
    for s in st.CATALOG:
        const = s.value.upper()
        lines.append(f"export const {const} = {_ts(s.value)};")
    lines.append("")

    lines.append("/** Der Katalog. Reihenfolge = Anzeige-Reihenfolge (Leiste, Legende).*/")
    lines.append("export const STATUS_CATALOG: readonly StatusEntry[] = [")
    for s in st.CATALOG:
        stock = _ts(s.stock) if s.stock else "null"
        lines.append(
            f"  {{ value: {s.value.upper()}, label: {_ts(s.label)}, "
            f"tone: {_ts(s.tone)}, axes: {_ts(list(s.axes))}, stock: {stock}, "
            f"selectable: {_ts(s.selectable)} }},"
        )
    lines.append("];")
    lines.append("")

    lines.append("/** Alle Werte in Anzeige-Reihenfolge. */")
    lines.append("export const STATUS_VALUES: readonly string[] = "
                 "STATUS_CATALOG.map((s) => s.value);")
    lines.append("")
    lines.append("/** Wer welche Werte tragen kann – abgeleitet, keine zweite Liste. */")
    for name, axis in (("UNIT_STATUSES", "unit"), ("ORDER_STATUSES", "order"),
                       ("ARTICLE_STATUSES", "article")):
        lines.append(
            f"export const {name}: readonly string[] = "
            f"STATUS_CATALOG.filter((s) => s.axes.includes({_ts(axis)})).map((s) => s.value);"
        )
    lines.append("")
    lines.append("/** Die festen Rand-Übergänge (PROCESS_CORE.md §4.1). */")
    for name, value in (("START_BEFORE", st.START_BEFORE), ("START_AFTER", st.START_AFTER),
                        ("END_BEFORE", st.END_BEFORE)):
        lines.append(f"export const {name} = {value.upper()};")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    OUT.write_text(build(), encoding="utf-8")
    print(f"Status-Katalog → {OUT}  ({len(st.CATALOG)} Zustände)")


if __name__ == "__main__":
    main()
