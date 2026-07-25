'use client';

import { useState, useRef } from 'react';
import {
  Building2, FileText, Phone, Landmark, ReceiptText, Globe2,
  Key, CheckCircle2, AlertCircle, Loader2, Lock, ShoppingBag, PackageSearch,
} from 'lucide-react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';
import type { CompanySettings } from '@/types';


type SectionKey = 'general' | 'legal' | 'contact' | 'banking' | 'vat' | 'eu' | 'integrations' | 'shop' | 'legal_docs' | 'logistics';

const EMPTY_SETTINGS: CompanySettings = {
  company_name: '', legal_form: null, street: '', street_number: null,
  zip: '', city: '', country: 'Schweiz', uid: null, vat_number: null,
  trade_register_number: null, trade_register_canton: null, share_capital: null,
  email: '', phone: null, website: '', logo_url: null, iban: null, iban_masked: null,
  qr_iban: null, qr_iban_masked: null, bank_name: null, bic: null,
  vat_method: 'effektiv', vat_period: 'quartal', default_payment_days: 30,
  default_discount_percent: null, default_discount_days: null, oss_active: false,
  oss_number: null, vies_validation: false, stripe_publishable_key: null,
  plausible_domain: null, hcaptcha_site_key: null, google_maps_api_key: null,
  default_receiving_location_id: null,
  shop_currencies: ['CHF', 'EUR', 'USD'], shop_country_currency: null,
  shop_default_currency: 'CHF', payments_provider: null, pricing_zone_factors: null,
  legal_documents: null,
};

