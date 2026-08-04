'use client';

import { useState } from 'react';
import { AlertTriangle, Bug, ChevronDown, ChevronRight, Copy, RefreshCw } from 'lucide-react';
import type { DiagnosticEntry, OrderDiagnostics } from '@/types';
import { api } from '@/lib/api';
import { formatObjectId, localDateTime } from '@/lib/utils';

/**
 * **Das Systemprotokoll eines Auftrags – für die Fehlersuche, nicht für den Betrieb.**
 *
 * Der Abschnitt «Verlauf» darüber beantwortet die **fachliche** Frage «was ist passiert?»
 * (die Material-Buchungen). Wenn etwas schiefgeht, lautet die Frage aber eine Ebene tiefer:
 * *welcher Mechanismus* hat das erzeugt, in welcher Reihenfolge, und stimmen die
 * abgeleiteten Grössen untereinander noch?
 *
 * Darum stehen hier **drei Ströme nebeneinander** – und zwar die, die es ohnehin gibt
 * (keine vierte Wahrheit):
 *
 *     Audit     wer hat welches Feld geändert          → Absicht
 *     Ereignis  welches fachliche Ereignis lief los    → Wirkung
 *     Journal   wo ist das Material hin                → Bestand (ADR 007)
 *
 * dazu der **Befund**: der abgeleitete Zustand zum Abfragezeitpunkt (Schritte, Fehlmenge,
 * Anteile, Kontostand je Instanz) samt **Drift-Prüfung**. Ein Bug ist fast immer ein
 * Widerspruch zwischen zwei dieser Angaben – nebeneinander gestellt sieht man ihn sofort.
 *
 * **Berichten in einem Klick**: «Als Markdown kopieren» erzeugt einen vollständigen Bericht
 * (Befund + Chronologie), der in eine Entwicklungs-Sitzung eingefügt werden kann – dieselbe
 * Brücke wie bei den Testnotizen, nur für den Maschinenzustand statt für das Pixel.
 *
 * Geladen wird **auf Klick**, nicht mit dem Auftrag: eine Diagnose ist um Grössenordnungen
 * umfangreicher als der Datensatz und interessiert nur, wenn etwas nicht stimmt.
 */
export function OrderDiagnosticsPanel({ objectId }: { objectId: number }) {
  const [open, setOpen] = useState(false);
  const [data, setData] = useState<OrderDiagnostics | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const load = async () => {
    setBusy(true); setErr(null);
    try {
      setData(await api.getOrderDiagnostics(objectId));
    } catch (e) {
      setErr(e instanceof Error ? e.message : 'Systemprotokoll nicht ladbar');
    } finally {
      setBusy(false);
    }
  };

  const toggle = () => {
    const next = !open;
    setOpen(next);
    if (next && !data && !busy) void load();
  };

  const copy = async () => {
    if (!data) return;
    await navigator.clipboard.writeText(asMarkdown(data));
    setCopied(true);
    setTimeout(() => setCopied(false), 1600);
  };

  const drift = (data?.snapshot?.instances as InstanceRow[] | undefined)
    ?.flatMap((i) => i.drift ?? []) ?? [];

  return (
    <div style={{ marginTop: 14, border: '1px solid var(--border-1)',
      borderRadius: 'var(--r-lg)', background: '#fff', overflow: 'hidden' }}>
      <button type="button" onClick={toggle}
        style={{ width: '100%', display: 'flex', alignItems: 'center', gap: 9,
          padding: '11px 14px', background: 'none', border: 'none', cursor: 'pointer',
          textAlign: 'left' }}>
        {open ? <ChevronDown size={15} style={{ color: 'var(--fg-4)' }} />
              : <ChevronRight size={15} style={{ color: 'var(--fg-4)' }} />}
        <Bug size={15} style={{ color: 'var(--fg-3)' }} />
        <span style={{ font: '700 10px var(--font-body)', textTransform: 'uppercase',
          letterSpacing: '0.06em', color: 'var(--fg-3)', flex: 1 }}>Systemprotokoll</span>
        {drift.length > 0 && (
          <span title={drift.join('\n')} style={{ display: 'inline-flex', alignItems: 'center',
            gap: 5, font: '600 11px var(--font-body)', color: 'var(--danger)' }}>
            <AlertTriangle size={13} /> {drift.length} Abweichung(en)
          </span>
        )}
      </button>

      {open && (
        <div style={{ borderTop: '1px solid var(--border-1)', padding: '12px 14px 14px' }}>
          <div style={{ display: 'flex', gap: 8, marginBottom: 10 }}>
            <button type="button" onClick={load} disabled={busy} className="erp-actbtn">
              <RefreshCw size={13} /> {busy ? 'lädt …' : 'Aktualisieren'}
            </button>
            <button type="button" onClick={copy} disabled={!data} className="erp-actbtn"
              title="Befund + Chronologie als Markdown – zum Einfügen in einen Fehlerbericht">
              <Copy size={13} /> {copied ? 'kopiert' : 'Als Markdown kopieren'}
            </button>
          </div>
          {err && <div style={{ color: 'var(--danger)', fontSize: 12.5 }}>{err}</div>}
          {data && <Findings data={data} />}
          {data && <Entries rows={data.entries ?? []} truncated={!!data.truncated} />}
        </div>
      )}
    </div>
  );
}

