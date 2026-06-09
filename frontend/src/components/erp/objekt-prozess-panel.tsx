'use client';

import { useState, useRef, useEffect, useCallback } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Check, ChevronRight, ChevronDown, Loader2, Network, MapPin,
  AlertTriangle, Search, X, Package, Wrench,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { formatObjectId } from '@/lib/utils';
import { api } from '@/lib/api';
import { OBJ_STATUS_CONFIG } from '@/types';
import type { UniObjekt, SchrittProtokollEintrag, UniObjektSummary } from '@/types';

// ─── Reference confirmation search field ─────────────────────────────────────

function ReferenzSearchField({
  referenzId,
  onMatch,
}: {
  referenzId: number;
  onMatch: (ok: boolean) => void;
}) {
  const [q, setQ] = useState('');
  const [open, setOpen] = useState(false);
  const [selected, setSelected] = useState<UniObjektSummary | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  const { data: results = [], isFetching } = useQuery({
    queryKey: ['objekt-search-ref', q],
    queryFn: () => api.searchObjekte(q, 'FREIGEGEBEN'),
    enabled: q.trim().length >= 1,
    staleTime: 10_000,
  });

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, []);

  function select(item: UniObjektSummary) {
    setSelected(item);
    setQ('');
    setOpen(false);
    onMatch(item.id === referenzId);
  }

  function clear() {
    setSelected(null);
    onMatch(false);
  }

  const isMatch = selected !== null && selected.id === referenzId;
  const isMismatch = selected !== null && selected.id !== referenzId;

  return (
    <div ref={containerRef} className="relative">
      {selected ? (
        <div className={cn(
          'flex items-center gap-2 rounded-lg border px-3 py-2 text-sm',
          isMatch ? 'border-green-300 bg-green-50' : 'border-red-300 bg-red-50',
        )}>
          <span className="flex-1 font-medium truncate text-slate-800">
            {formatObjectId(selected.id)} · {selected.name}
          </span>
          {isMatch
            ? <Check className="h-4 w-4 text-green-600 shrink-0" />
            : <AlertTriangle className="h-4 w-4 text-red-500 shrink-0" />
          }
          <button type="button" onClick={clear} className="text-slate-400 hover:text-slate-600">
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
      ) : (
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-slate-400 pointer-events-none" />
          <input
            type="search"
            value={q}
            onChange={e => { setQ(e.target.value); setOpen(true); }}
            onFocus={() => setOpen(true)}
            placeholder="Referenz suchen…"
            className="w-full pl-8 pr-3 py-2 text-sm border border-blue-200 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          {isFetching && (
            <Loader2 className="absolute right-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 animate-spin text-slate-400" />
          )}
        </div>
      )}

      {open && !selected && results.length > 0 && (
        <div className="absolute z-50 mt-1 w-full rounded-xl border border-slate-200 bg-white shadow-lg py-1 max-h-44 overflow-y-auto">
          {results.map(item => (
            <button
              key={item.id}
              type="button"
              onMouseDown={() => select(item)}
              className="flex w-full items-center gap-2 px-3 py-2.5 text-sm hover:bg-slate-50 text-left"
            >
              <span className="font-mono text-xs text-slate-400 shrink-0">{formatObjectId(item.id)}</span>
              <span className="flex-1 truncate text-slate-800">{item.name}</span>
            </button>
          ))}
        </div>
      )}

      {isMismatch && (
        <p className="mt-1 text-xs text-red-600 flex items-center gap-1">
          <AlertTriangle className="h-3 w-3 shrink-0" />
          Falsche Referenz. Erwartet: {formatObjectId(referenzId)}
        </p>
      )}
    </div>
  );
}

// ─── Inline step execution content ────────────────────────────────────────────

