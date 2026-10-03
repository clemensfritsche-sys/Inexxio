'use client';

import { useEffect, useState } from 'react';
import { LoginDialog } from '@/components/auth/login-dialog';
import { auth, onAuthChange } from '@/lib/firebase';
import { api } from '@/lib/api';
import { goTo, loginTarget } from '@/lib/login-target';

/**
 * **Die Route ist der zweite Weg zum selben Dialog.**
 *
 * Angemeldet wird im Pop-up über der Seite, auf der man steht (`Navbar`). Hierher kommt,
 * wer von einem geschützten Bereich umgeleitet wurde, ein Lesezeichen öffnet – oder auf der
 * Website «Login» wählt. Dort gibt es keine Seite dahinter, also heisst «daneben klicken»
 * hier **zur Website** (hart: sie ist keine Next-Seite).
 *
 * **Wer schon angemeldet ist, sieht keinen Dialog**, sondern geht direkt an seinen
 * Startplatz (ERP bzw. Konto). Vorher zeigte die Route jedem den Dialog, auch dem, der
 * längst angemeldet war – und nach der Anmeldung ging es zurück zur Website, wo nichts
 * davon zu sehen ist. Gefragt wird nur der **erste** Stand: danach meldet der Dialog selbst.
 */
export default function LoginPage() {
  const [ready, setReady] = useState(false);

  useEffect(() => {
    // Ohne Firebase gäbe es nie eine Antwort – dann eben gleich der Dialog (der meldet es).
    if (!auth) { setReady(true); return; }
    let first = true;
    return onAuthChange(async (user) => {
      if (!first) return;
      first = false;
      if (!user) { setReady(true); return; }
      api.setToken(await user.getIdToken());
      let role: string | null = null;
      try { role = (await api.getMe()).role; } catch { role = localStorage.getItem('inexxio_user_role'); }
      goTo(loginTarget(role));
    });
  }, []);

  if (!ready) return null;
  return <LoginDialog onClose={() => window.location.assign('/')} />;
}
