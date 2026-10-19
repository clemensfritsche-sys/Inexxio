'use client';

import { useCallback, useEffect, useState } from 'react';
import {
  Columns2, Grid2x2, Layers, Lock, Percent, Trash2,
} from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import { api } from '@/lib/api';
import type { ModuleCatalog, VoucherParty } from '@/types';
import {
  CAPTURE_ICON, VOUCHER_DIRECTION, VOUCHER_ORDER_REF, VOUCHER_ORDER_REF_HINT, VOUCHER_PARTY,
  VOUCHER_TASK, VOUCHER_TASK_HINT, voucherDirection,
  DISPOSAL_MODES, moduleIcon, NEEDS_TARGET,
  SAMPLE_PRESETS, blankModule, moduleTone,
  type DisposalMode, type ModuleDraft, type PointDraft, type SampleDraft, type SampleMode,
} from '@/lib/modules';

/** Symbol je Kurzweg. Die Wörter stehen daneben – ein Anteil hat kein Bild (#636). */
const SAMPLE_ICON: Record<SampleMode, LucideIcon> = {
  all: Layers, half: Columns2, quarter: Grid2x2, free: Percent,
};
import {
  DRAFT_OBJECT_ID, definitionGraph, type DiagramStep,
} from '@/components/erp/process-diagram';
import { ProcessColumns } from '@/components/erp/process-columns';
import { ObjId } from '@/components/erp/obj-id';
import { END_BEFORE } from '@/lib/process-status';
import type { RelatedOrder } from '@/types';
import {
  IconSwitch, Label, MICRO_LABEL, inputCls, numericInputProps, numericOnly,
} from '@/components/erp/fields';
import { DefinitionLines, emptyLine } from '@/components/erp/definition-lines';
import { ObjectSelect } from '@/components/erp/object-select';
import type { PlaceRef } from '@/types';
import { RUNTIME_CHOICE } from '@/lib/scan';

/**
 * **Den Prozess definieren — dieselbe Komponente am Artikel wie im Auftrag.**
 *
 * Beide Orte definieren denselben Prozess (PROCESS_CORE.md §8): am Artikel als Vorlage,
 * im Auftrag als das, was gleich läuft. Zwei Editoren dafür wären zwei Stände, und sie
 * liefen garantiert auseinander.
 *
 * **Kein «Hinzufügen»-Knopf und kein Bearbeiten-Modus.** Ein Klick auf die Palette legt
 * das Modul an; es steht ab dem ersten Moment im Fluss und füllt sich, während man tippt
 * (Autosave). Vollständig ist es, wenn seine Pflichtangaben stehen – bis dahin sagt die
 * Karte, was fehlt, und die Freigabe verweigert. Ändern heisst löschen und neu anlegen;
 * dafür gibt es den Mülleimer, keinen zweiten Weg.
 *
 * **Nach der Freigabe ist die Struktur eingefroren** (`frozen`): keine Palette, kein
 * Mülleimer, kein Ziehen. Das ist keine bewachte Regel, sondern ein fehlendes Bedienelement –
 * einen Endpunkt, der eine freigegebene Definition ändert, gibt es ohnehin nicht.
 */