function InlineSchrittContent({
  schritt,
  instanzId,
}: {
  schritt: SchrittProtokollEintrag;
  instanzId: number;
}) {
  const qc = useQueryClient();
  const [daten, setDaten] = useState<Record<string, string>>({});
  const autoTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const { mutate, isPending, error } = useMutation({
    mutationFn: (ergebnis: string) =>
      api.schrittErledigen(instanzId, schritt.position, {
        ergebnis,
        erfasste_daten: Object.keys(daten).length > 0 ? daten : undefined,
      }),
    onSuccess: (updated) => {
      qc.setQueryData(['uni-objekt', instanzId], updated);
    },
  });

  const hasReferenz = !!schritt.referenz_objekt_id;
  const hasDaten = !!(schritt.daten_felder && schritt.daten_felder.length > 0);
  const hasOptionen = !!(schritt.ergebnis_optionen && schritt.ergebnis_optionen.length > 0);
  const isGate = schritt.schritt_typ === 'gate';

  const allPflichtFilled = (schritt.daten_felder ?? [])
    .filter(f => f.pflicht !== false)
    .every(f => (daten[f.name] ?? '').trim() !== '');

  const handleDatenChange = useCallback((field: string, value: string) => {
    const next = { ...daten, [field]: value };
    setDaten(next);

    if (hasOptionen || isGate || hasReferenz) return;

    const allFilled = (schritt.daten_felder ?? [])
      .filter(f => f.pflicht !== false)
      .every(f => (next[f.name] ?? '').trim() !== '');
    if (!allFilled) return;

    if (autoTimer.current) clearTimeout(autoTimer.current);
    autoTimer.current = setTimeout(() => mutate('Erledigt'), 500);
  }, [daten, schritt.daten_felder, hasOptionen, isGate, hasReferenz, mutate]);

  const handleReferenzMatch = useCallback((ok: boolean) => {
    if (ok && allPflichtFilled) {
      mutate('Erledigt');
    }
  }, [allPflichtFilled, mutate]);

  const colorMap: Record<string, string> = {
    gruen: 'border-green-200 bg-green-50 text-green-800 hover:bg-green-100',
    rot: 'border-red-200 bg-red-50 text-red-800 hover:bg-red-100',
    gelb: 'border-amber-200 bg-amber-50 text-amber-800 hover:bg-amber-100',
  };

  const opts = hasOptionen
    ? schritt.ergebnis_optionen!
    : isGate
      ? [{ label: 'Erledigt', farbe: 'gruen' as const }, { label: 'Problem', farbe: 'rot' as const }]
      : null;

  if (isPending) {
    return (
      <div className="mt-2 flex items-center gap-2 text-xs text-slate-500">
        <Loader2 className="h-3.5 w-3.5 animate-spin" /> Wird gespeichert…
      </div>
    );
  }

  return (
    <div className="mt-2 space-y-2.5">
      {/* Daten fields */}
      {hasDaten && (schritt.daten_felder ?? []).map(feld => (
        <div key={feld.name}>
          <label className="block text-xs font-medium text-blue-800 mb-1">
            {feld.name}
            {feld.einheit && <span className="text-blue-600 font-normal ml-1">({feld.einheit})</span>}
            {feld.pflicht !== false && <span className="text-red-500 ml-0.5">*</span>}
          </label>
          {feld.typ === 'auswahl' && feld.optionen ? (
            <select
              value={daten[feld.name] ?? ''}
              onChange={e => handleDatenChange(feld.name, e.target.value)}
              className="w-full rounded-lg border border-blue-200 px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="">— Auswählen —</option>
              {feld.optionen.map(o => <option key={o} value={o}>{o}</option>)}
            </select>
          ) : (
            <input
              type={feld.typ === 'number' ? 'number' : feld.typ === 'datum' ? 'date' : 'text'}
              value={daten[feld.name] ?? ''}
              onChange={e => handleDatenChange(feld.name, e.target.value)}
              placeholder={feld.typ === 'number' ? '0.00' : 'Eingabe…'}
              className="w-full rounded-lg border border-blue-200 px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-blue-500 placeholder:text-slate-400"
            />
          )}
        </div>
      ))}

      {/* Reference confirmation (ressource, hilfsmittel, or any type with referenz) */}
      {hasReferenz && (
        <div>
          <p className="text-xs font-medium text-blue-800 mb-1 flex items-center gap-1">
            {schritt.schritt_typ === 'hilfsmittel'
              ? <Wrench className="h-3 w-3" />
              : <Package className="h-3 w-3" />
            }
            {schritt.schritt_typ === 'hilfsmittel' ? 'Hilfsmittel' : 'Referenz'} bestätigen
            <span className="font-mono text-blue-600">({formatObjectId(schritt.referenz_objekt_id!)})</span>
          </p>
          <ReferenzSearchField
            referenzId={schritt.referenz_objekt_id!}
            onMatch={handleReferenzMatch}
          />
        </div>
      )}

      {/* Ergebnis options (gate or explicit options) */}
      {opts && (
        <div className="space-y-1.5">
          {opts.map(opt => (
            <button
              key={opt.label}
              type="button"
              disabled={!allPflichtFilled}
              onClick={() => mutate(opt.label)}
              className={cn(
                'w-full text-left rounded-lg border px-3 py-2 text-sm font-medium transition-all flex items-center gap-2',
                allPflichtFilled
                  ? colorMap[opt.farbe] ?? colorMap.gruen
                  : 'border-slate-100 bg-slate-50 text-slate-400 cursor-not-allowed',
              )}
            >
              <ChevronRight className="h-3.5 w-3.5 shrink-0" />
              {opt.label}
            </button>
          ))}
        </div>
      )}

      {/* Simple done button (no daten, no reference, no options) */}
      {!opts && !hasReferenz && !hasDaten && (
        <button
          type="button"
          onClick={() => mutate('Erledigt')}
          className="flex items-center gap-2 rounded-lg bg-green-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-green-700 transition-colors"
        >
          <Check className="h-3.5 w-3.5" /> Erledigt
        </button>
      )}

      {/* Auto-save indicator */}
      {!opts && !hasReferenz && hasDaten && allPflichtFilled && (
        <div className="flex items-center gap-1.5 text-xs text-blue-500">
          <Loader2 className="h-3 w-3 animate-spin" /> Wird automatisch gespeichert…
        </div>
      )}

      {error && (
        <p className="text-xs text-red-600 flex items-center gap-1">
          <AlertTriangle className="h-3 w-3 shrink-0" />
          {(error as Error).message}
        </p>
      )}
    </div>
  );
}