// ─── Befund ───────────────────────────────────────────────────────────────────

type InstanceRow = {
  instance: number; quality: string; disposition: string; quantity: number;
  creator_order?: number | null; subject_of_order?: number | null;
  reservations?: Record<string, number>; held_by_this_order?: number;
  ledger_lots?: Record<string, number>; drift?: string[];
};
type StepRow = { step_id: number; type: string; state: string; fact_status?: string | null };
type SubRow = { object_id: number; reason?: string | null; status: string };

/** Der abgeleitete Zustand – kompakt, aber vollständig genug für einen Bericht. */
function Findings({ data }: { data: OrderDiagnostics }) {
  const s = (data.snapshot ?? {}) as {
    order?: Record<string, unknown>; steps?: StepRow[]; shortfall?: Record<string, number>;
    sub_orders?: SubRow[]; instances?: InstanceRow[]; paused?: boolean;
  };
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginBottom: 12 }}>
      <Line label="Auftrag">
        {String(s.order?.status ?? '—')}
        {s.order?.reason ? ` · ${String(s.order.reason)}` : ''}
        {s.paused ? ' · ruht (Fehlmenge)' : ''}
      </Line>
      <Line label="Schritte">
        {(s.steps ?? []).map((st) => `${st.type}:${st.state}`).join(' → ') || '—'}
      </Line>
      <Line label="Fehlmenge">
        {Object.keys(s.shortfall ?? {}).length
          ? Object.entries(s.shortfall ?? {}).map(([a, q]) => `Artikel ${a}: ${q}`).join(' · ')
          : 'keine'}
      </Line>
      <Line label="Unter-Aufträge">
        {(s.sub_orders ?? []).map((o) =>
          `${o.reason ?? '—'} ${formatObjectId(o.object_id)} (${o.status})`).join(' · ') || 'keine'}
      </Line>
      {(s.instances ?? []).map((i) => (
        <Line key={i.instance} label={`Instanz ${formatObjectId(i.instance)}`}>
          <span style={{ display: 'block' }}>
            {i.quantity} · {i.quality}/{i.disposition}
            {i.held_by_this_order != null && ` · hier ${i.held_by_this_order}`}
          </span>
          <span style={{ display: 'block', color: 'var(--fg-4)' }}>
            Ansprüche: {JSON.stringify(i.reservations ?? {})} · Journal:{' '}
            {JSON.stringify(i.ledger_lots ?? {})}
          </span>
          {(i.drift ?? []).length > 0 && (
            <span style={{ display: 'block', color: 'var(--danger)' }}>
              ⚠ {(i.drift ?? []).join(' · ')}
            </span>
          )}
        </Line>
      ))}
    </div>
  );
}