export function ProcessDesigner({ modules, onChange, frozen, readOnlySteps, head,
  parents, onToggleReturn }: {
  modules: ModuleDraft[];
  onChange: (m: ModuleDraft[]) => void;
  frozen?: boolean;
  /** Eingefrorener Stand (freigegebener Artikel/Auftrag) – dann wird nur gezeigt. */
  readOnlySteps?: DiagramStep[];
  /** Slot über dem Start – beim Auftrag die Definition der Einzelinstanzen. Der Artikel
   *  hat keine, und ein Diagramm, das sie voraussetzt, wäre dort nicht wiederverwendbar. */
  head?: React.ReactNode;
  /**
   * **Die Quell-Aufträge des Entwurfs** (Auftrag §2) – vom Server vorausberechnet, mit
   * der Abzweigung, die entstehen würde. Ein Artikel hat keine; dann steht hier nur der
   * Prozess, wie bisher.
   */
  parents?: RelatedOrder[];
  /** Ein Klick auf den Quell-Auftrag schaltet seine Rückführung an und aus (§5). */
  onToggleReturn?: (parentObjectId: number) => void;
}) {
  const [catalog, setCatalog] = useState<ModuleCatalog | null>(null);
  const [drag, setDrag] = useState<number | null>(null);
  // **Das zuletzt angelegte Modul startet aufgeklappt** (#696): es ist das, woran gerade
  // gearbeitet wird – die Entsprechung zum «aktiven» Modul im laufenden Auftrag. Alle
  // übrigen sind zu; ihr Kopf klappt sie auf.
  const [justAdded, setJustAdded] = useState<number | null>(null);

  // **Auch der eingefrorene Stand braucht den Katalog** (#771): die Felder nennen ihre
  // Erfassungspunkte beim Namen. Die Palette hängt an `frozen`, nicht am Katalog.
  useEffect(() => {
    let dead = false;
    api.getModuleCatalog()
      .then((c) => { if (!dead) setCatalog(c); })
      .catch(() => { /* ohne Katalog bleibt die Palette leer – kein erfundener Typ */ });
    return () => { dead = true; };
  }, []);

  // **Was ein Modul ist, sagt sein Typ** – im Entwurf über den Katalog, gespeichert über
  // die Antwort des Servers. Beides dieselbe Registry, nur zwei Wege dorthin; **beide**
  // bringen Beschriftung, Farbfamilie und «Ausgang?» mit, damit keine Ansicht sie
  // nachschlagen muss und keine sie vergessen kann.
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
        // **Der Graph eines Entwurfs ist seine Definition** – hier steht keine
        // Prozesslogik, sondern die Liste, die daneben bearbeitet wird.
        graph: definitionGraph(steps),
        steps,
        mode: 'definition',
        expandedStepId: justAdded,
        endStatus: END_BEFORE,
        head,
        onDelete: frozen ? undefined : (id) => onChange(modules.filter((m) => m.id !== id)),
        onReorder: frozen ? undefined : move,
        dragging: drag,
        onDragState: setDrag,
        // **Ein Modul zeigt seine Sache in JEDEM Zustand** (#771): derselbe Feldsatz, im
        // freigegebenen Prozess gesperrt über `fieldset[disabled]` – kein zweiter zum Lesen.
        renderStep: (step) => {
          const m = modules.find((x) => x.id === step.id);
          if (!m) return null;
          // **Welche Felder ein Modul hat, sagt sein Typ** – die Zuordnung steht hier,
          // nicht als Bedingung im Rumpf. Ein neuer Typ ist ein Eintrag, kein Eingriff.
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
        // **Hinter einem Ausgang gibt es nichts mehr anzubieten** (`Module.terminal`) – die
        // freundliche Hälfte der Regel; die Prüfung bei der Freigabe bleibt das Netz.
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
 * **Die Modulauswahl — dort, wo das nächste Modul hinkäme.**
 *
 * Ein Symbol je Modultyp, in seiner Farbe; der Name klappt beim Hovern daneben auf.
 * Dieselbe Interaktion wie die Mengeneinheit am Artikel (`IconSwitch labelActiveOnly`):
 * man sieht die Auswahl auf einen Blick, ohne dass Wörter um Aufmerksamkeit ringen –
 * nur ist dies keine Wahl zwischen Werten, sondern ein Griff in den Baukasten.
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
 * **Aussondern — eine Entscheidung, sonst nichts.**
 *
 * Verschrotten und Sperren tun dasselbe: das Stück verlässt den Auftrag. Der einzige
 * Unterschied ist, **ob es einen Weg zurück gibt** – und genau das steht hier. Es ist
 * kein Status-Dropdown: der Anwender wählt, was passieren soll, den Zustand leitet das
 * Modul ab (`Aussondern.status_after_for`).
 *
 * Keine Erfassungspunkte, keine Stichprobe: was ankommt, wird ausgesondert.
 *
 * **Der Grund gehört hierher, nicht ans Band.** Warum an dieser Stelle ausgesondert wird,
 * ist eine Eigenschaft des Ablaufs und lautet bei jedem Stück gleich – am Band wäre es
 * ein Feld, das immer dasselbe aufnimmt. Ohne ihn lässt sich das Modul nicht anlegen
 * (`Aussondern.clean_config`); die Meldung hier ist die Bedienung, die Regel steht dort.
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
      <input className={inputCls} value={m.reason} maxLength={200}
        placeholder="Grund, z. B. Ausschuss aus der Sichtprüfung"
        aria-label="Grund der Aussonderung"
        onChange={(e) => onChange({ reason: e.target.value })} />
    </div>
  );
}

