'use client';

import { useState, useEffect } from 'react';
import { Search, User, ArrowLeft } from 'lucide-react';
import { cn, userDisplayName } from '@/lib/utils';
import { api } from '@/lib/api';
import type { UserProfile } from '@/types';

// ─── Helpers ───────────────────────────────────────────────────────────────────

function fmtObjId(id: number | null | undefined): string {
  if (!id) return '—';
  return String(id).padStart(9, '0');
}

const ROLE_CFG: Record<string, { label: string; color: string; bg: string }> = {
  admin:    { label: 'Admin',       color: '#dc2626', bg: '#fef2f2' },
  employee: { label: 'Mitarbeiter', color: '#2563eb', bg: '#eff6ff' },
  supplier: { label: 'Lieferant',   color: '#d97706', bg: '#fffbeb' },
  customer: { label: 'Kunde',       color: '#16a34a', bg: '#f0fdf4' },
};

function localDate(iso: string | null | undefined): string {
  if (!iso) return '—';
  return new Date(iso).toLocaleDateString('de-CH');
}

// ─── Field ─────────────────────────────────────────────────────────────────────

interface FieldProps {
  label: string;
  val: string | boolean | number | null | undefined;
  onChange?: (v: string | boolean) => void;
  type?: 'text' | 'date' | 'select' | 'check' | 'email';
  opts?: string[];
  ro?: boolean;
  span2?: boolean;
}

function Field({ label, val, onChange, type = 'text', opts, ro, span2 }: FieldProps) {
  const editable = 'w-full px-2.5 py-1.5 text-sm rounded border border-slate-200 bg-white outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-colors';
  const readonlyCls = 'w-full px-2.5 py-1.5 text-sm rounded border border-slate-100 bg-slate-50 text-slate-400 outline-none cursor-default';

  if (type === 'check') {
    return (
      <label className={cn('flex items-center gap-2 text-sm text-slate-600 cursor-pointer', span2 && 'col-span-2')}>
        <input type="checkbox" checked={!!val} onChange={e => onChange?.(e.target.checked)} disabled={ro} className="w-3.5 h-3.5 rounded text-blue-600" />
        {label}
      </label>
    );
  }

  return (
    <div className={span2 ? 'col-span-2' : ''}>
      <div className="text-[10px] font-semibold uppercase tracking-wider text-slate-400 mb-1">{label}</div>
      {type === 'select' && !ro ? (
        <select value={String(val ?? '')} onChange={e => onChange?.(e.target.value)} className={editable}>
          {opts?.map(o => <option key={o} value={o}>{o || '—'}</option>)}
        </select>
      ) : (
        <input
          type={type === 'date' ? 'date' : type === 'email' ? 'email' : 'text'}
          value={String(val ?? '')}
          readOnly={ro}
          onChange={ro ? undefined : e => onChange?.(e.target.value)}
          className={ro ? readonlyCls : editable}
        />
      )}
    </div>
  );
}

// ─── Section ───────────────────────────────────────────────────────────────────

function Sec({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="mb-6">
      <div className="text-[10px] font-bold uppercase tracking-widest text-slate-400 pb-2 mb-3 border-b border-slate-100">{title}</div>
      <div className="grid grid-cols-2 gap-3">{children}</div>
    </div>
  );
}

// ─── RecordItem ────────────────────────────────────────────────────────────────

function RecordItem({ r, sel, onClick }: { r: UserProfile; sel: boolean; onClick: () => void }) {
  const rc = ROLE_CFG[r.role] ?? ROLE_CFG.customer;
  return (
    <button
      onClick={onClick}
      className="block w-full text-left"
      style={{
        padding: '10px 14px',
        background: sel ? '#eff6ff' : 'transparent',
        borderLeft: `3px solid ${sel ? '#2563eb' : 'transparent'}`,
        borderTop: 'none', borderRight: 'none',
        borderBottom: '1px solid #f1f5f9',
        cursor: 'pointer',
      }}
    >
      <div className="flex justify-between items-start gap-2">
        <span className="font-mono text-[11px] text-slate-400 leading-none">{fmtObjId(r.object_id)}</span>
        <span style={{ fontSize: 10, fontWeight: 600, padding: '1px 6px', borderRadius: 3, background: rc.bg, color: rc.color, flexShrink: 0 }}>{rc.label}</span>
      </div>
      <div className="mt-1 text-[11px] font-medium text-slate-400 uppercase tracking-wide">User</div>
      <div className="mt-0.5 text-[13px] font-semibold text-slate-800 truncate">{userDisplayName(r)}</div>
    </button>
  );
}

// ─── Form sections ─────────────────────────────────────────────────────────────

type GetVal = (k: keyof UserProfile) => string | boolean | null | undefined;
type SetVal = (k: keyof UserProfile) => (v: string | boolean) => void;

