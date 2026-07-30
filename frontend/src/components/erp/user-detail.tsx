'use client';

import { useState, useEffect, useRef } from 'react';
import {
  User, Pencil, MapPin, Building2, Shield, Briefcase, Truck, UserCircle,
  ShoppingBag, FolderOpen, Link2, Bell, Check, CreditCard, Cog,
} from 'lucide-react';
import { cn, userDisplayName, localDate } from '@/lib/utils';
import { api } from '@/lib/api';
import { OrdersList } from '@/components/orders-list';
import { ObjectDocuments } from '@/components/erp/object-documents';
import { UserDocumentsOverview } from '@/components/erp/user-documents';
import { ObjectReferences } from '@/components/erp/object-references';
import { DetailTabs } from '@/components/erp/detail-tabs';
import { DetailHeader } from '@/components/erp/fields';
// **ERP ist Master, das Profil ist der Spiegel** – und weil dem Nutzer Struktur, Logik
// und Namensgebung der Profileinstellungen besser gefallen (Notiz #294), übernimmt der
// Profil-Reiter hier **dieselben Bausteine** wie das Konto: EIN Formular, EIN Auto-Save,
// «Rechnungsadresse = Lieferadresse»-Schalter mit Spiegelung, Google-Adress-Suche. Keine
// zweite Optik, kein zweiter Feld-Satz – nur die ERP-Extras kommen dazu (Notiz #295:
// Rolle, Bankverbindung, admin-pflegbare Anstellung, System). Reuse statt Nachbau.
import { Field as AField, ToggleField, SelectField } from '@/components/account/field';
import { AddressField, type Address } from '@/components/erp/address-field';
import { useMapsApiKey } from '@/components/erp/use-maps-key';
import { useAutosave } from '@/components/account/use-autosave';
import { SaveStatusIndicator } from '@/components/account/save-status';
import type { UserProfile, CustomerOrder, UserRole } from '@/types';
import type { StatusCfg } from '@/lib/status-flow';

type UserTab = 'profil' | 'orders' | 'verwendung' | 'docs';

// ─── Helpers ─────────────────────────────────────────────────────────────────

// Re-Export der EINEN Regel (``lib/utils.formatObjectId``) – die vielen Aufrufstellen
// heissen historisch ``fmtObjId``.
export { formatObjectId as fmtObjId } from '@/lib/utils';

// Eine Rolle ist kein Lebenszyklus-Status, aber ein aktiver Benutzer ist ein **gültiger,
// aktiver** Datensatz – darum GRÜN (nicht Grau, das nach «aus» aussähe; deaktivierte Nutzer
// erscheinen ohnehin nicht im Feed). Die Rolle selbst trägt Symbol + Label zur Unterscheidung.
export const ROLE_CFG: Record<string, StatusCfg> = {
  admin:    { label: 'Admin',       color: 'var(--success)', bg: 'var(--success-bg)', icon: Shield },
  employee: { label: 'Mitarbeiter', color: 'var(--success)', bg: 'var(--success-bg)', icon: Briefcase },
  supplier: { label: 'Lieferant',   color: 'var(--success)', bg: 'var(--success-bg)', icon: Truck },
  customer: { label: 'Kunde',       color: 'var(--success)', bg: 'var(--success-bg)', icon: UserCircle },
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

// Auswahl für den manuellen Adress-Modus – **ISO-2-Werte** wie in den Profileinstellungen
// (dort werden dieselben sechs Länder geführt). Das Land-Format bestimmt `AddressField`.
const COUNTRIES: [string, string][] = [
  ['CH', 'Schweiz'], ['DE', 'Deutschland'], ['AT', 'Österreich'],
  ['FR', 'Frankreich'], ['IT', 'Italien'], ['LI', 'Liechtenstein'],
];

export function userInitials(name: string, email: string): string {
  if (name && name !== email) {
    return name.split(' ').filter(Boolean).map(n => n[0]).join('').toUpperCase().slice(0, 2);
  }
  return email[0]?.toUpperCase() ?? '?';
}

// ─── Field (ALT) ───────────────────────────────────────────────────────────────
// Wird noch vom Unternehmens-Datensatz (`organization-detail.tsx`) genutzt – bleibt
// unverändert erhalten. Der Benutzer-Profil-Reiter darunter nutzt die Konto-Bausteine.

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

// ─── Section card (ALT) ────────────────────────────────────────────────────────
// Ebenfalls von `organization-detail.tsx` genutzt – unverändert.

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
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 220px), 1fr))', gap: '10px 14px' }}>{children}</div>
    </div>
  );
}

