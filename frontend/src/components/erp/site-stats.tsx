'use client';

import { useState, type ReactNode } from 'react';
import { useQuery, keepPreviousData } from '@tanstack/react-query';
import { Inbox, Phone, Users, Percent, Mail, TrendingUp, Compass, Map as MapIcon, FileText,
         ListChecks, Smartphone, Gauge, MessageSquareText } from 'lucide-react';
import { api } from '@/lib/api';
import { qk } from '@/lib/queries';
import type { SiteStats as Stats } from '@/types';
import { Card, DetailBody } from '@/components/erp/detail-frame';
import { Segmented } from '@/components/erp/controls';
import { Skeleton } from '@/components/erp/skeleton';
import { useErpNav } from '@/components/erp/obj-id';
import { EUROPE } from '@/lib/europe-map';
import { formatAmount } from '@/lib/utils';
import { NOTHING, dayShort, when, formatWhen } from '@/lib/when';

/**
 * ►►► **Der Reiter «Website» am Betreiber** – was bringt Anfragen? ◄◄◄
 *
 * Eine Ableitung vom Server (`GET /erp/site-stats`, `services/site_stats_view`): ohne Cookies,
 * ohne IP; ein **Besuch** ist ein Besucher an einem Tag. Zuerst, was zählt (Anfragen, Anrufe),
 * dann woher (Quellen, Karte), dann wo (Seiten, Formular), zuletzt die Technik (Ladezeit).
 * Die Oberfläche rechnet nichts nach, sie stellt dar.
 */

const PERIODS = [
  { value: '7', label: '7 Tage' }, { value: '30', label: '30 Tage' },
  { value: '90', label: '90 Tage' }, { value: '365', label: '12 Monate' },
];
const n = (v: number) => formatAmount(v, 0);
const pct = (a: number, b: number) => (b ? `${formatAmount((a / b) * 100, 1)} %` : NOTHING);
const NUM: React.CSSProperties = { fontVariantNumeric: 'tabular-nums' };
const MUTED: React.CSSProperties = { color: 'var(--fg-3)', fontSize: 12.5 };

let regions: Intl.DisplayNames | null = null;
/** Ein Land als Klarname («CH» → «Schweiz»). */
function countryName(code: string): string {
  if (!code) return 'Unbekannt';
  try {
    regions ??= new Intl.DisplayNames(['de-CH'], { type: 'region' });
    return regions.of(code) ?? code;
  } catch { return code; }
}

export function SiteStats() {
  const [days, setDays] = useState('30');
  const q = useQuery({
    queryKey: qk.siteStats(Number(days)),
    queryFn: ({ signal }) => api.siteStats(Number(days), { signal }),
    placeholderData: keepPreviousData,
    meta: { what: 'Website-Statistik' },
  });
  const s = q.data;
  return (
    <DetailBody gap={16}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap' }}>
        <Segmented value={days} onChange={setDays} options={PERIODS} />
        {s && <span style={MUTED}>{dayShort(s.start)} – {dayShort(s.end)} · ohne Cookies, ohne IP · Personal zählt nicht</span>}
      </div>
      {!s ? <Skeleton rows={8} /> : <Body s={s} />}
    </DetailBody>
  );
}

function Body({ s }: { s: Stats }) {
  const empty = s.totals.visits === 0 && s.totals.inquiries === 0;
  return (
    <>
      {empty && (
        <div style={{ padding: '14px 18px', border: '1px solid var(--border-1)', borderRadius: 12,
                      background: 'var(--bg-1)', color: 'var(--fg-3)', fontSize: 14 }}>
          In diesem Zeitraum ist noch nichts gezählt. Die Website meldet jeden Besuch, sobald sie
          live ist; wer im ERP angemeldet ist, zählt nicht.
        </div>
      )}
      <Kpis s={s} />
      <Trend s={s} />
      <Sources s={s} />
      <Countries s={s} />
      <Pages s={s} />
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 16 }}>
        <Funnel s={s} />
        <Devices s={s} />
      </div>
      <Speed s={s} />
      <Inquiries s={s} />
    </>
  );
}

// ─── Kennzahlen ──────────────────────────────────────────────────────────────

