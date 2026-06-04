'use client';

import { useState, useEffect, useRef } from 'react';
import { Truck } from 'lucide-react';
import type { UserProfile } from '@/types';
import { Field, SelectField } from '../field';
import { useAutosave } from '../use-autosave';
import { SaveStatusIndicator } from '../save-status';

interface Form {
  ship_b2c_first_name: string;
  ship_b2c_last_name: string;
  ship_b2c_address_line1: string;
  ship_b2c_address_line2: string;
  ship_b2c_city: string;
  ship_b2c_postal_code: string;
  ship_b2c_country: string;
  ship_b2b_company: string;
  ship_b2b_contact: string;
  ship_b2b_address_line1: string;
  ship_b2b_address_line2: string;
  ship_b2b_city: string;
  ship_b2b_postal_code: string;
  ship_b2b_country: string;
}

function buildForm(p: UserProfile): Form {
  return {
    ship_b2c_first_name: p.ship_b2c_first_name ?? '',
    ship_b2c_last_name: p.ship_b2c_last_name ?? '',
    ship_b2c_address_line1: p.ship_b2c_address_line1 ?? '',
    ship_b2c_address_line2: p.ship_b2c_address_line2 ?? '',
    ship_b2c_city: p.ship_b2c_city ?? '',
    ship_b2c_postal_code: p.ship_b2c_postal_code ?? '',
    ship_b2c_country: p.ship_b2c_country ?? 'CH',
    ship_b2b_company: p.ship_b2b_company ?? '',
    ship_b2b_contact: p.ship_b2b_contact ?? '',
    ship_b2b_address_line1: p.ship_b2b_address_line1 ?? '',
    ship_b2b_address_line2: p.ship_b2b_address_line2 ?? '',
    ship_b2b_city: p.ship_b2b_city ?? '',
    ship_b2b_postal_code: p.ship_b2b_postal_code ?? '',
    ship_b2b_country: p.ship_b2b_country ?? 'CH',
  };
}

const COUNTRIES = [
  { value: 'CH', label: 'Schweiz' },
  { value: 'DE', label: 'Deutschland' },
  { value: 'AT', label: 'Österreich' },
  { value: 'FR', label: 'Frankreich' },
  { value: 'IT', label: 'Italien' },
  { value: 'LI', label: 'Liechtenstein' },
];

interface Props {
  profile: UserProfile;
  isBusiness: boolean;
  onSave: (data: Record<string, unknown>) => Promise<void>;
}

export function ShippingSection({ profile, isBusiness, onSave }: Props) {
  const [form, setForm] = useState<Form>(() => buildForm(profile));
  const [resetKey, setResetKey] = useState(0);
  const prevId = useRef<number | undefined>(undefined);

  useEffect(() => {
    if (profile.id !== prevId.current) {
      prevId.current = profile.id;
      setForm(buildForm(profile));
      setResetKey((k) => k + 1);
    }
  }, [profile.id, profile]);

  const { status, errorMsg } = useAutosave(form, (v) => onSave(v as unknown as Record<string, unknown>), 3000, resetKey);

  function set<K extends keyof Form>(key: K, value: Form[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  return (
    <div style={{ background: '#fff', border: '1px solid #E2E8F0', borderRadius: 12, overflow: 'hidden' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '18px 24px', borderBottom: '1px solid #F1F5F9' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <Truck style={{ width: 16, height: 16, color: '#64748b' }} />
          <h2 style={{ fontSize: 15, fontWeight: 600, color: '#0F172A', margin: 0 }}>Lieferadressen</h2>
        </div>
        <SaveStatusIndicator status={status} errorMsg={errorMsg} />
      </div>

      <div style={{ padding: 24, display: 'flex', flexDirection: 'column', gap: 24 }}>
        {!isBusiness && (
          <>
            <p style={{ fontSize: 13, fontWeight: 600, color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.05em', margin: 0 }}>
              Lieferadresse (Privat)
            </p>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
              <Field label="Vorname" value={form.ship_b2c_first_name} onChange={(v) => set('ship_b2c_first_name', v)} />
              <Field label="Nachname" value={form.ship_b2c_last_name} onChange={(v) => set('ship_b2c_last_name', v)} />
              <div style={{ gridColumn: '1 / -1' }}>
                <Field label="Strasse und Hausnummer" value={form.ship_b2c_address_line1} onChange={(v) => set('ship_b2c_address_line1', v)} />
              </div>
              <div style={{ gridColumn: '1 / -1' }}>
                <Field label="Adresszusatz" value={form.ship_b2c_address_line2} onChange={(v) => set('ship_b2c_address_line2', v)} placeholder="c/o, Postfach…" />
              </div>
              <Field label="PLZ" value={form.ship_b2c_postal_code} onChange={(v) => set('ship_b2c_postal_code', v)} />
              <Field label="Ort" value={form.ship_b2c_city} onChange={(v) => set('ship_b2c_city', v)} />
              <SelectField label="Land" value={form.ship_b2c_country} onChange={(v) => set('ship_b2c_country', v)} options={COUNTRIES} />
            </div>
          </>
        )}

        {isBusiness && (
          <>
            <p style={{ fontSize: 13, fontWeight: 600, color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.05em', margin: 0 }}>
              Lieferadresse (Firma)
            </p>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
              <Field label="Firmenname" value={form.ship_b2b_company} onChange={(v) => set('ship_b2b_company', v)} />
              <Field label="Ansprechperson" value={form.ship_b2b_contact} onChange={(v) => set('ship_b2b_contact', v)} />
              <div style={{ gridColumn: '1 / -1' }}>
                <Field label="Strasse und Hausnummer" value={form.ship_b2b_address_line1} onChange={(v) => set('ship_b2b_address_line1', v)} />
              </div>
              <div style={{ gridColumn: '1 / -1' }}>
                <Field label="Adresszusatz" value={form.ship_b2b_address_line2} onChange={(v) => set('ship_b2b_address_line2', v)} placeholder="c/o, Postfach…" />
              </div>
              <Field label="PLZ" value={form.ship_b2b_postal_code} onChange={(v) => set('ship_b2b_postal_code', v)} />
              <Field label="Ort" value={form.ship_b2b_city} onChange={(v) => set('ship_b2b_city', v)} />
              <SelectField label="Land" value={form.ship_b2b_country} onChange={(v) => set('ship_b2b_country', v)} options={COUNTRIES} />
            </div>
          </>
        )}
      </div>
    </div>
  );
}
