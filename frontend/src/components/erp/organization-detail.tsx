'use client';

import { useEffect, useState } from 'react';
import { Building2, ArrowLeft, FileText, Phone, Landmark, ReceiptText, Globe2, Key } from 'lucide-react';
import { api } from '@/lib/api';
import type { CompanySettings } from '@/types';
import { Field, Sec, fmtObjId } from '@/components/erp/user-detail';

/**
 * Detailansicht des **Unternehmens** als vollwertiger ERP-Datensatz – im **gleichen
 * Layout wie die Benutzer-Detailseite** (Kopf mit Objektnummer, Sektions-Karten mit
 * Feld-Raster, Speicherleiste). Die Firmen-/ERP-Konfiguration wird hier – statt in den
 * Profileinstellungen – gepflegt (admin-geschützt).
 */
export function OrganizationDetail({ record, onSaved, onBack }: {
  record: CompanySettings;
  onSaved: (s: CompanySettings) => void;
  onBack: () => void;
}) {
  const [settings, setSettings] = useState<CompanySettings | null>(null);
  const [form, setForm] = useState<Partial<CompanySettings>>({});
  const [dirty, setDirty] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setForm({}); setDirty(false); setError(null);
    api.getSettings().then(setSettings).catch(() => setSettings(record));
  }, [record]);

  const base = settings ?? record;
  function v(key: keyof CompanySettings): string | boolean | null | undefined {
    if (key in form) return form[key] as string | boolean | null | undefined;
    return base[key] as string | boolean | null | undefined;
  }
  function set(key: keyof CompanySettings) {
    return (val: string | boolean) => {
      setForm((prev) => ({ ...prev, [key]: val === '' ? null : val } as Partial<CompanySettings>));
      setDirty(true);
    };
  }
  async function save() {
    setSaving(true); setError(null);
    try {
      const updated = await api.updateSettings(form);
      setSettings(updated);
      onSaved(updated);
      setForm({}); setDirty(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Fehler beim Speichern');
    } finally { setSaving(false); }
  }

  return (
    <div className="flex flex-col h-full">
      {/* Header – analog zur Benutzer-Detailseite */}
      <div style={{ padding: '12px 20px', borderBottom: '1px solid #E2E8F0', background: '#fff', flexShrink: 0 }}>
        <button onClick={onBack} className="flex items-center gap-1 text-sm text-blue-600 mb-2 md:hidden">
          <ArrowLeft size={14} /> Zurück
        </button>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <div style={{ width: 44, height: 44, borderRadius: '50%', flexShrink: 0, background: '#f0fdfa', color: '#0d9488', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <Building2 size={20} />
          </div>
          <div style={{ minWidth: 0, flex: 1 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
              <span style={{ fontSize: 15, fontWeight: 700, color: '#0F172A' }}>{String(v('company_name') ?? 'Unternehmen')}</span>
              <span style={{ fontSize: 10, fontWeight: 700, padding: '2px 7px', borderRadius: 4, background: '#f0fdfa', color: '#0d9488' }}>Unternehmen</span>
            </div>
            <div style={{ fontSize: 12, color: '#94a3b8', marginTop: 2 }}>{String(v('email') ?? '')}</div>
          </div>
          <div style={{ flexShrink: 0, textAlign: 'right' }}>
            <div style={{ fontSize: 10, color: '#CBD5E1', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' }}>Obj.-Nr.</div>
            <div style={{ fontSize: 12, fontFamily: 'monospace', fontWeight: 700, color: '#475569' }}>{fmtObjId(record.object_id)}</div>
          </div>
        </div>
      </div>

      {/* Content */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '16px 20px', background: '#F8FAFC' }}>
        <Sec title="Allgemeine Angaben" editable icon={Building2}>
          <Field label="Firmenname" val={v('company_name')} onChange={set('company_name')} span2 />
          <Field label="Rechtsform" val={v('legal_form')} onChange={set('legal_form')} />
          <Field label="Land" val={v('country')} onChange={set('country')} />
          <Field label="Strasse" val={v('street')} onChange={set('street')} />
          <Field label="Hausnummer" val={v('street_number')} onChange={set('street_number')} />
          <Field label="PLZ" val={v('zip')} onChange={set('zip')} />
          <Field label="Ort" val={v('city')} onChange={set('city')} />
        </Sec>

        <Sec title="Rechtliche Identifikation" editable icon={FileText}>
          <Field label="UID-Nummer" val={v('uid')} onChange={set('uid')} />
          <Field label="MWST-Nummer" val={v('vat_number')} onChange={set('vat_number')} />
          <Field label="Handelsregister-Nr." val={v('trade_register_number')} onChange={set('trade_register_number')} />
          <Field label="HR-Kanton" val={v('trade_register_canton')} onChange={set('trade_register_canton')} />
          <Field label="Aktienkapital" val={v('share_capital')} onChange={set('share_capital')} span2 />
        </Sec>

        <Sec title="Kontakt & Web" editable icon={Phone}>
          <Field label="E-Mail" val={v('email')} onChange={set('email')} type="email" span2 />
          <Field label="Telefon" val={v('phone')} onChange={set('phone')} />
          <Field label="Website" val={v('website')} onChange={set('website')} />
        </Sec>

        <Sec title="Bankdaten" editable icon={Landmark}>
          <Field label="IBAN" val={v('iban') ?? (base.iban_masked ?? '')} onChange={set('iban')} span2 />
          <Field label="QR-IBAN" val={v('qr_iban') ?? (base.qr_iban_masked ?? '')} onChange={set('qr_iban')} span2 />
          <Field label="Bank" val={v('bank_name')} onChange={set('bank_name')} />
          <Field label="BIC/SWIFT" val={v('bic')} onChange={set('bic')} />
        </Sec>

        <Sec title="MWST & Zahlung" editable icon={ReceiptText}>
          <Field label="MWST-Methode" val={v('vat_method')} onChange={set('vat_method')} type="select" opts={['effektiv', 'saldosteuersatz']} />
          <Field label="MWST-Periode" val={v('vat_period')} onChange={set('vat_period')} type="select" opts={['quartal', 'semester', 'jahr']} />
          <Field label="Zahlungsfrist (Tage)" val={v('default_payment_days')} onChange={set('default_payment_days')} />
          <Field label="Skonto (%)" val={v('default_discount_percent')} onChange={set('default_discount_percent')} />
          <Field label="Skonto-Frist (Tage)" val={v('default_discount_days')} onChange={set('default_discount_days')} />
        </Sec>

        <Sec title="EU-Erweiterungen" editable icon={Globe2}>
          <Field label="OSS aktiv" val={v('oss_active')} onChange={set('oss_active')} type="check" />
          <Field label="VIES-Validierung" val={v('vies_validation')} onChange={set('vies_validation')} type="check" />
          <Field label="OSS-Nummer" val={v('oss_number')} onChange={set('oss_number')} span2 />
        </Sec>

        <Sec title="Integrationen & API-Keys" editable icon={Key}>
          <Field label="Stripe Publishable Key" val={v('stripe_publishable_key')} onChange={set('stripe_publishable_key')} span2 />
          <Field label="Plausible Domain" val={v('plausible_domain')} onChange={set('plausible_domain')} />
          <Field label="hCaptcha Site Key" val={v('hcaptcha_site_key')} onChange={set('hcaptcha_site_key')} />
          <Field label="Google Maps API Key" val={v('google_maps_api_key')} onChange={set('google_maps_api_key')} span2 />
        </Sec>

      </div>

      {/* Speicherleiste – analog zur Benutzer-Detailseite */}
      {(dirty || error) && (
        <div style={{ padding: '10px 20px', background: '#fff', borderTop: '1px solid #E2E8F0', display: 'flex', alignItems: 'center', gap: 10, flexShrink: 0 }}>
          <span style={{ flex: 1, fontSize: 13, color: error ? '#dc2626' : '#64748b', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {error ?? 'Ungespeicherte Änderungen'}
          </span>
          <button onClick={() => { setForm({}); setDirty(false); setError(null); }}
            style={{ padding: '6px 14px', borderRadius: 7, border: '1px solid #E2E8F0', background: '#fff', fontSize: 13, color: '#374151', cursor: 'pointer', flexShrink: 0 }}>
            Verwerfen
          </button>
          <button onClick={save} disabled={saving}
            style={{ padding: '6px 14px', borderRadius: 7, border: 'none', background: saving ? '#93c5fd' : '#2563eb', color: '#fff', fontSize: 13, fontWeight: 600, cursor: saving ? 'wait' : 'pointer', flexShrink: 0 }}>
            {saving ? 'Speichern…' : 'Speichern'}
          </button>
        </div>
      )}
    </div>
  );
}

