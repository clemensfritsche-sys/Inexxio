'use client';

import { initializeApp, getApps, type FirebaseApp } from 'firebase/app';
import {
  getAuth,
  initializeAuth,
  browserLocalPersistence,
  browserPopupRedirectResolver,
  GoogleAuthProvider,
  sendSignInLinkToEmail,
  isSignInWithEmailLink,
  signInWithEmailLink,
  signInWithPopup,
  signInWithCustomToken,
  signOut,
  onIdTokenChanged,
  verifyBeforeUpdateEmail,
  reauthenticateWithPopup,
  type Auth,
  type User,
} from 'firebase/auth';
import { api } from './api';
import { clearAccountCache } from './account-cache';

const firebaseConfig = {
  apiKey: process.env.NEXT_PUBLIC_FIREBASE_API_KEY || '',
  authDomain: process.env.NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN || '',
  projectId: process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID || '',
  storageBucket: process.env.NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET || '',
  messagingSenderId: process.env.NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID || '',
  appId: process.env.NEXT_PUBLIC_FIREBASE_APP_ID || '',
};

let app: FirebaseApp;
let auth: Auth;

if (typeof window !== 'undefined') {
  app = getApps().length ? getApps()[0] : initializeApp(firebaseConfig);
  try {
    // Use localStorage persistence to avoid IndexedDB initialization issues
    // (stale pendingRedirect entries can cause auth/internal-error on init).
    auth = initializeAuth(app, {
      persistence: browserLocalPersistence,
      popupRedirectResolver: browserPopupRedirectResolver,
    });
  } catch {
    // initializeAuth throws on hot-reload / multiple calls — fall back
    auth = getAuth(app);
  }
  // Wechselt die angemeldete Person (Abmelden, anderes Konto), gilt das gehaltene Profil
  // nicht mehr (`api.getMe`).
  let uid: string | null | undefined;
  onIdTokenChanged(auth, (user) => {
    const next = user?.uid ?? null;
    if (uid !== undefined && next !== uid) api.forgetMe();
    uid = next;
  });
}

export { auth };

const googleProvider = new GoogleAuthProvider();
googleProvider.setCustomParameters({ prompt: 'select_account' });

function getActionCodeSettings() {
  // Unter welcher Adresse die Oberfläche läuft, weiss das Deployment – nicht eine
  // fest verdrahtete Domain hier (die stand auf `inexxio.web.app`, also auf keinem
  // der beiden Ziele). Im Browser gilt ohnehin die Adresse, auf der man steht.
  const baseUrl = typeof window !== 'undefined'
    ? window.location.origin
    : (process.env.NEXT_PUBLIC_APP_URL || 'http://localhost:3000');
  return {
    url: `${baseUrl}/login/verify`,
    handleCodeInApp: true,
  };
}

export async function sendMagicLink(email: string): Promise<void> {
  if (!auth) throw new Error('Firebase not initialized');
  await sendSignInLinkToEmail(auth, email, getActionCodeSettings());
  localStorage.setItem('emailForSignIn', email);
}

export async function completeMagicLink(): Promise<User | null> {
  if (!auth) return null;
  if (!isSignInWithEmailLink(auth, window.location.href)) return null;

  const email = localStorage.getItem('emailForSignIn') || '';
  if (!email) {
    throw new Error('E-Mail-Adresse nicht gefunden. Bitte erneut eingeben.');
  }

  const result = await signInWithEmailLink(auth, email, window.location.href);
  localStorage.removeItem('emailForSignIn');
  return result.user;
}

export async function signInWithGoogle(): Promise<User> {
  if (!auth) throw new Error('Firebase not initialized');
  const result = await signInWithPopup(auth, googleProvider, browserPopupRedirectResolver);
  return result.user;
}

// Passkey-Anmeldung: Das Backend prüft die WebAuthn-Assertion und stellt einen
// Firebase Custom Token aus. Damit wird hier eine ganz normale Firebase-Session
// begründet – ab jetzt verhält sich alles wie bei Magic Link / Google.
export async function signInWithPasskey(firebaseToken: string): Promise<User> {
  if (!auth) throw new Error('Firebase not initialized');
  const result = await signInWithCustomToken(auth, firebaseToken);
  return result.user;
}

