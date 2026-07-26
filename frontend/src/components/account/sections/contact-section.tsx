'use client';

import { useState, useEffect, useRef } from 'react';
import { MapPin } from 'lucide-react';
import type { UserProfile } from '@/types';
import { Field } from '../field';
import { useAutosave } from '../use-autosave';
import { SaveStatusIndicator } from '../save-status';
import { AddressField, type Address } from '@/components/erp/address-field';
import { useMapsApiKey } from '@/components/erp/use-maps-key';

interface Form {
  phone: string;
  address_line1: string;
  address_line2: string;
  postal_code: string;
  city: string;
  state_region: string;
  country: string;
}

function buildForm(p: UserProfile): Form {
  return {
    phone: p.phone ?? '',
    address_line1: p.address_line1 ?? '',
    address_line2: p.address_line2 ?? '',
    postal_code: p.postal_code ?? '',
    city: p.city ?? '',
    state_region: p.state_region ?? '',
    country: p.country ?? 'CH',
  };
}

const COUNTRIES: [string, string][] = [
  ['CH', 'Schweiz'], ['DE', 'Deutschland'], ['AT', 'Österreich'],
  ['FR', 'Frankreich'], ['IT', 'Italien'], ['LI', 'Liechtenstein'],
];

interface Props {
  profile: UserProfile;
  onSave: (data: Partial<UserProfile>) => Promise<void>;
}

export function ContactSection({ profile, onSave }: Props) {
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

  const { status, errorMsg, saveNow } = useAutosave(form, (v) => onSave(v as Partial<UserProfile>), 3000, resetKey);
  const mapsKey = useMapsApiKey();

  function set<K extends keyof Form>(key: K, value: Form[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  // Die Adresse ist EIN Feld (Suche zuerst) – hier nur die Abbildung auf die
  // Profil-Spaltennamen (address_line1/postal_code …).
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

  return (
    <div style={{ background: '#fff', border: '1px solid #E2E8F0', borderRadius: 12, overflow: 'hidden' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '18px 24px', borderBottom: '1px solid #F1F5F9' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <MapPin style={{ width: 16, height: 16, color: '#64748b' }} />
          <h2 style={{ fontSize: 15, fontWeight: 600, color: '#0F172A', margin: 0 }}>Adresse</h2>
        </div>
        <SaveStatusIndicator status={status} errorMsg={errorMsg} />
      </div>

      <div style={{ padding: 24, display: 'flex', flexDirection: 'column', gap: 20 }}>
        <Field label="Telefon" value={form.phone} onChange={(v) => set('phone', v)} placeholder="+41 44 000 00 00" type="tel" required={!form.phone.trim()} onEnter={saveNow} />

        <div style={{ height: 1, background: '#F1F5F9' }} />

        <AddressField
          value={address} onChange={applyAddress} apiKey={mapsKey}
          countryOptions={COUNTRIES} showStreet2 showRegion label="Wohnadresse" />
      </div>
    </div>
  );
}
