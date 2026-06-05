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
  signOut,
  onAuthStateChanged,
  verifyBeforeUpdateEmail,
  type Auth,
  type User,
} from 'firebase/auth';

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
}

export { auth };

export const googleProvider = new GoogleAuthProvider();
googleProvider.setCustomParameters({ prompt: 'select_account' });

function getActionCodeSettings() {
  const baseUrl = typeof window !== 'undefined'
    ? window.location.origin
    : 'https://inexxio.web.app';
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

export async function completeMagicLink(): Promise<{ token: string; user: User } | null> {
  if (!auth) return null;
  if (!isSignInWithEmailLink(auth, window.location.href)) return null;

  const email = localStorage.getItem('emailForSignIn') || '';
  if (!email) {
    throw new Error('E-Mail-Adresse nicht gefunden. Bitte erneut eingeben.');
  }

  const result = await signInWithEmailLink(auth, email, window.location.href);
  localStorage.removeItem('emailForSignIn');
  const token = await result.user.getIdToken();
  return { token, user: result.user };
}

export async function signInWithGoogle(): Promise<{ token: string; user: User }> {
  if (!auth) throw new Error('Firebase not initialized');
  const result = await signInWithPopup(auth, googleProvider, browserPopupRedirectResolver);
  const token = await result.user.getIdToken();
  return { token, user: result.user };
}

export async function logout(): Promise<void> {
  if (!auth) return;
  await signOut(auth);
  localStorage.removeItem('inexxio_token');
}

export async function getIdToken(): Promise<string | null> {
  if (!auth?.currentUser) return null;
  return auth.currentUser.getIdToken();
}

export function onAuthChange(callback: (user: User | null) => void) {
  if (!auth) return () => {};
  return onAuthStateChanged(auth, callback);
}

export async function updateEmailAddress(newEmail: string): Promise<void> {
  if (!auth?.currentUser) throw new Error('Nicht angemeldet');
  const actionCodeSettings = {
    url: `${typeof window !== 'undefined' ? window.location.origin : 'https://inexxio-dev.web.app'}/konto`,
    handleCodeInApp: false,
  };
  await verifyBeforeUpdateEmail(auth.currentUser, newEmail, actionCodeSettings);
}