function Delta({ now, before, percent }: { now: number; before: number; percent?: boolean }) {
  const d = now - before;
  if (!d) return <span style={{ ...MUTED }}>wie im Vorzeitraum</span>;
  const tone = d > 0 ? 'var(--success)' : 'var(--danger)';
  const text = percent && before ? `${formatAmount(Math.abs(d / before) * 100, 0)} %` : n(Math.abs(d));
  return <span style={{ color: tone, fontSize: 12.5, ...NUM }}>{d > 0 ? '▲' : '▼'} {text} zum Vorzeitraum</span>;
}

function Kpi({ icon: Icon, label, value, delta, strong, tip }: {
  icon: typeof Inbox; label: string; value: string; delta: ReactNode; strong?: boolean; tip: string;
}) {
  return (
    <div data-tip={tip} style={{ background: 'var(--bg-1)', borderRadius: 12, padding: '14px 16px',
      border: `1px solid ${strong ? 'var(--fg-1)' : 'var(--border-1)'}`, display: 'grid', gap: 2, minWidth: 0 }}>
      <span style={{ display: 'flex', alignItems: 'center', gap: 6, ...MUTED }}><Icon size={14} aria-hidden />{label}</span>
      <b style={{ fontFamily: 'var(--font-display)', fontSize: 28, fontWeight: 600, letterSpacing: '-0.02em', ...NUM }}>{value}</b>
      {delta}
    </div>
  );
}

function Kpis({ s }: { s: Stats }) {
  const t = s.totals, p = s.previous;
  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: 12 }}>
      <Kpi icon={Inbox} strong label="Anfragen" value={n(t.inquiries)} delta={<Delta now={t.inquiries} before={p.inquiries} />}
        tip="Gesendete Anfragen über das Formular – jede ist eine Nachricht im Verlauf der Person." />
      <Kpi icon={Phone} label="Anrufe" value={n(t.calls)} delta={<Delta now={t.calls} before={p.calls} />}
        tip="Klicks auf eine Telefonnummer der Website (auf dem Handy: der Anruf beginnt)." />
      <Kpi icon={Users} label="Besuche" value={n(t.visits)} delta={<Delta now={t.visits} before={p.visits} percent />}
        tip="Ein Besucher an einem Tag – wer morgen wiederkommt, ist ein neuer Besuch (ohne Cookies)." />
      <Kpi icon={Percent} label="Anfrage-Quote" value={pct(t.inquiries, t.visits)}
        delta={<span style={MUTED}>vorher {pct(p.inquiries, p.visits)}</span>}
        tip="Anfragen je Besuch." />
      <Kpi icon={Mail} label="Newsletter" value={n(t.newsletter)} delta={<Delta now={t.newsletter} before={p.newsletter} />}
        tip="Anmeldungen auf der Website (die Bestätigung per Mail folgt)." />
    </div>
  );
}

// ─── Verlauf ─────────────────────────────────────────────────────────────────