// ─── Completed step read-only detail ─────────────────────────────────────────

function ErledigtDetail({ schritt }: { schritt: SchrittProtokollEintrag }) {
  return (
    <div className="mt-2 pt-2 border-t border-green-100 space-y-2">
      {schritt.ressourcen && schritt.ressourcen.length > 0 && (
        <div>
          <p className="text-xs font-medium text-green-700 mb-1 flex items-center gap-1">
            <Package className="h-3 w-3" /> Materialien
          </p>
          <div className="space-y-0.5">
            {schritt.ressourcen.map(r => (
              <div key={r.name} className="flex items-center justify-between text-xs">
                <span className="text-slate-600">{r.name}{r.ref_id ? ` (${formatObjectId(r.ref_id)})` : ''}</span>
                <span className="font-semibold text-slate-700">{r.menge} {r.einheit}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {schritt.daten_felder && schritt.daten_felder.length > 0 && (
        <div>
          <p className="text-xs font-medium text-green-700 mb-1">Erfasste Daten</p>
          <div className="space-y-0.5">
            {schritt.daten_felder.map(f => (
              <div key={f.name} className="flex items-center justify-between text-xs">
                <span className="text-slate-500">{f.name}{f.einheit ? ` (${f.einheit})` : ''}</span>
                <span className="font-medium text-slate-800">
                  {schritt.erfasste_daten?.[f.name] ?? '—'}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {schritt.referenz_objekt_id && (
        <div className="flex items-center gap-1.5 text-xs text-slate-600">
          <Check className="h-3 w-3 text-green-600 shrink-0" />
          Referenz bestätigt: <span className="font-mono font-medium">{formatObjectId(schritt.referenz_objekt_id)}</span>
        </div>
      )}

      {schritt.ergebnis && (
        <div className="flex items-center gap-1.5 text-xs">
          <span className="text-slate-500">Ergebnis:</span>
          <span className={cn(
            'font-semibold',
            schritt.ergebnis.toLowerCase().includes('problem') ? 'text-red-600' : 'text-green-700',
          )}>
            {schritt.ergebnis}
          </span>
        </div>
      )}

      <p className="text-xs text-green-600">
        ✓ {schritt.ausgefuehrt_von} · {schritt.ausgefuehrt_am
          ? new Date(schritt.ausgefuehrt_am).toLocaleString('de-CH', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })
          : ''}
      </p>
    </div>
  );
}

// ─── Main panel ───────────────────────────────────────────────────────────────

interface Props {
  objekt: UniObjekt;
  onRefresh?: () => void;
  onNavigate?: (id: number) => void;
}

export function ObjektProzessPanel({ objekt, onNavigate }: Props) {
  const qc = useQueryClient();
  const [expandedSteps, setExpandedSteps] = useState<Set<number>>(new Set());

  const protokoll = objekt.schritt_protokoll ?? [];
  const doneCount = protokoll.filter(s => s.status === 'erledigt').length;
  const totalCount = protokoll.length;
  const allDone = totalCount > 0 && doneCount === totalCount;

  const statusCfg = objekt.obj_status && objekt.obj_status in OBJ_STATUS_CONFIG
    ? OBJ_STATUS_CONFIG[objekt.obj_status as keyof typeof OBJ_STATUS_CONFIG]
    : { label: objekt.obj_status ?? '—', color: 'bg-slate-100 text-slate-600' };

  const { mutate: startUnterprozess, isPending: startingUnterprozess } = useMutation({
    mutationFn: (position: number) => api.unterprozessStarten(objekt.id, position),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['uni-objekt', objekt.id] });
    },
  });

  function toggleExpand(position: number) {
    setExpandedSteps(prev => {
      const next = new Set(prev);
      if (next.has(position)) next.delete(position);
      else next.add(position);
      return next;
    });
  }

  return (
    <div className="flex-1 flex flex-col overflow-hidden bg-white">
      {/* Header */}
      <div className="px-6 py-4 border-b border-slate-200 shrink-0">
        <div className="flex items-start justify-between mb-1">
          <div className="min-w-0">
            <div className="flex items-center gap-1.5 mb-0.5">
              <p className="text-xs font-mono text-slate-400">{formatObjectId(objekt.id)}</p>
              <span className="text-xs text-slate-300">·</span>
              <span className="text-xs text-slate-400">Instanz</span>
            </div>
            <h2 className="text-lg font-semibold text-slate-900 leading-tight">{objekt.name}</h2>
            {objekt.lagerort && (
              <p className="text-xs text-slate-500 mt-0.5 flex items-center gap-1">
                <MapPin className="h-3 w-3" />{objekt.lagerort}
              </p>
            )}
          </div>
          <span className={cn('shrink-0 ml-3 rounded-full px-2.5 py-1 text-xs font-semibold', statusCfg.color)}>
            {statusCfg.label}
          </span>
        </div>

        {totalCount > 0 && (
          <>
            <div className="mt-3 mb-1 flex items-center justify-between">
              <span className="text-xs text-slate-500">Fortschritt</span>
              <span className="text-xs font-semibold text-slate-700">{doneCount} / {totalCount}</span>
            </div>
            <div className="h-1.5 bg-slate-100 rounded-full overflow-hidden">
              <div
                className={cn('h-full rounded-full transition-all duration-700', allDone ? 'bg-green-500' : 'bg-blue-500')}
                style={{ width: `${(doneCount / totalCount) * 100}%` }}
              />
            </div>
          </>
        )}
      </div>

      {/* Step list */}
      <div className="flex-1 overflow-y-auto px-4 py-4 space-y-2">
        {allDone && (
          <div className="rounded-xl bg-green-50 border border-green-200 px-4 py-3 flex items-center gap-3 mb-2">
            <div className="h-8 w-8 rounded-full bg-green-500 flex items-center justify-center shrink-0">
              <Check className="h-4 w-4 text-white" />
            </div>
            <div>
              <p className="text-sm font-semibold text-green-800">Alle Schritte abgeschlossen</p>
              <p className="text-xs text-green-600 mt-0.5 flex items-center gap-1">
                <MapPin className="h-3 w-3" /> Objekt ist jetzt VERFÜGBAR
              </p>
            </div>
          </div>
        )}

        {protokoll.length === 0 && (
          <p className="text-sm text-slate-500 text-center py-8">Kein Prozessprotokoll vorhanden.</p>
        )}

        {protokoll.map(schritt => {
          const isExpanded = expandedSteps.has(schritt.position);
          const canExpand = schritt.status === 'erledigt';

          return (
            <div
              key={schritt.position}
              className={cn(
                'rounded-xl border transition-all',
                schritt.status === 'erledigt' && 'border-green-100 bg-green-50/60',
                schritt.status === 'aktiv' && 'border-blue-200 bg-blue-50 shadow-sm ring-1 ring-blue-100',
                schritt.status === 'wartend' && 'border-teal-200 bg-teal-50/60',
                schritt.status === 'ausstehend' && 'border-slate-100 bg-white opacity-60',
                schritt.status === 'problem' && 'border-red-200 bg-red-50',
              )}
            >
              {/* Step header row */}
              <div
                className={cn(
                  'flex items-start gap-3 px-4 py-3',
                  canExpand && 'cursor-pointer select-none',
                )}
                onClick={canExpand ? () => toggleExpand(schritt.position) : undefined}
              >
                <div className={cn(
                  'mt-0.5 flex h-7 w-7 items-center justify-center rounded-full shrink-0 text-xs font-bold',
                  schritt.status === 'erledigt' && 'bg-green-500 text-white',
                  schritt.status === 'aktiv' && 'bg-blue-600 text-white',
                  schritt.status === 'wartend' && 'bg-teal-500 text-white',
                  schritt.status === 'ausstehend' && 'bg-slate-100 text-slate-400',
                  schritt.status === 'problem' && 'bg-red-500 text-white',
                )}>
                  {schritt.status === 'erledigt'
                    ? <Check className="h-3.5 w-3.5" />
                    : schritt.status === 'wartend'
                      ? <Network className="h-3.5 w-3.5" />
                      : schritt.position}
                </div>

                <div className="flex-1 min-w-0">
                  <p className={cn(
                    'text-sm font-medium',
                    schritt.status === 'erledigt' && 'text-green-800',
                    schritt.status === 'aktiv' && 'text-blue-900',
                    schritt.status === 'wartend' && 'text-teal-800',
                    schritt.status === 'ausstehend' && 'text-slate-500',
                  )}>
                    {schritt.beschreibung}
                  </p>

                  {/* Compact erledigt summary (when collapsed) */}
                  {schritt.status === 'erledigt' && !isExpanded && (
                    <p className="text-xs text-green-600 mt-0.5">
                      ✓ {schritt.ergebnis ?? 'Erledigt'} · {schritt.ausgefuehrt_von}
                    </p>
                  )}

                  {/* Wartend sub-process links */}
                  {schritt.status === 'wartend' && schritt.sub_instanzen && schritt.sub_instanzen.length > 0 && (
                    <div className="mt-1.5 flex flex-wrap gap-1.5">
                      <span className="text-xs text-teal-600 font-medium">Unterprozesse:</span>
                      {schritt.sub_instanzen.map(subId => (
                        <button
                          key={subId}
                          onClick={e => { e.stopPropagation(); onNavigate?.(subId); }}
                          className="text-xs font-mono text-blue-600 hover:text-blue-800 hover:underline"
                        >
                          {formatObjectId(subId)}
                        </button>
                      ))}
                    </div>
                  )}

                  {/* Inline execution for active non-unterprozess steps */}
                  {schritt.status === 'aktiv' && schritt.schritt_typ !== 'unterprozess' && (
                    <InlineSchrittContent schritt={schritt} instanzId={objekt.id} />
                  )}

                  {/* Expanded erledigt detail */}
                  {schritt.status === 'erledigt' && isExpanded && (
                    <ErledigtDetail schritt={schritt} />
                  )}
                </div>

                {/* Expand/collapse chevron for erledigt */}
                {canExpand && (
                  <ChevronDown className={cn(
                    'h-4 w-4 text-green-500 shrink-0 mt-1 transition-transform',
                    isExpanded && 'rotate-180',
                  )} />
                )}

                {/* Unterprozess start button */}
                {schritt.status === 'aktiv' && schritt.schritt_typ === 'unterprozess' && (
                  <button
                    onClick={e => { e.stopPropagation(); startUnterprozess(schritt.position); }}
                    disabled={startingUnterprozess}
                    className="shrink-0 flex items-center gap-1.5 rounded-lg bg-teal-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-teal-700 active:bg-teal-800 transition-colors disabled:opacity-50"
                  >
                    {startingUnterprozess
                      ? <Loader2 className="h-3.5 w-3.5 animate-spin" />
                      : <Network className="h-3.5 w-3.5" />
                    }
                    Starten
                  </button>
                )}
              </div>

              {/* Active step: materials list */}
              {schritt.status === 'aktiv' && schritt.ressourcen && schritt.ressourcen.length > 0 && (
                <div className="px-4 pb-3 border-t border-blue-100 pt-2.5 space-y-1.5">
                  <p className="text-xs font-medium text-blue-700 mb-1.5">Benötigte Materialien:</p>
                  {schritt.ressourcen.map(r => (
                    <div key={r.name} className="flex items-center justify-between text-xs">
                      <span className="text-slate-700">{r.name}</span>
                      <span className="font-semibold text-slate-800">{r.menge} {r.einheit}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
