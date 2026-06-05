'use client';

import { useState, useEffect } from 'react';
import {
  Building2, FileText, Phone, Landmark, ReceiptText, Globe2,
  Key, CheckCircle2, AlertCircle, Loader2, Lock, Package,
} from 'lucide-react';
import { api } from '@/lib/api';
import type { CompanySettings, ItemName, ItemSurface, ItemCategory } from '@/types';

type SectionKey = 'general' | 'legal' | 'contact' | 'banking' | 'vat' | 'eu' | 'integrations';

type ListEntry = { id: number; label: string; is_active: boolean };

const EMPTY_SETTINGS: CompanySettings = {
  company_name: '',
  legal_form: null,
  street: '',
  street_number: null,
  zip: '',
  city: '',
  country: 'Schweiz',
  uid: null,
  vat_number: null,
  trade_register_number: null,
  trade_register_canton: null,
  share_capital: null,
  email: '',
  phone: null,
  website: '',
  logo_url: null,
  iban: null,
  iban_masked: null,
  qr_iban: null,
  qr_iban_masked: null,
  bank_name: null,
  bic: null,
  vat_method: 'effektiv',
  vat_period: 'quartal',
  default_payment_days: 30,
  default_discount_percent: null,
  default_discount_days: null,
  oss_active: false,
  oss_number: null,
  vies_validation: false,
  stripe_publishable_key: null,
  plausible_domain: null,
  hcaptcha_site_key: null,
};

