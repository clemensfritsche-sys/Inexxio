'use client';

import { useEffect, useState } from 'react';
import { Building2, FileText, Phone, Landmark, ReceiptText, Globe2, Key, Server, Sparkles, CreditCard, Coins, FolderOpen  } from 'lucide-react';
import { api } from '@/lib/api';
import type { CompanySettings, OperatingCosts, Site, SiteInput } from '@/types';
import { Field, Sec } from '@/components/erp/user-detail';
import { ObjectDocuments } from '@/components/erp/object-documents';
import { DetailTabs } from '@/components/erp/detail-tabs';
import { DetailHeader, StatusBadge } from '@/components/erp/fields';
import { AddressField, type Address } from '@/components/erp/address-field';
import { useMapsApiKey } from '@/components/erp/use-maps-key';

// Das Unternehmen führt das Land als Klarnamen (nicht ISO-2) – die Auswahl bestimmt
// daher zugleich das Format, das die Adress-Suche übernehmen darf.
const COUNTRIES: [string, string][] = [
  ['Schweiz', 'Schweiz'], ['Deutschland', 'Deutschland'], ['Österreich', 'Österreich'],
  ['Frankreich', 'Frankreich'], ['Italien', 'Italien'], ['Liechtenstein', 'Liechtenstein'],
];
const ISO_TO_NAME: Record<string, string> = {
  CH: 'Schweiz', DE: 'Deutschland', AT: 'Österreich', FR: 'Frankreich',
  IT: 'Italien', LI: 'Liechtenstein',
};

/** «Musterstrasse 12» → ('Musterstrasse', '12'). Das Unternehmen führt Strasse und
 *  Hausnummer getrennt; Google (und jede andere Quelle) liefert sie als eine Zeile. */
function splitStreet(line: string): [string, string] {
  const m = line.trim().match(/^(.*?)[\s,]+(\d+[a-zA-Z]?)$/);
  return m ? [m[1].trim(), m[2]] : [line.trim(), ''];
}

type OrgTab = 'stamm' | 'docs';

/** Aus einem (Teil-)Formular die reinen **Standortfelder** ziehen – der Gegenweg zu
 *  `siteAsBase`. Nur gesetzte Schlüssel wandern mit, damit ein PATCH nie Felder nullt,
 *  die gar nicht angefasst wurden. */
function siteFieldsOf(s: Partial<CompanySettings>): SiteInput {
  const out: SiteInput = {};
  if ('company_name' in s) out.company_name = s.company_name ?? '';
  if ('street' in s) out.street = s.street ?? null;
  if ('street_number' in s) out.street_number = s.street_number ?? null;
  if ('zip' in s) out.zip = s.zip ?? null;
  if ('city' in s) out.city = s.city ?? null;
  if ('country' in s) out.country = s.country ?? null;
  if ('email' in s) out.email = s.email ?? null;
  if ('phone' in s) out.phone = s.phone ?? null;
  return out;
}

/** Die Felder, die ein Standort mit dem Unternehmens-Datensatz **teilt** – mehr trägt ein
 *  Nebenstandort nicht. So kann dieselbe Maske beide rendern, ohne zwei Formulare. */
function siteAsBase(s: Site): Partial<CompanySettings> {
  return {
    object_id: s.object_id, company_name: s.company_name,
    street: s.street ?? '', street_number: s.street_number,
    zip: s.zip ?? '', city: s.city ?? '', country: s.country ?? '',
    email: s.email ?? '', phone: s.phone,
  };
}

/**
 * Detailansicht eines **Standorts** als vollwertiger ERP-Datensatz – im **gleichen
 * Layout wie die Benutzer-Detailseite** (Kopf mit Objektnummer, Sektions-Karten mit
 * Feld-Raster, Speicherleiste).
 *
 * **Ein Fenster, zwei Ausprägungen** – der Unterschied ist keine zweite Ansicht, sondern
 * schlicht, wie viel es zu zeigen gibt:
 *
 *   * **Hauptsitz** (`is_primary`): zusätzlich Rechtsidentität, Bank, MWST, Integrationen
 *     und Rechtstexte – die Firmen-/ERP-Konfiguration wird hier gepflegt (admin-geschützt).
 *   * **Nebenstandort**: Name, Anschrift, Kontakt. Nicht weil «weniger wichtig», sondern
 *     weil es eine UID nur EINMAL gibt; sie an n Standorten editierbar zu machen, wäre
 *     dieselbe Angabe an n Stellen.
 */
