'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import type { CSSProperties, ReactNode } from 'react';
import { AlertTriangle } from 'lucide-react';
import { api } from '@/lib/api';
import { day } from '@/lib/when';
import { ObjId } from '@/components/erp/obj-id';
import type { VoucherCorrectable, VoucherSide } from '@/types';
import {
  DocFind, DocPick, DocRef, LABEL, Missing, Section, may,
} from './shared';
import type { Filled, Send } from './shared';

/**
 * ►►► **Wer im Kopf steht – EINE Gegenpartei** (entschieden am 24.10.2026). ◄◄◄
 *
 * Auf einem Beleg steht genau ein Leistungsempfänger bzw. -erbringer. Steht er fest (der
 * Adressat, `side.object_id`), ist er es; sonst der Kandidat, den man im Angebotsspiegel
 * angeklickt hat (`shown`), sonst der erste. Die Kandidaten selbst stehen nur als Zeilen
 * im Angebotsspiegel – dort wird angeboten, angenommen, abgesagt.
 */
export function headOf(d: Filled, shown: number | null): VoucherSide | null {
  const theirs = [d.supplier, d.customer].find((s) => s && !s.ours) ?? null;
  const list = d.recipients ?? [];
  if (theirs?.object_id != null) return theirs;
  return list.find((r) => r.object_id === shown) ?? list[0] ?? theirs;
}

/**
 * **Die Parteien** – «Von» und «An» nebeneinander, getrennt durch eine Haarlinie. Je Seite:
 * Name mit Nummer, «z. H.», die beiden Anschriften nebeneinander (Rechnung · Lieferung
 * bzw. Versand), der Kontakt unter einer gestrichelten Linie. Wählbar ist, was der Server
 * als `choice` mitgibt (geschäftlich/privat, Anschriften) – nur vor der Zusage.
 */
export function Parties({ d, shown, orderObjectId, stepId, onAction }: {
  d: Filled; shown: number | null; orderObjectId: number; stepId: number; onAction: Send;
}) {
  const head = headOf(d, shown);
  const sides = [d.supplier, d.customer].map((s) => (s && !s.ours ? head ?? s : s));
  return (
    <Section title={d.parties_title} first>
      <div className="flex flex-col" style={{ gap: 14, minWidth: 0 }}>
        <Correction d={d} orderObjectId={orderObjectId} stepId={stepId}
          onAction={onAction} />
        <div style={{
          display: 'grid', gridTemplateColumns: 'minmax(0, 1fr) minmax(0, 1fr)',
          gridTemplateRows: `repeat(${SIDE_ROWS}, auto)`, minWidth: 0,
        }}>
          {sides.map((s, i) => (
            <Side key={i} side={s ?? null} role={roleOf(d, i)} d={d}
              second={i === 1} onAction={onAction} />
          ))}
        </div>
        <Gaps rows={d.gaps ?? []} />
      </div>
    </Section>
  );
}

/** Die Rolle einer Seite, auch wenn sie leer ist («Von» · «An» kommen vom Server). */
function roleOf(d: Filled, index: number): { label: string; hint: string } {
  const s = index === 0 ? d.supplier : d.customer;
  return { label: s?.label ?? (index === 0 ? 'Von' : 'An'), hint: s?.hint ?? '' };
}

/** Zeilen je Seite: Rolle · Name · z. H. · Anschriften · Kontakt – auf gleicher Höhe. */
const SIDE_ROWS = 5;

const NAME_FACE: CSSProperties = { font: '600 15px var(--font-body)', color: 'var(--fg-1)' };

function Side({ side, role, d, second, onAction }: {
  side: VoucherSide | null; role: { label: string; hint: string }; d: Filled;
  second: boolean; onAction: Send;
}) {
  return (
    <div style={{
      display: 'grid', gridRow: `span ${SIDE_ROWS}`, gridTemplateRows: 'subgrid',
      rowGap: 4, minWidth: 0, alignContent: 'start',
      ...(second
        ? { paddingLeft: 24, borderLeft: '1px solid var(--border-1)' }
        : { paddingRight: 24 }),
    }}>
      <span style={LABEL} {...(role.hint ? { 'data-tip': role.hint } : {})}>{role.label}</span>
      <span className="flex items-baseline" style={{ gap: 8, minWidth: 0 }}>
        <SideName side={side} d={d} onAction={onAction} />
        {side?.object_id != null && (
          <span style={{ flex: 'none' }}><ObjId value={side.object_id} /></span>
        )}
      </span>
      <Attn side={side} />
      <Addresses side={side} onAction={onAction} />
      <Contact side={side} />
    </div>
  );
}

/** Die beiden Antworten auf «geschäftlich oder privat?» – Werte des Wählers. */
const FIRM = 'firm';
const PERSON = 'person';

