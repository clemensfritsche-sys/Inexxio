'use client';

import { createContext, useContext, useEffect, useState, type ReactNode } from 'react';
import { type User } from 'firebase/auth';
import { onAuthChange, getIdToken } from './firebase';
import { api } from './api';

interface AuthContextValue {
  user: User | null;
  loading: boolean;
  token: string | null;
}

const AuthContext = createContext<AuthContextValue>({ user: null, loading: true, token: null });

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [token, setToken] = useState<string | null>(null);

  useEffect(() => {
    const unsubscribe = onAuthChange(async (firebaseUser) => {
      setUser(firebaseUser);
      if (firebaseUser) {
        const idToken = await getIdToken();
        if (idToken) {
          setToken(idToken);
          api.setToken(idToken);
          localStorage.setItem('inexxio_token', idToken);
        }
      } else {
        setToken(null);
        api.clearToken();
        localStorage.removeItem('inexxio_token');
      }
      setLoading(false);
    });

    return unsubscribe;
  }, []);

  return (
    <AuthContext.Provider value={{ user, loading, token }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}

export function useRequireAuth() {
  const { user, loading } = useAuth();
  return { user, loading, isAuthenticated: !loading && !!user };
}
