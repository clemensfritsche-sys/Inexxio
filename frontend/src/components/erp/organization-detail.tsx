'use client';

import { useEffect, useRef, useState } from 'react';
import { Building2, Server, Sparkles, CreditCard, Coins, FolderOpen, Star, Pencil, Ban } from 'lucide-react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { api } from '@/lib/api';
import type {CompanySettings } from '@/types';
import { DetailTabs } from '@/components/erp/detail-tabs';
import { Card, ChoiceButton, DetailHeader, Dialog } from '@/components/erp/fields';
import { organizationStatus } from '@/lib/record-status';
import { AddressField, type Address, hasAddress, toIso2 } from '@/components/erp/address-field';
import { useMapsApiKey } from '@/components/erp/use-maps-key';
import { Field as AField } from '@/components/account/field';
import { useAutosave } from '@/components/account/use-autosave';
import { SaveStatusIndicator } from '@/components/account/save-status';
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

/**
 * **Rechtsformen je Land** (Testnotiz #303) – Vorschläge, keine Auswahlliste.
 *
 * Eine brauchbare API dafür gibt es nicht: die einzige verbindliche Quelle ist die
 * ISO-20275-Liste der GLEIF («Entity Legal Forms»), ein Download mit ~2600 Einträgen ohne
 * Abfrage-Endpunkt – für eine Vorbelegung von acht Zeilen der falsche Preis. Die Liste ist
 * ausserdem träge (Rechtsformen ändern sich in Jahrzehnten, nicht in Wochen), also ist sie
 * hier richtig aufgehoben – genau wie die Land→Währung-Zuordnung darüber.
 *
 * Es bleibt ein **Freitextfeld** mit `datalist`: die Vorschläge decken den Normalfall,
 * jede Exotik (Anstalt, SCE, Zweigniederlassung) bleibt tippbar.
 */
const LEGAL_FORMS_BY_ISO2: Record<string, string[]> = {
  CH: ['AG', 'GmbH', 'Einzelunternehmen', 'Kollektivgesellschaft', 'Kommanditgesellschaft',
       'Genossenschaft', 'Verein', 'Stiftung', 'Zweigniederlassung'],
  LI: ['AG', 'GmbH', 'Anstalt', 'Stiftung', 'Treuunternehmen'],
  DE: ['GmbH', 'UG (haftungsbeschränkt)', 'AG', 'GmbH & Co. KG', 'KG', 'OHG', 'e.K.', 'GbR', 'eG', 'e.V.'],
  AT: ['GmbH', 'AG', 'OG', 'KG', 'e.U.', 'Genossenschaft'],
  US: ['Inc.', 'LLC', 'Corp.', 'LP', 'LLP', 'Sole Proprietorship'],
  GB: ['Ltd', 'PLC', 'LLP', 'Sole Trader'],
  FR: ['SARL', 'SAS', 'SASU', 'SA', 'EURL', 'SCI'],
  IT: ['S.r.l.', 'S.p.A.', 'S.n.c.', 'S.a.s.', 'Ditta individuale'],
  ES: ['S.L.', 'S.A.', 'Autónomo'],
  NL: ['B.V.', 'N.V.', 'Eenmanszaak', 'V.O.F.'],
  BE: ['BV', 'NV', 'VOF', 'CommV'],
  LU: ['S.à r.l.', 'S.A.', 'SCS'],
  PT: ['Lda.', 'S.A.', 'Unipessoal Lda.'],
  IE: ['Ltd', 'PLC', 'DAC', 'Sole Trader'],
};
function legalForms(country: string | undefined): string[] {
  return LEGAL_FORMS_BY_ISO2[toIso2(country)] ?? [];
}

/**
 * **Steuerliche Kennungen je Land** (Testnotiz #346) – gefragt wird nur, was es dort gibt.
 *
 * Dieselbe Bauart und derselbe Grund wie bei den Rechtsformen: eine Abfrage-API dafür
 * existiert nicht (die EU führt mit VIES nur eine *Prüfung* bestehender USt-IdNrn, keine
 * Auskunft darüber, welche Kennungen ein Land überhaupt kennt), und die Angaben sind
 * träge. Eine kleine, dokumentierte Tabelle ist hier ehrlicher als ein Fremdsystem.
 *
 * Der eigentliche Gewinn ist nicht die Beschriftung, sondern das **Weglassen**: die USA
 * kennen keine Mehrwertsteuer – dort nach einer «MWST-Nummer» zu fragen (und sie als
 * Pflichtfeld zu markieren) verlangt eine Angabe, die es nicht gibt. Fehlt ein Eintrag,
 * gilt der neutrale Standard: eine Steuernummer, USt-Nummer optional.
 */