function Line({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div style={{ display: 'flex', gap: 10, alignItems: 'baseline',
      font: '500 12px var(--font-body)', color: 'var(--fg-2)' }}>
      <span style={{ minWidth: 132, flexShrink: 0, font: '700 10px var(--font-body)',
        textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--fg-4)' }}>{label}</span>
      <span style={{ minWidth: 0, wordBreak: 'break-word' }}>{children}</span>
    </div>
  );
}

// ─── Chronologie ──────────────────────────────────────────────────────────────

const SOURCE: Record<string, { label: string; color: string; bg: string }> = {
  audit: { label: 'Audit', color: 'var(--fg-3)', bg: 'var(--bg-2)' },
  event: { label: 'Ereignis', color: 'var(--warning)', bg: 'var(--warning-bg, var(--bg-2))' },
  journal: { label: 'Journal', color: 'var(--success)', bg: 'var(--bg-2)' },
};

function Entries({ rows, truncated }: { rows: DiagnosticEntry[]; truncated: boolean }) {
  if (rows.length === 0) return <div style={{ fontSize: 12.5, color: 'var(--fg-4)' }}>Keine Einträge.</div>;
  return (
    <div className="ix-noscrollbar" style={{ maxHeight: 420, overflowY: 'auto',
      borderTop: '1px solid var(--border-1)' }}>
      {rows.map((e, i) => {
        const cfg = SOURCE[e.source] ?? SOURCE.audit;
        return (
          <div key={i} title={e.detail ? JSON.stringify(e.detail, null, 2) : undefined}
            style={{ display: 'flex', gap: 10, alignItems: 'baseline', padding: '6px 0',
              borderBottom: '1px solid var(--border-1)', font: '500 12px var(--font-body)' }}>
            <span style={{ width: 118, flexShrink: 0, color: 'var(--fg-4)',
              fontVariantNumeric: 'tabular-nums' }}>{e.at ? localDateTime(e.at) : '—'}</span>
            <span style={{ width: 62, flexShrink: 0, font: '700 10px var(--font-body)',
              textTransform: 'uppercase', letterSpacing: '0.05em', color: cfg.color }}>
              {cfg.label}
            </span>
            <span style={{ width: 170, flexShrink: 0, font: '600 11.5px var(--font-mono), monospace',
              color: 'var(--fg-2)', overflow: 'hidden', textOverflow: 'ellipsis',
              whiteSpace: 'nowrap' }}>{e.kind}</span>
            <span style={{ flex: 1, minWidth: 0, color: 'var(--fg-3)', wordBreak: 'break-word' }}>
              {e.summary}
              {e.object_id != null && (
                <span style={{ marginLeft: 6, font: '500 11px var(--font-mono), monospace',
                  color: 'var(--fg-4)' }}>{formatObjectId(e.object_id)}</span>
              )}
              {e.actor && <span style={{ marginLeft: 6, color: 'var(--fg-4)' }}>· {e.actor}</span>}
            </span>
          </div>
        );
      })}
      {truncated && (
        <div style={{ padding: '6px 0', fontSize: 12, color: 'var(--fg-4)' }}>
          … gekappt (Deckel erreicht) – ältere Einträge fehlen.
        </div>
      )}
    </div>
  );
}

// ─── Bericht ──────────────────────────────────────────────────────────────────

/** Vollständiger Bericht: Befund + Chronologie. Was hier steht, muss niemand nachfragen. */
function asMarkdown(d: OrderDiagnostics): string {
  const s = (d.snapshot ?? {}) as Record<string, unknown>;
  const lines: string[] = [
    `## Systemprotokoll Auftrag ${formatObjectId(d.order_object_id)}`,
    '',
    `- **Erzeugt:** ${d.generated_at}`,
    `- **Build:** ${process.env.NEXT_PUBLIC_COMMIT_SHA ?? 'unbekannt'}`,
    '',
    '### Befund',
    '',
    '```json',
    JSON.stringify(s, null, 2),
    '```',
    '',
    '### Anteile',
    '',
    '```json',
    JSON.stringify(d.share_map ?? {}, null, 2),
    '```',
    '',
    '### Chronologie',
    '',
    '| Zeit | Quelle | Was | Detail | Objekt | Wer |',
    '|---|---|---|---|---|---|',
  ];
  for (const e of d.entries ?? []) {
    const detail = e.detail ? JSON.stringify(e.detail).replace(/\|/g, '\\|') : '';
    lines.push(`| ${e.at ?? ''} | ${e.source} | \`${e.kind}\` | ${e.summary} ${detail} `
      + `| ${e.object_id ?? ''} | ${e.actor ?? ''} |`);
  }
  if (d.truncated) lines.push('', '> Gekappt – ältere Einträge fehlen.');
  return lines.join('\n');
}
