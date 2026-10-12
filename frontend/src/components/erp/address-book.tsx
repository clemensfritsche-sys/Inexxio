'use client';

import { useEffect, useRef, useState } from 'react';
import { Plus, Trash2 } from 'lucide-react';
import { api } from '@/lib/api';
import { inheritedEmail } from '@/lib/accounts';
import { Field as AField } from '@/components/account/field';
import { AddressField, type Address } from '@/components/erp/address-field';
import { ErrorText } from '@/components/erp/fields';
import { useAutosave } from '@/components/account/use-autosave';
import { SaveStatusIndicator } from '@/components/account/save-status';
import type { AddressEntry, AddressInput, UserProfile } from '@/types';

/**
 * ►►► **Das Adressbuch einer Person – EIN Bauteil für Konto und ERP.** ◄◄◄
 *
 * Beliebig viele Anschriften (Wohnung, Büro, Lager, Baustelle), privat wie geschäftlich,
 * und je eine **Standard-Lieferadresse** und **Standard-Rechnungsadresse**. Wohin Ware und
 * Rechnung bei einem bestimmten Beleg gehen, entscheidet der Beleg; die Standards sind,
 * was gilt, wenn niemand etwas sagt.
 *
 * **Gespeichert, nicht abgeschickt**: eine neue Anschrift entsteht, sobald Strasse, PLZ
 * und Ort dastehen; eine bestehende speichert sich selbst. **Einen Standard nimmt man
 * nicht weg, man gibt ihn einer anderen** – darum ist der Punkt an der Standard-Anschrift
 * kein Schalter, sondern ein Zustand.
 *
 * Die Regel steht im Dienst (`services/address_book`); hier wird gezeichnet.
 */
export const ADDRESS_COUNTRIES: [string, string][] = [
  ['CH', 'Schweiz'], ['DE', 'Deutschland'], ['AT', 'Österreich'],
  ['FR', 'Frankreich'], ['IT', 'Italien'], ['LI', 'Liechtenstein'],
];

const DEFAULTS: { key: 'is_default_delivery' | 'is_default_billing'; label: string }[] = [
  { key: 'is_default_delivery', label: 'Lieferadresse' },
  { key: 'is_default_billing', label: 'Rechnungsadresse' },
];

export function AddressBook({ owner, addresses, loginEmail, readOnly, mapsKey, onSaved }: {
  /** `null` = die eigene Person (Konto), sonst ihre Objektnummer (ERP). */
  owner: number | null;
  addresses: AddressEntry[];
  loginEmail: string;
  readOnly?: boolean;
  mapsKey: string | null | undefined;
  onSaved: (u: UserProfile) => void;
}) {
  const [adding, setAdding] = useState(false);
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      {addresses.length === 0 && !adding && (
        <span className="text-sm text-fg-3">Keine Anschrift erfasst</span>
      )}
      {addresses.map((a) => (
        <AddressRow key={a.id} owner={owner} entry={a} loginEmail={loginEmail}
          readOnly={readOnly} mapsKey={mapsKey} onSaved={onSaved} />
      ))}
      {!readOnly && (adding ? (
        <NewAddress owner={owner} mapsKey={mapsKey}
          onSaved={(u) => { setAdding(false); onSaved(u); }}
          onCancel={() => setAdding(false)} />
      ) : (
        <button type="button" onClick={() => setAdding(true)}
          className="self-start inline-flex items-center gap-1.5 text-xs text-accent hover:underline">
          <Plus size={13} /> Anschrift hinzufügen
        </button>
      ))}
    </div>
  );
}

function toAddress(a: AddressEntry): Address {
  return { street: a.street1, street2: a.street2 ?? '', zip: a.zip, city: a.city,
           region: a.region ?? '', country: a.country };
}

function toInput(a: Address): AddressInput {
  return { street1: a.street, street2: a.street2 || null, zip: a.zip, city: a.city,
           region: a.region || null, country: a.country || 'CH' };
}

const complete = (a: Address) => !!(a.street.trim() && a.zip.trim() && a.city.trim());

