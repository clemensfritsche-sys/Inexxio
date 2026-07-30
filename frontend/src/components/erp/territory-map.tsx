'use client';

/**
 * **Weltkarte der Gebietsaufteilung** (ADR 006). Seit Testnotiz #322 eine wirkliche, mit
 * Code gemalte Karte (`world-map.tsx`: 5°-Raster, nur Linien und Ecken) statt einer Reihe
 * von Kacheln – die Zuordnung will man **sehen**, nicht lesen. Darunter steht dieselbe
 * Aussage als Liste: die Karte zeigt die Geografie, die Liste die Zuweisung.
 *
 * Jede Region gehört **genau EINER** Gesellschaft – nicht zugewiesene Regionen dem
 * **Betreiber** (er besitzt die Welt per Default, andere «beissen sich» Regionen ab). So
 * gehört jeder Fleck der Erde jemandem (Totalität).
 *
 * **Ausnahmen je Land.** Ein einzelnes Land kann von seiner Region abweichen («Europa
 * gehört der GmbH, Liechtenstein aber der Schweizer AG»). Backend-seitig ist das derselbe
 * Anspruch in derselben Tabelle (Land ≻ Region ≻ Betreiber); hier ist es eine Liste unter
 * der Karte. Ein Land IST eine Ausnahme, wenn sein Besitzer vom Besitzer seiner Region
 * abweicht – **abgeleitet**, kein zweites Flag, das auseinanderlaufen könnte.
 *
 * Bedienung: Region auf der Karte ODER in der Liste anklicken → Gesellschafts-Chips
 * erscheinen → zuweisen. Der Chip der ohnehin zuständigen Gesellschaft setzt auf den
 * Standard zurück. `highlight` hebt die Gebiete der gerade geöffneten Gesellschaft hervor.
 *
 * Ländernamen kommen aus `Intl.DisplayNames` (im Browser eingebaut) – keine zweite
 * Länderliste im Repository, die von der des Backends abweichen könnte.
 */

