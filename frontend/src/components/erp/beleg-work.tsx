'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import type { CSSProperties, ReactNode } from 'react';
import {
  AlertTriangle, Check, CircleSlash, ClipboardList,
  CreditCard, Eraser, FileText, Loader2, Plus, RotateCcw, Send, Undo2,
  Wallet, X,
} from 'lucide-react';
import { api } from '@/lib/api';
import type {
  TransferInfo, VoucherCorrectable, VoucherEmbed, VoucherParty, VoucherQuoteOut,
  VoucherSide,
} from '@/types';
import { ObjId } from '@/components/erp/obj-id';
import { ObjectSelect } from '@/components/erp/object-select';
import { PayOnline } from '@/components/erp/pay-online';
import {
  Label, MICRO_LABEL, SearchSelect, Segmented, inputCls, numericInputProps, numericOnly,
} from '@/components/erp/fields';
import {
  ACT_H, ActionButton, Amount, FIELD_GAP, LedgerRow, ModuleSection,
} from '@/components/erp/module-ui';
import { VOUCHER_STAGE, QUOTE_STATE } from '@/lib/modules';
import { TONE } from '@/lib/status-tone';
import { useAutosaveSignature } from '@/lib/use-autosave';
import { day, happened, when } from '@/lib/when';

/**
 * **Der Beleg an der Ausführungsstelle — EIN Dokument, das WÄCHST**
 * (`docs/history/2026-09-neuaufbau-zahlungsmodul.md`, PROCESS_CORE §9.15).
 *
 *     Belegkopf → Positionen → Konditionen → Angebote → Fordern → Begleichen
 *
 * Die Ordnung eines Belegs. Er wächst, statt umzuschalten: dieselben Zeilen, ein Zustand
 * weiter – ein späterer PDF-Export ist damit dieselbe Komponente ohne Knöpfe.
 *
 * * **Kein einziges `if` auf die Richtung**: was Einnahme von Ausgabe unterscheidet,
 *   reist fertig mit (`label`, `stages[].label/verb`, `party_word`, `ask_verb`,
 *   `we_quote`, `ref_label`). Diese Datei fragt `may(...)` und zeichnet.
 * * **Was man ändern kann, sieht man** (#922): eine Auszeichnung (`.ix-editable`,
 *   `Editable`) an jedem änderbaren Wert, ohne Layoutwirkung.
 * * **Die Handlung, die weiterbringt, sieht überall gleich aus** (#923, `StageAction`).
 */
type Filled = Omit<VoucherEmbed,
  'stages' | 'entries' | 'allowed' | 'can' | 'quotes' | 'lines'> & {
  stages: NonNullable<VoucherEmbed['stages']>;
  entries: NonNullable<VoucherEmbed['entries']>;
  allowed: NonNullable<VoucherEmbed['allowed']>;
  can: NonNullable<VoucherEmbed['can']>;
  quotes: NonNullable<VoucherEmbed['quotes']>;
  lines: NonNullable<VoucherEmbed['lines']>;
};

type Action = { action: string } & Record<string, unknown>;
type Send = (body: Action) => Promise<unknown> | void;

/**
 * **Anfragen bzw. anbieten** – die Nutzlast entsteht an einer Stelle (`BelegWork`, #941);
 * wer fragt, sagt nur, **wen**. Die Fristen liest der Dienst vom Beleg.
 */
type Ask = (parties?: number[]) => void;

/**
 * **Darf man das hier tun?** – `can` ist Auskunft **und** Tor (`services/voucher`):
 * dieselbe Liste rendert die Knöpfe und weist ab. Das aktive Modul ist nicht die
 * Bedingung – die Geld-Zeilen hängen allein an `can` (#821); nur die Stufen fragen
 * zusätzlich nach `active`.
 */
function may(d: Filled, action: string): boolean {
  return d.can.includes(action);
}

/**
 * **Eine Aussage mitten im Satz beginnt klein** – gesenkt wird genau das erste Zeichen
 * («In 30 Tagen» → «in 30 Tagen»), nie ein Monatsname («12. Sep.»).
 */
function lower(text: string): string {
  return text.charAt(0).toLowerCase() + text.slice(1);
}

/** Das Vorzeichen drehen – die Vorbelegung einer Korrektur bzw. Erstattung. */
function negate(amount: string): string {
  const clean = amount.trim();
  return clean.startsWith('-') ? clean.slice(1) : `-${clean}`;
}

