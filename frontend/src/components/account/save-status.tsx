import { Loader2, Check, AlertCircle } from 'lucide-react';
import type { SaveStatus } from './use-autosave';

export function SaveStatusIndicator({ status, errorMsg }: { status: SaveStatus; errorMsg: string }) {
  if (status === 'idle' || status === 'dirty') return null;
  if (status === 'saving') return (
    <span style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 12, color: '#94a3b8' }}>
      <Loader2 style={{ width: 12, height: 12, animation: 'spin 0.7s linear infinite' }} />
      Speichert…
    </span>
  );
  if (status === 'saved') return (
    <span style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 12, color: '#16a34a' }}>
      <Check style={{ width: 12, height: 12 }} />
      Gespeichert
    </span>
  );
  return (
    <span style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 12, color: '#dc2626' }}>
      <AlertCircle style={{ width: 12, height: 12 }} />
      {errorMsg || 'Fehler'}
    </span>
  );
}