export default function EinstellungenPage() {
  const [settings, setSettings] = useState<CompanySettings | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState<SectionKey | null>(null);
  const [saved, setSaved] = useState<SectionKey | null>(null);
  const [error, setError] = useState('');

  const [itemNames, setItemNames] = useState<ItemName[]>([]);
  const [itemSurfaces, setItemSurfaces] = useState<ItemSurface[]>([]);
  const [itemCategories, setItemCategories] = useState<ItemCategory[]>([]);
  const [configLoading, setConfigLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const data = await api.getSettings();
        setSettings(data);
      } catch {
        setSettings(EMPTY_SETTINGS);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  useEffect(() => {
    async function loadConfig() {
      try {
        const [names, surfaces, cats] = await Promise.all([
          api.getItemNames(),
          api.getItemSurfaces(),
          api.getItemCategories(),
        ]);
        setItemNames(names);
        setItemSurfaces(surfaces);
        setItemCategories(cats);
      } catch {
        // silently ignore if API not yet available
      } finally {
        setConfigLoading(false);
      }
    }
    loadConfig();
  }, []);

  async function addItemName(label: string) {
    const item = await api.createItemName(label);
    setItemNames((prev) => [...prev, item]);
  }
  async function addItemSurface(label: string) {
    const item = await api.createItemSurface(label);
    setItemSurfaces((prev) => [...prev, item]);
  }
  async function addItemCategory(label: string) {
    const item = await api.createItemCategory(label);
    setItemCategories((prev) => [...prev, item]);
  }

  async function saveSection(section: SectionKey, data: Partial<CompanySettings>) {
    setSaving(section);
    setError('');
    try {
      const updated = await api.updateSettings(data);
      setSettings(updated);
      setSaved(section);
      setTimeout(() => setSaved(null), 3000);
    } catch {
      setError('Fehler beim Speichern. Bitte versuchen Sie es erneut.');
    } finally {
      setSaving(null);
    }
  }

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center">
        <Loader2 className="h-6 w-6 animate-spin text-blue-600" />
      </div>
    );
  }

  const s = settings ?? EMPTY_SETTINGS;

  return (
    <div className="p-6 max-w-3xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Firmeneinstellungen</h1>
        <p className="mt-1 text-sm text-slate-500">
          Firmen- und Rechtsdaten werden auf Rechnungen, im Impressum und in den AGB verwendet.
        </p>
      </div>

      {error && (
        <div className="flex items-center gap-3 rounded-lg border border-red-200 bg-red-50 px-4 py-3">
          <AlertCircle className="h-4 w-4 text-red-500" />
          <p className="text-sm text-red-700">{error}</p>
        </div>
      )}

      {/* Section 1: General */}
      <SettingsCard
        icon={<Building2 className="h-5 w-5" />}
        title="Allgemeine Angaben"
        saved={saved === 'general'}
        saving={saving === 'general'}
        onSave={(d) => saveSection('general', {
          company_name: d.company_name,
          legal_form: d.legal_form || null,
          street: d.street,
          street_number: d.street_number || null,
          zip: d.zip,
          city: d.city,
          country: d.country,
        })}
      >
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Firmenname" name="company_name" defaultValue={s.company_name} required />
          <Field label="Rechtsform" name="legal_form" defaultValue={s.legal_form ?? ''} placeholder="AG, GmbH, …" />
          <Field label="Strasse" name="street" defaultValue={s.street} required />
          <Field label="Hausnummer" name="street_number" defaultValue={s.street_number ?? ''} />
          <Field label="PLZ" name="zip" defaultValue={s.zip} required />
          <Field label="Ort" name="city" defaultValue={s.city} required />
          <Field label="Land" name="country" defaultValue={s.country} required className="sm:col-span-2" />
        </div>
      </SettingsCard>

      {/* Section 2: Legal */}
      <SettingsCard
        icon={<FileText className="h-5 w-5" />}
        title="Rechtliche Identifikation"
        saved={saved === 'legal'}
        saving={saving === 'legal'}
        onSave={(d) => saveSection('legal', {
          uid: d.uid || null,
          vat_number: d.vat_number || null,
          trade_register_number: d.trade_register_number || null,
          trade_register_canton: d.trade_register_canton || null,
          share_capital: d.share_capital || null,
        })}
      >
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="UID-Nummer" name="uid" defaultValue={s.uid ?? ''} placeholder="CHE-XXX.XXX.XXX" hint="Format: CHE-123.456.789" />
          <Field label="MWST-Nummer" name="vat_number" defaultValue={s.vat_number ?? ''} placeholder="CHE-XXX.XXX.XXX MWST" />
          <Field label="Handelsregister-Nr." name="trade_register_number" defaultValue={s.trade_register_number ?? ''} placeholder="CH-020.3.022.XXX-X" />
          <Field label="HR-Kanton" name="trade_register_canton" defaultValue={s.trade_register_canton ?? ''} placeholder="Zürich" />
          <Field label="Aktienkapital" name="share_capital" defaultValue={s.share_capital ?? ''} hint="z.B. CHF 100'000 voll liberiert" className="sm:col-span-2" />
        </div>
      </SettingsCard>

      {/* Section 3: Contact */}
      <SettingsCard
        icon={<Phone className="h-5 w-5" />}
        title="Kontakt & Web"
        saved={saved === 'contact'}
        saving={saving === 'contact'}
        onSave={(d) => saveSection('contact', {
          email: d.email,
          phone: d.phone || null,
          website: d.website,
        })}
      >
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="E-Mail" name="email" type="email" defaultValue={s.email} required className="sm:col-span-2" />
          <Field label="Telefon" name="phone" type="tel" defaultValue={s.phone ?? ''} placeholder="+41 44 123 45 67" />
          <Field label="Website" name="website" type="url" defaultValue={s.website} placeholder="https://www.inexxio.com" required />
        </div>
      </SettingsCard>

      {/* Section 4: Banking */}
      <SettingsCard
        icon={<Landmark className="h-5 w-5" />}
        title="Bankdaten"
        saved={saved === 'banking'}
        saving={saving === 'banking'}
        onSave={(d) => saveSection('banking', {
          iban: d.iban || null,
          qr_iban: d.qr_iban || null,
          bank_name: d.bank_name || null,
          bic: d.bic || null,
        })}
      >
        <div className="mb-4 flex items-center gap-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2">
          <Lock className="h-4 w-4 text-amber-600 shrink-0" />
          <p className="text-xs text-amber-800">
            Bankdaten werden verschlüsselt gespeichert. Nur Administratoren sehen den vollständigen Wert.
          </p>
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="IBAN" name="iban" defaultValue={s.iban ?? s.iban_masked ?? ''} placeholder="CH93 0076 2011 6238 5295 7" className="sm:col-span-2" />
          <Field label="QR-IBAN" name="qr_iban" defaultValue={s.qr_iban ?? s.qr_iban_masked ?? ''} placeholder="CH21 3080 8001 2345 6789 7" className="sm:col-span-2" />
          <Field label="Bank" name="bank_name" defaultValue={s.bank_name ?? ''} placeholder="UBS Switzerland AG" />
          <Field label="BIC/SWIFT" name="bic" defaultValue={s.bic ?? ''} placeholder="UBSWCHZH80A" />
        </div>
      </SettingsCard>

      {/* Section 5: VAT */}
      <SettingsCard
        icon={<ReceiptText className="h-5 w-5" />}
        title="MWST & Zahlungskonditionen"
        saved={saved === 'vat'}
        saving={saving === 'vat'}
        onSave={(d) => saveSection('vat', {
          vat_method: (d.vat_method as 'effektiv' | 'saldosteuersatz') || undefined,
          vat_period: (d.vat_period as 'quartal' | 'semester' | 'jahr') || undefined,
          default_payment_days: d.default_payment_days ? Number(d.default_payment_days) : 30,
          default_discount_percent: d.default_discount_percent || null,
          default_discount_days: d.default_discount_days ? Number(d.default_discount_days) : null,
        })}
      >
        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1.5">MWST-Methode</label>
            <select name="vat_method" defaultValue={s.vat_method ?? 'effektiv'} className="form-input">
              <option value="effektiv">Effektive Methode</option>
              <option value="saldosteuersatz">Saldosteuersatz</option>
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1.5">MWST-Periode</label>
            <select name="vat_period" defaultValue={s.vat_period ?? 'quartal'} className="form-input">
              <option value="quartal">Quartal</option>
              <option value="semester">Semester</option>
              <option value="jahr">Jahr</option>
            </select>
          </div>
          <Field label="Zahlungsfrist (Tage)" name="default_payment_days" type="number" defaultValue={String(s.default_payment_days)} required />
          <Field label="Skonto (%)" name="default_discount_percent" type="number" defaultValue={s.default_discount_percent ?? ''} hint="z.B. 2 für 2%" />
          <Field label="Skonto-Frist (Tage)" name="default_discount_days" type="number" defaultValue={String(s.default_discount_days ?? '')} />
        </div>
      </SettingsCard>

      {/* Section 6: EU */}
      <SettingsCard
        icon={<Globe2 className="h-5 w-5" />}
        title="EU-Erweiterungen"
        saved={saved === 'eu'}
        saving={saving === 'eu'}
        onSave={(d) => saveSection('eu', {
          oss_active: d.oss_active === 'true',
          oss_number: d.oss_number || null,
          vies_validation: d.vies_validation === 'true',
        })}
      >
        <div className="space-y-5">
          <ToggleField
            name="oss_active"
            label="OSS-Registrierung aktiv"
            defaultValue={s.oss_active}
            description="Aktiviert EU B2C MWST-Berechnung. Pflicht ab CHF 100'000 EU B2C-Umsatz pro Jahr."
          />
          {s.oss_active && (
            <Field label="OSS-Registrierungsnummer" name="oss_number" defaultValue={s.oss_number ?? ''} placeholder="EU372012345" />
          )}
          <ToggleField
            name="vies_validation"
            label="VIES UID-Validierung"
            defaultValue={s.vies_validation}
            description="Automatische Validierung von EU-Mehrwertsteuernummern bei neuen Firmenkunden."
          />
        </div>
      </SettingsCard>

      {/* Section 7: Integrations */}
      <SettingsCard
        icon={<Key className="h-5 w-5" />}
        title="Integrationen & API-Keys"
        saved={saved === 'integrations'}
        saving={saving === 'integrations'}
        onSave={(d) => saveSection('integrations', {
          stripe_publishable_key: d.stripe_publishable_key || null,
          plausible_domain: d.plausible_domain || null,
          hcaptcha_site_key: d.hcaptcha_site_key || null,
        })}
      >
        <div className="mb-4 flex items-start gap-2 rounded-lg border border-blue-200 bg-blue-50 px-3 py-2">
          <Lock className="mt-0.5 h-4 w-4 text-blue-600 shrink-0" />
          <p className="text-xs text-blue-800">
            Secret Keys werden im Google Secret Manager verwaltet und sind hier nicht sichtbar.
          </p>
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Stripe Publishable Key" name="stripe_publishable_key" defaultValue={s.stripe_publishable_key ?? ''} placeholder="pk_live_…" hint="Öffentlicher Key" />
          <Field label="Plausible Domain" name="plausible_domain" defaultValue={s.plausible_domain ?? ''} placeholder="inexxio.com" />
          <Field label="hCaptcha Site Key" name="hcaptcha_site_key" defaultValue={s.hcaptcha_site_key ?? ''} placeholder="10000000-ffff-ffff-ffff-000000000001" hint="Für Kontaktformular" className="sm:col-span-2" />
        </div>
      </SettingsCard>

      {/* Section 8: ERP Konfiguration */}
      <div className="card p-6">
        <div className="mb-5 flex items-center gap-3">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-purple-50 text-purple-600">
            <Package className="h-5 w-5" />
          </div>
          <div>
            <h2 className="text-base font-semibold text-slate-900">ERP Artikelkonfiguration</h2>
            <p className="text-xs text-slate-500 mt-0.5">
              Vordefinierte Auswahllisten für Artikel im ERP-System
            </p>
          </div>
        </div>
        <div className="divide-y divide-slate-100">
          <ListManager
            title="Artikelnamen"
            description="Namen, die beim Erstellen eines Artikels ausgewählt werden können"
            items={itemNames}
            loading={configLoading}
            onAdd={addItemName}
          />
          <ListManager
            title="Oberflächen"
            description="Oberflächenbehandlungen / Beschichtungen"
            items={itemSurfaces}
            loading={configLoading}
            onAdd={addItemSurface}
          />
          <ListManager
            title="Produktkategorien"
            description="Kategorien für Verkaufsartikel im Shop"
            items={itemCategories}
            loading={configLoading}
            onAdd={addItemCategory}
          />
        </div>
      </div>
    </div>
  );
}

