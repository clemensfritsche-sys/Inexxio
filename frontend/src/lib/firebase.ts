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
import { currentLang } from './lang';
import { cachedRole, clearAccountCache } from './account-cache';

const firebaseConfig = {
  apiKey: process.env.NEXT_PUBLIC_FIREBASE_API_KEY || '',
  authDomain: process.env.NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN || '',
  projectId: process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID || '',
  storageBucket: process.env.NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET || '',
  messagingSenderId: process.env.NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID || '',
  appId: process.env.NEXT_PUBLIC_FIREBASE_APP_ID || '',
};

// ►►► **Firebase startet erst, wenn es gebraucht wird – vorher spricht keine Seite mit Google.** ◄◄◄
//
// Gestartet wird es von einer Handlung (anmelden, abmelden, Token holen) oder von einem Abo
// (`onAuthChange`), aber Letzteres nur, wenn jemand angemeldet sein KANN (`mayBeSignedIn`).
// Ohne Hinweis weiss das Abo die Antwort selbst: niemand – so öffnen `/datenschutz`, `/agb`,
// `/dokument` keine Verbindung zu Google. Der Helfer für das Google-Pop-up (Rahmen von
// `<projekt>.firebaseapp.com`, Skript von apis.google.com) kommt erst, wenn der Anmeldedialog
// offen ist (`prepareSignIn`): er muss vor dem Klick bereitstehen, sonst sperrt Safari/iOS das
// Pop-up (der Klick wäre beim Öffnen schon «verbraucht»). Wer den Dialog öffnet, will sich
// anmelden – das sagt die Datenschutzerklärung (Ziff. 7).
let auth: Auth | undefined;
/** Abos, die auf den Start warten (niemand angemeldet) – sie hören ab dem Start mit. */
const waiting = new Set<(a: Auth) => void>();

function startAuth(withPopup = false): Auth | undefined {
  if (auth || typeof window === 'undefined') return auth;
  const app: FirebaseApp = getApps().length ? getApps()[0] : initializeApp(firebaseConfig);
  try {
    // localStorage statt IndexedDB (veraltete pendingRedirect-Einträge führten beim Start zu
    // auth/internal-error). Den popupRedirectResolver (er lädt den Rahmen von Google vor) nur
    // aus dem Anmeldedialog (`prepareSignIn`); sonst reist er mit dem Aufruf, der ihn braucht.
    auth = initializeAuth(app, withPopup
      ? { persistence: browserLocalPersistence, popupRedirectResolver: browserPopupRedirectResolver }
      : { persistence: browserLocalPersistence });
  } catch {
    // Schon gestartet (Hot Reload): `getAuth` gibt dieselbe Instanz zurück.
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
  const started = auth;
  for (const join of [...waiting]) join(started);
  waiting.clear();
  return auth;
}

/**
 * Kann hier jemand angemeldet sein? Firebase hält die Sitzung unter `firebase:authUser:…` in
 * localStorage (`browserLocalPersistence`); dazu der Anzeige-Cache (`cachedRole`) – steht er
 * noch, ohne dass eine Sitzung besteht, startet Firebase und räumt ihn (`AccountSync`).
 */
function mayBeSignedIn(): boolean {
  if (auth) return true;
  if (cachedRole()) return true;
  try {
    for (let i = 0; i < localStorage.length; i++) {
      if (localStorage.key(i)?.startsWith('firebase:authUser:')) return true;
    }
  } catch {
    // Kein Speicher – dann hat Firebase auch keine Sitzung gespeichert.
  }
  return false;
}

/** Firebase, falls jemand angemeldet sein kann – sonst nichts (und kein Start). */
function authIfSignedIn(): Auth | undefined {
  return mayBeSignedIn() ? startAuth() : undefined;
}

/** **Der Anmeldedialog ist offen** – Firebase samt Pop-up-Helfer vorbereiten, damit «Google»
 *  das Fenster im selben Klick öffnen kann (Safari/iOS). Läuft Firebase schon, bleibt es dabei. */
export function prepareSignIn(): void {
  startAuth(true);
}

function startedAuth(): Auth {
  const a = startAuth();
  if (!a) throw new Error('Firebase not initialized');
  return a;
}

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
    // Die Sprache steht immer darin – vor dem `lang`, das Firebase selbst anhängt (`lib/lang`).
    url: `${baseUrl}/login/verify?lang=${currentLang()}`,
    handleCodeInApp: true,
  };
}