export function SystemConfigSection({ onSaved }: { onSaved?: (s: CompanySettings) => void } = {}) {
  const queryClient = useQueryClient();
  const [saving, setSaving] = useState<SectionKey | null>(null);
  const [saved, setSaved] = useState<SectionKey | null>(null);
  const [error, setError] = useState('');

  const { data: settings, isLoading } = useQuery({
    queryKey: ['settings'],
    queryFn: () => api.getSettings(),
  });

  const mutation = useMutation({
    mutationFn: (data: Partial<CompanySettings>) => api.updateSettings(data),
    onSuccess: (updated) => {
      queryClient.setQueryData(['settings'], updated);
      onSaved?.(updated);   // Eltern-Feed (ERP «Unternehmen») synchron halten
    },
  });

  async function saveSection(section: SectionKey, data: Partial<CompanySettings>) {
    setSaving(section); setError('');
    try {
      await mutation.mutateAsync(data);
      setSaved(section);
      setTimeout(() => setSaved(null), 3000);
    } catch { setError('Fehler beim Speichern. Bitte versuchen Sie es erneut.'); }
    finally { setSaving(null); }
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-16">
        <Loader2 className="h-6 w-6 animate-spin text-blue-600" />
      </div>
    );
  }

  const s = settings ?? EMPTY_SETTINGS;

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-bold text-slate-900">Systemkonfiguration</h2>
        <p className="mt-1 text-sm text-slate-500">
          Firmen- und Rechtsdaten werden auf Rechnungen, im Impressum und in den AGB verwendet.
        </p>
      </div>

      {error && (
        <div className="flex items-center gap-3 rounded-lg border border-red-200 bg-red-50 px-4 py-3">
          <AlertCircle className="h-4 w-4 text-red-500 shrink-0" />
          <p className="text-sm text-red-700">{error}</p>
        </div>
      )}

      <SettingsCard icon={<Building2 className="h-5 w-5" />} title="Allgemeine Angaben"
        saved={saved === 'general'} saving={saving === 'general'}
        onSave={(d) => saveSection('general', { company_name: d.company_name, legal_form: d.legal_form || null, street: d.street, street_number: d.street_number || null, zip: d.zip, city: d.city, country: d.country })}>
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

      <SettingsCard icon={<FileText className="h-5 w-5" />} title="Rechtliche Identifikation"
        saved={saved === 'legal'} saving={saving === 'legal'}
        onSave={(d) => saveSection('legal', { uid: d.uid || null, vat_number: d.vat_number || null, trade_register_number: d.trade_register_number || null, trade_register_canton: d.trade_register_canton || null, share_capital: d.share_capital || null })}>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="UID-Nummer" name="uid" defaultValue={s.uid ?? ''} placeholder="CHE-XXX.XXX.XXX" hint="Format: CHE-123.456.789" />
          <Field label="MWST-Nummer" name="vat_number" defaultValue={s.vat_number ?? ''} placeholder="CHE-XXX.XXX.XXX MWST" />
          <Field label="Handelsregister-Nr." name="trade_register_number" defaultValue={s.trade_register_number ?? ''} placeholder="CH-020.3.022.XXX-X" />
          <Field label="HR-Kanton" name="trade_register_canton" defaultValue={s.trade_register_canton ?? ''} placeholder="Zürich" />
          <Field label="Aktienkapital" name="share_capital" defaultValue={s.share_capital ?? ''} hint="z.B. CHF 100'000 voll liberiert" className="sm:col-span-2" />
        </div>
      </SettingsCard>

      <SettingsCard icon={<Phone className="h-5 w-5" />} title="Kontakt & Web"
        saved={saved === 'contact'} saving={saving === 'contact'}
        onSave={(d) => saveSection('contact', { email: d.email, phone: d.phone || null, website: d.website })}>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="E-Mail" name="email" type="email" defaultValue={s.email} required className="sm:col-span-2" />
          <Field label="Telefon" name="phone" type="tel" defaultValue={s.phone ?? ''} placeholder="+41 44 123 45 67" />
          <Field label="Website" name="website" type="url" defaultValue={s.website} placeholder="https://www.inexxio.com" required />
        </div>
      </SettingsCard>

      <SettingsCard icon={<Landmark className="h-5 w-5" />} title="Bankdaten"
        saved={saved === 'banking'} saving={saving === 'banking'}
        onSave={(d) => saveSection('banking', { iban: d.iban || null, qr_iban: d.qr_iban || null, bank_name: d.bank_name || null, bic: d.bic || null })}>
        <div className="mb-4 flex items-center gap-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2">
          <Lock className="h-4 w-4 text-amber-600 shrink-0" />
          <p className="text-xs text-amber-800">Bankdaten werden verschlüsselt gespeichert. Nur Administratoren sehen den vollständigen Wert.</p>
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="IBAN" name="iban" defaultValue={s.iban ?? s.iban_masked ?? ''} placeholder="CH93 0076 2011 6238 5295 7" className="sm:col-span-2" />
          <Field label="QR-IBAN" name="qr_iban" defaultValue={s.qr_iban ?? s.qr_iban_masked ?? ''} placeholder="CH21 3080 8001 2345 6789 7" className="sm:col-span-2" />
          <Field label="Bank" name="bank_name" defaultValue={s.bank_name ?? ''} placeholder="UBS Switzerland AG" />
          <Field label="BIC/SWIFT" name="bic" defaultValue={s.bic ?? ''} placeholder="UBSWCHZH80A" />
        </div>
      </SettingsCard>

      <SettingsCard icon={<ReceiptText className="h-5 w-5" />} title="MWST & Zahlungskonditionen"
        saved={saved === 'vat'} saving={saving === 'vat'}
        onSave={(d) => saveSection('vat', { vat_method: (d.vat_method as 'effektiv' | 'saldosteuersatz') || undefined, vat_period: (d.vat_period as 'quartal' | 'semester' | 'jahr') || undefined, default_payment_days: d.default_payment_days ? Number(d.default_payment_days) : 30, default_discount_percent: d.default_discount_percent || null, default_discount_days: d.default_discount_days ? Number(d.default_discount_days) : null })}>
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

      <SettingsCard icon={<Globe2 className="h-5 w-5" />} title="EU-Erweiterungen"
        saved={saved === 'eu'} saving={saving === 'eu'}
        onSave={(d) => saveSection('eu', { oss_active: d.oss_active === 'true', oss_number: d.oss_number || null, vies_validation: d.vies_validation === 'true' })}>
        <div className="space-y-5">
          <ToggleField name="oss_active" label="OSS-Registrierung aktiv" defaultValue={s.oss_active}
            description="Aktiviert EU B2C MWST-Berechnung. Pflicht ab CHF 100'000 EU B2C-Umsatz pro Jahr." />
          {s.oss_active && <Field label="OSS-Registrierungsnummer" name="oss_number" defaultValue={s.oss_number ?? ''} placeholder="EU372012345" />}
          <ToggleField name="vies_validation" label="VIES UID-Validierung" defaultValue={s.vies_validation}
            description="Automatische Validierung von EU-Mehrwertsteuernummern bei neuen Firmenkunden." />
        </div>
      </SettingsCard>

      <SettingsCard icon={<Key className="h-5 w-5" />} title="Integrationen & API-Keys"
        saved={saved === 'integrations'} saving={saving === 'integrations'}
        onSave={(d) => saveSection('integrations', { stripe_publishable_key: d.stripe_publishable_key || null, plausible_domain: d.plausible_domain || null, hcaptcha_site_key: d.hcaptcha_site_key || null, google_maps_api_key: d.google_maps_api_key || null })}>
        <div className="mb-4 flex items-start gap-2 rounded-lg border border-blue-200 bg-blue-50 px-3 py-2">
          <Lock className="mt-0.5 h-4 w-4 text-blue-600 shrink-0" />
          <p className="text-xs text-blue-800">Secret Keys werden im Google Secret Manager verwaltet und sind hier nicht sichtbar.</p>
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Stripe Publishable Key" name="stripe_publishable_key" defaultValue={s.stripe_publishable_key ?? ''} placeholder="pk_live_…" hint="Öffentlicher Key" />
          <Field label="Plausible Domain" name="plausible_domain" defaultValue={s.plausible_domain ?? ''} placeholder="inexxio.com" />
          <Field label="hCaptcha Site Key" name="hcaptcha_site_key" defaultValue={s.hcaptcha_site_key ?? ''} placeholder="10000000-ffff-ffff-ffff-000000000001" hint="Für Kontaktformular" className="sm:col-span-2" />
          <Field label="Google Maps API Key" name="google_maps_api_key" defaultValue={s.google_maps_api_key ?? ''} placeholder="AIza…" hint="Für Lagerplatz-Karte; Maps JavaScript API + Geocoding API aktivieren, auf Domain einschränken" className="sm:col-span-2" />
        </div>
      </SettingsCard>

      <SettingsCard icon={<PackageSearch className="h-5 w-5" />} title="Lager & Logistik (Bereitstellungsorte)"
        saved={saved === 'logistics'} saving={saving === 'logistics'}
        onSave={(d) => saveSection('logistics', {
          default_receiving_location_id: d.default_receiving_location_id ? Number(d.default_receiving_location_id) : null,
        })}>
        <div className="mb-4 flex items-start gap-2 rounded-lg border border-blue-200 bg-blue-50 px-3 py-2">
          <PackageSearch className="mt-0.5 h-4 w-4 text-blue-600 shrink-0" />
          <p className="text-xs text-blue-800">
            Objektnummer eines <strong>Lagerplatzes</strong> für den <strong>Wareneingang</strong> eintragen –
            das Standard-Ziel für angelieferte Ware. Leer = das System legt bei Bedarf automatisch einen
            Lagerplatz «Wareneingang» an. <em>Verschrottete Instanzen sind bewusst standortlos</em> (der
            Endzustand «verschrottet» ist die Wo-Aussage) – daher kein Schrottplatz-Lagerort mehr.
          </p>
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Wareneingang · Lagerplatz-Nr." name="default_receiving_location_id" type="number"
            defaultValue={s.default_receiving_location_id ?? ''} placeholder="z. B. 100000200" hint="Standard-Lieferadresse" />
        </div>
      </SettingsCard>

      <SettingsCard icon={<FileText className="h-5 w-5" />} title="AGB & Datenschutz (Website-Rechtstexte)"
        saved={saved === 'legal_docs'} saving={saving === 'legal_docs'}
        onSave={(d) => saveSection('legal_docs', { legal_documents: buildLegalDocs(d, s.legal_documents) })}>
        <div className="mb-4 flex items-start gap-2 rounded-lg border border-blue-200 bg-blue-50 px-3 py-2">
          <FileText className="mt-0.5 h-4 w-4 text-blue-600 shrink-0" />
          <p className="text-xs text-blue-800">
            Objektnummer des <strong>Artikels</strong> eintragen, der das Rechtsdokument trägt (ein Artikel
            mit «Dokument»-Prozessschritt und freigegebenem Bestand). Die Website zieht daraus die erste
            freigegebene Fassung. Neue Fassung = Artikel «Ersetzen» – die Website folgt automatisch auf den
            Nachfolger, sobald dieser einen freigegebenen Beleg hat; ältere bleiben archiviert. Leer =
            eingebauter Standardtext.
          </p>
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="AGB · Artikelnummer" name="legal_agb" type="number"
            defaultValue={s.legal_documents?.agb ?? ''} placeholder="z. B. 100000123" hint="Objektnummer des AGB-Artikels" />
          <Field label="Datenschutz · Artikelnummer" name="legal_datenschutz" type="number"
            defaultValue={s.legal_documents?.datenschutz ?? ''} placeholder="z. B. 100000124" hint="Objektnummer des Datenschutz-Artikels" />
        </div>
      </SettingsCard>

      <MaintenanceCard />

      <ShopConfigCard
        settings={s}
        saving={saving === 'shop'}
        saved={saved === 'shop'}
        onSave={(d) => saveSection('shop', d)}
      />
    </div>
  );
}