function AddressRow({ owner, entry, loginEmail, readOnly, mapsKey, onSaved }: {
  owner: number | null; entry: AddressEntry; loginEmail: string; readOnly?: boolean;
  mapsKey: string | null | undefined; onSaved: (u: UserProfile) => void;
}) {
  const [form, setForm] = useState({ address: toAddress(entry), email: entry.email ?? '' });
  const [error, setError] = useState('');
  const { status, errorMsg, saveNow } = useAutosave(form, async (v) => {
    if (readOnly || !complete(v.address)) return;
    onSaved(await api.changeAddress(owner, entry.id,
      { ...toInput(v.address), email: v.email.trim() || null }));
  }, 1500);

  async function act(data: AddressInput | null) {
    setError('');
    try {
      onSaved(data ? await api.changeAddress(owner, entry.id, data)
        : await api.removeAddress(owner, entry.id));
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Nicht möglich.');
    }
  }

  return (
    <div className="ix-row rounded-ds-md border border-border-1 p-3 flex flex-col gap-3">
      <div className="flex items-center justify-between gap-2 flex-wrap">
        <div className="flex items-center gap-2 flex-wrap">
          {/* **Ein Standard ist ein Zustand, kein Schalter** – an der anderen Anschrift
              ist er die Handlung «diese wird es». */}
          {DEFAULTS.map(({ key, label }) => entry[key] ? (
            <span key={key} className="inline-flex items-center gap-1.5 text-xs font-semibold text-fg-1">
              <span style={{ width: 6, height: 6, borderRadius: 9, background: 'var(--accent)' }} />
              {label}
            </span>
          ) : !readOnly ? (
            <button key={key} type="button" className="text-xs text-fg-3 hover:text-accent hover:underline"
              onClick={() => void act({ [key]: true })}>
              Als {label}
            </button>
          ) : null)}
        </div>
        <div className="flex items-center gap-2">
          {!readOnly && <SaveStatusIndicator status={status} errorMsg={errorMsg} />}
          {!readOnly && (
            <button type="button" className="erp-actbtn erp-actbtn-icon" title="Anschrift entfernen"
              aria-label="Anschrift entfernen" onClick={() => void act(null)}>
              <Trash2 size={14} />
            </button>
          )}
        </div>
      </div>
      <fieldset disabled={readOnly} style={{ border: 0, padding: 0, margin: 0, minWidth: 0 }}
        className="flex flex-col gap-3">
        <AddressField value={form.address} apiKey={mapsKey} countryOptions={ADDRESS_COUNTRIES}
          showStreet2 showRegion label="Anschrift"
          onChange={(a) => setForm((p) => ({ ...p, address: a }))} />
        <AField label="Rechnungs-E-Mail" type="email" value={form.email} readOnly={readOnly}
          placeholder={inheritedEmail(loginEmail)} onEnter={saveNow}
          onChange={(v) => setForm((p) => ({ ...p, email: v }))} />
      </fieldset>
      {error && <ErrorText msg={error} />}
    </div>
  );
}

/** Eine neue Anschrift – sie entsteht, sobald Strasse, PLZ und Ort dastehen. */
function NewAddress({ owner, mapsKey, onSaved, onCancel }: {
  owner: number | null; mapsKey: string | null | undefined;
  onSaved: (u: UserProfile) => void; onCancel: () => void;
}) {
  const [draft, setDraft] = useState<Address>({ street: '', zip: '', city: '', country: 'CH' });
  const [error, setError] = useState('');
  const sent = useRef(false);
  // **Einmal, und erst vollständig** – ein Treffer der Adresssuche ist es sofort, eine
  // getippte Anschrift nach einer kurzen Pause (sonst entstünde sie beim ersten Buchstaben
  // des Orts).
  useEffect(() => {
    if (sent.current || !complete(draft)) return;
    const t = setTimeout(() => {
      sent.current = true;
      api.addAddress(owner, toInput(draft)).then(onSaved).catch((e) => {
        sent.current = false;
        setError(e instanceof Error ? e.message : 'Nicht möglich.');
      });
    }, 1200);
    return () => clearTimeout(t);
  }, [draft, owner, onSaved]);

  return (
    <div className="rounded-ds-md border border-border-1 p-3 flex flex-col gap-3">
      <AddressField value={draft} onChange={setDraft} apiKey={mapsKey}
        countryOptions={ADDRESS_COUNTRIES} showStreet2 showRegion label="Neue Anschrift" />
      <button type="button" className="self-start text-xs text-fg-3 hover:underline" onClick={onCancel}>
        Abbrechen
      </button>
      {error && <ErrorText msg={error} />}
    </div>
  );
}