/** Der Anmeldelink kommt im Kleid des Hauses (`POST /api/v1/auth/link`, aus dem Postfach der
 *  Gesellschaft). Geht er dort nicht hinaus – kein Postfach, Begrenzung, kein Netz zum Dienst –,
 *  schickt ihn Firebase wie bisher: angemeldet wird in jedem Fall. */
async function sentByUs(email: string): Promise<boolean> {
  try {
    return (await api.sendLoginLink(email, currentLang())).sent;
  } catch {
    // Ausnahme notice: der Rückweg über Firebase IST die Antwort, keine Meldung nötig.
    return false;
  }
}

export async function sendMagicLink(email: string): Promise<void> {
  // Firebase nur, wenn der Link nicht von uns hinausging – sonst bleibt Google ganz aussen vor.
  if (!(await sentByUs(email))) {
    await sendSignInLinkToEmail(startedAuth(), email, getActionCodeSettings());
  }
  localStorage.setItem('emailForSignIn', email);
}

export async function completeMagicLink(): Promise<User | null> {
  const auth = startAuth();
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

/** Der Helfer des Pop-ups lädt erst hier (Rahmen + apis.google.com). In Safari und auf dem
 *  Handy kann das Laden die Geste des Klicks aufbrauchen – dann blockiert der Browser das
 *  Pop-up (`auth/popup-blocked`); der zweite Klick öffnet es sofort, der Helfer steht dann. */
export async function signInWithGoogle(): Promise<User> {
  const result = await signInWithPopup(startedAuth(), googleProvider, browserPopupRedirectResolver);
  return result.user;
}

// Passkey-Anmeldung: Das Backend prüft die WebAuthn-Assertion und stellt einen
// Firebase Custom Token aus. Damit wird hier eine ganz normale Firebase-Session
// begründet – ab jetzt verhält sich alles wie bei Magic Link / Google.
export async function signInWithPasskey(firebaseToken: string): Promise<User> {
  const result = await signInWithCustomToken(startedAuth(), firebaseToken);
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
    const a = authIfSignedIn();
    if (a) await signOut(a);
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
// Kann niemand angemeldet sein, geht die Anfrage ohne Token – und ohne Firebase zu starten.
api.setTokenProvider(async (force) => {
  const auth = authIfSignedIn();
  if (!auth) return null;
  await auth.authStateReady();
  return auth.currentUser ? auth.currentUser.getIdToken(force) : null;
});

export function onAuthChange(callback: (user: User | null) => void): () => void {
  if (typeof window === 'undefined') return () => {};
  // `onIdTokenChanged` statt `onAuthStateChanged`: feuert bei Anmelden/Abmelden UND bei
  // jeder Token-Erneuerung (die Abonnenten – `AuthGate`, `AccountSync`,
  // Passkey-Hinweis, `/login` – prüfen darum selbst, ob sich für sie etwas geändert hat).
  const started = authIfSignedIn();
  if (started) return onIdTokenChanged(started, callback);
  // Niemand angemeldet: die Antwort «niemand» kommt ohne Firebase (wie sonst von ihm: nicht
  // synchron). Startet es später (eine Anmeldung auf dieser Seite), hört das Abo ab da mit.
  let gone = false;
  let stop: (() => void) | undefined;
  const join = (a: Auth) => { if (!gone) stop = onIdTokenChanged(a, callback); };
  waiting.add(join);
  queueMicrotask(() => { if (!gone && !stop) callback(null); });
  return () => {
    gone = true;
    waiting.delete(join);
    stop?.();
  };
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
