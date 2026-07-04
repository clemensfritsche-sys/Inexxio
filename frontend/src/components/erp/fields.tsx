'use client';

import { useEffect, useRef, useState } from 'react';
import type { ElementType, ReactNode } from 'react';
import { AlertCircle, ChevronDown, Search, Info, Loader2, CheckCircle2 } from 'lucide-react';
import type { StatusAction, StatusTone, StatusCfg } from '@/lib/status-flow';

// ─── Hover-Hilfen: Erklärungen/Infotexte gehören in den Hover, nicht in die Fläche ──

/** Leichter Hover-/Fokus-Tooltip (dunkle Sprechblase). Trägt erklärende Texte, ohne
 *  die Oberfläche zu fluten – «weniger ist mehr». */
export function Tooltip({ text, children, side = 'top' }: {
  text: string; children: ReactNode; side?: 'top' | 'bottom';
}) {
  const [show, setShow] = useState(false);
  return (
    <span style={{ position: 'relative', display: 'inline-flex', alignItems: 'center' }}
      onMouseEnter={() => setShow(true)} onMouseLeave={() => setShow(false)}
      onFocus={() => setShow(true)} onBlur={() => setShow(false)}>
      {children}
      {show && (
        <span role="tooltip" style={{
          position: 'absolute', zIndex: 50, left: '50%', transform: 'translateX(-50%)',
          ...(side === 'top' ? { bottom: '100%', marginBottom: 7 } : { top: '100%', marginTop: 7 }),
          padding: '7px 10px', borderRadius: 7, background: '#0f172a', color: '#fff',
          fontSize: 11, fontWeight: 500, lineHeight: 1.4, width: 'max-content', maxWidth: 240,
          textAlign: 'left', whiteSpace: 'normal', boxShadow: '0 6px 18px rgba(0,0,0,0.22)', pointerEvents: 'none',
        }}>{text}</span>
      )}
    </span>
  );
}

/** Dezentes ⓘ-Symbol; die Erklärung erscheint im Hover. Ersetzt Infotext-Blöcke. */
export function InfoHint({ text, side }: { text: string; side?: 'top' | 'bottom' }) {
  return (
    <Tooltip text={text} side={side}>
      <Info size={13} style={{ color: '#cbd5e1', cursor: 'help', flexShrink: 0 }} />
    </Tooltip>
  );
}

/** Einheitlicher Abschnitts-Titel (Symbol + Versalien-Label + optional ⓘ-Hover + rechte Slot). */
export function SectionTitle({ icon: Icon, info, right, children }: {
  icon?: ElementType; info?: string; right?: ReactNode; children: ReactNode;
}) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 6, margin: '4px 2px 8px' }}>
      {Icon && <Icon size={13} style={{ color: '#94a3b8' }} />}
      <span style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.07em', color: '#64748b' }}>{children}</span>
      {info && <InfoHint text={info} />}
      {right && <span style={{ marginLeft: 'auto' }}>{right}</span>}
    </div>
  );
}

/** Einheitlicher Prozessschritt-Kopf: getöntes Symbol + Titel + optional ⓘ-Hover + rechter
 *  Slot (z. B. Status). EIN Look über alle Schritt-Panels (Bewegung/Ressource/…). */
export function PanelHeader({ icon: Icon, title, tone = '#2563eb', info, right }: {
  icon: ElementType; title: string; tone?: string; info?: string; right?: ReactNode;
}) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
      <span style={{ width: 26, height: 26, borderRadius: 7, flexShrink: 0, background: `${tone}14`, color: tone, display: 'inline-flex', alignItems: 'center', justifyContent: 'center' }}>
        <Icon size={15} />
      </span>
      <span style={{ fontSize: 13, fontWeight: 700, color: '#0F172A' }}>{title}</span>
      {info && <InfoHint text={info} />}
      {right && <span style={{ marginLeft: 'auto', display: 'inline-flex', alignItems: 'center' }}>{right}</span>}
    </div>
  );
}

export const inputCls = 'w-full px-2.5 py-1.5 text-sm rounded-md border bg-white outline-none focus:ring-2 focus:ring-accent focus:border-transparent transition-colors';

export function Label({ children, required }: { children: React.ReactNode; required?: boolean }) {
  return (
    <div style={{ fontSize: 11, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: '#94a3b8', marginBottom: 4 }}>
      {children}{required && <span style={{ color: '#dc2626' }}> *</span>}
    </div>
  );
}