export function OrganizationDetail({ record, onSaved, onBack }: {
  record: Site;
  onSaved: (s: Site) => void;
  onBack: () => void;
}) {
  const isPrimary = record.is_primary;
  const [settings, setSettings] = useState<CompanySettings | null>(null);
  const [form, setForm] = useState<Partial<CompanySettings>>({});
  const [dirty, setDirty] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<OrgTab>('stamm');
  const mapsKey = useMapsApiKey();

  // Die Firmenadresse ist EIN Feld (Suche zuerst); Strasse und Hausnummer werden
  // beim Übernehmen getrennt, weil das Unternehmen sie in zwei Spalten führt.
  function applyCompanyAddress(a: Address) {
    const [street, nr] = splitStreet(a.street);
    setForm((prev) => ({ ...prev, street, street_number: nr, zip: a.zip, city: a.city, country: a.country }));
    setDirty(true);
  }

  useEffect(() => {
    setForm({}); setDirty(false); setError(null); setSettings(null);
    // Nur der Hauptsitz hat mehr zu zeigen, als der Datensatz selbst schon trägt –
    // für einen Nebenstandort gibt es nichts nachzuladen.
    if (!isPrimary) return;
    api.getSettings().then(setSettings).catch(() => setSettings(null));
  }, [record, isPrimary]);

  const base: Partial<CompanySettings> = settings ?? siteAsBase(record);
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
      if (isPrimary) {
        // Der Hauptsitz läuft über die Firmeneinstellungen – dort sitzt u. a. die
        // IBAN-Sonderbehandlung. Die Standortfelder gehen denselben Weg mit.
        const updated = await api.updateSettings(form);
        setSettings(updated);
        onSaved({ ...record, ...siteFieldsOf(updated) });
      } else if (record.object_id) {
        onSaved(await api.updateSite(record.object_id, siteFieldsOf(form)));
      }
      setForm({}); setDirty(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Fehler beim Speichern');
    } finally { setSaving(false); }
  }

  // Rechtstexte-Zeiger (kind → Artikelnummer) + Bestätigungspflicht (kind → Rollen).
  const legalDocs: Record<string, number> =
    (('legal_documents' in form ? form.legal_documents : base.legal_documents) as Record<string, number> | null | undefined) ?? {};
  function setLegal(kind: 'agb' | 'datenschutz') {
    return (val: string | boolean) => {
      const raw = String(val ?? '').trim();
      const n = Number(raw);
      const next: Record<string, number> = { ...legalDocs };
      if (raw && Number.isFinite(n) && n > 0) next[kind] = Math.trunc(n);
      else delete next[kind];
      setForm((prev) => ({ ...prev, legal_documents: next }));
      setDirty(true);
    };
  }

  return (
    <div className="flex flex-col h-full">
      {/* Kopf – die EINE Anatomie aller Datensatz-Fenster (`DetailHeader`, Notiz #242). */}
      <DetailHeader
        icon={Building2} iconBg="#F3E5DD" iconFg="#A65A3C"
        eyebrow={isPrimary ? 'Unternehmen' : 'Standort'} title={(v('company_name') as string) || null}
        objectId={record.object_id} onBack={onBack}
        status={{ label: isPrimary ? 'Hauptsitz' : 'Standort', color: 'var(--success)',
                  bg: 'var(--success-bg)', icon: Building2 }}
      >
        <DetailTabs<OrgTab> style={{ marginTop: 16 }} active={tab} onChange={setTab} tabs={[
          { key: 'stamm', label: 'Stammdaten', icon: Building2 },
          { key: 'docs', label: 'Dokumente', icon: FolderOpen },
        ]} />
      </DetailHeader>

      {/* Content */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '16px 20px 88px', background: 'var(--bg-2)' }}>
        {tab === 'docs' && <ObjectDocuments objectId={record.object_id}
          contextLabel={isPrimary ? 'dem Unternehmen' : 'dem Standort'} />}
        {tab === 'stamm' && (<>
        <Sec title="Allgemeine Angaben" editable icon={Building2}>
          <Field label={isPrimary ? 'Firmenname' : 'Standortname'} val={v('company_name')} onChange={set('company_name')} span2 />
          {isPrimary && <Field label="Rechtsform" val={v('legal_form')} onChange={set('legal_form')} />}
          <div style={{ gridColumn: '1 / -1' }}>
            <AddressField
              value={{
                street: [v('street'), v('street_number')].filter(Boolean).join(' '),
                zip: (v('zip') as string) ?? '', city: (v('city') as string) ?? '',
                country: (v('country') as string) ?? 'Schweiz',
              }}
              onChange={applyCompanyAddress} apiKey={mapsKey}
              countryOptions={COUNTRIES} label={isPrimary ? 'Firmensitz' : 'Anschrift'} />
          </div>
          {/* Eine Tatsache über DIESEN Datensatz, kein Erklärtext: ohne eigene Anschrift
              lässt sich ein Standort nicht von den übrigen unterscheiden – eine Bewegung
              dorthin bleibt innerbetrieblich statt Versand zu werden (ADR 005). */}
          {!isPrimary && !record.has_address && !dirty && (
            <div style={{ gridColumn: '1 / -1', font: '500 11.5px var(--font-body)',
                          color: 'var(--warning)', lineHeight: 1.5 }}>
              Ohne Anschrift zählt eine Bewegung hierher als innerbetrieblich – kein Versand.
            </div>
          )}
        </Sec>

        {isPrimary && (<>
        <Sec title="Rechtliche Identifikation" editable icon={FileText}>
          <Field label="UID-Nummer" val={v('uid')} onChange={set('uid')} />
          <Field label="MWST-Nummer" val={v('vat_number')} onChange={set('vat_number')} />
          <Field label="Handelsregister-Nr." val={v('trade_register_number')} onChange={set('trade_register_number')} />
          <Field label="HR-Kanton" val={v('trade_register_canton')} onChange={set('trade_register_canton')} />
          <Field label="Aktienkapital" val={v('share_capital')} onChange={set('share_capital')} span2 />
        </Sec>

        </>)}

        <Sec title="Kontakt & Web" editable icon={Phone}>
          <Field label="E-Mail" val={v('email')} onChange={set('email')} type="email" span2 />
          <Field label="Telefon" val={v('phone')} onChange={set('phone')} />
          {isPrimary && <Field label="Website" val={v('website')} onChange={set('website')} />}
        </Sec>

        {isPrimary && (<>
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


        <Sec title="AGB & Datenschutz (Website-Rechtstexte)" editable icon={FileText}>
          <Field label="AGB · Artikelnummer" val={legalDocs.agb != null ? String(legalDocs.agb) : ''} onChange={setLegal('agb')} />
          <Field label="Datenschutz · Artikelnummer" val={legalDocs.datenschutz != null ? String(legalDocs.datenschutz) : ''} onChange={setLegal('datenschutz')} />
          <div style={{ gridColumn: '1 / -1', font: '500 11.5px var(--font-body)', color: 'var(--fg-4)', lineHeight: 1.5 }}>
            Die AGB müssen von allen angemeldeten Nutzern (inkl. Lieferanten) aktiv bestätigt werden;
            bei einer neuen Fassung («Ersetzen» des Artikels) erneut. Das Dokument muss dazu im
            Auftrag <strong>ausgestellt</strong> sein.
          </div>
        </Sec>

        <CostOverview />
        </>)}
        </>)}
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

