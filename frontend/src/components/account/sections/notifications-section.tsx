'use client';

import { useState, useEffect, useRef } from 'react';
import { Bell } from 'lucide-react';
import type { UserProfile } from '@/types';
import { ToggleField } from '../field';
import { useAutosave } from '../use-autosave';
import { SaveStatusIndicator } from '../save-status';

interface Form {
  notification_email: boolean;
  notification_inapp: boolean;
  newsletter_opt_in: boolean;
}

function buildForm(p: UserProfile): Form {
  return {
    notification_email: p.notification_email ?? true,
    notification_inapp: p.notification_inapp ?? true,
    newsletter_opt_in: p.newsletter_opt_in ?? false,
  };
}

interface Props {
  profile: UserProfile;
  onSave: (data: Record<string, unknown>) => Promise<void>;
}

export function NotificationsSection({ profile, onSave }: Props) {
  const [form, setForm] = useState<Form>(() => buildForm(profile));
  const [resetKey, setResetKey] = useState(0);
  const prevId = useRef<number | undefined>(undefined);

  useEffect(() => {
    if (profile.id !== prevId.current) {
      prevId.current = profile.id;
      setForm(buildForm(profile));
      setResetKey((k) => k + 1);
    }
  }, [profile.id, profile]);

  const { status, errorMsg } = useAutosave(form, (v) => onSave(v as unknown as Record<string, unknown>), 1000, resetKey);

  function set<K extends keyof Form>(key: K, value: Form[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  return (
    <div style={{ background: '#fff', border: '1px solid #E2E8F0', borderRadius: 12, overflow: 'hidden' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '18px 24px', borderBottom: '1px solid #F1F5F9' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <Bell style={{ width: 16, height: 16, color: '#64748b' }} />
          <h2 style={{ fontSize: 15, fontWeight: 600, color: '#0F172A', margin: 0 }}>Benachrichtigungen</h2>
        </div>
        <SaveStatusIndicator status={status} errorMsg={errorMsg} />
      </div>

      <div style={{ padding: 24, display: 'flex', flexDirection: 'column', gap: 20 }}>
        <ToggleField
          label="E-Mail-Benachrichtigungen"
          description="Wichtige Updates und Systembenachrichtigungen per E-Mail"
          checked={form.notification_email}
          onChange={(v) => set('notification_email', v)}
        />
        <div style={{ height: 1, background: '#F1F5F9' }} />
        <ToggleField
          label="In-App-Benachrichtigungen"
          description="Benachrichtigungen direkt in der Anwendung anzeigen"
          checked={form.notification_inapp}
          onChange={(v) => set('notification_inapp', v)}
        />
        <div style={{ height: 1, background: '#F1F5F9' }} />
        <ToggleField
          label="Newsletter"
          description="Neuigkeiten, Produkt-Updates und Angebote von Inexxio"
          checked={form.newsletter_opt_in}
          onChange={(v) => set('newsletter_opt_in', v)}
        />
      </div>
    </div>
  );
}
