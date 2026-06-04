'use client';

import { useState, useEffect, useRef } from 'react';
import { MapPin } from 'lucide-react';
import type { UserProfile } from '@/types';
import { Field, SelectField } from '../field';
import { useAutosave } from '../use-autosave';
import { SaveStatusIndicator } from '../save-status';

interface Form {
  phone: string;
  phone_mobile: string;
  address_line1: string;
  address_line2: string;
  postal_code: string;
  city: string;
  state_canton: string;
  country: string;
}

function buildForm(p: UserProfile): Form {
  return {
    phone: p.phone ?? '',
    phone_mobile: p.phone_mobile ?? '',
    address_line1: p.address_line1 ?? '',
    address_line2: p.address_line2 ?? '',
    postal_code: p.postal_code ?? '',
    city: p.city ?? '',
    state_canton: p.state_canton ?? '',
    country: p.country ?? 'CH',
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
  onSave: (data: Record<string, unknown>) => Promise<void>;
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

  const { status, errorMsg } = useAutosave(form, (v) => onSave(v as unknown as Record<string, unknown>), 3000, resetKey);

  function set<K extends keyof Form>(key: K, value: Form[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  return (
    <div style={{ background: '#fff', border: '1px solid #E2E8F0', borderRadius: 12, overflow: 'hidden' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '18px 24px', borderBottom: '1px solid #F1F5F9' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <MapPin style={{ width: 16, height: 16, color: '#64748b' }} />
          <h2 style={{ fontSize: 15, fontWeight: 600, color: '#0F172A', margin: 0 }}>Kontakt & Adresse</h2>
        </div>
        <SaveStatusIndicator status={status} errorMsg={errorMsg} />
      </div>

      <div style={{ padding: 24, display: 'flex', flexDirection: 'column', gap: 20 }}>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
          <Field label="Telefon" value={form.phone} onChange={(v) => set('phone', v)} placeholder="+41 44 000 00 00" type="tel" />
          <Field label="Mobiltelefon" value={form.phone_mobile} onChange={(v) => set('phone_mobile', v)} placeholder="+41 79 000 00 00" type="tel" />
        </div>

        <div style={{ height: 1, background: '#F1F5F9' }} />

        <div style={{ display: 'grid', gridTemplateColumns: '1fr', gap: 16 }}>
          <Field label="Strasse und Hausnummer" value={form.address_line1} onChange={(v) => set('address_line1', v)} placeholder="Musterstrasse 12" />
          <Field label="Adresszusatz" value={form.address_line2} onChange={(v) => set('address_line2', v)} placeholder="c/o, Postfach…" />
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: '140px 1fr', gap: 16 }}>
          <Field label="PLZ" value={form.postal_code} onChange={(v) => set('postal_code', v)} placeholder="8000" />
          <Field label="Ort" value={form.city} onChange={(v) => set('city', v)} placeholder="Zürich" />
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
          <Field label="Kanton / Region" value={form.state_canton} onChange={(v) => set('state_canton', v)} placeholder="ZH" />
          <SelectField label="Land" value={form.country} onChange={(v) => set('country', v)} options={COUNTRIES} />
        </div>
      </div>
    </div>
  );
}