// ─── Karten-Bausteine (Spiegel der Profileinstellungen) ────────────────────────
// Gleiche Anatomie wie `account/sections/profile-section.tsx`, damit «fast eine
// Spiegelung» entsteht (Notiz #294) – Symbol + Titel + optionaler rechter Slot.

function Card({ icon: Icon, title, right, children }: {
  icon: React.ElementType; title: string; right?: React.ReactNode; children: React.ReactNode;
}) {
  return (
    <div style={{ background: '#fff', border: '1px solid var(--border-1)', borderRadius: 12, overflow: 'hidden' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '18px 24px', borderBottom: '1px solid var(--border-1)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <Icon style={{ width: 16, height: 16, color: 'var(--fg-3)' }} />
          <h2 style={{ fontSize: 15, fontWeight: 600, color: 'var(--fg-1)', margin: 0 }}>{title}</h2>
        </div>
        {right}
      </div>
      <div style={{ padding: 24, display: 'flex', flexDirection: 'column', gap: 20 }}>{children}</div>
    </div>
  );
}

function SubBlock({ icon: Icon, title, children }: {
  icon: React.ElementType; title: string; children: React.ReactNode;
}) {
  return (
    <div style={{ padding: 16, background: 'var(--bg-2)', borderRadius: 10, border: '1px solid var(--border-1)' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 14 }}>
        <Icon style={{ width: 13, height: 13, color: 'var(--fg-3)' }} />
        <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--fg-3)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
          {title}
        </span>
      </div>
      {children}
    </div>
  );
}

/** Read-only-Adresse (Nicht-Admin sieht, ändert nicht). `AddressField` ist ein
 *  Editier-Baustein (Suche + «Ändern») – für die reine Anzeige die kompakte
 *  Zusammenfassung, die dieselbe Optik wie sein gefüllter Zustand trägt. */
function AddrSummary({ label, a }: { label: string; a: Address }) {
  const empty = !a.street?.trim() && !a.zip?.trim() && !a.city?.trim();
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
        <MapPin size={14} style={{ color: 'var(--fg-3)' }} />
        <span style={{ font: '600 13px var(--font-body)', color: 'var(--fg-2)' }}>{label}</span>
      </div>
      {empty ? (
        <div style={{ fontSize: 13, color: 'var(--fg-4)' }}>Nicht erfasst</div>
      ) : (
        <div style={{ padding: '11px 13px', borderRadius: 'var(--r-md)', border: '1px solid var(--border-1)', background: 'var(--bg-2)', lineHeight: 1.5 }}>
          <div style={{ font: '600 13.5px var(--font-body)', color: 'var(--fg-1)' }}>{a.street || '—'}</div>
          {a.street2 && <div style={{ fontSize: 13, color: 'var(--fg-3)' }}>{a.street2}</div>}
          <div style={{ fontSize: 13, color: 'var(--fg-3)' }}>{[a.zip, a.city].filter(Boolean).join(' ')}</div>
          {a.region && <div style={{ fontSize: 13, color: 'var(--fg-3)' }}>{a.region}</div>}
          <div style={{ fontSize: 13, color: 'var(--fg-3)' }}>{countryName(a.country)}</div>
        </div>
      )}
    </div>
  );
}

// ─── Formular (Spiegel des Profils + ERP-Extras) ───────────────────────────────

