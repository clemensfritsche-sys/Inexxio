'use client';

import { useEffect, useState } from 'react';
import { QueryClientProvider, useQuery, useQueryClient } from '@tanstack/react-query';
import { newQueryClient } from '@/lib/use-feed';
import { api } from '@/lib/api';
import { refreshAfterEmailChange } from '@/lib/firebase';
import { AccountShell } from '@/components/account/account-shell';
import type { UserProfileUpdate } from '@/types';
import { tell } from '@/lib/notice';

type Language = NonNullable<UserProfileUpdate['language']>;
const LANGUAGES: readonly Language[] = ['de', 'fr', 'en', 'it'];

/** Die ausdrücklich gewählte Sprache aus der Adresse (`?lang=`) – sonst keine. */
function useChosenLanguage(): Language | null {
  const [lang, setLang] = useState<Language | null>(null);
  useEffect(() => {
    const raw = new URLSearchParams(window.location.search).get('lang');
    setLang(LANGUAGES.find((l) => l === raw) ?? null);
  }, []);
  return lang;
}

// Dieselbe Bauart wie im ERP: jeder Fehler meldet sich (`tell`), kein zweiter Wiederholungsweg.
const queryClient = newQueryClient();

function KontoInner() {
  const qc = useQueryClient();
  const { data: profile, isLoading } = useQuery({
    queryKey: ['me'],
    queryFn: () => api.getMe(),
    meta: { what: 'Profil' },
  });

  // ►►► **Zurück vom Bestätigungslink der neuen Anmelde-E-Mail** (`?email=neu`): frischer
  // Token, damit das Backend die neue Adresse übernimmt – oder, ist die Sitzung widerrufen,
  // zur Anmeldung (mit der neuen Adresse). ◄◄◄
  useEffect(() => {
    const url = new URL(window.location.href);
    if (url.searchParams.get('email') !== 'neu') return;
    url.searchParams.delete('email');
    window.history.replaceState(null, '', url.pathname + url.search + '#sicherheit');
    void refreshAfterEmailChange().then((token) => { if (token) void qc.invalidateQueries({ queryKey: ['me'] }); });
  }, [qc]);

  // ►►► **Die Sprache, die die Person im Konto wählt, ist ihre Sprache** (`?lang=`, gesetzt von
  // der Website und der Sprachwahl im Kopf). Ab dann folgen ihr die automatischen Mails. Nur eine
  // ausdrücklich gewählte Sprache zählt – ein Konto ohne `?lang=` ändert nichts. ◄◄◄
  const chosen = useChosenLanguage();
  useEffect(() => {
    if (!profile || !chosen || profile.language === chosen) return;
    api.updateMe({ language: chosen })
      .then((u) => qc.setQueryData(['me'], u))
      .catch(tell('Sprache', 'Nicht gespeichert'));
  }, [profile, chosen, qc]);

  async function handleSave(data: UserProfileUpdate) {
    await api.updateMe(data);
    await qc.invalidateQueries({ queryKey: ['me'] });
    if (data.first_name !== undefined || data.last_name !== undefined) {
      const firstName = data.first_name ?? profile?.first_name ?? '';
      const lastName = data.last_name ?? profile?.last_name ?? '';
      const fullName = [firstName, lastName].filter(Boolean).join(' ');
      // Den Anzeige-Cache schreibt `AccountSync` – hier wird der Name nur gemeldet.
      if (fullName) {
        window.dispatchEvent(new CustomEvent<string>('inexxio:profile-name-updated', { detail: fullName }));
      }
    }
  }

  return <AccountShell profile={profile ?? null} isLoading={isLoading} onSave={handleSave} />;
}

export default function KontoPage() {
  return (
    <QueryClientProvider client={queryClient}>
      <KontoInner />
    </QueryClientProvider>
  );
}
