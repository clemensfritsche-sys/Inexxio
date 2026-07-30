'use client';

import { useEffect, useState } from 'react';
import { Building2, FileText, Phone, Landmark, ReceiptText, Globe2, Server, Sparkles, CreditCard, Coins, FolderOpen, Star  } from 'lucide-react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { api } from '@/lib/api';
import type { CompanySettings, OperatingCosts } from '@/types';
import { Field, Sec } from '@/components/erp/user-detail';
import { ObjectDocuments } from '@/components/erp/object-documents';
import { DetailTabs } from '@/components/erp/detail-tabs';
import { DetailHeader } from '@/components/erp/fields';
import { AddressField, type Address, toIso2 } from '@/components/erp/address-field';
import { useMapsApiKey } from '@/components/erp/use-maps-key';
import { SystemConfigSection } from '@/components/account/sections/system-config-section';
import { TerritoryMap } from '@/components/erp/territory-map';

// Das Unternehmen führt das Land als Klarnamen (nicht ISO-2). Die Adress-Suche mappt Googles
// ISO-2-Code über ``toIso2`` auf diese Klarnamen (siehe address-field.tsx). Eine Gesellschaft
// kann überall sitzen – daher eine breitere Auswahl als bei einer CH/EU-Personenadresse.
const COUNTRIES: [string, string][] = [
  ['Schweiz', 'Schweiz'], ['Deutschland', 'Deutschland'], ['Österreich', 'Österreich'],
  ['Frankreich', 'Frankreich'], ['Italien', 'Italien'], ['Liechtenstein', 'Liechtenstein'],
  ['USA', 'USA'], ['Grossbritannien', 'Grossbritannien'], ['Spanien', 'Spanien'],
  ['Niederlande', 'Niederlande'], ['Belgien', 'Belgien'], ['Luxemburg', 'Luxemburg'],
  ['Portugal', 'Portugal'], ['Irland', 'Irland'],
];
// Auswählbare Funktionswährungen + Land→Währung-Vorschlag über **ISO-2** (Spiegel von
// services/sites._COUNTRY_CURRENCY; nur eine UI-Bequemlichkeit – die Wahrheit setzt das
// Backend beim Anlegen, hier wird beim Länderwechsel nur vorgeschlagen). ISO-2, damit es
// egal ist, ob das Land als Klarname («USA») oder Code («US») ankommt.
const CURRENCIES = ['CHF', 'EUR', 'USD', 'GBP'];
const CURRENCY_BY_ISO2: Record<string, string> = {
  CH: 'CHF', LI: 'CHF', US: 'USD', GB: 'GBP',
  DE: 'EUR', AT: 'EUR', FR: 'EUR', IT: 'EUR', ES: 'EUR', NL: 'EUR', BE: 'EUR', LU: 'EUR',
  PT: 'EUR', IE: 'EUR', FI: 'EUR',
};
function suggestCurrency(country: string | undefined): string | undefined {
  return CURRENCY_BY_ISO2[toIso2(country)];
}

// EIN QueryClient für den System-Reiter (die Plattform-Konfiguration nutzt React Query,
// wie zuvor die – jetzt entfallene – Seite Admin → Einstellungen).
const systemQueryClient = new QueryClient({
  defaultOptions: { queries: { retry: 1, staleTime: 60_000 } },
});

/** «Musterstrasse 12» → ('Musterstrasse', '12'). Das Unternehmen führt Strasse und
 *  Hausnummer getrennt; Google (und jede andere Quelle) liefert sie als eine Zeile. */
function splitStreet(line: string): [string, string] {
  const m = line.trim().match(/^(.*?)[\s,]+(\d+[a-zA-Z]?)$/);
  return m ? [m[1].trim(), m[2]] : [line.trim(), ''];
}

type OrgTab = 'stamm' | 'system' | 'docs';

