'use client';

import { Fragment, useCallback, useEffect, useMemo, useState } from 'react';
import type { CSSProperties, ReactNode } from 'react';
import {
  AlertTriangle, ArrowUpRight, Check, ChevronDown, CircleSlash, ClipboardList,
  CreditCard, FileText, Landmark, Loader2, Pencil, Plus, RotateCcw, Send, Undo2,
  Wallet, X,
} from 'lucide-react';
import { api } from '@/lib/api';
import type {
  TransferInfo, VoucherEmbed, VoucherParty, VoucherQuoteOut, VoucherSide,
} from '@/types';
import { ObjId } from '@/components/erp/obj-id';
import { ObjectSelect } from '@/components/erp/object-select';
import { PayOnline } from '@/components/erp/pay-online';
import {
  Label, MICRO_LABEL, TermField, inputCls, numericInputProps, numericOnly,
} from '@/components/erp/fields';
import { ACT_H, ActionButton, Actions, ModuleSection } from '@/components/erp/module-ui';
import { DEAL_STAGE, PARTY_NUMBER_LABEL, QUOTE_STATE } from '@/lib/modules';
import { useAutosave } from '@/lib/use-autosave';
import { formatAmount, localDate } from '@/lib/utils';

/**
 * ►►► **Der Beleg an der Ausführungsstelle — EIN Dokument, das WÄCHST.** ◄◄◄
 *
 * Der Neuaufbau des Zahlungsmoduls (`docs/neuaufbau-zahlungsmodul.md`). Der Vorgänger
 * (`deal-work.tsx`) entstand als Modulkarte und wurde über mehrere Runden zu einem Beleg
 * umgeformt; hier ist er von der ersten Zeile an einer:
 *
 *     Belegkopf → Positionen → Konditionen → Rückläufe → Rechnung & Zahlung → Chronik
 *
 * Das ist die Ordnung, die ein Beleg seit Jahrhunderten hat. Und er **wächst**, statt
 * umzuschalten: mit der Zusage heisst der Kopf «Auftragsbestätigung» statt «Offerte» und
 * nennt den Empfänger, die Preisspalte trägt die gebuchten Zahlen statt des Entwurfs, die
 * Konditionen stehen als Auskunft statt als Feld, die Rückläufe klappen auf eine Zeile
 * zusammen, und darunter kommt das Geld dazu. **Dieselben Zeilen, ein Zustand weiter** –
 * ein späterer PDF-Export ist damit dieselbe Komponente ohne Knöpfe.
 *
 * ## Kein einziges `if` auf die Richtung
 *
 * Was Einnahme von Ausgabe unterscheidet, **reist fertig mit** (`label`,
 * `stages[].label/verb`, `party_word`, `ask_verb`, `we_quote`, `ref_label`). Diese Datei
 * kennt weder «Kunde» noch «Lieferant»; sie fragt `may(...)` und zeichnet.
 *
 * ## Was man ändern kann, sieht man (Testnotiz #922)
 *
 * *«Es soll so ausschauen wie der finale Beleg, nur eben gehighlighted, damit man sieht:
 * ah, dieser Wert kann angepasst werden. ACHTUNG: Ich will das auch für alle anderen
 * Angaben auf dem Beleg.»*
 *
 * Also **eine** Auszeichnung (`.ix-editable` in `globals.css`), und jeder änderbare Wert
 * trägt sie: Währung · Zahlungsfrist · Lieferfrist · Lieferbedingung · Preis · MWST ·
 * Zolltarifnummer · Ursprungsland · Gegenpartei. Eine Haarlinie in der leisen Stimme des
 * Hauses, ohne Layoutwirkung – keine andere Grösse, Form oder Schrift.
 *
 * ## Die Handlung, die weiterbringt, sieht überall gleich aus (Testnotiz #923)
 *
 * *«Kann dieser Button so gross und ausdrucksstark werden wie ‹Vorgang abschliessen› am
 * Schluss? Eine UI-Logik.»* – Genau: `StageAction` ist **ein** Bauteil für «Anbieten /
 * Anfragen», «Angebot annehmen» und den Modul-Abschluss. Volle Breite, Fläche, 42 px –
 * dieselben Masse wie der Knopf, der jedes Modul beendet (`order-detail`).
 *
 * ## Und drei Dinge stehen nicht mehr da
 *
 * Die **Vorauszahlungs-Pille** im Kopf (#924/#925): ob vorausbezahlt wird, sagt die
 * **Zahlungsfrist** in den Konditionen – eine Zeile tiefer, wo man sie ändert. Die
 * Überschrift **«Konditionen»** (#926): die drei Zeilen darunter sagen selbst, was sie
 * sind. Und die **Währung** steht bei den Beträgen (#921), nicht in einem eigenen Feld.
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
 * **Darf man das hier tun?** – die eine Frage, und sie geht an den Server.
 *
 * `can` ist Auskunft **und** Tor (`services/voucher`): dieselbe Liste rendert die Knöpfe
 * und weist ab. Eine zweite Bedingung in dieser Datei wäre ein zweiter Massstab – und der
 * bekäme die nächste Regel nicht mit.
 *
 * **Das aktive Modul ist nicht die Bedingung.** Ein Zahlungsziel läuft weiter, wenn die
 * Ware längst draussen ist; die Geld-Zeilen hängen darum allein an `can` (#821). Die
 * beiden **Stufen** fragen zusätzlich nach `active` – dort ist es richtig.
 */
function may(d: Filled, action: string): boolean {
  return d.can.includes(action);
}

/** Das Vorzeichen drehen – die Vorbelegung einer Korrektur bzw. Erstattung. */
function negate(amount: string): string {
  const clean = amount.trim();
  return clean.startsWith('-') ? clean.slice(1) : `-${clean}`;
}

/** Wie viele Tage von heute bis zu diesem Datum? Negativ heisst: vorbei. */
function daysUntil(iso: string): number {
  const day = new Date(`${iso}T00:00:00`);
  const now = new Date();
  now.setHours(0, 0, 0, 0);
  return Math.round((day.getTime() - now.getTime()) / 86_400_000);
}