export function BelegWork({
  voucher, busy, active, orderObjectId, stepId, onAction, onPaid, children,
}: {
  voucher: VoucherEmbed;
  busy: boolean;
  /** Ist dieses Modul an der Reihe? Nur die **Stufen** fragen danach – Geld nie (#821). */
  active: boolean;
  orderObjectId: number;
  stepId: number;
  onAction: Send;
  /** Der Auftrag soll neu geladen werden – eine Karten-Zahlung kommt über den Webhook. */
  onPaid: () => void;
  /** Der Inhalt des Moduls selbst (der Abschluss) – **am Ende der Karte** (#829). */
  children?: ReactNode;
}) {
  const d = voucher as Filled;
  const agreed = d.stage !== VOUCHER_STAGE.offer;
  // **Kein Entwurf im Browser** (#985): jeder änderbare Wert wird sofort geschrieben
  // (die Fristen über das Verb `terms`), `ask` liest ihn vom Beleg.
  const onAsk = useCallback<Ask>((parties) => {
    void onAction({
      action: 'ask',
      ...(parties && parties.length ? { parties } : {}),
    });
  }, [onAction]);

  return (
    <div className="flex flex-col" style={{ minWidth: 0 }}>
      <DocHead d={d} busy={busy} orderObjectId={orderObjectId} stepId={stepId}
        onAction={onAction} onAsk={onAsk} />
      <Goods d={d} busy={busy} onAction={onAction} />
      <Terms d={d} busy={busy} onAction={onAction} />
      <Quotes d={d} busy={busy} active={active} onAsk={onAsk} onAction={onAction} />
      {agreed && (
        <Money d={d} busy={busy} orderObjectId={orderObjectId} stepId={stepId}
          onAction={onAction} onPaid={onPaid} />
      )}
      {/* Der Modul-Abschluss steht am Ende (#829), der Storno daneben (#957). */}
      <Footer d={d} busy={busy} onAction={onAction}>{children}</Footer>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// Die Bausteine des Belegs
// ═══════════════════════════════════════════════════════════════════════════════

/**
 * **Ein Wert, den man ändern kann** (#922) – die eine Hülle: sie setzt die Klasse
 * `.ix-editable` (Aussehen in `globals.css`) und sagt, wann sie **nicht** gilt. `as` ist
 * die Form, die der Aufrufer braucht (`<span>` in einer Zeile, `<div>` um ein Feld).
 *
 * **Die Auszeichnung ist deckungsgleich mit dem Bedienelement** (#948): `inline-flex`
 * macht konstruktiv **eine** Box – die Hülle nimmt die Höhe ihres Kindes, das Kind
 * streckt sich auf ihre.
 */
function Editable({ on = true, as: Tag = 'span', style, title, missing, children }: {
  on?: boolean;
  as?: 'span' | 'div';
  style?: CSSProperties;
  title?: string;
  /**
   * **Ein Pflichtwert, der fehlt, sagt es an seiner Stelle** (#964): dieselbe
   * Auszeichnung, warnfarben statt akzentfarben. Die Regel selbst steht im Dienst
   * (`voucher.ask_problem`/`_assert_ask`); dies ist ihre freundliche Hälfte.
   */
  missing?: boolean;
  children: ReactNode;
}) {
  // **Sie darf sich nicht strecken** (#948, #961/#963): in einer Flex-Spalte würde sie auf
  // die volle Breite gezogen. `width: fit-content` (eine definite Quergrösse, CSS Flexbox
  // §8.3) verhindert das – und lässt in einer Zeile die Ausrichtung des Elternteils
  // unberührt (`align-self: start` hätte sie dort nach oben gerückt).
  const box: CSSProperties = Tag === 'span'
    ? { display: 'inline-flex', width: 'fit-content', maxWidth: '100%', ...style }
    // Auch der Block-Fall ist ein Flex-Kasten – sonst wäre die Hülle so hoch wie ihre Zeile.
    : { display: 'flex', ...style };
  return (
    <Tag className={on ? `ix-editable${missing ? ' is-missing' : ''}` : undefined}
      style={box}
      {...(on ? {} : { 'aria-disabled': true as const })}
      {...(on && missing ? { 'aria-invalid': true as const } : {})}
      {...(title ? { 'data-tip': missing ? `${title} – Pflichtangabe` : title } : {})}>
      {children}
    </Tag>
  );
}

/**
 * **Die Handlung, die den Beleg eine Stufe weiterbringt** (#923): volle Breite, Fläche,
 * 42 px, 14 px Schrift – dieselbe Form wie der Modul-Abschluss in `order-detail`.
 */
function StageAction({ icon: Icon, label, disabled, tip, onClick }: {
  icon: typeof Check;
  label: string;
  disabled?: boolean;
  tip?: string;
  onClick: () => void;
}) {
  return (
    <button type="button" className="erp-actbtn erp-actbtn-primary w-full"
      disabled={disabled} style={{ height: ACT_H.stage, fontSize: 14 }}
      {...(tip ? { 'data-tip': tip } : {})} onClick={onClick}>
      <Icon size={16} /> {label}
    </button>
  );
}

/**
 * **Die dominante Handlung, und daneben die leise** (#976): eine nimmt den Platz, alles
 * andere steht als Quadrat daneben. Die Fusszeile der Karte (Abschluss ↔ Storno), der
 * Zuschlag (annehmen ↔ absagen) und das Erfassungsformular sind dieselbe Zeile.
 */
function StageRow({ children, aside }: { children?: ReactNode; aside?: ReactNode }) {
  return (
    <div className="flex items-stretch" style={{ gap: 8, minWidth: 0 }}>
      {children && <div style={{ flex: 1, minWidth: 0 }}>{children}</div>}
      {aside}
    </div>
  );
}

/** Was man an einer Angebotszeile tut, wenn man den Preis nennt – in beiden Richtungen. */
const QUOTE_VERB = 'Offerte erfassen';

/** Die Beschriftung des Betrags an einer Angebotszeile (#1049) – in beiden Richtungen
 *  dieselbe: was der Betrag *ist*, sagt der Abschnitt, in dem er steht. */
const AMOUNT_LABEL = 'Betrag';

/**
 * **Ein Feld auf dem Beleg sieht aus wie der Beleg** (#922): kein Rahmen, keine Fläche –
 * was es von einer gedruckten Zeile unterscheidet, ist allein `.ix-editable`. `inputCls`
 * bleibt richtig, wo man ein **Formular** ausfüllt (Editor, Erfassung einer Geld-Zeile).
 */
const DOC_FIELD: CSSProperties = {
  background: 'transparent', border: 0, outline: 'none', padding: 0,
  font: 'inherit', color: 'inherit',
};

/**
 * **Der gedruckte Wert IST das Bedienelement** (#929/#930/#934/#935): sichtbar ein
 * `<span>` in der Schrift, die dort ohnehin steht, bedienbar ein unsichtbares `<select>`
 * darüber. So bestimmt die **Anzeige** die Breite, nicht die längste Zeile der Liste.
 * Steht der Wert fest, bleibt der Text ohne Auszeichnung.
 *
 * `MIN_PICK` ist eine **Untergrenze** (#942): wo noch nichts dasteht («—»), muss der
 * Wähler trotzdem zu treffen und zu sehen sein.
 */
const MIN_PICK = 44;

function DocPick({ on, value, text, options, face, tip, aria, missing, onChange }: {
  on: boolean;
  value: string;
  /** Was dasteht – der **kurze** Name, nie die Zeile des Auswahlfelds. */
  text: string;
  options: { value: string; label: string }[];
  face?: CSSProperties;
  tip?: string;
  aria: string;
  /** Pflichtangabe und noch leer (#964) – siehe `Editable.missing`. */
  missing?: boolean;
  onChange: (value: string) => void;
}) {
  const shown = <span aria-hidden style={face}>{text}</span>;
  if (!on) return shown;
  // **EINE Box** (#948): Auszeichnung und Bedienelement sitzen auf demselben Element;
  // `inset: 0` deckt exakt die getönte Fläche.
  return (
    <Editable title={tip} missing={missing}
      style={{ position: 'relative', minWidth: MIN_PICK, maxWidth: '100%' }}>
      {shown}
      <select value={value} aria-label={aria}
        onChange={(e) => onChange(e.target.value)}
        style={{ position: 'absolute', inset: 0, width: '100%', height: '100%',
                 opacity: 0, cursor: 'pointer' }}>
        {options.map((o) => (
          <option key={o.value} value={o.value}>{o.label}</option>
        ))}
      </select>
    </Editable>
  );
}

/**
 * **Ein Datensatz auf dem Beleg — dieselbe Form, nur mit Suche** (#928–#930): im
 * Ruhezustand der gedruckte Name mit der Auszeichnung, der Klick macht daraus die Suche
 * (`ObjectSelect`, die eine Bauart für Referenzen).
 */
function DocRef<T extends { object_id: number; name: string }>({
  on, text, placeholder, value, selected, find, face, tip, onChange,
}: {
  on: boolean;
  text: ReactNode;
  placeholder: string;
  value: number | null;
  selected?: T | null;
  find: (query: string) => Promise<T[]>;
  face?: CSSProperties;
  tip?: string;
  onChange: (objectId: number | null, option: T | null) => void;
}) {
  const [open, setOpen] = useState(false);
  // **Wer klickt, will tippen.** Ohne den Sprung in das Feld kostet die Wahl zwei Klicks –
  // der erste öffnet nur, und das sieht aus wie ein Aussetzer.
  const focus = useCallback((node: HTMLDivElement | null) => {
    node?.querySelector('input')?.focus();
  }, []);

  if (!on) return <span style={face}>{text}</span>;
  if (!open) {
    return (
      <Editable title={tip}>
        <button type="button" onClick={() => setOpen(true)}
          style={{ ...DOC_FIELD, ...face, cursor: 'pointer', textAlign: 'left',
                   maxWidth: '100%' }}>
          {text}
        </button>
      </Editable>
    );
  }
  return (
    <div ref={focus} style={{ minWidth: 0 }}>
      <Editable as="div" style={{ minWidth: 170 }}>
        <ObjectSelect<T>
          value={value} selected={selected} placeholder={placeholder} find={find}
          onChange={(n, option) => { setOpen(false); onChange(n, option); }}
        />
      </Editable>
    </div>
  );
}

/**
 * **Eine Liste, die zu gross für eine Aufzählung ist** (#1050) – die dritte Hülle neben
 * `DocPick` (Aufzählung) und `DocRef` (Datensatz): eine Liste von **Belegen**, gesucht auf
 * dem Server (`SearchSelect.search`). **Ohne Kamera**: eine Rechnung zieht keine
 * Objektnummer, es kann für sie kein Etikett geben.
 */
function DocFind({ on, text, value, options, placeholder, emptyOption, face, tip,
                  search, onChange }: {
  on: boolean;
  text: ReactNode;
  value: string;
  /** Nur die **gewählte** Zeile – alles andere kommt aus `search` (#730). */
  options: { value: string; label: string }[];
  placeholder: string;
  emptyOption: string;
  face?: CSSProperties;
  tip?: string;
  search: (query: string) => Promise<{ value: string; label: string }[]>;
  onChange: (value: string) => void;
}) {
  const [open, setOpen] = useState(false);
  // **Wer klickt, will tippen** – dieselbe Zeile wie in `DocRef`: ohne den Sprung ins Feld
  // kostet die Wahl zwei Klicks, und der erste sieht aus wie ein Aussetzer.
  const focus = useCallback((node: HTMLDivElement | null) => {
    node?.querySelector('input')?.focus();
  }, []);

  if (!on) return <span style={face}>{text}</span>;
  if (!open) {
    return (
      <Editable title={tip} style={{ minWidth: MIN_PICK }}>
        <button type="button" onClick={() => setOpen(true)}
          style={{ ...DOC_FIELD, ...face, cursor: 'pointer', textAlign: 'left',
                   maxWidth: '100%' }}>
          {text}
        </button>
      </Editable>
    );
  }
  return (
    <div ref={focus} style={{ minWidth: 0 }}>
      <Editable as="div" style={{ minWidth: 190 }}>
        <SearchSelect value={value} options={options} placeholder={placeholder}
          emptyOption={emptyOption} search={search}
          onChange={(v) => { setOpen(false); onChange(v); }} />
      </Editable>
    </div>
  );
}

/** Eine Pflichtangabe, die fehlt – klein, rot, an ihrer Stelle. Erfunden wird nichts. */
function Missing({ what }: { what: string }) {
  return (
    <span style={{ ...MICRO_LABEL, color: 'var(--danger)' }}>{what} fehlt</span>
  );
}

/**
 * **Eine leise Auskunft — und ihre Blase steht darüber** (#978). Die Blase sitzt über
 * der Mitte ihres Elements; `width: fit-content` hält das Element so breit wie seinen
 * Text (in einer Flex-Spalte wäre es sonst die ganze Zeile).
 */
function Note({ tip, icon: Icon, color, children }: {
  tip?: string | null; icon?: typeof ClipboardList;
  /** Wo die Aussage zugleich der Zustand ist, trägt sie dessen Ton (#1053). */
  color?: string;
  children: ReactNode;
}) {
  return (
    <span className="inline-flex items-center"
      style={{ gap: 6, fontSize: 11.5, color: color ?? 'var(--fg-3)', width: 'fit-content',
               flex: 'none', minWidth: 0 }}
      {...(tip ? { 'data-tip': tip } : {})}>
      {Icon && <Icon size={11} style={{ flex: 'none' }} />}
      {children}
    </span>
  );
}

// ───────────────────────────────────────────────────────────────────────────────
// Der Belegkopf
// ───────────────────────────────────────────────────────────────────────────────

/**
 * **Wie viele Zeilen ein Partei-Block hat** – siehe `Party`: Auswahl (#981) · Rolle ·
 * Name mit Nummer (#940) · z. H. · Anschrift · Lieferadresse (#952) · Kontakt · UID. Jede
 * Zeile steht auf **beiden** Seiten, auch leer – die Symmetrie ist die Aussage (#913).
 */
const PARTY_ROWS = 8;

/**
 * **Der Belegkopf** – beide Parteien, und sonst nichts. **Keine Belegart** (#974/#977):
 * wie weit der Beleg ist, steht als Punkt an jedem Abschnitt. **Der Storno bleibt** –
 * er ist eine Tatsache über dieses Papier. Der offene Betrag steht an der Rechnung (#902).
 */
function DocHead({ d, busy, orderObjectId, stepId, onAction, onAsk }: {
  d: Filled; busy: boolean; orderObjectId: number; stepId: number;
  onAction: Send; onAsk: Ask;
}) {
  return (
    <ModuleSection first>
      <div className="flex flex-col" style={{ gap: 14, minWidth: 0 }}>
        {/* Zeit zuerst, dann was passiert ist (#1052, `lib/when.happened`). */}
        {d.cancelled_on && (() => {
          const w = happened(d.cancelled_on, d.cancelled_word);
          return (
            <span style={{ ...MICRO_LABEL, color: 'var(--danger)', width: 'fit-content' }}
              data-tip={w.title}>{w.text}</span>
          );
        })()}
        <Correction d={d} orderObjectId={orderObjectId} stepId={stepId}
          onAction={onAction} />
        <Parties d={d} busy={busy} onAction={onAction} onAsk={onAsk} />
        <Gaps rows={d.gaps ?? []} />
      </div>
    </ModuleSection>
  );
}

/**
 * **«Korrektur zu …» — der Verweis, der auf das Papier gehört** (§9.15q). Wo er steht,
 * **mindert** dieser Beleg den genannten (MWSTG Art. 26: Leistung und Entgelt eindeutig
 * bestimmbar); die Positionen tragen positive Preise. Die genannte Rechnung steht meist
 * in einem **anderen** Auftrag – die Gutschrift gehört dorthin, wo die Ware zurückkommt,
 * und ihre Positionen entstehen dort aus den zurückkommenden Stücken.
 *
 * Gesucht wird auf dem Server (`voucherCorrectable`, #1050); die erste Zeile ist «keine».
 */
const NO_CORRECTION = '';

function Correction({ d, orderObjectId, stepId, onAction }: {
  d: Filled; orderObjectId: number; stepId: number; onAction: Send;
}) {
  const [any, setAny] = useState<boolean | null>(null);
  // **`busy` gehört hier nicht hinein** (#1016): `busy` sperrt Handlungen, nie Geometrie.
  const on = may(d, 'correct');
  const label = useCallback((r: VoucherCorrectable) => [
    r.number ?? `Beleg ${r.id}`,
    r.amount ? `${r.amount} ${r.currency}` : null,
    r.order_object_id ? `Auftrag ${r.order_object_id}` : null,
  ].filter(Boolean).join(' · '), []);
  // Die Liste wird gesucht (#1050). Vorab gefragt wird nur «gibt es überhaupt etwas zu
  // korrigieren?» – sonst stünde eine Zeile da, die für fast jeden Beleg leer bleibt.
  const find = useCallback(
    (query: string) => api.voucherCorrectable(orderObjectId, stepId, query)
      .then((rows) => rows.map((r) => ({ value: String(r.id), label: label(r) }))),
    [orderObjectId, stepId, label]);
  useEffect(() => {
    if (!on) return;
    let stale = false;
    void api.voucherCorrectable(orderObjectId, stepId)
      .then((r) => { if (!stale) setAny(r.length > 0); })
      .catch(() => { if (!stale) setAny(false); });
    return () => { stale = true; };
  }, [on, orderObjectId, stepId]);

  // **Gibt es nichts zu korrigieren und ist nichts gesetzt, gibt es die Zeile nicht.**
  // Ein Wähler ohne Wahl ist eine Frage, die niemand beantworten kann.
  if (!d.corrects && (!on || any === false)) return null;

  const text = d.corrects
    ? [d.corrects.number ?? `Beleg ${d.corrects.id}`,
       d.corrects.billed_on ? day(d.corrects.billed_on) : null]
      .filter(Boolean).join(' · ')
    : '—';

  return (
    <span className="flex items-baseline" style={{ gap: 8, minWidth: 0 }}>
      <span style={MICRO_LABEL}>{d.corrects_label || 'Korrektur zu'}</span>
      <DocFind on={on} value={d.corrects ? String(d.corrects.id) : NO_CORRECTION}
        text={text} placeholder="Rechnungsnummer"
        tip={d.corrects_hint ?? undefined}
        face={{ fontSize: 12.5, color: 'var(--fg-2)' }}
        emptyOption="keine"
        options={d.corrects
          ? [{ value: String(d.corrects.id), label: text }]
          : []}
        search={find}
        onChange={(v) => void onAction({
          action: 'correct', corrects: v === NO_CORRECTION ? null : Number(v),
        })} />
    </span>
  );
}

/**
 * **Beide Parteien auf EINEM Raster** (#913): eine feste Zeile je Angabe (`subgrid`) –
 * fehlt eine, bleibt die Zeile leer; gleiche Angabe steht auf gleicher Höhe.
 */
function Parties({ d, busy, onAction, onAsk }: {
  d: Filled; busy: boolean; onAction: Send; onAsk: Ask;
}) {
  return (
    <div style={{
      display: 'grid',
      gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 200px), 1fr))',
      gridTemplateRows: `repeat(${PARTY_ROWS}, auto)`,
      gap: '14px 24px', minWidth: 0,
    }}>
      <Party side={d.supplier} d={d} busy={busy} onAction={onAction} onAsk={onAsk} />
      <Party side={d.customer} d={d} busy={busy} onAction={onAction} onAsk={onAsk} />
    </div>
  );
}

/**
 * **Eine Seite des Belegkopfs.** Jede Angabe belegt **ihre** Zeile im gemeinsamen Raster
 * – darum steht ein `<div />` statt `null`, wo nichts dasteht. Die Gegenpartei wählt man
 * dort, wo sie steht (#912).
 */
