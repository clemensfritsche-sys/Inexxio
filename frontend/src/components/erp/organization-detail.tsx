'use client';

import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Building2, FolderOpen, Star, Pencil, Ban, Users, RotateCcw, MessagesSquare, HandCoins } from 'lucide-react';
import { Communication } from '@/components/erp/communication';
import { api } from '@/lib/api';
import { qk } from '@/lib/queries';
import type { CompanySettings, CompanySettingsUpdate, Todo } from '@/types';
import { DetailTabs } from '@/components/erp/detail-tabs';
import { DetailBody, Card, DetailHeader, SectionSep, TodoAt } from '@/components/erp/detail-frame';
import { Segmented } from '@/components/erp/controls';
import { DocumentTiles } from '@/components/erp/documents';
import { LegalTexts } from '@/components/erp/legal-texts';
import { CompanyTime } from '@/components/erp/time/company-time';
import { sectionItems } from '@/lib/todo';
import { organizationStatus } from '@/lib/record-status';
import { organizationName } from '@/lib/record-name';
import { AddressField, type Address, hasAddress, toIso2 } from '@/components/erp/address-field';
import { legalForms } from '@/lib/legal-forms';
import { useMapsApiKey } from '@/lib/use-maps-key';
import { Field as AField, Select } from '@/components/form/field';
import { useAutosaveValue } from '@/lib/use-autosave';
import { SaveStatusIndicator } from '@/components/form/save-status';
import { TerritoryMap } from '@/components/erp/territory-map';
import { ObjId } from '@/components/erp/obj-id';
import { PAYMENTS_TIP, PaymentList, usePayments } from '@/components/erp/payment-list';
import { useAction } from '@/lib/use-action';

// Das Land als Klarname (`toIso2` in address-field.tsx); breiter als bei einer Personenadresse.
const COMPANY_COUNTRIES: [string, string][] = [
  ['Schweiz', 'Schweiz'], ['Deutschland', 'Deutschland'], ['Österreich', 'Österreich'],
  ['Frankreich', 'Frankreich'], ['Italien', 'Italien'], ['Liechtenstein', 'Liechtenstein'],
  ['USA', 'USA'], ['Grossbritannien', 'Grossbritannien'], ['Spanien', 'Spanien'],
  ['Niederlande', 'Niederlande'], ['Belgien', 'Belgien'], ['Luxemburg', 'Luxemburg'],
  ['Portugal', 'Portugal'], ['Irland', 'Irland'],
];

// Währungen + Vorschlag Land→Währung über ISO-2 (Spiegel von services/sites._COUNTRY_CURRENCY;
// nur ein Vorschlag beim Länderwechsel).
const CURRENCIES = ['CHF', 'EUR', 'USD', 'GBP'];

/** Die Art einer Firma – ein Schieber, keine Auswahlliste (zwei Werte sieht man). */
export const OWN_OPTIONS = [{ value: 'foreign', label: 'Extern' }, { value: 'own', label: 'Eigen' }];
const CURRENCY_BY_ISO2: Record<string, string> = {
  CH: 'CHF', LI: 'CHF', US: 'USD', GB: 'GBP',
  DE: 'EUR', AT: 'EUR', FR: 'EUR', IT: 'EUR', ES: 'EUR', NL: 'EUR', BE: 'EUR', LU: 'EUR',
  PT: 'EUR', IE: 'EUR', FI: 'EUR',
};
function suggestCurrency(country: string | undefined): string | undefined {
  return CURRENCY_BY_ISO2[toIso2(country)];
}

/**
 * **Steuerliche Kennungen je Land** – gefragt wird nur, was es dort gibt (`vat: null` =
 * keine MWST, das Feld entfällt). Kein Eintrag → Steuernummer, USt-Nummer optional.
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
  // Keine bundesweite Mehrwertsteuer – das Feld entfällt.
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

/** «Musterstrasse 12» → ('Musterstrasse', '12') – das Unternehmen führt beides getrennt. */
function splitStreet(line: string): [string, string] {
  const m = line.trim().match(/^(.*?)[\s,]+(\d+[a-zA-Z]?)$/);
  return m ? [m[1].trim(), m[2]] : [line.trim(), ''];
}

