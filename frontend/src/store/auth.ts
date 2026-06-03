import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { api } from '@/lib/api';
import type { UserProfile } from '@/types';

interface AuthState {
  token: string | null;
  user: UserProfile | null;
  isAuthenticated: boolean;
  setAuth: (token: string, user: UserProfile) => void;
  clearAuth: () => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      token: null,
      user: null,
      isAuthenticated: false,
      setAuth: (token, user) => {
        api.setToken(token);
        set({ token, user, isAuthenticated: true });
      },
      clearAuth: () => {
        api.clearToken();
        set({ token: null, user: null, isAuthenticated: false });
      },
    }),
    {
      name: 'inexxio-auth',
      partialize: (state) => ({ token: state.token, user: state.user }),
      onRehydrateStorage: () => (state) => {
        if (state?.token) {
          api.setToken(state.token);
          if (state.token) {
            state.isAuthenticated = true;
          }
        }
      },
    },
  ),
);