// ─── Betriebskosten-Übersicht – tatsächliche Zahlen Monat-bis-heute ───────────
// KI (Tokens × Tarif) und Zahlungen (Stripe-Gebühren) sind GEMESSEN; die Infrastruktur
// ist eine anteilige Schätzung der fixen Google-Cloud-Grundkosten. Kompakt gruppiert,
// mit grosser Summe und Monats-Hochrechnung.
const GROUP_ICON: Record<string, React.ElementType> = {
  ai: Sparkles, payments: CreditCard, infrastructure: Server,
};

function chf(v: number): string {
  return v.toLocaleString('de-CH', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function CostOverview() {
  const [data, setData] = useState<OperatingCosts | null>(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    let cancelled = false;
    api.getOperatingCosts().then((d) => { if (!cancelled) setData(d); }).catch(() => { if (!cancelled) setFailed(true); });
    return () => { cancelled = true; };
  }, []);
  if (failed) return null;   // Zusatz-Übersicht – bei Fehler still weglassen (kein Blocker)

  const unit = <span style={{ font: '600 11px var(--font-body)', color: 'var(--fg-4)', marginLeft: 3 }}>CHF</span>;
  return (
    <div style={{ marginBottom: 18 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
        <span style={{ width: 26, height: 26, borderRadius: 'var(--r-sm)', background: '#F4EBDD', color: '#9A7238', display: 'flex', alignItems: 'center', justifyContent: 'center', flex: 'none' }}>
          <Coins size={15} />
        </span>
        <span style={{ font: '800 13px var(--font-display)', letterSpacing: '.02em', color: 'var(--fg-1)' }}>
          Betriebskosten{data ? ` · ${data.period_label}` : ''}
        </span>
      </div>
      <div style={{ background: '#fff', border: '1px solid var(--border-1)', borderRadius: 'var(--r-lg)', overflow: 'hidden' }}>
        {/* Kopf: grosse Ist-Summe + Monats-Hochrechnung */}
        <div style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', gap: 16, padding: '16px 18px 14px', background: 'linear-gradient(180deg,#FBF7F0,#fff)' }}>
          <div>
            <div style={{ font: '600 11px var(--font-body)', textTransform: 'uppercase', letterSpacing: '.06em', color: 'var(--fg-4)' }}>
              Bisher diesen Monat{data ? ` · Tag ${data.day_of_month}/${data.days_in_month}` : ''}
            </div>
            <div style={{ font: '800 26px var(--font-display)', color: 'var(--fg-1)', fontVariantNumeric: 'tabular-nums', marginTop: 2 }}>
              {data ? chf(data.total_mtd_chf) : '—'}{unit}
            </div>
          </div>
          {data && (
            <div style={{ textAlign: 'right' }}>
              <div style={{ font: '600 11px var(--font-body)', color: 'var(--fg-4)' }}>Hochrechnung Monat</div>
              <div style={{ font: '700 15px var(--font-body)', color: 'var(--fg-2)', fontVariantNumeric: 'tabular-nums' }}>
                ≈ {chf(data.projected_month_chf)}{unit}
              </div>
            </div>
          )}
        </div>
        {/* Gruppen – je eine kompakte Zeile mit Basis-Badge + Betrag + Detail-Hinweis */}
        {(data?.groups ?? []).map((g) => {
          const Icon = GROUP_ICON[g.key] ?? Coins;
          const measured = g.basis === 'actual';
          const hints = g.items.map((i) => i.hint).filter(Boolean).join(' · ');
          return (
            <div key={g.key} style={{ borderTop: '1px solid var(--border-1)', padding: '10px 18px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <Icon size={15} style={{ color: 'var(--fg-3)', flex: 'none' }} />
                <span style={{ flex: 1, font: '650 13.5px var(--font-body)', color: 'var(--fg-1)', minWidth: 0 }}>{g.label}</span>
                <span style={{ flex: 'none', font: '600 10px var(--font-body)', textTransform: 'uppercase', letterSpacing: '.04em', padding: '2px 7px', borderRadius: 999,
                  color: measured ? '#166534' : '#9A7238', background: measured ? '#DCFCE7' : '#F4EBDD' }}>
                  {measured ? 'gemessen' : 'geschätzt'}
                </span>
                <span style={{ flex: 'none', font: '700 14px var(--font-body)', color: 'var(--fg-1)', fontVariantNumeric: 'tabular-nums', whiteSpace: 'nowrap', minWidth: 78, textAlign: 'right' }}>
                  {chf(g.total_chf)}{unit}
                </span>
              </div>
              {hints && (
                <div style={{ font: '500 11.5px var(--font-body)', color: 'var(--fg-4)', marginTop: 3, marginLeft: 25 }}>{hints}</div>
              )}
            </div>
          );
        })}
        {!data && !failed && (
          <div style={{ padding: '14px 18px', borderTop: '1px solid var(--border-1)', font: '500 12.5px var(--font-body)', color: 'var(--fg-4)' }}>
            Wird geladen …
          </div>
        )}
      </div>
      <p style={{ font: '500 11.5px var(--font-body)', color: 'var(--fg-4)', lineHeight: 1.5, marginTop: 8 }}>
        KI und Zahlungen sind <b>tatsächlich gemessen</b> (verbrauchte Tokens × Modell-Tarif bzw. Stripe-Gebühren
        der bezahlten Verkäufe). Die Infrastruktur ist eine anteilige Schätzung der fixen Google-Cloud-Grundkosten.
      </p>
    </div>
  );
}

