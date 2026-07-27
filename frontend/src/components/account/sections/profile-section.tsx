'use client';

/**
 * **Mein Profil – EINE Sektion, drei Container.**
 *
 * Vorher lagen dieselben Daten in vier Karten mit vier Auto-Saves (Profil, Adresse,
 * Rechnungsadresse, Datenschutz) – und die Rechnungsadresse spiegelte den Profil-Stand
 * aus dem `profile`-Prop, hinkte also jeder noch nicht gespeicherten Änderung hinterher.
 *
 * Jetzt: ein Formular, ein Auto-Save, eine Rückmeldung. Gruppiert nach dem, was fachlich
 * zusammengehört:
 *   1. **Persönliche Angaben** – wer bin ich (inkl. Telefon; + Firmendaten/Anstellung)
 *   2. **Adressen**          – wohin (Liefer- + Rechnungsadresse, «gleich wie»-Schalter)
 *   3. **Kommunikation**     – Newsletter + Nachweis der akzeptierten Rechtstexte
 */

import { useState, useEffect, useRef } from 'react';
import { User, Briefcase, Building2, MapPin, Bell, Check } from 'lucide-react';
import Link from 'next/link';
import type { UserProfile } from '@/types';
import { Field, ToggleField } from '../field';
import { useAutosave } from '../use-autosave';
import { SaveStatusIndicator } from '../save-status';
import { AddressField, type Address } from '@/components/erp/address-field';
import { useMapsApiKey } from '@/components/erp/use-maps-key';

interface Form {
  // Person
  first_name: string;
  last_name: string;
  date_of_birth: string;
  phone: string;
  // Firma (nur Lieferant)
  company_name: string;
  uid_number: string;
  company_billing_email: string;
  // Adresse
  address_line1: string;
  address_line2: string;
  postal_code: string;
  city: string;
  state_region: string;
  country: string;
  // Rechnungsadresse
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
  // Kommunikation
  newsletter_opt_in: boolean;
}

function buildForm(p: UserProfile): Form {
  return {
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
    newsletter_opt_in: p.newsletter_opt_in ?? false,
  };
}

const COUNTRIES: [string, string][] = [
  ['CH', 'Schweiz'], ['DE', 'Deutschland'], ['AT', 'Österreich'],
  ['FR', 'Frankreich'], ['IT', 'Italien'], ['LI', 'Liechtenstein'],
];

interface Props {
  profile: UserProfile;
  isEmployee: boolean;
  isSupplier: boolean;
  onSave: (data: Partial<UserProfile>) => Promise<void>;
}