function FormSections({ v, set, record, isAdmin }: { v: GetVal; set: SetVal; record: UserProfile; isAdmin: boolean }) {
  const isSupplier = record.role === 'supplier';
  const isEmployee = record.role === 'employee' || record.role === 'admin';
  const isB2B = record.role === 'supplier' || record.role === 'customer';

  return (
    <>
      <Sec title="Rolle">
        <div>
          <div className="text-[10px] font-semibold uppercase tracking-wider text-slate-400 mb-1">Rolle</div>
          {isAdmin ? (
            <select value={String(v('role') ?? 'customer')} onChange={e => set('role')(e.target.value)} className="w-full px-2.5 py-1.5 text-sm rounded border border-slate-200 bg-white outline-none focus:ring-2 focus:ring-blue-500 transition-colors">
              <option value="admin">Admin</option>
              <option value="employee">Mitarbeiter</option>
              <option value="supplier">Lieferant</option>
              <option value="customer">Kunde</option>
            </select>
          ) : (
            <div className="px-2.5 py-1.5 text-sm rounded border border-slate-100 bg-slate-50 text-slate-400">{ROLE_CFG[record.role]?.label ?? record.role}</div>
          )}
        </div>
      </Sec>

      <Sec title="Personalien">
        <Field label="Vorname" val={v('first_name')} onChange={set('first_name')} />
        <Field label="Nachname" val={v('last_name')} onChange={set('last_name')} />
        <Field label="Geburtsdatum" val={v('date_of_birth')} onChange={set('date_of_birth')} type="date" />
        <Field label="Telefon" val={v('phone')} onChange={set('phone')} />
      </Sec>

      <Sec title="Adresse">
        <Field label="Adresszeile 1" val={v('address_line1')} onChange={set('address_line1')} />
        <Field label="Adresszeile 2" val={v('address_line2')} onChange={set('address_line2')} />
        <Field label="PLZ" val={v('postal_code')} onChange={set('postal_code')} />
        <Field label="Ort" val={v('city')} onChange={set('city')} />
        <Field label="Region/Bundesland" val={v('state_region')} onChange={set('state_region')} />
        <Field label="Land" val={v('country')} onChange={set('country')} />
      </Sec>

      {isB2B && (
        <Sec title="Lieferadresse">
          <Field label="Name" val={v('ship_name')} onChange={set('ship_name')} />
          <Field label="Firma" val={v('ship_company')} onChange={set('ship_company')} />
          <Field label="Adresszeile 1" val={v('ship_address_line1')} onChange={set('ship_address_line1')} />
          <Field label="Adresszeile 2" val={v('ship_address_line2')} onChange={set('ship_address_line2')} />
          <Field label="PLZ" val={v('ship_postal_code')} onChange={set('ship_postal_code')} />
          <Field label="Ort" val={v('ship_city')} onChange={set('ship_city')} />
          <Field label="Region/Bundesland" val={v('ship_state_region')} onChange={set('ship_state_region')} />
          <Field label="Land" val={v('ship_country')} onChange={set('ship_country')} />
        </Sec>
      )}

      {isB2B && (
        <Sec title="Rechnungsadresse">
          <Field label="Firma" val={v('invoice_company')} onChange={set('invoice_company')} />
          <div />
          <Field label="Vorname" val={v('invoice_first_name')} onChange={set('invoice_first_name')} />
          <Field label="Nachname" val={v('invoice_last_name')} onChange={set('invoice_last_name')} />
          <Field label="Adresszeile 1" val={v('invoice_address_line1')} onChange={set('invoice_address_line1')} />
          <Field label="Adresszeile 2" val={v('invoice_address_line2')} onChange={set('invoice_address_line2')} />
          <Field label="PLZ" val={v('invoice_postal_code')} onChange={set('invoice_postal_code')} />
          <Field label="Ort" val={v('invoice_city')} onChange={set('invoice_city')} />
          <Field label="Land" val={v('invoice_country')} onChange={set('invoice_country')} />
          <Field label="Rechnungs-E-Mail" val={v('invoice_email')} onChange={set('invoice_email')} type="email" />
          <Field label="Gleich wie Lieferadresse" val={v('invoice_same_as_shipping')} onChange={set('invoice_same_as_shipping')} type="check" span2 />
        </Sec>
      )}

      {isB2B && (
        <Sec title="Unternehmen">
          <Field label="Firmenname" val={v('company_name')} onChange={set('company_name')} />
          <div />
          <Field label="UID-Nummer" val={v('uid_number')} onChange={set('uid_number')} />
          <Field label="MwSt-Nummer" val={v('vat_number')} onChange={set('vat_number')} />
          <Field label="Handelsreg.-Nr." val={v('trade_register_nr')} onChange={set('trade_register_nr')} />
          <Field label="Handelsreg.-Kanton" val={v('trade_register_canton')} onChange={set('trade_register_canton')} />
          <Field label="Website" val={v('company_website')} onChange={set('company_website')} />
          <Field label="Rechnungs-E-Mail" val={v('company_billing_email')} onChange={set('company_billing_email')} type="email" />
          <Field label="MwSt. registriert" val={v('vat_registered')} onChange={set('vat_registered')} type="check" span2 />
        </Sec>
      )}

      {isSupplier && (
        <Sec title="Bankverbindung">
          <Field label="Kontoinhaber" val={v('bank_account_holder')} onChange={set('bank_account_holder')} />
          <Field label="Bank" val={v('bank_name')} onChange={set('bank_name')} />
          <Field label="IBAN" val={v('bank_iban')} onChange={set('bank_iban')} />
          <Field label="BIC/SWIFT" val={v('bank_bic')} onChange={set('bank_bic')} />
        </Sec>
      )}

      {isEmployee && (
        <Sec title="Anstellung">
          <Field label="Abteilung" val={v('department')} onChange={set('department')} />
          <Field label="Berufsbezeichnung" val={v('job_title')} onChange={set('job_title')} />
          <Field label="Eintrittsdatum" val={v('employment_start_date')} onChange={set('employment_start_date')} type="date" />
          <Field label="Wochenstunden" val={v('weekly_hours')} onChange={set('weekly_hours')} />
        </Sec>
      )}

      <Sec title="Einstellungen">
        <Field label="Sprache" val={v('language')} onChange={set('language')} type="select" opts={['de', 'en']} />
        <div />
        <div className="col-span-2 flex flex-wrap gap-4">
          <Field label="E-Mail-Benachrichtigungen" val={v('notification_email')} onChange={set('notification_email')} type="check" />
          <Field label="In-App-Benachrichtigungen" val={v('notification_inapp')} onChange={set('notification_inapp')} type="check" />
          <Field label="Newsletter" val={v('newsletter_opt_in')} onChange={set('newsletter_opt_in')} type="check" />
        </div>
      </Sec>

      <Sec title="System">
        <Field label="E-Mail" val={record.email} ro />
        <Field label="Erstellt" val={localDate(record.created_at)} ro />
        <Field label="Zuletzt geändert" val={localDate(record.updated_at)} ro />
        <Field label="Letzter Login" val={localDate(record.last_login_at)} ro />
        <Field label="AGB akzeptiert" val={localDate(record.terms_accepted_at)} ro />
        <Field label="AGB Version" val={record.terms_version ?? '—'} ro />
        {isAdmin && <Field label="Firebase UID" val={record.firebase_uid.slice(0, 16) + '…'} ro span2 />}
      </Sec>
    </>
  );
}

