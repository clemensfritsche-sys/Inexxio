'use client';

import type { ReactNode } from 'react';
import {
  Bell, Check, CircleSlash, CreditCard, FileText, Send as SendIcon, UserPlus, Wallet, X,
} from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import { day } from '@/lib/when';
import { VOUCHER_STAGE } from '@/lib/modules';
import { inputCls, Label, Segmented } from '@/components/erp/fields';
import { ACT_H, ActionButton } from '@/components/erp/module-ui';
import { formBody, formProblem, formWord, startForm } from './forms';
import type { Form } from './forms';
import { may, unsigned } from './shared';
import type { Filled, Send } from './shared';

type Way = NonNullable<Filled['ways']>[number];

/** Eine Handlung der Leiste – Wort, Symbol, und warum sie gerade nicht kann. */
type Primary = { label: string; icon: LucideIcon; run: () => void; problem?: string | null };

/** Was die Leiste von der Karte braucht. */
export type FooterProps = {
  d: Filled; busy: boolean;
  form: Form | null; setForm: (f: Form | null) => void;
  ways: Way[]; way: Way | null; setWay: (key: string) => void;
  setCard: (open: boolean) => void;
  /** «Partner wählen» – öffnet die Suche im Angebotsspiegel. */
  onPicking: () => void;
  /** Zurück auf die Karte, mit der bezahlt wurde (über den Dienst). */
  onRefundCard: () => void;
  /** Die Erstattung auf die Karte ist unterwegs – der Knopf ist ab dem Klick zu. */
  refunding: boolean;
  /** Wie viele Kandidaten noch nichts bekommen haben – die Zahl im Wort «Anbieten (2)». */
  fresh: number;
  onAction: Send;
};

/** Die Farbe des Punkts – der Ton der Leiste. */
const DOT: Record<string, string> = {
  done: 'var(--success)', danger: 'var(--danger)', pending: 'var(--warning)',
  neutral: 'var(--fg-4)',
};

/**
 * ►►► **DIE LEISTE – Stand, wer dran ist, die eine Handlung.** ◄◄◄
 *
 * Unten an der Karte, grau: Punkt + Wort (`state.label`), der Satz (`state.text`, mit dem
 * Datum über `lib/when`), rechts die Wege zum Geld als Wahl, die eine Handlung
 * (`state.primary`) und das Storno-Symbol, wo `can` es führt. Nie leer – ausser bei
 * «Erledigt» und «Storniert». Passen die Stücke nicht mehr (`locked`), ist die Handlung
 * gesperrt und es bleibt nur «Stornieren».
 */
export function Footer(p: FooterProps) {
  const { d, form } = p;
  const state = d.state;
  if (!state) return null;
  const date = state.date as string | null | undefined;
  const text = [state.text, date ? `${state.date_word ?? ''} ${day(date)}`.trim() : '']
    .filter(Boolean).join(' · ');
  const inline = form && (form.kind === 'writeoff' || form.kind === 'revoke');
  return (
    <footer style={{
      display: 'flex', flexDirection: 'column', gap: 12, margin: '30px -18px -16px',
      padding: '16px 18px', background: 'var(--bg-2)', borderTop: '1px solid var(--border-1)',
      borderRadius: '0 0 var(--r-lg) var(--r-lg)',
    }}>
      <div className="flex flex-wrap items-center justify-between" style={{ gap: '12px 16px' }}>
        <div className="flex items-start" style={{ gap: 9, minWidth: 0, flex: '1 1 200px' }}>
          <span aria-hidden className="rounded-full" style={{
            width: 7, height: 7, flex: 'none', marginTop: 6,
            background: DOT[state.tone] ?? 'var(--fg-4)',
          }} />
          <div style={{ minWidth: 0 }}>
            <div style={{ font: '600 14px var(--font-body)', color: 'var(--fg-1)' }}>{state.label}</div>
            <div style={{ fontSize: 12.5, color: 'var(--fg-3)', marginTop: 2 }}>
              {inline && form.kind === 'writeoff' ? 'Grund wählen, dann ausbuchen' : text}
            </div>
          </div>
        </div>
        {!inline && <Doing {...p} />}
      </div>
      {inline && <InlineForm {...p} form={form} />}
    </footer>
  );
}

