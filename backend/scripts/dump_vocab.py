"""**Das Vokabular für das Frontend — generiert, nicht gespiegelt.**

Schlüssel und Wörter, die das Backend festlegt und die Oberfläche schon braucht, bevor eine
Antwort da ist (der Editor, die Symbole, die Wahl im Entwurf). Vorher standen sie von Hand in
``lib/modules.ts`` & Co., und ein Test verglich beide Seiten per Textsuche
(``tests/test_frontend_mirrors.py``). Jetzt wird die eine Quelle ausgeschrieben – wie
``status-catalog.ts`` (``scripts/dump_statuses``) und ``api.ts`` (OpenAPI).

Was die Oberfläche selbst hält (Symbol, Farbwert, Hover-Satz), tippt sie **gegen die
generierten Schlüssel** (``Record<ModuleKey, LucideIcon>``): ein neuer Schlüssel im Backend
ist dann ein Typfehler im Frontend, ein entfernter auch. Die CI prüft, dass die Datei aktuell
ist (derselbe Vergleich wie bei den Typen).

    cd backend && python -m scripts.dump_vocab
"""

import json
import pathlib
import sys
from typing import Any

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from app.domain import capture_types, communication, competences, incoterms, loop  # noqa: E402
from app.domain import modules, policy, timekeeping, voucher  # noqa: E402
from app.models.instance import KINDS  # noqa: E402
from app.schemas.order import DRAFT_OBJECT_ID  # noqa: E402
from app.schemas.process import CapturePoint  # noqa: E402

OUT = pathlib.Path(__file__).resolve().parents[2] / "frontend" / "src" / "lib" / "vocab.ts"

HEAD = """// ⚠ GENERIERT aus backend/app/domain/… – NICHT EDITIEREN.
//   Neu erzeugen: cd backend && python -m scripts.dump_vocab
//
// **Das Vokabular ist eine Quelle, kein Spiegel.** Ein neuer Schlüssel wird ausschliesslich
// im Backend ergänzt. Was die Oberfläche selbst hält (Symbol, Farbwert, Hover-Satz), tippt
// sie gegen die Typen hier (`Record<ModuleKey, …>`) – fehlt ein Eintrag, baut sie nicht.
"""


def _ts(value: object) -> str:
    return json.dumps(value, ensure_ascii=False)


def _list(name: str, doc: str, values: list[Any], type_name: str) -> list[str]:
    return [f"/** {doc} */", f"export const {name} = {_ts(values)} as const;",
            f"export type {type_name} = (typeof {name})[number];", ""]


def _map(name: str, doc: str, values: dict[str, Any], key_type: str = "") -> list[str]:
    lines = [f"/** {doc} */", f"export const {name} = {{"]
    lines += [f"  {_ts(k)}: {_ts(v)}," for k, v in values.items()]
    lines.append("} as const;")
    if key_type:
        lines.append(f"export type {key_type} = keyof typeof {name};")
    return lines + [""]


_TS_TYPES = {"string": "string", "number": "number", "integer": "number", "boolean": "boolean"}


def _interface(model: Any) -> list[str]:
    """Ein Pydantic-Modell als TypeScript-Schnittstelle – nur die einfachen Formen, die es
    hier gibt (Text, Zahl, Ja/Nein, jeweils optional ``null``); alles andere bricht ab."""
    schema = model.model_json_schema()
    required = set(schema.get("required", ()))
    lines = [f"/** `{model.__module__}.{model.__name__}` */",
             f"export interface {model.__name__} {{"]
    for field, spec in schema["properties"].items():
        kinds = [s["type"] for s in spec.get("anyOf", [spec])]
        ts = " | ".join(_TS_TYPES[k] if k != "null" else "null" for k in kinds)
        lines.append(f"  {field}{'' if field in required else '?'}: {ts};")
    return lines + ["}", ""]


