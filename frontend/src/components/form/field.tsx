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
function fieldFormatIssue(type: string, value: string): string | null {
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
      <label style={{ fontSize: 13, fontWeight: 500, color: 'var(--fg-2)' }}>
        {label}
        {isEmpty && <span style={{ color: 'var(--warning)', marginLeft: 3, fontWeight: 700 }}>*</span>}
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
          border: isEmpty || issue ? '1px solid var(--warning)' : '1px solid var(--border-1)',
          fontSize: 14,
          color: readOnly ? 'var(--fg-4)' : 'var(--fg-1)',
          background: isEmpty ? 'var(--warning-bg)' : readOnly ? 'var(--bg-2)' : 'var(--bg-1)',
          outline: 'none',
          width: '100%',
          boxSizing: 'border-box',
          cursor: readOnly ? 'default' : 'text',
          transition: 'border-color 0.15s, background 0.15s',
        }}
        onFocus={(e) => { if (!readOnly) e.target.style.borderColor = isEmpty || issue ? 'var(--warning)' : 'var(--inexxio-red)'; }}
        onBlur={(e) => { e.target.style.borderColor = isEmpty || issue ? 'var(--warning)' : 'var(--border-1)'; }}
      />
      {/* Der Hinweis meldet, blockiert aber nicht (#326) – gespeichert wird trotzdem. */}
      {issue && <p style={{ fontSize: 12, color: 'var(--warning)', margin: 0 }}>{issue}</p>}
      {hint && !issue && <p style={{ fontSize: 12, color: 'var(--fg-4)', margin: 0 }}>{hint}</p>}
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
      <label style={{ fontSize: 13, fontWeight: 500, color: 'var(--fg-2)' }}>{label}</label>
      <select
        value={value}
        onChange={disabled ? undefined : (e) => onChange(e.target.value)}
        disabled={disabled}
        style={{
          padding: '8px 12px',
          borderRadius: 8,
          border: '1px solid var(--border-1)',
          fontSize: 14,
          color: disabled ? 'var(--fg-4)' : 'var(--fg-1)',
          background: disabled ? 'var(--bg-2)' : 'var(--bg-1)',
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
      {hint && <p style={{ fontSize: 12, color: 'var(--fg-4)', margin: 0 }}>{hint}</p>}
    </div>
  );
}
