"""**Der Vergabe-Katalog für das Frontend — generiert, nicht gespiegelt.**

Zustände und Kanäle stehen in ``domain/vergabe.py``. Das Frontend braucht davon genau
zwei Dinge, die **nicht** mit den Daten mitreisen können: die Liste der **Kanäle** (für
eine Vergabe, die es noch gar nicht gibt) und die Reihenfolge der Zustände.

Ein von Hand gepflegter Spiegel wäre die falsche Antwort auf dieselbe Frage: Stufe 5 des
Ort-Auftrags fügt genau **einen Kanal** hinzu (``plattform``), und ein Spiegel kostete
dann zwei Einträge – wer den zweiten vergisst, sieht es erst in der CI. Hier kostet er
keinen: ein neuer Kanal ist eine Zeile in ``CHANNELS`` und ist damit auch in der
Oberfläche wählbar.

Was mit den Daten reisen **kann**, reist mit ihnen (``state_label``, ``state_tone``,
``next_states`` an der ``AwardResponse``) – nicht hier noch einmal nachgeschlagen.

    cd backend && python -m scripts.dump_vergabe
"""

import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from app.domain import vergabe  # noqa: E402

OUT = (pathlib.Path(__file__).resolve().parents[2]
       / "frontend" / "src" / "lib" / "vergabe-catalog.ts")

HEAD = '''// ⚠ GENERIERT aus backend/app/domain/vergabe.py – NICHT EDITIEREN.
//   Neu erzeugen: cd backend && python -m scripts.dump_vergabe
//
// **Der Zyklus ist eine Quelle, kein Spiegel.** Ein neuer Kanal wird ausschliesslich im
// Backend ergänzt und ist damit auch hier wählbar; die Zustände samt Ampelton kommen von
// selbst mit. Was an einer konkreten Vergabe hängt (Beschriftung, Ton, mögliche
// Handlungen), reist mit **ihren** Daten – hier steht nur, was es ohne sie zu wissen gibt.

/** Ampelton eines Zustands. Die Farbwerte stehen in den Design-Tokens. */
export type AwardTone = 'done' | 'pending' | 'danger';

export interface AwardState {
  value: string;
  label: string;
  tone: AwardTone;
  /** Endgültig – für **diese** Vergabe gibt es keinen Weg mehr. */
  terminal: boolean;
  /** Ab hier ist ein **Zweiter gebunden**; das System rührt nichts mehr an, es meldet. */
  binding: boolean;
  /** Verlangt der Übergang hierher einen Grund? */
  needsReason: boolean;
}

export interface AwardChannel {
  value: string;
  label: string;
  hint: string;
  /** Bringt dieser Kanal von sich aus Angebote? «Selbst bestellt» nicht. */
  offers: boolean;
}

'''


def build() -> str:
    """Der Dateiinhalt – **getrennt vom Schreiben**, damit ein Wächter genau diese
    Zeichenkette vergleichen kann statt sie nachzubauen (wie ``dump_statuses``)."""
    states = [
        {"value": s.key, "label": s.label, "tone": s.tone, "terminal": s.terminal,
         "binding": s.binding, "needsReason": s.needs_reason}
        for s in vergabe.CATALOG
    ]
    channels = [
        {"value": c.key, "label": c.label, "hint": c.hint, "offers": c.offers}
        for c in vergabe.CHANNELS.values()
    ]
    return (
        HEAD
        + "export const AWARD_STATES: readonly AwardState[] = "
        + json.dumps(states, ensure_ascii=False, indent=2) + " as const;\n\n"
        + "export const AWARD_CHANNELS: readonly AwardChannel[] = "
        + json.dumps(channels, ensure_ascii=False, indent=2) + " as const;\n\n"
        + "/** Ein Zustand zu seinem Schlüssel – unbekannt = `undefined`, kein Rückfall. */\n"
        + "export function awardState(value: string): AwardState | undefined {\n"
        + "  return AWARD_STATES.find((s) => s.value === value);\n}\n\n"
        + "/** Ein Kanal zu seinem Schlüssel. */\n"
        + "export function awardChannel(value: string): AwardChannel | undefined {\n"
        + "  return AWARD_CHANNELS.find((c) => c.value === value);\n}\n"
    )


def main() -> None:
    OUT.write_text(build(), encoding="utf-8")
    print(f"Wrote Vergabe-Katalog → {OUT}")


if __name__ == "__main__":
    main()