type TaxIds = { uid: { label: string; ph: string }; vat: { label: string; ph: string } | null };
const TAX_IDS_BY_ISO2: Record<string, TaxIds> = {
  CH: { uid: { label: 'UID', ph: 'CHE-123.456.789' },
        vat: { label: 'MWST-Nummer', ph: 'CHE-123.456.789 MWST' } },
  LI: { uid: { label: 'UID', ph: 'FL-0002.123.456-7' },
        vat: { label: 'MWST-Nummer', ph: '12345' } },
  DE: { uid: { label: 'Steuernummer', ph: '12/345/67890' },
        vat: { label: 'USt-IdNr.', ph: 'DE123456789' } },
  AT: { uid: { label: 'Firmenbuchnummer', ph: 'FN 123456a' },
        vat: { label: 'UID-Nummer', ph: 'ATU12345678' } },
  // Keine bundesweite Mehrwertsteuer – Sales Tax wird je Bundesstaat erhoben und hat
  // keine landesweite Nummer. Darum entfällt das Feld ganz, statt leer zu bleiben.
  US: { uid: { label: 'EIN', ph: '12-3456789' }, vat: null },
  GB: { uid: { label: 'Company number', ph: '12345678' },
        vat: { label: 'VAT number', ph: 'GB123456789' } },
  FR: { uid: { label: 'SIREN', ph: '123456789' },
        vat: { label: 'Numéro de TVA', ph: 'FR12345678901' } },
  IT: { uid: { label: 'Codice fiscale', ph: '12345678901' },
        vat: { label: 'Partita IVA', ph: 'IT12345678901' } },
  ES: { uid: { label: 'NIF', ph: 'B12345678' },
        vat: { label: 'NIF-IVA', ph: 'ESB12345678' } },
  NL: { uid: { label: 'KvK-nummer', ph: '12345678' },
        vat: { label: 'Btw-nummer', ph: 'NL123456789B01' } },
};
const TAX_IDS_DEFAULT: TaxIds = {
  uid: { label: 'Steuernummer', ph: '' },
  vat: { label: 'USt-Nummer (optional)', ph: '' },
};
function taxIds(country: string | undefined): TaxIds {
  return TAX_IDS_BY_ISO2[toIso2(country)] ?? TAX_IDS_DEFAULT;
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

/** Das Formular – nur die Felder, die es noch gibt (alles String, wie im Konto). */
interface OrgForm {
  company_name: string;
  legal_form: string;
  street: string;
  street_number: string;
  zip: string;
  city: string;
  country: string;
  currency: string;
  uid: string;
  vat_number: string;
  email: string;
  phone: string;
  iban: string;
}

function buildForm(s: CompanySettings): OrgForm {
  return {
    company_name: s.company_name ?? '',
    legal_form: s.legal_form ?? '',
    street: s.street ?? '',
    street_number: s.street_number ?? '',
    zip: s.zip ?? '',
    city: s.city ?? '',
    country: s.country || 'Schweiz',
    currency: s.currency || 'CHF',
    uid: s.uid ?? '',
    vat_number: s.vat_number ?? '',
    email: s.email ?? '',
    phone: s.phone ?? '',
    iban: '',                                  // die echte IBAN kommt nie zurück (maskiert)
  };
}

const nn = (s: string): string | null => (s.trim() === '' ? null : s);

/**
 * Detailansicht eines **Unternehmens** (einer Gesellschaft) – ein gleichrangiger
 * ERP-Datensatz in derselben Anatomie wie Benutzer und Profil: EIN Formular, EIN
 * Auto-Save (Testnotiz #312), Karten statt Sektionsraster, Pflichtfelder markiert.
 *
 * **Ein Fenster, ein Feldsatz – für JEDE Gesellschaft gleich.** Jede trägt ihre eigene,
 * vollständige Rechtsidentität (die US-Gesellschaft hat ihre eigene EIN/Steuer/Bank). Es
 * gibt keinen «Hauptsitz» mit mehr Feldern und keinen kastrierten «Standort».
 *
 * **Wenige Felder, dafür Pflicht** (Testnotizen #301/#305/#307/#310/#313/#314/#317–#321,
 * #323). Der Massstab war nicht «könnte man mal brauchen», sondern: *nennt es jemand auf
 * einem Beleg, im Impressum oder in einer Regel?* Neun Angaben bleiben – und weil es neun
 * sind, dürfen sie Pflicht sein. Zwei davon füllt das System selbst: die **Währung** folgt
 * dem Land (#304) und die **Website-Adresse** dem Deployment (#309).
 *
 * Die **Plattform-/Systemkonfiguration** (Stripe, Shop, Rechtstexte) gilt der EINEN
 * Website, nicht je Gesellschaft – sie steht im Reiter «System» am **Betreiber**.
 */
export function OrganizationDetail({ record, onSaved, onBack }: {
  record: CompanySettings;
  onSaved: (s: CompanySettings) => void;
  onBack: () => void;
}) {
  // Frisch nachgeladener Datensatz (der Feed liefert schon den vollen Satz, aber beim
  // Öffnen holen wir ihn erneut – Bank maskiert, abgeleitete Felder aktuell).
  const [base, setBase] = useState<CompanySettings>(record);
  const [form, setForm] = useState<OrgForm>(() => buildForm(record));
  const [resetKey, setResetKey] = useState(0);
  const [tab, setTab] = useState<OrgTab>('stamm');
  const [opBusy, setOpBusy] = useState(false);
  const [opError, setOpError] = useState<string | null>(null);
  const [closing, setClosing] = useState(false);
  const [closeBusy, setCloseBusy] = useState(false);
  const [currencyOpen, setCurrencyOpen] = useState(false);
  const mapsKey = useMapsApiKey();
  const prevId = useRef<number | null | undefined>(undefined);

  const isOperator = !!base.is_operator;

  // Nur bei Datensatz-WECHSEL neu aufbauen – sonst klobbert ein Auto-Save → onSaved →
  // neuer Prop die gerade getippte Eingabe (dieselbe Regel wie im Benutzer-Datensatz).
  useEffect(() => {
    if (record.object_id === prevId.current) return;
    prevId.current = record.object_id;
    setBase(record);
    setForm(buildForm(record));
    setResetKey((k) => k + 1);
    setTab('stamm');
    setCurrencyOpen(false);
    setOpError(null);
    if (record.object_id != null) {
      api.getCompany(record.object_id).then((fresh) => {
        if (record.object_id !== prevId.current) return;
        setBase(fresh);
        setForm(buildForm(fresh));
        setResetKey((k) => k + 1);
      }).catch(() => undefined);
    }
  }, [record]);

  const { status, errorMsg, saveNow } = useAutosave(
    form,
    async (v) => {
      if (record.object_id == null) return;
      // Ein leerer Name ist kein speicherbarer Zustand (er ist zugleich das Halter-Label) –
      // das Feld markiert ihn als fehlend, gesendet wird er nicht. Das Backend weist ihn
      // ebenfalls ab; hier ersparen wir dem Tippenden die Fehlermeldung nach jedem Zeichen.
      if (!v.company_name.trim()) return;
      const data: Partial<CompanySettings> = {
        company_name: v.company_name.trim(),
        legal_form: nn(v.legal_form),
        street: v.street, street_number: nn(v.street_number),
        zip: v.zip, city: v.city, country: v.country,
        currency: v.currency,
        uid: nn(v.uid), vat_number: nn(v.vat_number),
        email: v.email, phone: nn(v.phone),
      };
      // Die IBAN wird nur gesendet, wenn sie neu eingegeben wurde (sonst überschriebe der
      // maskierte Platzhalter die echte Nummer).
      if (v.iban.trim()) data.iban = v.iban.trim();
      const updated = await api.updateCompany(record.object_id, data);
      setBase(updated);
      onSaved(updated);
    },
    2500,
    resetKey,
  );

  const str = (k: keyof OrgForm) => (val: string) => setForm((p) => ({ ...p, [k]: val }));

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
  }

  /** Diese Gesellschaft zum Betreiber der Website machen (genau eine trägt den Titel). */
  async function makeOperator() {
    if (record.object_id == null) return;
    setOpBusy(true); setOpError(null);
    try {
      const updated = await api.setCompanyOperator(record.object_id);
      setBase(updated);
      onSaved(updated);   // Eltern-Feed lädt die Liste neu → alter Betreiber verliert den Titel
    } catch (e) {
      setOpError(e instanceof Error ? e.message : 'Betreiber konnte nicht gesetzt werden');
    } finally { setOpBusy(false); }
  }

  /** Diese Gesellschaft schliessen – endgültig (keine Reaktivierung, siehe Backend). */
  async function closeCompany() {
    if (record.object_id == null) return;
    setCloseBusy(true); setOpError(null);
    try {
      const updated = await api.deactivateCompany(record.object_id);
      setBase(updated);
      onSaved(updated);
      setClosing(false);
    } catch (e) {
      setOpError(e instanceof Error ? e.message : 'Unternehmen konnte nicht geschlossen werden');
      setClosing(false);
    } finally { setCloseBusy(false); }
  }

  const address: Address = {
    street: [form.street, form.street_number].filter(Boolean).join(' '),
    zip: form.zip, city: form.city, country: form.country,
  };
  const forms = legalForms(form.country);
  // Welche steuerlichen Kennungen dieses Land kennt (#346) – die USA z. B. keine MWST-Nr.
  const ids = taxIds(form.country);
  const derivedCurrency = suggestCurrency(form.country);
  const saveIndicator = <SaveStatusIndicator status={status} errorMsg={errorMsg} />;

  return (
    <div className="flex flex-col h-full">
      {/* Kopf – die EINE Anatomie aller Datensatz-Fenster (`DetailHeader`, Notiz #242).
          Für jede Gesellschaft gleich; kein «Hauptsitz»-Rang. */}
      <DetailHeader
        icon={Building2} iconBg="#F3E5DD" iconFg="#A65A3C"
        eyebrow="Unternehmen" title={form.company_name || null}
        objectId={record.object_id} onBack={onBack}
        // **Der Zustand, nicht der Typ** (Notiz #364): «Unternehmen» stand als Status da –
        // das ist aber die Datensatzart und steht bereits als Eyebrow. Ein Unternehmen kennt
        // dieselben zwei Zustände wie alles andere im System, also dieselben zwei Wörter:
        // **Freigegeben** (gültig, verwendbar) und **Inaktiv** (geschlossen, endgültig).
        status={organizationStatus(record)}
        // **Betreiber der Website: ein Stern bei den Aktionen** (Testnotiz #339) statt eines
        // Knopfes mitten im Formular. Er ist keine Stammdaten-Angabe, sondern eine Rolle über
        // dem Datensatz – also gehört er zur Kopfzeile, wo die übrigen Datensatz-Aktionen
        // stehen. Gesetzt: leuchtender Stern (Tatsache, kein Knopf). Nicht gesetzt: derselbe
        // Stern als leiser Knopf, Erklärung im Hover.
        actions={<>
          {isOperator ? (
            <span className="erp-idbtn erp-idbtn-flag" data-tip="Betreiber der Website – nennt das Impressum und trägt die Systemkonfiguration"
              data-tip-pos="bottom" style={{ cursor: 'default' }}>
              <Star size={14} fill="currentColor" />
            </span>
          ) : (
            <button className="erp-idbtn" data-tip={opBusy ? 'Wird gesetzt…' : 'Als Betreiber der Website festlegen'}
              data-tip-pos="bottom" aria-label="Als Betreiber der Website festlegen"
              onClick={makeOperator} disabled={opBusy}>
              <Star size={14} />
            </button>
          )}
          {/* **Schliessen** (Notiz #365) – wie das Deaktivieren am Artikel, und wie dort
              **endgültig**: eine wiedereröffnete Gesellschaft ist rechtlich eine andere
              (neue UID, neues HR-Datum), also wird sie neu angelegt statt wiederbelebt.
              Ein «Ersetzen» gibt es bewusst nicht – zu heikel bei einer Rechtsperson.
              Der Betreiber trägt den Knopf gar nicht erst: ohne ihn hätte die Website
              keinen Absender (erst den Stern weitergeben, dann schliessen). */}
          {!isOperator && record.is_active !== false && (
            <button className="erp-idbtn erp-idbtn-danger"
              data-tip="Unternehmen schliessen – endgültig, keine Reaktivierung"
              data-tip-pos="bottom" aria-label="Unternehmen schliessen"
              onClick={() => setClosing(true)} disabled={closeBusy}>
              <Ban size={14} />
            </button>
          )}
        </>}
        tabs={<DetailTabs<OrgTab> active={tab} onChange={setTab} tabs={[
          { key: 'stamm', label: 'Stammdaten', icon: Building2 },
          // Der System-Reiter (Plattform-Konfiguration der EINEN Website) erscheint nur am
          // Betreiber – es gibt ihn genau einmal.
          ...(isOperator ? [{ key: 'system' as const, label: 'System', icon: Server }] : []),
          { key: 'docs', label: 'Dokumente', icon: FolderOpen },
        ]} />}
      />

      {/* **Schliessen ist endgültig** – darum eine Frage, aber nur eine: der Klick auf den
          Weg IST die Ausführung (wie im Deaktivieren-Dialog des Artikels, Notiz #152). */}
      {closing && (
        <Dialog icon={Ban} title="Unternehmen schliessen" tone="var(--danger)" width={460}
          onClose={() => setClosing(false)}>
          <span style={{ font: '500 12.5px var(--font-body)', color: 'var(--fg-2)', lineHeight: 1.55 }}>
            «{form.company_name}» wird geschlossen. Der Datensatz bleibt lesbar (er hält
            historische Instanzen und steht auf alten Belegen), seine Gebiete fallen an den
            Betreiber zurück.
          </span>
          <ChoiceButton icon={Ban} tone="var(--danger)" disabled={closeBusy}
            title="Endgültig schliessen"
            text="Keine Reaktivierung – eine Wiedereröffnung ist rechtlich eine neue Gesellschaft (neue UID, neues HR-Datum) und wird neu angelegt."
            onClick={closeCompany} />
        </Dialog>
      )}

      {/* Content */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '16px 20px 40px', background: 'var(--bg-2)' }}>
        {tab === 'system' && isOperator && (
          <QueryClientProvider client={systemQueryClient}>
            <SystemConfigSection onSaved={(s) => onSaved({ ...base, ...s })} />
          </QueryClientProvider>
        )}
        {tab === 'stamm' && (
        <div style={{ maxWidth: 760, marginInline: 'auto', display: 'flex', flexDirection: 'column', gap: 16 }}>
          {/* ── 1. Allgemeine Angaben ────────────────────────────────────────── */}
          <Card title="Allgemeine Angaben" right={saveIndicator}>
            <AField label="Unternehmensname" value={form.company_name} onChange={str('company_name')}
              placeholder="Inexxio AG" required onEnter={saveNow} />

            {/* Rechtsform: Freitext mit Vorschlägen aus dem Land (#303). */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
              <AField label="Rechtsform" value={form.legal_form} onChange={str('legal_form')}
                placeholder={forms[0] ?? 'AG'} required onEnter={saveNow} list="legal-forms" />
              <datalist id="legal-forms">
                {forms.map((f) => <option key={f} value={f} />)}
              </datalist>
            </div>

            <div>
              <AddressField value={address} onChange={applyCompanyAddress} apiKey={mapsKey}
                countryOptions={COUNTRIES} label="Anschrift" required />
              {/* Eine Tatsache über DIESEN Datensatz: ohne eigene Anschrift bleibt eine
                  Bewegung hierher innerbetrieblich statt Versand zu werden (ADR 005). */}
              {!hasAddress(address) && (
                <p style={{ font: '500 12px var(--font-body)', color: 'var(--warning)', margin: '6px 0 0' }}>
                  Ohne Anschrift zählt eine Bewegung hierher als innerbetrieblich – kein Versand.
                </p>
              )}
            </div>

            {/* Währung – **abgeleitet** aus dem Land (#304). Änderbar, aber nicht beiläufig:
                erst der Klick auf «Ändern» macht daraus ein Feld. Wer bewusst abweicht
                (Holding fakturiert in EUR), kommt hin; niemand verstellt sie im Vorbeitippen. */}
            {currencyOpen ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                <label style={{ fontSize: 13, fontWeight: 500, color: '#374151' }}>Währung</label>
                <select value={form.currency} onChange={(e) => str('currency')(e.target.value)}
                  style={{ padding: '8px 12px', borderRadius: 8, border: '1px solid #E2E8F0',
                           fontSize: 14, color: '#0F172A', background: '#fff', outline: 'none',
                           width: '100%', boxSizing: 'border-box', cursor: 'pointer' }}>
                  {CURRENCIES.map((c) => <option key={c} value={c}>{c}</option>)}
                </select>
              </div>
            ) : (
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <div style={{ minWidth: 0 }}>
                  <div style={{ fontSize: 13, fontWeight: 500, color: '#374151' }}>Währung</div>
                  <div style={{ font: '600 14px var(--font-body)', color: 'var(--fg-1)', marginTop: 2 }}>
                    {form.currency}
                    {derivedCurrency === form.currency && (
                      <span style={{ font: '500 12px var(--font-body)', color: 'var(--fg-4)', marginLeft: 8 }}>
                        aus dem Land
                      </span>
                    )}
                  </div>
                </div>
                <button type="button" onClick={() => setCurrencyOpen(true)}
                  style={{ marginLeft: 'auto', display: 'inline-flex', alignItems: 'center', gap: 4,
                           font: '600 12px var(--font-body)', color: 'var(--accent)',
                           background: 'none', border: 'none', padding: 0, cursor: 'pointer' }}>
                  <Pencil size={12} /> Ändern
                </button>
              </div>
            )}

            {/* Der Betreiber-Schalter steht seit Notiz #339 als Stern in der Kopfzeile –
                er ist eine Rolle über dem Datensatz, keine Stammdaten-Angabe. Hier bleibt
                nur der Fehlerfall stehen, wo die Handlung ausgelöst wurde. */}
            {opError && (
              <p style={{ font: '500 12px var(--font-body)', color: 'var(--danger)', margin: 0 }}>{opError}</p>
            )}
          </Card>

          {/* ── 2. Rechtliche Identifikation ─────────────────────────────────── */}
          {/* Was die Gesellschaft ausweist: die Kennungen stehen auf dem Beleg-Briefkopf und
              im Impressum. Handelsregister-Nr./-Kanton und Aktienkapital sind entfallen
              (#307) – in der Schweiz IST die HR-Nummer seit 2016 die UID, der Kanton steht
              im Register, und Kapital ist nirgends vorgeschrieben.
              **Gefragt wird, was es im jeweiligen Land gibt** (#346): eine US-Gesellschaft
              hat eine EIN und keine MWST-Nummer – das Feld erscheint dort gar nicht. */}
          <Card title="Rechtliche Identifikation">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <AField label={ids.uid.label} value={form.uid} onChange={str('uid')}
                placeholder={ids.uid.ph} required onEnter={saveNow} />
              {ids.vat && (
                <AField label={ids.vat.label} value={form.vat_number} onChange={str('vat_number')}
                  placeholder={ids.vat.ph} required onEnter={saveNow} />
              )}
            </div>
          </Card>

          {/* ── 3. Kontakt ───────────────────────────────────────────────────── */}
          <Card title="Kontakt">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <AField label="E-Mail" value={form.email} onChange={str('email')} type="email"
                placeholder="info@inexxio.com" required onEnter={saveNow} />
              <AField label="Telefon" value={form.phone} onChange={str('phone')} type="tel"
                placeholder="+41 44 000 00 00" required onEnter={saveNow} />
            </div>
            {/* Website: **abgeleitet** aus dem Deployment (#309) – die Adresse, unter der
                diese Installation läuft. Angezeigt, weil sie im Impressum und auf dem
                Briefkopf steht; nicht editierbar, weil ein Eingabefeld daneben beim ersten
                Domain-Wechsel still falsch würde. */}
            {/* Ohne Hinweistext (#337): dass hier nichts einzugeben ist, sagt das Feld selbst
                (grau, nicht fokussierbar). */}
            <AField label="Website" value={base.website ?? ''} readOnly />
          </Card>

          {/* ── 4. Bankverbindung ────────────────────────────────────────────── */}
          {/* EINE Zahl: die IBAN trägt Land, Bank und Konto. QR-IBAN (die QR-Rechnung ist
              nicht gebaut), Bankname und BIC waren Abschriften daraus (#313). */}
          <Card title="Bankverbindung">
            <AField label="IBAN" value={form.iban} onChange={str('iban')}
              placeholder={base.iban_masked ?? 'CH00 0000 0000 0000 0000 0'}
              required={!base.iban_masked} onEnter={saveNow} />
          </Card>

          {/* ── 5. Gebiete (Weltkarte) ───────────────────────────────────────── */}
          {/* Welche Märkte diese Gesellschaft fakturiert, ist Stammdaten (#299). Die Karte
              ist global (alle Regionen/Gesellschaften) und hebt die aktuelle hervor. */}
          <Card title="Gebiete">
            <TerritoryMap highlight={record.object_id} embedded />
          </Card>
        </div>
        )}
      </div>
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

// Die Betriebskosten-Karte ist entfallen: sie summierte KI-Ereignisse und
// Stripe-Gebühren – beide Module sind abgeschaltet (core/features.py).
