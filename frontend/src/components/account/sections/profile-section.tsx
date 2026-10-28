'use client';

/**
 * **Mein Konto – Person · Adressen · Firma · Newsletter** (Abschnitte der einen Konto-Seite).
 *
 *   1. **Person**      – ein Formular, ein Auto-Save («Gespeichert» unter dem Titel); für
 *                        Personal dazu die Anstellung (nur Anzeige, pflegt der Administrator)
 *   2. **Adressen**    – das Adressbuch des privaten Kontos, jede Anschrift als graue Karte
 *   3. **Firma**       – die Firma (genannt, nie gesucht) und ihr Adressbuch
 *   4. **Newsletter**  – ein Schalter, sofort geschrieben (die Einwilligung ist ein Nachweis)
 */

import { useState, useEffect, useRef } from 'react';
import type { NewsletterState, UserProfile } from '@/types';
import { api } from '@/lib/api';
import { day } from '@/lib/when';
import { useAutosaveValue } from '@/lib/use-autosave';
import { SaveStatusIndicator } from '@/components/form/save-status';
import { AddressBook } from '@/components/erp/address-book';
import { CompanyField } from '@/components/erp/company-field';
import { useQueryClient } from '@tanstack/react-query';
import { useMapsApiKey } from '@/components/erp/use-maps-key';
import { KtDate, KtField, KtSection } from '@/components/form/kt-section';
import { tell } from '@/lib/notice';

interface Form {
  first_name: string;
  last_name: string;
  date_of_birth: string;
  phone: string;
  // ►►► **Die Anschriften stehen im Adressbuch** (`AddressBook`) – nicht in diesem
  // Formular: jede ist ein eigener Eintrag mit eigenem Auto-Save.
}

function buildForm(p: UserProfile): Form {
  return {
    first_name: p.first_name ?? '',
    last_name: p.last_name ?? '',
    date_of_birth: p.date_of_birth ?? '',
    phone: p.phone ?? '',
  };
}

interface Props {
  profile: UserProfile;
  isStaff: boolean;
  onSave: (data: Partial<UserProfile>) => Promise<void>;
}

