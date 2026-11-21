'use client';

import { useEffect, useState } from 'react';
import { LoginDialog } from '@/components/auth/login-dialog';
import { onAuthChange } from '@/lib/firebase';
import { api } from '@/lib/api';
import { framed, goTo, isSafeTarget, loginTarget } from '@/lib/login-target';
import { cachedRole } from '@/lib/account-cache';

/**
 * **Die Route ist der zweite Weg zum selben Dialog.**
 *
 * Seit Website und ERP EINEN Kopf tragen (WEBSITE_PLAN Entscheid 60), führt «Anmelden» von
 * überall hierher – der Kopf hängt die Seite an, auf der man stand (`?from=`). Dorthin geht es
 * nach der Anmeldung (`loginTarget`) und ebenso beim Danebenklicken; ohne Angabe zur Website
 * (hart: sie ist keine Next-Seite).
 *
 * **Wer schon angemeldet ist, sieht keinen Dialog**, sondern geht direkt an seinen
 * Startplatz (ERP bzw. Konto). Vorher zeigte die Route jedem den Dialog, auch dem, der
 * längst angemeldet war – und nach der Anmeldung ging es zurück zur Website, wo nichts
 * davon zu sehen ist. Gefragt wird nur der **erste** Stand: danach meldet der Dialog selbst.
 *
 * **Im Rahmen der Website** (`website/src/scripts/account.ts`, «Anmelden» über der Seite): ohne
 * Kopf und Fuss, durchsichtig (`html[data-embed]`), «daneben klicken» schliesst den Rahmen
 * (`close`), und erst wenn der Dialog steht, wird er sichtbar (`ready`).
 */
export default function LoginPage() {
  const [ready, setReady] = useState(false);

  useEffect(() => {
    // Ist niemand angemeldet, antwortet `onAuthChange` «niemand», ohne Firebase zu starten –
    // der Dialog steht, und erst eine Anmeldung spricht mit Google.
    let first = true;
    return onAuthChange(async (user) => {
      if (!first) return;
      first = false;
      if (!user) {
        setReady(true);
        if (framed()) {
          document.documentElement.setAttribute('data-embed', '');
          tellSite('ready');
        }
        return;
      }
      let role: string | null = null;
      try { role = (await api.getMe()).role; } catch { role = cachedRole(); }
      goTo(loginTarget(role));
    });
  }, []);

  if (!ready) return null;
  return <LoginDialog onClose={() => (framed() ? tellSite('close') : window.location.assign(cameFrom()))} />;
}

/** Der Website (dem Fenster dahinter, gleicher Ursprung) sagen, wie es steht. */
function tellSite(what: 'ready' | 'close'): void {
  window.parent.postMessage({ source: 'inexxio-login', what }, window.location.origin);
}

/** Daneben klicken führt dorthin zurück, wo man war (`?from=`, vom Kopf gesetzt) – sonst zur Website. */
function cameFrom(): string {
  const from = new URLSearchParams(window.location.search).get('from');
  return isSafeTarget(from) ? from : '/';
}
