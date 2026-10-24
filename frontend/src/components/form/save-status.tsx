import { Loader2, Check, AlertCircle } from 'lucide-react';
import type { SaveStatus } from '@/lib/use-autosave';

export function SaveStatusIndicator({ status, errorMsg }: { status: SaveStatus; errorMsg: string }) {
  if (status === 'idle' || status === 'dirty') return null;
  if (status === 'saving') return (
    <span style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 12, color: 'var(--fg-4)' }}>
      <Loader2 style={{ width: 12, height: 12, animation: 'spin 0.7s linear infinite' }} />
      Speichert…
    </span>
  );
  if (status === 'saved') return (
    <span style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 12, color: 'var(--success)' }}>
      <Check style={{ width: 12, height: 12 }} />
      Gespeichert
    </span>
  );
  return (
    <span style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 12, color: 'var(--danger)' }}>
      <AlertCircle style={{ width: 12, height: 12 }} />
      {errorMsg || 'Fehler'}
    </span>
  );
}
