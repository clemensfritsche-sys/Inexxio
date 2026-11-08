'use client';

/**
 * **Weltkarte der Gebietsaufteilung** (ADR 006, Karte aus `world-map.tsx`). Jede Region
 * gehört **genau EINER** Gesellschaft, nicht zugewiesene dem **Betreiber**. Ein Land kann
 * abweichen (Land ≻ Region ≻ Betreiber); Ausnahme ist **abgeleitet**, kein Flag.
 *
 * Bedienung: Region anklicken → Gesellschaft wählen; die ohnehin zuständige setzt zurück.
 * `highlight` hebt die Gebiete der geöffneten Gesellschaft hervor. Ländernamen aus
 * `Intl.DisplayNames`.
 */

import { useCallback, useEffect, useMemo, useState } from 'react';
import { Globe2, Check, Plus, X, Search } from 'lucide-react';
import { api } from '@/lib/api';
import type { TerritoryMap as TerritoryMapData } from '@/types';
import { WorldMap, regionAnchor } from '@/components/erp/world-map';
import { MICRO_LABEL } from '@/components/erp/fields';
import { Skeleton } from './skeleton';
import { errorText } from '@/lib/use-action';

// Kategoriale Identitäts-Farben (KEINE Ampel): Farbe = «welche Gesellschaft». Drei Stärken
// je Ton: `dot` (Punkt/Kontur), `land` (Landfläche), `bg` (Chips und Zeilen).
const OPERATOR_TONE = { dot: '#A65A3C', land: '#D9B09C', bg: '#F7EEE9', ring: '#A65A3C' };
const TONES = [
  { dot: '#0F766E', land: '#8FC9C1', bg: '#EAF7F4', ring: '#0F766E' },  // Teal
  { dot: '#6D28D9', land: '#B9A2E8', bg: '#F1ECFB', ring: '#6D28D9' },  // Violett
  { dot: '#B45309', land: '#E0B37A', bg: '#FBF1E3', ring: '#B45309' },  // Amber
  { dot: '#BE123C', land: '#E79FAF', bg: '#FBEAEE', ring: '#BE123C' },  // Rosé
  { dot: '#0369A1', land: '#8FBBDC', bg: '#E8F1F9', ring: '#0369A1' },  // Blau
  { dot: '#4D7C0F', land: '#AFCD86', bg: '#F0F6E4', ring: '#4D7C0F' },  // Limette
];

/** Ländername in Deutsch – aus der eingebauten `Intl.DisplayNames`; Rückfall auf den Code. */
function countryLabel(code: string, dn: Intl.DisplayNames | null): string {
  try { return dn?.of(code) ?? code; } catch { return code; }
}