export async function logout(): Promise<void> {
  // ►►► **Erst die Sitzung beenden, DANN den Anzeige-Cache räumen – und das unbedingt.** ◄◄◄
  //
  // Die Website liest den Cache, um «Anmelden» bzw. das Profilmenü zu zeigen
  // (`lib/account-cache`). Wurde er **vor** `signOut` geräumt, konnte ein noch laufender
  // Profil-Abruf (`AccountSync`, er läuft auf jeder Seite – auch auf `/abmelden`) ihn in der
  // Lücke wieder füllen: die Startseite zeigte danach weiter einen Namen, und man musste ein
  // zweites Mal abmelden. Nach `signOut` gibt es keine Sitzung mehr, auf die ein Schreiber
  // sich berufen könnte (`AccountSync` prüft `currentUid()` vor jedem Schreiben); das
  // `finally` räumt auch dann, wenn das Abmelden scheitert.
  try {
    if (auth) await signOut(auth);
  } finally {
    api.forgetMe();
    clearAccountCache();
  }
}

/** Wer jetzt angemeldet ist – die Frage, die ein Schreiber NACH einem `await` stellt. */
export function currentUid(): string | null {
  return auth?.currentUser?.uid ?? null;
}

// ►►► **Der Token kommt je Anfrage von hier** – kein Aufrufer setzt ihn. ◄◄◄ Der API-Client
// fragt vor jeder Anfrage (`force = false`: Firebase liefert den vorgehaltenen Token und
// erneuert ihn selbst kurz vor Ablauf) und nach einem 401 EINMAL erzwungen
// (`getIdToken(true)`: im Hintergrund-Tab oder im Ruhezustand läuft Firebases
// Erneuerungs-Timer nicht). `authStateReady` wartet beim Laden der Seite, bis Firebase die
// gespeicherte Sitzung gelesen hat – sonst ginge die erste Anfrage ohne Token hinaus.
// Hier registriert, damit `api.ts` nichts von Firebase wissen muss.
api.setTokenProvider(async (force) => {
  if (!auth) return null;
  await auth.authStateReady();
  return auth.currentUser ? auth.currentUser.getIdToken(force) : null;
});

export function onAuthChange(callback: (user: User | null) => void) {
  if (!auth) return () => {};
  // `onIdTokenChanged` statt `onAuthStateChanged`: feuert bei Anmelden/Abmelden UND bei
  // jeder Token-Erneuerung (die Abonnenten – `AuthGate`, `AccountSync`, Testnotizen,
  // Passkey-Hinweis – prüfen darum selbst, ob sich für sie etwas geändert hat).
  return onIdTokenChanged(auth, callback);
}

/**
 * ►►► **Die Anmelde-E-Mail ändern** – Firebase schickt einen Bestätigungslink an die NEUE
 * Adresse (`verifyBeforeUpdateEmail`); erst der Klick ändert sie. Die alte Adresse bekommt
 * von Firebase eine Nachricht mit einem Link zum Rückgängigmachen. ◄◄◄
 *
 * Nach dem Klick sind alle Sitzungen abgelaufen (Firebase widerruft sie bei einer neuen
 * E-Mail); der Link führt zurück nach `/konto?email=neu`, wo `refreshAfterEmailChange` das
 * prüft. Das Backend übernimmt die Adresse aus dem nächsten Token (`core/auth`).
 * Verlangt eine frische Anmeldung (`auth/requires-recent-login`) – siehe `reauthenticate`.
 */
export async function updateEmailAddress(newEmail: string): Promise<void> {
  if (!auth?.currentUser) throw new Error('Nicht angemeldet');
  auth.languageCode = 'de';
  await verifyBeforeUpdateEmail(auth.currentUser, newEmail, {
    url: `${window.location.origin}/konto?email=neu`,
    handleCodeInApp: false,
  });
}

/**
 * Frisch anmelden, ohne die Seite zu verlassen – geht nur mit Google (Pop-up). Wer per
 * E-Mail-Link oder Passkey angemeldet ist, meldet sich neu an (`'login'`).
 */
export async function reauthenticate(): Promise<'done' | 'login'> {
  const user = auth?.currentUser;
  if (!user?.providerData.some((p) => p.providerId === 'google.com')) return 'login';
  await reauthenticateWithPopup(user, googleProvider, browserPopupRedirectResolver);
  return 'done';
}

/**
 * Zurück vom Bestätigungslink: Gilt die Sitzung noch, holt sie einen frischen Token mit der
 * neuen Adresse; ist sie widerrufen, wird abgemeldet (das Konto schickt dann zur Anmeldung).
 */
export async function refreshAfterEmailChange(): Promise<string | null> {
  try {
    await auth?.currentUser?.reload();
    const token = await auth?.currentUser?.getIdToken(true);
    api.forgetMe();   // die neue Adresse steht erst in der nächsten Antwort
    return token ?? null;
  } catch {
    await logout();
    return null;
  }
}