function Party({ side, d, busy, onAction, onAsk }: {
  side: VoucherSide | null | undefined; d: Filled; busy: boolean; onAction: Send;
  onAsk: Ask;
}) {
  // **Welcher Angefragte gerade dasteht** (#951): ein Beleg hat einen Adressaten, ein Klick
  // auf einen Chip schaltet um. Die Seiten aller reisen mit (`recipients`).
  const [shown, setShown] = useState<number | null>(null);
  if (!side) return <div />;
  // **Wer die Gegenseite ist, sagt die Struktur** (`ours` vom Server) – nicht ein Vergleich
  // auf «Leistungserbringer». Ein Spiegel über die API-Grenze wird beim ersten Umbenennen
  // still falsch.
  const list = side.ours ? [] : (d.recipients ?? []);
  // **Mindestens eine** – der Adressat, wenn es einen gibt, sonst der erste Angefragte.
  const current = shown ?? side.object_id ?? list[0]?.object_id ?? null;
  const view = list.find((r) => r.object_id === current) ?? side;
  return (
    <div style={{
      display: 'grid', gridRow: `span ${PARTY_ROWS}`, gridTemplateRows: 'subgrid',
      rowGap: 3, minWidth: 0, alignContent: 'start',
    }}>
      {/* Die Auswahl steht über der Rolle (#981): erst wen, dann was für ihn gilt. */}
      {side.ours
        ? <div />
        : (
          <Recipients d={d} busy={busy} onAsk={onAsk}
            current={current} onShow={setShown} onAction={onAction} />
        )}
      <span style={MICRO_LABEL} data-tip={side.hint || undefined}>{side.label}</span>
      {/* Name und Nummer in einer Zeile – sie benennen einen Datensatz (#940/#933). */}
      <span className="flex items-baseline" style={{ gap: 8, minWidth: 0 }}>
        {side.ours
          ? <Issuer d={d} side={side} onAction={onAction} />
          : view.choice?.company ? (
            // **An die Firma oder an die Person?** Es bestellt immer eine Person; die
            // Firma ist der Rechnungsempfänger «im Namen von». Der gedruckte Name IST die Wahl.
            <DocPick on value={view.choice.bill_to_company ? FIRM : PERSON}
              text={view.name || view.choice.person}
              aria="Rechnung an" tip="Rechnung an die Firma oder an die Person"
              face={{ font: '600 13px var(--font-body)', color: 'var(--fg-1)' }}
              options={[{ value: FIRM, label: view.choice.company },
                        { value: PERSON, label: view.choice.person }]}
              onChange={(v) => void onAction({ action: 'address',
                                               bill_to_company: v === FIRM })} />
          ) : (
            <span className="truncate"
              style={{ font: '600 13px var(--font-body)', color: 'var(--fg-1)',
                       minWidth: 0 }}>
              {view.name || <Missing what="Name" />}
            </span>
          )}
        {view.object_id != null && (
          <span style={{ flex: 'none' }}><ObjId value={view.object_id} /></span>
        )}
      </span>
      {view.attn
        ? <span style={{ fontSize: 12, color: 'var(--fg-2)' }}>{view.attn}</span>
        : <div />}
      {(view.address ?? []).length
        ? <Anschrift label={view.address_label} lines={view.address ?? []}
            choice={view.choice} pick={view.choice?.billing_address_id}
            onPick={(id) => void onAction({ action: 'address', billing_address: id })} />
        /* Was fehlt, wird gesagt – aber nur über jemanden, den es gibt (#939). */
        : <div>{view.object_id != null ? <Missing what="Anschrift" /> : null}</div>}
      {/* Die Lieferadresse (#952). Ob es eine Beschriftung gibt, sagt der Server. */}
      {(view.shipping ?? []).length
        ? <Anschrift label={view.shipping_label} lines={view.shipping ?? []}
            choice={view.choice} pick={view.choice?.delivery_address_id}
            onPick={(id) => void onAction({ action: 'address', delivery_address: id })} />
        : <div />}
      {/* E-Mail und Telefon untereinander – zwei Wege, nicht ein Wert (#944). */}
      {view.email || view.phone
        ? (
          <span style={{ fontSize: 12, color: 'var(--fg-3)', whiteSpace: 'pre-line' }}>
            {[view.email, view.phone].filter(Boolean).join('\n')}
          </span>
        )
        : <div />}
      {view.uid
        ? <span style={{ fontSize: 12, color: 'var(--fg-3)' }}>{view.uid}</span>
        : <div />}
    </div>
  );
}

/** Die beiden Antworten auf «an wen geht die Rechnung?» – Werte des Wählers. */
const FIRM = 'firm';
const PERSON = 'person';

/**
 * **Eine Anschrift als Zeilen** – mit Beschriftung (#952). Wo das Adressbuch mehr als
 * eine kennt, ist sie die Wahl (`DocPick`); was wählbar ist, sagt der Server (`choice` –
 * nur am Adressaten, nur vor der Zusage, nur für das Personal).
 */
function Anschrift({ label, lines, choice, pick, onPick }: {
  label?: string | null; lines: string[];
  choice?: VoucherSide['choice']; pick?: number | null;
  onPick?: (id: number) => void;
}) {
  const face: CSSProperties = { fontSize: 12, color: 'var(--fg-2)', whiteSpace: 'pre-line' };
  const options = choice?.options ?? [];
  return (
    <span className="flex flex-col" style={{ gap: 1, minWidth: 0 }}>
      {label && <span style={MICRO_LABEL}>{label}</span>}
      {options.length > 1 && onPick ? (
        <DocPick on value={String(pick ?? '')} text={lines.join('\n')} face={face}
          aria={label ?? 'Anschrift'} tip="Andere Anschrift aus dem Adressbuch wählen"
          options={options.map((o) => ({ value: String(o.id), label: o.label }))}
          onChange={(v) => onPick(Number(v))} />
      ) : (
        <span style={face}>{lines.join('\n')}</span>
      )}
    </span>
  );
}

/**
 * **Die Gegenpartei — EINE Liste, EINE Form** (#912/#951/#962/#981): ein Chip je
 * möglicher Gegenpartei (zugelassen ∪ angefragt, `recipients` vom Server). Der **Name**
 * zeigt die Anschrift – auch bei einer noch nicht angefragten –, `+` fragt an, `✕` zieht
 * zurück. Was man **tun** darf, sagt `can` je Chip; die Liste selbst hängt nicht an `ask`.
 * Nach dem Zuschlag gibt es nichts mehr zu wählen.
 */
function Recipients({ d, busy, current, onAsk, onShow, onAction }: {
  d: Filled; busy: boolean;
  /** Wessen Anschrift gerade dasteht – der Chip dazu ist markiert. */
  current: number | null;
  onAsk: Ask;
  onShow: (objectId: number) => void;
  onAction: Send;
}) {
  const open = d.stage === VOUCHER_STAGE.offer;
  const [picked, setPicked] = useState<VoucherParty | null>(null);
  const find = useCallback((q: string) => api.searchPeople(q).catch(() => []), []);

  // Steht der Zuschlag, gibt es nichts mehr zu wählen – der Name steht eine Zeile tiefer,
  // wo er auf jedem Beleg steht.
  if (!open) return <div />;
  const asked = new Map(d.quotes.map((q) => [q.party_object_id, q]));
  const free = (d.allowed ?? []).length === 0;
  const canAsk = may(d, 'ask');
  // **Abwählen ist die Gegenhandlung zum Anfragen** (#951) – jede Zusage nach aussen hat
  // ihre Gegenhandlung an derselben Stelle. Ob es geht, sagt `can`.
  const canDrop = may(d, 'unask');
  // **Die Reihenfolge kommt vom Server** (`recipients`: Definition zuerst, frei
  // Hinzugefügte dahinter). Sie hier neu zu sortieren wäre eine zweite Ordnung.
  const rows = (d.recipients ?? []).filter((r) => r.object_id != null);
  const allowed = d.allowed ?? [];
  return (
    <div className="flex flex-wrap items-center" style={{ gap: 6, minWidth: 0 }}>
      {rows.map((r) => {
        const number = r.object_id as number;
        const quote = asked.get(number);
        // **Wegnehmen kann man, was man selbst dazugestellt hat** (#951/#1000): eine Zeile,
        // die hinausging, solange sie nicht die zugesagte ist; eine blosse Wahl ganz. Wer in
        // der **Definition** steht, bleibt – die ist die Vorlage.
        const removable = quote
          ? quote.state !== QUOTE_STATE.chosen
          : !allowed.some((p) => p.object_id === number);
        return (
          <RecipientChip key={number} name={r.name || String(number)} number={number}
            state={quote ? (quote.state ?? QUOTE_STATE.asked) : null}
            active={number === current} busy={busy}
            onShow={() => onShow(number)}
            onAsk={!quote && canAsk ? () => onAsk([number]) : undefined}
            askProblem={d.ask_problem ?? undefined}
            onDrop={canDrop && removable
              ? () => void onAction({ action: 'unask', party: number })
              : undefined} />
        );
      })}
      {free && (
        // Nur wo die Definition **niemanden** nennt. **Die Wahl wird geschrieben, nicht
        // abgeschickt** (#1000): `party` hält fest, wen der Beleg betrifft; anfragen tut der
        // `+` am Chip, wenn der Beleg vollständig ist.
        <DocRef<VoucherParty>
          on text={rows.length ? `+ ${d.party_word}` : d.party_word}
          placeholder={d.party_word} tip={d.party_word}
          face={{ fontSize: 13, color: 'var(--fg-3)' }}
          value={picked?.object_id ?? null} selected={picked} find={find}
          onChange={(_n, option) => {
            setPicked(null);
            if (option) void onAction({ action: 'party', party: option.object_id });
          }}
        />
      )}
    </div>
  );
}

/**
 * **Eine mögliche Gegenpartei** – Name und Handlung. Zwei Knöpfe in einer Hülle, nie
 * einer im anderen (#951): der Name zeigt die Anschrift, das Zeichen rechts fragt an bzw.
 * zieht zurück. Kein Zustandspunkt (#983): was angefragt ist, sagen Zeichen, Textfarbe und
 * das Wort im Hover; ausführlich steht es im Abschnitt *Angebote*.
 */
function RecipientChip({
  name, number, state, active, busy, askProblem, onShow, onAsk, onDrop,
}: {
  name: string; number: number;
  /** Der Zustand der Angebotszeile – `null` heisst «noch nicht angefragt». */
  state: string | null;
  active?: boolean;
  /**
   * **Ein Auto-Save verändert die Geometrie nicht** (#1016): `busy` blendet nichts ein
   * oder aus – die Knöpfe bleiben stehen und sind nur nicht auslösbar (Deckkraft).
   */
  busy?: boolean;
  /** **Warum gerade nicht angefragt werden kann** (#1046) – der `+` bleibt stehen und trägt den Satz. */
  askProblem?: string;
  onShow?: () => void;
  onAsk?: () => void;
  onDrop?: () => void;
}) {
  const look = quoteLook(state);
  const askOff = busy || !!askProblem;
  return (
    <span className="inline-flex items-center" style={{
      gap: 6, padding: `3px ${onAsk || onDrop ? 4 : 8}px 3px 8px`, borderRadius: 999,
      border: `1px solid ${active ? 'var(--accent)' : 'var(--border-1)'}`,
      background: active ? 'var(--accent-soft)' : undefined,
      fontSize: 12, color: state ? 'var(--fg-1)' : 'var(--fg-3)', minWidth: 0,
    }} data-tip={look.label}>
      <button type="button" onClick={onShow} aria-label={`Anschrift von ${name || number}`}
        className="truncate" style={{ ...DOC_FIELD, maxWidth: 150,
                                      cursor: onShow ? 'pointer' : 'default' }}>
        {name || number}
      </button>
      {onAsk && (
        <button type="button" onClick={askOff ? undefined : onAsk} aria-disabled={askOff}
          aria-label="Anfragen" data-tip={askProblem || 'Anfragen'}
          style={{ ...DOC_FIELD, display: 'inline-flex', color: 'var(--accent)',
                   cursor: askOff ? 'default' : 'pointer', opacity: askOff ? 0.45 : 1,
                   padding: '0 2px' }}>
          <Plus size={11} />
        </button>
      )}
      {onDrop && (
        <button type="button" onClick={busy ? undefined : onDrop} aria-disabled={busy}
          aria-label="Anfrage zurückziehen" data-tip="Anfrage zurückziehen"
          style={{ ...DOC_FIELD, display: 'inline-flex', color: 'var(--danger)',
                   cursor: busy ? 'default' : 'pointer', opacity: busy ? 0.45 : 1,
                   padding: '0 2px' }}>
          <X size={11} />
        </button>
      )}
    </span>
  );
}

/**
 * **Der Zustand einer Angebotszeile als Wort – die eine Auflösung** (#1032). Dasselbe
 * Wort bedeutet vor und nach dem Zuschlag Verschiedenes, darum nimmt sie die Entscheidung
 * als zweite Angabe:
 *
 * | | offen | entschieden |
 * |---|---|---|
 * | zugesagt | – | **Zugesagt** (grün) |
 * | offeriert | **Offeriert** (gelb) | **Unterlegen** (gedämpft) |
 * | angefragt | **Angefragt** (gedämpft) | **Unbeantwortet** (gedämpft) |
 * | abgesagt | **Abgesagt** (rot) | **Abgesagt** (rot) |
 *
 * Richtungsneutral – kein `if` auf die Richtung.
 */