// ─── Lagerwartung (E): Meldebestand prüfen (Auto-Nachbestellung) ──────────────────
function MaintenanceCard() {
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<{ reordered: number } | null>(null);
  const [err, setErr] = useState('');
  async function run() {
    setRunning(true); setErr(''); setResult(null);
    try { setResult(await api.runMaintenanceSweep()); }
    catch { setErr('Wartungslauf fehlgeschlagen.'); }
    finally { setRunning(false); }
  }
  return (
    <div className="card p-4 sm:p-6">
      <div className="mb-4 flex items-center gap-3">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-blue-50 text-blue-600"><PackageSearch className="h-5 w-5" /></div>
        <h2 className="text-base font-semibold text-slate-900">Lagerwartung</h2>
      </div>
      <p className="mb-4 text-sm text-slate-600">
        Prüft alle Artikel auf ihren Meldebestand – fehlt Bestand, wird automatisch nachbestellt.
        Läuft ausserdem reaktiv bei Bestandsabgängen; dieser Knopf stösst einen vollständigen Lauf
        sofort an.
      </p>
      <div className="flex items-center gap-3">
        <button type="button" onClick={run} disabled={running}
          className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-3 py-2 text-sm font-medium text-white disabled:opacity-50">
          {running ? <Loader2 className="h-4 w-4 animate-spin" /> : <PackageSearch className="h-4 w-4" />}
          Jetzt prüfen
        </button>
        {result && (
          <span className="text-sm text-slate-600">
            {result.reordered} nachbestellt
          </span>
        )}
        {err && <span className="text-sm text-red-600">{err}</span>}
      </div>
    </div>
  );
}