import { useCallback, useEffect, useMemo, useState } from 'react';
import { Globe2, Building2, Check, Plus, X, Search } from 'lucide-react';
import { api } from '@/lib/api';
import type { TerritoryMap as TerritoryMapData } from '@/types';
import { WorldMap } from '@/components/erp/world-map';

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
    catch (e) { setError(e instanceof Error ? e.message : 'Fehler beim Laden'); }
  }, []);
  useEffect(() => { load(); }, [load]);

  const assign = useCallback(async (area: string, companyObjectId: number | null) => {
    if (busy) return;
    setBusy(true); setError(null);
    try { setData(await api.assignTerritory(area, companyObjectId)); setSelected(null); }
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

  // Ein Land ist eine **Ausnahme**, wenn sein Besitzer vom Besitzer seiner Region abweicht –
  // abgeleitet aus den Daten, nicht als zweites Flag geführt.
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

  return (
    <div style={{ maxWidth: 760, marginInline: 'auto', display: 'flex', flexDirection: 'column', gap: 16 }}>
      {/* Eigener Titel nur ausserhalb einer Sektion – eingebettet (Stammdaten-Reiter, #299)
          liefert die umgebende Sektion die Überschrift «Gebiete». */}
      {!embedded && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <Globe2 size={16} style={{ color: 'var(--fg-3)' }} />
          <span style={{ font: '700 11px var(--font-body)', letterSpacing: '.06em', textTransform: 'uppercase', color: 'var(--fg-3)' }}>
            Gebiete – wer fakturiert welche Region
          </span>
        </div>
      )}

      {/* ── Die Karte ────────────────────────────────────────────────────────────
          Eine mit Code gemalte Welt (#322): 5°-Raster, harte Kanten, keine Rundungen.
          Die Farbe einer Fläche IST ihre Gesellschaft – die Zuordnung wird sichtbar,
          statt gelesen zu werden. Klick auf eine Fläche = Klick auf ihre Zeile. */}
      <div style={{ border: '1px solid var(--border-1)', overflow: 'hidden' }}>
        <WorldMap
          selected={selRegion?.code ?? null}
          onSelect={(code) => setSelected(selected === code ? null : code)}
          fill={(code) => toneOf(regionOwner(code)).bg}
          stroke={(code) => toneOf(regionOwner(code)).ring}
          title={(code) => `${data.regions.find((r) => r.code === code)?.label ?? code} · ${nameOf(regionOwner(code))}`}
        />
      </div>

      {/* ── Die Zuweisung als Liste ──────────────────────────────────────────────
          Dieselbe Aussage in Worten: eine Zeile je Region. Die Karte kann nicht sagen,
          wie eine Gesellschaft heisst – die Liste kann nicht zeigen, wo Ozeanien liegt. */}
      <div style={{ display: 'flex', flexDirection: 'column' }}>
        {data.regions.map((r) => {
          const tone = toneOf(r.company_object_id);
          const isSel = selected === r.code;
          const isHi = highlight != null && r.company_object_id === highlight;
          const exc = exceptions.filter((c) => c.region === r.code).length;
          return (
            <button key={r.code} onClick={() => setSelected(isSel ? null : r.code)}
              style={{
                display: 'flex', alignItems: 'center', gap: 9, textAlign: 'left', cursor: 'pointer',
                padding: '8px 10px', border: 'none', borderTop: '1px solid var(--border-1)',
                background: isSel ? tone.bg : 'transparent',
                font: `${isHi ? 600 : 400} 12.5px var(--font-body)`, color: 'var(--fg-1)',
              }}>
              <span style={{ width: 9, height: 9, background: tone.dot, flex: 'none' }} />
              <span style={{ minWidth: 92 }}>{r.label}</span>
              <span style={{ color: 'var(--fg-2)', minWidth: 0, flex: 1 }}>{nameOf(r.company_object_id)}</span>
              {/* Wie viele Länder dieser Region weichen ab? Ohne den Hinweis wäre die Zeile
                  eine halbe Wahrheit («Europa gehört X» – ausser Liechtenstein). */}
              {exc > 0 && (
                <span style={{ fontSize: 11, color: 'var(--fg-4)', flex: 'none' }}>
                  {exc} Ausnahme{exc === 1 ? '' : 'n'}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {error && <div style={{ fontSize: 12, color: 'var(--danger)' }}>{error}</div>}

      {/* Zuweisung – EIN Panel für Region wie Land: dieselbe Aussage «dieses Gebiet
          fakturiert …», also dieselbe Bedienung. */}
      {selected && (
        <div style={{ border: '1px solid var(--border-1)', borderRadius: 'var(--r-md)', padding: 12,
          display: 'flex', flexDirection: 'column', gap: 10, background: '#fff' }}>
          <span style={{ fontSize: 12.5, color: 'var(--fg-2)' }}>
            <b style={{ color: 'var(--fg-1)' }}>{selLabel}</b>{' '}fakturiert durch:
          </span>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
            {data.companies.map((c) => {
              const cur = selOwner === c.object_id;
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

      {/* ── Ausnahmen je Land ────────────────────────────────────────────────────
          Die Region ist die Regel, ein Land kann davon abweichen. Darum stehen die
          Ausnahmen unter der Karte statt als 250 Kacheln darin – gepflegt wird nur, was
          tatsächlich abweicht. */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ font: '700 11px var(--font-body)', letterSpacing: '.06em', textTransform: 'uppercase', color: 'var(--fg-3)' }}>
            Ausnahmen je Land
          </span>
          <button type="button" onClick={() => { setAdding(!adding); setQuery(''); }}
            style={{ marginLeft: 'auto', display: 'inline-flex', alignItems: 'center', gap: 4,
              border: '1px solid var(--border-1)', background: '#fff', borderRadius: 999,
              padding: '4px 10px', cursor: 'pointer', font: '600 12px var(--font-body)', color: 'var(--fg-2)' }}>
            {adding ? <X size={12} /> : <Plus size={12} />}{adding ? 'Schliessen' : 'Land'}
          </button>
        </div>

        {adding && (
          <div style={{ border: '1px solid var(--border-1)', borderRadius: 'var(--r-md)', background: '#fff', padding: 10,
            display: 'flex', flexDirection: 'column', gap: 8 }}>
            <div style={{ position: 'relative' }}>
              <Search size={14} style={{ position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)', color: 'var(--fg-4)', pointerEvents: 'none' }} />
              <input value={query} onChange={(e) => setQuery(e.target.value)} autoFocus
                placeholder="Land suchen – z. B. Liechtenstein"
                style={{ width: '100%', padding: '8px 10px 8px 32px', borderRadius: 'var(--r-md)',
                  border: '1px solid var(--border-1)', background: 'var(--bg-1)', outline: 'none',
                  font: '400 13.5px var(--font-body)', color: 'var(--fg-1)', boxSizing: 'border-box' }} />
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
              {candidates.map((c) => (
                <button key={c.code} type="button" onClick={() => { setSelected(c.code); setAdding(false); setQuery(''); }}
                  style={{ display: 'inline-flex', alignItems: 'center', gap: 6, padding: '5px 10px', borderRadius: 999,
                    border: '1px solid var(--border-1)', background: '#fff', cursor: 'pointer',
                    font: '500 12.5px var(--font-body)', color: 'var(--fg-1)' }}>
                  {c.label}
                  <span style={{ fontSize: 11, color: 'var(--fg-4)' }}>{nameOf(c.company_object_id)}</span>
                </button>
              ))}
              {candidates.length === 0 && <span style={{ fontSize: 12, color: 'var(--fg-4)' }}>Kein Land gefunden.</span>}
            </div>
          </div>
        )}

        {exceptions.length === 0 && !adding && (
          <span style={{ fontSize: 12, color: 'var(--fg-4)' }}>Keine – jedes Land folgt seiner Region.</span>
        )}

        {exceptions.map((c) => {
          const tone = toneOf(c.company_object_id);
          const isHi = highlight != null && c.company_object_id === highlight;
          return (
            <div key={c.code} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '7px 10px',
              borderRadius: 'var(--r-md)', background: '#fff',
              border: `1px solid ${isHi ? tone.ring : 'var(--border-1)'}` }}>
              <span style={{ width: 8, height: 8, borderRadius: 999, background: tone.dot, flex: 'none' }} />
              <button type="button" onClick={() => setSelected(selected === c.code ? null : c.code)}
                style={{ background: 'none', border: 'none', padding: 0, cursor: 'pointer', textAlign: 'left',
                  font: '600 12.5px var(--font-body)', color: 'var(--fg-1)' }}>
                {countryLabel(c.code, displayNames)}
              </button>
              <span style={{ fontSize: 11.5, color: 'var(--fg-3)' }}>→ {nameOf(c.company_object_id)}</span>
              {/* Zurücksetzen = der Region folgen (die Ausnahme entfällt). */}
              <button type="button" disabled={busy} onClick={() => assign(c.code, regionOwner(c.region))}
                title="Ausnahme entfernen – folgt wieder der Region"
                style={{ marginLeft: 'auto', display: 'inline-flex', background: 'none', border: 'none',
                  padding: 2, cursor: busy ? 'default' : 'pointer', color: 'var(--fg-4)' }}>
                <X size={14} />
              </button>
            </div>
          );
        })}
      </div>

      <p style={{ display: 'inline-flex', alignItems: 'flex-start', gap: 6, fontSize: 11.5, color: 'var(--fg-4)', lineHeight: 1.5 }}>
        <Building2 size={13} style={{ color: 'var(--fg-4)', flex: 'none', marginTop: 1 }} />
        Nicht zugewiesene Regionen gehören dem Betreiber, ein Land folgt seiner Region – solange es
        keine Ausnahme trägt. Ausschlaggebend ist die Rechnungsadresse des Kunden (Sitz); die Steuer
        richtet sich getrennt nach der Lieferadresse.
      </p>
    </div>
  );
}
