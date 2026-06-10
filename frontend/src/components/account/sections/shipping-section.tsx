'use client';

import { useState, useEffect, useRef } from 'react';
import { Truck } from 'lucide-react';
import type { UserProfile } from '@/types';
import { Field, SelectField } from '../field';
import { useAutosave } from '../use-autosave';
import { SaveStatusIndicator } from '../save-status';

interface Form {
  ship_name: string;
  ship_company: string;
  ship_address_line1: string;
  ship_address_line2: string;
  ship_city: string;
  ship_postal_code: string;
  ship_state_region: string;
  ship_country: string;
}

function buildForm(p: UserProfile): Form {
  return {
    ship_name: p.ship_name ?? '',
    ship_company: p.ship_company ?? '',
    ship_address_line1: p.ship_address_line1 ?? '',
    ship_address_line2: p.ship_address_line2 ?? '',
    ship_city: p.ship_city ?? '',
    ship_postal_code: p.ship_postal_code ?? '',
    ship_state_region: p.ship_state_region ?? '',
    ship_country: p.ship_country ?? 'CH',
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
  onSave: (data: Partial<UserProfile>) => Promise<void>;
}

export function ShippingSection({ profile, isBusiness: _isBusiness, onSave }: Props) {
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

  function set<K extends keyof Form>(key: K, value: Form[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  return (
    <div style={{ background: '#fff', border: '1px solid #E2E8F0', borderRadius: 12, overflow: 'hidden' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '18px 24px', borderBottom: '1px solid #F1F5F9' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <Truck style={{ width: 16, height: 16, color: '#64748b' }} />
          <h2 style={{ fontSize: 15, fontWeight: 600, color: '#0F172A', margin: 0 }}>Lieferadresse</h2>
        </div>
        <SaveStatusIndicator status={status} errorMsg={errorMsg} />
      </div>

      <div style={{ padding: 24, display: 'flex', flexDirection: 'column', gap: 16 }}>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <Field label="Name" value={form.ship_name} onChange={(v) => set('ship_name', v)} placeholder="Max Muster" onEnter={saveNow} />
          <Field label="Firma (optional)" value={form.ship_company} onChange={(v) => set('ship_company', v)} placeholder="Muster AG" onEnter={saveNow} />
          <div className="col-span-2">
            <Field label="Strasse und Hausnummer" value={form.ship_address_line1} onChange={(v) => set('ship_address_line1', v)} placeholder="Musterstrasse 12" required={!form.ship_address_line1.trim()} onEnter={saveNow} />
          </div>
          <div className="col-span-2">
            <Field label="Adresszusatz" value={form.ship_address_line2} onChange={(v) => set('ship_address_line2', v)} placeholder="c/o, Postfach…" onEnter={saveNow} />
          </div>
          <Field label="PLZ" value={form.ship_postal_code} onChange={(v) => set('ship_postal_code', v)} placeholder="8000" required={!form.ship_postal_code.trim()} onEnter={saveNow} />
          <Field label="Ort" value={form.ship_city} onChange={(v) => set('ship_city', v)} placeholder="Zürich" required={!form.ship_city.trim()} onEnter={saveNow} />
          <Field label="Kanton / Region" value={form.ship_state_region} onChange={(v) => set('ship_state_region', v)} placeholder="ZH" onEnter={saveNow} />
          <SelectField label="Land" value={form.ship_country} onChange={(v) => set('ship_country', v)} options={COUNTRIES} />
        </div>
      </div>
    </div>
  );
}