function Trend({ s }: { s: Stats }) {
  const W = 640, H = 170, L = 36, B = 22, T = 8;
  const max = Math.max(4, ...s.series.map((d) => d.visits));
  const top = Math.ceil(max / 4) * 4;
  const step = s.series.length > 1 ? (W - L - 8) / (s.series.length - 1) : 0;
  const x = (i: number) => L + i * step;
  const y = (v: number) => T + (H - T - B) * (1 - v / top);
  const line = s.series.map((d, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)} ${y(d.visits).toFixed(1)}`).join(' ');
  const ticks = [0, Math.round((s.series.length - 1) / 2), s.series.length - 1];
  return (
    <Card icon={TrendingUp} title="Besuche und Anfragen" info="Je Tag. Ein roter Punkt: an diesem Tag kam mindestens eine Anfrage.">
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img" aria-label="Besuche je Tag" style={{ display: 'block' }}>
        {[0, 0.5, 1].map((f) => (
          <g key={f}>
            <line x1={L} x2={W - 8} y1={y(top * f)} y2={y(top * f)} stroke="var(--border-1)" />
            <text x={L - 6} y={y(top * f) + 3} textAnchor="end" fontSize="10" fill="var(--fg-3)">{n(top * f)}</text>
          </g>
        ))}
        <path d={`${line} L${x(s.series.length - 1)} ${y(0)} L${L} ${y(0)} Z`} fill="var(--accent)" fillOpacity={0.1} />
        <path d={line} fill="none" stroke="var(--accent)" strokeWidth={1.8} strokeLinejoin="round" />
        {s.series.map((d, i) => d.inquiries > 0 && (
          <circle key={d.day} cx={x(i)} cy={y(d.visits)} r={s.series.length > 120 ? 2.5 : 4} fill="var(--inexxio-red)"
            data-tip={`${dayShort(d.day)} · ${n(d.visits)} Besuche · ${n(d.inquiries)} Anfrage${d.inquiries > 1 ? 'n' : ''}`} />
        ))}
        {ticks.map((i) => s.series[i] && (
          <text key={i} x={x(i)} y={H - 6} textAnchor={i === 0 ? 'start' : i === ticks[2] ? 'end' : 'middle'}
            fontSize="10" fill="var(--fg-3)">{dayShort(s.series[i].day)}</text>
        ))}
      </svg>
    </Card>
  );
}

// ─── Quellen ─────────────────────────────────────────────────────────────────

function Bar({ share, tone = 'var(--accent)' }: { share: number; tone?: string }) {
  return (
    <div style={{ height: 6, borderRadius: 3, background: 'var(--bg-3)', overflow: 'hidden' }}>
      <div style={{ width: `${Math.max(share > 0 ? 2 : 0, share * 100)}%`, height: '100%', background: tone }} />
    </div>
  );
}

function Sources({ s }: { s: Stats }) {
  const [all, setAll] = useState(false);
  const total = s.sources.reduce((a, x) => a + x.visits, 0);
  const max = Math.max(1, ...s.sources.map((x) => x.visits));
  const label = Object.fromEntries(s.channels.map((c) => [c.key, c.label]));
  const byChannel = s.channels.map((c) => ({ ...c,
    visits: s.sources.filter((x) => x.channel === c.key).reduce((a, x) => a + x.visits, 0),
    inquiries: s.sources.filter((x) => x.channel === c.key).reduce((a, x) => a + x.inquiries, 0) }))
    .filter((c) => c.visits || c.inquiries);
  const rows = all ? s.sources : s.sources.slice(0, 10);
  return (
    <Card icon={Compass} title="Woher" info="Jede Quelle erscheint – auch eine unbekannte heisst wie ihre Adresse. Besuche zählen beim Einstieg; Anfragen und Anrufe tragen die Quelle ihres Besuchs.">
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px 16px', fontSize: 13 }}>
        {byChannel.map((c) => (
          <span key={c.key} style={NUM}>
            <b style={{ fontWeight: 600, color: c.key === 'ai' ? 'var(--inexxio-red)' : 'var(--fg-1)' }}>{c.label}</b>{' '}
            <span style={{ color: 'var(--fg-3)' }}>{pct(c.visits, total)} · {n(c.inquiries)} Anfr.</span>
          </span>
        ))}
      </div>
      <div style={{ display: 'grid', gap: 10 }}>
        {rows.map((x) => (
          <div key={x.key} style={{ display: 'grid', gridTemplateColumns: 'minmax(0,1fr) auto', gap: '4px 12px', fontSize: 13.5 }}>
            <span style={{ minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {x.label} <span style={MUTED}>{label[x.channel] ?? ''}</span>
            </span>
            <span style={{ ...NUM, color: 'var(--fg-3)' }} data-tip="Besuche · Anfragen · Anrufe">
              {n(x.visits)} · <b style={{ color: x.inquiries ? 'var(--inexxio-red)' : 'var(--fg-3)' }}>{n(x.inquiries)}</b> · {n(x.calls)}
            </span>
            <div style={{ gridColumn: '1 / -1' }}>
              <Bar share={x.visits / max} tone={x.channel === 'ai' ? 'var(--inexxio-red)' : 'var(--accent)'} />
            </div>
          </div>
        ))}
        {!rows.length && <span style={MUTED}>Noch keine Quelle.</span>}
      </div>
      {s.sources.length > 10 && (
        <button type="button" className="erp-actbtn" onClick={() => setAll(!all)} style={{ alignSelf: 'flex-start' }}>
          {all ? 'Weniger zeigen' : `Alle ${s.sources.length} Quellen`}
        </button>
      )}
    </Card>
  );
}

// ─── Karte ───────────────────────────────────────────────────────────────────

function Countries({ s }: { s: Stats }) {
  const max = Math.max(1, ...s.countries.map((c) => c.visits));
  const by = Object.fromEntries(s.countries.map((c) => [c.key, c]));
  const outside = s.countries.filter((c) => !EUROPE.paths[c.key]);
  const list = s.countries.slice(0, 8);
  return (
    <Card icon={MapIcon} title="Woher – auf der Karte" info="Je Land: je dunkler, desto mehr Besuche; ein roter Punkt zeigt die Anfragen. Das Land kommt aus der Adresse (gespeichert wird nur das Land).">
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: 20, alignItems: 'start' }}>
        <svg viewBox={`0 0 ${EUROPE.w} ${EUROPE.h}`} width="100%" role="img" aria-label="Europakarte der Besuche"
          style={{ display: 'block', background: 'var(--bg-2)', borderRadius: 8 }}>
          {Object.entries(EUROPE.paths).map(([code, d]) => {
            const c = by[code];
            const share = c ? Math.sqrt(c.visits / max) : 0;
            return (
              <path key={code} d={d} stroke="var(--bg-1)" strokeWidth={0.6}
                fill={c?.visits ? 'var(--accent)' : 'var(--bg-4)'} fillOpacity={c?.visits ? 0.18 + 0.82 * share : 1}
                data-tip={`${countryName(code)} · ${n(c?.visits ?? 0)} Besuche · ${n(c?.inquiries ?? 0)} Anfragen`} />
            );
          })}
          {s.countries.filter((c) => c.inquiries > 0 && EUROPE.centers[c.key]).map((c) => {
            const [cx, cy] = EUROPE.centers[c.key];
            return <circle key={c.key} cx={cx} cy={cy} r={2.5 + Math.sqrt(c.inquiries) * 1.6} fill="var(--inexxio-red)"
              stroke="var(--bg-1)" strokeWidth={0.8}
              data-tip={`${countryName(c.key)} · ${n(c.inquiries)} Anfrage${c.inquiries > 1 ? 'n' : ''}`} />;
          })}
        </svg>
        <div style={{ display: 'grid', gap: 10 }}>
          {list.map((c) => (
            <div key={c.key || 'x'} style={{ display: 'grid', gridTemplateColumns: 'minmax(0,1fr) auto', gap: '4px 12px', fontSize: 13.5 }}>
              <span>{countryName(c.key)}</span>
              <span style={{ ...NUM, color: 'var(--fg-3)' }}>{n(c.visits)} · <b style={{ color: c.inquiries ? 'var(--inexxio-red)' : 'var(--fg-3)' }}>{n(c.inquiries)}</b></span>
              <div style={{ gridColumn: '1 / -1' }}><Bar share={c.visits / max} /></div>
            </div>
          ))}
          {!list.length && <span style={MUTED}>Noch kein Land.</span>}
          {outside.length > 0 && (
            <span style={MUTED}>Ausserhalb der Karte: {outside.map((c) => `${countryName(c.key)} ${n(c.visits)}`).join(' · ')}</span>
          )}
        </div>
      </div>
    </Card>
  );
}

// ─── Seiten ──────────────────────────────────────────────────────────────────

function seconds(v: number): string {
  if (!v) return NOTHING;
  return `${Math.floor(v / 60)}:${String(v % 60).padStart(2, '0')}`;
}

const TH: React.CSSProperties = { textAlign: 'left', fontWeight: 500, color: 'var(--fg-3)', fontSize: 12, padding: '8px 6px', borderBottom: '1px solid var(--border-1)', whiteSpace: 'nowrap' };
const TD: React.CSSProperties = { padding: '8px 6px', borderBottom: '1px solid var(--border-1)', ...NUM };
const R: React.CSSProperties = { textAlign: 'right' };

function Pages({ s }: { s: Stats }) {
  return (
    <Card icon={FileText} title="Seiten" info="Sortiert nach Anfragen. «Anfragen» zählt, auf welcher Seite der Besuch begann; «gesendet» steht im Hover. Lesezeit: sichtbar, im Schnitt je Aufruf.">
      <div style={{ overflowX: 'auto', margin: '-8px -6px 0' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13.5 }}>
          <thead><tr>
            <th style={TH}>Seite</th><th style={{ ...TH, ...R }}>Besuche</th><th style={{ ...TH, ...R }}>Einstiege</th>
            <th style={{ ...TH, ...R }}>Lesezeit</th><th style={{ ...TH, ...R }}>Anrufe</th><th style={{ ...TH, ...R }}>Anfragen</th>
          </tr></thead>
          <tbody>
            {s.pages.map((p) => (
              <tr key={p.path}>
                <td style={{ ...TD, maxWidth: 340, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  <a href={p.path} target="_blank" rel="noreferrer" style={{ color: 'var(--fg-1)' }}>{p.path === '/' ? '/ (Startseite)' : p.path}</a>
                </td>
                <td style={{ ...TD, ...R }}>{n(p.visits)}</td>
                <td style={{ ...TD, ...R }}>{n(p.entries)}</td>
                <td style={{ ...TD, ...R }}>{seconds(p.read_seconds)}</td>
                <td style={{ ...TD, ...R }}>{n(p.calls)}</td>
                <td style={{ ...TD, ...R, fontWeight: p.inquiries ? 600 : 400, color: p.inquiries ? 'var(--inexxio-red)' : undefined }}
                  data-tip={`Begonnen: ${n(p.inquiries)} · hier gesendet: ${n(p.sent)}`}>{n(p.inquiries)}</td>
              </tr>
            ))}
            {!s.pages.length && <tr><td colSpan={6} style={{ ...TD, color: 'var(--fg-3)' }}>Noch keine Seite.</td></tr>}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

// ─── Formular, Gerät, Sprache ────────────────────────────────────────────────

function Funnel({ s }: { s: Stats }) {
  const f = s.funnel;
  const steps: [string, number][] = [['Formular gesehen', f.seen], ['Angefangen', f.started], ['Schritt 2', f.step2], ['Gesendet', f.sent]];
  const top = Math.max(1, f.seen, f.sent);
  return (
    <Card icon={ListChecks} title="Formular" info="Wo Leute abbrechen. Gezählt je Besuch; «Gesendet» sind die Anfragen.">
      <div style={{ display: 'grid', gap: 8 }}>
        {steps.map(([label, v]) => (
          <div key={label} style={{ display: 'grid', gridTemplateColumns: '120px minmax(0,1fr) 48px', alignItems: 'center', gap: 10, fontSize: 13 }}>
            <span>{label}</span>
            <div style={{ height: 20, borderRadius: 4, background: 'var(--bg-3)', overflow: 'hidden' }}>
              <div style={{ width: `${(v / top) * 100}%`, height: '100%', background: 'var(--accent)' }} />
            </div>
            <span style={{ ...NUM, ...R }}>{n(v)}</span>
          </div>
        ))}
      </div>
    </Card>
  );
}

const DEVICE: Record<string, string> = { mobile: 'Handy', desktop: 'Computer', tablet: 'Tablet' };
const LANG: Record<string, string> = { de: 'Deutsch', fr: 'Französisch', it: 'Italienisch', en: 'Englisch' };

function Split({ rows, names }: { rows: Stats['devices']; names: Record<string, string> }) {
  const total = rows.reduce((a, x) => a + x.visits, 0);
  return (
    <div style={{ display: 'grid', gap: 10 }}>
      {rows.map((x) => (
        <div key={x.key} style={{ display: 'grid', gridTemplateColumns: 'minmax(0,1fr) auto', gap: '4px 12px', fontSize: 13.5 }}>
          <span>{names[x.key] ?? x.key}</span><span style={{ ...NUM, color: 'var(--fg-3)' }}>{pct(x.visits, total)}</span>
          <div style={{ gridColumn: '1 / -1' }}><Bar share={total ? x.visits / total : 0} /></div>
        </div>
      ))}
      {!rows.length && <span style={MUTED}>Noch nichts.</span>}
    </div>
  );
}

function Devices({ s }: { s: Stats }) {
  return (
    <Card icon={Smartphone} title="Gerät und Sprache">
      <Split rows={s.devices} names={DEVICE} />
      <Split rows={s.languages} names={LANG} />
    </Card>
  );
}

// ─── Ladezeit ────────────────────────────────────────────────────────────────

function rating(ms: number): [string, string] {
  if (ms <= 2500) return ['gut', 'var(--success)'];
  if (ms <= 4000) return ['verbesserungswürdig', 'var(--warning)'];
  return ['langsam', 'var(--danger)'];
}

function Speed({ s }: { s: Stats }) {
  const sp = s.speed;
  const cls = sp.cls == null ? null : sp.cls / 1000;
  return (
    <Card icon={Gauge} title="Ladezeit" info="Wie Google sie misst (Core Web Vitals, 75 % der Aufrufe sind schneller): bis das grösste Bild oder der grösste Text steht (LCP) und wie viel verrutscht (CLS). Gut: LCP bis 2,5 s, CLS bis 0,1.">
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 24 }}>
        {(['mobile', 'desktop'] as const).map((d) => {
          const v = sp.by_device[d];
          const [word, tone] = v ? rating(v.lcp) : ['noch nicht gemessen', 'var(--fg-3)'];
          return (
            <div key={d} style={{ display: 'grid', gap: 2 }}>
              <span style={MUTED}>{DEVICE[d]}</span>
              <b style={{ fontFamily: 'var(--font-display)', fontSize: 22, ...NUM }}>{v ? `${formatAmount(v.lcp / 1000, 1)} s` : NOTHING}</b>
              <span style={{ fontSize: 12.5, color: tone }}>● {word}</span>
            </div>
          );
        })}
        <div style={{ display: 'grid', gap: 2 }}>
          <span style={MUTED}>Verrutschen (CLS)</span>
          <b style={{ fontFamily: 'var(--font-display)', fontSize: 22, ...NUM }}>{cls == null ? NOTHING : formatAmount(cls, 2)}</b>
          {cls != null && <span style={{ fontSize: 12.5, color: cls <= 0.1 ? 'var(--success)' : cls <= 0.25 ? 'var(--warning)' : 'var(--danger)' }}>
            ● {cls <= 0.1 ? 'gut' : cls <= 0.25 ? 'verbesserungswürdig' : 'schlecht'}</span>}
        </div>
      </div>
      {sp.slowest.length > 0 && (
        <div style={{ display: 'grid', gap: 6, fontSize: 13.5 }}>
          <span style={MUTED}>Langsamste Seiten</span>
          {sp.slowest.map((p) => (
            <div key={p.path} style={{ display: 'flex', justifyContent: 'space-between', gap: 12 }}>
              <span style={{ minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{p.path}</span>
              <span style={{ ...NUM, color: rating(p.lcp)[1] }}>{formatAmount(p.lcp / 1000, 1)} s</span>
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}

// ─── Anfragen ────────────────────────────────────────────────────────────────

function Inquiries({ s }: { s: Stats }) {
  const nav = useErpNav();
  return (
    <Card icon={MessageSquareText} title="Anfragen" info="Die Anfragen des Zeitraums mit Quelle und Einstieg ihres Besuchs. Ein Klick auf den Namen öffnet die Person (dort steht die Nachricht).">
      <div style={{ overflowX: 'auto', margin: '-8px -6px 0' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13.5 }}>
          <thead><tr>
            <th style={TH}>Eingang</th><th style={TH}>Wer</th><th style={TH}>Kam über</th>
            <th style={TH}>Eingestiegen auf</th><th style={TH}>Gesendet von</th><th style={TH}>Land</th>
          </tr></thead>
          <tbody>
            {s.inquiries.map((r, i) => (
              <tr key={`${r.at}-${i}`}>
                <td style={{ ...TD, whiteSpace: 'nowrap', color: 'var(--fg-3)' }} data-tip={formatWhen(r.at)}>{when(r.at)}</td>
                <td style={TD}>
                  {r.person_object_id && nav
                    ? <button type="button" className="erp-objid" onClick={() => nav(r.person_object_id!)}>{r.person ?? r.person_object_id}</button>
                    : (r.person ?? NOTHING)}
                </td>
                <td style={{ ...TD, color: r.channel === 'ai' ? 'var(--inexxio-red)' : undefined }}>{r.source}</td>
                <td style={TD}>{r.entry_path ?? NOTHING}</td>
                <td style={TD}>{r.path}</td>
                <td style={TD}>{r.country ? countryName(r.country) : NOTHING}</td>
              </tr>
            ))}
            {!s.inquiries.length && <tr><td colSpan={6} style={{ ...TD, color: 'var(--fg-3)' }}>Keine Anfragen in diesem Zeitraum.</td></tr>}
          </tbody>
        </table>
      </div>
    </Card>
  );
}
