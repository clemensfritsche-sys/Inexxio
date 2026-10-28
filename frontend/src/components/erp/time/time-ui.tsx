'use client';

/**
 * Zeiterfassung – kleine Bausteine und Formate. Jede Zahl kommt in **Minuten** vom Server
 * (`services/timekeeping`); hier wird sie nur gezeigt.
 *
 * Die **Symbole** der Absenzarten und Hinweise sind ein Spiegel von `domain/timekeeping`
 * (`Art.icon`, `HINTS`) – geprüft in `backend/tests/test_frontend_mirrors.py`. Ein
 * unbekannter Schlüssel sieht unbekannt aus (`HelpCircle`), nie wie eine andere Art.
 */
import type { CSSProperties, ElementType, ReactNode } from 'react';
import {
  Activity, AlertTriangle, Baby, CalendarCheck, CalendarX, FileWarning, HelpCircle,
  OctagonAlert, Shield, Sun, Thermometer,
} from 'lucide-react';
import { InfoHint, MICRO_LABEL, StatusBadge, inputClass } from '@/components/erp/fields';
import { TONE } from '@/lib/status-tone';

/** Lucide-Name (Backend) → Symbol. */
export const TIME_ICONS: Record<string, ElementType> = {
  sun: Sun,
  thermometer: Thermometer,
  activity: Activity,
  shield: Shield,
  baby: Baby,
  'calendar-check': CalendarCheck,
  'calendar-x': CalendarX,
  'alert-triangle': AlertTriangle,
  'octagon-alert': OctagonAlert,
  'file-warning': FileWarning,
};

export const timeIcon = (name: string): ElementType => TIME_ICONS[name] ?? HelpCircle;

// ─── Formate ────────────────────────────────────────────────────────────────────────

const MINUS = '−';

/** «8:24» – Minuten als Stunden; ein Minus ist ein echtes Minus. */
export function hm(min: number): string {
  const m = Math.round(min);
  const a = Math.abs(m);
  return `${m < 0 ? MINUS : ''}${Math.floor(a / 60)}:${String(a % 60).padStart(2, '0')}`;
}

/** «42» oder «41:30» – Wochenstunden, ohne «:00». */
export function hours(min: number): string {
  return min % 60 ? hm(min) : String(Math.round(min / 60));
}

/** «+6:30» / «−4:45» – ein Saldo mit Vorzeichen. */
export function sgn(min: number): string {
  return Math.round(min) > 0 ? `+${hm(min)}` : hm(min);
}

/** «121:48 h (14.5 Tage)» – Ferien in Stunden, in Klammern in Tagen (Tagessoll). */
export function vacationText(min: number, daySoll: number, signed = false): { h: string; d: string } {
  const h = `${signed ? sgn(min) : hm(min)} h`;
  if (!daySoll) return { h, d: '' };
  const days = Math.round((min / daySoll) * 10) / 10;
  const abs = Math.abs(days).toFixed(1).replace(/\.0$/, '');
  return { h, d: `(${days < 0 ? MINUS : signed && days > 0 ? '+' : ''}${abs} Tage)` };
}

/** «8:24» oder «8» → Minuten; ungültig → `null`. */
export function parseHm(raw: string): number | null {
  const v = raw.trim();
  const m = /^(\d{1,3}):([0-5]\d)$/.exec(v);
  if (m) return Number(m[1]) * 60 + Number(m[2]);
  const n = /^(\d{1,3})(?:[.,](\d{1,2}))?$/.exec(v);
  return n ? Math.round(Number(`${n[1]}.${n[2] ?? 0}`) * 60) : null;
}

/** «±H:MM» → Minuten mit Vorzeichen (leer = 0). */
export function parseSigned(raw: string): number | null {
  const v = raw.trim().replace(MINUS, '-');
  if (!v) return 0;
  const neg = v.startsWith('-');
  const n = parseHm(v.replace(/^[+-]/, ''));
  return n == null ? null : neg ? -n : n;
}

/** «07:45» – eine Uhrzeit als Minute des Tages; ungültig → `null`. */
export function parseClock(raw: string): number | null {
  const m = /^(\d{1,2}):(\d{2})$/.exec(raw.trim());
  return m && Number(m[1]) < 24 && Number(m[2]) < 60 ? Number(m[1]) * 60 + Number(m[2]) : null;
}

/** Wochentag eines Tages, 0 = Mo … 6 = So. */
export function weekday(iso: string): number {
  return (new Date(`${iso}T12:00:00`).getDay() + 6) % 7;
}

export const WEEKDAYS = ['Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa', 'So'];

/** «Mo–Fr» oder «Mo, Mi, Fr». */
export function daysLabel(days: number[]): string {
  const d = [...days].sort((a, b) => a - b);
  if (!d.length) return '–';
  const run = d.every((x, i) => x === d[0] + i);
  return run && d.length > 2 ? `${WEEKDAYS[d[0]]}–${WEEKDAYS[d[d.length - 1]]}` : d.map((x) => WEEKDAYS[x]).join(', ');
}

// ─── Bausteine ──────────────────────────────────────────────────────────────────────

/** Ein Zustand als Pille – Ton + Wort (+ Symbol), Einzelheiten im Hover. */
export function Pill({ tone, label, icon, tip }: {
  tone: 'pending' | 'done' | 'danger' | 'neutral'; label: string; icon?: ElementType; tip?: string;
}) {
  const t = tone === 'neutral' ? { color: 'var(--fg-3)', bg: 'var(--bg-3)' } : TONE[tone];
  const badge = <StatusBadge cfg={{ label, icon, ...t }} size={10.5} />;
  return tip
    ? <span data-tip={tip} style={{ display: 'inline-flex', cursor: 'help' }}>{badge}</span>
    : badge;
}