export function ProfileSection({ profile, isStaff, onSave }: Props) {
  const [form, setForm] = useState<Form>(() => buildForm(profile));
  const [resetKey, setResetKey] = useState(0);
  const prevId = useRef<number | undefined>(undefined);
  const mapsKey = useMapsApiKey();
  const qc = useQueryClient();

  useEffect(() => {
    if (profile.id !== prevId.current) {
      prevId.current = profile.id;
      setForm(buildForm(profile));
      setResetKey((k) => k + 1);
    }
  }, [profile.id, profile]);

  // ►►► **Die Telefonnummer schreibt der Server lesbar zurück** («+41 79 505 83 02»,
  // `people.tidy_phone`). Übernommen wird sie nur, solange im Feld noch steht, was gesendet
  // wurde – wer schon weitertippt, verliert nichts; der nächste Auto-Save bringt sie wieder. ◄◄◄
  const sentPhone = useRef<string | null>(null);
  const formRef = useRef(form);
  formRef.current = form;
  const { status, errorMsg, saveNow } = useAutosaveValue(
    form,
    (v) => { sentPhone.current = v.phone; return onSave({ ...v } as Partial<UserProfile>); },
    resetKey,
  );
  useEffect(() => {
    const server = profile.phone ?? '';
    if (sentPhone.current !== null && formRef.current.phone === sentPhone.current && server !== sentPhone.current) {
      sentPhone.current = server;
      setForm((f) => ({ ...f, phone: server }));
    }
  }, [profile.phone]);

  function set<K extends keyof Form>(key: K, value: Form[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }
  // «· fehlt» steht, solange ein Pflichtfeld leer ist. **Was Pflicht ist, sagt der Server**
  // (`people.required_fields`) – das Konto spiegelt es, es entscheidet nicht.
  const empty = (k: keyof Form) => (profile.required_fields ?? []).includes(k) && !form[k].trim();

  return (
    <>
      <KtSection id="person" title="Person" text="So sprechen wir Sie an und so erreichen wir Sie."
        aside={<SaveStatusIndicator status={status} errorMsg={errorMsg} />}>
        <div className="kt-grid2">
          <KtField id="kt-first" label="Vorname" value={form.first_name} onChange={(v) => set('first_name', v)}
            onEnter={saveNow} missing={empty('first_name')} autoComplete="given-name" />
          <KtField id="kt-last" label="Nachname" value={form.last_name} onChange={(v) => set('last_name', v)}
            onEnter={saveNow} missing={empty('last_name')} autoComplete="family-name" />
          <KtField id="kt-phone" label="Telefon" type="tel" value={form.phone} onChange={(v) => set('phone', v)}
            onEnter={saveNow} missing={empty('phone')} placeholder="+41 44 000 00 00" autoComplete="tel" />
          <KtDate id="kt-born" label="Geburtsdatum" value={form.date_of_birth}
            onChange={(v) => set('date_of_birth', v)} onEnter={saveNow} missing={empty('date_of_birth')} />
        </div>
      </KtSection>

      {/* ►►► **Eine Adresse, optional eine abweichende Lieferadresse und weitere
          Lieferadressen.** ◄◄◄ Privat geht die Rechnung an die E-Mail der Person. */}
      <KtSection id="adressen" title="Adressen"
        text="Eine Anschrift für Rechnungen, dazu so viele Lieferadressen, wie Sie brauchen.">
        <AddressBook owner={null} account="private" addresses={profile.addresses ?? []} cards
          loginEmail={profile.email} mapsKey={mapsKey}
          onSaved={(u) => qc.setQueryData(['me'], u)} />
      </KtSection>

      {/* ►►► **Dieselbe Maske noch einmal – für die Firma.** ◄◄◄ Die Firma wird genannt
          (UID, sonst Name und Rechtsform) und vom Server erkannt oder angelegt; eine Liste
          fremder Firmen sieht ein Kunde nie. */}
      <KtSection id="firma" title="Firma"
        text="Bestellen Sie für einen Betrieb? Dann geht die Rechnung an die Firma.">
        <CompanyField look="kt" company={profile.company} readOnly={isStaff}
          country={profile.addresses?.[0]?.country}
          onLink={(id) => onSave({ company_object_id: id } as Partial<UserProfile>)}
          onCreate={(nc) => onSave({ new_company: nc } as Partial<UserProfile>)} />
        {profile.company && (
          <AddressBook owner={null} account="business" addresses={profile.addresses ?? []} cards
            loginEmail={profile.email} mapsKey={mapsKey}
            onSaved={(u) => qc.setQueryData(['me'], u)} />
        )}
      </KtSection>

      <KtSection id="newsletter" title="Newsletter"
        text="«Post von INEXXIO» – selten, und nur, wenn es etwas zu sagen gibt.">
        <Newsletter />
      </KtSection>
    </>
  );
}

/** ►►► **Der Newsletter – ein Schalter, sofort geschrieben.** ◄◄◄ Die Adresse ist im Konto
 *  bestätigt, darum ohne zweiten Klick. Neben dem Schalter steht der Satz, dem man
 *  zustimmt – derselbe, der als Nachweis gespeichert wird (vom Server). */
function Newsletter() {
  const [state, setState] = useState<NewsletterState | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => { api.myNewsletter().then(setState).catch(tell('Newsletter-Stand')); }, []);
  const flip = (on: boolean) => {
    setError(null);
    api.setMyNewsletter(on).then(setState)
      .catch((e) => setError(e instanceof Error ? e.message : 'Konnte nicht gespeichert werden.'));
  };
  const on = !!state?.subscribed;
  return (
    <div className="kt-switch">
      <button type="button" role="switch" aria-checked={on} aria-label="Newsletter"
        disabled={!state} onClick={() => flip(!on)} />
      <div>
        <p>{state?.wording ?? ''}</p>
        {on && state?.since && <p className="kt-note">Angemeldet seit {day(state.since)}</p>}
        {error && <p className="kt-note is-error">{error}</p>}
      </div>
    </div>
  );
}