// Baut die legal_documents-Map aus den Formularfeldern (leer → Eintrag entfernen).
function buildLegalDocs(d: Record<string, string>, current: Record<string, number> | null): Record<string, number> {
  const out: Record<string, number> = { ...(current ?? {}) };
  for (const [field, kind] of [['legal_agb', 'agb'], ['legal_datenschutz', 'datenschutz']] as const) {
    const raw = (d[field] ?? '').trim();
    const n = Number(raw);
    if (raw && Number.isFinite(n) && n > 0) out[kind] = Math.trunc(n);
    else delete out[kind];
  }
  return out;
}

// ─── Shop / Verkauf ───────────────────────────────────────────────────────────

function ShopConfigCard({ settings, onSave, saving, saved }: {
  settings: CompanySettings; onSave: (d: Partial<CompanySettings>) => void; saving: boolean; saved: boolean;
}) {
  const [currencies, setCurrencies] = useState((settings.shop_currencies ?? ['CHF', 'EUR', 'USD']).join(', '));
  const [defaultCur, setDefaultCur] = useState(settings.shop_default_currency || 'CHF');
  const [provider, setProvider] = useState(settings.payments_provider || 'manual');
  const [countryMap, setCountryMap] = useState(
    Object.entries(settings.shop_country_currency ?? {}).map(([k, v]) => `${k}=${v}`).join('\n'),
  );
  const [zoneMap, setZoneMap] = useState(
    Object.entries(settings.pricing_zone_factors ?? {}).map(([k, v]) => `${k}=${v}`).join('\n'),
  );

  function save() {
    const curList = currencies.split(',').map((c) => c.trim().toUpperCase()).filter(Boolean);
    const map: Record<string, string> = {};
    for (const line of countryMap.split('\n')) {
      const [k, v] = line.split('=').map((x) => x.trim());
      if (k && v) map[k] = v.toUpperCase();
    }
    const zones: Record<string, number> = {};
    for (const line of zoneMap.split('\n')) {
      const [k, v] = line.split('=').map((x) => x.trim());
      const f = Number(v);
      if (k && v && !Number.isNaN(f) && f > 0) zones[k] = f;
    }
    onSave({
      shop_currencies: curList.length ? curList : ['CHF'],
      shop_default_currency: defaultCur.trim().toUpperCase() || 'CHF',
      payments_provider: provider,
      shop_country_currency: Object.keys(map).length ? map : null,
      pricing_zone_factors: Object.keys(zones).length ? zones : null,
    });
  }

  return (
    <div className="card p-4 sm:p-6">
      <div className="mb-5 flex items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-blue-50 text-blue-600"><ShoppingBag className="h-5 w-5" /></div>
          <h2 className="text-base font-semibold text-slate-900">Shop / Verkauf</h2>
        </div>
        <div className="flex items-center gap-1.5 text-xs shrink-0">
          {saving && <><Loader2 className="h-3.5 w-3.5 animate-spin text-slate-400" /><span className="text-slate-400">Speichert…</span></>}
          {saved && !saving && <><CheckCircle2 className="h-3.5 w-3.5 text-green-500" /><span className="text-green-600">Gespeichert</span></>}
        </div>
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        <div className="sm:col-span-2">
          <label className="block text-sm font-medium text-slate-700 mb-1.5">Währungen (Shop-Umschalter)</label>
          <input value={currencies} onChange={(e) => setCurrencies(e.target.value)} className="form-input" placeholder="CHF, EUR, USD" />
          <p className="mt-1 text-xs text-slate-500">Komma-getrennt. Die erste/markierte ist die Standard-Währung.</p>
        </div>
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1.5">Standard-Währung</label>
          <input value={defaultCur} onChange={(e) => setDefaultCur(e.target.value)} className="form-input" placeholder="CHF" />
        </div>
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1.5">Zahlungs-Provider</label>
          <select value={provider} onChange={(e) => setProvider(e.target.value)} className="form-input">
            <option value="manual">Manuell (Test, ohne externen Dienst)</option>
            <option value="stripe">Stripe (Gerüst – Keys erforderlich)</option>
          </select>
        </div>
        <div className="sm:col-span-2">
          <label className="block text-sm font-medium text-slate-700 mb-1.5">Land → Währung (optional)</label>
          <textarea value={countryMap} onChange={(e) => setCountryMap(e.target.value)} rows={3}
            className="form-input" placeholder={'Deutschland=EUR\nUSA=USD'} />
          <p className="mt-1 text-xs text-slate-500">Eine Zuordnung pro Zeile: <code>Land=WÄHRUNG</code>. Bestimmt die Default-Währung je Land.</p>
        </div>
        <div className="sm:col-span-2">
          <label className="block text-sm font-medium text-slate-700 mb-1.5">Kaufkraft-Faktoren / Zonen (optional, PPP)</label>
          <textarea value={zoneMap} onChange={(e) => setZoneMap(e.target.value)} rows={2}
            className="form-input" placeholder={'Deutschland=1.1\nUSA=0.9'} />
          <p className="mt-1 text-xs text-slate-500">Eine Zeile je Land: <code>Land=Faktor</code> (z. B. 1.1). Leer = abgeschaltet – der Basispreis gilt unverändert.</p>
        </div>
      </div>
      <div className="mt-4">
        <button type="button" onClick={save} disabled={saving}
          className="inline-flex items-center gap-1 rounded-lg bg-blue-600 px-3 py-2 text-sm font-medium text-white disabled:opacity-50">
          Speichern
        </button>
      </div>
    </div>
  );
}