export function TerritoryMap({ highlight, embedded }: { highlight?: number | null; embedded?: boolean }) {
  const [data, setData] = useState<TerritoryMapData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [adding, setAdding] = useState(false);
  const [query, setQuery] = useState('');

  const displayNames = useMemo(() => {
    try { return new Intl.DisplayNames(['de'], { type: 'region' }); } catch { return null; }
  }, []);

  const load = useCallback(async () => {
    try { setData(await api.getTerritories()); }
    catch (e) { setError(errorText(e, 'Fehler beim Laden')); }
  }, []);
  useEffect(() => { load(); }, [load]);

  const assign = useCallback(async (area: string, companyObjectId: number | null) => {
    if (busy) return;
    setBusy(true); setError(null);
    try { setData(await api.assignTerritory(area, companyObjectId)); setSelected(null); }
    catch (e) { setError(errorText(e, 'Zuweisung fehlgeschlagen')); }
    finally { setBusy(false); }
  }, [busy]);

  if (error && !data) return <div style={{ padding: 16, fontSize: 13, color: 'var(--danger)' }}>{error}</div>;
  if (!data) return <Skeleton block={240} label="Gebietskarte wird geladen" style={{ padding: 16 }} />;

  const operatorId = data.operator_object_id ?? null;
  // Ton je Gesellschaft: Betreiber = warmer Grundton, sonst stabil nach Reihenfolge.
  const nonOp = data.companies.filter((c) => c.object_id !== operatorId);
  const toneOf = (objId: number | null | undefined) => {
    if (objId == null || objId === operatorId) return OPERATOR_TONE;
    const idx = nonOp.findIndex((c) => c.object_id === objId);
    return TONES[idx % TONES.length] ?? OPERATOR_TONE;
  };
  const nameOf = (objId: number | null | undefined) =>
    data.companies.find((c) => c.object_id === objId)?.name
    ?? data.companies.find((c) => c.object_id === operatorId)?.name ?? 'Betreiber';

  // Ein Land ist eine **Ausnahme**, wenn sein Besitzer von dem seiner Region abweicht.
  const regionOwner = (code: string) => data.regions.find((r) => r.code === code)?.company_object_id ?? null;
  const countries = data.countries ?? [];
  const exceptions = countries.filter((c) => c.company_object_id !== regionOwner(c.region));
  const named = countries
    .map((c) => ({ ...c, label: countryLabel(c.code, displayNames) }))
    .sort((a, b) => a.label.localeCompare(b.label, 'de'));
  const q = query.trim().toLowerCase();
  const candidates = (q
    ? named.filter((c) => c.label.toLowerCase().includes(q) || c.code.toLowerCase() === q)
    : named
  ).slice(0, 8);

  // Beschriftung des Auswahl-Panels: Region ODER Land (dieselbe Zuweisung, ein Panel).
  const selRegion = selected ? data.regions.find((r) => r.code === selected) : undefined;
  const selCountry = selected && !selRegion ? countries.find((c) => c.code === selected) : undefined;
  const selLabel = selRegion?.label ?? (selCountry ? countryLabel(selCountry.code, displayNames) : '');
  const selOwner = selRegion?.company_object_id ?? selCountry?.company_object_id ?? null;
  // Wo das Kärtchen sitzt: über der gewählten Fläche (bei einem Land über seiner Region).
  const anchor = regionAnchor(selRegion?.code ?? selCountry?.region ?? 'EUR');
  const regionExceptions = selRegion ? exceptions.filter((c) => c.region === selRegion.code) : [];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      {/* Eigener Titel nur ausserhalb einer Sektion (`embedded`). */}
      {!embedded && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <Globe2 size={16} style={{ color: 'var(--fg-3)' }} />
          <span style={{ ...MICRO_LABEL, color: 'var(--fg-3)' }}>
            Gebiete – wer fakturiert welche Region
          </span>
        </div>
      )}

      {/* **Die Zuordnung wird am Ort gemanagt**: jede Fläche trägt Namen und Gesellschaft,
          ein Klick öffnet die Zuweisung dort. */}
      <div style={{ position: 'relative', border: '1px solid var(--border-1)',
        borderRadius: 'var(--r-lg)', overflow: 'hidden' }}>
        <WorldMap
          selected={selRegion?.code ?? null}
          onSelect={(code) => { setSelected(selected === code ? null : code); setAdding(false); }}
          fill={(code) => toneOf(regionOwner(code)).land}
          stroke={(code) => toneOf(regionOwner(code)).ring}
          title={(code) => `${data.regions.find((r) => r.code === code)?.label ?? code} · ${nameOf(regionOwner(code))}`}
          label={(code) => {
            const r = data.regions.find((x) => x.code === code);
            if (!r) return null;
            const exc = exceptions.filter((c) => c.region === code).length;
            // Ist eine Gesellschaft geöffnet, treten die Gebiete der anderen zurück.
            const dim = highlight != null && r.company_object_id !== highlight;
            return {
              title: r.label,
              sub: nameOf(r.company_object_id) + (exc ? ` · ${exc} Ausnahme${exc === 1 ? '' : 'n'}` : ''),
              ink: dim ? 'var(--fg-4)' : toneOf(r.company_object_id).dot,
            };
          }}
        />

        {/* Die Zuweisung **am Ort**: ein Kärtchen über der gewählten Fläche. */}
        {selected && (
          <div
            style={{
              position: 'absolute', zIndex: 2,
              left: `clamp(8px, ${anchor.x}%, calc(100% - 8px))`,
              top: `clamp(8px, ${anchor.y}%, calc(100% - 8px))`,
              transform: `translate(${anchor.x > 65 ? '-100%' : anchor.x < 35 ? '0' : '-50%'}, ${anchor.y > 55 ? '-100%' : '0'})`,
              minWidth: 210, maxWidth: 300,
              background: 'var(--bg-1)', border: '1px solid var(--border-1)', borderRadius: 'var(--r-md)',
              boxShadow: 'var(--shadow-md)', padding: 11,
              display: 'flex', flexDirection: 'column', gap: 9,
            }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ font: '700 12.5px var(--font-body)', color: 'var(--fg-1)' }}>{selLabel}</span>
              <button type="button" onClick={() => { setSelected(null); setAdding(false); }}
                aria-label={`${selLabel} schliessen`} data-tip="Schliessen"
                style={{ marginLeft: 'auto', display: 'inline-flex', background: 'none', border: 'none',
                  padding: 2, cursor: 'pointer', color: 'var(--fg-4)' }}>
                <X size={14} aria-hidden />
              </button>
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
              {data.companies.map((c) => {
                const cur = selOwner === c.object_id;
                const tone = toneOf(c.object_id);
                return (
                  <button key={c.object_id} disabled={busy} onClick={() => assign(selected, c.object_id)}
                    style={{ display: 'inline-flex', alignItems: 'center', gap: 6, padding: '5px 10px',
                      borderRadius: 999, cursor: busy ? 'default' : 'pointer',
                      border: `1px solid ${cur ? tone.ring : 'var(--border-1)'}`,
                      background: cur ? tone.bg : 'var(--bg-1)', font: '600 12px var(--font-body)', color: 'var(--fg-1)' }}>
                    <span style={{ width: 7, height: 7, borderRadius: 999, background: tone.dot, flex: 'none' }} />
                    {c.name}
                    {cur && <Check size={12} style={{ color: tone.dot }} />}
                  </button>
                );
              })}
            </div>

            {/* Ausnahmen im selben Panel – nur, was tatsächlich abweicht. */}
            {selRegion && (
              <div style={{ borderTop: '1px solid var(--border-1)', paddingTop: 8, display: 'flex', flexDirection: 'column', gap: 6 }}>
                {regionExceptions.map((c) => (
                  <div key={c.code} style={{ display: 'flex', alignItems: 'center', gap: 7, fontSize: 12 }}>
                    <span style={{ width: 7, height: 7, borderRadius: 999, background: toneOf(c.company_object_id).dot, flex: 'none' }} />
                    <button type="button" onClick={() => { setSelected(c.code); setAdding(false); }}
                      style={{ background: 'none', border: 'none', padding: 0, cursor: 'pointer',
                        font: '600 12px var(--font-body)', color: 'var(--fg-1)' }}>
                      {countryLabel(c.code, displayNames)}
                    </button>
                    <span style={{ color: 'var(--fg-3)', minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {nameOf(c.company_object_id)}
                    </span>
                    <button type="button" disabled={busy} onClick={() => assign(c.code, regionOwner(c.region))}
                      title="Ausnahme entfernen – folgt wieder der Region"
                      style={{ marginLeft: 'auto', display: 'inline-flex', background: 'none', border: 'none',
                        padding: 2, cursor: busy ? 'default' : 'pointer', color: 'var(--fg-4)' }}>
                      <X size={13} />
                    </button>
                  </div>
                ))}
                {adding ? (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                    <div style={{ position: 'relative' }}>
                      <Search size={13} style={{ position: 'absolute', left: 9, top: '50%', transform: 'translateY(-50%)', color: 'var(--fg-4)', pointerEvents: 'none' }} />
                      <input value={query} onChange={(e) => setQuery(e.target.value)} autoFocus
                        placeholder="Land suchen"
                        style={{ width: '100%', padding: '6px 9px 6px 28px', borderRadius: 'var(--r-md)',
                          border: '1px solid var(--border-1)', background: 'var(--bg-1)', outline: 'none',
                          font: '400 12.5px var(--font-body)', color: 'var(--fg-1)', boxSizing: 'border-box' }} />
                    </div>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5 }}>
                      {candidates.map((c) => (
                        <button key={c.code} type="button" onClick={() => { setSelected(c.code); setAdding(false); setQuery(''); }}
                          style={{ padding: '4px 9px', borderRadius: 999, border: '1px solid var(--border-1)',
                            background: 'var(--bg-1)', cursor: 'pointer', font: '500 12px var(--font-body)', color: 'var(--fg-1)' }}>
                          {c.label}
                        </button>
                      ))}
                    </div>
                  </div>
                ) : (
                  <button type="button" onClick={() => { setAdding(true); setQuery(''); }}
                    style={{ alignSelf: 'flex-start', display: 'inline-flex', alignItems: 'center', gap: 4,
                      border: 'none', background: 'none', padding: 0, cursor: 'pointer',
                      font: '600 12px var(--font-body)', color: 'var(--fg-3)' }}>
                    <Plus size={12} /> Land
                  </button>
                )}
              </div>
            )}
          </div>
        )}
      </div>

      {error && <div style={{ fontSize: 12, color: 'var(--danger)' }}>{error}</div>}

    </div>
  );
}