export const ROW_FORM: CSSProperties = {
  display: 'flex', flexWrap: 'wrap', gap: '12px 16px', alignItems: 'flex-end',
};

/** Ein kleines beschriftetes Feld – Beschriftung mit ⓘ, Warnfarbe, solange es nicht stimmt. */
export function TimeField({ id, label, value, onChange, info, bad, placeholder, width, onEnter }: {
  id: string; label: string; value: string; onChange: (v: string) => void; info?: string;
  bad?: boolean; placeholder?: string; width?: number; onEnter?: () => void;
}) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 4, width, maxWidth: '100%' }}>
      <label htmlFor={id} style={{ fontSize: 13, fontWeight: 500, color: 'var(--fg-2)',
        display: 'inline-flex', alignItems: 'center', gap: 5 }}>
        {label}{info && <InfoHint text={info} />}
      </label>
      <input id={id} value={value} placeholder={placeholder} autoComplete="off"
        className={`${inputClass(bad ? 'warn' : 'normal')} tabular-nums`}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={(e) => { if (e.key === 'Enter') onEnter?.(); }} />
    </div>
  );
}

/**
 * **Nur Symbole, feste Breite** – die Wahl der Art im Werkzeug «Erfassen». Nichts wächst beim
 * Darüberfahren (ein ausklappender Name liess am rechten Rand die Zeile umbrechen und das
 * Symbol unter dem Zeiger springen); der Name steht in der Blase und im Titel darüber.
 */
export function IconBar<T extends string>({ value, options, onChange }: {
  value: T | null; onChange: (v: T) => void;
  options: { value: T; label: string; icon: ElementType }[];
}) {
  return (
    <div role="tablist" style={{ display: 'inline-flex', flexWrap: 'wrap', justifySelf: 'start',
      width: 'fit-content', maxWidth: '100%', gap: 2, padding: 3, borderRadius: 999,
      background: 'var(--bg-2)', border: '1px solid var(--border-1)' }}>
      {options.map((o) => {
        const on = o.value === value;
        const Icon = o.icon;
        return (
          <button key={o.value} type="button" role="tab" aria-selected={on} aria-label={o.label}
            data-tip={o.label} data-tip-pos="bottom" onClick={() => onChange(o.value)}
            style={{ width: 34, height: 30, display: 'inline-flex', alignItems: 'center',
              justifyContent: 'center', border: 'none', borderRadius: 999, cursor: 'pointer',
              background: on ? 'var(--bg-1)' : 'none',
              boxShadow: on ? '0 1px 2px rgba(0,0,0,.12)' : undefined,
              color: on ? 'var(--accent-ink)' : 'var(--fg-3)' }}>
            <Icon size={15} />
          </button>
        );
      })}
    </div>
  );
}

/** Ein Symbol-Knopf, der **nicht** ausklappt – der Name steht in der Blase (wie in einer
 *  Zeile, `module-ui.RowActions`), damit nichts unter dem Zeiger springt. */
export function IconButton({ icon: Icon, label, onClick, height = 26 }: {
  icon: ElementType; label: string; onClick: () => void; height?: number;
}) {
  return (
    <span data-tip={label} className="inline-flex">
      <button type="button" aria-label={label} onClick={onClick}
        className="erp-actbtn erp-actbtn-neutral erp-actbtn-icon"
        style={{ height, '--actbtn-w': `${height}px` } as CSSProperties}>
        <Icon size={13} />
      </button>
    </span>
  );
}

/** Ein leiser Satz, wo sonst nichts steht. */
export function Note({ children }: { children: ReactNode }) {
  return <p style={{ fontSize: 13, color: 'var(--fg-3)', margin: 0 }}>{children}</p>;
}

/** Ein leiser Knopf mit Symbol und Wort («Erfassen», «Neuer Vertrag»). */
export function QuietButton({ icon: Icon, label, onClick, disabled, tip }: {
  icon: ElementType; label: string; onClick: () => void; disabled?: boolean; tip?: string;
}) {
  return (
    <div>
      <button type="button" className="erp-actbtn erp-actbtn-neutral" disabled={disabled}
        onClick={onClick} {...(tip ? { 'data-tip': tip } : {})}
        style={{ height: 30, padding: '0 12px', fontSize: 12.5 }}>
        <Icon size={14} />{label}
      </button>
    </div>
  );
}

/** Ein Abschnitt in der Karte: Symbol + Mikro-Label + ⓘ, rechts ein Platz. */
export function Sect({ icon: Icon, title, info, right, children }: {
  icon: ElementType; title: ReactNode; info?: string; right?: ReactNode; children: ReactNode;
}) {
  return (
    <div style={{ display: 'grid', gap: 12 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
        <Icon size={13} style={{ color: 'var(--fg-3)' }} />
        <span style={{ ...MICRO_LABEL, color: 'var(--fg-3)', display: 'inline-flex',
          alignItems: 'center', gap: 6 }}>{title}</span>
        {info && <InfoHint text={info} />}
        <span style={{ flex: 1 }} />
        {right}
      </div>
      {children}
    </div>
  );
}

export const HR = <div style={{ height: 1, background: 'var(--border-1)' }} />;