/** «in 30 Tagen» · «heute» · «seit 4 Tagen» – ein Datum wird zur Aussage (#890). */
function relative(iso: string): string {
  const n = daysUntil(iso);
  if (n === 0) return 'heute';
  return n > 0 ? `in ${n} Tag${n === 1 ? '' : 'en'}` : `seit ${-n} Tag${n === -1 ? '' : 'en'}`;
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
  const agreed = d.stage !== DEAL_STAGE.offer;
  // ►►► **Der Entwurf der beiden Fristen wohnt HIER.** ◄◄◄ Sie gehören zum **Angebot**:
  // es gibt sie erst, wenn eines hinausgeht – ein Auto-Save dafür schriebe an eine Zeile,
  // die es noch nicht gibt. Getippt werden sie in `Terms`, mitgeschickt von `Offer`; ein
  // gehobener Zustand ist der einfachste Weg, dass beide **dieselbe** Zahl sehen.
  const [terms, setTerms] = useState<{ pay: string; lead: string }>({
    pay: d.due_days == null ? '' : String(d.due_days),
    lead: d.lead_days == null ? '' : String(d.lead_days),
  });

  return (
    <div className="flex flex-col" style={{ minWidth: 0 }}>
      <DocHead d={d} busy={busy} onAction={onAction} />
      <Goods d={d} busy={busy} onAction={onAction} />
      <Terms d={d} busy={busy} terms={terms} onTerms={setTerms} onAction={onAction} />
      <Quotes d={d} busy={busy} active={active} terms={terms} onAction={onAction} />
      {agreed && (
        <Money d={d} busy={busy} orderObjectId={orderObjectId} stepId={stepId}
          onAction={onAction} onPaid={onPaid} />
      )}
      <Chronicle d={d} />
      {/* ►►► **Der Modul-Abschluss steht am ENDE** (Testnotiz #829). ◄◄◄ Er stand einmal
          mitten in der Kette und sagte «hier ist Schluss», während sichtbar noch etwas
          folgte. */}
      {children && <div style={{ marginTop: 18 }}>{children}</div>}
      <Bottom d={d} busy={busy} onAction={onAction} />
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// ►►► DIE BAUSTEINE DES BELEGS
// ═══════════════════════════════════════════════════════════════════════════════

/**
 * ►►► **Ein Wert, den man ändern kann** (Testnotiz #922). ◄◄◄
 *
 * Die eine Hülle – sie setzt nur die Klasse und sagt, wann sie **nicht** gilt. Dass die
 * Auszeichnung so aussieht, wie sie aussieht, steht in `globals.css`; hier steht, **wo**
 * sie gilt, und das ist die ganze Regel: jeder änderbare Wert auf dem Beleg.
 *
 * `as` ist die Form, die der Aufrufer ohnehin braucht – ein `<span>` mitten in einer
 * Zeile, ein `<div>` um ein Feld. Ein zweites Bauteil dafür wäre dieselbe Regel ein
 * zweites Mal.
 */
function Editable({ on = true, as: Tag = 'span', style, title, children }: {
  on?: boolean;
  as?: 'span' | 'div';
  style?: CSSProperties;
  title?: string;
  children: ReactNode;
}) {
  return (
    <Tag className={on ? 'ix-editable' : undefined} style={style}
      {...(on ? {} : { 'aria-disabled': true as const })}
      {...(title ? { 'data-tip': title } : {})}>
      {children}
    </Tag>
  );
}

/**
 * ►►► **Die Handlung, die den Beleg eine Stufe weiterbringt** (Testnotiz #923). ◄◄◄
 *
 * *«Kann dieser Button so gross und ausdrucksstark werden wie ‹Vorgang abschliessen› am
 * Schluss? Eine UI-Logik.»*
 *
 * Ja – und es ist buchstäblich dieselbe Form: volle Breite, Fläche, 42 px, 14 px Schrift.
 * Sie steht **einmal** hier und gilt für «Anbieten / Anfragen» wie für «Angebot annehmen»;
 * der Modul-Abschluss selbst trägt sie in `order-detail`, wo er entsteht.
 *
 * Ein Knopf, der den Beleg weiterbringt, sieht überall gleich aus – das ist die verlangte
 * UI-Logik und kein Sonderfall für eine Zeile.
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
      disabled={disabled} style={{ height: 42, fontSize: 14 }}
      {...(tip ? { 'data-tip': tip } : {})} onClick={onClick}>
      <Icon size={16} /> {label}
    </button>
  );
}

/**
 * ►►► **Ein Feld auf dem Beleg sieht aus wie der Beleg** (Testnotiz #922). ◄◄◄
 *
 * *«So dass es eigentlich ausschaut wie der final definierte Beleg, nur eben
 * gehighlighted.»* – Ein gerahmter Eingabekasten tut das **nicht**: er ist die Form eines
 * Formulars, und ein Beleg ist kein Formular. Die Eingaben auf der Karte tragen darum
 * keinen Rahmen und keine Fläche; was sie von einer gedruckten Zeile unterscheidet, ist
 * allein die Haarlinie aus `.ix-editable`.
 *
 * `inputCls` bleibt richtig, wo man wirklich ein **Formular** ausfüllt – im Editor und in
 * der Erfassungsmaske einer Geld-Zeile.
 */
const DOC_FIELD: CSSProperties = {
  background: 'transparent', border: 0, outline: 'none', padding: 0,
  font: 'inherit', color: 'inherit',
};

/** Eine Pflichtangabe, die fehlt – klein, rot, an ihrer Stelle. Erfunden wird nichts. */
function Missing({ what }: { what: string }) {
  return (
    <span style={{ ...MICRO_LABEL, color: 'var(--danger)' }}>{what} fehlt</span>
  );
}

// ───────────────────────────────────────────────────────────────────────────────
// Der Belegkopf
// ───────────────────────────────────────────────────────────────────────────────

/** Wie viele Zeilen ein Partei-Block hat – siehe `Party`. */
const PARTY_ROWS = 7;

/**
 * **Der Belegkopf** – die Belegart und beide Parteien.
 *
 * ►►► **Die Belegart ist die eine Angabe, die ein Papier zu einem Beleg macht.** ◄◄◄ Sie
 * steht sonst nirgends. Der **offene Betrag** stand einmal daneben und ist entfallen
 * (#902): auf einer Offerte ist nichts gefordert, also null – und «Offen 0.00» liest sich
 * wie «bezahlt». Er steht an der **Rechnung**, wo es ihn wirklich gibt.
 *
 * ►►► **Und die Vorauszahlungs-Pille ebenso** (Testnotizen #924/#925). ◄◄◄ *«Diese Info
 * kann komplett hier entfallen, denn ich sehe es ja unten, ob Vorauszahlung oder nicht.»*
 * – Genau: sie war die zweite Aussage über die **Zahlungsfrist**, die zwei Abschnitte
 * tiefer als Wert dasteht und dort geändert wird.
 */
function DocHead({ d, busy, onAction }: {
  d: Filled; busy: boolean; onAction: Send;
}) {
  return (
    <ModuleSection first>
      <div className="flex flex-col" style={{ gap: 14, minWidth: 0 }}>
        <div className="flex items-baseline" style={{ gap: 10, minWidth: 0 }}>
          <span style={{ font: '700 15px var(--font-display)', color: 'var(--fg-1)' }}>
            {d.stage_label}
          </span>
          <Issuer d={d} busy={busy} onAction={onAction} />
        </div>
        <Parties d={d} busy={busy} onAction={onAction} />
        <Gaps rows={d.gaps ?? []} />
      </div>
    </ModuleSection>
  );
}

/**
 * ►►► **Beide Parteien auf EINEM Raster** (Testnotiz #913). ◄◄◄
 *
 * Vorher floss jede Seite für sich untereinander: hatte die eine kein «z. H.», rutschte
 * bei ihr alles eine Zeile hoch, und die Anschrift der einen stand neben der Nummer der
 * anderen. Sie teilen jetzt **ein** Raster mit einer festen Zeile je Angabe (`subgrid`) –
 * fehlt eine, bleibt die Zeile **leer**: die Symmetrie ist die Aussage, nicht die Dichte.
 */
function Parties({ d, busy, onAction }: { d: Filled; busy: boolean; onAction: Send }) {
  return (
    <div style={{
      display: 'grid',
      gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 200px), 1fr))',
      gridTemplateRows: `repeat(${PARTY_ROWS}, auto)`,
      gap: '14px 24px', minWidth: 0,
    }}>
      <Party side={d.supplier} d={d} busy={busy} onAction={onAction} />
      <Party side={d.customer} d={d} busy={busy} onAction={onAction} />
    </div>
  );
}

/**
 * **Eine Seite des Belegkopfs.** Jede Angabe belegt **ihre** Zeile im gemeinsamen Raster –
 * darum steht überall ein `<div />` statt `null`, wo nichts dasteht.
 *
 * ►►► **Die Gegenpartei wählt man dort, wo sie steht** (Testnotiz #912). ◄◄◄ *Ändern, wo
 * man liest*: der Leistungsempfänger **ist** das Bedienelement, nicht ein Feld an anderer
 * Stelle, dessen Wirkung man drei Zeilen höher sucht.
 */
function Party({ side, d, busy, onAction }: {
  side: VoucherSide | null | undefined; d: Filled; busy: boolean; onAction: Send;
}) {
  if (!side) return <div />;
  // **Wer die Gegenseite ist, sagt die Struktur** – nicht ein Vergleich auf «Leistungs-
  // erbringer». Ein Spiegel über die API-Grenze wird beim ersten Umbenennen still falsch:
  // die Gegenseite ist die, die **wir** nicht sind, und uns kennt der Beleg am Aussteller.
  const ours = side.object_id != null && side.object_id === d.issuer;
  return (
    <div style={{
      display: 'grid', gridRow: `span ${PARTY_ROWS}`, gridTemplateRows: 'subgrid',
      rowGap: 3, minWidth: 0, alignContent: 'start',
    }}>
      <span style={MICRO_LABEL} data-tip={side.hint || undefined}>{side.label}</span>
      {ours ? (
        <span style={{ font: '600 13px var(--font-body)', color: 'var(--fg-1)' }}>
          {side.name || <Missing what="Firma" />}
        </span>
      ) : (
        <Recipients d={d} side={side} busy={busy} onAction={onAction} />
      )}
      {side.attn
        ? <span style={{ fontSize: 12, color: 'var(--fg-2)' }}>{side.attn}</span>
        : <div />}
      {(side.address ?? []).length
        ? (
          <span style={{ fontSize: 12, color: 'var(--fg-2)', whiteSpace: 'pre-line' }}>
            {(side.address ?? []).join('\n')}
          </span>
        )
        : <div><Missing what="Anschrift" /></div>}
      {side.email || side.phone
        ? (
          <span style={{ fontSize: 12, color: 'var(--fg-3)' }}>
            {[side.email, side.phone].filter(Boolean).join(' · ')}
          </span>
        )
        : <div />}
      {side.object_id != null
        ? (
          <span className="flex items-baseline" style={{ gap: 6 }}>
            <span style={MICRO_LABEL}>{d.party_number_label || PARTY_NUMBER_LABEL}</span>
            <ObjId value={side.object_id} />
          </span>
        )
        : <div />}
      {side.uid
        ? <span style={{ fontSize: 12, color: 'var(--fg-3)' }}>{side.uid}</span>
        : <div />}
    </div>
  );
}

