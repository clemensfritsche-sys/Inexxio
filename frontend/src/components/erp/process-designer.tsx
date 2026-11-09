'use client';

import { useCallback, useEffect, useState } from 'react';
import {
  Columns2, Grid2x2, Layers, Lock, Percent, Plus, Trash2,
} from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import { api } from '@/lib/api';
import type { ArticleOption, ModuleCatalog, VoucherParty } from '@/types';
import {
  CAPTURE_ICON, VOUCHER_DIRECTION, VOUCHER_ORDER_REF, VOUCHER_ORDER_REF_HINT, VOUCHER_PARTY,
  VOUCHER_TASK, VOUCHER_TASK_HINT, voucherDirection,
  VOUCHER_PRESETS, VOUCHER_PRESET_OPEN, VOUCHER_PRESETS_HINT, VOUCHER_OWNERSHIP, INCOTERMS, type VoucherPresetKey,
  DISPOSAL_MODES, moduleIcon, NEEDS_TARGET,
  SAMPLE_PRESETS, blankModule, moduleTone,
  type DisposalMode, type ModuleDraft, type PointDraft, type PricePreset, type SampleDraft,
  type SampleMode,
} from '@/lib/modules';

/** Symbol je Kurzweg. Die Wörter stehen daneben – ein Anteil hat kein Bild. */
const SAMPLE_ICON: Record<SampleMode, LucideIcon> = {
  all: Layers, half: Columns2, quarter: Grid2x2, free: Percent,
};
import { DRAFT_OBJECT_ID, definitionGraph, type DiagramStep } from '@/lib/process-graph';
import { ProcessColumns } from '@/components/erp/process-columns';
import { ObjId } from '@/components/erp/obj-id';
import { END_BEFORE } from '@/lib/process-status';
import type { RelatedOrder } from '@/types';
import { IconSwitch, Label, inputCls, numericInputProps, numericOnly } from '@/components/erp/controls';
import { InfoHint } from '@/components/erp/hints';
import { Input, Select } from '@/components/form/field';
import { MICRO_LABEL } from '@/components/erp/fields';
import { DefinitionLines, emptyLine } from '@/components/erp/definition-lines';
import { ObjectSelect } from '@/components/erp/object-select';
import type { PlaceRef } from '@/types';
import { RUNTIME_CHOICE } from '@/lib/scan';
import { tell } from '@/lib/notice';
import { useQuery } from '@tanstack/react-query';
import { qk } from '@/lib/queries';

/**
 * **Den Prozess definieren — dieselbe Komponente am Artikel wie im Auftrag** (PROCESS_CORE.md §8).
 *
 * Kein «Hinzufügen»-Knopf, kein Bearbeiten-Modus: ein Klick auf die Palette legt das Modul an,
 * es füllt sich per Autosave; bis die Pflichtangaben stehen, sagt die Karte, was fehlt. Ändern
 * heisst löschen und neu anlegen. Nach der Freigabe ist die Struktur eingefroren (`frozen`):
 * keine Palette, kein Mülleimer, kein Ziehen.
 */
