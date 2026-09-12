'use client';

import { useRouter } from 'next/navigation';
import { LoginDialog } from '@/components/auth/login-dialog';

/**
 * **Die Route ist der zweite Weg zum selben Dialog.**
 *
 * Angemeldet wird im Pop-up über der Seite, auf der man steht (`Navbar`). Hierher kommt
 * nur, wer von einem geschützten Bereich umgeleitet wurde oder ein Lesezeichen öffnet –
 * dort gibt es keine Seite dahinter, also heisst «daneben klicken» hier **zur
 * Startseite**. Genau das war früher ein eigener Link im Fenster.
 */
export default function LoginPage() {
  const router = useRouter();
  return <LoginDialog onClose={() => router.push('/')} />;
}