// ─── Sub-components ───────────────────────────────────────────────────────────

function SettingsCard({
  icon,
  title,
  children,
  onSave,
  saving,
  saved,
}: {
  icon: React.ReactNode;
  title: string;
  children: React.ReactNode;
  onSave: (data: Record<string, string>) => void;
  saving: boolean;
  saved: boolean;
}) {
  function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const formData = new FormData(e.currentTarget);
    const data: Record<string, string> = {};
    formData.forEach((value, key) => { data[key] = value as string; });
    onSave(data);
  }

  return (
    <form onSubmit={handleSubmit} className="card p-6">
      <div className="mb-5 flex items-center gap-3">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-blue-50 text-blue-600">
          {icon}
        </div>
        <h2 className="text-base font-semibold text-slate-900">{title}</h2>
      </div>

      {children}

      <div className="mt-5 flex items-center justify-between border-t border-slate-100 pt-4">
        <div className="flex items-center gap-2">
          {saved && (
            <span className="flex items-center gap-1.5 text-sm text-green-600">
              <CheckCircle2 className="h-4 w-4" />
              Gespeichert
            </span>
          )}
        </div>
        <button type="submit" disabled={saving} className="btn-primary disabled:opacity-50">
          {saving ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              Speichert…
            </>
          ) : (
            'Speichern'
          )}
        </button>
      </div>
    </form>
  );
}