export function ProcessDesigner({ modules, onChange, frozen, readOnlySteps, head, loop,
  parents, onToggleReturn }: {
  modules: ModuleDraft[];
  onChange: (m: ModuleDraft[]) => void;
  frozen?: boolean;
  /** Eingefrorener Stand (freigegebener Artikel/Auftrag) – dann wird nur gezeigt. */
  readOnlySteps?: DiagramStep[];
  /** Slot über dem Start – beim Auftrag die Definition der Einzelinstanzen (der Artikel hat keine). */
  head?: React.ReactNode;
  /** Die Karte «Wiederholen» unter dem Ende – nur im Auftragsentwurf. */
  loop?: React.ReactNode;
  /** Die Quell-Aufträge des Entwurfs (Auftrag §2), vom Server vorausberechnet. */
  parents?: RelatedOrder[];
  /** Ein Klick auf den Quell-Auftrag schaltet seine Rückführung an und aus (§5). */
  onToggleReturn?: (parentObjectId: number) => void;
}) {
  const [drag, setDrag] = useState<number | null>(null);
  // Das zuletzt angelegte Modul startet aufgeklappt – woran gerade gearbeitet wird.
  const [justAdded, setJustAdded] = useState<number | null>(null);

  // Auch der eingefrorene Stand braucht den Katalog (Namen der Erfassungspunkte) – geladen
  // einmal je Sitzung (er ändert sich nur mit einem Deploy).
  const catalog: ModuleCatalog | null = useQuery({
    queryKey: qk.catalog('modules'),
    queryFn: ({ signal }) => api.getModuleCatalog({ signal }),
    staleTime: Infinity,
    meta: { what: 'Modul-Katalog' },
  }).data ?? null;

  // Was ein Modul ist, sagt sein Typ – im Entwurf über den Katalog, gespeichert über die
  // Antwort des Servers; beide bringen Beschriftung, Farbfamilie und «Ausgang?» mit.
  const steps: DiagramStep[] = readOnlySteps
    ?? modules.map((m) => {
      const type = catalog?.modules?.find((x) => x.key === m.moduleType);
      return {
        id: m.id,
        moduleType: m.moduleType,
        label: type?.label ?? m.moduleType,
        tone: type?.tone ?? null,
        terminal: !!type?.terminal,
      };
    });

  function add(moduleType: string) {
    const id = (modules[modules.length - 1]?.id ?? 0) + 1;
    setJustAdded(id);
    onChange([...modules, blankModule(id, moduleType)]);
  }
  function patch(id: number, next: Partial<ModuleDraft>) {
    onChange(modules.map((m) => (m.id === id ? { ...m, ...next } : m)));
  }

  /** Ein Modul an eine andere Stelle ziehen. Die Reihenfolge IST der Prozess. */
  function move(from: number, to: number) {
    if (from === to) return;
    const next = [...modules];
    const [row] = next.splice(from, 1);
    next.splice(to, 0, row);
    onChange(next);
  }

  return (
    <ProcessColumns
      mid={{
        objectId: DRAFT_OBJECT_ID,
        // Der Graph eines Entwurfs ist seine Definition.
        graph: definitionGraph(steps),
        steps,
        mode: 'definition',
        expandedStepId: justAdded,
        endStatus: END_BEFORE,
        head,
        loop,
        onDelete: frozen ? undefined : (id) => onChange(modules.filter((m) => m.id !== id)),
        onReorder: frozen ? undefined : move,
        dragging: drag,
        onDragState: setDrag,
        // Ein Modul zeigt seine Sache in jedem Zustand: derselbe Feldsatz, gesperrt über
        // `fieldset[disabled]`.
        renderStep: (step) => {
          const m = modules.find((x) => x.id === step.id);
          if (!m) return null;
          // Welche Felder ein Modul hat, sagt sein Typ – eine Zuordnung, keine Bedingung.
          const known = m.moduleType in MODULE_FIELDS;
          const Fields = MODULE_FIELDS[m.moduleType];
          if (!known) {
            return (
              <p className="text-xs" style={{ color: 'var(--danger)' }}>
                Modultyp «{m.moduleType}» ist dieser Oberfläche unbekannt.
              </p>
            );
          }
          return (
            <fieldset disabled={frozen}
              style={{ border: 0, padding: 0, margin: 0, minWidth: 0 }}>
              <div className="flex flex-col gap-3">
                {Fields && (
                  <Fields module={m} types={catalog?.capture_types ?? []}
                    onChange={(next) => patch(m.id, next)} />
                )}
              </div>
            </fieldset>
          );
        },
        // Hinter einem Ausgang gibt es nichts mehr anzubieten (`Module.terminal`); die Prüfung
        // bei der Freigabe bleibt das Netz.
        tail: frozen || steps.some((s) => s.terminal)
          ? undefined
          : <Palette catalog={catalog} onPick={add} />,
      }}
      parents={parents}
      onToggleReturn={onToggleReturn}
    />
  );
}

/**
 * **Die Modulauswahl** – dort, wo das nächste Modul hinkäme: ein Symbol je Modultyp in seiner
 * Farbe, der Name klappt beim Hovern auf.
 */