interface ERPForm {
  role: UserRole;
  first_name: string;
  last_name: string;
  date_of_birth: string;
  phone: string;
  company_name: string;
  uid_number: string;
  company_billing_email: string;
  address_line1: string;
  address_line2: string;
  postal_code: string;
  city: string;
  state_region: string;
  country: string;
  invoice_same_as_shipping: boolean;
  invoice_company: string;
  invoice_first_name: string;
  invoice_last_name: string;
  invoice_address_line1: string;
  invoice_address_line2: string;
  invoice_postal_code: string;
  invoice_city: string;
  invoice_country: string;
  invoice_email: string;
  bank_account_holder: string;
  bank_name: string;
  bank_iban: string;
  bank_bic: string;
  department: string;
  job_title: string;
  employment_start_date: string;
  weekly_hours: string;
  newsletter_opt_in: boolean;
}

type StrKey = { [K in keyof ERPForm]: ERPForm[K] extends string ? K : never }[keyof ERPForm];

function buildForm(p: UserProfile): ERPForm {
  return {
    role: p.role,
    first_name: p.first_name ?? '',
    last_name: p.last_name ?? '',
    date_of_birth: p.date_of_birth ?? '',
    phone: p.phone ?? '',
    company_name: p.company_name ?? '',
    uid_number: p.uid_number ?? '',
    company_billing_email: p.company_billing_email ?? '',
    address_line1: p.address_line1 ?? '',
    address_line2: p.address_line2 ?? '',
    postal_code: p.postal_code ?? '',
    city: p.city ?? '',
    state_region: p.state_region ?? '',
    country: p.country ?? 'CH',
    invoice_same_as_shipping: p.invoice_same_as_shipping ?? true,
    invoice_company: p.invoice_company ?? '',
    invoice_first_name: p.invoice_first_name ?? '',
    invoice_last_name: p.invoice_last_name ?? '',
    invoice_address_line1: p.invoice_address_line1 ?? '',
    invoice_address_line2: p.invoice_address_line2 ?? '',
    invoice_postal_code: p.invoice_postal_code ?? '',
    invoice_city: p.invoice_city ?? '',
    invoice_country: p.invoice_country ?? 'CH',
    invoice_email: p.invoice_email ?? '',
    bank_account_holder: p.bank_account_holder ?? '',
    bank_name: p.bank_name ?? '',
    bank_iban: p.bank_iban ?? '',
    bank_bic: p.bank_bic ?? '',
    department: p.department ?? '',
    job_title: p.job_title ?? '',
    employment_start_date: p.employment_start_date ?? '',
    weekly_hours: p.weekly_hours != null ? String(p.weekly_hours) : '',
    newsletter_opt_in: p.newsletter_opt_in ?? false,
  };
}

const nn = (s: string): string | null => (s.trim() === '' ? null : s);

/** Form → Update-Payload. **Dieselbe Spiegel-Logik wie im Profil:** «Rechnung =
 *  Lieferung» kopiert die Rechnungsfelder aus der Adresse (EIN Datensatz, eine
 *  Wahrheit); rollen-fremde Felder (Firma/Bank nur Lieferant, Anstellung nur Staff)
 *  werden nicht mitgeschickt. */
