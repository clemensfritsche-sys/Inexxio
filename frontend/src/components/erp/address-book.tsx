'use client';

import { useEffect, useRef, useState } from 'react';
import { MapPin, Pencil, Plus, Trash2 } from 'lucide-react';
import { api } from '@/lib/api';
import { Field as AField } from '@/components/form/field';
import { AddressField, type Address } from '@/components/erp/address-field';
import { ErrorText, MICRO_LABEL } from '@/components/erp/fields';
import { useAutosaveValue } from '@/lib/use-autosave';
import { SaveStatusIndicator } from '@/components/form/save-status';
import type { AddressEntry, AddressInput, UserProfile } from '@/types';

/**
 * **Die Anschriften EINES Kontos – dasselbe Bauteil für Privat und Geschäftskonto, für
 * Konto und ERP.**
 *
 * Je Konto eine **Liste**: die Rechnungsadresse zuoberst, darunter die Lieferadressen
 * (die erste ist der Standard; ohne eigene wird an die Rechnungsadresse geliefert). Der einzige Unterschied zwischen den Konten: im **Geschäftskonto** steht
 * an der Adresse eine **Rechnungs-E-Mail** – privat geht die Rechnung an die E-Mail der
 * Person.
 *
 * Wird die Standard-Lieferadresse entfernt, geht der Titel an die Rechnungsadresse zurück
 * (`address_book.remove`).
 *
 * Die Regeln stehen im Dienst (`services/address_book`); hier wird gezeichnet.
 */
export const ADDRESS_COUNTRIES: [string, string][] = [
  ['CH', 'Schweiz'], ['DE', 'Deutschland'], ['AT', 'Österreich'],
  ['FR', 'Frankreich'], ['IT', 'Italien'], ['LI', 'Liechtenstein'],
];

export type Account = 'private' | 'business';

/**
 * **Der Platzhalter der Rechnungs-E-Mail** (#1042/#1043): sie ist freiwillig und fällt
 * leer auf die Login-/Kontakt-Adresse zurück – der Platzhalter nennt die **Regel**, nicht
 * nur die Adresse (sonst sähe er aus wie eine Vorbelegung).
 */
function inheritedEmail(login: string | null | undefined): string {
  return login ? `übernimmt ${login}` : 'rechnung@firma.ch';
}

