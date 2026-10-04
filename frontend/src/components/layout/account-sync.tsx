'use client';

/**
 * Der Anzeige-Cache des Kontos – das Einzige, was das Frontend zum Kopf beiträgt.
 *
 * Der Kopf (der der Website, `site-shell.tsx`) liest Rolle, Name, Kontakt und Profilbild aus
 * localStorage – auf der Website wie hier. Geschrieben wird der Cache an genau EINER Stelle:
 * hier, nach jeder Anmeldung; danach zeichnet `window.inexxioShell.account()` den Kopf neu.
 * Vorher schrieb ihn der React-Kopf nebenbei, und wer die Website vor dem ERP öffnete, sah
 * einen anderen Stand als im ERP.
 */
import { useEffect } from 'react';
import { onAuthChange } from '@/lib/firebase';
import { api } from '@/lib/api';
import { NAME_KEY, ROLE_KEY, clearAccountCache, rememberContact, rememberPhoto } from '@/lib/account-cache';

type ShellApi = { init: () => void; account: () => void };
const shellApi = () => (window as unknown as { inexxioShell?: ShellApi }).inexxioShell;

export function AccountSync() {
  // Name im Profil geändert (konto/page.tsx) – gleich im Kopf zeigen.
  useEffect(() => {
    const onName = (e: Event) => {
      const name = (e as CustomEvent<string>).detail;
      try { if (name) localStorage.setItem(NAME_KEY, name); } catch { /* kein Speicher */ }
      shellApi()?.account();
    };
    window.addEventListener('inexxio:profile-name-updated', onName);
    return () => window.removeEventListener('inexxio:profile-name-updated', onName);
  }, []);

  useEffect(() => {
    shellApi()?.init();
    return onAuthChange(async (user) => {
      if (!user) {
        clearAccountCache();
        shellApi()?.account();
        return;
      }
      // Sofort das Bild der Anmeldung, danach das des Datensatzes – derselbe Vorrang wie im ERP.
      rememberPhoto(user.photoURL);
      try {
        api.setToken(await user.getIdToken());
        const me = await api.getMe();
        localStorage.setItem(ROLE_KEY, me.role);
        const name = [me.first_name, me.last_name].filter(Boolean).join(' ');
        if (name) localStorage.setItem(NAME_KEY, name);
        rememberContact(me);
        rememberPhoto(me.photo_url || user.photoURL);
      } catch {
        // Ohne Antwort bleibt der letzte bekannte Stand stehen.
      }
      shellApi()?.account();
    });
  }, []);
  return null;
}