/**
 * ►►► **Die Gegenpartei — Chips, kein Karussell** (Testnotiz #912). ◄◄◄
 *
 * Steht der Zuschlag, ist es ein Name. Davor sind es die angefragten Zeilen als Chips
 * (Punkt + Wort je Zustand) plus, wo die Definition niemanden nennt, ein Suchfeld: ein
 * Karussell mit Pfeilen sagte weder, wie viele es gibt, noch welcher gewählt ist.
 */
function Recipients({ d, side, busy, onAction }: {
  d: Filled; side: VoucherSide; busy: boolean; onAction: Send;
}) {
  const open = d.stage === DEAL_STAGE.offer;
  const canAsk = may(d, 'ask');
  const [picked, setPicked] = useState<VoucherParty | null>(null);
  const find = useCallback((q: string) => api.searchVoucherParties(q).catch(() => []), []);

  if (!open || !canAsk) {
    return (
      <span style={{ font: '600 13px var(--font-body)', color: 'var(--fg-1)' }}>
        {side.name || <Missing what="Name" />}
      </span>
    );
  }
  const known = d.quotes.map((q) => q.party_object_id);
  const free = (d.allowed ?? []).length === 0;
  return (
    <div className="flex flex-wrap items-center" style={{ gap: 6, minWidth: 0 }}>
      {d.quotes.map((q) => (
        <Chip key={q.id} name={q.party_name} number={q.party_object_id}
          state={q.state ?? QUOTE_STATE.asked} />
      ))}
      {free ? (
        <Editable as="div" style={{ minWidth: 170, flex: '1 1 170px' }}>
          <ObjectSelect<VoucherParty>
            value={picked?.object_id ?? null} selected={picked}
            placeholder={d.party_word}
            find={find}
            onChange={(_n, option) => {
              setPicked(null);
              if (option) void onAction({ action: 'ask', parties: [option.object_id] });
            }}
          />
        </Editable>
      ) : (
        (d.allowed ?? [])
          .filter((p) => !known.includes(p.object_id))
          .map((p) => (
            <button key={p.object_id} type="button" disabled={busy}
              className="ix-editable inline-flex items-center"
              style={{ gap: 5, padding: '2px 7px', fontSize: 12, color: 'var(--fg-2)',
                       background: 'transparent', border: 0, cursor: 'pointer' }}
              onClick={() => void onAction({ action: 'ask', parties: [p.object_id] })}>
              <Plus size={11} /> {p.name || p.object_id}
            </button>
          ))
      )}
    </div>
  );
}

/** Eine angefragte Gegenpartei – Punkt, Name, Nummer. Die Anatomie jedes Zustands im Haus. */
function Chip({ name, number, state }: {
  name: string; number: number; state: string;
}) {
  const look = quoteLook(state);
  return (
    <span className="inline-flex items-center" style={{
      gap: 6, padding: '3px 8px', borderRadius: 999,
      border: '1px solid var(--border-1)', fontSize: 12, color: 'var(--fg-1)',
      minWidth: 0,
    }} data-tip={look.label}>
      <span aria-hidden className="rounded-full"
        style={{ width: 6, height: 6, flex: 'none', background: look.color }} />
      <span className="truncate" style={{ maxWidth: 150 }}>{name || number}</span>
    </span>
  );
}

/** Der Zustand einer Angebotszeile als Punkt + Wort – die eine Auflösung. */
function quoteLook(state: string): { label: string; color: string } {
  if (state === QUOTE_STATE.chosen) return { label: 'Zugesagt', color: 'var(--ok)' };
  if (state === QUOTE_STATE.declined) return { label: 'Abgesagt', color: 'var(--danger)' };
  if (state === QUOTE_STATE.quoted) return { label: 'Offeriert', color: 'var(--warn)' };
  return { label: 'Angefragt', color: 'var(--fg-4)' };
}

/**
 * **Welche unserer Gesellschaften den Beleg stellt** – vorgewählt, hier steht die
 * Korrektur. Nur, wo es mehr als eine gibt: eine Auswahl mit genau einer Antwort ist keine.
 */
function Issuer({ d, busy, onAction }: { d: Filled; busy: boolean; onAction: Send }) {
  // **Stabil über Renderings** – sonst baut `find` bei jedem Rendern neu, und das
  // Suchfeld verlöre seine Ergebnisse mitten im Tippen.
  const options = useMemo(() => d.issuers ?? [], [d.issuers]);
  const [open, setOpen] = useState(false);
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

  if (!may(d, 'issuer') || options.length < 2) return null;
  const chosen = options.find((o) => o.object_id === d.issuer);
  if (!open) {
    return (
      <ActionButton icon={Pencil} label={d.issuer_label} height={ACT_H.row}
        disabled={busy} onClick={() => setOpen(true)} />
    );
  }
  return (
    // **Ein Datensatz wird über `ObjectSelect` gewählt, nie über ein natives `<select>`** –
    // nicht durchsuchbar, und eine Gesellschaft ist eine **Referenz**, keine Aufzählung.
    <Editable as="div" style={{ minWidth: 200, flex: '1 1 200px' }}>
      <ObjectSelect
        value={d.issuer ?? null}
        selected={chosen?.object_id != null
          ? { object_id: chosen.object_id, name: chosen.name } : null}
        placeholder={d.issuer_label} find={find}
        onChange={(n) => {
          setOpen(false);
          void onAction({ action: 'issuer', issuer: n });
        }}
      />
    </Editable>
  );
}


/**
 * ►►► **Was fehlt, um weiterzukommen** – `StepNeed` für Stammdaten. ◄◄◄
 *
 * Wo sie hingehört (klickbar), was fehlt und **warum dieser Beleg sie braucht**. Kein
 * Zustand und kein Pausenwert: der Knopf ist nicht da, und hier steht, woran es liegt.
 */