type OrgTab = 'stamm' | 'pay' | 'docs' | 'comm';

/** Das Formular – nur die Felder, die es noch gibt (alles String, wie im Konto). */
interface OrgForm {
  company_name: string;
  legal_form: string;
  street: string;
  street_nr: string;
  zip_code: string;
  city: string;
  country: string;
  currency: string;
  uid_number: string;
  vat_number: string;
  phone: string;
  iban: string;
}

function buildForm(s: CompanySettings): OrgForm {
  return {
    company_name: s.company_name ?? '',
    legal_form: s.legal_form ?? '',
    street: s.street ?? '',
    street_nr: s.street_nr ?? '',
    zip_code: s.zip_code ?? '',
    city: s.city ?? '',
    country: s.country || 'Schweiz',
    currency: s.currency || 'CHF',
    uid_number: s.uid_number ?? '',
    vat_number: s.vat_number ?? '',
    phone: s.phone ?? '',
    iban: s.iban ?? '',
  };
}

const nn = (s: string): string | null => (s.trim() === '' ? null : s);

/**
 * Detailansicht eines **Unternehmens** – EIN Formular, EIN Auto-Save, für JEDE Gesellschaft
 * derselbe Feldsatz (kein «Hauptsitz»). **Wenige Felder, dafür Pflicht**: nur was ein Beleg,
 * das Impressum oder eine Regel nennt; die Währung folgt dem Land, die Website dem Deployment.
 */
