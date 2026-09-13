/**
 * **Weiche Format-Prüfung** (Testnotiz #326) – für Telefon und E-Mail.
 *
 * Warum weich: eine harte Telefon-Validierung ist der Klassiker unter den
 * Formular-Ärgernissen. Gültige Nummern gibt es in Dutzenden Schreibweisen (`+41 44 …`,
 * `0044 …`, mit Klammern, mit Durchwahl), und jede strenge Regex sperrt irgendwann eine
 * echte Nummer aus. Die verlässliche Lösung wäre libphonenumber – ~150 kB für ein Feld,
 * das niemand automatisiert wählt. Also: **melden statt blockieren.** Wer eine Nummer
 * tippt, die offensichtlich keine ist (zu wenige Ziffern, fremde Zeichen), sieht einen
 * Hinweis; gespeichert wird trotzdem, denn die Angabe ist informativ, nicht funktional.
 */
export function fieldFormatIssue(type: string, value: string): string | null {
  const v = value.trim();
  if (!v) return null;
  if (type === 'tel') {
    if (/[^\d\s+()/.-]/.test(v)) return 'Enthält Zeichen, die in einer Telefonnummer nicht vorkommen.';
    const digits = v.replace(/\D/g, '');
    if (digits.length < 7) return 'Wirkt zu kurz für eine Telefonnummer.';
    if (digits.length > 15) return 'Wirkt zu lang – international sind max. 15 Ziffern üblich.';
    return null;
  }
  if (type === 'email' && !/^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(v)) {
    return 'Sieht nicht wie eine E-Mail-Adresse aus.';
  }
  return null;
}

interface FieldProps {
  label: string;
  value: string;
  onChange?: (v: string) => void;
  type?: string;
  readOnly?: boolean;
  placeholder?: string;
  hint?: string;
  onEnter?: () => void;
  required?: boolean;
  /** `id` einer `<datalist>` – Vorschläge beim Tippen, Freitext bleibt möglich. */
  list?: string;
}

export function Field({ label, value, onChange, type = 'text', readOnly = false, placeholder, hint, onEnter, required, list }: FieldProps) {
  const isEmpty = required && !value.trim();
  const issue = readOnly ? null : fieldFormatIssue(type, value);
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
      <label style={{ fontSize: 13, fontWeight: 500, color: '#374151' }}>
        {label}
        {isEmpty && <span style={{ color: '#f59e0b', marginLeft: 3, fontWeight: 700 }}>*</span>}
      </label>
      <input
        type={type}
        value={value}
        onChange={onChange ? (e) => onChange(e.target.value) : undefined}
        readOnly={readOnly}
        placeholder={placeholder}
        list={list}
        onKeyDown={(e) => { if (e.key === 'Enter' && !readOnly && onEnter) { e.preventDefault(); onEnter(); } }}
        inputMode={type === 'tel' ? 'tel' : type === 'email' ? 'email' : undefined}
        style={{
          padding: '8px 12px',
          borderRadius: 8,
          border: isEmpty || issue ? '1px solid #f59e0b' : '1px solid #E2E8F0',
          fontSize: 14,
          color: readOnly ? '#94a3b8' : '#0F172A',
          background: isEmpty ? '#FFFBEB' : readOnly ? '#F8FAFC' : '#fff',
          outline: 'none',
          width: '100%',
          boxSizing: 'border-box',
          cursor: readOnly ? 'default' : 'text',
          transition: 'border-color 0.15s, background 0.15s',
        }}
        onFocus={(e) => { if (!readOnly) e.target.style.borderColor = isEmpty || issue ? '#d97706' : '#E51A14'; }}
        onBlur={(e) => { e.target.style.borderColor = isEmpty || issue ? '#f59e0b' : '#E2E8F0'; }}
      />
      {/* Der Hinweis meldet, blockiert aber nicht (#326) – gespeichert wird trotzdem. */}
      {issue && <p style={{ fontSize: 12, color: '#b45309', margin: 0 }}>{issue}</p>}
      {hint && !issue && <p style={{ fontSize: 12, color: '#94a3b8', margin: 0 }}>{hint}</p>}
    </div>
  );
}

interface SelectFieldProps {
  label: string;
  value: string;
  onChange: (v: string) => void;
  options: { value: string; label: string }[];
  hint?: string;
  disabled?: boolean;
}

export function SelectField({ label, value, onChange, options, hint, disabled = false }: SelectFieldProps) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
      <label style={{ fontSize: 13, fontWeight: 500, color: '#374151' }}>{label}</label>
      <select
        value={value}
        onChange={disabled ? undefined : (e) => onChange(e.target.value)}
        disabled={disabled}
        style={{
          padding: '8px 12px',
          borderRadius: 8,
          border: '1px solid #E2E8F0',
          fontSize: 14,
          color: disabled ? '#94a3b8' : '#0F172A',
          background: disabled ? '#F8FAFC' : '#fff',
          outline: 'none',
          width: '100%',
          boxSizing: 'border-box',
          cursor: disabled ? 'default' : 'pointer',
        }}
      >
        {options.map((o) => (
          <option key={o.value} value={o.value}>{o.label}</option>
        ))}
      </select>
      {hint && <p style={{ fontSize: 12, color: '#94a3b8', margin: 0 }}>{hint}</p>}
    </div>
  );
}

interface ToggleFieldProps {
  label: string;
  description?: string;
  checked: boolean;
  onChange: (v: boolean) => void;
}

export function ToggleField({ label, description, checked, onChange }: ToggleFieldProps) {
  return (
    <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 16 }}>
      <div>
        <p style={{ fontSize: 14, fontWeight: 500, color: '#0F172A', margin: 0 }}>{label}</p>
        {description && <p style={{ fontSize: 13, color: '#64748b', margin: '2px 0 0' }}>{description}</p>}
      </div>
      <button
        role="switch"
        aria-checked={checked}
        onClick={() => onChange(!checked)}
        style={{
          width: 44, height: 24, borderRadius: 12, border: 'none', cursor: 'pointer',
          background: checked ? '#E51A14' : '#cbd5e1',
          position: 'relative', flexShrink: 0, transition: 'background 0.2s',
        }}
      >
        <span style={{
          position: 'absolute', top: 3, left: checked ? 23 : 3,
          width: 18, height: 18, borderRadius: '50%', background: '#fff',
          transition: 'left 0.2s', boxShadow: '0 1px 3px rgba(0,0,0,0.2)',
        }} />
      </button>
    </div>
  );
}
