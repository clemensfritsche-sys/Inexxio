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
import { currentUid, onAuthChange } from '@/lib/firebase';
import { api } from '@/lib/api';
import { clearAccountCache, rememberContact, rememberName, rememberPhoto, rememberRole } from '@/lib/account-cache';

type ShellApi = { init: () => void; account: () => void };
const shellApi = () => (window as unknown as { inexxioShell?: ShellApi }).inexxioShell;

export function AccountSync() {
  // Name im Profil geändert (konto/page.tsx) – gleich im Kopf zeigen. Geschrieben wird er
  // nur hier; das Konto meldet ihn bloss.
  useEffect(() => {
    const onName = (e: Event) => {
      rememberName((e as CustomEvent<string>).detail);
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
        const me = await api.getMe();
        // ►►► **Nach einem `await` gilt die Voraussetzung nicht mehr von selbst.** ◄◄◄ Wer
        // inzwischen abgemeldet hat (oder ein anderes Konto angemeldet), bekäme sonst den
        // Cache dieser Antwort zurück – genau das war «zweimal abmelden».
        if (currentUid() !== user.uid) return;
        rememberRole(me.role);
        rememberName([me.first_name, me.last_name].filter(Boolean).join(' '));
        rememberContact({ email: me.email, phone: me.phone, company_name: me.company?.legal_name });
        rememberPhoto(me.photo_url || user.photoURL);
      } catch {
        // Ohne Antwort bleibt der letzte bekannte Stand stehen.
      }
      shellApi()?.account();
    });
  }, []);
  return null;
}