/**
 * **Der Name – und wo es eine Wahl gibt, IST er die Wahl**: der gedruckte Name sagt, ob
 * der Beleg an die Firma (z. H. der Person) oder an die Person privat geht.
 */
function SideName({ side, d, onAction }: { side: VoucherSide | null; d: Filled; onAction: Send }) {
  if (!side) return <span style={{ ...NAME_FACE, color: 'var(--fg-3)' }}>—</span>;
  if (side.ours) return <Issuer d={d} side={side} onAction={onAction} />;
  const c = side.choice;
  if (c?.company) {
    return (
      <DocPick on value={c.bill_to_company ? FIRM : PERSON}
        text={side.name || c.person} aria="Rechnung an"
        tip="Geschäftlich oder privat – der gedruckte Name ist die Wahl" face={NAME_FACE}
        options={[{ value: FIRM, label: `${c.company} – geschäftlich` },
                  { value: PERSON, label: `${c.person} – privat` }]}
        onChange={(v) => void onAction({ action: 'address', bill_to_company: v === FIRM })} />
    );
  }
  if (!side.name && side.object_id == null) {
    return <span style={{ ...NAME_FACE, color: 'var(--fg-3)' }}>—</span>;
  }
  return (
    <span className="truncate" style={{ ...NAME_FACE, minWidth: 0 }}>
      {side.name || <Missing what="Name" />}
    </span>
  );
}

/** «z. H. …» – oder «privat», wo die Person für sich selbst handelt und es eine Wahl gab. */
function Attn({ side }: { side: VoucherSide | null }) {
  const text = side?.attn || (side?.choice?.company && !side.choice.bill_to_company
    ? 'privat' : '');
  return text
    ? <span style={{ fontSize: 12, color: 'var(--fg-2)' }}>{text}</span>
    : <div />;
}

/** Die beiden Anschriften nebeneinander – Rechnung und Lieferung bzw. Versand. */
function Addresses({ side, onAction }: { side: VoucherSide | null; onAction: Send }) {
  if (!side || (!(side.address ?? []).length && !(side.shipping ?? []).length)) {
    return <div>{side?.object_id != null ? <Missing what="Anschrift" /> : null}</div>;
  }
  return (
    <div style={{
      display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(110px, 1fr))',
      gap: 12, marginTop: 6, minWidth: 0,
    }}>
      <Anschrift label={side.address_label} lines={side.address ?? []} side={side}
        pick={side.choice?.billing_address_id}
        onPick={(id) => void onAction({ action: 'address', billing_address: id })} />
      {(side.shipping ?? []).length > 0 && (
        <Anschrift label={side.shipping_label} lines={side.shipping ?? []} side={side}
          pick={side.choice?.delivery_address_id}
          onPick={(id) => void onAction({ action: 'address', delivery_address: id })} />
      )}
    </div>
  );
}

/**
 * **Eine Anschrift als Zeilen** – mit Beschriftung. Wo das Adressbuch des gewählten Kontos
 * mehr als eine kennt, ist sie die Wahl (`DocPick`); vorbelegt ist der Standard.
 */
function Anschrift({ label, lines, side, pick, onPick }: {
  label?: string | null; lines: string[]; side: VoucherSide;
  pick?: number | null; onPick: (id: number) => void;
}) {
  const face: CSSProperties = { fontSize: 12.5, color: 'var(--fg-1)', lineHeight: 1.45,
                                whiteSpace: 'pre-line' };
  const options = side.choice?.options ?? [];
  return (
    <span className="flex flex-col" style={{ gap: 2, minWidth: 0 }}>
      {label && <span style={{ ...LABEL, fontSize: 10.5 }}>{label}</span>}
      {options.length > 1 ? (
        <DocPick on value={String(pick ?? '')} text={lines.join('\n')} face={face}
          aria={label ?? 'Anschrift'} tip="Andere Anschrift aus dem Adressbuch wählen"
          options={[...(pick == null ? [{ value: '', label: '—' }] : []),
                    ...options.map((o) => ({ value: String(o.id), label: o.label }))]}
          onChange={(v) => { if (v) onPick(Number(v)); }} />
      ) : (
        <span style={face}>{lines.join('\n') || '—'}</span>
      )}
    </span>
  );
}

/** Kontakt unter einer gestrichelten Linie – E-Mail und Telefon untereinander, dann die UID. */
function Contact({ side }: { side: VoucherSide | null }) {
  const reach = [side?.email, side?.phone].filter(Boolean).join('\n');
  return (
    <div className="flex flex-col" style={{
      gap: 3, marginTop: 6, paddingTop: 10, borderTop: '1px dashed var(--border-1)',
    }}>
      {reach && (
        <span style={{ fontSize: 12, color: 'var(--fg-3)', whiteSpace: 'pre-line' }}>{reach}</span>
      )}
      {side?.uid && <span style={{ fontSize: 12, color: 'var(--fg-3)' }}>{side.uid}</span>}
    </div>
  );
}