function quoteLook(state: string | null, decided = false): { label: string; color: string } {
  if (state === QUOTE_STATE.chosen) return { label: 'Zugesagt', color: 'var(--success)' };
  if (state === QUOTE_STATE.declined) return { label: 'Abgesagt', color: 'var(--danger)' };
  if (state === QUOTE_STATE.quoted) {
    return decided
      ? { label: 'Unterlegen', color: 'var(--fg-4)' }
      : { label: 'Offeriert', color: 'var(--warning)' };
  }
  if (state === null) return { label: 'Noch nicht angefragt', color: 'var(--fg-4)' };
  return { label: decided ? 'Unbeantwortet' : 'Angefragt', color: 'var(--fg-4)' };
}

/**
 * **Welche unserer Gesellschaften den Beleg stellt** – vorgewählt (eingefroren mit der
 * Freigabe), hier steht die Korrektur.
 */
function Issuer({ d, side, onAction }: {
  d: Filled; side: VoucherSide; onAction: Send;
}) {
  // **Stabil über Renderings** – sonst baut `find` bei jedem Rendern neu, und das
  // Suchfeld verlöre seine Ergebnisse mitten im Tippen.
  const options = useMemo(() => d.issuers ?? [], [d.issuers]);
  // **Die Liste reist mit dem Vorgang** – ein eigener Such-Endpunkt für eine Handvoll
  // Gesellschaften wäre ein Weg zu viel. Gesucht wird darum in ihr.
  const find = useCallback(
    async (q: string) => options
      .filter((o) => o.object_id != null)
      .map((o) => ({ object_id: o.object_id as number, name: o.name }))
      .filter((o) => !q.trim()
        || o.name.toLowerCase().includes(q.toLowerCase())
        || String(o.object_id).includes(q.trim())),
    [options]);

  const face: CSSProperties = { font: '600 13px var(--font-body)', color: 'var(--fg-1)' };
  const chosen = options.find((o) => o.object_id === d.issuer);
  return (
    <DocRef
      // **Wählbar, solange man darf** (#936) – auch bei nur einer Gesellschaft: es ist eine
      // Korrektur, keine Frage.
      on={may(d, 'issuer')}
      text={side.name || <Missing what="Firma" />}
      placeholder={d.issuer_label} tip={d.issuer_label} face={face}
      value={d.issuer ?? null}
      selected={chosen?.object_id != null
        ? { object_id: chosen.object_id, name: chosen.name } : null}
      find={find}
      onChange={(n) => void onAction({ action: 'issuer', issuer: n })}
    />
  );
}

/**
 * **Was fehlt, um weiterzukommen** – `StepNeed` für Stammdaten.
 *
 * Wo sie hingehört (klickbar), was fehlt und **warum dieser Beleg sie braucht**. Kein
 * Zustand und kein Pausenwert: der Knopf ist nicht da, und hier steht, woran es liegt.
 */
function Gaps({ rows }: { rows: NonNullable<Filled['gaps']> }) {
  if (!rows.length) return null;
  return (
    <div className="flex flex-col" style={{
      gap: 6, padding: '9px 11px', borderRadius: 'var(--r-md)',
      background: 'var(--warning-bg)', border: '1px solid var(--warning)',
    }}>
      {rows.map((g, i) => (
        <div key={i} className="flex flex-col" style={{ gap: 2 }}>
          <span className="flex items-center" style={{ gap: 6, fontSize: 12.5 }}>
            <AlertTriangle size={12} style={{ color: 'var(--warning)', flex: 'none' }} />
            <strong style={{ fontWeight: 600 }}>{g.field_label}</strong>
            <span style={{ color: 'var(--fg-3)' }}>bei</span>
            {g.record_object_id
              ? <ObjId value={g.record_object_id} />
              : <span>{g.record_label}</span>}
          </span>
          <span style={{ fontSize: 11.5, color: 'var(--fg-3)', paddingLeft: 18 }}>
            {g.why}
          </span>
        </div>
      ))}
    </div>
  );
}

// ───────────────────────────────────────────────────────────────────────────────
// Die Positionen
// ───────────────────────────────────────────────────────────────────────────────

/** Unter dieser Breite nennt die Zeile ihre Sache nicht mehr – dann bricht sie um. */
const NAME_MIN = 190;

/**
 * **Die Positionen — gespeichert, nicht abgeschickt**: geschrieben wird, sooft jemand
 * tippt (`price`), und `ask` schickt sie hinaus. Jeder änderbare Wert trägt die
 * Auszeichnung (#922): Preis, Satz, Zolltarifnummer, Ursprungsland.
 */
function Goods({ d, busy, onAction }: { d: Filled; busy: boolean; onAction: Send }) {
  const editable = may(d, 'price') && d.we_quote;
  const customs = may(d, 'price');
  return (
    <ModuleSection title={d.goods_title || 'Positionen'}
      state={d.stage === VOUCHER_STAGE.offer ? 'active' : 'past'}>
      <div className="flex flex-col" style={{ gap: 10, minWidth: 0 }}>
        {d.lines.length === 0 && (
          <span style={{ fontSize: 12.5, color: 'var(--fg-3)' }}>
            Vor diesem Modul steht noch nichts – die Positionen sind die Einzelinstanzen
            des Auftrags.
          </span>
        )}
        {d.lines.map((ln) => (
          <LineRow key={ln.id} d={d} line={ln} busy={busy}
            editable={editable} customs={customs} onAction={onAction} />
        ))}
        {/* **Was ist zu tun?** – der Satz am Modul, als Auskunft (entschieden wird er beim
            Modellieren). Leer heisst «gemäss Spezifikation» und steht nicht da. */}
        {d.task && (
          <div className="flex" style={{ gap: 8, minWidth: 0,
                                         paddingTop: 2, alignItems: 'baseline' }}>
            <span style={{ ...MICRO_LABEL, flex: 'none' }}>{d.task_label}</span>
            <span style={{ fontSize: 12.5, color: 'var(--fg-2)', minWidth: 0 }}>
              {d.task}
            </span>
          </div>
        )}
        <Sums d={d} onAction={onAction} />
      </div>
    </ModuleSection>
  );
}

/** Eine Positionszeile – Menge, Sache, Zoll · Preis und Satz. */
function LineRow({ d, line, busy, editable, customs, onAction }: {
  d: Filled; line: Filled['lines'][number]; busy: boolean;
  editable: boolean; customs: boolean; onAction: Send;
}) {
  const [price, setPrice] = useState(line.price ?? '');
  const [vat, setVat] = useState(line.vat ?? 'normal');
  const [hs, setHs] = useState(line.hs_code ?? '');
  const [origin, setOrigin] = useState(line.origin_country ?? '');

  // **Was der Server sagt, gewinnt** – aber nur, wenn er sich ändert: ein `useState`-
  // Startwert wird einmal gelesen, und wer danach etwas anderes tippt, schriebe den alten
  // Wert zurück (#846).
  useEffect(() => { setPrice(line.price ?? ''); }, [line.price]);
  useEffect(() => { setVat(line.vat ?? 'normal'); }, [line.vat]);
  useEffect(() => { setHs(line.hs_code ?? ''); }, [line.hs_code]);
  useEffect(() => { setOrigin(line.origin_country ?? ''); }, [line.origin_country]);

  const dirty = price !== (line.price ?? '') || vat !== (line.vat ?? 'normal')
    || hs !== (line.hs_code ?? '') || origin !== (line.origin_country ?? '');
  const save = useCallback(() => {
    void onAction({
      action: 'price',
      lines: [{ id: line.id, price: price === '' ? null : price, vat,
                hs_code: hs, origin_country: origin }],
    });
  }, [onAction, line.id, price, vat, hs, origin]);
  const now = useAutosaveSignature(`${line.id}:${price}:${vat}:${hs}:${origin}`,
    dirty && !busy, save);

  return (
    <div className="flex flex-wrap items-start" style={{ gap: '6px 12px', minWidth: 0 }}>
      <div className="flex items-baseline"
        style={{ gap: 8, flex: `1 1 ${NAME_MIN}px`, minWidth: 0 }}>
        <span style={{ font: '600 13px var(--font-mono, var(--font-body))',
                       fontVariantNumeric: 'tabular-nums', flex: 'none' }}>
          {line.quantity}×
        </span>
        <div className="flex flex-col" style={{ gap: 2, minWidth: 0 }}>
          {/* Name und Nummer in einer Zeile (#933); gekappt wird der Name, nie die Kennung. */}
          <span className="flex items-baseline" style={{ gap: 8, minWidth: 0 }}>
            <span className="truncate" style={{ fontSize: 13, color: 'var(--fg-1)' }}>
              {line.article_name || '—'}
            </span>
            {line.article_object_id != null && (
              <span style={{ flex: 'none' }}><ObjId value={line.article_object_id} /></span>
            )}
          </span>
          <span className="flex flex-wrap items-center" style={{ gap: 8, minWidth: 0 }}>
            {/* Zoll (#915): der Artikel belegt vor, der Beleg trägt den Wert. */}
            <Customs label="Zolltarif" value={hs} on={customs} width={86}
              onChange={setHs} onDone={now} />
            <Customs label="Ursprung" value={origin} on={customs} width={64}
              onChange={setOrigin} onDone={now} />
          </span>
        </div>
      </div>
      {d.we_quote && (
        // **Der Satz steht vor dem Betrag** (#972): der Betrag ist die letzte Angabe der
        // Zeile und bildet mit den Zeilen darunter eine Spalte. Beide sitzen auf **einer
        // Grundlinie** (#963), und die Gruppe darf umbrechen – ein langer Satzname
        // («0.00 % · Steuerfreie Ausfuhrlieferung») liefe sonst in schmalen Spuren über.
        <div className="flex flex-wrap items-baseline justify-end"
          style={{ gap: '2px 10px', flex: '0 1 auto', minWidth: 0 }}>
          {/* Der Steuersatz nennt seinen Prozentsatz (#932, `vatText`). */}
          <DocPick on={editable} value={vat} text={vatText(line.vat_label, line.vat_rate)}
            aria={d.vat_label} tip={line.vat_note || d.vat_label}
            face={{ fontSize: 12, color: 'var(--fg-3)' }}
            options={(d.vat_rates ?? []).map((v) => ({
              value: v.key, label: vatText(v.label, v.rate) }))}
            onChange={(v) => { setVat(v); }} />
          <Editable on={editable} title="Einzelpreis, netto"
            missing={editable && price.trim() === ''}>
            {/* Kein Betrag ohne Währung (#1010/#1017); die Stellenzahl ist die der Währung
                (#931). Beim Speichern wird nicht gesperrt – `disabled` nähme den Fokus (#1009). */}
            {editable ? (
              <Amount currency={d.currency} size={13}>
              <input {...numericInputProps} value={price}
                onChange={(e) => setPrice(
                  numericOnly(e.target.value, { decimals: d.currency_decimals ?? 2 }))}
                onBlur={now}
                onKeyDown={(e) => { if (e.key === 'Enter') now(); }}
                aria-label="Einzelpreis"
                style={{ ...DOC_FIELD, width: 92, textAlign: 'right', fontSize: 13,
                         fontVariantNumeric: 'tabular-nums' }} />
              </Amount>
            ) : (
              <Amount value={line.price} currency={d.currency}
                decimals={d.currency_decimals ?? 2} weight={400} />
            )}
          </Editable>
        </div>
      )}
    </div>
  );
}

/**
 * **Ein Steuersatz heisst, wie er heisst – und wie hoch er ist** (#932): Wert zuerst,
 * Name danach (#938), an einer Stelle zusammengesetzt, damit Auswahl und Anzeige gleich
 * lauten.
 */
function vatText(label?: string | null, rate?: string | null): string {
  const name = label ?? '';
  if (!rate) return name || '—';
  return name ? `${rate} % · ${name}` : `${rate} %`;
}

/**
 * **Eine Zoll-Angabe** – klein, an ihrer Zeile, änderbar, solange der Beleg offen ist.
 * Die Beschriftung steht **davor**, beim Eingeben wie im fertigen Beleg (#982) – nie als
 * Platzhalter, der beim ersten Zeichen verschwindet.
 */
function Customs({ label, value, on, width, onChange, onDone }: {
  label: string; value: string; on: boolean; width: number;
  onChange: (v: string) => void; onDone: () => void;
}) {
  if (!on) {
    return value
      ? <span style={{ fontSize: 11.5, color: 'var(--fg-3)' }}>{label} {value}</span>
      : null;
  }
  return (
    <span className="inline-flex items-baseline" style={{ gap: 4, minWidth: 0 }}>
      <span style={{ fontSize: 11.5, color: 'var(--fg-3)', flex: 'none' }}>{label}</span>
      <Editable title={label} missing={value.trim() === ''}>
        <input value={value} aria-label={label}
          onChange={(e) => onChange(e.target.value)}
          onBlur={onDone}
          onKeyDown={(e) => { if (e.key === 'Enter') onDone(); }}
          style={{ ...DOC_FIELD, width, fontSize: 11.5, color: 'var(--fg-2)' }} />
      </Editable>
    </span>
  );
}