function Gaps({ rows }: { rows: NonNullable<Filled['gaps']> }) {
  if (!rows.length) return null;
  return (
    <div className="flex flex-col" style={{
      gap: 6, padding: '9px 11px', borderRadius: 'var(--r-md)',
      background: 'var(--warn-bg)', border: '1px solid var(--warn)',
    }}>
      {rows.map((g, i) => (
        <div key={i} className="flex flex-col" style={{ gap: 2 }}>
          <span className="flex items-center" style={{ gap: 6, fontSize: 12.5 }}>
            <AlertTriangle size={12} style={{ color: 'var(--warn)', flex: 'none' }} />
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
 * ►►► **Die Positionen — und sie werden GESPEICHERT, nicht abgeschickt.** ◄◄◄
 *
 * Beim Vorgänger reisten die Preise in der Nutzlast des **Anfragens** mit: man tippte sie
 * und schickte sie im selben Zug hinaus. Damit gab es keinen Zustand «geschrieben, aber
 * noch nicht angeboten» – und die Hausregel «Auto-Save überall» galt ausgerechnet für das
 * Herzstück des Belegs nicht.
 *
 * Hier ist die Position **der Beleg**: sie wird geschrieben, sooft jemand tippt (`price`),
 * und `ask` schickt sie hinaus. Zwei Handlungen, zwei Verben.
 *
 * **Jeder Wert trägt die Auszeichnung** (#922): Preis, Satz, Zolltarifnummer und
 * Ursprungsland. Sie sehen aus wie auf dem fertigen Beleg, nur gehighlighted.
 */
function Goods({ d, busy, onAction }: { d: Filled; busy: boolean; onAction: Send }) {
  const editable = may(d, 'price') && d.we_quote;
  const customs = may(d, 'price');
  return (
    <ModuleSection title={d.goods_title || 'Positionen'}
      state={d.stage === DEAL_STAGE.offer ? 'active' : 'past'}>
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
        <Sums d={d} busy={busy} onAction={onAction} />
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
  const now = useAutosave(`${line.id}:${price}:${vat}:${hs}:${origin}`,
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
          <span className="truncate" style={{ fontSize: 13, color: 'var(--fg-1)' }}>
            {line.article_name || '—'}
          </span>
          <span className="flex flex-wrap items-center" style={{ gap: 8, minWidth: 0 }}>
            {line.article_object_id != null && <ObjId value={line.article_object_id} />}
            {/* ►►► **Zoll: der Artikel belegt vor, der Beleg trägt den Wert** (#915). ◄◄◄
                Zolltarifnummer und Ursprungsland sind keine Beschreibung, sondern
                Voraussetzung der Ausfuhr – sie stehen offen in der Zeile, nicht hinter
                einem Klick. */}
            <Customs label="Zolltarif" value={hs} on={customs} width={86}
              busy={busy} onChange={setHs} onDone={now} />
            <Customs label="Ursprung" value={origin} on={customs} width={64}
              busy={busy} onChange={setOrigin} onDone={now} />
          </span>
        </div>
      </div>
      {d.we_quote && (
        <div className="flex items-center" style={{ gap: 10, flex: 'none' }}>
          <Editable on={editable} title="Einzelpreis, netto">
            {editable ? (
              <input {...numericInputProps} value={price} disabled={busy}
                onChange={(e) => setPrice(numericOnly(e.target.value))}
                onBlur={now}
                onKeyDown={(e) => { if (e.key === 'Enter') now(); }}
                aria-label="Einzelpreis"
                style={{ ...DOC_FIELD, width: 92, textAlign: 'right', fontSize: 13,
                         fontVariantNumeric: 'tabular-nums' }} />
            ) : (
              <span style={{ fontSize: 13, fontVariantNumeric: 'tabular-nums' }}>
                {line.price ? formatAmount(line.price, d.currency_decimals ?? 2) : '—'}
              </span>
            )}
          </Editable>
          <Editable on={editable} title={d.vat_label}>
            {editable ? (
              <select disabled={busy} value={vat} aria-label={d.vat_label}
                onChange={(e) => { setVat(e.target.value); }}
                onBlur={now}
                style={{ ...DOC_FIELD, font: '400 12px var(--font-body)',
                         color: 'var(--fg-2)', cursor: 'pointer' }}>
                {(d.vat_rates ?? []).map((v) => (
                  <option key={v.key} value={v.key}>{v.label}</option>
                ))}
              </select>
            ) : (
              <span style={{ fontSize: 12, color: 'var(--fg-3)' }}
                data-tip={line.vat_note || undefined}>{line.vat_label}</span>
            )}
          </Editable>
        </div>
      )}
    </div>
  );
}

/** Eine Zoll-Angabe – klein, an ihrer Zeile, und änderbar, solange der Beleg offen ist. */
function Customs({ label, value, on, width, busy, onChange, onDone }: {
  label: string; value: string; on: boolean; width: number; busy: boolean;
  onChange: (v: string) => void; onDone: () => void;
}) {
  if (!on) {
    return value
      ? <span style={{ fontSize: 11.5, color: 'var(--fg-3)' }}>{label} {value}</span>
      : null;
  }
  return (
    <Editable title={label}>
      <input value={value} disabled={busy} placeholder={label}
        aria-label={label}
        onChange={(e) => onChange(e.target.value)}
        onBlur={onDone}
        onKeyDown={(e) => { if (e.key === 'Enter') onDone(); }}
        style={{ ...DOC_FIELD, width, fontSize: 11.5, color: 'var(--fg-2)' }} />
    </Editable>
  );
}

/**
 * ►►► **Netto · Steuer je Satz · Total — und jede Zahl nennt ihre Währung** (#921). ◄◄◄
 *
 * *«Eigentlich wäre es schon schön und einheitlich, wenn daneben die Währung stehen
 * würde.»* – Die Regel daraus: **jede Zahl, die man abschreibt oder überweist, nennt ihre
 * Währung.** Nicht an jedem Einzelpreis: dort stünde dasselbe Wort zwanzigmal.
 *
 * **Die Währung selbst IST das Bedienelement** (#917): kein Formularfeld über einer
 * Tabelle, in der sonst nur Zahlen stehen – der Code am Total, in derselben Schrift wie
 * die Zahl daneben, mit der Auszeichnung aus #922.
 */
function Sums({ d, busy, onAction }: {
  d: Filled; busy: boolean; onAction: Send;
}) {
  const splits = d.vat_split ?? [];
  const code = d.currency;
  const dec = d.currency_decimals ?? 2;
  if (!d.we_quote && !d.amount) return null;
  const total = d.amount ?? sum(splits, dec);
  return (
    <div className="flex flex-col" style={{
      gap: 4, marginTop: 4, paddingTop: 9, borderTop: '1px solid var(--border-1)',
    }}>
      {d.net != null && (
        <SumRow label="Netto" value={`${formatAmount(d.net, dec)} ${code}`} />
      )}
      {splits.map((v, i) => (
        <SumRow key={i} label={`${d.vat_label} ${v.label ?? v.rate} (${v.rate} %)`}
          value={`${formatAmount(v.tax, dec)} ${code}`} hint={v.note ?? undefined} />
      ))}
      <div className="flex items-baseline" style={{
        gap: 10, marginTop: 4, paddingTop: 7, borderTop: '1px solid var(--border-1)',
      }}>
        <span style={{ ...MICRO_LABEL, flex: 1 }}>Total</span>
        <span style={{ font: '700 14px var(--font-body)',
                       fontVariantNumeric: 'tabular-nums' }}>
          {formatAmount(total, dec)}
        </span>
        <Currency d={d} busy={busy} onAction={onAction} />
      </div>
    </div>
  );
}

function SumRow({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="flex items-baseline" style={{ gap: 10 }}>
      <span style={{ fontSize: 12, color: 'var(--fg-3)', flex: 1, minWidth: 0 }}
        {...(hint ? { 'data-tip': hint } : {})}>{label}</span>
      <span style={{ fontSize: 12.5, fontVariantNumeric: 'tabular-nums' }}>{value}</span>
    </div>
  );
}

function sum(rows: NonNullable<Filled['vat_split']>, dec: number): string {
  const total = rows.reduce(
    (n, r) => n + Number(r.net ?? 0) + Number(r.tax ?? 0), 0);
  return total.toFixed(dec);
}

/**
 * **Die Währung — der Code selbst ist der Wähler** (#917/#921).
 *
 * Sichtbar ist ein `<span>` in der Schrift der Zahl daneben; bedienbar ein unsichtbares
 * `<select>` darüber. Ein nativer Wähler zeigt geschlossen den Text **seiner** Zeile, und
 * der wäre bei «CHF · Schweizer Franken» auf Code-Breite ein halber Name.
 *
 * Steht die Zusage, gibt es nichts mehr zu wählen – dann ist es eine Tatsache, und die
 * Auszeichnung fällt mit ihr weg.
 */
function Currency({ d, busy, onAction }: {
  d: Filled; busy: boolean; onAction: Send;
}) {
  const code = d.currency;
  const face: CSSProperties = {
    font: '600 13px var(--font-body)', color: 'var(--fg-2)',
  };
  if (!may(d, 'currency')) return <span style={face}>{code}</span>;
  return (
    <Editable title={d.currency_label}>
      <span style={{ position: 'relative', display: 'inline-block' }}>
        <span aria-hidden style={face}>{code}</span>
        <select value={code} disabled={busy} aria-label={d.currency_label}
          onChange={(e) => void onAction({ action: 'currency',
                                           currency: e.target.value })}
          style={{ position: 'absolute', inset: 0, width: '100%', height: '100%',
                   opacity: 0, cursor: 'pointer' }}>
          {(d.currencies ?? []).map((c) => (
            <option key={c.code} value={c.code}>{c.label}</option>
          ))}
        </select>
      </span>
    </Editable>
  );
}

// ───────────────────────────────────────────────────────────────────────────────
// Die Konditionen — ohne Überschrift (#926)
// ───────────────────────────────────────────────────────────────────────────────

/**
 * ►►► **Zahlungsfrist · Lieferfrist · Lieferbedingung — ohne Überschrift** (#926). ◄◄◄
 *
 * *«Ich würde gerne eine reduziertere Ansicht probieren, bei der es keine Überschrift
 * ‹Konditionen› mehr gibt, sondern einfach unter den Positionen und Beträgen die Zahlungs-
 * und Lieferkonditionen stehen. Sollte selbsterklärend genug sein.»* – Stimmt: jede der
 * drei Zeilen trägt ihren Namen, und ein Sammelbegriff darüber sagt nichts dazu.
 *
 * ►►► **Die Zahlungsfrist steht ÜBER der Lieferfrist** (#897). ◄◄◄ Sie ist die
 * folgenreichere Angabe: aus ihr kommt die Fälligkeit, und null heisst Vorauszahlung.
 *
 * **Wer den Preis nennt, nennt auch die Fristen** (`we_quote`): bei einer Einnahme
 * schreiben wir sie hier, bei einer Ausgabe füllt sie die Gegenpartei an ihrer Zeile.
 */
function Terms({ d, busy, terms, onTerms, onAction }: {
  d: Filled; busy: boolean;
  terms: { pay: string; lead: string };
  onTerms: (next: { pay: string; lead: string }) => void;
  onAction: Send;
}) {
  const open = d.stage === DEAL_STAGE.offer;
  const editable = d.we_quote && may(d, 'ask');
  const { pay, lead } = terms;
  const setPay = (v: string) => onTerms({ pay: v, lead });
  const setLead = (v: string) => onTerms({ pay, lead: v });

  if (!open || !editable) {
    return (
      <ModuleSection>
        <div style={{ display: 'grid', gap: '10px 24px',
                      gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 170px), 1fr))' }}>
          <Fixed label={d.payment_term_label}
            value={termWord(d, d.due_days, d.payment_terms ?? [])} />
          <Fixed label={d.lead_term_label}
            value={termWord(d, d.lead_days, d.lead_terms ?? [])}
            hint={d.due_date ? `Termin ${localDate(d.due_date)}` : undefined} />
          <Delivery d={d} busy={busy} onAction={onAction} />
        </div>
      </ModuleSection>
    );
  }
  return (
    <ModuleSection>
      <div style={{ display: 'grid', gap: '12px 24px',
                    gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 190px), 1fr))' }}>
        <Editable as="div">
          <TermField label={d.payment_term_label} value={pay} required
            onChange={setPay} terms={d.payment_terms ?? []}
            freeMin={d.term_free_min ?? 1} freeLabel={d.term_free_label ?? 'Individuell'} />
        </Editable>
        <Editable as="div">
          <TermField label={d.lead_term_label} value={lead} required
            onChange={setLead} terms={d.lead_terms ?? []}
            freeMin={d.term_free_min ?? 1} freeLabel={d.term_free_label ?? 'Individuell'} />
        </Editable>
        <Delivery d={d} busy={busy} onAction={onAction} />
      </div>
    </ModuleSection>
  );
}

/** Wie diese Frist **heisst** – gelesen aus derselben Liste, aus der man sie wählt (#885). */
function termWord(d: Filled, days: number | null | undefined,
                  terms: NonNullable<Filled['payment_terms']>): string {
  if (days == null) return '—';
  const named = terms.find((t) => t.days === days);
  return named ? named.label : `${days} Tag${days === 1 ? '' : 'e'}`;
}

/** Ein feststehender Wert – Versalien-Beschriftung, Wert darunter. Wie eine Beleg-Fusszeile. */
function Fixed({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="flex flex-col" style={{ gap: 2, minWidth: 0 }}>
      <span style={MICRO_LABEL}>{label}</span>
      <span style={{ fontSize: 13, color: 'var(--fg-1)' }}
        {...(hint ? { 'data-tip': hint } : {})}>{value}</span>
    </div>
  );
}

/**
 * ►►► **Die Lieferbedingung — Klausel UND Ort sind EINE Vereinbarung** (#911). ◄◄◄
 *
 * Sie leben als **ein** Entwurf und gehen zusammen hinaus, sobald er vollständig ist: das
 * Feld hing einmal am Serverwert und schickte beim Wählen sofort die Klausel **ohne** Ort;
 * der Dienst weist das zu Recht ab («FCA» allein ist keine Vereinbarung), der Server
 * änderte also nichts, und es sah aus, als täte der Klick nichts.
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
  const now = useAutosave(`${key}:${place}`, dirty && complete && !busy, save);

  if (!editable) {
    return (
      <Fixed label={d.incoterm_label || 'Lieferbedingung'}
        value={d.incoterm_text || '—'} />
    );
  }
  const chosen = (d.incoterms ?? []).find((t) => t.key === key);
  return (
    <div className="flex flex-col" style={{ gap: 4, minWidth: 0 }}>
      <Label>{d.incoterm_label}</Label>
      <Editable as="div">
        <select disabled={busy} value={key} aria-label={d.incoterm_label}
          onChange={(e) => setKey(e.target.value)}
          style={{ ...DOC_FIELD, fontSize: 13, cursor: 'pointer' }}>
          <option value="">—</option>
          {(d.incoterms ?? []).map((t) => (
            <option key={t.key} value={t.key}>{t.key} · {t.label}</option>
          ))}
        </select>
      </Editable>
      {key !== '' && (
        <Editable as="div">
          <input value={place} disabled={busy}
            placeholder={d.incoterm_place_label} aria-label={d.incoterm_place_label}
            onChange={(e) => setPlace(e.target.value)}
            onBlur={now}
            onKeyDown={(e) => { if (e.key === 'Enter') now(); }}
            style={{ ...DOC_FIELD, fontSize: 13 }} />
        </Editable>
      )}
      {/* ►►► **Die Erklärung steht SICHTBAR, nicht im Hover.** ◄◄◄ Es ist die Stelle im
          ganzen Beleg, an der ein Kürzel über Tausende entscheidet – und wer nicht weiss,
          dass er fragen müsste, findet keinen Hover. */}
      {chosen?.hint && (
        <span style={{ fontSize: 11.5, color: 'var(--fg-3)' }}>{chosen.hint}</span>
      )}
    </div>
  );
}

// ───────────────────────────────────────────────────────────────────────────────
// Die Rückläufe
// ───────────────────────────────────────────────────────────────────────────────

/**
 * **Der Angebotsspiegel** – wir fragen an bzw. bieten an, sie nennen ihren Preis oder
 * sagen ab, wir geben den Zuschlag.
 *
 * **Zusammengeklappt wird erst NACH dem Zuschlag**: solange verhandelt wird, versteckt der
 * Beleg nichts; danach sind die unterlegenen Zeilen der **Nachweis**, warum so entschieden
 * wurde – und der gehört auf Klick, nicht auf den Bildschirm.
 */
function Quotes({ d, busy, active, terms, onAction }: {
  d: Filled; busy: boolean; active: boolean;
  terms: { pay: string; lead: string }; onAction: Send;
}) {
  const open = d.stage === DEAL_STAGE.offer;
  const [shown, setShown] = useState(false);
  const chosen = d.quotes.find((q) => q.state === QUOTE_STATE.chosen);
  const rest = d.quotes.filter((q) => q.state !== QUOTE_STATE.chosen);

  if (!d.quotes.length && !may(d, 'ask')) return null;
  return (
    <ModuleSection title={d.quotes_title || 'Rückläufe'}
      state={open ? 'active' : 'past'}>
      <div className="flex flex-col" style={{ gap: 10, minWidth: 0 }}>
        {open
          ? d.quotes.map((q) => (
            <QuoteRow key={q.id} d={q} voucher={d} busy={busy} onAction={onAction} />
          ))
          : (
            <>
              {chosen && (
                <QuoteRow d={chosen} voucher={d} busy={busy} onAction={onAction} />
              )}
              {rest.length > 0 && (
                <>
                  <button type="button"
                    className="inline-flex items-center self-start"
                    style={{ gap: 6, fontSize: 12, color: 'var(--fg-3)',
                             background: 'transparent', border: 0, cursor: 'pointer' }}
                    onClick={() => setShown((v) => !v)}>
                    <ChevronDown size={12} style={{
                      transform: shown ? 'rotate(180deg)' : undefined,
                      transition: 'transform .12s',
                    }} />
                    {d.quotes.length - rest.length} von {d.quotes.length} Angeboten gewählt
                  </button>
                  {shown && rest.map((q) => (
                    <QuoteRow key={q.id} d={q} voucher={d} busy={busy}
                      onAction={onAction} />
                  ))}
                </>
              )}
            </>
          )}
        {open && <Offer d={d} busy={busy} active={active} terms={terms}
          onAction={onAction} />}
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
  const look = quoteLook(d.state ?? QUOTE_STATE.asked);
  const declined = d.state === QUOTE_STATE.declined;
  const chosen = d.state === QUOTE_STATE.chosen;
  const dec = v.currency_decimals ?? 2;
  // **Offerieren darf, wer den Preis nennt** – und bei einer Einnahme nennen wir ihn
  // bereits in den Positionen; dort ist an dieser Zeile nichts einzutragen.
  const canQuote = may(v, 'quote') && !v.we_quote && !declined && !chosen;
  const canAgree = may(v, 'agree') && !declined && !chosen;
  const canDecline = may(v, 'decline') && !declined && !chosen;

  const [amount, setAmount] = useState(d.amount ?? '');
  const [lead, setLead] = useState(d.lead_days == null ? '' : String(d.lead_days));
  const [pay, setPay] = useState(d.payment_days == null ? '' : String(d.payment_days));
  useEffect(() => { setAmount(d.amount ?? ''); }, [d.amount]);
  useEffect(() => { setLead(d.lead_days == null ? '' : String(d.lead_days)); },
    [d.lead_days]);
  useEffect(() => { setPay(d.payment_days == null ? '' : String(d.payment_days)); },
    [d.payment_days]);

  return (
    <div className="flex flex-col" style={{
      gap: 8, padding: '9px 0', borderTop: '1px solid var(--border-1)', minWidth: 0,
    }}>
      <div className="flex flex-wrap items-baseline" style={{ gap: '4px 10px', minWidth: 0 }}>
        <span aria-hidden className="rounded-full" style={{
          width: 6, height: 6, flex: 'none', background: look.color,
          alignSelf: 'center',
        }} />
        <span className="truncate" style={{ fontSize: 13, flex: `1 1 ${NAME_MIN}px`,
                                            minWidth: 0 }}>
          {d.party_name || d.party_object_id}
        </span>
        <ObjId value={d.party_object_id} />
        {d.amount != null && !declined && (
          <span style={{ font: '600 13px var(--font-body)',
                         fontVariantNumeric: 'tabular-nums' }}>
            {formatAmount(d.amount, dec)} {v.currency}
          </span>
        )}
      </div>
      {d.ref && (
        <span className="flex items-center" style={{ gap: 6, fontSize: 11.5,
                                                     color: 'var(--fg-3)' }}
          data-tip={v.task_label}>
          <ClipboardList size={11} /> {d.ref}
        </span>
      )}
      {canQuote && (
        <div className="flex flex-wrap items-end" style={{ gap: 10, minWidth: 0 }}>
          <Editable as="div">
            <input {...numericInputProps} value={amount} disabled={busy}
              onChange={(e) => setAmount(numericOnly(e.target.value))}
              aria-label="Betrag"
              style={{ ...DOC_FIELD, width: 110, textAlign: 'right', fontSize: 13,
                       fontVariantNumeric: 'tabular-nums' }} />
          </Editable>
          <Editable as="div" style={{ minWidth: 150 }}>
            <TermField label={v.payment_term_label} value={pay} onChange={setPay}
              terms={v.payment_terms ?? []} freeMin={v.term_free_min ?? 1}
              freeLabel={v.term_free_label ?? 'Individuell'} />
          </Editable>
          <Editable as="div" style={{ minWidth: 150 }}>
            <TermField label={v.lead_term_label} value={lead} onChange={setLead}
              terms={v.lead_terms ?? []} freeMin={v.term_free_min ?? 1}
              freeLabel={v.term_free_label ?? 'Individuell'} />
          </Editable>
        </div>
      )}
      <Actions>
        {canQuote && (
          <ActionButton icon={Send} label="Offerte erfassen" tone="primary"
            disabled={busy || amount.trim() === ''}
            onClick={() => void onAction({
              action: 'quote', party: d.party_object_id, amount,
              ...(pay === '' ? {} : { payment_days: Number(pay) }),
              ...(lead === '' ? {} : { lead_days: Number(lead) }),
            })} />
        )}
        {canAgree && d.amount != null && (
          <ActionButton icon={Check} label={v.stages[0]?.verb ?? 'Angebot annehmen'}
            tone="primary" disabled={busy}
            onClick={() => void onAction({ action: 'agree', party: d.party_object_id })} />
        )}
        {canDecline && (
          <ActionButton icon={CircleSlash} label="Absage · liefert nicht" tone="danger"
            disabled={busy}
            onClick={() => void onAction({ action: 'decline',
                                           party: d.party_object_id })} />
        )}
      </Actions>
    </div>
  );
}

/**
 * ►►► **Anbieten bzw. anfragen — und der Knopf sieht aus wie der am Ende** (#923). ◄◄◄
 *
 * Die Zahl im Wort ist die der Gegenparteien, die noch nichts bekommen haben; sie fällt
 * weg, wenn es nur eine gibt – dann ist die Wahl keine (#793).
 */
function Offer({ d, busy, active, terms, onAction }: {
  d: Filled; busy: boolean; active: boolean;
  terms: { pay: string; lead: string }; onAction: Send;
}) {
  const allowed = d.allowed ?? [];
  const known = d.quotes.map((q) => q.party_object_id);
  const fresh = allowed.filter((p) => !known.includes(p.object_id));
  const canAsk = may(d, 'ask') && active;
  if (!canAsk || (allowed.length > 0 && fresh.length === 0)) return null;

  const label = allowed.length > 1
    ? `${d.ask_verb} (${fresh.length})`
    : d.ask_verb;
  return (
    <StageAction icon={Send} label={label} disabled={busy}
      tip={allowed.length === 0
        ? `Wähle oben den ${d.party_word}` : undefined}
      onClick={() => void onAction({
        action: 'ask',
        ...(fresh.length ? { parties: fresh.map((p) => p.object_id) } : {}),
        // **Die Null ist eine Angabe** («Vorauszahlung» · «Sofort») – darum auf den
        // leeren String geprüft, nicht auf Wahrheit: `0 ? … : …` verlöre genau den Wert,
        // um den es geht.
        ...(terms.pay === '' ? {} : { payment_days: Number(terms.pay) }),
        ...(terms.lead === '' ? {} : { lead_days: Number(terms.lead) }),
      })} />
  );
}

// ───────────────────────────────────────────────────────────────────────────────
// Rechnung & Zahlung
// ───────────────────────────────────────────────────────────────────────────────

const WAIT_TRIES = 10;
const WAIT_STEP = 1500;

/**
 * ►►► **Rechnung und Zahlung — und sie hängen an `can`, nicht an «ist dran».** ◄◄◄
 *
 * Ein Zahlungsziel läuft weiter, wenn die Ware längst draussen ist: der Dienst erlaubt
 * Rechnung und Zahlung auch an einem **abgeschlossenen** Auftrag. Eine erfundene Sperre
 * («nur wenn das Modul aktiv ist») hätte keinen Schlüssel – dieselbe Fehlerform wie damals
 * bei «nicht bestanden».
 */
function Money({ d, busy, orderObjectId, stepId, onAction, onPaid }: {
  d: Filled; busy: boolean; orderObjectId: number; stepId: number;
  onAction: Send; onPaid: () => void;
}) {
  const [form, setForm] = useState<{ kind: 'charge' | 'pay'; preset: string;
                                     chargeId?: number | null } | null>(null);
  const [panel, setPanel] = useState<{ kind: 'pay' | 'transfer'; entry: number } | null>(null);
  const dec = d.currency_decimals ?? 2;
  const code = d.currency;

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

  const charges = d.entries.filter((e) => e.kind === 'charge');
  const payments = d.entries.filter((e) => e.kind === 'payment');

  return (
    <ModuleSection title={d.money_label || 'Rechnung & Zahlung'}
      state={charges.length ? 'active' : 'ahead'}>
      <div className="flex flex-col" style={{ gap: 10, minWidth: 0 }}>
        {charges.length === 0 && (
          <span style={{ fontSize: 12.5, color: 'var(--fg-3)' }}>Nichts berechnet</span>
        )}
        {charges.map((e) => (
          <Fragment key={e.id}>
            <EntryRow d={d} e={e} busy={busy} panel={panel}
              onAction={onAction}
              onPanel={(kind) => setPanel(
                panel && panel.entry === e.id && panel.kind === kind
                  ? null : { kind, entry: e.id })}
              onPay={() => setForm({ kind: 'pay', preset: e.open ?? '',
                                     chargeId: e.id })}
              orderObjectId={orderObjectId} stepId={stepId}
              onPaid={() => { setPanel(null); setWaiting(WAIT_TRIES); onPaid(); }} />
            {payments.filter((p) => p.charge_id === e.id).map((p) => (
              <EntryRow key={p.id} d={d} e={p} sub busy={busy} panel={null}
                onAction={onAction} onPanel={() => {}} onPay={() => {}}
                orderObjectId={orderObjectId} stepId={stepId} onPaid={onPaid} />
            ))}
          </Fragment>
        ))}
        {payments.filter((p) => p.charge_id == null).map((p) => (
          <EntryRow key={p.id} d={d} e={p} busy={busy} panel={null}
            onAction={onAction} onPanel={() => {}} onPay={() => {}}
            orderObjectId={orderObjectId} stepId={stepId} onPaid={onPaid} />
        ))}
        {form && (
          <Entry kind={form.kind} d={d} busy={busy} preset={form.preset}
            chargeId={form.chargeId ?? null}
            onCancel={() => setForm(null)}
            onSubmit={(body) => { setForm(null); void onAction(body); }} />
        )}
        <Actions>
          {may(d, 'charge') && !d.credit_only && (
            <ActionButton icon={FileText} label={d.charge_word} tone="primary"
              height={ACT_H.inline} disabled={busy}
              onClick={() => setForm({ kind: 'charge', preset: d.next_charge ?? '' })} />
          )}
          {may(d, 'pay') && (
            <ActionButton icon={Wallet} label={d.payment_word} height={ACT_H.inline}
              disabled={busy}
              onClick={() => setForm({ kind: 'pay', preset: d.next_payment ?? '' })} />
          )}
        </Actions>
        {d.open != null && charges.length > 0 && (
          <div className="flex items-baseline" style={{
            gap: 10, paddingTop: 8, borderTop: '1px solid var(--border-1)',
          }}>
            <span style={{ ...MICRO_LABEL, flex: 1 }}>{d.open_word}</span>
            <span style={{ font: '700 14px var(--font-body)',
                           fontVariantNumeric: 'tabular-nums',
                           color: Number(d.open) > 0 ? 'var(--fg-1)' : 'var(--ok)' }}>
              {formatAmount(d.open, dec)}
            </span>
            <span style={{ font: '600 13px var(--font-body)', color: 'var(--fg-2)' }}>
              {code}
            </span>
          </div>
        )}
      </div>
    </ModuleSection>
  );
}

/**
 * **Eine Geld-Zeile** – Nummer, Datum als Aussage, Betrag, Zustand und was man tun kann.
 *
 * ►►► **EIN Datum je Zeile** (#890). ◄◄◄ «6.9.2026 · fällig 6.9.2026» waren zwei Zahlen,
 * die man vergleichen muss, um die eine Aussage zu bekommen. Hier steht «fällig in 30
 * Tagen» bzw. «überfällig seit 17 Tagen»; die beiden Daten stehen im Hover.
 */
function EntryRow({ d, e, sub, busy, panel, onAction, onPanel, onPay,
                    orderObjectId, stepId, onPaid }: {
  d: Filled; e: Filled['entries'][number]; sub?: boolean; busy: boolean;
  panel: { kind: 'pay' | 'transfer'; entry: number } | null;
  onAction: Send; onPanel: (kind: 'pay' | 'transfer') => void; onPay: () => void;
  orderObjectId: number; stepId: number; onPaid: () => void;
}) {
  const dec = d.currency_decimals ?? 2;
  const charge = e.kind === 'charge';
  const state = charge ? invoiceState(e) : null;
  const when = charge && e.due_on
    ? { text: `fällig ${relative(e.due_on)}`,
        tip: `Rechnung ${localDate(e.booked_on ?? '')} · fällig ${localDate(e.due_on)}` }
    : { text: localDate(e.booked_on ?? ''), tip: e.service_date
        ? `${d.service_date_label} ${localDate(e.service_date)}` : '' };

  return (
    <div className="flex flex-col" style={{
      gap: 6, paddingLeft: sub ? 18 : 0, minWidth: 0,
      opacity: e.reversed ? 0.55 : 1,
    }}>
      <div className="flex flex-wrap items-baseline" style={{ gap: '3px 10px', minWidth: 0 }}>
        {state && (
          <span aria-hidden className="rounded-full" style={{
            width: 6, height: 6, flex: 'none', background: state.color,
            alignSelf: 'center',
          }} />
        )}
        <span className="truncate" style={{ fontSize: 12.5, color: 'var(--fg-2)',
                                            flex: '1 1 96px', minWidth: 0 }}>
          {e.reference || (charge ? 'Rechnung' : 'Zahlung')}
        </span>
        <span style={{ fontSize: 11.5, color: 'var(--fg-3)', flex: 'none',
                       fontVariantNumeric: 'tabular-nums' }}
          {...(when.tip ? { 'data-tip': when.tip } : {})}>{when.text}</span>
        <span style={{ font: '600 13px var(--font-body)', flex: 'none',
                       fontVariantNumeric: 'tabular-nums',
                       color: Number(e.amount) < 0 ? 'var(--fg-3)' : 'var(--fg-1)' }}>
          {formatAmount(e.amount, dec)} {d.currency}
        </span>
      </div>
      {(state || e.method_label) && (
        <span className="flex items-center" style={{ gap: 8, fontSize: 11.5,
                                                     color: 'var(--fg-3)' }}>
          {state && <span style={{ color: state.color }}>{state.label}</span>}
          {e.method_label && <span>{e.method_label}</span>}
          {e.note && <span className="truncate">{e.note}</span>}
        </span>
      )}
      <Actions>
        {charge && !e.reversed && may(d, 'reverse') && (
          <ActionButton icon={RotateCcw} label={e.reverse_word ?? 'Stornieren'}
            tone="danger" disabled={busy}
            onClick={() => void onAction({ action: 'reverse', entry: e.id })} />
        )}
        {charge && !e.reversed && may(d, 'pay') && Number(e.open ?? 0) > 0 && (
          <ActionButton icon={Wallet} label={d.payment_word} disabled={busy}
            onClick={onPay} />
        )}
        {e.transferable && (
          <ActionButton icon={Landmark} label={d.transfer_word ?? 'Überweisen'}
            disabled={busy} onClick={() => onPanel('transfer')} />
        )}
        {charge && !e.reversed && may(d, 'pay_online') && Number(e.open ?? 0) > 0 && (
          <ActionButton icon={CreditCard} label={d.pay_online_word} tone="primary"
            disabled={busy} onClick={() => onPanel('pay')} />
        )}
        {e.refundable && (
          <ActionButton icon={Undo2} label={d.refund_online_word ?? 'Online erstatten'}
            disabled={busy}
            onClick={() => void api.refundVoucherPayment(orderObjectId, stepId, e.id)
              .then(onPaid).catch(() => {})} />
        )}
        {!charge && may(d, 'pay') && (
          <ActionButton icon={Plus} label="Korrigieren" disabled={busy}
            tip="Eine zweite Zahlung mit dem negativen Betrag – ein Ereignis der
                 Aussenwelt macht man nicht ungeschehen."
            onClick={() => void onAction({
              action: 'pay', amount: negate(e.amount), charge_id: e.charge_id ?? null,
            })} />
        )}
      </Actions>
      {panel?.entry === e.id && panel.kind === 'pay' && (
        <PayOnline orderObjectId={orderObjectId} stepId={stepId} chargeId={e.id}
          label={d.pay_online_word} onDone={onPaid} onClose={() => onPanel('pay')} />
      )}
      {panel?.entry === e.id && panel.kind === 'transfer' && (
        <Transfer orderObjectId={orderObjectId} stepId={stepId} entryId={e.id} />
      )}
    </div>
  );
}

/** Punkt + Wort an der Rechnung – abgeleitet aus den Zahlen, kein Zustandsfeld (#875). */
function invoiceState(e: Filled['entries'][number]): { label: string; color: string } {
  const open = Number(e.open ?? 0);
  if (e.reversed) return { label: 'Storniert', color: 'var(--fg-4)' };
  if (open === 0) return { label: 'Bezahlt', color: 'var(--ok)' };
  if (open < 0) return { label: 'Überzahlt', color: 'var(--warn)' };
  if (e.overdue) return { label: 'Überfällig', color: 'var(--danger)' };
  return { label: 'Offen', color: 'var(--warn)' };
}

/**
 * **Wie man diese Rechnung überweist** – Bankverbindung, Referenz und, wo er gilt, die
 * Swiss QR-Rechnung. Eine Auskunft, keine Buchung – erst auf Klick.
 */
function Transfer({ orderObjectId, stepId, entryId }: {
  orderObjectId: number; stepId: number; entryId: number;
}) {
  const [info, setInfo] = useState<TransferInfo | null>(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    let stale = false;
    void api.voucherTransfer(orderObjectId, stepId, entryId)
      .then((r) => { if (!stale) setInfo(r); })
      .catch(() => { if (!stale) setFailed(true); });
    return () => { stale = true; };
  }, [orderObjectId, stepId, entryId]);

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
        <Fixed label="Referenz" value={info.reference ?? '—'}
          hint="Aus der Rechnungsnummer abgeleitet (ISO 11649)" />
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
 * **Eine Geld-Zeile erfassen** – Betrag, und wo es etwas zu wählen gibt, die Zahlungsart.
 *
 * Die Vorgabe kommt vom Server (`next_charge` ↔ `next_payment`) und ist **nie negativ**:
 * überberechnet ist eine gültige Aussage, aber kein Vorschlag in einem Eingabefeld.
 */
function Entry({ kind, d, busy, preset, chargeId, onCancel, onSubmit }: {
  kind: 'charge' | 'pay'; d: Filled; busy: boolean; preset: string;
  chargeId: number | null;
  onCancel: () => void; onSubmit: (body: Action) => void;
}) {
  const [amount, setAmount] = useState(preset);
  const [method, setMethod] = useState((d.methods ?? [])[0]?.key ?? '');
  const [reference, setReference] = useState('');
  const [vat, setVat] = useState(d.vat_rate ?? 'normal');
  // **Der Satz wird nur gefragt, wo es keine bepreisten Positionen gibt** – sonst kommt
  // die Aufteilung aus ihnen, und ein Feld daneben wäre eine zweite Aussage.
  const asksVat = kind === 'charge' && !d.we_quote;

  return (
    <div className="flex flex-col" style={{
      gap: 9, padding: 11, borderRadius: 'var(--r-md)',
      border: '1px solid var(--border-1)', minWidth: 0,
    }}>
      <div className="flex flex-wrap items-end" style={{ gap: 10, minWidth: 0 }}>
        <div className="flex flex-col" style={{ gap: 3 }}>
          <Label>{kind === 'charge' ? d.charge_word : d.payment_word}</Label>
          <input {...numericInputProps} value={amount} autoFocus
            onChange={(e) => setAmount(numericOnly(e.target.value, { signed: true }))}
            className={inputCls} aria-label="Betrag"
            style={{ width: 120, textAlign: 'right',
                     fontVariantNumeric: 'tabular-nums' }} />
        </div>
        {kind === 'pay' && (d.methods ?? []).length > 0 && (
          <div className="flex flex-col" style={{ gap: 3 }}>
            <Label>{d.method_label}</Label>
            <select className={inputCls} value={method}
              aria-label={d.method_label}
              onChange={(e) => setMethod(e.target.value)}>
              {(d.methods ?? []).map((m) => (
                <option key={m.key} value={m.key}>{m.label}</option>
              ))}
            </select>
          </div>
        )}
        {asksVat && (
          <div className="flex flex-col" style={{ gap: 3 }}>
            <Label>{d.vat_label}</Label>
            <select className={inputCls} value={vat} aria-label={d.vat_label}
              onChange={(e) => setVat(e.target.value)}>
              {(d.vat_rates ?? []).map((v) => (
                <option key={v.key} value={v.key}>{v.label}</option>
              ))}
            </select>
          </div>
        )}
        {/* **Das Nummernfeld gibt es nur, wo die Nummer von AUSSEN kommt** – eine, die wir
            vergeben, tippt niemand ab. */}
        {d.ref_label && (
          <div className="flex flex-col" style={{ gap: 3, flex: '1 1 160px', minWidth: 0 }}>
            <Label>{d.ref_label}</Label>
            <input value={reference} className={inputCls}
              aria-label={d.ref_label}
              onChange={(e) => setReference(e.target.value)} />
          </div>
        )}
      </div>
      <Actions>
        <ActionButton icon={Check} label="Buchen" tone="primary"
          disabled={busy || amount.trim() === ''}
          onClick={() => onSubmit({
            action: kind, amount,
            ...(kind === 'pay' && method ? { method } : {}),
            ...(kind === 'pay' && chargeId != null ? { charge_id: chargeId } : {}),
            ...(asksVat ? { vat } : {}),
            ...(reference.trim() ? { reference: reference.trim() } : {}),
          })} />
        <ActionButton icon={X} label="Abbrechen" onClick={onCancel} />
      </Actions>
    </div>
  );
}

// ───────────────────────────────────────────────────────────────────────────────
// Chronik und die Handlungen unter dem Strich
// ───────────────────────────────────────────────────────────────────────────────

/**
 * ►►► **Eine Chronik, kein zweiter Beleg** (Testnotiz #918). ◄◄◄
 *
 * *«Eigentlich muss ich ja nur wissen: wann wurde offeriert, wann wurde die Offerte
 * angenommen – alle anderen Details sind nur Duplikate.»* Stimmt: Partner, Betrag und
 * Fristen stehen im Kopf, in den Positionen und in den Konditionen. Übrig bleiben die
 * **Daten**.
 */
function Chronicle({ d }: { d: Filled }) {
  const rows: { when: string; what: string }[] = [];
  const first = d.quotes
    .map((q) => q.sent_on).filter((x): x is string => !!x).sort()[0];
  if (first) rows.push({ when: first, what: d.stages[0]?.label ?? 'Angebot' });
  if (d.agreed_on) {
    rows.push({ when: d.agreed_on, what: d.stages[1]?.label ?? 'Zusage' });
  }
  if (d.cancelled_on) rows.push({ when: d.cancelled_on, what: 'Storniert' });
  if (!rows.length) return null;
  return (
    <ModuleSection title={d.history_title || 'Chronik'}>
      <div className="flex flex-col" style={{ gap: 4 }}>
        {rows.map((r) => (
          <div key={`${r.when}:${r.what}`} className="flex items-baseline"
            style={{ gap: 10 }}>
            <span style={{ fontSize: 12, color: 'var(--fg-3)', flex: 'none',
                           fontVariantNumeric: 'tabular-nums', width: 92 }}>
              {localDate(r.when)}
            </span>
            <span style={{ fontSize: 12.5 }}>{r.what}</span>
          </div>
        ))}
      </div>
    </ModuleSection>
  );
}

/**
 * **Die Handlungen unter dem Strich** – wie die Unterschrift auf einem Beleg.
 *
 * Der **Zuschlag** steht an der Angebotszeile (dort wirkt er), der **Storno** hier: er ist
 * die Gegenhandlung des ganzen Belegs, keine Buchung.
 */
function Bottom({ d, busy, onAction }: { d: Filled; busy: boolean; onAction: Send }) {
  if (!d.undo) return null;
  return (
    <div style={{ marginTop: 18, paddingTop: 12, borderTop: '1px solid var(--border-1)' }}>
      <Actions>
        <ActionButton icon={ArrowUpRight} label={d.undo} tone="danger" disabled={busy}
          tip="Der Beleg behält seinen Weg – ein Storno sagt nur, dass nichts mehr kommt."
          onClick={() => void onAction({ action: 'revoke' })} />
      </Actions>
    </div>
  );
}