/**
 * **Bewegen — eine Frage: wohin?**
 *
 * Und sie darf **offen bleiben**. Das ist der einzige Unterschied zu jedem anderen
 * Pflichtfeld im Editor, und er ist fachlich: beim Modellieren steht oft nicht fest, wo
 * in drei Wochen Platz sein wird. Eine Vorlage, die dann trotzdem ein Regal nennt, ist
 * beim zweiten Durchlauf falsch — und zwar stillschweigend.
 *
 * Damit «leer» nicht wie «vergessen» aussieht, sagt das Feld selbst, was dann passiert.
 * Steht eine Nummer da, wird sie **aufgelöst**: man sieht den Namen des Halters, nicht
 * nur seine Ziffern — sonst prüft niemand nach, ob es das richtige Regal ist.
 *
 * Der Scan-Knopf ist die Abkürzung dafür: am Regal steht man ohnehin, und sein Etikett
 * trägt die Nummer. Er nutzt denselben Dialog wie die Ausführung, nur mit einem freien
 * Lookup statt einer Verifikation.
 */
function MoveFields({ module: m, onChange }: {
  module: ModuleDraft;
  types: { key: string; label: string }[];
  onChange: (next: Partial<ModuleDraft>) => void;
}) {
  const [place, setPlace] = useState<PlaceRef | null>(null);
  const target = m.target.trim();

  // Den **gewählten** Halter benennen, damit im Feld sein Name steht und nicht seine
  // Ziffern. Nur diesen einen – die Vorschläge holt die Suche, wenn getippt wird.
  useEffect(() => {
    if (target === '') { setPlace(null); return; }
    let stale = false;
    api.getPlace(Number(target))
      .then((p) => { if (!stale) setPlace(p); })
      .catch(() => { if (!stale) setPlace(null); });
    return () => { stale = true; };
  }, [target]);

  // `PlaceRef` nennt sein Namensfeld `label`; hier wird es zu `name` – ein Mapping an der
  // Stelle, an der der Unterschied entsteht, statt einer zweiten Feld-Konvention.
  const findPlaces = useCallback(
    (q: string) => api.searchPlaces(q)
      .then((rows) => rows.map((p) => ({ ...p, name: p.label })))
      .catch(() => []),
    [],
  );

  return (
    <ObjectSelect<PlaceRef & { name: string }>
      // **Das Feld nennt seine Sorte, der Scanner nennt dieselbe** – im Feld als
      // Beschriftung, im Dialog als Zeile über der Suchleiste. Ohne sie stünde nur
      // «Nummer oder Name» da, und im Vollbild-Dialog bliebe nach dem ersten Zeichen
      // gar nichts mehr, das sagt, wonach gesucht wird. `scanLabel` ist damit
      // überflüssig geworden: die Beschriftung IST die Sorte.
      label="Zielort"
      value={target === '' ? null : Number(target)}
      selected={place ? { ...place, name: place.label } : null}
      find={findPlaces}
      onChange={(nr) => onChange({ target: nr == null ? '' : String(nr) })}
      // **«Kein Ziel» ist eine Wahl, keine Lücke** (#734–#736): sie steht als erste Zeile
      // in derselben Liste und im Feld, sobald sie gilt. Vorher stand dieselbe Aussage an
      // drei Stellen – im Platzhalter, in einem Erklärsatz darunter und in einem X-Knopf
      // daneben – und an keiner davon konnte man sie wählen.
      emptyOption={RUNTIME_CHOICE}
    />
  );
}

