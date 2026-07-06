'use client';

import { useState, useEffect } from 'react';
import { User, ArrowLeft, Pencil, MapPin, Building2, Shield, Settings, Briefcase, Truck, UserCircle, ShoppingBag } from 'lucide-react';
import { cn, userDisplayName } from '@/lib/utils';
import { api } from '@/lib/api';
import { OrdersList } from '@/components/orders-list';
import { ObjectDocuments } from '@/components/erp/object-documents';
import type { UserProfile, CustomerOrder } from '@/types';
import type { StatusCfg } from '@/lib/status-flow';
import { localDate } from '@/lib/utils';

// ─── Helpers ─────────────────────────────────────────────────────────────────

export function fmtObjId(id: number | null | undefined): string {
  if (!id) return '—';
  return String(id).padStart(9, '0');
}

export const ROLE_CFG: Record<string, StatusCfg> = {
  admin:    { label: 'Admin',       color: '#dc2626', bg: '#fef2f2', icon: Shield },
  employee: { label: 'Mitarbeiter', color: '#2563eb', bg: '#eff6ff', icon: Briefcase },
  supplier: { label: 'Lieferant',   color: '#d97706', bg: '#fffbeb', icon: Truck },
  customer: { label: 'Kunde',       color: '#16a34a', bg: '#f0fdf4', icon: UserCircle },
};

const COUNTRY_NAMES: Record<string, string> = {
  CH: 'Schweiz', DE: 'Deutschland', AT: 'Österreich', FR: 'Frankreich',
  IT: 'Italien', LI: 'Liechtenstein', LU: 'Luxemburg', NL: 'Niederlande',
  BE: 'Belgien', ES: 'Spanien', PT: 'Portugal', GB: 'Grossbritannien',
  US: 'USA', PL: 'Polen', CZ: 'Tschechien', SK: 'Slowakei', HU: 'Ungarn',
  HR: 'Kroatien', SI: 'Slowenien', RO: 'Rumänien', BG: 'Bulgarien',
  SE: 'Schweden', NO: 'Norwegen', DK: 'Dänemark', FI: 'Finnland',
};

function countryName(code: string | null | undefined): string {
  if (!code) return '';
  return COUNTRY_NAMES[code.toUpperCase()] ?? code;
}


export function userInitials(name: string, email: string): string {
  if (name && name !== email) {
    return name.split(' ').filter(Boolean).map(n => n[0]).join('').toUpperCase().slice(0, 2);
  }
  return email[0]?.toUpperCase() ?? '?';
}

// ─── Field ───────────────────────────────────────────────────────────────────

interface FieldProps {
  label: string;
  val: string | boolean | number | null | undefined;
  onChange?: (v: string | boolean) => void;
  type?: 'text' | 'date' | 'select' | 'check' | 'email';
  opts?: string[];
  ro?: boolean;
  span2?: boolean;
}