function Palette({ catalog, onPick }: {
  catalog: ModuleCatalog | null; onPick: (key: string) => void;
}) {
  const mods = catalog?.modules ?? [];
  if (!mods.length) return null;
  return (
    <div className="flex flex-wrap justify-center gap-1.5">
      {mods.map((m) => {
        const Icon = moduleIcon(m.key);
        const tone = moduleTone(m.tone);
        return (
          <button
            key={m.key}
            type="button"
            className="ix-palette ix-tuck"
            style={{ background: tone.bg, color: tone.fg, borderColor: tone.border }}
            aria-label={`${m.label} hinzufügen`}
            onClick={() => onPick(m.key)}
          >
            <Icon size={17} />
            <span className="ix-tuck-name">{m.label}</span>
          </button>
        );
      })}
    </div>
  );
}

/**
 * **Aussondern — eine Entscheidung**: gibt es einen Weg zurück (Sperren) oder nicht
 * (Verschrotten)? Den Zustand leitet das Modul ab (`Aussondern.status_after_for`). Keine
 * Erfassungspunkte, keine Stichprobe. Der Grund gehört zum Ablauf, nicht ans Band; ohne ihn
 * lässt sich das Modul nicht anlegen (`Aussondern.clean_config`).
 */
function DisposalFields({ module: m, onChange }: {
  module: ModuleDraft;
  types: { key: string; label: string }[];
  onChange: (next: Partial<ModuleDraft>) => void;
}) {
  return (
    <div className="flex flex-col gap-2">
      <IconSwitch
        value={m.mode}
        onChange={(mode: DisposalMode) => onChange({ mode })}
        options={DISPOSAL_MODES.map((o) => ({
          value: o.value, icon: o.value === 'scrap' ? Trash2 : Lock,
          label: o.label, hint: o.hint,
        }))}
      />
      <Input name="reason" className={inputCls} value={m.reason} maxLength={200}
        placeholder="Grund, z. B. Ausschuss aus der Sichtprüfung"
        aria-label="Grund der Aussonderung"
        onChange={(reason) => onChange({ reason })} />
    </div>
  );
}

/**
 * **Bewegen — wohin?** Das Ziel darf offen bleiben (beim Modellieren steht oft nicht fest, wo
 * Platz sein wird); das Feld sagt dann selbst, was passiert. Eine Nummer wird zum Namen des
 * Halters aufgelöst. Der Scan-Knopf nutzt denselben Dialog wie die Ausführung, mit freiem Lookup.
 */
function MoveFields({ module: m, onChange }: {
  module: ModuleDraft;
  types: { key: string; label: string }[];
  onChange: (next: Partial<ModuleDraft>) => void;
}) {
  const target = m.target.trim();
  // Den gewählten Halter benennen; die Vorschläge holt die Suche.
  const place: PlaceRef | null = useQuery({
    queryKey: qk.catalog('place', target),
    queryFn: ({ signal }) => api.getPlace(Number(target), { signal }),
    enabled: target !== '',
    meta: { what: 'Zielort' },
  }).data ?? null;

  // `PlaceRef` nennt sein Namensfeld `label`; hier wird es zu `name`.
  const findPlaces = useCallback(
    (q: string) => api.searchPlaces(q)
      .then((rows) => rows.map((p) => ({ ...p, name: p.label }))),
    [],
  );

  return (
    <ObjectSelect<PlaceRef & { name: string }>
      // Das Feld nennt seine Sorte, der Scanner dieselbe – die Beschriftung IST die Sorte.
      label="Zielort"
      value={target === '' ? null : Number(target)}
      selected={place ? { ...place, name: place.label } : null}
      find={findPlaces}
      onChange={(nr) => onChange({ target: nr == null ? '' : String(nr) })}
      // «Kein Ziel» ist eine Wahl, keine Lücke: erste Zeile in derselben Liste.
      emptyOption={RUNTIME_CHOICE}
    />
  );
}

/**
 * **Was ein Modultyp ZUSÄTZLICH hat** – eine Zuordnung, keine Bedingung. `null` heisst «kennt
 * ihn, hat nichts zu fragen»; ein fehlender Schlüssel heisst «unbekannt». Ein Wächter hält die
 * Schlüssel mit dem Backend deckungsgleich.
 */
const MODULE_FIELDS: Record<string, React.ComponentType<{
  module: ModuleDraft;
  types: { key: string; label: string }[];
  onChange: (next: Partial<ModuleDraft>) => void;
}> | null> = {
  datenerfassung: ModuleFields,
  aussondern: DisposalFields,
  verbrauch: ConsumptionFields,
  bewegen: MoveFields,
  beleg: MoneyFields,
};

