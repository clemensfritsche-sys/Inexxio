'use client';

/**
 * **Weltkarte der Gebietsaufteilung** (ADR 006). Eine abstrakte Karte aus Regions-Kacheln,
 * grob geografisch angeordnet. Jede Region gehört **genau EINER** Gesellschaft – nicht
 * zugewiesene Regionen dem **Betreiber** (er besitzt die Welt per Default, andere «beissen
 * sich» Regionen ab). So gehört jeder Fleck der Erde jemandem (Totalität).
 *
 * Bedienung: Region-Kachel anklicken → Gesellschafts-Chips erscheinen → zuweisen. Der
 * Betreiber-Chip setzt die Region auf den Default zurück. `highlight` hebt die Regionen der
 * gerade geöffneten Gesellschaft hervor.
 */

import { useCallback, useEffect, useState } from 'react';
import { Globe2, Building2, Check } from 'lucide-react';
import { api } from '@/lib/api';
import type { TerritoryMap as TerritoryMapData } from '@/types';

// Kategoriale Identitäts-Farben (KEINE Ampel – hier steht Farbe für «welche Gesellschaft»,
// nicht für Status). Der Betreiber trägt den warmen Grundton der Unternehmens-Kachel; die
// übrigen Gesellschaften bekommen je einen ruhigen, unterscheidbaren Ton nach Reihenfolge.
const OPERATOR_TONE = { dot: '#A65A3C', bg: '#F7EEE9', ring: '#A65A3C' };
const TONES = [
  { dot: '#0F766E', bg: '#EAF7F4', ring: '#0F766E' },  // Teal
  { dot: '#6D28D9', bg: '#F1ECFB', ring: '#6D28D9' },  // Violett
  { dot: '#B45309', bg: '#FBF1E3', ring: '#B45309' },  // Amber
  { dot: '#BE123C', bg: '#FBEAEE', ring: '#BE123C' },  // Rosé
  { dot: '#0369A1', bg: '#E8F1F9', ring: '#0369A1' },  // Blau
  { dot: '#4D7C0F', bg: '#F0F6E4', ring: '#4D7C0F' },  // Limette
];