function mapUpdate(v: ERPForm): Partial<UserProfile> {
  const isSupplier = v.role === 'supplier';
  const isStaff = v.role === 'employee' || v.role === 'admin';
  const data: Record<string, unknown> = {
    role: v.role,
    first_name: nn(v.first_name),
    last_name: nn(v.last_name),
    date_of_birth: nn(v.date_of_birth),
    phone: nn(v.phone),
    address_line1: nn(v.address_line1),
    address_line2: nn(v.address_line2),
    postal_code: nn(v.postal_code),
    city: nn(v.city),
    state_region: nn(v.state_region),
    country: v.country || 'CH',
    invoice_same_as_shipping: v.invoice_same_as_shipping,
    invoice_email: nn(v.invoice_email),
    newsletter_opt_in: v.newsletter_opt_in,
  };
  if (v.invoice_same_as_shipping) {
    data.invoice_company = isSupplier ? nn(v.company_name) : null;
    data.invoice_first_name = nn(v.first_name);
    data.invoice_last_name = nn(v.last_name);
    data.invoice_address_line1 = nn(v.address_line1);
    data.invoice_address_line2 = nn(v.address_line2);
    data.invoice_postal_code = nn(v.postal_code);
    data.invoice_city = nn(v.city);
    data.invoice_country = v.country || 'CH';
  } else {
    data.invoice_company = isSupplier ? nn(v.invoice_company) : null;
    data.invoice_first_name = nn(v.invoice_first_name);
    data.invoice_last_name = nn(v.invoice_last_name);
    data.invoice_address_line1 = nn(v.invoice_address_line1);
    data.invoice_address_line2 = nn(v.invoice_address_line2);
    data.invoice_postal_code = nn(v.invoice_postal_code);
    data.invoice_city = nn(v.invoice_city);
    data.invoice_country = v.invoice_country || 'CH';
  }
  if (isSupplier) {
    data.company_name = nn(v.company_name);
    data.uid_number = nn(v.uid_number);
    data.company_billing_email = nn(v.company_billing_email);
    data.bank_account_holder = nn(v.bank_account_holder);
    data.bank_name = nn(v.bank_name);
    data.bank_iban = nn(v.bank_iban);
    data.bank_bic = nn(v.bank_bic);
  }
  if (isStaff) {
    data.department = nn(v.department);
    data.job_title = nn(v.job_title);
    data.employment_start_date = nn(v.employment_start_date);
    data.weekly_hours = nn(v.weekly_hours);
  }
  return data as Partial<UserProfile>;
}