def build() -> str:
    beleg = modules.MODULES[modules.BELEG]
    lines = [HEAD]
    lines += _list("INSTANCE_KINDS", "Instanz-Arten (`models/instance.KINDS`).",
                   list(KINDS), "InstanceKind")
    lines += _list("MODULE_KEYS", "Die Prozessschrittmodule (`domain/modules.KEYS`).",
                   list(modules.KEYS), "ModuleKey")
    lines += _map("MODULE_TONES", "Die Farbfamilie je Modul (`Module.tone`).", modules.TONES)
    lines.append("export type ModuleTone = (typeof MODULE_TONES)[ModuleKey];\n")
    lines += _list("COMPETENCES", "Die Kompetenzen – eine Liste (`domain/competences`).",
                   list(competences.COMPETENCES), "Competence")
    lines += _map("MODULE_COMPETENCES", "Die Vorgabe je Modul (`Module.competence`), am Schritt "
                  "tauschbar.", {k: m.competence for k, m in modules.MODULES.items()})
    lines += _list("CAPTURE_KEYS", "Erfassungspunkt-Typen (`domain/capture_types.KEYS`).",
                   list(capture_types.KEYS), "CaptureKey")
    lines += _map("DISPOSAL_ACTIONS", "Aussondern: Ausprägung → Verb (`Aussondern.ACTIONS`).",
                  modules.Aussondern.ACTIONS, "DisposalMode")
    lines += _map("VOUCHER_DIRECTIONS", "Die Richtungen eines Geldvorgangs (`voucher.DIRECTIONS`)"
                  " – `weQuote`: wir nennen den Preis (`quoted_by`).", {
                      k: {"label": d.label, "hint": d.hint, "partyRef": d.party_ref,
                          "weQuote": d.quoted_by == voucher.BY_US}
                      for k, d in voucher.DIRECTIONS.items()}, "VoucherDirectionKey")
    lines.append("/** Die Gegenpartei – in beiden Richtungen gleich (`voucher.PARTY`). */")
    lines.append(f"export const VOUCHER_PARTY = {_ts(voucher.PARTY)};\n")
    stages = [*voucher.STAGES, voucher.DONE, voucher.CANCELLED]
    lines += _map("VOUCHER_STAGE", "Stufen und Ausgänge eines Geldvorgangs (`voucher.STAGES`, "
                  "`DONE`, `CANCELLED`) – Schlüssel, keine Wörter.", {s: s for s in stages},
                  "VoucherStageKey")
    lines += _map("VOUCHER_STATES", "Der Stand eines Belegs – Karte und Zahlungsliste "
                  "(`voucher.STATES`): Schlüssel → Wort.",
                  {k: word for k, (word, _tone) in voucher.STATES.items()}, "VoucherStateKey")
    lines += _map("QUOTE_STATE","Zustände einer Angebotszeile (`voucher.ASKED` …).", {
        "asked": voucher.ASKED, "quoted": voucher.QUOTED, "declined": voucher.DECLINED,
        "chosen": voucher.CHOSEN})
    lines += _map("VOUCHER_PRESET_LABELS", "Was das Modul dem Beleg vorgeben darf "
                  "(`Beleg.PRESETS` / `PRESET_LABELS`), in dieser Reihenfolge.",
                  {k: beleg.PRESET_LABELS[k] for k in beleg.PRESETS}, "VoucherPresetKey")
    lines += _list("VOUCHER_OWNERSHIP", "Wem die Stücke danach gehören (`voucher.OWNERSHIP`).",
                   [{"value": v, "label": w} for v, w in voucher.OWNERSHIP], "VoucherOwnership")
    lines += _list("INCOTERMS", "Die Klauseln der Incoterms 2020 (`incoterms.INCOTERMS`).",
                   [{"key": t.key, "label": t.label} for t in incoterms.INCOTERMS], "Incoterm")
    lines += _map("DELIVERY_LABELS", "Versandarten einer E-Mail (`communication.DELIVERIES`).",
                  communication.DELIVERIES, "DeliveryKey")
    kinds = list(dict.fromkeys([*(c.kind for c in communication.CHANNELS.values()),
                                communication.channel(communication.company(1)).kind]))
    lines += _list("CHANNEL_KINDS", "Arten eines Kanals (`communication.CHANNELS` + Postfach).",
                   kinds, "ChannelKind")
    icons = list(dict.fromkeys([*(a.icon for a in timekeeping.ARTS),
                                *(h[2] for h in timekeeping.HINTS.values())]))
    lines += _list("TIME_ICON_NAMES", "Lucide-Namen der Zeiterfassung (`timekeeping.ARTS`, "
                   "`HINTS`).", icons, "TimeIconName")
    lines += _map("LOOP_EVERY", "Takte der Wiederholung (`loop.EVERY`).",
                  {k: word for k, (word, _months) in loop.EVERY.items()}, "LoopEvery")
    lines += _map("LOOP_TAKES", "Was eine Wiederholung je Zeile nimmt (`loop.TAKES`).",
                  loop.TAKES, "LoopTake")
    lines += _list("ROLES", "Die Rollen – die Rolle ist der Zugang (`policy.ROLES`).",
                   list(policy.ROLES), "Role")
    lines += _list("STAFF_ROLES", "Wer ins ERP darf (`policy.STAFF_ROLES`) – gefragt nur über "
                   "`record-status.isStaff`.", list(policy.STAFF_ROLES), "StaffRole")
    lines.append("/** Wie ein Entwurf im Prozessbild heisst (`schemas/order.DRAFT_OBJECT_ID`). */")
    lines.append(f"export const DRAFT_OBJECT_ID = {_ts(DRAFT_OBJECT_ID)};\n")
    lines += _interface(CapturePoint)
    lines += [
        "/** Ein Eintrag einer Tabelle zu einem Schlüssel, der von aussen kommt (Antwort, Entwurf)",
        " *  – `undefined`, wenn es ihn nicht gibt (auch nicht über den Prototyp). */",
        "export function lookup<K extends string, V>(table: Readonly<Record<K, V>>,",
        "                                            key: string | null | undefined): V | undefined {",
        "  return key != null && Object.prototype.hasOwnProperty.call(table, key)",
        "    ? table[key as K] : undefined;",
        "}",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    OUT.write_text(build(), encoding="utf-8")
    print(f"Vokabular → {OUT}")


if __name__ == "__main__":
    main()