/**
 * **Eine Zeile entfernen** – dasselbe Zeichen wie am Modul: 26-px-Quadrat, nur Warnfarbe.
 * Die Aufrufstellen unterscheidet der Satz im Hover.
 */
function RowDelete({ label, hint, reveal, onClick }: {
  label: string; hint?: string;
  /** Erst beim Hovern (`.ix-rowactions`, auf Touch immer sichtbar). */
  reveal?: boolean; onClick: () => void;
}) {
  return (
    <button type="button" aria-label={label} data-tip={hint}
      className={`flex items-center justify-center rounded flex-none${reveal ? ' ix-rowactions' : ''}`}
      // Eine Zeilenaktion steht am Ende ihrer Zeile.
      style={{ width: 26, height: 26, color: 'var(--danger)', marginLeft: 'auto' }}
      onClick={onClick}>
      <Trash2 size={14} />
    </button>
  );
}

/**
 * **Zahlung — Richtung, Partner, Auftrag.** Die Richtung ist ein Schieber (EIN Modul). Keine
 * Menge, kein Artikel, kein Termin, kein Betrag, kein Steuersatz (hängt an der Sache), keine
 * Vorauszahlungs-Sperre (folgt aus der Zahlungsfrist).
 */
function MoneyFields({ module: m, onChange, search = api.searchPeople }: {
  module: ModuleDraft;
  types: { key: string; label: string }[];
  onChange: (next: Partial<ModuleDraft>) => void;
  /** Woher die Gegenparteien kommen – eine Angabe, kein `if` auf den Modultyp. */
  search?: (q: string, limit?: number) => Promise<{ object_id: number; name: string }[]>;
}) {
  const [known, setKnown] = useState<Record<number, string>>({});

  // Die gewählten Gegenparteien benennen – eine Abfrage je fehlender Nummer.
  useEffect(() => {
    const missing = m.parties.map((r) => r.party).filter((n) => !(n in known));
    if (missing.length === 0) return;
    let stale = false;
    void Promise.all(missing.map((n) => search(String(n), 1)))
      .then((groups) => {
        if (stale) return;
        const found: Record<number, string> = {};
        groups.flat().forEach((o) => { found[o.object_id] = o.name; });
        setKnown((k) => ({ ...k, ...found }));
      })
      .catch(tell('Namen der Datensätze'));
    return () => { stale = true; };
  }, [m.parties, known, search]);

  const find = search;

  return (
    <div className="flex flex-col gap-3">
      <div>
        {/* Kein Label: «Einnahme» ↔ «Ausgabe» sagen selbst, was sie sind. */}
        <IconSwitch
          value={m.direction === 'in' ? 'in' : 'out'}
          onChange={(v) => onChange({ direction: v })}
          options={[
            { value: 'in', icon: VOUCHER_DIRECTION.in.icon,
              label: VOUCHER_DIRECTION.in.label, hint: VOUCHER_DIRECTION.in.hint },
            { value: 'out', icon: VOUCHER_DIRECTION.out.icon,
              label: VOUCHER_DIRECTION.out.label, hint: VOUCHER_DIRECTION.out.hint },
          ]}
        />
      </div>
      <div className="flex flex-col gap-1.5">
        {/* Ein Hinzufüger, kein Auswahlfeld: was man wählt, wandert in die Liste darunter.
            «Leer heisst frei» steht als Zeile in der Liste, solange niemand zugelassen ist. */}
        <ObjectSelect<VoucherParty>
          value={null}
          selected={null}
          find={find}
          scanLabel={VOUCHER_PARTY}
          emptyOption={m.parties.length === 0 ? RUNTIME_CHOICE : undefined}
          placeholder={`${VOUCHER_PARTY} – Nummer oder Name`}
          onChange={(nr, opt) => {
            if (nr === null || m.parties.some((r) => r.party === nr)) return;
            if (opt) setKnown((k) => ({ ...k, [nr]: opt.name }));
            onChange({ parties: [...m.parties, { party: nr, ref: '' }] });
          }}
        />
        {m.parties.map((row) => (
          /* Alles zu einem Partner auf einer Zeile; «Entfernen» beim Hovern, auf Touch immer. */
          <div key={row.party}
            className="ix-row flex items-center gap-2 py-1.5 flex-wrap"
            style={{ borderTop: '1px solid var(--border-1)' }}>
            <ObjId value={row.party} />
            <span className="text-[12.5px] truncate" style={{
              color: 'var(--fg-3)', maxWidth: 180, flex: 'none',
            }}>{known[row.party] ?? ''}</span>
            {/* Die Bestellangabe gibt es nur, wo wir bestellen (`partyRef`). */}
            {voucherDirection(m.direction).partyRef && (
              <Input name="parties.ref" className={inputCls} value={row.ref} maxLength={200} required
                aria-label={VOUCHER_ORDER_REF} placeholder={VOUCHER_ORDER_REF_HINT}
                style={{ flex: '1 1 160px', minWidth: 0 }}
                onChange={(ref) => onChange({
                  parties: m.parties.map((x) => (x.party === row.party
                    ? { ...x, ref } : x)),
                })} />
            )}
            <RowDelete label="Entfernen" hint="Aus der Freigabe nehmen" reveal
              onClick={() => onChange({
                parties: m.parties.filter((x) => x.party !== row.party),
              })} />
          </div>
        ))}
      </div>
      {/* Was ist zu tun? – ein freiwilliger Satz am Modul; leer heisst «gemäss Spezifikation». */}
      <div>
        <Label>{VOUCHER_TASK}</Label>
        <Input name="instruction" className={inputCls} value={m.instruction} maxLength={400}
          aria-label={VOUCHER_TASK} placeholder={VOUCHER_TASK_HINT}
          onChange={(v) => onChange({ instruction: v })} />
      </div>
      <MoneyPresets module={m} onChange={onChange} />
      {voucherDirection(m.direction).weQuote && <PricePresets module={m} onChange={onChange} />}
    </div>
  );
}