/**
 * Detailansicht eines **Unternehmens** (einer Gesellschaft) – ein gleichrangiger
 * ERP-Datensatz im gleichen Layout wie die Benutzer-Detailseite (Kopf mit Objektnummer,
 * Sektions-Karten, Speicherleiste).
 *
 * **Ein Fenster, ein Feldsatz – für JEDE Gesellschaft gleich.** Jede trägt ihre eigene,
 * vollständige Rechtsidentität (die US-Gesellschaft hat ihre eigene EIN/Steuer/Bank). Es
 * gibt keinen «Hauptsitz» mit mehr Feldern und keinen kastrierten «Standort».
 *
 * Die **Plattform-/Systemkonfiguration** (Stripe, Shop, Rechtstexte) gilt der EINEN
 * Website, nicht je Gesellschaft – sie lebt in der **Systemkonfiguration**
 * (Admin → Einstellungen), nicht hier. Der **Betreiber** (`is_operator`, das älteste
 * Unternehmen) vertritt die Website nach aussen; das ist eine abgeleitete Rolle, kein Rang
 * – der einzige sichtbare Unterschied ist ein dezenter Hinweis und die Konzern-Kosten.
 */
export function OrganizationDetail({ record, onSaved, onBack }: {
  record: CompanySettings;
  onSaved: (s: CompanySettings) => void;
  onBack: () => void;
}) {
  // Frisch nachgeladener Datensatz (der Feed liefert schon den vollen Satz, aber beim
  // Öffnen holen wir ihn erneut – Bank maskiert, abgeleitete Felder aktuell).
  const [loaded, setLoaded] = useState<CompanySettings | null>(null);
  const [form, setForm] = useState<Partial<CompanySettings>>({});
  const [dirty, setDirty] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<OrgTab>('stamm');
  const [opBusy, setOpBusy] = useState(false);
  const mapsKey = useMapsApiKey();

  const base: CompanySettings = loaded ?? record;
  const isOperator = !!base.is_operator;

  // Die Firmenadresse ist EIN Feld (Suche zuerst); Strasse und Hausnummer werden
  // beim Übernehmen getrennt, weil das Unternehmen sie in zwei Spalten führt. Beim
  // Länderwechsel wird die Währung **vorgeschlagen** (US → USD), aber nicht erzwungen.
  function applyCompanyAddress(a: Address) {
    const [street, nr] = splitStreet(a.street);
    const suggested = suggestCurrency(a.country);
    setForm((prev) => ({
      ...prev, street, street_number: nr, zip: a.zip, city: a.city, country: a.country,
      ...(suggested ? { currency: suggested } : {}),
    }));
    setDirty(true);
  }

  /** Diese Gesellschaft zum Betreiber der Website machen (genau eine trägt den Titel). */
  async function makeOperator() {
    if (record.object_id == null) return;
    setOpBusy(true); setError(null);
    try {
      const updated = await api.setCompanyOperator(record.object_id);
      setLoaded(updated);
      onSaved(updated);   // Eltern-Feed lädt die Liste neu → alter Betreiber verliert den Titel
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Betreiber konnte nicht gesetzt werden');
    } finally { setOpBusy(false); }
  }

  useEffect(() => {
    setForm({}); setDirty(false); setError(null); setLoaded(null); setTab('stamm');
    if (record.object_id != null) api.getCompany(record.object_id).then(setLoaded).catch(() => setLoaded(null));
  }, [record]);

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
    if (record.object_id == null) return;
    setSaving(true); setError(null);
    try {
      // EIN Pfad für JEDE Gesellschaft (auch den Betreiber): die Entitäts-Felder gehen an
      // den Datensatz selbst. Die Plattform-Konfiguration wird hier gar nicht angeboten.
      const updated = await api.updateCompany(record.object_id, form);
      setLoaded(updated);
      onSaved(updated);
      setForm({}); setDirty(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Fehler beim Speichern');
    } finally { setSaving(false); }
  }

  return (
    <div className="flex flex-col h-full">
      {/* Kopf – die EINE Anatomie aller Datensatz-Fenster (`DetailHeader`, Notiz #242).
          Für jede Gesellschaft gleich; kein «Hauptsitz»-Rang. */}
      <DetailHeader
        icon={Building2} iconBg="#F3E5DD" iconFg="#A65A3C"
        eyebrow="Unternehmen" title={(v('company_name') as string) || null}
        objectId={record.object_id} onBack={onBack}
        status={{ label: 'Unternehmen', color: 'var(--success)', bg: 'var(--success-bg)', icon: Building2 }}
      >
        <DetailTabs<OrgTab> style={{ marginTop: 16 }} active={tab} onChange={setTab} tabs={[
          { key: 'stamm', label: 'Stammdaten', icon: Building2 },
          // Der System-Reiter (Plattform-Konfiguration der EINEN Website) erscheint nur am
          // Betreiber – es gibt ihn genau einmal.
          ...(isOperator ? [{ key: 'system' as const, label: 'System', icon: Server }] : []),
          { key: 'docs', label: 'Dokumente', icon: FolderOpen },
        ]} />
      </DetailHeader>

      {/* Content */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '16px 20px 88px', background: 'var(--bg-2)' }}>
        {tab === 'docs' && <ObjectDocuments objectId={record.object_id} contextLabel="dem Unternehmen" />}
        {tab === 'system' && isOperator && (
          <QueryClientProvider client={systemQueryClient}>
            <SystemConfigSection onSaved={(s) => onSaved({ ...base, ...s })} />
          </QueryClientProvider>
        )}
        {tab === 'stamm' && (<>
        <Sec title="Allgemeine Angaben" editable icon={Building2}>
          <Field label="Name" val={v('company_name')} onChange={set('company_name')} span2 />
          <Field label="Rechtsform" val={v('legal_form')} onChange={set('legal_form')} />
          <div style={{ gridColumn: '1 / -1' }}>
            <AddressField
              value={{
                street: [v('street'), v('street_number')].filter(Boolean).join(' '),
                zip: (v('zip') as string) ?? '', city: (v('city') as string) ?? '',
                country: (v('country') as string) ?? 'Schweiz',
              }}
              onChange={applyCompanyAddress} apiKey={mapsKey}
              countryOptions={COUNTRIES} label="Anschrift" />
          </div>
          {/* Funktionswährung – aus dem Land vorbelegt (US → USD), frei änderbar. Grundlage
              für «ein Preis, überall in Landeswährung». */}
          <Field label="Währung" val={v('currency')} onChange={set('currency')}
            type="select" opts={CURRENCIES} />
          {/* Betreiber der Website – WÄHLBAR, genau eine Gesellschaft trägt den Titel. */}
          <div style={{ gridColumn: '1 / -1' }}>
            {isOperator ? (
              <div style={{ display: 'flex', alignItems: 'center', gap: 8,
                            font: '600 12px var(--font-body)', color: 'var(--fg-3)' }}>
                <Star size={14} style={{ color: 'var(--warning)' }} fill="currentColor" />
                Betreiber der Website – nennt das Impressum und trägt die Systemkonfiguration
                (Reiter «System»).
              </div>
            ) : (
              <button type="button" onClick={makeOperator} disabled={opBusy}
                className="erp-actbtn" style={{ display: 'inline-flex', alignItems: 'center', gap: 7 }}>
                <Star size={14} /> {opBusy ? 'Wird gesetzt…' : 'Als Betreiber der Website festlegen'}
              </button>
            )}
          </div>
          {/* Eine Tatsache über DIESEN Datensatz: ohne eigene Anschrift bleibt eine Bewegung
              hierher innerbetrieblich statt Versand zu werden (ADR 005). */}
          {!base.has_address && !dirty && (
            <div style={{ gridColumn: '1 / -1', font: '500 11.5px var(--font-body)',
                          color: 'var(--warning)', lineHeight: 1.5 }}>
              Ohne Anschrift zählt eine Bewegung hierher als innerbetrieblich – kein Versand.
            </div>
          )}
        </Sec>

        {/* Rechtsidentität – für JEDE Gesellschaft (die US-Gesellschaft hat ihre eigene EIN). */}
        <Sec title="Rechtliche Identifikation" editable icon={FileText}>
          <Field label="UID / Steuernummer" val={v('uid')} onChange={set('uid')} />
          <Field label="MWST-Nummer" val={v('vat_number')} onChange={set('vat_number')} />
          <Field label="Handelsregister-Nr." val={v('trade_register_number')} onChange={set('trade_register_number')} />
          <Field label="HR-Kanton / Region" val={v('trade_register_canton')} onChange={set('trade_register_canton')} />
          <Field label="Kapital" val={v('share_capital')} onChange={set('share_capital')} span2 />
        </Sec>

        <Sec title="Kontakt & Web" editable icon={Phone}>
          <Field label="E-Mail" val={v('email')} onChange={set('email')} type="email" span2 />
          <Field label="Telefon" val={v('phone')} onChange={set('phone')} />
          <Field label="Website" val={v('website')} onChange={set('website')} />
        </Sec>

        <Sec title="Bankdaten" editable icon={Landmark}>
          <Field label="IBAN / Konto" val={v('iban') ?? (base.iban_masked ?? '')} onChange={set('iban')} span2 />
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

        {/* Gebiete (Weltkarte) – seit Notiz #299 hier im Stammdaten-Reiter statt als eigener
            Reiter: welche Märkte diese Gesellschaft fakturiert, ist Stammdaten. Die Karte ist
            global (alle Regionen/Gesellschaften) und hebt die aktuelle hervor. */}
        <Sec title="Gebiete" editable icon={Globe2}>
          <div style={{ gridColumn: '1 / -1' }}>
            <TerritoryMap highlight={record.object_id} embedded />
          </div>
        </Sec>

        {/* Konzern-Kosten – eine GRUPPEN-Kennzahl (nicht je Gesellschaft), darum am
            Betreiber, der die Gruppe nach aussen vertritt. */}
        {isOperator && <CostOverview />}
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
        <span style={{ width: 26, height: 26, borderRadius: 'var(--r-sm)', background: 'var(--bg-3)', color: 'var(--fg-3)', display: 'flex', alignItems: 'center', justifyContent: 'center', flex: 'none' }}>
          <Coins size={15} />
        </span>
        <span style={{ font: '800 13px var(--font-display)', letterSpacing: '.02em', color: 'var(--fg-1)' }}>
          Betriebskosten{data ? ` · ${data.period_label}` : ''}
        </span>
      </div>
      <div style={{ background: '#fff', border: '1px solid var(--border-1)', borderRadius: 'var(--r-lg)', overflow: 'hidden' }}>
        {/* Kopf: grosse Ist-Summe + Monats-Hochrechnung (Notiz #292: Design-Tokens statt Hex). */}
        <div style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', gap: 16, padding: '16px 18px 14px', background: 'var(--bg-2)', borderBottom: '1px solid var(--border-1)' }}>
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
          // Harter Wert = gemessen (aus dem Event-Strom) ODER fix (hinterlegter Realbetrag, #293)
          // → grün; nur der reine Schätzwert ist neutral.
          const known = g.basis === 'actual' || g.basis === 'fixed';
          const basisLabel = g.basis === 'actual' ? 'gemessen' : g.basis === 'fixed' ? 'fix' : 'geschätzt';
          const hints = g.items.map((i) => i.hint).filter(Boolean).join(' · ');
          return (
            <div key={g.key} style={{ borderTop: '1px solid var(--border-1)', padding: '10px 18px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <Icon size={15} style={{ color: 'var(--fg-3)', flex: 'none' }} />
                <span style={{ flex: 1, font: '650 13.5px var(--font-body)', color: 'var(--fg-1)', minWidth: 0 }}>{g.label}</span>
                <span style={{ flex: 'none', font: '600 10px var(--font-body)', textTransform: 'uppercase', letterSpacing: '.04em', padding: '2px 7px', borderRadius: 999,
                  color: known ? 'var(--success)' : 'var(--fg-3)', background: known ? 'var(--success-bg)' : 'var(--bg-3)' }}>
                  {basisLabel}
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

