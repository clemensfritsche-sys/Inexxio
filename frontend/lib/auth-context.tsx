"use client";

import { createContext, useContext, useEffect, useState } from "react";
import {
  User,
  onAuthStateChanged,
  signInWithEmailLink,
  sendSignInLinkToEmail,
  GoogleAuthProvider,
  signInWithPopup,
  signOut as firebaseSignOut,
  isSignInWithEmailLink,
} from "firebase/auth";
import { auth } from "@/lib/firebase";
import { api } from "@/lib/api";
import type { UserProfile } from "@/types";

interface AuthContextValue {
  firebaseUser: User | null;
  userProfile: UserProfile | null;
  loading: boolean;
  signInWithGoogle: () => Promise<void>;
  sendMagicLink: (email: string) => Promise<void>;
  completeMagicLink: () => Promise<boolean>;
  signOut: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

const EMAIL_FOR_SIGNIN_KEY = "inexxio_signin_email";

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [firebaseUser, setFirebaseUser] = useState<User | null>(null);
  const [userProfile, setUserProfile] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const unsubscribe = onAuthStateChanged(auth, async (user) => {
      setFirebaseUser(user);
      if (user) {
        await syncUserProfile(user);
      } else {
        setUserProfile(null);
      }
      setLoading(false);
    });
    return unsubscribe;
  }, []);

  async function syncUserProfile(user: User) {
    try {
      const profile = await api.get<UserProfile>("/api/v1/auth/me");
      setUserProfile(profile);
    } catch {
      // User not in DB yet – register
      try {
        const profile = await api.post<UserProfile>("/api/v1/auth/register", {
          firebase_uid: user.uid,
          email: user.email,
          first_name: user.displayName?.split(" ")[0] ?? null,
          last_name: user.displayName?.split(" ").slice(1).join(" ") || null,
          avatar_url: user.photoURL ?? null,
        });
        setUserProfile(profile);
      } catch {
        setUserProfile(null);
      }
    }
  }

  async function signInWithGoogle() {
    const provider = new GoogleAuthProvider();
    await signInWithPopup(auth, provider);
  }

  async function sendMagicLink(email: string) {
    const actionCodeSettings = {
      url: `${window.location.origin}/auth/verify`,
      handleCodeInApp: true,
    };
    await sendSignInLinkToEmail(auth, email, actionCodeSettings);
    localStorage.setItem(EMAIL_FOR_SIGNIN_KEY, email);
  }

  async function completeMagicLink(): Promise<boolean> {
    if (!isSignInWithEmailLink(auth, window.location.href)) return false;
    let email = localStorage.getItem(EMAIL_FOR_SIGNIN_KEY);
    if (!email) {
      email = window.prompt("Bitte geben Sie Ihre E-Mail-Adresse ein:");
    }
    if (!email) return false;
    await signInWithEmailLink(auth, email, window.location.href);
    localStorage.removeItem(EMAIL_FOR_SIGNIN_KEY);
    return true;
  }

  async function signOut() {
    await firebaseSignOut(auth);
    setUserProfile(null);
  }

  return (
    <AuthContext.Provider
      value={{
        firebaseUser,
        userProfile,
        loading,
        signInWithGoogle,
        sendMagicLink,
        completeMagicLink,
        signOut,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