function ProfileForm({ record, isAdmin, onSaved }: {
  record: UserProfile; isAdmin: boolean; onSaved: (u: UserProfile) => void;
}) {
  const canEdit = isAdmin;
  const ro = !canEdit;
  const mapsKey = useMapsApiKey();
  const [form, setForm] = useState<ERPForm>(() => buildForm(record));
  const [resetKey, setResetKey] = useState(0);
  const prevId = useRef<number | null | undefined>(undefined);

  // Nur bei Datensatz-Wechsel neu aufbauen (nicht bei jedem `record`-Prop) – sonst
  // klobbert ein Auto-Save → onSaved → neuer Prop die gerade getippte Eingabe.
  useEffect(() => {
    if (record.object_id !== prevId.current) {
      prevId.current = record.object_id;
      setForm(buildForm(record));
      setResetKey((k) => k + 1);
    }
  }, [record.object_id, record]);

  const { status, errorMsg, saveNow } = useAutosave(
    form,
    async (v) => {
      if (!canEdit || !record.object_id) return;
      const updated = await api.updateErpRecord(record.object_id, mapUpdate(v));
      onSaved(updated);
    },
    2500,
    resetKey,
  );

  function set<K extends keyof ERPForm>(key: K, value: ERPForm[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }
  const str = (k: StrKey) => (canEdit ? (val: string) => setForm((prev) => ({ ...prev, [k]: val })) : undefined);

  const role = form.role;
  const isSupplier = role === 'supplier';
  const isStaff = role === 'employee' || role === 'admin';

  const address: Address = {
    street: form.address_line1, street2: form.address_line2, zip: form.postal_code,
    city: form.city, region: form.state_region, country: form.country,
  };
  const applyAddress = (a: Address) => setForm((p) => ({
    ...p, address_line1: a.street, address_line2: a.street2 ?? '', postal_code: a.zip,
    city: a.city, state_region: a.region ?? '', country: a.country,
  }));

  const invoiceAddress: Address = {
    street: form.invoice_address_line1, street2: form.invoice_address_line2,
    zip: form.invoice_postal_code, city: form.invoice_city, country: form.invoice_country,
  };
  const applyInvoiceAddress = (a: Address) => setForm((p) => ({
    ...p, invoice_address_line1: a.street, invoice_address_line2: a.street2 ?? '',
    invoice_postal_code: a.zip, invoice_city: a.city, invoice_country: a.country,
  }));

  const termsDate = record.terms_accepted_at
    ? new Date(record.terms_accepted_at).toLocaleDateString('de-CH') : null;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {/* ── 1. Persönliche Angaben ─────────────────────────────────────────── */}
      <Card icon={User} title="Persönliche Angaben" right={canEdit ? <SaveStatusIndicator status={status} errorMsg={errorMsg} /> : undefined}>
        {/* Rolle – ERP-Extra (das Konto kennt sie nicht, die eigene Rolle ändert man nicht). */}
        {canEdit ? (
          <SelectField label="Rolle" value={role} onChange={(x) => set('role', x as UserRole)} options={[
            { value: 'admin', label: 'Admin' }, { value: 'employee', label: 'Mitarbeiter' },
            { value: 'supplier', label: 'Lieferant' }, { value: 'customer', label: 'Kunde' },
          ]} />
        ) : (
          <AField label="Rolle" value={ROLE_CFG[role]?.label ?? role} readOnly />
        )}

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <AField label="Vorname" value={form.first_name} onChange={str('first_name')} readOnly={ro} placeholder="Max" onEnter={saveNow} />
          <AField label="Nachname" value={form.last_name} onChange={str('last_name')} readOnly={ro} placeholder="Muster" onEnter={saveNow} />
          <AField label="Telefon" value={form.phone} onChange={str('phone')} readOnly={ro} type="tel" placeholder="+41 44 000 00 00" onEnter={saveNow} />
          <AField label="Geburtsdatum" value={form.date_of_birth} onChange={str('date_of_birth')} readOnly={ro} type="date" onEnter={saveNow} />
        </div>

        {isSupplier && (
          <SubBlock icon={Building2} title="Firmendaten">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <AField label="Firmenname" value={form.company_name} onChange={str('company_name')} readOnly={ro} placeholder="Muster AG" onEnter={saveNow} />
              <AField label="UID-Nummer" value={form.uid_number} onChange={str('uid_number')} readOnly={ro} placeholder="CHE-123.456.789" onEnter={saveNow} />
              <div className="sm:col-span-2">
                <AField label="Rechnungs-E-Mail (Firma)" value={form.company_billing_email} onChange={str('company_billing_email')} readOnly={ro} type="email" onEnter={saveNow} />
              </div>
            </div>
          </SubBlock>
        )}

        {/* Anstellung: im Profil read-only, **im ERP admin-pflegbar** (Notiz #295 –
            «das ERP muss ALLES können»; ``ErpAdminUpdate`` erbt + ergänzt genau das). */}
        {isStaff && (
          <SubBlock icon={Briefcase} title="Anstellung">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <AField label="Abteilung" value={form.department} onChange={str('department')} readOnly={ro} onEnter={saveNow} />
              <AField label="Funktion" value={form.job_title} onChange={str('job_title')} readOnly={ro} onEnter={saveNow} />
              <AField label="Eintrittsdatum" value={form.employment_start_date} onChange={str('employment_start_date')} readOnly={ro} type="date" onEnter={saveNow} />
              <AField label="Pensum (h/Woche)" value={form.weekly_hours} onChange={str('weekly_hours')} readOnly={ro} onEnter={saveNow} />
            </div>
          </SubBlock>
        )}

        {isSupplier && (
          <SubBlock icon={CreditCard} title="Bankverbindung">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <AField label="Kontoinhaber" value={form.bank_account_holder} onChange={str('bank_account_holder')} readOnly={ro} onEnter={saveNow} />
              <AField label="Bank" value={form.bank_name} onChange={str('bank_name')} readOnly={ro} onEnter={saveNow} />
              <AField label="IBAN" value={form.bank_iban} onChange={str('bank_iban')} readOnly={ro} onEnter={saveNow} />
              <AField label="BIC/SWIFT" value={form.bank_bic} onChange={str('bank_bic')} readOnly={ro} onEnter={saveNow} />
            </div>
          </SubBlock>
        )}
      </Card>

      {/* ── 2. Adressen (Lieferung + Rechnung in EINEM Container) ───────────── */}
      <Card icon={MapPin} title="Adressen">
        {canEdit ? (
          <AddressField value={address} onChange={applyAddress} apiKey={mapsKey}
            countryOptions={COUNTRIES} showStreet2 showRegion label="Lieferadresse" />
        ) : (
          <AddrSummary label="Lieferadresse" a={address} />
        )}

        <div style={{ height: 1, background: 'var(--border-1)' }} />

        {canEdit ? (
          <ToggleField label="Rechnungsadresse = Lieferadresse" checked={form.invoice_same_as_shipping}
            onChange={(x) => set('invoice_same_as_shipping', x)} />
        ) : (
          <AField label="Rechnungsadresse = Lieferadresse" value={form.invoice_same_as_shipping ? 'Ja' : 'Nein'} readOnly />
        )}

        {!form.invoice_same_as_shipping && (canEdit ? (
          <>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {isSupplier && (
                <div className="sm:col-span-2">
                  <AField label="Firmenname" value={form.invoice_company} onChange={str('invoice_company')} onEnter={saveNow} />
                </div>
              )}
              <AField label="Vorname" value={form.invoice_first_name} onChange={str('invoice_first_name')} onEnter={saveNow} />
              <AField label="Nachname" value={form.invoice_last_name} onChange={str('invoice_last_name')} onEnter={saveNow} />
            </div>
            <AddressField value={invoiceAddress} onChange={applyInvoiceAddress} apiKey={mapsKey}
              countryOptions={COUNTRIES} showStreet2 label="Rechnungsadresse" />
          </>
        ) : (
          <>
            {isSupplier && <AField label="Firmenname" value={form.invoice_company} readOnly />}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <AField label="Vorname" value={form.invoice_first_name} readOnly />
              <AField label="Nachname" value={form.invoice_last_name} readOnly />
            </div>
            <AddrSummary label="Rechnungsadresse" a={invoiceAddress} />
          </>
        ))}

        {/* Rechnungs-E-Mail: leer = die Konto-Adresse (als Platzhalter sichtbar). */}
        <AField label="Rechnungs-E-Mail" value={form.invoice_email} onChange={str('invoice_email')}
          readOnly={ro} type="email" placeholder={record.email ?? 'rechnung@firma.ch'} onEnter={saveNow} />
      </Card>

      {/* ── 3. Kommunikation & Rechtliches ──────────────────────────────────── */}
      <Card icon={Bell} title="Kommunikation">
        {canEdit ? (
          <ToggleField label="Newsletter" description="Produktneuigkeiten und Angebote per E-Mail"
            checked={form.newsletter_opt_in} onChange={(x) => set('newsletter_opt_in', x)} />
        ) : (
          <AField label="Newsletter" value={form.newsletter_opt_in ? 'Abonniert' : 'Nicht abonniert'} readOnly />
        )}
        {/* Kein Schalter, sondern eine Tatsache (wie im Profil): die Rechtstexte sind
            akzeptiert. Die vollständige, versionierte Historie führt der Reiter «Dokumente». */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap', fontSize: 13, color: 'var(--fg-3)' }}>
          {termsDate && <Check size={15} style={{ color: 'var(--success)', flexShrink: 0 }} />}
          <span>
            {termsDate
              ? `AGB und Datenschutzerklärung akzeptiert am ${termsDate}${record.terms_version ? ` · v${record.terms_version}` : ''}`
              : 'AGB und Datenschutzerklärung noch nicht akzeptiert'}
          </span>
        </div>
      </Card>

      {/* ── 4. System (ERP-Extra, read-only – Notiz #295) ───────────────────── */}
      <Card icon={Cog} title="System">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <AField label="E-Mail" value={record.email} readOnly />
          <AField label="Anmeldung" value={signInLabel(record.last_sign_in_provider)} readOnly />
          <AField label="Passkeys" value={passkeyLabel(record.passkey_count)} readOnly />
          <AField label="Letzter Login" value={localDate(record.last_login_at)} readOnly />
          <AField label="Erstellt" value={localDate(record.created_at)} readOnly />
          <AField label="Zuletzt geändert" value={localDate(record.updated_at)} readOnly />
          {isAdmin && (
            <div className="sm:col-span-2">
              <AField label="Firebase UID" value={record.firebase_uid} readOnly />
            </div>
          )}
        </div>
      </Card>
    </div>
  );
}

/** Anmeldeweg aus dem Firebase-ID-Token, in Klartext. */
function signInLabel(provider: string | null | undefined): string {
  const map: Record<string, string> = {
    'google.com': 'Google SSO',
    custom: 'Passkey',          // Passkey-Login stellt ein Firebase Custom Token aus
    emailLink: 'Anmeldelink',
    password: 'Passwort',
  };
  return provider ? (map[provider] ?? provider) : '—';
}

function passkeyLabel(count: number | null | undefined): string {
  const n = count ?? 0;
  return n === 0 ? 'Keiner eingerichtet' : `${n} Gerät${n === 1 ? '' : 'e'}`;
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
    <Card icon={ShoppingBag} title="Bestellungen">
      {orders === null
        ? <div style={{ fontSize: 13, color: 'var(--fg-4)' }}>Lädt…</div>
        : <OrdersList orders={orders} />}
    </Card>
  );
}