// ─── Sub-components ───────────────────────────────────────────────────────────

function SettingsCard({ icon, title, children, onSave, saving, saved }: {
  icon: React.ReactNode; title: string; children: React.ReactNode;
  onSave: (data: Record<string, string>) => void; saving: boolean; saved: boolean;
}) {
  const formRef = useRef<HTMLFormElement>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  function collectData(form: HTMLFormElement): Record<string, string> {
    const data: Record<string, string> = {};
    new FormData(form).forEach((value, key) => { data[key] = value as string; });
    return data;
  }

  function scheduleAutoSave() {
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => {
      if (formRef.current) onSave(collectData(formRef.current));
    }, 3000);
  }

  return (
    <form ref={formRef} onSubmit={(e) => { e.preventDefault(); if (timerRef.current) clearTimeout(timerRef.current); onSave(collectData(e.currentTarget)); }} onChange={scheduleAutoSave} className="card p-4 sm:p-6">
      <div className="mb-5 flex items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-blue-50 text-blue-600">{icon}</div>
          <h2 className="text-base font-semibold text-slate-900">{title}</h2>
        </div>
        <div className="flex items-center gap-1.5 text-xs shrink-0">
          {saving && <><Loader2 className="h-3.5 w-3.5 animate-spin text-slate-400" /><span className="text-slate-400">Speichert…</span></>}
          {saved && !saving && <><CheckCircle2 className="h-3.5 w-3.5 text-green-500" /><span className="text-green-600">Gespeichert</span></>}
        </div>
      </div>
      {children}
    </form>
  );
}