export function AddressBook({ owner, account, addresses, loginEmail, readOnly, mapsKey, onSaved, cards }: {
  /** `null` = die eigene Person (Konto), sonst ihre Objektnummer (ERP). */
  owner: number | null;
  account: Account;
  addresses: AddressEntry[];
  loginEmail: string;
  readOnly?: boolean;
  mapsKey: string | null | undefined;
  onSaved: (u: UserProfile) => void;
  /** Konto (Gestaltung der Website): jede Anschrift als graue Karte – dieselben Daten, dieselben Aktionen. */
  cards?: boolean;
}) {
  const mine = addresses.filter((a) => a.account === account);
  const main = mine.find((a) => a.is_default_billing) ?? null;
  const delivery = mine.find((a) => a.is_default_delivery && a.id !== main?.id) ?? null;
  const rest = mine.filter((a) => a.id !== main?.id && a.id !== delivery?.id);
  const business = account === 'business';
  const [editing, setEditing] = useState<number | null>(null);
  const [adding, setAdding] = useState(false);
  const [error, setError] = useState('');
  const row = { owner, account, loginEmail, readOnly, mapsKey, onSaved };

  async function remove(id: number) {
    setError('');
    try {
      onSaved(await api.removeAddress(owner, id));
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Nicht möglich.');
    }
  }

  if (!main) {
    return readOnly ? <span className="text-sm text-fg-3">Keine Adresse erfasst</span>
      : <NewAddress {...row} label="Rechnungsadresse" extra={{}} onDone={() => {}} />;
  }

  // **Eine Liste, eine Zeile je Anschrift** – oben die Rechnungsadresse, darunter die
  // Lieferadressen. Ob es eine eigene Lieferadresse gibt, sagt die Liste selbst; wer an
  // die Rechnungsadresse liefert, sieht es am Wort.
  const lines: { a: AddressEntry; tag: string; note?: string; removable: boolean }[] = [
    { a: main, tag: delivery ? 'Rechnung' : 'Rechnung · Lieferung', removable: false,
      note: business ? `Rechnung per E-Mail an ${main.email || loginEmail}` : `Rechnung per E-Mail an ${loginEmail}` },
    ...(delivery ? [{ a: delivery, tag: 'Lieferung', note: 'Standard', removable: true }] : []),
    ...rest.map((a) => ({ a, tag: 'Lieferung', removable: true })),
  ];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: cards ? 12 : 0 }}>
      {lines.map(({ a, tag, note, removable }, i) => (
        <div key={a.id} className={cards ? 'kt-card' : undefined}
          style={cards ? undefined : { display: 'flex', gap: 16, padding: '14px 0', alignItems: 'flex-start',
            borderTop: i ? '1px solid var(--border-1)' : 'none' }}>
          {cards ? <span className="kt-card-ic"><MapPin aria-hidden /></span> : (
            <div style={{ width: 112, flexShrink: 0, paddingTop: 1 }}>
              <span style={{ ...MICRO_LABEL, display: 'inline-block', color: i ? 'var(--fg-3)' : 'var(--fg-2)',
                background: i ? 'var(--bg-2)' : 'var(--bg-3)', borderRadius: 4, padding: '3px 7px' }}>{tag}</span>
            </div>
          )}
          <div style={{ flex: 1, minWidth: 0 }}>
            {cards && <span className="kt-card-tag">{tag}</span>}
            {editing === a.id ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                <AddressRow entry={a} label="Anschrift" email={business && a.id === main.id} {...row} />
                <button type="button" className="self-start text-xs text-accent hover:underline"
                  onClick={() => setEditing(null)}>Fertig</button>
              </div>
            ) : (
              <div className={cards ? 'kt-card-text' : undefined}
                style={cards ? undefined : { font: '400 13.5px/20px var(--font-body)', color: 'var(--fg-2)' }}>
                <div style={cards ? undefined : { fontWeight: 600, color: 'var(--fg-1)' }}>{a.street1}</div>
                {a.street2 && <div>{a.street2}</div>}
                <div>{[a.zip, a.city].filter(Boolean).join(' ')} · {ADDRESS_COUNTRIES.find(([c]) => c === a.country)?.[1] ?? a.country}</div>
                {note && <small style={cards ? undefined : { display: 'block', fontSize: 12, color: 'var(--fg-4)', marginTop: 2 }}>{note}</small>}
              </div>
            )}
          </div>
          {!readOnly && editing !== a.id && (
            <div style={{ display: 'flex', gap: cards ? 6 : 2, flexShrink: 0 }}>
              <button type="button" className={cards ? 'kt-round' : 'erp-actbtn erp-actbtn-icon'} title="Ändern" aria-label="Ändern"
                onClick={() => setEditing(a.id)}><Pencil size={cards ? 16 : 14} /></button>
              {removable && (
                <button type="button" className={cards ? 'kt-round' : 'erp-actbtn erp-actbtn-icon'} title="Entfernen" aria-label="Entfernen"
                  onClick={() => void remove(a.id)}><Trash2 size={cards ? 16 : 14} /></button>
              )}
            </div>
          )}
        </div>
      ))}
      {!readOnly && (adding ? (
        <NewAddress {...row} label="Lieferadresse" extra={{ is_default_delivery: !delivery }}
          onDone={() => setAdding(false)} onCancel={() => setAdding(false)} />
      ) : (
        <button type="button" onClick={() => setAdding(true)}
          className={cards ? 'kt-add' : 'self-start inline-flex items-center gap-1.5 text-sm text-accent hover:underline'}
          style={cards ? undefined : { marginTop: 4 }}>
          <Plus size={cards ? 16 : 13} /> Lieferadresse hinzufügen
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
  const { status, errorMsg, saveNow } = useAutosaveValue(form, async (v) => {
    if (readOnly || !complete(v.address)) return;
    onSaved(await api.changeAddress(owner, entry.id,
      { ...toInput(v.address), ...(email ? { email: v.email.trim() || null } : {}) }));
  });

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