// ─── UserDetail ──────────────────────────────────────────────────────────────

export function UserDetail({ record, onSave, isAdmin, onBack }: {
  record: UserProfile;
  onSave: (u: UserProfile) => void;
  isAdmin: boolean;
  onBack: () => void;
}) {
  const [tab, setTab] = useState<UserTab>('profil');

  const rc       = ROLE_CFG[record.role] ?? ROLE_CFG.customer;
  const name     = userDisplayName(record);
  const hasName  = !!name && name !== record.email;
  const initials = userInitials(name, record.email);

  return (
    <div className="flex flex-col h-full">
      {/* Kopf – die EINE Anatomie aller Datensatz-Fenster (`DetailHeader`, Notiz #242).
          Das runde Foto als `avatar`; die Objektnummer trägt der Kopf (darum steht sie –
          anders als im Profil – nicht noch einmal als Kachel im Formular). */}
      <DetailHeader
        eyebrow="Benutzer" title={hasName ? name : null} placeholder="Kein Name"
        objectId={record.object_id} onBack={onBack}
        status={{ label: rc.label, color: rc.color, bg: rc.bg }}
        avatar={
          <div style={{
            width: 56, height: 56, borderRadius: '50%', flex: 'none',
            background: record.photo_url ? 'transparent' : rc.bg, color: rc.color, overflow: 'hidden',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            font: '700 19px var(--font-body)',
          }}>
            {record.photo_url
              // eslint-disable-next-line @next/next/no-img-element
              ? <img src={record.photo_url} alt="" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
              : initials}
          </div>
        }
      >
        <DetailTabs<UserTab> style={{ marginTop: 16 }} active={tab} onChange={setTab} tabs={[
          { key: 'profil', label: 'Profil', icon: User },
          { key: 'orders', label: 'Bestellungen', icon: ShoppingBag },
          { key: 'verwendung', label: 'Verwendung', icon: Link2 },
          { key: 'docs', label: 'Dokumente', icon: FolderOpen },
        ]} />
      </DetailHeader>

      {/* Content */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '16px 20px 40px', background: 'var(--bg-2)' }}>
        {tab === 'profil' && <ProfileForm record={record} isAdmin={isAdmin} onSaved={onSave} />}
        {tab === 'orders' && <OrdersSec objectId={record.object_id} />}
        {tab === 'verwendung' && <ObjectReferences objectId={record.object_id} emptyHint="Diese Person hält aktuell keine Instanzen." />}
        {tab === 'docs' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 22 }}>
            <div>
              <div style={{ font: '700 13px var(--font-body)', color: 'var(--fg-1)', marginBottom: 2 }}>Freigaben & Anerkennungen</div>
              <div style={{ fontSize: 12, color: 'var(--fg-4)', marginBottom: 10 }}>
                Dokumente, die diese Person unterschreibt/bestätigt (als Partei) oder anerkennt (als Publikum).
                Die Ansicht «Meine Dokumente» im Konto der Person spiegelt genau diese Daten.
              </div>
              <UserDocumentsOverview objectId={record.object_id} />
            </div>
            <div>
              <div style={{ font: '700 13px var(--font-body)', color: 'var(--fg-1)', marginBottom: 10 }}>Abgelegte Dokumente</div>
              <ObjectDocuments objectId={record.object_id} contextLabel="dieser Person" />
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