/** Die rechte Seite: Wege · Mahnung · die eine Handlung · Storno. */
function Doing(p: FooterProps) {
  const { d, busy, form } = p;
  const primary = primaryOf(p);
  // **Die Wege zum Geld** – eine Wahl, solange es ums Bezahlen geht (auch beim Erfassen).
  const money = p.ways.length > 1 && (form
    ? form.kind === 'pay'
    : ['pay', 'remind'].includes(d.state?.primary ?? ''));
  const remind = !form && remindOf(d);
  return (
    <div className="flex flex-wrap items-center justify-end" style={{ gap: 8 }}>
      {money && p.way && (
        <Segmented value={p.way.key} onChange={p.setWay}
          options={p.ways.map((w) => ({ value: w.key, label: w.label }))} />
      )}
      {remind && (
        <MainButton label={remind.label} icon={Bell} busy={busy} problem={remind.problem}
          quiet={d.state?.primary !== 'remind'} onClick={() => void p.onAction({ action: 'remind' })} />
      )}
      {primary && (
        <MainButton label={primary.label} icon={primary.icon} busy={busy}
          problem={primary.problem} onClick={primary.run} />
      )}
      {may(d, 'revoke') && (
        <ActionButton icon={CircleSlash} label={d.undo ?? 'Stornieren'} tone="danger"
          height={ACT_H.stage} square disabled={busy}
          tip={d.locked ?? 'Ein Wort für den Storno in jeder Stufe – mit Grund, wer ihn kennt.'}
          onClick={() => p.setForm(startForm('revoke', d))} />
      )}
    </div>
  );
}

/**
 * **Die eine Handlung** – ein Formular wird abgeschickt, sonst sagt der Server, welche
 * ansteht (`state.primary`). Was noch nicht kann, ist gesperrt und nennt den Grund.
 */
function primaryOf(p: FooterProps): Primary | null {
  const { d, form } = p;
  if (form) {
    return { label: formWord(form, d), icon: Check, problem: formProblem(form, d),
             run: () => { void p.onAction(formBody(form, d)); p.setForm(null); } };
  }
  if (d.locked) return lockedOf(d);
  switch (d.state?.primary) {
    case 'ask':
      return { label: p.fresh > 1 ? `${d.ask_verb} (${p.fresh})` : d.ask_verb, icon: SendIcon,
               problem: d.ask_problem ?? (may(d, 'ask') ? null : gapsWord(d)),
               run: () => void p.onAction({ action: 'ask' }) };
    case 'party':
      return may(d, 'party') && d.allowed.length === 0
        ? { label: `${d.party_word} wählen`, icon: UserPlus, run: p.onPicking } : null;
    case 'bill':
      return { label: d.charge_word, icon: FileText,
               problem: may(d, 'bill') ? null : gapsWord(d),
               run: () => (d.we_quote
                 ? void p.onAction({ action: 'bill' })
                 : p.setForm(startForm('bill', d))) };
    case 'pay':
    case 'remind':
      return wayOf(p);
    default:
      return null;
  }
}

/** Was der gewählte Weg zum Geld auslöst – eine Buchung, die Karte, oder nur Auskunft. */
function wayOf(p: FooterProps): Primary | null {
  const { d, way } = p;
  if (!way) return null;
  if (way.action === 'pay') {
    return { label: way.verb ?? d.payment_word, icon: Wallet,
             problem: may(d, 'pay') ? null : 'Bezahlt wird erst nach dem Entscheid oben.',
             run: () => p.setForm(startForm('pay', d, way.key)) };
  }
  if (way.action === 'pay_online') {
    return { label: way.verb ?? d.pay_online_word, icon: CreditCard, run: () => p.setCard(true) };
  }
  if (way.action === 'refund_online') {
    // **Ab dem Klick zu** – bis der Dienst meldet; danach sagt der Server, ob es ihn gibt.
    return { label: `${way.verb ?? d.refund_online_word} · ${unsigned(d.open ?? '')} ${d.currency}`,
             icon: CreditCard, run: p.onRefundCard,
             problem: p.refunding ? 'Unterwegs – gebucht wird, wenn der Dienst die Erstattung meldet.' : null };
  }
  return null;
}

/** Fehlende Angaben sagen, wo sie fehlen – die Zeilen stehen oben im Kopf. */
function gapsWord(d: Filled): string {
  const g = (d.gaps ?? [])[0];
  return g ? `Dafür fehlt ${g.field_label} bei «${g.record_label}».` : 'Geht in dieser Lage nicht.';
}

