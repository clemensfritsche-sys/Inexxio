'use client';

import { useEffect, useRef, useState } from 'react';
import { Plus, Trash2 } from 'lucide-react';
import { api } from '@/lib/api';
import { inheritedEmail } from '@/lib/accounts';
import { Field as AField, ToggleField } from '@/components/account/field';
import { AddressField, type Address } from '@/components/erp/address-field';
import { ErrorText } from '@/components/erp/fields';
import { useAutosave } from '@/components/account/use-autosave';
import { SaveStatusIndicator } from '@/components/account/save-status';
import type { AddressEntry, AddressInput, UserProfile } from '@/types';

/**
 * ►►► **Die Anschriften EINES Kontos – dasselbe Bauteil für Privat und Geschäftskonto,
 * für Konto und ERP.** ◄◄◄
 *
 * Je Konto: eine **Adresse** (Hauptadresse = Rechnungsadresse), optional eine
 * **abweichende Lieferadresse** (Schalter) und optional **weitere Lieferadressen**
 * (unauffällig). Der einzige Unterschied zwischen den Konten: im **Geschäftskonto** steht
 * an der Adresse eine **Rechnungs-E-Mail** – privat geht die Rechnung an die E-Mail der
 * Person.
 *
 * **Der Schalter ist eine Ableitung**, keine gespeicherte Angabe: an ist er, wo eine eigene
 * Lieferadresse dasteht; «aus» entfernt sie, und geliefert wird wieder an die Adresse
 * (`address_book.remove` gibt den Titel an die Hauptadresse zurück).
 *
 * Die Regeln stehen im Dienst (`services/address_book`); hier wird gezeichnet.
 */
export const ADDRESS_COUNTRIES: [string, string][] = [
  ['CH', 'Schweiz'], ['DE', 'Deutschland'], ['AT', 'Österreich'],
  ['FR', 'Frankreich'], ['IT', 'Italien'], ['LI', 'Liechtenstein'],
];

export type Account = 'private' | 'business';

