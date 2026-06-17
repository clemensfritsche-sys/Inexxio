'use client';

import { useEffect, useRef, useState } from 'react';
import { AlertCircle, ChevronDown, Search } from 'lucide-react';
import type { StatusAction, StatusTone } from '@/lib/status-flow';

export const inputCls = 'w-full px-2.5 py-1.5 text-sm rounded-md border bg-white outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-colors';

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
                background: o.value === value ? '#eff6ff' : '#fff', color: o.value === value ? '#2563eb' : '#0f172a', cursor: 'pointer' }}>
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
                border: `1px solid ${active ? '#2563eb' : '#e2e8f0'}`,
                background: active ? '#eff6ff' : '#fff',
                color: active ? '#2563eb' : '#64748b',
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

export function StatusBadge({ cfg, size = 10 }: { cfg: { label: string; color: string; bg: string }; size?: number }) {
  return (
    <span style={{
      fontSize: size, fontWeight: 700, padding: '2px 7px', borderRadius: 4,
      background: cfg.bg, color: cfg.color, whiteSpace: 'nowrap',
    }}>
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
  cfg: { label: string; color: string; bg: string };
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

export function Placeholder({ icon: Icon, title, text }: { icon: React.ElementType; title: string; text: string }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', textAlign: 'center', padding: 24 }}>
      <Icon size={40} strokeWidth={1} style={{ color: '#CBD5E1' }} />
      <p style={{ marginTop: 12, fontSize: 14, fontWeight: 600, color: '#64748b' }}>{title}</p>
      <p style={{ marginTop: 4, fontSize: 13, color: '#94a3b8', maxWidth: 280 }}>{text}</p>
    </div>
  );
}
