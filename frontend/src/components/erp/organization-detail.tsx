'use client';

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Building2, ArrowLeft } from 'lucide-react';
import type { CompanySettings } from '@/types';
import { StatusBadge } from '@/components/erp/fields';
import { fmtObjId } from '@/components/erp/user-detail';
import { SystemConfigSection } from '@/components/account/sections/system-config-section';

// Eigener QueryClient: die ERP-Feed-Seite hat (anders als die Profil-/Admin-Seiten)
// keinen QueryClientProvider; die wiederverwendete SystemConfigSection nutzt aber
// React Query. Darum hier lokal bereitstellen.
const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 1, staleTime: 60_000 } },
});

const CFG = { label: 'Stammdaten', color: '#0f766e', bg: '#f0fdfa', icon: Building2 };

/**
 * Detailansicht des **Unternehmens** als vollwertiger ERP-Datensatz. Die ERP-/
 * Firmen-Konfiguration (Stammdaten, Recht, Bank, MWST, Integrationen, Artikelnamen,
 * Wareneingang) wird hier – statt in den Profileinstellungen – gepflegt. Nur Admins
 * sehen diesen Datensatz im Feed; das Bearbeiten ist serverseitig admin-geschützt.
 */
export function OrganizationDetail({ record, onSaved, onBack }: {
  record: CompanySettings;
  onSaved: (s: CompanySettings) => void;
  onBack: () => void;
}) {
  return (
    <div className="flex flex-col h-full">
      {/* Header (analog zu den übrigen ERP-Detailansichten) */}
      <div style={{ padding: '12px 20px', borderBottom: '1px solid #E2E8F0', background: '#fff', flexShrink: 0 }}>
        <button onClick={onBack} className="flex items-center gap-1 text-sm text-blue-600 mb-2 md:hidden">
          <ArrowLeft size={14} /> Zurück
        </button>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <div style={{ width: 44, height: 44, borderRadius: 10, flexShrink: 0, background: '#F1F5F9', color: '#64748b', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <Building2 size={20} />
          </div>
          <div style={{ minWidth: 0, flex: 1 }}>
            <div style={{ fontSize: 15, fontWeight: 700, color: '#0F172A' }}>{record.company_name || 'Unternehmen'}</div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 4 }}>
              <span style={{ fontSize: 12, color: '#94a3b8', fontFamily: 'monospace' }}>{fmtObjId(record.object_id)}</span>
              <StatusBadge cfg={CFG} size={10} />
            </div>
          </div>
        </div>
      </div>

      {/* Konfiguration (wiederverwendete Systemkonfiguration, hier im ERP statt im Profil) */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '20px', background: '#f8fafc' }}>
        <QueryClientProvider client={queryClient}>
          <SystemConfigSection onSaved={onSaved} />
        </QueryClientProvider>
      </div>
    </div>
  );
}