export function ErrorText({ msg }: { msg: string }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 4, marginTop: 4, fontSize: 11, color: '#dc2626' }}>
      <AlertCircle size={11} /> {msg}
    </div>
  );
}

export function TextField({ label, value, onChange, error, placeholder, required, hint }: {
  label: string; value: string; onChange: (v: string) => void;
  error?: string | null; placeholder?: string; required?: boolean; hint?: string;
}) {
  return (
    <div>
      <Label required={required}>{label}</Label>
      <input
        value={value}
        placeholder={placeholder}
        onChange={(e) => onChange(e.target.value)}
        className={inputCls}
        style={{ borderColor: error ? '#fca5a5' : '#e2e8f0' }}
      />
      {error ? <ErrorText msg={error} /> : hint ? (
        <div style={{ marginTop: 4, fontSize: 11, color: '#94a3b8' }}>{hint}</div>
      ) : null}
    </div>
  );
}

export function SelectField({ label, value, onChange, options, required }: {
  label: string; value: string; onChange: (v: string) => void;
  options: { value: string; label: string }[]; required?: boolean;
}) {
  return (
    <div>
      <Label required={required}>{label}</Label>
      <select value={value} onChange={(e) => onChange(e.target.value)} className={inputCls} style={{ borderColor: '#e2e8f0' }}>
        {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
      </select>
    </div>
  );
}

/** Durchsuchbare Referenz-Auswahl (Combobox). Filtert Optionen per Tippen –
 *  z. B. «003» findet die Objektnummer 100000003. */
export function SearchSelect({ label, value, onChange, options, required, placeholder }: {
  label?: string; value: string; onChange: (v: string) => void;
  options: { value: string; label: string }[]; required?: boolean; placeholder?: string;
}) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const ref = useRef<HTMLDivElement>(null);
  const selected = options.find((o) => o.value === value);

  useEffect(() => {
    function onDoc(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) { setOpen(false); setQuery(''); }
    }
    document.addEventListener('mousedown', onDoc);
    return () => document.removeEventListener('mousedown', onDoc);
  }, []);

  const q = query.trim().toLowerCase();
  const filtered = q ? options.filter((o) => o.label.toLowerCase().includes(q)) : options;

  function pick(v: string) { onChange(v); setOpen(false); setQuery(''); }

  return (
    <div ref={ref} style={{ position: 'relative' }}>
      {label && <Label required={required}>{label}</Label>}
      <div style={{ position: 'relative' }}>
        <input
          value={open ? query : (selected?.label ?? '')}
          placeholder={placeholder ?? '— wählen —'}
          onFocus={() => { setOpen(true); setQuery(''); }}
          onChange={(e) => { setQuery(e.target.value); if (!open) setOpen(true); }}
          className={inputCls}
          style={{ borderColor: '#e2e8f0', paddingRight: 28 }}
        />
        {open
          ? <Search size={14} style={{ position: 'absolute', right: 9, top: '50%', transform: 'translateY(-50%)', color: '#94a3b8', pointerEvents: 'none' }} />
          : <ChevronDown size={14} style={{ position: 'absolute', right: 9, top: '50%', transform: 'translateY(-50%)', color: '#94a3b8', pointerEvents: 'none' }} />}
      </div>
      {open && (
        <div style={{ position: 'absolute', zIndex: 40, top: 'calc(100% + 4px)', left: 0, right: 0, maxHeight: 240, overflowY: 'auto', background: '#fff', border: '1px solid #e2e8f0', borderRadius: 8, boxShadow: '0 8px 24px rgba(0,0,0,0.12)' }}>
          {filtered.length === 0 ? (
            <div style={{ padding: '10px 12px', fontSize: 13, color: '#94a3b8' }}>Keine Treffer</div>
          ) : filtered.map((o) => (
            <button key={o.value} type="button" onClick={() => pick(o.value)}
              style={{ display: 'block', width: '100%', textAlign: 'left', padding: '8px 12px', fontSize: 13, border: 'none',
                background: o.value === value ? 'var(--accent-soft)' : '#fff', color: o.value === value ? 'var(--accent-ink)' : 'var(--fg-1)', cursor: 'pointer' }}>
              {o.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

export function Segmented({ label, value, onChange, options, required }: {
  label: string; value: string; onChange: (v: string) => void;
  options: { value: string; label: string }[]; required?: boolean;
}) {
  return (
    <div>
      <Label required={required}>{label}</Label>
      <div style={{ display: 'flex', gap: 6 }}>
        {options.map((o) => {
          const active = value === o.value;
          return (
            <button
              key={o.value}
              type="button"
              onClick={() => onChange(o.value)}
              style={{
                flex: 1, padding: '7px 10px', fontSize: 13, fontWeight: 600,
                borderRadius: 8, cursor: 'pointer',
                border: `1px solid ${active ? 'var(--accent)' : 'var(--border-2)'}`,
                background: active ? 'var(--accent-soft)' : '#fff',
                color: active ? 'var(--accent-ink)' : 'var(--fg-3)',
              }}
            >
              {o.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}

export function StatusBadge({ cfg, size = 10 }: { cfg: StatusCfg; size?: number }) {
  const Icon = cfg.icon;
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 4,
      fontSize: size, fontWeight: 700, padding: '2px 8px', borderRadius: 999,
      background: cfg.bg, color: cfg.color, whiteSpace: 'nowrap',
    }}>
      {Icon && <Icon size={size + 3} strokeWidth={2.5} />}
      {cfg.label}
    </span>
  );
}

function statusActionStyle(tone: StatusTone = 'neutral', disabled?: boolean): React.CSSProperties {
  const base: React.CSSProperties = {
    padding: '3px 10px', borderRadius: 6, fontSize: 12, fontWeight: 600,
    cursor: disabled ? 'not-allowed' : 'pointer', opacity: disabled ? 0.5 : 1,
  };
  if (tone === 'primary') return { ...base, border: 'none', background: '#2563eb', color: '#fff' };
  if (tone === 'danger') return { ...base, border: '1px solid #fecaca', background: '#fff', color: '#dc2626' };
  return { ...base, border: '1px solid #e2e8f0', background: '#fff', color: '#475569' };
}

/** Status-Badge + Prozess-Buttons (Freigeben / Deaktivieren / Reaktivieren). */
export function StatusFlow({ cfg, actions = [], busy, onAction }: {
  cfg: StatusCfg;
  actions?: StatusAction[];
  busy?: boolean;
  onAction?: (target: string) => void;
}) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
      <StatusBadge cfg={cfg} />
      {actions.map((a) => (
        <button
          key={a.target}
          type="button"
          title={a.hint}
          disabled={busy || a.disabled}
          onClick={() => onAction?.(a.target)}
          style={statusActionStyle(a.tone, busy || a.disabled)}
        >
          {a.label}
        </button>
      ))}
    </div>
  );
}

/** Grosse, eindeutige Hauptaktion (touch-first, volle Breite, ≥44 px). Ein
 *  klarer «Was jetzt?»-Button je Prozessschritt – statt mehrerer kleiner Knöpfe. */
export function PrimaryButton({ icon: Icon, children, onClick, disabled, tone = 'primary' }: {
  icon?: React.ElementType; children: React.ReactNode; onClick: () => void;
  disabled?: boolean; tone?: 'primary' | 'success';
}) {
  return (
    <button onClick={onClick} disabled={disabled}
      style={{
        display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 8, width: '100%',
        minHeight: 44, padding: '0 16px', borderRadius: 10, border: 'none',
        background: tone === 'success' ? '#16a34a' : '#2563eb', color: '#fff',
        fontSize: 14, fontWeight: 700, cursor: disabled ? 'not-allowed' : 'pointer',
        opacity: disabled ? 0.55 : 1,
      }}>
      {Icon && <Icon size={18} />} {children}
    </button>
  );
}

export function Placeholder({ icon: Icon, title, text }: { icon: React.ElementType; title: string; text: string }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', textAlign: 'center', padding: 24 }}>
      <Icon size={40} strokeWidth={1} style={{ color: '#CBD5E1' }} />
      <p style={{ marginTop: 12, fontSize: 14, fontWeight: 600, color: '#64748b' }}>{title}</p>
      <p style={{ marginTop: 4, fontSize: 13, color: '#94a3b8', maxWidth: 280 }}>{text}</p>
    </div>
  );
}

// Autosave-Statusanzeige («Speichert… / Gespeichert») – geteilt von allen Detailfenstern
// (vorher 3 identische Kopien in Artikel-/Auftrag-/Lagerplatz-Detail).
export function SaveIndicator({ saving, flash }: { saving: boolean; flash: boolean }) {
  if (saving) return <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, fontSize: 11, color: '#94a3b8' }}><Loader2 size={12} className="animate-spin" /> Speichert…</span>;
  if (flash) return <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, fontSize: 11, color: '#16a34a' }}><CheckCircle2 size={12} /> Gespeichert</span>;
  return null;
}
