interface FieldProps {
  label: string;
  value: string;
  onChange?: (v: string) => void;
  type?: string;
  readOnly?: boolean;
  placeholder?: string;
  hint?: string;
}

export function Field({ label, value, onChange, type = 'text', readOnly = false, placeholder, hint }: FieldProps) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
      <label style={{ fontSize: 13, fontWeight: 500, color: '#374151' }}>{label}</label>
      <input
        type={type}
        value={value}
        onChange={onChange ? (e) => onChange(e.target.value) : undefined}
        readOnly={readOnly}
        placeholder={placeholder}
        style={{
          padding: '8px 12px',
          borderRadius: 8,
          border: '1px solid #E2E8F0',
          fontSize: 14,
          color: readOnly ? '#94a3b8' : '#0F172A',
          background: readOnly ? '#F8FAFC' : '#fff',
          outline: 'none',
          width: '100%',
          boxSizing: 'border-box',
          cursor: readOnly ? 'default' : 'text',
          transition: 'border-color 0.15s',
        }}
        onFocus={(e) => { if (!readOnly) e.target.style.borderColor = '#E51A14'; }}
        onBlur={(e) => { e.target.style.borderColor = '#E2E8F0'; }}
      />
      {hint && <p style={{ fontSize: 12, color: '#94a3b8', margin: 0 }}>{hint}</p>}
    </div>
  );
}

interface SelectFieldProps {
  label: string;
  value: string;
  onChange: (v: string) => void;
  options: { value: string; label: string }[];
  hint?: string;
}

export function SelectField({ label, value, onChange, options, hint }: SelectFieldProps) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
      <label style={{ fontSize: 13, fontWeight: 500, color: '#374151' }}>{label}</label>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        style={{
          padding: '8px 12px',
          borderRadius: 8,
          border: '1px solid #E2E8F0',
          fontSize: 14,
          color: '#0F172A',
          background: '#fff',
          outline: 'none',
          width: '100%',
          cursor: 'pointer',
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