/**
 * **Welche unserer Gesellschaften den Beleg stellt** – wählbar, solange `can` es sagt; die
 * Liste reist mit dem Vorgang und wird in ihr gesucht.
 */
function Issuer({ d, side, onAction }: { d: Filled; side: VoucherSide; onAction: Send }) {
  const options = useMemo(() => (d.issuers ?? [])
    .filter((o) => o.object_id != null)
    .map((o) => ({ object_id: o.object_id as number, name: o.name })), [d.issuers]);
  const find = useCallback(async (q: string) => options.filter((o) => !q.trim()
    || o.name.toLowerCase().includes(q.toLowerCase())
    || String(o.object_id).includes(q.trim())), [options]);
  const chosen = options.find((o) => o.object_id === d.issuer) ?? null;
  return (
    <DocRef on={may(d, 'issuer')} text={side.name || <Missing what="Firma" />}
      placeholder={d.issuer_label} tip={d.issuer_label} face={NAME_FACE}
      value={d.issuer ?? null} selected={chosen} find={find}
      onChange={(n) => void onAction({ action: 'issuer', issuer: n })} />
  );
}

/** Kein Verweis – die erste Zeile der Suche. */
const NO_CORRECTION = '';

/**
 * **«Korrektur zu …» — welche Rechnung diese Gutschrift mindert.** Vorgeschlagen werden
 * die Rechnungen, über die diese Stücke liefen (`corrects_suggested`, aus dem Log); weiter
 * gesucht wird auf dem Server, auch über Auftragsgrenzen. Die Zeile steht nur, wo es eine
 * Rechnung zu mindern gibt oder eine gesetzt ist.
 */
function Correction({ d, orderObjectId, stepId, onAction }: {
  d: Filled; orderObjectId: number; stepId: number; onAction: Send;
}) {
  const [found, setFound] = useState<boolean | null>(null);
  const on = may(d, 'correct');
  const suggested = d.corrects_suggested ?? [];
  const label = useCallback((r: VoucherCorrectable) => [
    r.number ?? `Beleg ${r.id}`,
    r.billed_on ? `vom ${day(r.billed_on)}` : null,
    r.amount ? `${r.amount} ${r.currency}` : null,
  ].filter(Boolean).join(' · '), []);
  const search = useCallback((query: string) => api.voucherCorrectable(orderObjectId, stepId, query)
    .then((rows) => rows.map((r) => ({ value: String(r.id), label: label(r) }))),
  [orderObjectId, stepId, label]);
  useEffect(() => {
    if (!on || suggested.length) return;
    let stale = false;
    void api.voucherCorrectable(orderObjectId, stepId)
      .then((r) => { if (!stale) setFound(r.length > 0); })
      .catch(() => { if (!stale) setFound(false); });
    return () => { stale = true; };
  }, [on, suggested.length, orderObjectId, stepId]);

  if (!d.corrects && (!on || (!suggested.length && found !== true))) return null;
  const text = d.corrects
    ? [d.corrects.number ?? `Beleg ${d.corrects.id}`,
       d.corrects.billed_on ? `vom ${day(d.corrects.billed_on)}` : null]
      .filter(Boolean).join(' · ')
    : '—';
  return (
    <span className="flex items-baseline" style={{ gap: 8, minWidth: 0 }}>
      <span style={LABEL}>{d.corrects_label}</span>
      <DocFind on={on} value={d.corrects ? String(d.corrects.id) : NO_CORRECTION}
        text={text} placeholder="Rechnungsnummer" tip={d.corrects_hint}
        face={{ fontSize: 12.5, color: 'var(--fg-1)' }} emptyOption="keine"
        missing={!d.corrects}
        options={d.corrects
          ? [{ value: String(d.corrects.id), label: text }]
          : suggested.map((r) => ({ value: String(r.id), label: label(r) }))}
        search={search}
        onChange={(v) => void onAction({
          action: 'correct', corrects: v === NO_CORRECTION ? null : Number(v),
        })} />
    </span>
  );
}

/**
 * **Was fehlt, um weiterzukommen** – `DataGap`: wo es hingehört (die Nummer ist der Weg
 * dorthin), was fehlt und warum dieser Beleg es braucht. Eine Zeile, kein Zustand.
 */
function Gaps({ rows }: { rows: NonNullable<Filled['gaps']> }): ReactNode {
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
          <span style={{ fontSize: 11.5, color: 'var(--fg-3)', paddingLeft: 18 }}>{g.why}</span>
        </div>
      ))}
    </div>
  );
}