export function TerritoryMap({ highlight }: { highlight?: number | null }) {
  const [data, setData] = useState<TerritoryMapData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try { setData(await api.getTerritories()); }
    catch (e) { setError(e instanceof Error ? e.message : 'Fehler beim Laden'); }
  }, []);
  useEffect(() => { load(); }, [load]);

  const assign = useCallback(async (region: string, companyObjectId: number) => {
    if (busy) return;
    setBusy(true); setError(null);
    try { setData(await api.assignTerritory(region, companyObjectId)); setSelected(null); }
    catch (e) { setError(e instanceof Error ? e.message : 'Zuweisung fehlgeschlagen'); }
    finally { setBusy(false); }
  }, [busy]);

  if (error && !data) return <div style={{ padding: 16, fontSize: 13, color: 'var(--danger)' }}>{error}</div>;
  if (!data) return <div style={{ padding: 16, fontSize: 13, color: 'var(--fg-4)' }}>Lädt…</div>;

  const operatorId = data.operator_object_id ?? null;
  // Ton je Gesellschaft: Betreiber = warmer Grundton, sonst nach Reihenfolge der (nicht-
  // Betreiber-)Gesellschaften – stabil, damit die Karte sich beim Neuladen nicht umfärbt.
  const nonOp = data.companies.filter((c) => c.object_id !== operatorId);
  const toneOf = (objId: number | null | undefined) => {
    if (objId == null || objId === operatorId) return OPERATOR_TONE;
    const idx = nonOp.findIndex((c) => c.object_id === objId);
    return TONES[idx % TONES.length] ?? OPERATOR_TONE;
  };
  const nameOf = (objId: number | null | undefined) =>
    data.companies.find((c) => c.object_id === objId)?.company_name
    ?? data.companies.find((c) => c.object_id === operatorId)?.company_name ?? 'Betreiber';

  const cols = Math.max(...data.regions.map((r) => r.pos[0])) + 1;

  return (
    <div style={{ maxWidth: 760, marginInline: 'auto', display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <Globe2 size={16} style={{ color: 'var(--fg-3)' }} />
        <span style={{ font: '700 11px var(--font-body)', letterSpacing: '.06em', textTransform: 'uppercase', color: 'var(--fg-3)' }}>
          Gebiete – wer fakturiert welche Region
        </span>
      </div>

      {/* Abstrakte Weltkarte: Regions-Kacheln nach grober geografischer Position. */}
      <div style={{ display: 'grid', gridTemplateColumns: `repeat(${cols}, 1fr)`, gap: 8 }}>
        {data.regions.map((r) => {
          const tone = toneOf(r.company_object_id);
          const isSel = selected === r.code;
          const isHi = highlight != null && r.company_object_id === highlight;
          return (
            <button key={r.code} onClick={() => setSelected(isSel ? null : r.code)}
              style={{
                gridColumn: r.pos[0] + 1, gridRow: r.pos[1] + 1,
                textAlign: 'left', cursor: 'pointer', padding: '10px 12px',
                borderRadius: 'var(--r-md)', background: tone.bg,
                border: `1px solid ${isSel || isHi ? tone.ring : 'var(--border-1)'}`,
                boxShadow: isSel ? `inset 0 0 0 1px ${tone.ring}` : 'none',
                display: 'flex', flexDirection: 'column', gap: 6, minHeight: 68,
              }}>
              <span style={{ font: '700 12.5px var(--font-body)', color: 'var(--fg-1)' }}>{r.label}</span>
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 11.5, color: 'var(--fg-2)' }}>
                <span style={{ width: 8, height: 8, borderRadius: 999, background: tone.dot, flex: 'none' }} />
                {nameOf(r.company_object_id)}
              </span>
            </button>
          );
        })}
      </div>

      {error && <div style={{ fontSize: 12, color: 'var(--danger)' }}>{error}</div>}

      {/* Zuweisung: gewählte Region einer Gesellschaft geben (Betreiber = Default). */}
      {selected && (
        <div style={{ border: '1px solid var(--border-1)', borderRadius: 'var(--r-md)', padding: 12,
          display: 'flex', flexDirection: 'column', gap: 10, background: '#fff' }}>
          <span style={{ fontSize: 12.5, color: 'var(--fg-2)' }}>
            <b style={{ color: 'var(--fg-1)' }}>{data.regions.find((r) => r.code === selected)?.label}</b>{' '}
            fakturiert durch:
          </span>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
            {data.companies.map((c) => {
              const cur = data.regions.find((r) => r.code === selected)?.company_object_id === c.object_id;
              const tone = toneOf(c.object_id);
              return (
                <button key={c.object_id} disabled={busy} onClick={() => assign(selected, c.object_id)}
                  style={{ display: 'inline-flex', alignItems: 'center', gap: 6, padding: '6px 11px',
                    borderRadius: 999, cursor: busy ? 'default' : 'pointer',
                    border: `1px solid ${cur ? tone.ring : 'var(--border-1)'}`,
                    background: cur ? tone.bg : '#fff', font: '600 12.5px var(--font-body)', color: 'var(--fg-1)' }}>
                  <span style={{ width: 8, height: 8, borderRadius: 999, background: tone.dot, flex: 'none' }} />
                  {c.company_name}{c.object_id === operatorId ? ' · Betreiber' : ''}
                  {cur && <Check size={13} style={{ color: tone.dot }} />}
                </button>
              );
            })}
          </div>
        </div>
      )}

      <p style={{ display: 'inline-flex', alignItems: 'flex-start', gap: 6, fontSize: 11.5, color: 'var(--fg-4)', lineHeight: 1.5 }}>
        <Building2 size={13} style={{ color: 'var(--fg-4)', flex: 'none', marginTop: 1 }} />
        Nicht zugewiesene Regionen gehören dem Betreiber. Ausschlaggebend ist die Rechnungsadresse
        des Kunden (Sitz); die Steuer richtet sich getrennt nach der Lieferadresse.
      </p>
    </div>
  );
}