/**
 * **Netto · Steuer je Satz · Total** – jede Zahl nennt ihre Währung (#921/#1010), und der
 * Währungscode am Total **ist** der Wähler (#917).
 */
function Sums({ d, onAction }: { d: Filled; onAction: Send }) {
  const splits = useMemo(() => d.vat_split ?? [], [d.vat_split]);
  const dec = d.currency_decimals ?? 2;
  // **Die Aufstellung steht von Anfang an da** (#1009): welche Zeilen es gibt, sagen die
  // **Positionen** (jede trägt ihren Satz), nicht die Preise – sonst wüchse sie mit der
  // ersten Serverantwort in den Beleg und schöbe alles darunter weg. Wo noch nichts
  // gebucht ist, steht «—»; die Zeilen des Servers gewinnen.
  const rows = useMemo(() => {
    const out = splits.map((v) => ({
      key: v.vat, rate: v.rate, label: v.label, note: v.note,
      tax: v.tax as string | null,
    }));
    if (d.we_quote) {
      for (const ln of d.lines) {
        if (!ln.vat || out.some((r) => r.key === ln.vat)) continue;
        out.push({ key: ln.vat, rate: ln.vat_rate, label: ln.vat_label,
                   note: ln.vat_note, tax: null });
      }
    }
    // Dieselbe Reihenfolge wie beim Server (`domain/voucher.vat_split`): der höhere Satz
    // zuerst – sonst sprängen die Zeilen, sobald seine Fassung eintrifft.
    return out.sort((a, b) => Number(b.rate ?? 0) - Number(a.rate ?? 0));
  }, [splits, d.lines, d.we_quote]);

  // **Sie steht IMMER da – und mit ihr die Währung** (#1049), auch bei einer Ausgabe ohne
  // bepreiste Positionen: dort wäre die Währung sonst nie wählbar.
  const total = d.amount ?? (splits.length ? sum(splits, dec) : null);
  return (
    <div className="flex flex-col" style={{
      gap: 4, marginTop: 4, paddingTop: 9, borderTop: '1px solid var(--border-1)',
    }}>
      <SumRow label="Netto" value={d.net} code={d.currency} dec={dec} />
      {rows.map((v) => (
        <SumRow key={v.key} label={`${d.vat_label} ${v.label ?? v.rate} (${v.rate} %)`}
          value={v.tax} code={d.currency} dec={dec} hint={v.note ?? undefined} />
      ))}
      <div className="flex items-baseline" style={{
        gap: 10, marginTop: 4, paddingTop: 7, borderTop: '1px solid var(--border-1)',
      }}>
        <span style={{ ...MICRO_LABEL, flex: 1 }}>Total</span>
        {/* **Der Währungscode ist hier zugleich der Wähler** (#917) – und darum steht er
            im Währungs-Platz des Betrags, nicht als eigenes Geschwister daneben (#1007). */}
        <Amount value={total} decimals={dec} size={14} weight={700}
          currency={<Currency d={d} onAction={onAction} />} />
      </div>
    </div>
  );
}

function SumRow({ label, value, code, dec, hint }: {
  label: string; value: string | null | undefined; code: string; dec: number;
  hint?: string;
}) {
  return (
    <div className="flex items-baseline" style={{ gap: 10 }}>
      <span style={{ fontSize: 12, color: 'var(--fg-3)', flex: 1, minWidth: 0 }}
        {...(hint ? { 'data-tip': hint } : {})}>{label}</span>
      <Amount value={value} currency={code} decimals={dec} size={12.5} weight={400} />
    </div>
  );
}

function sum(rows: NonNullable<Filled['vat_split']>, dec: number): string {
  const total = rows.reduce(
    (n, r) => n + Number(r.net ?? 0) + Number(r.tax ?? 0), 0);
  return total.toFixed(dec);
}

/**
 * **Die Währung — der Code selbst ist der Wähler** (#917): ein `<span>` in der Schrift der
 * Zahl, ein unsichtbares `<select>` darüber. Nach der Zusage ist es eine Tatsache.
 */
function Currency({ d, onAction }: { d: Filled; onAction: Send }) {
  return (
    <DocPick on={may(d, 'currency')} value={d.currency} text={d.currency}
      /* Er erbt Schrift und Farbe des Betrags (#1007). */
      face={{ font: 'inherit', color: 'inherit' }}
      tip={d.currency_label} aria={d.currency_label}
      options={(d.currencies ?? []).map((c) => ({ value: c.code, label: c.label }))}
      onChange={(currency) => void onAction({ action: 'currency', currency })} />
  );
}

// ───────────────────────────────────────────────────────────────────────────────
// Die Konditionen — ohne Überschrift (#926)
// ───────────────────────────────────────────────────────────────────────────────

/**
 * **Zahlungsfrist · Lieferfrist · Lieferbedingung — ohne Überschrift** (#926). Die
 * Zahlungsfrist steht oben (#897): aus ihr kommt die Fälligkeit, null heisst
 * Vorauszahlung. **Wer den Preis nennt, nennt auch die Fristen** (`we_quote`): bei einer
 * Einnahme hier, bei einer Ausgabe an der Angebotszeile der Gegenpartei.
 */
function Terms({ d, busy, onAction }: { d: Filled; busy: boolean; onAction: Send }) {
  const on = d.stage === VOUCHER_STAGE.offer && d.we_quote && may(d, 'terms');
  return (
    <ModuleSection>
      <div style={{ display: 'grid', gap: '10px 24px',
                    gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 170px), 1fr))' }}>
        <SavedTerm label={d.payment_term_label} on={on} busy={busy} field="payment_days"
          days={d.due_days} terms={d.payment_terms ?? []} onAction={onAction}
          freeMin={d.term_free_min ?? 1} freeLabel={d.term_free_label ?? 'Individuell'} />
        <SavedTerm label={d.lead_term_label} on={on} busy={busy} field="lead_days"
          days={d.lead_days} terms={d.lead_terms ?? []} onAction={onAction}
          hint={d.due_date ? `Termin ${day(d.due_date)}` : undefined}
          freeMin={d.term_free_min ?? 1} freeLabel={d.term_free_label ?? 'Individuell'} />
        <Delivery d={d} busy={busy} onAction={onAction} />
      </div>
    </ModuleSection>
  );
}

/**
 * **Eine Frist auf dem Beleg wird sofort geschrieben** (#985): Entwurf, `useAutosaveSignature`,
 * ein Verb (`terms`), der Server ist die eine Wahrheit – dieselbe Bauart wie `Delivery`.
 * `Term` selbst bleibt gesteuert (Wert + `onChange`): an einer Angebotszeile geht die
 * Offerte nur vollständig hinaus.
 */
function SavedTerm({ label, on, busy, field, days, terms, hint, freeMin, freeLabel,
                     onAction }: {
  label: string; on: boolean; busy: boolean;
  /** Welche der beiden Fristen – zugleich der Name im Befehl. */
  field: 'payment_days' | 'lead_days';
  days: number | null | undefined;
  terms: { days: number; label: string }[];
  hint?: string;
  freeMin: number; freeLabel: string;
  onAction: Send;
}) {
  const remote = days == null ? '' : String(days);
  const [draft, setDraft] = useState(remote);
  useEffect(() => { setDraft(remote); }, [remote]);

  const save = useCallback(() => {
    // **Die Null ist eine Angabe** («Vorauszahlung» · «Sofort») – darum auf den leeren
    // String geprüft, nicht auf Wahrheit: `Number('') === 0` machte aus «noch nichts
    // gewählt» die Vorauszahlung.
    void onAction({ action: 'terms',
                    [field]: draft === '' ? null : Number(draft) });
  }, [onAction, field, draft]);
  useAutosaveSignature(`${field}:${draft}`, draft !== remote && !busy, save);

  return (
    <Term label={label} on={on} value={draft} days={days} terms={terms}
      hint={hint} freeMin={freeMin} freeLabel={freeLabel} onChange={setDraft} />
  );
}

/**
 * **Eine Frist ist ein Wert auf dem Beleg, keine Knopfreihe** (#934): der gedruckte Wert
 * («30 Tage») ist der Wähler; die freie Eingabe steht an derselben Stelle. Der Platzhalter
 * der freien Wahl ist ein Wort, kein Steuerzeichen (#943 – PostgreSQL nimmt kein NUL auf).
 */
const TERM_FREE = 'frei';

function Term({ label, on, value, days, terms, hint, freeMin, freeLabel, onChange }: {
  label: string; on: boolean;
  /** Der Entwurf (leer = noch nichts gewählt) – die gebuchte Zahl steht in `days`. */
  value: string;
  days: number | null | undefined;
  terms: { days: number; label: string }[];
  hint?: string;
  freeMin: number; freeLabel: string;
  onChange: (value: string) => void;
}) {
  const current = on ? value : (days == null ? '' : String(days));
  const named = terms.find((t) => String(t.days) === current);
  const free = current !== '' && !named;
  const [typing, setTyping] = useState(false);
  const word = current === ''
    ? '—'
    : (named ? named.label : `${current} Tag${current === '1' ? '' : 'e'}`);

  return (
    <Stacked label={label}>
      {on && (free || typing) ? (
        <Editable title={label} missing={current === ''}>
          <input {...numericInputProps} autoFocus value={current}
            aria-label={label}
            onChange={(e) => onChange(numericOnly(e.target.value, { decimals: false }))}
            onBlur={() => {
              setTyping(false);
              const n = Number(current);
              onChange(String(Number.isFinite(n) && n >= freeMin ? n : freeMin));
            }}
            onKeyDown={(e) => { if (e.key === 'Enter') e.currentTarget.blur(); }}
            style={{ ...DOC_FIELD, width: 64, fontSize: 13,
                     fontVariantNumeric: 'tabular-nums' }} />
        </Editable>
      ) : (
        <DocPick on={on} value={named ? current : ''} text={word} aria={label}
          missing={current === ''}
          face={{ fontSize: 13, color: 'var(--fg-1)' }} tip={hint}
          options={[
            ...(current === '' ? [{ value: '', label: '—' }] : []),
            ...terms.map((t) => ({ value: String(t.days), label: t.label })),
            { value: TERM_FREE, label: freeLabel },
          ]}
          onChange={(v) => {
            if (v === TERM_FREE) { setTyping(true); onChange(String(freeMin)); return; }
            onChange(v);
          }} />
      )}
    </Stacked>
  );
}

/**
 * **Beschriftung über dem Wert** – die Anatomie jeder benannten Angabe dieses Belegs
 * (Frist, feststehender Wert, Betrag einer Angebotszeile, #1049).
 */
function Stacked({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex flex-col" style={{ gap: 2, minWidth: 0 }}>
      <span style={MICRO_LABEL}>{label}</span>
      {children}
    </div>
  );
}

/** Ein feststehender Wert – Versalien-Beschriftung, Wert darunter. Wie eine Beleg-Fusszeile. */
function Fixed({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <Stacked label={label}>
      <span style={{ fontSize: 13, color: 'var(--fg-1)' }}
        {...(hint ? { 'data-tip': hint } : {})}>{value}</span>
    </Stacked>
  );
}

/**
 * **Die Lieferbedingung — Klausel UND Ort sind EINE Vereinbarung** (#911): ein Entwurf,
 * der erst hinausgeht, wenn er vollständig ist («FCA» allein weist der Dienst zu Recht ab).
 */