/**
 * **Vorgegebene Preise** – je Artikel ein Einzelpreis, netto, in der Hauswährung
 * (`Beleg.PRICES`). Nur bei einer Einnahme: bei einer Ausgabe nennt die Partei den Preis.
 * Was hier steht, steht im Beleg fest; ein Artikel ohne Vorgabe wird in der Offerte bepreist.
 * Den **Steuersatz** gibt es hier nicht – ihn entscheidet die Anschrift.
 */
function PricePresets({ module: m, onChange }: {
  module: ModuleDraft; onChange: (next: Partial<ModuleDraft>) => void;
}) {
  const rows = m.prices;
  const set = (i: number, next: Partial<PricePreset>) =>
    onChange({ prices: rows.map((r, j) => (j === i ? { ...r, ...next } : r)) });
  const find = useCallback(
    (q: string) => api.getArticleOptions({ search: q, limit: 20 }), []);
  return (
    <div className="flex flex-col gap-1.5">
      <span className="inline-flex items-center gap-1.5" style={MICRO_LABEL}>
        Preise
        <InfoHint text="Ein Einzelpreis je Artikel, netto – steht im Beleg fest. Ohne Vorgabe wird der Preis in der Offerte gesetzt. Den Steuersatz bestimmt die Anschrift." />
      </span>
      {rows.map((r, i) => (
        <div key={i} className="flex items-center gap-2" style={{ minWidth: 0 }}>
          <div className="flex-1" style={{ minWidth: 0 }}>
            <ObjectSelect<ArticleOption>
              value={r.article}
              selected={r.article !== null
                ? { object_id: r.article, name: r.name } as ArticleOption : null}
              find={find}
              kind="article"
              scanLabel="Artikel"
              onChange={(nr, opt) => set(i, { article: nr, name: opt?.name ?? '' })}
            />
          </div>
          <div className="flex items-center gap-1.5" style={{ flex: 'none' }}>
            <Input name={`prices.${i}`} className={inputCls} value={r.price} {...numericInputProps}
              aria-label="Einzelpreis, netto" placeholder="Preis"
              style={{ width: 110, textAlign: 'right' }}
              onChange={(v) => set(i, { price: numericOnly(v, { decimals: 2 }) })} />
          </div>
          <RowDelete label="Preis entfernen"
            onClick={() => onChange({ prices: rows.filter((_, j) => j !== i) })} />
        </div>
      ))}
      <button type="button"
        onClick={() => onChange({ prices: [...rows, { article: null, name: '', price: '' }] })}
        className="self-start inline-flex items-center gap-1 text-xs px-2 py-1 rounded-full"
        style={{ border: '1px dashed var(--border-2)', color: 'var(--fg-3)' }}>
        <Plus size={12} /> Preis vorgeben
      </button>
    </div>
  );
}