// ─── DetailPanel ───────────────────────────────────────────────────────────────

function DetailPanel({
  record, onSave, isAdmin, onBack,
}: {
  record: UserProfile;
  onSave: (u: UserProfile) => void;
  isAdmin: boolean;
  onBack: () => void;
}) {
  const [form, setForm] = useState<Partial<UserProfile>>({});
  const [dirty, setDirty] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => { setForm({}); setDirty(false); setError(null); }, [record.object_id]);

  function v(key: keyof UserProfile): string | boolean | null | undefined {
    if (key in form) return form[key] as string | boolean | null | undefined;
    return record[key] as string | boolean | null | undefined;
  }

  function set(key: keyof UserProfile) {
    return (val: string | boolean) => {
      setForm(prev => ({ ...prev, [key]: val === '' ? null : val } as Partial<UserProfile>));
      setDirty(true);
    };
  }

  async function save() {
    if (!record.object_id) return;
    setSaving(true);
    setError(null);
    try {
      const updated = await api.updateErpRecord(record.object_id, form);
      onSave(updated);
      setForm({});
      setDirty(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Fehler beim Speichern');
    } finally {
      setSaving(false);
    }
  }

  const currentRole = (v('role') as string | null | undefined) ?? record.role;
  const rc = ROLE_CFG[currentRole] ?? ROLE_CFG.customer;
  const name = userDisplayName(record);

  return (
    <div className="flex flex-col h-full">
      <div className="px-4 py-3 border-b border-slate-200 bg-white flex-shrink-0">
        <button onClick={onBack} className="flex items-center gap-1 text-sm text-blue-600 mb-2 md:hidden">
          <ArrowLeft size={14} /> Zurück
        </button>
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-full bg-slate-100 flex items-center justify-center flex-shrink-0 overflow-hidden">
            {record.photo_url
              ? <img src={record.photo_url} alt="" className="w-full h-full object-cover" />
              : <User size={16} className="text-slate-400" />}
          </div>
          <div className="min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="font-mono text-xs text-slate-400 font-semibold">{fmtObjId(record.object_id)}</span>
              <span style={{ fontSize: 10, fontWeight: 700, padding: '2px 8px', borderRadius: 4, background: rc.bg, color: rc.color }}>{rc.label}</span>
            </div>
            <div className="text-[11px] font-semibold text-slate-400 uppercase tracking-wide">User</div>
            <div className="text-sm font-semibold text-slate-900 truncate">{name}</div>
          </div>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-4 md:p-6 bg-slate-50">
        <FormSections v={v} set={set} record={record} isAdmin={isAdmin} />
      </div>

      {(dirty || error) && (
        <div className="px-4 py-2.5 bg-white border-t border-slate-200 flex items-center gap-2 flex-shrink-0">
          <span className="flex-1 text-sm truncate" style={{ color: error ? '#dc2626' : '#64748b' }}>
            {error ?? 'Ungespeicherte Änderungen'}
          </span>
          <button onClick={() => { setForm({}); setDirty(false); setError(null); }} className="px-3 py-1.5 rounded text-sm border border-slate-200 bg-white text-slate-600 hover:bg-slate-50 flex-shrink-0">
            Verwerfen
          </button>
          <button onClick={save} disabled={saving} className="px-3 py-1.5 rounded text-sm font-medium text-white flex-shrink-0" style={{ background: saving ? '#93c5fd' : '#2563eb' }}>
            {saving ? 'Speichern…' : 'Speichern'}
          </button>
        </div>
      )}
    </div>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function ErpPage() {
  const [records, setRecords] = useState<UserProfile[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [selId, setSelId] = useState<number | null>(null);
  const [mobileView, setMobileView] = useState<'list' | 'detail'>('list');
  const [isAdmin, setIsAdmin] = useState(false);

  useEffect(() => {
    const cached = typeof window !== 'undefined' ? localStorage.getItem('inexxio_user_role') : null;
    setIsAdmin(cached === 'admin');
    api.getErpRecords()
      .then(r => { setRecords(r); setLoading(false); })
      .catch(() => setLoading(false));
  }, []);

  const filtered = records.filter(r => {
    if (!search) return true;
    const q = search.toLowerCase();
    return (
      r.email.toLowerCase().includes(q) ||
      userDisplayName(r).toLowerCase().includes(q) ||
      String(r.object_id ?? '').includes(q)
    );
  });

  const selected = records.find(r => r.object_id === selId) ?? null;

  function handleSelect(id: number | null) {
    setSelId(id);
    setMobileView('detail');
  }

  function handleSave(updated: UserProfile) {
    setRecords(prev => prev.map(r => r.id === updated.id ? updated : r));
  }

  const showList = mobileView === 'list';

  return (
    <div className="flex overflow-hidden" style={{ height: 'calc(100vh - 72px)' }}>
      <div className={cn(
        'flex-shrink-0 border-r border-slate-200 flex flex-col bg-white',
        'w-full md:w-[280px] lg:w-[320px]',
        showList ? 'flex' : 'hidden md:flex',
      )}>
        <div className="px-3.5 pt-4 pb-3 border-b border-slate-100">
          <div className="text-[11px] font-bold uppercase tracking-widest text-slate-400 mb-2">
            Datensätze · {filtered.length}
          </div>
          <div className="relative">
            <Search size={13} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" />
            <input
              value={search}
              onChange={e => setSearch(e.target.value)}
              placeholder="Suchen…"
              className="w-full pl-7 pr-3 py-1.5 text-sm border border-slate-200 rounded-md bg-slate-50 outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
          </div>
        </div>
        <div className="flex-1 overflow-y-auto">
          {loading && <div className="p-6 text-center text-sm text-slate-400">Laden…</div>}
          {!loading && filtered.length === 0 && (
            <div className="p-6 text-center text-sm text-slate-400">{search ? 'Keine Treffer' : 'Keine Datensätze'}</div>
          )}
          {filtered.map(r => (
            <RecordItem key={r.id} r={r} sel={r.object_id === selId} onClick={() => handleSelect(r.object_id ?? null)} />
          ))}
        </div>
      </div>

      <div className={cn(
        'flex-1 overflow-hidden flex flex-col',
        !showList ? 'flex' : 'hidden md:flex',
      )}>
        {selected
          ? <DetailPanel
              key={selected.object_id}
              record={selected}
              onSave={handleSave}
              isAdmin={isAdmin}
              onBack={() => setMobileView('list')}
            />
          : (
            <div className="flex-1 flex flex-col items-center justify-center text-slate-300">
              <User size={48} strokeWidth={1} />
              <p className="mt-3 text-sm text-slate-400">Datensatz auswählen</p>
            </div>
          )
        }
      </div>
    </div>
  );
}