export function ProfileSection({ profile, isEmployee, isSupplier, onSave }: Props) {
  const [form, setForm] = useState<Form>(() => buildForm(profile));
  const [resetKey, setResetKey] = useState(0);
  const prevId = useRef<number | undefined>(undefined);
  const mapsKey = useMapsApiKey();

  useEffect(() => {
    if (profile.id !== prevId.current) {
      prevId.current = profile.id;
      setForm(buildForm(profile));
      setResetKey((k) => k + 1);
    }
  }, [profile.id, profile]);

  const { status, errorMsg, saveNow } = useAutosave(
    form,
    (v) => {
      const data = { ...v } as Partial<UserProfile>;
      if (!isSupplier) {
        delete data.company_name;
        delete data.uid_number;
        delete data.company_billing_email;
      }
      // «Gleich wie Lieferadresse»: die Rechnungsfelder werden aus der Adresse gespiegelt,
      // damit Rechnung/Versand nie auseinanderlaufen (EIN Datensatz, eine Wahrheit).
      if (v.invoice_same_as_shipping) {
        Object.assign(data, {
          invoice_company: isSupplier ? v.company_name : '',
          invoice_first_name: v.first_name,
          invoice_last_name: v.last_name,
          invoice_address_line1: v.address_line1,
          invoice_address_line2: v.address_line2,
          invoice_postal_code: v.postal_code,
          invoice_city: v.city,
          invoice_country: v.country,
        });
      }
      return onSave(data);
    },
    3000,
    resetKey,
  );

  function set<K extends keyof Form>(key: K, value: Form[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  const objectNumber = profile.object_id != null
    ? String(profile.object_id).padStart(9, '0')
    : String(profile.id);

  const address: Address = {
    street: form.address_line1, street2: form.address_line2, zip: form.postal_code,
    city: form.city, region: form.state_region, country: form.country,
  };
  function applyAddress(a: Address) {
    setForm((prev) => ({
      ...prev,
      address_line1: a.street, address_line2: a.street2 ?? '', postal_code: a.zip,
      city: a.city, state_region: a.region ?? '', country: a.country,
    }));
  }

  const invoiceAddress: Address = {
    street: form.invoice_address_line1, street2: form.invoice_address_line2,
    zip: form.invoice_postal_code, city: form.invoice_city, country: form.invoice_country,
  };
  function applyInvoiceAddress(a: Address) {
    setForm((prev) => ({
      ...prev,
      invoice_address_line1: a.street, invoice_address_line2: a.street2 ?? '',
      invoice_postal_code: a.zip, invoice_city: a.city, invoice_country: a.country,
    }));
  }

  const termsDate = profile.terms_accepted_at
    ? new Date(profile.terms_accepted_at).toLocaleDateString('de-CH')
    : null;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {/* ── 1. Persönliche Angaben ─────────────────────────────────────────── */}
      <Card icon={User} title="Persönliche Angaben" right={<SaveStatusIndicator status={status} errorMsg={errorMsg} />}>
        {/* Die Objektnummer ist vergeben und unveränderlich – sie wie ein Formularfeld
            zu zeigen, lud zum Hineinklicken ein. Jetzt steht sie da wie überall sonst
            im System: Versalien-Label + monospaced Nummer. */}
        <div>
          <div style={{ font: '600 11px var(--font-body)', textTransform: 'uppercase', letterSpacing: '.06em', color: 'var(--fg-4)', marginBottom: 4 }}>
            Benutzernummer
          </div>
          <div style={{ fontFamily: 'var(--font-mono)', fontSize: 14, fontVariantNumeric: 'tabular-nums', color: 'var(--fg-2)' }}>
            {objectNumber}
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <Field label="Vorname" value={form.first_name} onChange={(v) => set('first_name', v)} placeholder="Max" required={!form.first_name.trim()} onEnter={saveNow} />
          <Field label="Nachname" value={form.last_name} onChange={(v) => set('last_name', v)} placeholder="Muster" required={!form.last_name.trim()} onEnter={saveNow} />
          <Field label="Telefon" value={form.phone} onChange={(v) => set('phone', v)} placeholder="+41 44 000 00 00" type="tel" required={!form.phone.trim()} onEnter={saveNow} />
          <Field label="Geburtsdatum" value={form.date_of_birth} onChange={(v) => set('date_of_birth', v)} type="date" onEnter={saveNow} />
        </div>

        {isSupplier && (
          <SubBlock icon={Building2} title="Firmendaten">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <Field label="Firmenname" value={form.company_name} onChange={(v) => set('company_name', v)} placeholder="Muster AG" required={!form.company_name.trim()} onEnter={saveNow} />
              <Field label="UID-Nummer" value={form.uid_number} onChange={(v) => set('uid_number', v)} placeholder="CHE-123.456.789" required={!form.uid_number.trim()} onEnter={saveNow} />
            </div>
          </SubBlock>
        )}

        {isEmployee && (
          <SubBlock icon={Briefcase} title="Anstellung · wird vom Administrator gepflegt">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <Field label="Abteilung" value={profile.department ?? ''} readOnly />
              <Field label="Funktion" value={profile.job_title ?? ''} readOnly />
              <Field label="Eintrittsdatum" value={profile.employment_start_date ? new Date(profile.employment_start_date).toLocaleDateString('de-CH') : ''} readOnly />
              <Field label="Pensum" value={profile.weekly_hours ? `${profile.weekly_hours}h / Woche` : ''} readOnly />
            </div>
          </SubBlock>
        )}
      </Card>

      {/* ── 2. Adressen (Lieferung + Rechnung in EINEM Container) ───────────── */}
      <Card icon={MapPin} title="Adressen">
        <AddressField
          value={address} onChange={applyAddress} apiKey={mapsKey}
          countryOptions={COUNTRIES} showStreet2 showRegion label="Lieferadresse" />

        <div style={{ height: 1, background: 'var(--border-1)' }} />

        <ToggleField
          label="Rechnungsadresse = Lieferadresse"
          checked={form.invoice_same_as_shipping}
          onChange={(v) => set('invoice_same_as_shipping', v)}
        />

        {!form.invoice_same_as_shipping && (
          <>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {isSupplier && (
                <div className="sm:col-span-2">
                  <Field label="Firmenname" value={form.invoice_company} onChange={(v) => set('invoice_company', v)} onEnter={saveNow} />
                </div>
              )}
              <Field label="Vorname" value={form.invoice_first_name} onChange={(v) => set('invoice_first_name', v)} required={!form.invoice_first_name.trim()} onEnter={saveNow} />
              <Field label="Nachname" value={form.invoice_last_name} onChange={(v) => set('invoice_last_name', v)} required={!form.invoice_last_name.trim()} onEnter={saveNow} />
            </div>
            <AddressField
              value={invoiceAddress} onChange={applyInvoiceAddress} apiKey={mapsKey}
              countryOptions={COUNTRIES} showStreet2 label="Rechnungsadresse" />
          </>
        )}

        {/* Rechnungs-E-Mail: leer = die Konto-Adresse (als Platzhalter sichtbar). */}
        <Field
          label="Rechnungs-E-Mail" value={form.invoice_email}
          onChange={(v) => set('invoice_email', v)} type="email"
          placeholder={profile.email ?? 'rechnung@firma.ch'}
          onEnter={saveNow}
        />
      </Card>

      {/* ── 3. Kommunikation & Rechtliches ──────────────────────────────────── */}
      <Card icon={Bell} title="Kommunikation">
        <ToggleField
          label="Newsletter"
          description="Produktneuigkeiten und Angebote per E-Mail"
          checked={form.newsletter_opt_in}
          onChange={(v) => set('newsletter_opt_in', v)}
        />
        {/* Kein Schalter, sondern eine Tatsache: die Rechtstexte sind akzeptiert. */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap', fontSize: 13, color: 'var(--fg-3)' }}>
          {termsDate && <Check size={15} style={{ color: 'var(--success)', flexShrink: 0 }} />}
          <span>
            {termsDate
              ? `AGB und Datenschutzerklärung akzeptiert am ${termsDate}${profile.terms_version ? ` · v${profile.terms_version}` : ''}`
              : 'AGB und Datenschutzerklärung noch nicht akzeptiert'}
          </span>
          <Link href="/agb" style={LINK}>AGB</Link>
          <Link href="/datenschutz" style={LINK}>Datenschutz</Link>
        </div>
      </Card>
    </div>
  );
}

// ─── Bausteine ────────────────────────────────────────────────────────────────

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

const LINK: React.CSSProperties = {
  fontSize: 12.5, color: 'var(--accent)', textDecoration: 'none', fontWeight: 600,
};