export function OrganizationDetail({ record, isAdmin, onSaved, onBack, todo }: {
  record: CompanySettings;
  /** Was zu tun ist – die Zahl am Symbol (fehlende Feiertage). */
  todo?: Todo | null;
  /** Eine **eigene** Gesellschaft ändert nur ein Admin; eine fremde jedes Personal. */
  isAdmin: boolean;
  onSaved: (s: CompanySettings) => void;
  onBack: () => void;
}) {
  // ►►► **Der Datensatz ist eine Query, das Formular nicht** – es wird EINMAL befüllt; ein
  // anderer Datensatz ist ein neues Bauteil (`key`). ◄◄◄
  const qc = useQueryClient();
  const objectId = record.object_id ?? 0;
  const base = useQuery({
    queryKey: qk.company(objectId),
    queryFn: ({ signal }) => api.getCompany(objectId, { signal }),
    initialData: record,
    enabled: record.object_id != null,
    meta: { what: 'Gesellschaft' },
  }).data;
  const setBase = (c: CompanySettings) => qc.setQueryData(qk.company(objectId), c);
  const [form, setForm] = useState<OrgForm>(() => buildForm(record));
  const [tab, setTab] = useState<OrgTab>('stamm');
  // Eigen ↔ fremd, Betreiber, Schliessen: eine Handlung zur Zeit, ein Satz bei einem Fehler.
  const { busy: opBusy, error: opError, run } = useAction('Nicht möglich');
  const [currencyOpen, setCurrencyOpen] = useState(false);
  const mapsKey = useMapsApiKey();

  const isOperator = !!base.is_operator;
  // ►►► **Eigen oder fremd** – Bank, Währung, Gebiete und Betreiber nur bei einer eigenen.
  const own = !!base.is_own;
  const canEdit = isAdmin || !own;

  const { status, errorMsg, saveNow } = useAutosaveValue(
    form,
    async (v) => {
      if (record.object_id == null || !canEdit) return;
      // Ein leerer Name wird nicht gesendet (das Feld markiert ihn als fehlend).
      if (!v.company_name.trim()) return;
      // ►►► **Eine fremde Firma ist ihre Identität** – Name, Rechtsform, UID (`sites.EXTERNAL_FIELDS`).
      const data: CompanySettingsUpdate = {
        company_name: v.company_name.trim(),
        legal_form: nn(v.legal_form),
        uid_number: nn(v.uid_number),
      };
      // Auch leer gesendet – sonst ginge ein absichtliches Löschen verloren.
      if (own) {
        Object.assign(data, {
          street: v.street, street_nr: nn(v.street_nr),
          zip_code: v.zip_code, city: v.city, country: v.country,
          vat_number: nn(v.vat_number), phone: nn(v.phone),
          iban: nn(v.iban), currency: v.currency,
        });
      }
      const updated = await api.updateCompany(record.object_id, data);
      setBase(updated);
      onSaved(updated);
    },
  );

  const str = (k: keyof OrgForm) => (val: string) => setForm((p) => ({ ...p, [k]: val }));

  // Die Adresse ist EIN Feld; Strasse/Nummer werden getrennt, die Währung vorgeschlagen.
  function applyCompanyAddress(a: Address) {
    const [street, nr] = splitStreet(a.street);
    const suggested = suggestCurrency(a.country);
    setForm((prev) => ({
      ...prev, street, street_nr: nr, zip_code: a.zip, city: a.city, country: a.country,
      ...(suggested ? { currency: suggested } : {}),
    }));
  }

  /** «Eigenes Unternehmen» umschalten – nur ein Admin; der Dienst weist ab, wo etwas
   *  daran hängt (Betreiber, Personal). */
  const apply = (call: (id: number) => Promise<CompanySettings>) => {
    const id = record.object_id;
    if (id == null) return;
    return run(async () => {
      const updated = await call(id);
      setBase(updated);
      onSaved(updated);   // Eltern-Feed lädt die Liste neu → alter Betreiber verliert den Titel
    });
  };
  const setOwn = (next: boolean) => apply((id) => api.updateCompany(id, { is_own: next }));

  /** Diese Gesellschaft zum Betreiber der Website machen (genau eine trägt den Titel). */
  const makeOperator = () => apply((id) => api.setCompanyOperator(id));

  /** Schliessen ↔ wieder öffnen – ein Klick, umkehrbar (keine Rückfrage nötig). */
  const toggleClosed = () => apply((id) => (base.is_active === false
    ? api.reopenCompany(id) : api.deactivateCompany(id)));

  const address: Address = {
    street: [form.street, form.street_nr].filter(Boolean).join(' '),
    zip: form.zip_code, city: form.city, country: form.country,
  };
  const forms = legalForms(form.country);
  const ids = taxIds(form.country);
  const derivedCurrency = suggestCurrency(form.country);
  const saveIndicator = <SaveStatusIndicator status={status} errorMsg={errorMsg} />;

  return (
    <div className="flex flex-col h-full">
      <DetailHeader
        // Der Name trägt die Rechtsform – fertig vom Server (`sites.legal_name`).
        type="organization" title={organizationName(base)}
        objectId={record.object_id} onBack={onBack} todo={todo}
        // Der Zustand, nicht der Typ: Freigegeben · Inaktiv.
        status={organizationStatus(record)}
        // **Betreiber der Website: ein Stern in der Kopfzeile** – eine Rolle, keine Angabe.
        // Gesetzt: Tatsache; nicht gesetzt: leiser Knopf.
        actions={<>
          {own && isAdmin && (isOperator ? (
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
          ))}
          {/* Schliessen ↔ öffnen, ohne Rückfrage; nicht am Betreiber (die Website braucht ihn). */}
          {!isOperator && canEdit && (base.is_active === false ? (
            <button className="erp-idbtn"
              data-tip="Unternehmen wieder öffnen" data-tip-pos="bottom"
              aria-label="Unternehmen wieder öffnen"
              onClick={toggleClosed} disabled={opBusy}>
              <RotateCcw size={14} />
            </button>
          ) : (
            <button className="erp-idbtn erp-idbtn-danger"
              data-tip="Unternehmen schliessen – lässt sich wieder öffnen" data-tip-pos="bottom"
              aria-label="Unternehmen schliessen"
              onClick={toggleClosed} disabled={opBusy}>
              <Ban size={14} />
            </button>
          ))}
        </>}
        tabs={<DetailTabs<OrgTab> active={tab} onChange={setTab} tabs={[
          { key: 'stamm', label: 'Stammdaten', icon: Building2 },
          ...(own ? [{ key: 'pay' as const, label: 'Zahlungen', icon: HandCoins }] : []),
          { key: 'docs', label: 'Dokumente', icon: FolderOpen },
          { key: 'comm', label: 'Verlauf', icon: MessagesSquare },
        ]} />}
      />


      {/* Content */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '16px 20px 40px', background: 'var(--bg-2)' }}>
        {tab === 'comm' && record.object_id != null && (
          <DetailBody><Communication company={record.object_id} ownCompany={own} /></DetailBody>
        )}
        {tab === 'pay' && own && record.object_id != null && (
          <CompanyPayments company={record.object_id} name={organizationName(base)} />
        )}
        {tab === 'stamm' && (
        <fieldset disabled={!canEdit} style={{ border: 0, padding: 0, margin: 0, minWidth: 0 }}>
        <DetailBody gap={16}>
          {/* ── 1. Allgemeine Angaben ────────────────────────────────────────── */}
          <Card title="Allgemeine Angaben" right={saveIndicator}>
            {/* «Extern ↔ Eigen» – eine Admin-Entscheidung; alle anderen sehen sie gesperrt. */}
            <Segmented value={own ? 'own' : 'foreign'} disabled={!isAdmin || opBusy}
              tip={isAdmin ? undefined : 'Ob eine Firma eine unserer Gesellschaften ist, legt ein Admin fest.'}
              onChange={(v) => void setOwn(v === 'own')}
              options={OWN_OPTIONS} />
            <AField name="company_name" label="Unternehmensname" value={form.company_name} onChange={str('company_name')}
              placeholder="Inexxio AG" required onEnter={saveNow} />

            {/* Rechtsform: Freitext mit Vorschlägen aus dem Land. */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
              <AField name="legal_form" label="Rechtsform" value={form.legal_form} onChange={str('legal_form')}
                placeholder={forms[0] ?? 'AG'} required onEnter={saveNow} list="legal-forms" />
              <datalist id="legal-forms">
                {forms.map((f) => <option key={f} value={f} />)}
              </datalist>
            </div>

            {/* Die Kennungen gehören zur Rechtsperson – gefragt wird, was es im Land gibt. */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <AField name="uid_number" label={ids.uid.label} value={form.uid_number} onChange={str('uid_number')}
                placeholder={ids.uid.ph} required={own} onEnter={saveNow} />
              {own && ids.vat && (
                <AField name="vat_number" label={ids.vat.label} value={form.vat_number} onChange={str('vat_number')}
                  placeholder={ids.vat.ph} required onEnter={saveNow} />
              )}
            </div>
            {/* Anschrift, Kontakt und Bank nur an einer EIGENEN Gesellschaft. */}
            {own && <div>
              <AddressField value={address} onChange={applyCompanyAddress} apiKey={mapsKey}
                countryOptions={COMPANY_COUNTRIES} label="Anschrift" required />
              {/* Ohne Anschrift bleibt eine Bewegung hierher innerbetrieblich (ADR 005). */}
              {!hasAddress(address) && (
                <p style={{ font: '500 12px var(--font-body)', color: 'var(--warning)', margin: '6px 0 0' }}>
                  Ohne Anschrift zählt eine Bewegung hierher als innerbetrieblich – kein Versand.
                </p>
              )}
            </div>}

            {/* Währung – abgeleitet aus dem Land; erst «Ändern» macht daraus ein Feld. */}
            {own && (currencyOpen ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                <label style={{ fontSize: 13, fontWeight: 500, color: 'var(--fg-2)' }}>Währung</label>
                <Select name="currency" value={form.currency} onChange={str('currency')}
                  style={{ padding: '8px 12px', borderRadius: 8, border: '1px solid var(--border-1)',
                           fontSize: 14, color: 'var(--fg-1)', background: 'var(--bg-1)', outline: 'none',
                           width: '100%', boxSizing: 'border-box', cursor: 'pointer' }}>
                  {CURRENCIES.map((c) => <option key={c} value={c}>{c}</option>)}
                </Select>
              </div>
            ) : (
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <div style={{ minWidth: 0 }}>
                  <div style={{ fontSize: 13, fontWeight: 500, color: 'var(--fg-2)' }}>Währung</div>
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
            ))}

            {opError && (
              <p style={{ font: '500 12px var(--font-body)', color: 'var(--danger)', margin: 0 }}>{opError}</p>
            )}
          </Card>

          {/* ── 2. Kontakt ───────────────────────────────────────────────────── */}
          {own && <Card title="Kontakt">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {/* Die Kontakt-E-Mail IST das Postfach: gesetzt durch «Verbinden», geleert durch «Trennen». */}
              <AField name="email" label="E-Mail" value={base.email ?? ''} readOnly
                placeholder="Postfach unter «Kommunikation» verbinden" />
              {own && (
                <AField name="phone" label="Telefon" value={form.phone} onChange={str('phone')} type="tel"
                  placeholder="+41 44 000 00 00" required onEnter={saveNow} />
              )}
            </div>
            {/* Website: abgeleitet aus dem Deployment, nicht editierbar. */}
            {own && <AField name="website" label="Website" value={base.website ?? ''} readOnly />}
          </Card>}

          {/* ── 4. Bankverbindung ────────────────────────────────────────────── */}
          {/* EINE Zahl: die IBAN (liest auch die QR-Rechnung, `services/qrbill`). */}
          {own && (<>
          <Card title="Bankverbindung">
            <AField name="iban" label="IBAN" value={form.iban} onChange={str('iban')}
              placeholder="CH00 0000 0000 0000 0000 0"
              required onEnter={saveNow} />
          </Card>

          {/* ── 5. Gebiete (Weltkarte) ───────────────────────────────────────── */}
          {/* Die Karte ist global und hebt diese Gesellschaft hervor. */}
          <Card title="Gebiete">
            <TerritoryMap highlight={record.object_id} embedded />
          </Card>
          {record.object_id != null && (
            <TodoAt part="dokumente" objectId={record.object_id}>
              <LegalTexts company={record.object_id} isAdmin={isAdmin} />
            </TodoAt>
          )}
          </>)}

          {/* ►►► **Wer gehört zu dieser Firma?** – abgeleitet aus der Zuordnung an der
              Person; gepflegt wird sie dort. */}
          <Card icon={Users} title="Personen">
            {(base.people ?? []).length === 0 ? (
              <span className="text-sm text-fg-3">Keine Personen zugeordnet.</span>
            ) : (
              <div className="flex flex-col">
                {(base.people ?? []).map((p) => (
                  <div key={p.object_id}
                    className="flex items-center gap-3 py-1.5 border-b border-border-1 last:border-b-0 text-sm">
                    <ObjId value={p.object_id} />
                    <span className="text-fg-1 truncate">{p.name}</span>
                    <span className="text-fg-3 truncate ml-auto">{p.email}</span>
                  </div>
                ))}
              </div>
            )}
          </Card>
          <DocumentTiles objectId={record.object_id} />
        </DetailBody>
        </fieldset>
        )}
        {/* ►►► **Zeiterfassung der Gesellschaft** – ganz unten in den Stammdaten, nur für
            eine eigene und nur für den Admin (Feiertage, Nachweise, Regeln). */}
        {tab === 'stamm' && own && isAdmin && record.object_id != null && (
          <div style={{ marginTop: 24 }}>
            <DetailBody gap={24}>
              <SectionSep label="Zeiterfassung" anchor="feiertage" todo={sectionItems(todo, 'feiertage')} />
              <CompanyTime company={record.object_id} todo={sectionItems(todo, 'feiertage')} />
            </DetailBody>
          </div>
        )}
      </div>
    </div>
  );
}


/**
 * ►►► **Alle Zahlungen einer eigenen Gesellschaft** – dieselbe Liste wie an der Person, mit
 * der Partei je Zeile. Eine Ableitung aus den Zahlungsmodulen, keine eigene Liste.
 */
function CompanyPayments({ company, name }: { company: number; name: string | null }) {
  const rows = usePayments({ company });
  return (
    <DetailBody gap={16}>
      <SectionSep label={name ? `Alle Zahlungen der ${name}` : 'Alle Zahlungen'} tip={PAYMENTS_TIP} />
      {rows == null ? null : rows.length > 0 ? (
        <PaymentList rows={rows} withParty />
      ) : (
        <p style={{ color: 'var(--fg-3)', fontSize: 13, margin: 0 }}>
          Noch keine Zahlungen in ihrem Namen.
        </p>
      )}
    </DetailBody>
  );
}