export function AddressBook({ owner, account, addresses, loginEmail, readOnly, mapsKey, onSaved }: {
  /** `null` = die eigene Person (Konto), sonst ihre Objektnummer (ERP). */
  owner: number | null;
  account: Account;
  addresses: AddressEntry[];
  loginEmail: string;
  readOnly?: boolean;
  mapsKey: string | null | undefined;
  onSaved: (u: UserProfile) => void;
}) {
  const mine = addresses.filter((a) => a.account === account);
  const main = mine.find((a) => a.is_default_billing) ?? null;
  const delivery = mine.find((a) => a.is_default_delivery && a.id !== main?.id) ?? null;
  const extra = mine.filter((a) => a.id !== main?.id && a.id !== delivery?.id);
  const business = account === 'business';
  // «An» geklickt, aber noch nichts getippt – das eine Gedächtnis, das der Schalter braucht.
  const [wantsDelivery, setWantsDelivery] = useState(false);
  const [addingExtra, setAddingExtra] = useState(false);
  const [error, setError] = useState('');
  const row = { owner, account, loginEmail, readOnly, mapsKey, onSaved };

  async function deliveryOff() {
    setWantsDelivery(false);
    if (!delivery) return;
    setError('');
    try {
      onSaved(await api.removeAddress(owner, delivery.id));
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Nicht möglich.');
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {main ? (
        <AddressRow key={main.id} entry={main} label="Adresse" email={business}
          {...row} />
      ) : readOnly ? (
        <span className="text-sm text-fg-3">Keine Adresse erfasst</span>
      ) : (
        <NewAddress {...row} label="Adresse" extra={{}} onDone={() => {}} />
      )}

      {main && !readOnly && (
        <ToggleField label="Abweichende Lieferadresse"
          checked={!!delivery || wantsDelivery}
          onChange={(on) => (on ? setWantsDelivery(true) : void deliveryOff())} />
      )}
      {delivery ? (
        <AddressRow key={delivery.id} entry={delivery} label="Lieferadresse" {...row} />
      ) : main && wantsDelivery && !readOnly ? (
        <NewAddress {...row} label="Lieferadresse" extra={{ is_default_delivery: true }}
          onDone={() => setWantsDelivery(false)} />
      ) : null}

      {extra.map((a) => (
        <AddressRow key={a.id} entry={a} label="Weitere Lieferadresse" removable {...row} />
      ))}
      {main && !readOnly && (addingExtra ? (
        <NewAddress {...row} label="Weitere Lieferadresse" extra={{}}
          onDone={() => setAddingExtra(false)} onCancel={() => setAddingExtra(false)} />
      ) : (
        <button type="button" onClick={() => setAddingExtra(true)}
          className="self-start inline-flex items-center gap-1.5 text-xs text-fg-3 hover:text-accent hover:underline">
          <Plus size={13} /> Weitere Lieferadresse
        </button>
      ))}
      {error && <ErrorText msg={error} />}
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

interface RowProps {
  owner: number | null; account: Account; loginEmail: string; readOnly?: boolean;
  mapsKey: string | null | undefined; onSaved: (u: UserProfile) => void;
}

/** Eine bestehende Anschrift – sie speichert sich selbst. */
function AddressRow({ owner, entry, label, email, removable, loginEmail, readOnly, mapsKey,
  onSaved }: RowProps & {
  entry: AddressEntry; label: string;
  /** Trägt diese Anschrift die Rechnungs-E-Mail? Nur im Geschäftskonto, nur die Adresse. */
  email?: boolean;
  removable?: boolean;
}) {
  const [form, setForm] = useState({ address: toAddress(entry), email: entry.email ?? '' });
  const [error, setError] = useState('');
  const { status, errorMsg, saveNow } = useAutosave(form, async (v) => {
    if (readOnly || !complete(v.address)) return;
    onSaved(await api.changeAddress(owner, entry.id,
      { ...toInput(v.address), ...(email ? { email: v.email.trim() || null } : {}) }));
  }, 1500);

  async function remove() {
    setError('');
    try {
      onSaved(await api.removeAddress(owner, entry.id));
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Nicht möglich.');
    }
  }

  return (
    <div className="ix-row flex flex-col gap-3">
      <fieldset disabled={readOnly} style={{ border: 0, padding: 0, margin: 0, minWidth: 0 }}
        className="flex flex-col gap-3">
        <AddressField value={form.address} apiKey={mapsKey} countryOptions={ADDRESS_COUNTRIES}
          showStreet2 showRegion label={label}
          onChange={(a) => setForm((p) => ({ ...p, address: a }))} />
        {email && (
          <AField label="Rechnungs-E-Mail" type="email" value={form.email} readOnly={readOnly}
            placeholder={inheritedEmail(loginEmail)} onEnter={saveNow}
            onChange={(v) => setForm((p) => ({ ...p, email: v }))} />
        )}
      </fieldset>
      {!readOnly && (
        <div className="flex items-center justify-between gap-2">
          <SaveStatusIndicator status={status} errorMsg={errorMsg} />
          {removable && (
            <button type="button" className="erp-actbtn erp-actbtn-icon"
              title="Lieferadresse entfernen" aria-label="Lieferadresse entfernen"
              onClick={() => void remove()}>
              <Trash2 size={14} />
            </button>
          )}
        </div>
      )}
      {error && <ErrorText msg={error} />}
    </div>
  );
}

/** Eine neue Anschrift – sie entsteht, sobald Strasse, PLZ und Ort dastehen. */
function NewAddress({ owner, account, mapsKey, onSaved, label, extra, onDone, onCancel }: RowProps & {
  label: string;
  /** Was die neue Anschrift ausserdem ist (z. B. die Lieferadresse). */
  extra: Partial<AddressInput>;
  onDone: () => void;
  onCancel?: () => void;
}) {
  const [draft, setDraft] = useState<Address>({ street: '', zip: '', city: '', country: 'CH' });
  const [error, setError] = useState('');
  const sent = useRef(false);
  // Die Rückrufe in einem Ref: ein neues Objekt je Rendern des Aufrufers soll die Pause
  // nicht neu starten – nur eine neue Eingabe tut das.
  const call = useRef({ owner, account, extra, onSaved, onDone });
  call.current = { owner, account, extra, onSaved, onDone };
  // **Einmal, und erst vollständig** – ein Treffer der Adresssuche ist es sofort, eine
  // getippte Anschrift nach einer kurzen Pause (sonst entstünde sie beim ersten Buchstaben
  // des Orts).
  useEffect(() => {
    if (sent.current || !complete(draft)) return;
    const t = setTimeout(() => {
      sent.current = true;
      const c = call.current;
      api.addAddress(c.owner, { ...toInput(draft), ...c.extra, account: c.account })
        .then((u) => { c.onSaved(u); c.onDone(); })
        .catch((e) => {
          sent.current = false;
          setError(e instanceof Error ? e.message : 'Nicht möglich.');
        });
    }, 1200);
    return () => clearTimeout(t);
  }, [draft]);

  return (
    <div className="flex flex-col gap-3">
      <AddressField value={draft} onChange={setDraft} apiKey={mapsKey}
        countryOptions={ADDRESS_COUNTRIES} showStreet2 showRegion label={label} />
      {onCancel && (
        <button type="button" className="self-start text-xs text-fg-3 hover:underline" onClick={onCancel}>
          Abbrechen
        </button>
      )}
      {error && <ErrorText msg={error} />}
    </div>
  );
}