/**
 * **Vorgaben an den Beleg** – Fristen, Lieferbedingung, Eigentum. Alle freiwillig: was hier
 * steht, gilt für jeden Auftrag aus diesem Prozess und steht im Beleg fest; **leer heisst
 * «wählt der Mensch am Beleg»**. Ob ein Wert gilt, sagt der Server (`Beleg._clean_presets`).
 */
function MoneyPresets({ module: m, onChange }: {
  module: ModuleDraft; onChange: (next: Partial<ModuleDraft>) => void;
}) {
  const set = (key: VoucherPresetKey, value: string) =>
    onChange({ presets: { ...m.presets, [key]: value } });
  const options = (key: VoucherPresetKey) => (key === 'incoterm'
    ? INCOTERMS.map((t) => ({ value: t.key, label: `${t.key} – ${t.label}` }))
    : VOUCHER_OWNERSHIP);
  return (
    <div className="flex flex-col gap-1.5">
      <span className="inline-flex items-center gap-1.5" style={MICRO_LABEL}>
        Vorgaben an den Beleg <InfoHint text={VOUCHER_PRESETS_HINT} />
      </span>
      <div style={{
        display: 'grid', gap: '12px 16px',
        gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 150px), 1fr))',
      }}>
        {VOUCHER_PRESETS.map((p) => (
          <div key={p.key} data-tip={p.hint} style={{ minWidth: 0 }}>
            <Label>{p.label}</Label>
            {p.days ? (
              <div className="flex items-center gap-1.5">
                <Input name={`presets.${p.key}`} className={inputCls} value={m.presets[p.key]} {...numericInputProps}
                  aria-label={p.label} placeholder={VOUCHER_PRESET_OPEN}
                  onChange={(v) => set(p.key, numericOnly(v, { decimals: false }))} />
                <span className="text-xs" style={{ color: 'var(--fg-4)', flex: 'none' }}>Tage</span>
              </div>
            ) : (
              <Select name={`presets.${p.key}`} className={inputCls} value={m.presets[p.key]} aria-label={p.label}
                style={{ color: m.presets[p.key] ? undefined : 'var(--fg-4)' }}
                onChange={(v) => set(p.key, v)}>
                <option value="">{VOUCHER_PRESET_OPEN}</option>
                {options(p.key).map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
              </Select>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

/**
 * **Verbrauch — die Stückliste: Artikel und Menge JE Einzelinstanz.** Dieselbe Komponente
 * wie der Bedarf am Auftragsanfang (`DefinitionLines`), ohne Herkunft und ohne konkrete
 * Stücke – die wählt der Lagerist beim Ausführen. Gerechnet wird beim Erreichen.
 */
function ConsumptionFields({ module: m, onChange }: {
  module: ModuleDraft;
  types: { key: string; label: string }[];
  onChange: (next: Partial<ModuleDraft>) => void;
}) {
  return (
    <DefinitionLines
      perUnit
      lines={m.lines.length ? m.lines : [emptyLine(1)]}
      setLines={(lines) => onChange({ lines })}
    />
  );
}

/**
 * **Die Stichprobe — eine Zeile**: EINE Zahl, der Anteil an der Gesamtmenge (alle · Hälfte ·
 * Viertel · frei, §4.4), mit ausgeschriebenen Wörtern.
 */
function SampleRow({ value, onChange }: {
  value: SampleDraft; onChange: (next: SampleDraft) => void;
}) {
  return (
    // Die Beschriftung steht über den Knöpfen – daneben las sie sich wie eine Option.
    <div className="flex flex-col gap-1">
      <span style={MICRO_LABEL}>Stichprobe</span>
      <div className="flex flex-wrap items-center gap-2">
        <IconSwitch
          value={value.mode}
          onChange={(mode: SampleMode) => onChange({ mode, value: mode === 'free' ? value.value : '' })}
          options={SAMPLE_PRESETS.map((p) => ({
            value: p.value,
            icon: SAMPLE_ICON[p.value],
            label: p.label,
            hint: p.percent
              ? `${p.percent} % aller wartenden Einzelinstanzen`
              : 'Ein frei gewählter Anteil, aufgerundet',
          }))}
        />
        {value.mode === 'free' && (
          <>
            <Input name="sample" className={inputCls} style={{ width: 80 }} value={value.value}
              {...numericInputProps} placeholder="z. B. 10"
              onChange={(v) => onChange({ ...value, value: numericOnly(v) })} />
            <span className="text-xs" style={{ color: 'var(--fg-4)' }}>%</span>
          </>
        )}
      </div>
    </div>
  );
}

/** Die Art eines Erfassungspunktes – Symbol mit dem Namen im Hover. */
function PointIcon({ type, types }: { type: string; types: { key: string; label: string }[] }) {
  const Icon = CAPTURE_ICON[type] ?? CAPTURE_ICON.text;
  return (
    <span className="flex items-center justify-center flex-none rounded"
      style={{ width: 26, height: 26, color: 'var(--fg-3)' }}
      data-tip={types.find((t) => t.key === type)?.label ?? type}>
      <Icon size={14} />
    </span>
  );
}

/** Der Inhalt eines Moduls im Entwurf: seine Erfassungspunkte. Alles Angelegte ist Pflicht. */
function ModuleFields({ module: m, types, onChange }: {
  module: ModuleDraft;
  types: { key: string; label: string }[];
  onChange: (next: Partial<ModuleDraft>) => void;
}) {
  const defaultType = types[0]?.key ?? 'text';
  function setPoint(i: number, p: Partial<PointDraft>) {
    onChange({ points: m.points.map((row, n) => (n === i ? { ...row, ...p } : row)) });
  }

  return (
    <div className="flex flex-col gap-2">
      <SampleRow value={m.sample} onChange={(sample) => onChange({ sample })} />

      <div className="flex flex-col gap-1.5">
        {m.points.map((p, i) => (
          <div key={i} className="flex flex-wrap gap-1.5 items-center">
            {/* Die Art ist das Symbol der Zeile, kein Feld; umentscheiden heisst löschen und neu anlegen. */}
            <PointIcon type={p.type} types={types} />
            <Input name="points.label" className={inputCls} style={{ flex: 1, minWidth: 120 }} value={p.label}
              maxLength={120} placeholder="Erfassungspunkt, z. B. Gratfrei"
              onChange={(label) => setPoint(i, { label })} />
            {p.type === NEEDS_TARGET && (
              <>
                <Input name="points.target" className={inputCls} style={{ width: 76 }} value={p.target ?? ''}
                  {...numericInputProps} placeholder="Soll"
                  onChange={(v) => setPoint(i, { target: numericOnly(v, { decimals: true }) })} />
                <Input name="points.tolerance" className={inputCls} style={{ width: 76 }} value={p.tolerance ?? ''}
                  {...numericInputProps} placeholder="± Tol."
                  onChange={(v) => setPoint(i, { tolerance: numericOnly(v, { decimals: true }) })} />
                {/* Worin gemessen wird – ein freies, kurzes Wort. */}
                <Input name="points.unit" className={inputCls} style={{ width: 62 }} value={p.unit ?? ''}
                  maxLength={8} placeholder="Einheit" data-tip="mm · kg · °C …"
                  onChange={(unit) => setPoint(i, { unit })} />
              </>
            )}
            <RowDelete label="Erfassungspunkt entfernen"
              onClick={() => onChange({ points: m.points.filter((_, n) => n !== i) })} />
          </div>
        ))}
      </div>

      {/* Ein Symbol je Erfassungstyp; Klick legt den Punkt an. */}
      <div className="flex flex-wrap gap-1.5">
        {types.map((t) => {
          const Icon = CAPTURE_ICON[t.key] ?? CAPTURE_ICON.text;
          return (
            <button key={t.key} type="button" className="ix-palette ix-palette-sm ix-tuck"
              aria-label={`${t.label} hinzufügen`}
              onClick={() => onChange({
                points: [...m.points, { label: '', type: t.key || defaultType, target: '',
                                        tolerance: '', unit: '' }],
              })}>
              <Icon size={14} />
              <span className="ix-tuck-name">{t.label}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