function Delivery({ d, busy, onAction }: { d: Filled; busy: boolean; onAction: Send }) {
  const editable = may(d, 'incoterm');
  const [key, setKey] = useState(d.incoterm ?? '');
  const [place, setPlace] = useState(d.incoterm_place ?? '');
  useEffect(() => { setKey(d.incoterm ?? ''); }, [d.incoterm]);
  useEffect(() => { setPlace(d.incoterm_place ?? ''); }, [d.incoterm_place]);

  const complete = key === '' || place.trim() !== '';
  const dirty = key !== (d.incoterm ?? '') || place !== (d.incoterm_place ?? '');
  const save = useCallback(() => {
    void onAction({ action: 'incoterm', incoterm: key || null, incoterm_place: place });
  }, [onAction, key, place]);
  const now = useAutosaveSignature(`${key}:${place}`, dirty && complete && !busy, save);

  if (!editable) {
    return (
      <div className="flex flex-col" style={{ gap: 2, minWidth: 0 }}>
        <span style={MICRO_LABEL}>{d.incoterm_label || 'Lieferbedingung'}</span>
        <span style={{ fontSize: 13, color: 'var(--fg-1)' }}>{d.incoterm_text || '—'}</span>
      </div>
    );
  }
  const chosen = (d.incoterms ?? []).find((t) => t.key === key);
  return (
    <div className="flex flex-col" style={{ gap: 2, minWidth: 0 }}>
      <span style={MICRO_LABEL}>{d.incoterm_label}</span>
      {/* Die Klausel steht als Kürzel da (#935); die Erklärung folgt darunter. */}
      <DocPick on value={key} text={chosen ? chosen.key : '—'}
        aria={d.incoterm_label} face={{ fontSize: 13, color: 'var(--fg-1)' }}
        missing={key === ''}
        options={[{ value: '', label: '—' },
                  ...(d.incoterms ?? []).map((t) => ({
                    value: t.key, label: `${t.key} · ${t.label}` }))]}
        onChange={setKey} />
      {key !== '' && (
        <Editable as="div" missing={place.trim() === ''}>
          <input value={place}
            placeholder={d.incoterm_place_label} aria-label={d.incoterm_place_label}
            onChange={(e) => setPlace(e.target.value)}
            onBlur={now}
            onKeyDown={(e) => { if (e.key === 'Enter') now(); }}
            style={{ ...DOC_FIELD, fontSize: 13, width: '100%' }} />
        </Editable>
      )}
      {/* Die Erklärung steht sichtbar, nicht im Hover: hier entscheidet ein Kürzel über
          Tausende, und wer nicht weiss, dass er fragen müsste, findet keinen Hover. */}
      {chosen?.hint && (
        <span style={{ fontSize: 11.5, color: 'var(--fg-3)' }}>{chosen.hint}</span>
      )}
    </div>
  );
}

// ───────────────────────────────────────────────────────────────────────────────
// Die Angebote
// ───────────────────────────────────────────────────────────────────────────────

/**
 * **Der Angebotsspiegel** – wir fragen an bzw. bieten an, sie nennen ihren Preis oder
 * sagen ab, wir geben den Zuschlag. **Es wird nichts zusammengeklappt** (#1032): die
 * unterlegenen Zeilen sind der Nachweis, warum so entschieden wurde; jede nennt ihren
 * Ausgang in einem Wort (`quoteLook`).
 */
function Quotes({ d, busy, active, onAsk, onAction }: {
  d: Filled; busy: boolean; active: boolean; onAsk: Ask; onAction: Send;
}) {
  const open = d.stage === VOUCHER_STAGE.offer;

  if (!d.quotes.length && !may(d, 'ask')) return null;
  // **Wann offeriert wurde, steht am Abschnitt** (#968) – die erste hinausgegangene Zeile;
  // jede Zeile trägt ihr eigenes Datum an ihrem Ort.
  const first = d.quotes
    .map((q) => q.sent_at).filter((x): x is string => !!x).sort()[0];
  return (
    <ModuleSection title={d.quotes_title || 'Angebote'}
      state={open ? 'active' : 'past'}
      right={first && (
        <Note tip={happened(first, d.sent_word).title}>
          {happened(first, d.sent_word).text}
        </Note>
      )}>
      <div className="flex flex-col" style={{ gap: 10, minWidth: 0 }}>
        {d.quotes.map((q) => (
          <QuoteRow key={q.id} d={q} voucher={d} busy={busy} onAction={onAction} />
        ))}
        {open && <Offer d={d} busy={busy} active={active} onAsk={onAsk} />}
      </div>
    </ModuleSection>
  );
}

/**
 * **Eine Angebotszeile** – wer, wie viel, welche Fristen, und was man damit tun kann.
 *
 * Sie ist zugleich der **Schalter für den Zuschlag** (#809): die Zeile IST die Wahl, kein
 * Häkchen daneben. Und **abgesagt ist abgesagt** (#811) – kein Preis, keine Frist mehr.
 */
function QuoteRow({ d, voucher: v, busy, onAction }: {
  d: VoucherQuoteOut; voucher: Filled; busy: boolean; onAction: Send;
}) {
  // **Ist die Entscheidung gefallen?** – eine Frage an den Beleg, kein Rang, den diese
  // Zeile sich selbst gibt. Ab der Zusage sagt der Zustand jeder Zeile ihren **Ausgang**.
  const decided = v.stage !== VOUCHER_STAGE.offer;
  const look = quoteLook(d.state ?? QUOTE_STATE.asked, decided);
  const declined = d.state === QUOTE_STATE.declined;
  const chosen = d.state === QUOTE_STATE.chosen;
  // **Das Wort steht da, sobald der Preis die Aussage nicht mehr trägt** (#1005/#1032):
  // während verhandelt wird, IST der Preis die Aussage; danach sagt er nicht mehr, wer
  // den Zuschlag bekam. Und wo gar kein Preis steht, war er es nie.
  const word = decided || declined || d.amount == null ? look.label : null;
  // **Ein Zustand steht EINMAL je Zeile** (#1053): «Vor 3 Tagen angenommen» sagt schon,
  // dass diese Zeile den Zuschlag hat – das Wort «Zugesagt» daneben entfällt.
  const taken = chosen && !!d.agreed_at;
  const dec = v.currency_decimals ?? 2;
  // **Offerieren darf, wer den Preis nennt** – und bei einer Einnahme nennen wir ihn
  // bereits in den Positionen; dort ist an dieser Zeile nichts einzutragen.
  const canQuote = may(v, 'quote') && !v.we_quote && !declined && !chosen;
  const canAgree = may(v, 'agree') && !declined && !chosen;
  const canDecline = may(v, 'decline') && !declined && !chosen;

  // **Welche Handlung diese Zeile weiterbringt** – eine Frage an die Daten, kein Rang, den
  // die Oberfläche vergibt: annehmen, sobald ein Preis dasteht; sonst ihn erfassen.
  const forward = canAgree && d.amount != null ? 'agree' : (canQuote ? 'quote' : null);

  const [amount, setAmount] = useState(d.amount ?? '');
  const [lead, setLead] = useState(d.lead_days == null ? '' : String(d.lead_days));
  const [pay, setPay] = useState(d.payment_days == null ? '' : String(d.payment_days));
  useEffect(() => { setAmount(d.amount ?? ''); }, [d.amount]);
  useEffect(() => { setLead(d.lead_days == null ? '' : String(d.lead_days)); },
    [d.lead_days]);
  useEffect(() => { setPay(d.payment_days == null ? '' : String(d.payment_days)); },
    [d.payment_days]);

  // **Je Handlung EIN Aufruf** – derselbe Knopf steht je nach Lage als Fläche oder als
  // Quadrat da, und zwei Fassungen desselben Befehls liefen beim nächsten Feld auseinander.
  const sendQuote = () => void onAction({
    action: 'quote', party: d.party_object_id, amount,
    ...(pay === '' ? {} : { payment_days: Number(pay) }),
    ...(lead === '' ? {} : { lead_days: Number(lead) }),
  });
  const sendAgree = () => void onAction({ action: 'agree', party: d.party_object_id });
  const sendDecline = () => void onAction({ action: 'decline', party: d.party_object_id });

  return (
    // Die Haarlinie schliesst die Zeile (#955); nach der Entscheidung treten die
    // unterlegenen über Deckkraft zurück (#1032) – lesbar, nicht gleich laut.
    <div className="flex flex-col" style={{
      gap: 6, padding: '0 0 7px', borderBottom: '1px solid var(--border-1)', minWidth: 0,
      opacity: decided && !chosen ? 0.6 : 1,
    }}>
      <div className="flex flex-wrap items-baseline" style={{ gap: '4px 10px', minWidth: 0 }}>
        {/* Kein Zustandspunkt davor (#1005): die Zeile beginnt auf derselben Kante wie jede
            andere; steht kein Preis da, sagt es das Wort. Name und Nummer sind eine Gruppe
            (#953) – gekappt wird der Name, nie die Kennung. */}
        <span className="flex items-baseline"
          style={{ gap: 8, flex: `1 1 ${NAME_MIN}px`, minWidth: 0 }}>
          <span className="truncate" style={{ fontSize: 13, minWidth: 0 }}>
            {d.party_name || d.party_object_id}
          </span>
          <span style={{ flex: 'none' }}><ObjId value={d.party_object_id} /></span>
        </span>
        {/* Wann diese Zeile den Zuschlag bekam – neben dem Betrag, die Blase darüber (#969/#978). */}
        {taken && (
          <Note tip={happened(d.agreed_at, v.taken_word).title} color={look.color}>
            {happened(d.agreed_at, v.taken_word).text}
          </Note>
        )}
        {word && !taken && (
          <span style={{ ...MICRO_LABEL, color: look.color, flex: 'none' }}>{word}</span>
        )}
        {/* **Der Betrag steht zuletzt** – dieselbe Flucht wie in jeder Geld-Zeile. Er
            bleibt auch an einer unterlegenen Zeile stehen: *warum* so entschieden wurde,
            ist genau diese Zahl. Nur eine **Absage** trägt keine mehr (#811). */}
        {d.amount != null && !declined && (
          <Amount value={d.amount} currency={v.currency} decimals={dec}
            tip={word ? undefined : look.label} />
        )}
      </div>
      {/* **Wie man bei ihm bestellt** – seine Artikelnummer, sein Shop-Link. Es gibt sie
          nur, wo wir bestellen; *was* zu tun ist, steht einmal am Beleg (`Task`). */}
      {d.ref && (
        <Note tip={v.order_label} icon={ClipboardList}>{d.ref}</Note>
      )}
      {canQuote && (
        <div className="flex flex-wrap items-end" style={{ gap: 10, minWidth: 0 }}>
          {/* Betragsfeld mit Währung, Stellenzahl der Währung und Beschriftung (#1049). */}
          <Stacked label={AMOUNT_LABEL}>
            <Editable as="div" missing={amount.trim() === ''}>
              <Amount currency={v.currency} size={13}>
                <input {...numericInputProps} value={amount}
                  onChange={(e) => setAmount(numericOnly(e.target.value, { decimals: dec }))}
                  aria-label={AMOUNT_LABEL}
                  style={{ ...DOC_FIELD, width: 92, textAlign: 'right', fontSize: 13,
                           fontVariantNumeric: 'tabular-nums' }} />
              </Amount>
            </Editable>
          </Stacked>
          {/* **Dieselbe Frist-Form wie im Beleg** – zwei Bauarten für dieselbe Frage
              liefen beim nächsten üblichen Wert auseinander, und die Zeile des Partners
              ist derselbe Beleg, nur seine Seite davon. */}
          <Term label={v.payment_term_label} on value={pay} days={null}
            terms={v.payment_terms ?? []} onChange={setPay}
            freeMin={v.term_free_min ?? 1}
            freeLabel={v.term_free_label ?? 'Individuell'} />
          <Term label={v.lead_term_label} on value={lead} days={null}
            terms={v.lead_terms ?? []} onChange={setLead}
            freeMin={v.term_free_min ?? 1}
            freeLabel={v.term_free_label ?? 'Individuell'} />
        </div>
      )}
      {/* Die Handlung, die weiterbringt, und daneben die leise Absage (#976) – dieselbe
          Zeile wie der Abschluss der Karte. Welche dominant ist, sagen die Daten: annehmen,
          sobald ein Preis dasteht, sonst ihn erfassen. */}
      <StageRow aside={(
        <>
          {canQuote && forward !== 'quote' && (
            <ActionButton icon={Send} label={QUOTE_VERB} tone="primary" height={ACT_H.stage} square
              disabled={busy || amount.trim() === ''} onClick={sendQuote} />
          )}
          {canDecline && (
            // «Absage» – richtungsneutral (#965).
            <ActionButton icon={CircleSlash} label="Absage" tone="danger" height={ACT_H.stage}
              square disabled={busy} onClick={sendDecline} />
          )}
        </>
      )}>
        {forward === 'quote' && (
          <StageAction icon={Send} label={QUOTE_VERB}
            disabled={busy || amount.trim() === ''} onClick={sendQuote} />
        )}
        {forward === 'agree' && (
          // **Das Verb kommt vom Server** (`stages[0].verb`) – es ist das Wort der
          // Schwelle und lautet in beiden Richtungen gleich (#966: «Offerte annehmen»).
          <StageAction icon={Check} label={v.stages[0]?.verb ?? 'Offerte annehmen'}
            disabled={busy} onClick={sendAgree} />
        )}
      </StageRow>
    </div>
  );
}

/**
 * **Anbieten bzw. anfragen** (#923). Die Zahl im Wort ist die der Gegenparteien, die noch
 * nichts bekommen haben; sie fällt weg, wenn es nur eine gibt (#793).
 */