export function Field({ label, val, onChange, type = 'text', opts, ro, span2 }: FieldProps) {
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

// ─── Section card ────────────────────────────────────────────────────────────

export function Sec({ title, children, editable, icon: Icon }: {
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

// ─── Form sections ───────────────────────────────────────────────────────────

type GetVal = (k: keyof UserProfile) => string | boolean | null | undefined;
type SetVal = (k: keyof UserProfile) => (v: string | boolean) => void;

function FormSections({ v, set, record, isAdmin }: { v: GetVal; set: SetVal; record: UserProfile; isAdmin: boolean }) {
  const isSupplier = record.role === 'supplier';
  const isB2B      = record.role === 'supplier' || record.role === 'customer';
  const isStaff    = record.role === 'employee'  || record.role === 'admin';

  return (
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
        <Field label="Vorname"      val={v('first_name')}    ro />
        <Field label="Nachname"     val={v('last_name')}     ro />
        <Field label="Geburtsdatum" val={v('date_of_birth')} type="date" ro />
        <Field label="Telefon"      val={v('phone')}         ro />
      </Sec>

      <Sec title="Adresse" icon={MapPin}>
        <Field label="Adresszeile 1" val={v('address_line1')}              ro />
        <Field label="Adresszeile 2" val={v('address_line2')}              ro />
        <Field label="PLZ"           val={v('postal_code')}                ro />
        <Field label="Ort"           val={v('city')}                       ro />
        <Field label="Region"        val={v('state_region')}               ro />
        <Field label="Land"          val={countryName(v('country') as string)} ro />
      </Sec>

      {isB2B && (
        <Sec title="Rechnungsadresse" icon={Building2}>
          <Field label="Firma"            val={v('invoice_company')}       ro />
          <div />
          <Field label="Vorname"          val={v('invoice_first_name')}    ro />
          <Field label="Nachname"         val={v('invoice_last_name')}     ro />
          <Field label="Adresszeile 1"    val={v('invoice_address_line1')} ro />
          <Field label="Adresszeile 2"    val={v('invoice_address_line2')} ro />
          <Field label="PLZ"              val={v('invoice_postal_code')}   ro />
          <Field label="Ort"              val={v('invoice_city')}          ro />
          <Field label="Land"             val={countryName(v('invoice_country') as string)} ro />
          <Field label="Rechnungs-E-Mail" val={v('invoice_email')} type="email" ro />
          <Field label="Gleich wie Adresse" val={v('invoice_same_as_shipping')} type="check" span2 ro />
        </Sec>
      )}

      {isB2B && (
        <Sec title="Unternehmen" icon={Building2}>
          <Field label="Firmenname"       val={v('company_name')}          ro />
          <Field label="UID-Nummer"       val={v('uid_number')}            ro />
          <Field label="Rechnungs-E-Mail" val={v('company_billing_email')} type="email" ro />
        </Sec>
      )}

      {isSupplier && (
        <Sec title="Bankverbindung">
          <Field label="Kontoinhaber" val={v('bank_account_holder')} ro />
          <Field label="Bank"         val={v('bank_name')}           ro />
          <Field label="IBAN"         val={v('bank_iban')}           ro />
          <Field label="BIC/SWIFT"    val={v('bank_bic')}            ro />
        </Sec>
      )}

      {isStaff && (
        <Sec title="Anstellung" editable={isAdmin} icon={Briefcase}>
          <Field label="Abteilung"         val={v('department')}            onChange={isAdmin ? set('department') : undefined}            ro={!isAdmin} />
          <Field label="Berufsbezeichnung" val={v('job_title')}             onChange={isAdmin ? set('job_title') : undefined}             ro={!isAdmin} />
          <Field label="Eintrittsdatum"    val={v('employment_start_date')} onChange={isAdmin ? set('employment_start_date') : undefined} type="date" ro={!isAdmin} />
          <Field label="Wochenstunden"     val={v('weekly_hours')}          onChange={isAdmin ? set('weekly_hours') : undefined}          ro={!isAdmin} />
        </Sec>
      )}

      <Sec title="Einstellungen" icon={Settings}>
        <div className="col-span-2 flex flex-wrap gap-4">
          <Field label="E-Mail-Benachrichtigungen" val={v('notification_email')}  type="check" ro />
          <Field label="In-App-Benachrichtigungen"  val={v('notification_inapp')} type="check" ro />
          <Field label="Newsletter"                  val={v('newsletter_opt_in')} type="check" ro />
        </div>
      </Sec>

      <Sec title="System" icon={Shield}>
        <Field label="E-Mail"           val={record.email}                       ro />
        <Field label="Erstellt"         val={localDate(record.created_at)}       ro />
        <Field label="Zuletzt geändert" val={localDate(record.updated_at)}       ro />
        <Field label="Letzter Login"    val={localDate(record.last_login_at)}    ro />
        <Field label="AGB akzeptiert"   val={localDate(record.terms_accepted_at)} ro />
        <Field label="AGB Version"      val={record.terms_version ?? '—'}        ro />
        {isAdmin && <Field label="Firebase UID" val={record.firebase_uid.slice(0, 16) + '…'} ro span2 />}
      </Sec>
    </>
  );
}

// ─── Bestellungen (Reiter) ─────────────────────────────────────────────────────

function OrdersSec({ objectId }: { objectId: number | null | undefined }) {
  const [orders, setOrders] = useState<CustomerOrder[] | null>(null);
  useEffect(() => {
    if (!objectId) return;
    setOrders(null);
    api.getRecordOrders(objectId).then(setOrders).catch(() => setOrders([]));
  }, [objectId]);

  return (
    <div style={{ background: '#fff', border: '1px solid #E2E8F0', borderRadius: 10, padding: '14px 16px', marginBottom: 12 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 12, paddingBottom: 10, borderBottom: '1px solid #F1F5F9' }}>
        <ShoppingBag size={13} style={{ color: '#94a3b8' }} />
        <span style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase' as const, letterSpacing: '0.07em', color: '#64748b' }}>Bestellungen</span>
      </div>
      {orders === null
        ? <div style={{ fontSize: 13, color: '#94a3b8' }}>Lädt…</div>
        : <OrdersList orders={orders} />}
    </div>
  );
}

// ─── UserDetail ──────────────────────────────────────────────────────────────

export function UserDetail({ record, onSave, isAdmin, onBack }: {
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
  const rc       = ROLE_CFG[currentRole] ?? ROLE_CFG.customer;
  const name     = userDisplayName(record);
  const hasName  = name && name !== record.email;
  const initials = userInitials(name, record.email);

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
            <div style={{ fontSize: 12, fontFamily: 'monospace', fontWeight: 700, color: '#475569' }}>{fmtObjId(record.object_id)}</div>
          </div>
        </div>
      </div>

      {/* Content */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '16px 20px', background: '#F8FAFC' }}>
        <FormSections v={v} set={set} record={record} isAdmin={isAdmin} />
        <OrdersSec objectId={record.object_id} />
        <div style={{ background: '#fff', border: '1px solid #E2E8F0', borderRadius: 10, padding: '14px 16px', marginBottom: 12 }}>
          <ObjectDocuments objectId={record.object_id} contextLabel="dieser Person" />
        </div>
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