function Field({
  label,
  name,
  type = 'text',
  defaultValue,
  required,
  placeholder,
  hint,
  className = '',
}: {
  label: string;
  name: string;
  type?: string;
  defaultValue?: string | number | null;
  required?: boolean;
  placeholder?: string;
  hint?: string;
  className?: string;
}) {
  return (
    <div className={className}>
      <label htmlFor={name} className="block text-sm font-medium text-slate-700 mb-1.5">
        {label}{required && <span className="ml-1 text-red-500">*</span>}
      </label>
      <input
        id={name}
        name={name}
        type={type}
        defaultValue={defaultValue ?? ''}
        required={required}
        placeholder={placeholder}
        className="form-input"
      />
      {hint && <p className="mt-1 text-xs text-slate-500">{hint}</p>}
    </div>
  );
}

function ToggleField({
  name,
  label,
  defaultValue,
  description,
}: {
  name: string;
  label: string;
  defaultValue: boolean;
  description: string;
}) {
  const [enabled, setEnabled] = useState(defaultValue);

  return (
    <div className="flex items-start justify-between gap-4">
      <div>
        <p className="text-sm font-medium text-slate-900">{label}</p>
        <p className="mt-0.5 text-xs text-slate-500">{description}</p>
      </div>
      <input type="hidden" name={name} value={String(enabled)} />
      <button
        type="button"
        onClick={() => setEnabled(!enabled)}
        className={`relative inline-flex h-6 w-11 shrink-0 items-center rounded-full transition-colors focus:outline-none ${
          enabled ? 'bg-blue-600' : 'bg-slate-200'
        }`}
      >
        <span
          className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
            enabled ? 'translate-x-6' : 'translate-x-1'
          }`}
        />
      </button>
    </div>
  );
}

function ListManager({
  title,
  description,
  items,
  loading,
  onAdd,
}: {
  title: string;
  description: string;
  items: ListEntry[];
  loading: boolean;
  onAdd: (label: string) => Promise<void>;
}) {
  const [newLabel, setNewLabel] = useState('');
  const [adding, setAdding] = useState(false);
  const [addError, setAddError] = useState('');

  const handleAdd = async () => {
    const label = newLabel.trim();
    if (!label) return;
    const duplicate = items.some((i) => i.label.toLowerCase() === label.toLowerCase());
    if (duplicate) { setAddError('Dieser Eintrag existiert bereits.'); return; }
    setAdding(true);
    setAddError('');
    try {
      await onAdd(label);
      setNewLabel('');
    } catch {
      setAddError('Fehler beim Hinzufügen.');
    } finally {
      setAdding(false);
    }
  };

  const activeItems = items.filter((i) => i.is_active);

  return (
    <div className="py-5 first:pt-0">
      <div className="mb-3">
        <h3 className="text-sm font-semibold text-slate-800">{title}</h3>
        <p className="text-xs text-slate-500 mt-0.5">{description}</p>
      </div>

      {loading ? (
        <div className="flex items-center gap-1.5 text-xs text-slate-400 mb-3">
          <Loader2 className="h-3.5 w-3.5 animate-spin" />Lädt…
        </div>
      ) : (
        <div className="flex flex-wrap gap-1.5 mb-3 min-h-[1.75rem]">
          {activeItems.length === 0 ? (
            <span className="text-xs text-slate-400 italic">Noch keine Einträge vorhanden</span>
          ) : (
            activeItems.map((item) => (
              <span
                key={item.id}
                className="px-2.5 py-1 bg-slate-100 text-slate-700 text-xs rounded-full border border-slate-200"
              >
                {item.label}
              </span>
            ))
          )}
        </div>
      )}

      <div className="flex gap-2">
        <input
          type="text"
          value={newLabel}
          onChange={(e) => { setNewLabel(e.target.value); setAddError(''); }}
          onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); handleAdd(); } }}
          placeholder={`Neuer ${title.replace(/en$/, '').replace(/en$/, '')}…`}
          className="form-input flex-1 text-sm"
        />
        <button
          type="button"
          onClick={handleAdd}
          disabled={adding || !newLabel.trim()}
          className="btn-primary text-sm px-4 disabled:opacity-50 shrink-0"
        >
          {adding ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Hinzufügen'}
        </button>
      </div>
      {addError && <p className="mt-1 text-xs text-red-500">{addError}</p>}
    </div>
  );
}