function Offer({ d, busy, active, onAsk }: {
  d: Filled; busy: boolean; active: boolean; onAsk: Ask;
}) {
  const allowed = d.allowed ?? [];
  const known = d.quotes.map((q) => q.party_object_id);
  const fresh = allowed.filter((p) => !known.includes(p.object_id));
  const canAsk = may(d, 'ask') && active;
  if (!canAsk || (allowed.length > 0 && fresh.length === 0)) return null;

  const label = allowed.length > 1
    ? `${d.ask_verb} (${fresh.length})`
    : d.ask_verb;
  // **Was fehlt, steht am Knopf** (#1046): der Satz kommt vom Server (`ask_problem`),
  // dieselbe Ableitung, mit der `_ask` abweist. Gesperrt ist hier richtig – der Knopf
  // **kann**, sobald die Angaben stehen (wie «Freigeben» am Auftragsentwurf).
  const problem = d.ask_problem ?? null;
  return (
    <StageAction icon={Send} label={label} disabled={busy || !!problem}
      tip={problem ?? undefined}
      onClick={() => onAsk(fresh.map((p) => p.object_id))} />
  );
}

// ───────────────────────────────────────────────────────────────────────────────
// Rechnung & Zahlung
// ───────────────────────────────────────────────────────────────────────────────

const WAIT_TRIES = 10;
const WAIT_STEP = 1500;

/**
 * **Rechnung & Zahlung: zwei Fächer, eine Handlung, eine Wahl** (§9.15i/§9.15q).
 *
 * 1. **Zwei Fächer**: **Fordern** – *was schuldet uns jemand?* (stellen, zurücknehmen) –
 *    und **Begleichen** – *wie kommt das Geld hierher?* (bar, Überweisung, Karte). Beide
 *    sind ein gewöhnlicher `ModuleSection` mit Fortschritts-Punkt.
 * 2. **Genau eine Handlung bringt jedes Fach weiter** – unten, breit, als `StageAction`;
 *    alles andere ist eine Korrektur bei der Zeile, die sie korrigiert. Kassiert wird auf
 *    eine gestellte Rechnung – das sagt `can`.
 * 3. **Der Weg zum Geld ist eine Wahl, kein Verb** – ein Schieber; die Antworten sagt der
 *    Server (`ways`).
 *
 * **Die Rechnung IST der Beleg** (`d.invoice`, eine oder keine). Was eine gestellte
 * Rechnung mindert, ist ein eigener Beleg in einem eigenen Modul.
 */
function Money({ d, busy, orderObjectId, stepId, onAction, onPaid }: {
  d: Filled; busy: boolean; orderObjectId: number; stepId: number;
  onAction: Send; onPaid: () => void;
}) {
  const [form, setForm] = useState<{ kind: 'bill' | 'pay'; preset: string;
                                     method?: string } | null>(null);
  const [card, setCard] = useState(false);
  // **Die gewählte Antwort ist eine Ableitung**: fällt der Weg weg, steht sie auf dem
  // ersten, den es noch gibt – nie auf einem, den der Server nicht mehr führt.
  const [picked, setPicked] = useState<string | null>(null);
  const ways = d.ways ?? [];
  const way = ways.find((w) => w.key === picked) ?? ways[0] ?? null;

  // **Angezeigt wird sofort, gebucht weiterhin vom Webhook** (#857): nachgefragt wird,
  // bis sich die Summe der Zahlungen ändert – höchstens zehnmal. Kein zweiter Kanal für
  // ein Ereignis, das einmal je Zahlung eintrifft.
  const [waiting, setWaiting] = useState(0);
  const paid = d.paid ?? '';
  useEffect(() => {
    if (waiting === 0) return;
    const t = setTimeout(() => { onPaid(); setWaiting((n) => n - 1); }, WAIT_STEP);
    return () => clearTimeout(t);
  }, [waiting, onPaid]);
  useEffect(() => { setWaiting(0); }, [paid]);

  // **«Online erstatten» sagt, was daraus wurde** (#1013/#1018): gebucht wird erst, wenn
  // der Dienst es meldet, darum wird nachgefragt wie bei einer Zahlung. Ab dem Klick ist der
  // Knopf zu; dass er danach verschwindet, sagt der Server (`e.refundable`).
  const [sent, setSent] = useState<number[]>([]);
  const [failed, setFailed] = useState<string | null>(null);
  const refund = useCallback(async (entryId: number) => {
    setFailed(null);
    setSent((s) => (s.includes(entryId) ? s : [...s, entryId]));
    try {
      await api.refundVoucherPayment(orderObjectId, stepId, entryId);
      setWaiting(WAIT_TRIES);
      onPaid();
    } catch (e) {
      // **Der Knopf kommt zurück, wenn es nicht geklappt hat** – sonst wäre ein
      // Netzwerkfehler eine Sackgasse. Der Satz kommt von unserem Dienst, nie roh vom
      // Zahlungsdienst.
      setSent((s) => s.filter((id) => id !== entryId));
      setFailed(e instanceof Error ? e.message : String(e));
    }
  }, [orderObjectId, stepId, onPaid]);

  const invoice = d.invoice ?? null;
  const payments = d.entries;

  // **Fach «Fordern»: stellen → nichts mehr.** Wo **wir** den Preis
  // nennen, ist der Betrag die Summe der Positionen – dann gibt es nichts zu fragen, und
  // die Handlung geht direkt hinaus. Wo **er** ihn nennt, schreiben wir seine Rechnung ab,
  // und dafür braucht es ein Formular.
  const claimAction = may(d, 'bill')
    ? { icon: FileText, label: d.charge_word,
        run: () => (d.we_quote
          ? void onAction({ action: 'bill' })
          : setForm({ kind: 'bill', preset: d.amount ?? '' })) }
    : null;

  // **Fach «Begleichen»: was der gewählte Weg auslöst.** Jeder Weg sagt es selbst
  // (`action`/`verb`); beides leer heisst *reine Auskunft*, und dann steht dort kein
  // Knopf, der nach Buchung aussieht.
  const settleAction = way?.action === 'pay' && way.verb
    ? { icon: Wallet, label: way.verb,
        run: () => setForm({ kind: 'pay', preset: d.next_payment ?? '',
                             method: way.key }) }
    : way?.action === 'pay_online'
      ? { icon: CreditCard, label: way.verb ?? d.pay_online_word,
          run: () => setCard(true) }
      : null;

  const slot = (kind: 'bill' | 'pay') => {
    if (form) {
      return form.kind === kind ? (
        <div style={{ marginTop: 2 }}>
          <Entry kind={form.kind} d={d} busy={busy} preset={form.preset}
            method={form.method ?? null}
            onCancel={() => setForm(null)}
            onSubmit={(body) => { setForm(null); void onAction(body); }} />
        </div>
      ) : null;
    }
    const act = kind === 'bill' ? claimAction : settleAction;
    return act && (
      <div style={{ marginTop: 2 }}>
        <StageAction icon={act.icon} label={act.label} disabled={busy}
          onClick={act.run} />
      </div>
    );
  };

  /**
   * **Kleinbetragstoleranz — angeboten, nie automatisch**: ein Restsaldo unter einem
   * Franken darf als Differenz ausgebucht werden (eine gewöhnliche Zahlung mit
   * Gegenvorzeichen). Ob die Lage vorliegt, sagt der Server (`write_off`).
   */
  const writeOff = d.write_off && may(d, 'pay') ? (
    <div className="flex justify-end">
      <ActionButton icon={Eraser} label={d.write_off_word ?? 'Differenz ausbuchen'}
        disabled={busy}
        tip={`Bucht ${d.write_off} ${d.currency} als Differenz aus.`}
        onClick={() => void onAction({
          action: 'pay', amount: d.write_off as string,
          note: d.write_off_note || undefined,
        })} />
    </div>
  ) : null;

  return (
    <>
      {/* Fach 1 – was schuldet uns jemand? Aktiv, bis die Rechnung gestellt ist (#1047). */}
      <ModuleSection title={d.claim_title || 'Fordern'}
        state={invoice ? 'past' : 'active'}>
        <div className="flex flex-col" style={{ gap: 10, minWidth: 0 }}>
          {!invoice && (
            <span style={{ fontSize: 12.5, color: 'var(--fg-3)' }}>Nichts berechnet</span>
          )}
          {invoice && (
            <InvoiceRow d={d} invoice={invoice} busy={busy} onAction={onAction} />
          )}
          {slot('bill')}
        </div>
      </ModuleSection>

      {/* Fach 2 – wie kommt das Geld hierher? Feste Reihenfolge (#1001/#1019): erfasste
          Zahlungen → Saldo → Ausbuchung → Wahl → Auskunft/Karte → Knopf. Bei genau einer
          Antwort steht kein Schieber da (#793). */}
      <ModuleSection title={d.settle_title || 'Begleichen'}
        state={!ways.length && !payments.length
          ? 'ahead' : (d.open_state === 'settled' ? 'past' : 'active')}>
        <div className="flex flex-col" style={{ gap: 10, minWidth: 0 }}>
          {/* Der leere Zustand sagt nur, was wahr ist: ohne Rechnung nichts zu begleichen;
              mit einer sagt es die Zahl darunter. */}
          {!invoice && payments.length === 0 && (
            <span style={{ fontSize: 12.5, color: 'var(--fg-3)' }}>
              Noch nichts zu begleichen
            </span>
          )}
          {payments.map((p) => (
            <EntryRow key={p.id} d={d} e={p} busy={busy} onAction={onAction}
              onRefund={refund} refunding={sent.includes(p.id)} />
          ))}
          {failed && (
            <span className="flex items-center" style={{
              gap: 6, fontSize: 12, color: 'var(--danger)', minWidth: 0,
            }}>
              <AlertTriangle size={12} style={{ flex: 'none' }} />
              <span style={{ minWidth: 0 }}>{failed}</span>
            </span>
          )}
          <Balance d={d} />
          {writeOff}
          {/* Ohne Beschriftung (#1020) – die Antworten sagen selbst, was sie sind. */}
          {ways.length > 1 && way && (
            <Segmented value={way.key}
              onChange={(v) => { setPicked(v); setCard(false); }}
              options={ways.map((w) => ({ value: w.key, label: w.label }))} />
          )}
          {/* Die Auskunft kommt mit dem Weg (`info`), nicht aus einem Vergleich auf «transfer». */}
          {way?.info && (
            <Transfer orderObjectId={orderObjectId} stepId={stepId} />
          )}
          {card && (
            <PayOnline orderObjectId={orderObjectId} stepId={stepId}
              prepare={api.prepareVoucherPayment} label={d.pay_online_word}
              onDone={() => { setCard(false); setWaiting(WAIT_TRIES); onPaid(); }}
              onClose={() => setCard(false)} />
          )}
          {slot('pay')}
        </div>
      </ModuleSection>
    </>
  );
}

/**
 * **DIE Rechnung** – eine Zeile in der Grammatik jeder Geld-Zeile (`LedgerRow`), aber
 * der Beleg selbst. Die einzige Korrektur an ihr ist die Rücknahme (`unbill`), solange
 * kein Geld geflossen ist; ob es sie gibt, sagt `can`.
 */
function InvoiceRow({ d, invoice, busy, onAction }: {
  d: Filled; invoice: NonNullable<Filled['invoice']>; busy: boolean; onAction: Send;
}) {
  const dec = d.currency_decimals ?? 2;
  const tone = TONE[invoice.state_tone as keyof typeof TONE]?.color ?? 'var(--fg-1)';
  // **EIN Datum je Zeile** (#890) – die Aussage steht da, die Tatsachen im Hover.
  const stamp = invoice.due_on
    ? { text: `fällig ${lower(when(invoice.due_on))}`,
        tip: `Rechnung ${day(invoice.billed_on)} · fällig ${day(invoice.due_on)}` }
    : { text: when(invoice.billed_on),
        tip: `Rechnung ${day(invoice.billed_on)}` };
  return (
    <LedgerRow
      ident={invoice.number || 'Rechnung'}
      date={stamp.text}
      actions={may(d, 'unbill') ? (
        <ActionButton icon={Undo2} label={d.unbill_word || 'Rechnung zurücknehmen'}
          disabled={busy}
          tip="Sie ist nie hinausgegangen – die Nummer bleibt, der Beleg wird wieder
               änderbar."
          onClick={() => void onAction({ action: 'unbill' })} />
      ) : null}
      /* Der Zustand trägt die Farbe des Betrags (#996/#997), das Wort steht im Hover
         (WCAG 1.4.1). */
      tip={[invoice.state_label, stamp.tip,
            invoice.service_date
              ? `${d.service_date_label} ${day(invoice.service_date)}` : '']
        .filter(Boolean).join(' · ')}
      amount={(
        <Amount value={invoice.amount ?? ''} currency={d.currency} decimals={dec}
          color={tone} />
      )} />
  );
}

