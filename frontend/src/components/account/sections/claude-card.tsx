'use client';

import { useState } from 'react';
import { Sparkles, Unlink } from 'lucide-react';
import { api } from '@/lib/api';
import type { McpGrant } from '@/types';
import { when } from '@/lib/when';
import { errorText } from '@/lib/use-action';
import { useQuery, useQueryClient } from '@tanstack/react-query';

/**
 * ►►► **Claude** – das ERP im eigenen Claude (Claude.ai, Desktop, Code), nur für Personal. ◄◄◄
 * Die Adresse zum Hinzufügen als Connector, darunter je erlaubtem Client eine Karte mit «Trennen»
 * (`services/mcp`: danach kommt dieser Client nicht mehr hinein).
 */
export function ClaudeCard() {
  const qc = useQueryClient();
  const grants: McpGrant[] | null = useQuery({
    queryKey: ['me', 'mcp'],
    queryFn: () => api.myMcpGrants(),
    meta: { what: 'Verbindungen mit Claude' },
  }).data ?? null;
  const setGrants = (rows: McpGrant[]) => qc.setQueryData(['me', 'mcp'], rows);
  const [error, setError] = useState('');
  const url = `${window.location.origin}/api/v1/mcp`;

  const cut = async (id: number) => {
    setError('');
    try { setGrants(await api.revokeMcpGrant(id)); } catch (e) { setError(errorText(e)); }
  };

  return (
    <>
      <div className="kt-card">
        <span className="kt-card-ic"><Sparkles aria-hidden /></span>
        <div className="kt-card-text" style={{ flex: 1, minWidth: 0 }}>
          Claude mit dem ERP verbinden
          <small>In Claude unter Connectors «Eigenen Connector hinzufügen» mit dieser Adresse: <code>{url}</code></small>
        </div>
      </div>
      {error && <p className="kt-note is-error">{error}</p>}
      {(grants ?? []).map((g) => (
        <div key={g.id} className="kt-card">
          <span className="kt-card-ic"><Sparkles aria-hidden /></span>
          <div style={{ flex: 1, minWidth: 0 }}>
            <span className="kt-card-tag">Verbunden</span>
            <div className="kt-card-text">{g.client}<small>Erlaubt {when(g.at)}</small></div>
          </div>
          <button type="button" className="kt-round" onClick={() => cut(g.id)} aria-label="Trennen" data-tip="Trennen">
            <Unlink size={16} />
          </button>
        </div>
      ))}
    </>
  );
}
