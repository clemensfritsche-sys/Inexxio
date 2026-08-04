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

  const drift = (data?.snapshot?.instanzen as InstanceRow[] | undefined)
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
  instanz: number; artikel?: string; menge: number; zustand: string;
  erzeugt_von?: string; festes_subjekt_von?: string | null;
  'ansprüche'?: Record<string, number>; 'gehört_diesem_auftrag'?: number;
  journal_kontostand?: Record<string, number>; drift?: string[];
};
type StepRow = { nr: number; modul: string; zustand: string; beleg?: string | null };
type SubRow = { objektnummer: number; art?: string | null; status: string };

/**
 * **Der Befund – Klartext zuerst.** Oben die drei, vier Sätze, die die Frage «warum geht es
 * nicht weiter?» beantworten; darunter die Belege dafür. Wer nur wissen will, was los ist,
 * liest die ersten Zeilen und ist fertig.
 */
function Findings({ data }: { data: OrderDiagnostics }) {
  const s = (data.snapshot ?? {}) as {
    zusammenfassung?: string[]; auftrag?: Record<string, unknown>; schritte?: StepRow[];
    fehlmenge?: Record<string, number>; unter_aufträge?: SubRow[];
    instanzen?: InstanceRow[]; ruht?: boolean;
  };
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginBottom: 12 }}>
      {(s.zusammenfassung ?? []).length > 0 && (
        <div style={{ padding: '10px 12px', borderRadius: 'var(--r-md)',
          background: 'var(--bg-2)', display: 'flex', flexDirection: 'column', gap: 4 }}>
          {(s.zusammenfassung ?? []).map((t, i) => (
            <span key={i} style={{ font: `${i === 0 ? '700' : '500'} 12.5px var(--font-body)`,
              color: t.startsWith('⚠') ? 'var(--danger)' : 'var(--fg-2)' }}>{t}</span>
          ))}
        </div>
      )}
      <Line label="Schritte">
        {(s.schritte ?? []).map((st) => `${st.modul}: ${st.zustand}`).join(' → ') || '—'}
      </Line>
      <Line label="Unter-Aufträge">
        {(s.unter_aufträge ?? []).map((o) =>
          `${o.art ?? '—'} ${formatObjectId(o.objektnummer)} (${o.status})`).join(' · ') || 'keine'}
      </Line>
      {(s.instanzen ?? []).map((i) => (
        <Line key={i.instanz} label={`Instanz ${formatObjectId(i.instanz)}`}>
          <span style={{ display: 'block' }}>
            {i.menge} · {i.zustand}
            {i['gehört_diesem_auftrag'] != null && ` · hier ${i['gehört_diesem_auftrag']}`}
          </span>
          <span style={{ display: 'block', color: 'var(--fg-4)' }}>
            Journal: {Object.entries(i.journal_kontostand ?? {})
              .map(([k, v]) => `${v} × ${k}`).join(' · ') || '—'}
          </span>
          {Object.keys(i['ansprüche'] ?? {}).length > 0 && (
            <span style={{ display: 'block', color: 'var(--fg-4)' }}>
              Ansprüche: {Object.entries(i['ansprüche'] ?? {})
                .map(([k, v]) => `${v} × ${k}`).join(' · ')}
            </span>
          )}
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
            <span style={{ flex: 1, minWidth: 0, color: 'var(--fg-2)', wordBreak: 'break-word' }}>
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

/**
 * **Der Bericht: erst der Klartext, dann die Belege.** Wer ihn liest (Mensch oder
 * Entwicklungs-Sitzung), soll in den ersten Zeilen wissen, worum es geht – die Rohwerte
 * stehen darunter für den, der nachrechnen will.
 */
function asMarkdown(d: OrderDiagnostics): string {
  const s = (d.snapshot ?? {}) as { zusammenfassung?: string[] } & Record<string, unknown>;
  const lines: string[] = [
    `## Systemprotokoll ${formatObjectId(d.order_object_id)}`,
    '',
    ...(s.zusammenfassung ?? []).map((t) => `- ${t}`),
    '',
    `_Erzeugt ${d.generated_at} · Build ${process.env.NEXT_PUBLIC_COMMIT_SHA ?? 'unbekannt'}_`,
    '',
    '### Chronologie',
    '',
    '| Zeit | Quelle | Was ist passiert | Objekt | Wer |',
    '|---|---|---|---|---|',
  ];
  for (const e of d.entries ?? []) {
    lines.push(`| ${e.at ?? ''} | ${e.source} | ${e.summary.replace(/\|/g, '\\|')} `
      + `| ${e.object_id ?? ''} | ${e.actor ?? ''} |`);
  }
  if (d.truncated) lines.push('', '> Gekappt – ältere Einträge fehlen.');
  lines.push(
    '',
    '<details><summary>Rohdaten (Befund · Anteile · Detailwerte)</summary>',
    '',
    '```json',
    JSON.stringify({ befund: s, anteile: d.share_map ?? {},
      details: (d.entries ?? []).map((e) => ({ at: e.at, kind: e.kind, detail: e.detail })) },
      null, 2),
    '```',
    '',
    '</details>',
  );
  return lines.join('\n');
}