function Field({ label, name, type = 'text', defaultValue, required, placeholder, hint, className = '' }: {
  label: string; name: string; type?: string; defaultValue?: string | number | null;
  required?: boolean; placeholder?: string; hint?: string; className?: string;
}) {
  return (
    <div className={className}>
      <label htmlFor={name} className="block text-sm font-medium text-slate-700 mb-1.5">
        {label}{required && <span className="ml-1 text-red-500">*</span>}
      </label>
      <input id={name} name={name} type={type} defaultValue={defaultValue ?? ''} required={required} placeholder={placeholder} className="form-input" />
      {hint && <p className="mt-1 text-xs text-slate-500">{hint}</p>}
    </div>
  );
}

function ToggleField({ name, label, defaultValue, description }: {
  name: string; label: string; defaultValue: boolean; description: string;
}) {
  const [enabled, setEnabled] = useState(defaultValue);
  return (
    <div className="flex items-start justify-between gap-4">
      <div>
        <p className="text-sm font-medium text-slate-900">{label}</p>
        <p className="mt-0.5 text-xs text-slate-500">{description}</p>
      </div>
      <input type="hidden" name={name} value={String(enabled)} />
      <button type="button" onClick={() => setEnabled(!enabled)}
        className={`relative inline-flex h-6 w-11 shrink-0 items-center rounded-full transition-colors focus:outline-none ${enabled ? 'bg-blue-600' : 'bg-slate-200'}`}>
        <span className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${enabled ? 'translate-x-6' : 'translate-x-1'}`} />
      </button>
    </div>
  );
}