/**
 * **Was ein Modultyp ZUSÄTZLICH hat.** Eine Zuordnung, keine Bedingung – und jeder Typ
 * steht darin, auch der mit `null`: die Liste beantwortet «kennt die Oberfläche diesen
 * Typ?», und ein fehlender Schlüssel ist die Antwort «nein».
 *
 * **`null` heisst «kennt ihn, hat aber nichts zu fragen».** Es gibt heute keinen solchen
 * Typ mehr – der Wert bleibt trotzdem erlaubt: ein **fehlender** Schlüssel wäre die
 * Antwort «diesen Typ kenne ich nicht», und die Karte sagte das dann auch. Ein Wächter
 * hält die Schlüssel mit dem Backend deckungsgleich.
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
 * **Eine Zeile entfernen — dasselbe Zeichen wie am Modul selbst** (#844): ein 26-px-
 * Quadrat, kein Rahmen, keine Fläche, allein die Warnfarbe. Was die Aufrufstellen
 * unterscheidet, ist der Satz im Hover.
 */
function RowDelete({ label, hint, reveal, onClick }: {
  label: string; hint?: string;
  /** **Erst beim Hovern** (#832, `.ix-rowactions`, auf Touch immer sichtbar). */
  reveal?: boolean; onClick: () => void;
}) {
  return (
    <button type="button" aria-label={label} data-tip={hint}
      className={`flex items-center justify-center rounded flex-none${reveal ? ' ix-rowactions' : ''}`}
      // Eine Zeilenaktion steht am Ende ihrer Zeile (#995).
      style={{ width: 26, height: 26, color: 'var(--danger)', marginLeft: 'auto' }}
      onClick={onClick}>
      <Trash2 size={14} />
    </button>
  );
}

/**
 * **Zahlung — Richtung, Partner, Auftrag.** Die Richtung (*kommt Geld herein oder geht es
 * hinaus?*) ist ein Schieber, keine zweite Kachel: es ist EIN Modul. **Keine Menge, kein
 * Artikel, kein Termin, kein Betrag** (das sagen die Einzelinstanzen bzw. die Ausführung),
 * **kein Steuersatz** (#851, er hängt an der Sache) und **keine Vorauszahlungs-Sperre**
 * (#854, sie folgt aus der Zahlungsfrist auf dem Beleg).
 */