/**
 * **Passen die Stücke nicht mehr, bleibt nur «Stornieren»** – die gewohnte Handlung der
 * Stufe steht gesperrt da, mit dem Satz, warum.
 */
function lockedOf(d: Filled): Primary | null {
  const why = d.locked ?? '';
  if (d.stage === VOUCHER_STAGE.offer) return { label: d.ask_verb, icon: SendIcon, problem: why, run: () => {} };
  if (d.stage === VOUCHER_STAGE.agreed) return { label: d.charge_word, icon: FileText, problem: why, run: () => {} };
  if (d.stage === VOUCHER_STAGE.billed) return { label: d.payment_word, icon: Wallet, problem: why, run: () => {} };
  return null;
}

/**
 * **Mahnen** – nur, wo eine Stufe ansteht (`remind_word`); möglich ab `remind_from`. Davor
 * steht der Knopf gesperrt da und sagt, ab wann.
 */
function remindOf(d: Filled): { label: string; problem: string | null } | null {
  if (!d.remind_word || d.locked) return null;
  return {
    label: `${d.remind_word} senden`,
    problem: may(d, 'remind') ? null
      : (d.remind_from ? `Möglich ab ${day(d.remind_from)}` : 'Gerade nicht möglich'),
  };
}

function MainButton({ label, icon: Icon, busy, problem, quiet, onClick }: {
  label: string; icon: LucideIcon; busy: boolean; problem?: string | null; quiet?: boolean;
  onClick: () => void;
}) {
  const button = (
    <button type="button" disabled={busy || !!problem} onClick={onClick}
      className={`erp-actbtn ${quiet ? 'erp-actbtn-neutral' : 'erp-actbtn-primary'}`}
      style={{ height: ACT_H.stage, fontSize: 14, padding: '0 20px' }}>
      <Icon size={16} /> {label}
    </button>
  );
  // Der Grund hängt an einer Hülle – ein gesperrter Knopf bekommt keine Zeigerereignisse.
  return problem ? <span data-tip={problem} className="inline-flex">{button}</span> : button;
}

/**
 * **Was in der Leiste selbst gefragt wird** – der Grund des Ausbuchens (eine Entgelts-
 * minderung, MWST anteilig korrigiert) und der Grund eines Stornos (intern, freiwillig).
 */
function InlineForm(p: FooterProps & { form: Form }) {
  const { d, busy, form } = p;
  const set = (patch: Record<string, string>) => p.setForm({ ...form, f: { ...form.f, ...patch } });
  const problem = formProblem(form, d);
  let body: ReactNode;
  if (form.kind === 'writeoff') {
    body = (
      <>
        <div>
          <Label>Grund</Label>
          <Segmented value={form.f.reason ?? ''} onChange={(reason) => set({ reason })}
            options={(d.write_off_reasons ?? []).map((r) => ({ value: r.key, label: r.label }))} />
        </div>
        <span style={{ fontSize: 12, color: 'var(--fg-3)' }}>
          Jeder Grund ist rechtlich dasselbe: eine Entgeltsminderung. Die MWST wird anteilig
          korrigiert (Art. 41 MWSTG).
        </span>
      </>
    );
  } else {
    body = (
      <div>
        <Label>Grund (freiwillig)</Label>
        <input className={inputCls} value={form.f.note ?? ''} autoFocus aria-label="Grund"
          placeholder="z. B. Kulanz, zurückgezogen"
          onChange={(e) => set({ note: e.target.value })} />
      </div>
    );
  }
  return (
    <div className="flex flex-col" style={{ gap: 10 }}>
      {body}
      <div className="flex items-center justify-end" style={{ gap: 8 }}>
        {form.kind === 'revoke' ? (
          <span {...(problem ? { 'data-tip': problem } : {})} className="inline-flex">
            <button type="button" className="erp-actbtn erp-actbtn-danger" disabled={busy || !!problem}
              style={{ height: ACT_H.stage, fontSize: 14, padding: '0 20px' }}
              onClick={() => { void p.onAction(formBody(form, d)); p.setForm(null); }}>
              <CircleSlash size={16} /> {formWord(form, d)}
            </button>
          </span>
        ) : (
          <MainButton label={formWord(form, d)} icon={Check} busy={busy} problem={problem}
            onClick={() => { void p.onAction(formBody(form, d)); p.setForm(null); }} />
        )}
        <ActionButton icon={X} label="Abbrechen" height={ACT_H.stage} square
          onClick={() => p.setForm(null)} />
      </div>
    </div>
  );
}