/**
 * **Der Saldo — eine Zahl, und ihre Farbe ist die Aussage** (#997): orange offen · rot
 * überfällig · grün beglichen; das Wort steht im Hover (WCAG 1.4.1). Der Zustand kommt vom
 * Server (`open_state*`, `domain/voucher.invoice_state`). Eine Überzahlung nennt sich
 * beim Namen («Guthaben») und steht positiv da – ein offener Posten ist kein negativer Wert.
 */
function Balance({ d }: { d: Filled }) {
  if (d.open == null || !d.invoice) return null;
  const dec = d.currency_decimals ?? 2;
  const credit = d.open_state === 'overpaid';
  const tone = TONE[d.open_state_tone as keyof typeof TONE]?.color ?? 'var(--fg-1)';
  return (
    <div className="flex items-baseline" style={{
      gap: 10, paddingTop: 8, borderTop: '1px solid var(--border-1)',
    }}>
      <span style={{ ...MICRO_LABEL, flex: 1, color: credit ? tone : undefined }}>
        {credit ? d.open_state_label : ''}
      </span>
      <Amount value={credit ? negate(d.open) : d.open} currency={d.currency}
        decimals={dec} size={14} weight={700} color={tone}
        tip={d.open_state_label ?? undefined} />
    </div>
  );
}

/**
 * **Eine Zahlung** – in der Grammatik jeder Geld-Zeile (`LedgerRow`: Zahlungsart · Vermerk
 * · Korrektur · Datum · Betrag). Ein Ereignis der Aussenwelt macht man nicht ungeschehen
 * (#842): korrigiert wird durch eine zweite, negative Zahlung; eine Karten-Zahlung gibt der
 * Dienst zurück, der sie eingezogen hat.
 */
function EntryRow({ d, e, busy, onAction, onRefund, refunding = false }: {
  d: Filled; e: Filled['entries'][number]; busy: boolean;
  onAction: Send;
  /** Erstatten über den Zahlungsdienst – samt Warten und sichtbarer Meldung (#1013). */
  onRefund: (entryId: number) => void;
  /** **Ab dem Klick zu** (#1018) – bis der Server sagt, dass es nichts mehr gibt. */
  refunding?: boolean;
}) {
  const dec = d.currency_decimals ?? 2;
  // «Wann war das» braucht den Zeitpunkt (`booked_at`, #1004/#1014); im Hover steht der
  // Belegtag.
  const stamp = {
    text: when(e.booked_at ?? e.booked_on),
    tip: `Gebucht ${day(e.booked_on)}`,
  };

  return (
    <LedgerRow
      /* Der Identifikator ist die Art der Zahlung (#994/#999). */
      ident={e.method_label || e.reference || 'Zahlung'}
      meta={e.note ?? ''}
      date={stamp.text}
      actions={(
        <>
          {e.refundable && (
            <ActionButton icon={Undo2} label={d.refund_online_word ?? 'Online erstatten'}
              disabled={busy || refunding}
              tip="Geht über den Zahlungsdienst zurück – gebucht wird sie, wenn er sie meldet."
              onClick={() => onRefund(e.id)} />
          )}
          {may(d, 'pay') && (
            <ActionButton icon={RotateCcw} label="Korrigieren" disabled={busy}
              tip="Eine zweite Zahlung mit dem negativen Betrag – ein Ereignis der
                   Aussenwelt macht man nicht ungeschehen."
              onClick={() => void onAction({
                action: 'pay', amount: negate(e.amount),
              })} />
          )}
        </>
      )}
      tip={stamp.tip}
      amount={(
        <Amount value={e.amount} currency={d.currency} decimals={dec}
          color={Number(e.amount) < 0 ? 'var(--fg-3)' : 'var(--fg-1)'} />
      )} />
  );
}

/**
 * **Wie man diese Rechnung überweist** – Bankverbindung, Referenz und, wo er gilt, die
 * Swiss QR-Rechnung. Eine Auskunft, keine Buchung – erst auf Klick.
 */
function Transfer({ orderObjectId, stepId }: {
  orderObjectId: number; stepId: number;
}) {
  const [info, setInfo] = useState<TransferInfo | null>(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    let stale = false;
    void api.voucherTransfer(orderObjectId, stepId)
      .then((r) => { if (!stale) setInfo(r); })
      .catch(() => { if (!stale) setFailed(true); });
    return () => { stale = true; };
  }, [orderObjectId, stepId]);

  if (failed) {
    return <span style={{ fontSize: 12, color: 'var(--danger)' }}>
      Die Angaben zur Überweisung sind gerade nicht abrufbar.
    </span>;
  }
  if (!info) {
    return <span className="flex items-center" style={{ gap: 6, fontSize: 12,
                                                        color: 'var(--fg-3)' }}>
      <Loader2 size={12} className="animate-spin" /> Einen Moment …
    </span>;
  }
  return (
    <div className="flex flex-wrap" style={{
      gap: 14, padding: 11, borderRadius: 'var(--r-md)',
      border: '1px solid var(--border-1)', minWidth: 0,
    }}>
      <div className="flex flex-col" style={{ gap: 4, flex: '1 1 200px', minWidth: 0 }}>
        <Fixed label="Empfänger" value={info.creditor ?? ''} />
        <Fixed label="IBAN" value={info.iban ?? '—'} />
        {/* Die Referenz sagt, woher sie kommt (#871). */}
        <Fixed label="Referenz" value={info.reference ?? '—'}
          hint={`Aus der Rechnungsnummer ${info.invoice} abgeleitet (ISO 11649)`} />
        <Fixed label="Betrag" value={`${info.amount ?? ''} ${info.currency ?? ''}`} />
      </div>
      {info.qr ? (
        <div style={{ flex: '0 0 168px', width: 168 }}
          dangerouslySetInnerHTML={{ __html: info.qr }} />
      ) : (
        <span style={{ fontSize: 11.5, color: 'var(--fg-3)', flex: '1 1 160px' }}>
          {info.problem}
        </span>
      )}
    </div>
  );
}

/**
 * **Eine Geld-Zeile erfassen.** Die Rechnung fragt nur, wo **sie** von aussen kommt (dann
 * schreiben wir ihre Summe, ihren Satz und ihre Nummer ab); wo wir den Preis je Position
 * nennen, geht «Rechnung stellen» ohne Feld hinaus. Die Zahlungsart ist die Wahl im Fach
 * «Begleichen» und wird hier nicht noch einmal gefragt. Masse aus den Bauteilen
 * (`inputCls`, `FIELD_GAP`, `Label`), die Fusszeile ist `StageRow` (#987/#990).
 */
function Entry({ kind, d, busy, preset, method, onCancel, onSubmit }: {
  kind: 'bill' | 'pay'; d: Filled; busy: boolean; preset: string;
  /** Der im Fach «Begleichen» gewählte Weg – bei einer Rechnung `null`. */
  method: string | null;
  onCancel: () => void; onSubmit: (body: Action) => void;
}) {
  const [amount, setAmount] = useState(preset);
  const [reference, setReference] = useState('');
  const [vat, setVat] = useState(d.vat_rate ?? 'normal');
  // **Der Satz wird nur gefragt, wo es keine bepreisten Positionen gibt** – sonst kommt
  // die Aufteilung aus ihnen, und ein Feld daneben wäre eine zweite Aussage.
  const asksVat = kind === 'bill' && !d.we_quote;
  // **Eine Rechnung von aussen hat immer eine Nummer** (#1058): der Dienst weist `bill`
  // ohne sie ab, also ist «Buchen» vorher gesperrt. Bei einer Zahlung ist sie freiwillig.
  const needsRef = kind === 'bill' && !!d.ref_label;
  const missingRef = needsRef && reference.trim() === '';

  const book = () => onSubmit({
    action: kind, amount,
    ...(kind === 'pay' && method ? { method } : {}),
    ...(asksVat ? { vat } : {}),
    ...(reference.trim() ? { reference: reference.trim() } : {}),
  });
  const ready = !busy && amount.trim() !== '' && !missingRef;

  return (
    <div className="flex flex-col" style={{
      gap: 12, padding: 12, borderRadius: 'var(--r-md)',
      border: '1px solid var(--border-1)', minWidth: 0,
    }}>
      <div className="flex flex-wrap items-end" style={{ gap: FIELD_GAP, minWidth: 0 }}>
        <Ask label={kind === 'bill' ? d.charge_word : d.payment_word}>
          <input {...numericInputProps} value={amount} autoFocus
            onChange={(e) => setAmount(numericOnly(e.target.value, { signed: true }))}
            onKeyDown={(e) => { if (e.key === 'Enter' && ready) book(); }}
            className={inputCls} aria-label="Betrag"
            style={{ width: 120, textAlign: 'right',
                     fontVariantNumeric: 'tabular-nums' }} />
        </Ask>
        {asksVat && (
          <Ask label={d.vat_label}>
            <select className={inputCls} value={vat} aria-label={d.vat_label}
              onChange={(e) => setVat(e.target.value)}>
              {(d.vat_rates ?? []).map((v) => (
                <option key={v.key} value={v.key}>{v.label}</option>
              ))}
            </select>
          </Ask>
        )}
        {/* **Das Nummernfeld gibt es nur, wo die Nummer von AUSSEN kommt** – eine, die wir
            vergeben, tippt niemand ab. */}
        {d.ref_label && (
          <Ask label={d.ref_label} grow required={needsRef}>
            <input value={reference} className={inputCls} aria-label={d.ref_label}
              onKeyDown={(e) => { if (e.key === 'Enter' && ready) book(); }}
              onChange={(e) => setReference(e.target.value)} />
          </Ask>
        )}
      </div>
      {/* **Eine Primäraktion, Abbrechen dezent** – dieselbe Zeile wie am Abschluss der
          Karte und am Zuschlag (#976). */}
      <StageRow aside={
        <ActionButton icon={X} label="Abbrechen" height={ACT_H.stage} square
          disabled={busy} onClick={onCancel} />
      }>
        {/* **Der Grund steht am Knopf, nicht nach dem Klick** (#1058/#1046) – derselbe
            Satz, den der Dienst sagen würde, nur vorher. */}
        <StageAction icon={Check} label="Buchen" disabled={!ready} onClick={book}
          tip={missingRef
            ? `Ohne ${d.ref_label} lässt sich diese Rechnung nicht zuordnen – sie steht `
              + `auf seinem Beleg.`
            : undefined} />
      </StageRow>
    </div>
  );
}

/** **Eine Frage im Formular** – Beschriftung über dem Feld, dieselbe Luft wie überall (#987/#990). */
function Ask({ label, grow, required, children }: {
  label?: string; grow?: boolean;
  /** **Pflicht, und zwar dieselbe wie im Dienst** (#1058) – `Label` trägt die Form. */
  required?: boolean;
  children: ReactNode;
}) {
  return (
    // Kein `gap`: `Label` bringt seine 4 px mit (`fields.tsx`).
    <div className="flex flex-col"
      style={{ minWidth: 0, ...(grow ? { flex: '1 1 160px' } : {}) }}>
      <Label required={required}>{label}</Label>
      {children}
    </div>
  );
}

// ───────────────────────────────────────────────────────────────────────────────
// Die Handlungen unter dem Strich
// ───────────────────────────────────────────────────────────────────────────────

/**
 * **Die Handlungen unter dem Strich** – wie die Unterschrift auf einem Beleg: der
 * **Abschluss** bringt den Vorgang ans Ziel und nimmt den Platz, der **Storno** nimmt ihn
 * zurück und steht als Quadrat daneben (#957). Wann es ihn gibt und wie er heisst («Vorgang
 * abbrechen» ↔ «Auftrag stornieren»), sagt der Server (`can`, `undo`).
 */
function Footer({ d, busy, onAction, children }: {
  d: Filled; busy: boolean; onAction: Send; children?: ReactNode;
}) {
  if (!children && !d.undo) return null;
  return (
    <div style={{ marginTop: 18, paddingTop: 12, borderTop: '1px solid var(--border-1)' }}>
      <StageRow aside={d.undo && (
        <ActionButton icon={CircleSlash} label={d.undo} tone="danger"
          height={ACT_H.stage} square
          disabled={busy}
          tip="Der Beleg behält seinen Weg – ein Storno sagt nur, dass nichts mehr kommt."
          onClick={() => void onAction({ action: 'revoke' })} />
      )}>
        {children}
      </StageRow>
    </div>
  );
}