function MoneyFields({ module: m, onChange, search = api.searchVoucherParties }: {
  module: ModuleDraft;
  types: { key: string; label: string }[];
  onChange: (next: Partial<ModuleDraft>) => void;
  /** Woher die Gegenparteien kommen – eine Angabe, kein `if` auf den Modultyp. */
  search?: (q: string, limit?: number) => Promise<{ object_id: number; name: string }[]>;
}) {
  const [known, setKnown] = useState<Record<number, string>>({});

  // Die gewählten Gegenparteien benennen – sonst stünden dort nur Ziffern. Eine Abfrage
  // je fehlender Nummer, nicht je Rendern.
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
      .catch(() => {});
    return () => { stale = true; };
  }, [m.parties, known, search]);

  const find = useCallback((q: string) => search(q).catch(() => []), [search]);

  return (
    <div className="flex flex-col gap-3">
      <div>
        {/* Kein Label darüber (#816): «Einnahme» ↔ «Ausgabe» sagen selbst, was sie sind. */}
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
        {/* **Ein Hinzufüger, kein Auswahlfeld**: was man wählt, wandert in die Liste darunter.
            «Leer heisst frei» steht als Zeile in der Liste (#786), solange niemand
            zugelassen ist; «Partner» steht im Platzhalter (#843), im Scan-Vollbild als
            Beschriftung (`scanLabel`). */}
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
          /* Alles zu einem Partner auf einer Zeile (#833); «Entfernen» erscheint beim
             Hovern, auf Touch immer (#832). */
          <div key={row.party}
            className="ix-row flex items-center gap-2 py-1.5 flex-wrap"
            style={{ borderTop: '1px solid var(--border-1)' }}>
            <ObjId value={row.party} />
            <span className="text-[12.5px] truncate" style={{
              color: 'var(--fg-3)', maxWidth: 180, flex: 'none',
            }}>{known[row.party] ?? ''}</span>
            {/* Die Bestellangabe gibt es nur, wo wir bestellen (`partyRef`). */}
            {voucherDirection(m.direction).partyRef && (
              <input className={inputCls} value={row.ref} maxLength={200} required
                aria-label={VOUCHER_ORDER_REF} placeholder={VOUCHER_ORDER_REF_HINT}
                style={{ flex: '1 1 160px', minWidth: 0 }}
                onChange={(e) => onChange({
                  parties: m.parties.map((x) => (x.party === row.party
                    ? { ...x, ref: e.target.value } : x)),
                })} />
            )}
            <RowDelete label="Entfernen" hint="Aus der Freigabe nehmen" reveal
              onClick={() => onChange({
                parties: m.parties.filter((x) => x.party !== row.party),
              })} />
          </div>
        ))}
      </div>
      {/* **Was ist zu tun?** – ein Satz am Modul, freiwillig, in beiden Richtungen: in der
          Definition wird vorher festgelegt, was zu tun ist. Leer heisst «gemäss
          Spezifikation». */}
      <div>
        <Label>{VOUCHER_TASK}</Label>
        <input className={inputCls} value={m.instruction} maxLength={400}
          aria-label={VOUCHER_TASK} placeholder={VOUCHER_TASK_HINT}
          onChange={(e) => onChange({ instruction: e.target.value })} />
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
 * **Die Stichprobe — eine Zeile, keine Maske.**
 *
 * EINE Zahl: der Anteil an der Gesamtmenge (alle · Hälfte · Viertel · frei, §4.4). Die
 * Wörter stehen ausgeschrieben da – ein Anteil hat kein Bild (#618/#636).
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
            <input className={inputCls} style={{ width: 80 }} value={value.value}
              {...numericInputProps} placeholder="z. B. 10"
              onChange={(e) => onChange({ ...value, value: numericOnly(e.target.value) })} />
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

/**
 * Der Inhalt eines Moduls im Entwurf: seine Erfassungspunkte.
 *
 * Es gibt **kein** «Pflicht ja/nein» mehr: alles, was angelegt ist, ist Pflicht. Ein
 * Schalter dafür wäre die Frage, warum man einen Erfassungspunkt anlegt, den niemand
 * ausfüllen muss – und jeder ausgeschaltete Punkt eine Lücke, die erst später auffällt.
 */
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
            {/* **Die Art ist das Symbol der Zeile, kein Feld** (Testnotiz #683). Gewählt
                wird sie unten mit der Palette – ein Auswahlfeld daneben wäre der zweite
                Weg zur selben Entscheidung. Umentscheiden heisst löschen und neu
                anlegen, wie beim Modul selbst. */}
            <PointIcon type={p.type} types={types} />
            <input className={inputCls} style={{ flex: 1, minWidth: 120 }} value={p.label}
              maxLength={120} placeholder="Erfassungspunkt, z. B. Gratfrei"
              onChange={(e) => setPoint(i, { label: e.target.value })} />
            {p.type === NEEDS_TARGET && (
              <>
                <input className={inputCls} style={{ width: 76 }} value={p.target ?? ''}
                  {...numericInputProps} placeholder="Soll"
                  onChange={(e) => setPoint(i, { target: numericOnly(e.target.value, { decimals: true }) })} />
                <input className={inputCls} style={{ width: 76 }} value={p.tolerance ?? ''}
                  {...numericInputProps} placeholder="± Tol."
                  onChange={(e) => setPoint(i, { tolerance: numericOnly(e.target.value, { decimals: true }) })} />
                {/* Worin gemessen wird – ein freies, kurzes Wort (#707). */}
                <input className={inputCls} style={{ width: 62 }} value={p.unit ?? ''}
                  maxLength={8} placeholder="Einheit" data-tip="mm · kg · °C …"
                  onChange={(e) => setPoint(i, { unit: e.target.value })} />
              </>
            )}
            <RowDelete label="Erfassungspunkt entfernen"
              onClick={() => onChange({ points: m.points.filter((_, n) => n !== i) })} />
          </div>
        ))}
      </div>

      {/* Ein Symbol je Erfassungstyp – dieselbe Geste wie die Modulauswahl, eine Ebene
          tiefer. Klick legt den Punkt an; ausgefüllt wird er dort, wo er steht. */}
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
