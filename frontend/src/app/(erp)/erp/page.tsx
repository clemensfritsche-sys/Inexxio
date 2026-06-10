'use client';

import { useState, useEffect } from 'react';
import { Search, User, ArrowLeft, Pencil, MapPin, Building2, Shield, Settings, Briefcase } from 'lucide-react';
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

function getInitials(name: string, email: string): string {
  if (name && name !== email) {
    return name.split(' ').filter(Boolean).map(n => n[0]).join('').toUpperCase().slice(0, 2);
  }
  return email[0]?.toUpperCase() ?? '?';
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
  const editable = 'w-full px-2.5 py-1.5 text-sm rounded-md border border-slate-200 bg-white outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-colors';
  const readonlyCls = 'w-full px-2.5 py-1.5 text-sm rounded-md border border-slate-100 bg-slate-50 text-slate-400 outline-none cursor-default';

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
      <div style={{ fontSize: 11, fontWeight: 600, textTransform: 'uppercase' as const, letterSpacing: '0.05em', color: '#94a3b8', marginBottom: 4 }}>{label}</div>
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

// ─── Section card ──────────────────────────────────────────────────────────────

function Sec({ title, children, editable, icon: Icon }: {
  title: string;
  children: React.ReactNode;
  editable?: boolean;
  icon?: React.ElementType;
}) {
  return (
    <div style={{ background: '#fff', border: '1px solid #E2E8F0', borderRadius: 10, padding: '14px 16px', marginBottom: 12 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 12, paddingBottom: 10, borderBottom: '1px solid #F1F5F9' }}>
        {Icon && <Icon size={13} style={{ color: '#94a3b8' }} />}
        <span style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase' as const, letterSpacing: '0.07em', color: '#64748b' }}>{title}</span>
        {editable && <Pencil size={10} style={{ color: '#2563eb', marginLeft: 2 }} />}
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px 14px' }}>{children}</div>
    </div>
  );
}

// ─── RecordItem ────────────────────────────────────────────────────────────────

function RecordItem({ r, sel, onClick }: { r: UserProfile; sel: boolean; onClick: () => void }) {
  const rc = ROLE_CFG[r.role] ?? ROLE_CFG.customer;
  const name = userDisplayName(r);
  const hasName = name && name !== r.email;
  const initials = getInitials(name, r.email);

  return (
    <button
      onClick={onClick}
      style={{
        display: 'flex', alignItems: 'center', gap: 10,
        padding: '10px 14px', width: '100%', textAlign: 'left',
        background: sel ? '#EFF6FF' : 'transparent',
        borderLeft: `3px solid ${sel ? '#2563eb' : 'transparent'}`,
        borderBottom: '1px solid #F1F5F9',
        cursor: 'pointer',
      }}
    >
      <div style={{
        width: 36, height: 36, borderRadius: '50%', flexShrink: 0,
        background: r.photo_url ? 'transparent' : rc.bg, color: rc.color,
        overflow: 'hidden',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontSize: 12, fontWeight: 700,
      }}>
        {r.photo_url
          // eslint-disable-next-line @next/next/no-img-element
          ? <img src={r.photo_url} alt="" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
          : initials}
      </div>
      <div style={{ minWidth: 0, flex: 1 }}>
        <div style={{ fontSize: 13, fontWeight: 600, color: hasName ? '#0F172A' : '#94a3b8', fontStyle: hasName ? 'normal' : 'italic', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {hasName ? name : 'Kein Name'}
        </div>
        <div style={{ fontSize: 11, color: '#94a3b8', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', marginTop: 1 }}>
          {r.email}
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 5, marginTop: 4 }}>
          <span style={{ fontSize: 10, fontWeight: 700, padding: '1px 6px', borderRadius: 4, background: rc.bg, color: rc.color }}>{rc.label}</span>
          <span style={{ fontSize: 10, fontFamily: 'monospace', color: '#CBD5E1' }}>{fmtObjId(r.object_id)}</span>
        </div>
      </div>
    </button>
  );
}

// ─── Form sections (tabbed) ────────────────────────────────────────────────────

type GetVal = (k: keyof UserProfile) => string | boolean | null | undefined;
type SetVal = (k: keyof UserProfile) => (v: string | boolean) => void;
type TabId = 'stammdaten' | 'geschaeftlich' | 'anstellung' | 'system';

function FormSections({ v, set, record, isAdmin }: { v: GetVal; set: SetVal; record: UserProfile; isAdmin: boolean }) {
  const isSupplier = record.role === 'supplier';
  const isB2B = record.role === 'supplier' || record.role === 'customer';
  const isStaff = record.role === 'employee' || record.role === 'admin';

  const tabs: { id: TabId; label: string }[] = [
    { id: 'stammdaten', label: 'Stammdaten' },
    ...(isB2B   ? [{ id: 'geschaeftlich' as TabId, label: 'Geschäftlich' }] : []),
    ...(isStaff ? [{ id: 'anstellung'    as TabId, label: 'Anstellung'   }] : []),
    { id: 'system', label: 'System' },
  ];

  const [activeTab, setActiveTab] = useState<TabId>('stammdaten');

  return (
    <>
      {/* Tab bar */}
      <div style={{ display: 'flex', borderBottom: '1px solid #E2E8F0', marginBottom: 16, background: 'transparent' }}>
        {tabs.map(tab => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            style={{
              padding: '8px 14px', border: 'none', background: 'none', cursor: 'pointer',
              fontSize: 13, fontWeight: activeTab === tab.id ? 600 : 400,
              color: activeTab === tab.id ? '#2563eb' : '#64748b',
              borderBottom: `2px solid ${activeTab === tab.id ? '#2563eb' : 'transparent'}`,
              marginBottom: -1,
            }}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {activeTab === 'stammdaten' && (
        <>
          <Sec title="Rolle" editable={isAdmin} icon={Shield}>
            <div>
              <div style={{ fontSize: 11, fontWeight: 600, textTransform: 'uppercase' as const, letterSpacing: '0.05em', color: '#94a3b8', marginBottom: 4 }}>Rolle</div>
              {isAdmin ? (
                <select value={String(v('role') ?? 'customer')} onChange={e => set('role')(e.target.value)} className="w-full px-2.5 py-1.5 text-sm rounded-md border border-slate-200 bg-white outline-none focus:ring-2 focus:ring-blue-500 transition-colors">
                  <option value="admin">Admin</option>
                  <option value="employee">Mitarbeiter</option>
                  <option value="supplier">Lieferant</option>
                  <option value="customer">Kunde</option>
                </select>
              ) : (
                <div className="px-2.5 py-1.5 text-sm rounded-md border border-slate-100 bg-slate-50 text-slate-400">{ROLE_CFG[record.role]?.label ?? record.role}</div>
              )}
            </div>
          </Sec>

          <Sec title="Personalien" icon={User}>
            <Field label="Vorname"      val={v('first_name')}   ro />
            <Field label="Nachname"     val={v('last_name')}    ro />
            <Field label="Geburtsdatum" val={v('date_of_birth')} type="date" ro />
            <Field label="Telefon"      val={v('phone')}        ro />
          </Sec>

          <Sec title="Adresse" icon={MapPin}>
            <Field label="Adresszeile 1" val={v('address_line1')}  ro />
            <Field label="Adresszeile 2" val={v('address_line2')}  ro />
            <Field label="PLZ"           val={v('postal_code')}    ro />
            <Field label="Ort"           val={v('city')}           ro />
            <Field label="Region"        val={v('state_region')}   ro />
            <Field label="Land"          val={v('country')}        ro />
          </Sec>
        </>
      )}

      {activeTab === 'geschaeftlich' && isB2B && (
        <>
          <Sec title="Lieferadresse" icon={MapPin}>
            <Field label="Name"          val={v('ship_name')}          ro />
            <Field label="Firma"         val={v('ship_company')}       ro />
            <Field label="Adresszeile 1" val={v('ship_address_line1')} ro />
            <Field label="Adresszeile 2" val={v('ship_address_line2')} ro />
            <Field label="PLZ"           val={v('ship_postal_code')}   ro />
            <Field label="Ort"           val={v('ship_city')}          ro />
            <Field label="Region"        val={v('ship_state_region')}  ro />
            <Field label="Land"          val={v('ship_country')}       ro />
          </Sec>

          <Sec title="Rechnungsadresse" icon={Building2}>
            <Field label="Firma"               val={v('invoice_company')}          ro />
            <div />
            <Field label="Vorname"             val={v('invoice_first_name')}       ro />
            <Field label="Nachname"            val={v('invoice_last_name')}        ro />
            <Field label="Adresszeile 1"       val={v('invoice_address_line1')}    ro />
            <Field label="Adresszeile 2"       val={v('invoice_address_line2')}    ro />
            <Field label="PLZ"                 val={v('invoice_postal_code')}      ro />
            <Field label="Ort"                 val={v('invoice_city')}             ro />
            <Field label="Land"                val={v('invoice_country')}          ro />
            <Field label="Rechnungs-E-Mail"    val={v('invoice_email')}  type="email" ro />
            <Field label="Gleich wie Lieferadresse" val={v('invoice_same_as_shipping')} type="check" span2 ro />
          </Sec>

          <Sec title="Unternehmen" icon={Building2}>
            <Field label="Firmenname"      val={v('company_name')}           ro />
            <div />
            <Field label="UID-Nummer"      val={v('uid_number')}             ro />
            <Field label="MwSt-Nummer"     val={v('vat_number')}             ro />
            <Field label="HR-Nr."          val={v('trade_register_nr')}      ro />
            <Field label="HR-Kanton"       val={v('trade_register_canton')}  ro />
            <Field label="Website"         val={v('company_website')}        ro />
            <Field label="Rechnungs-E-Mail" val={v('company_billing_email')} type="email" ro />
            <Field label="MwSt. registriert" val={v('vat_registered')} type="check" span2 ro />
          </Sec>

          {isSupplier && (
            <Sec title="Bankverbindung">
              <Field label="Kontoinhaber" val={v('bank_account_holder')} ro />
              <Field label="Bank"         val={v('bank_name')}           ro />
              <Field label="IBAN"         val={v('bank_iban')}           ro />
              <Field label="BIC/SWIFT"    val={v('bank_bic')}            ro />
            </Sec>
          )}
        </>
      )}

      {activeTab === 'anstellung' && isStaff && (
        <Sec title="Anstellung" editable={isAdmin} icon={Briefcase}>
          <Field label="Abteilung"        val={v('department')}          onChange={isAdmin ? set('department') : undefined}          ro={!isAdmin} />
          <Field label="Berufsbezeichnung" val={v('job_title')}          onChange={isAdmin ? set('job_title') : undefined}           ro={!isAdmin} />
          <Field label="Eintrittsdatum"   val={v('employment_start_date')} onChange={isAdmin ? set('employment_start_date') : undefined} type="date" ro={!isAdmin} />
          <Field label="Wochenstunden"    val={v('weekly_hours')}        onChange={isAdmin ? set('weekly_hours') : undefined}        ro={!isAdmin} />
        </Sec>
      )}

      {activeTab === 'system' && (
        <>
          <Sec title="Einstellungen" icon={Settings}>
            <Field label="Sprache" val={v('language')} type="select" opts={['de', 'en']} ro />
            <div />
            <div className="col-span-2 flex flex-wrap gap-4">
              <Field label="E-Mail-Benachrichtigungen" val={v('notification_email')}  type="check" ro />
              <Field label="In-App-Benachrichtigungen"  val={v('notification_inapp')} type="check" ro />
              <Field label="Newsletter"                  val={v('newsletter_opt_in')} type="check" ro />
            </div>
          </Sec>

          <Sec title="System" icon={Shield}>
            <Field label="E-Mail"           val={record.email}                    ro />
            <Field label="Erstellt"         val={localDate(record.created_at)}    ro />
            <Field label="Zuletzt geändert" val={localDate(record.updated_at)}    ro />
            <Field label="Letzter Login"    val={localDate(record.last_login_at)} ro />
            <Field label="AGB akzeptiert"   val={localDate(record.terms_accepted_at)} ro />
            <Field label="AGB Version"      val={record.terms_version ?? '—'}     ro />
            {isAdmin && <Field label="Firebase UID" val={record.firebase_uid.slice(0, 16) + '…'} ro span2 />}
          </Sec>
        </>
      )}
    </>
  );
}

// ─── DetailPanel ───────────────────────────────────────────────────────────────

function DetailPanel({ record, onSave, isAdmin, onBack }: {
  record: UserProfile;
  onSave: (u: UserProfile) => void;
  isAdmin: boolean;
  onBack: () => void;
}) {
  const [form, setForm]     = useState<Partial<UserProfile>>({});
  const [dirty, setDirty]   = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError]   = useState<string | null>(null);

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
  const rc      = ROLE_CFG[currentRole] ?? ROLE_CFG.customer;
  const name    = userDisplayName(record);
  const hasName = name && name !== record.email;
  const initials = getInitials(name, record.email);

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div style={{ padding: '12px 20px', borderBottom: '1px solid #E2E8F0', background: '#fff', flexShrink: 0 }}>
        <button onClick={onBack} className="flex items-center gap-1 text-sm text-blue-600 mb-2 md:hidden">
          <ArrowLeft size={14} /> Zurück
        </button>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <div style={{
            width: 44, height: 44, borderRadius: '50%', flexShrink: 0,
            background: record.photo_url ? 'transparent' : rc.bg,
            color: rc.color, overflow: 'hidden',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 15, fontWeight: 700,
          }}>
            {record.photo_url
              // eslint-disable-next-line @next/next/no-img-element
              ? <img src={record.photo_url} alt="" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
              : initials}
          </div>
          <div style={{ minWidth: 0, flex: 1 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
              <span style={{ fontSize: 15, fontWeight: 700, color: hasName ? '#0F172A' : '#94a3b8', fontStyle: hasName ? 'normal' : 'italic' }}>
                {hasName ? name : 'Kein Name'}
              </span>
              <span style={{ fontSize: 10, fontWeight: 700, padding: '2px 7px', borderRadius: 4, background: rc.bg, color: rc.color }}>{rc.label}</span>
            </div>
            <div style={{ fontSize: 12, color: '#94a3b8', marginTop: 2 }}>{record.email}</div>
          </div>
          <div style={{ flexShrink: 0, textAlign: 'right' }}>
            <div style={{ fontSize: 10, color: '#CBD5E1', fontWeight: 600, textTransform: 'uppercase' as const, letterSpacing: '0.05em' }}>Obj.-Nr.</div>
            <div style={{ fontSize: 11, fontFamily: 'monospace', fontWeight: 600, color: '#94a3b8' }}>{fmtObjId(record.object_id)}</div>
          </div>
        </div>
      </div>

      {/* Content */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '16px 20px', background: '#F8FAFC' }}>
        <FormSections v={v} set={set} record={record} isAdmin={isAdmin} />
      </div>

      {/* Save bar */}
      {(dirty || error) && (
        <div style={{ padding: '10px 20px', background: '#fff', borderTop: '1px solid #E2E8F0', display: 'flex', alignItems: 'center', gap: 10, flexShrink: 0 }}>
          <span style={{ flex: 1, fontSize: 13, color: error ? '#dc2626' : '#64748b', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {error ?? 'Ungespeicherte Änderungen'}
          </span>
          <button
            onClick={() => { setForm({}); setDirty(false); setError(null); }}
            style={{ padding: '6px 14px', borderRadius: 7, border: '1px solid #E2E8F0', background: '#fff', fontSize: 13, color: '#374151', cursor: 'pointer', flexShrink: 0 }}
          >
            Verwerfen
          </button>
          <button
            onClick={save}
            disabled={saving}
            style={{ padding: '6px 14px', borderRadius: 7, border: 'none', background: saving ? '#93c5fd' : '#2563eb', color: '#fff', fontSize: 13, fontWeight: 600, cursor: saving ? 'wait' : 'pointer', flexShrink: 0 }}
          >
            {saving ? 'Speichern…' : 'Speichern'}
          </button>
        </div>
      )}
    </div>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function ErpPage() {
  const [records, setRecords]   = useState<UserProfile[]>([]);
  const [loading, setLoading]   = useState(true);
  const [search, setSearch]     = useState('');
  const [selId, setSelId]       = useState<number | null>(null);
  const [mobileView, setMobileView] = useState<'list' | 'detail'>('list');
  const [isAdmin, setIsAdmin]   = useState(false);
  const [roleFilter, setRoleFilter] = useState<string | null>(null);

  useEffect(() => {
    const cached = typeof window !== 'undefined' ? localStorage.getItem('inexxio_user_role') : null;
    setIsAdmin(cached === 'admin');
    api.getErpRecords()
      .then(r => { setRecords(r); setLoading(false); })
      .catch(() => setLoading(false));
  }, []);

  const filtered = records.filter(r => {
    if (roleFilter && r.role !== roleFilter) return false;
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

  const roleCounts = records.reduce<Record<string, number>>((acc, r) => {
    acc[r.role] = (acc[r.role] ?? 0) + 1;
    return acc;
  }, {});

  return (
    <div className="flex overflow-hidden" style={{ height: 'calc(100vh - 72px)' }}>

      {/* ── List panel ─────────────────────────────────────────────────────── */}
      <div className={cn(
        'flex-shrink-0 border-r border-slate-200 flex flex-col bg-white',
        'w-full md:w-[300px] lg:w-[340px]',
        showList ? 'flex' : 'hidden md:flex',
      )}>
        <div style={{ padding: '14px 14px 10px', borderBottom: '1px solid #F1F5F9' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
            <span style={{ fontSize: 13, fontWeight: 700, color: '#0F172A' }}>Datensätze</span>
            <span style={{ fontSize: 12, color: '#94a3b8' }}>{filtered.length} / {records.length}</span>
          </div>
          <div style={{ position: 'relative' }}>
            <Search size={13} style={{ position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)', color: '#94a3b8', pointerEvents: 'none' }} />
            <input
              value={search}
              onChange={e => setSearch(e.target.value)}
              placeholder="Name, E-Mail, Nummer…"
              style={{
                width: '100%', paddingLeft: 30, paddingRight: 12, paddingTop: 7, paddingBottom: 7,
                fontSize: 13, border: '1px solid #E2E8F0', borderRadius: 8, background: '#F8FAFC',
                outline: 'none', boxSizing: 'border-box' as const,
              }}
            />
          </div>
          {/* Role filter pills */}
          <div style={{ display: 'flex', gap: 5, marginTop: 10, flexWrap: 'wrap' }}>
            {(['admin', 'employee', 'supplier', 'customer'] as const)
              .filter(role => roleCounts[role])
              .map(role => {
                const rc = ROLE_CFG[role];
                const active = roleFilter === role;
                return (
                  <button
                    key={role}
                    onClick={() => setRoleFilter(active ? null : role)}
                    style={{
                      padding: '3px 8px', borderRadius: 12,
                      border: `1px solid ${active ? rc.color : '#E2E8F0'}`,
                      background: active ? rc.bg : '#fff',
                      color: active ? rc.color : '#64748b',
                      fontSize: 11, fontWeight: 600, cursor: 'pointer',
                    }}
                  >
                    {rc.label} {roleCounts[role]}
                  </button>
                );
              })}
          </div>
        </div>

        <div style={{ flex: 1, overflowY: 'auto' }}>
          {loading && <div style={{ padding: 24, textAlign: 'center', fontSize: 13, color: '#94a3b8' }}>Laden…</div>}
          {!loading && filtered.length === 0 && (
            <div style={{ padding: 24, textAlign: 'center', fontSize: 13, color: '#94a3b8' }}>
              {search || roleFilter ? 'Keine Treffer' : 'Keine Datensätze'}
            </div>
          )}
          {filtered.map(r => (
            <RecordItem key={r.id} r={r} sel={r.object_id === selId} onClick={() => handleSelect(r.object_id ?? null)} />
          ))}
        </div>
      </div>

      {/* ── Detail panel ───────────────────────────────────────────────────── */}
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
            <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>
              <User size={48} strokeWidth={1} style={{ color: '#CBD5E1' }} />
              <p style={{ marginTop: 12, fontSize: 14, color: '#94a3b8' }}>Datensatz auswählen</p>
            </div>
          )
        }
      </div>
    </div>
  );
}
