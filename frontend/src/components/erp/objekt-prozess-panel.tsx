'use client';

import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Check, ChevronRight, X, Loader2,
  Package, MapPin, AlertTriangle,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { formatObjectId } from '@/lib/utils';
import { api } from '@/lib/api';
import { OBJ_STATUS_CONFIG } from '@/types';
import type { UniObjekt, SchrittProtokollEintrag } from '@/types';

// ─── Step execution modal ─────────────────────────────────────────────────────

function SchrittModal({
  schritt,
  instanzId,
  onClose,
}: {
  schritt: SchrittProtokollEintrag;
  instanzId: number;
  onClose: () => void;
}) {
  const qc = useQueryClient();
  const [daten, setDaten] = useState<Record<string, string>>({});
  const [ergebnis, setErgebnis] = useState<string | null>(null);

  const { mutate, isPending, error } = useMutation({
    mutationFn: () =>
      api.schrittErledigen(instanzId, schritt.position, {
        ergebnis: ergebnis ?? 'Erledigt',
        erfasste_daten: Object.keys(daten).length > 0 ? daten : undefined,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['uni-objekt', instanzId] });
      onClose();
    },
  });

  const pflichtErfuellt =
    !schritt.daten_felder ||
    schritt.daten_felder
      .filter(f => f.pflicht)
      .every(f => (daten[f.name] ?? '').trim() !== '');
  const ergebnisErfuellt =
    !schritt.ergebnis_optionen ||
    schritt.ergebnis_optionen.length === 0 ||
    ergebnis !== null;
  const canComplete = pflichtErfuellt && ergebnisErfuellt;

  return (
    <div className="fixed inset-0 bg-black/50 flex items-end sm:items-center justify-center z-50 p-0 sm:p-4">
      <div className="bg-white w-full sm:rounded-xl sm:shadow-2xl sm:max-w-lg max-h-[90vh] flex flex-col">
        <div className="flex items-start justify-between px-5 py-4 border-b border-slate-200 shrink-0">
          <div>
            <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-0.5">
              Schritt {schritt.position} ausführen
            </p>
            <h3 className="text-base font-semibold text-slate-900">{schritt.beschreibung}</h3>
          </div>
          <button
            onClick={onClose}
            className="ml-4 shrink-0 rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-600 transition-colors"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-5 py-4 space-y-5">
          {schritt.ressourcen && schritt.ressourcen.length > 0 && (
            <div>
              <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">
                Ressourcen entnehmen
              </p>
              <div className="space-y-1.5">
                {schritt.ressourcen.map(r => (
                  <div key={r.name} className="flex items-center justify-between rounded-lg bg-amber-50 border border-amber-100 px-3 py-2">
                    <div className="flex items-center gap-2">
                      <Package className="h-3.5 w-3.5 text-amber-600 shrink-0" />
                      <span className="text-sm text-slate-800">{r.name}</span>
                      {r.ref_id && (
                        <span className="text-xs font-mono text-slate-400">{formatObjectId(r.ref_id)}</span>
                      )}
                    </div>
                    <span className="text-sm font-semibold text-amber-700">{r.menge} {r.einheit}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {schritt.daten_felder && schritt.daten_felder.length > 0 && (
            <div className="space-y-3">
              <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
                Daten erfassen
              </p>
              {schritt.daten_felder.map(feld => (
                <div key={feld.name}>
                  <label className="block text-sm font-medium text-slate-700 mb-1.5">
                    {feld.name}
                    {feld.einheit && <span className="text-slate-400 font-normal ml-1">({feld.einheit})</span>}
                    {feld.pflicht && <span className="text-red-500 ml-0.5">*</span>}
                  </label>
                  {feld.typ === 'auswahl' && feld.optionen ? (
                    <select
                      value={daten[feld.name] ?? ''}
                      onChange={e => setDaten(p => ({ ...p, [feld.name]: e.target.value }))}
                      className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                    >
                      <option value="">— Auswählen —</option>
                      {feld.optionen.map(o => <option key={o} value={o}>{o}</option>)}
                    </select>
                  ) : (
                    <input
                      type={feld.typ === 'number' ? 'number' : feld.typ === 'datum' ? 'date' : 'text'}
                      value={daten[feld.name] ?? ''}
                      onChange={e => setDaten(p => ({ ...p, [feld.name]: e.target.value }))}
                      placeholder={feld.typ === 'number' ? '0.00' : 'Eingabe…'}
                      className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 placeholder:text-slate-400"
                    />
                  )}
                </div>
              ))}
            </div>
          )}

          {schritt.ergebnis_optionen && schritt.ergebnis_optionen.length > 0 && (
            <div>
              <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">
                Ergebnis wählen
              </p>
              <div className="space-y-2">
                {schritt.ergebnis_optionen.map(opt => {
                  const selected = ergebnis === opt.label;
                  const colorMap = {
                    gruen: selected ? 'border-green-500 bg-green-50 text-green-800' : 'border-slate-200 hover:border-green-300 hover:bg-green-50/50',
                    rot: selected ? 'border-red-500 bg-red-50 text-red-800' : 'border-slate-200 hover:border-red-300 hover:bg-red-50/50',
                    gelb: selected ? 'border-amber-500 bg-amber-50 text-amber-800' : 'border-slate-200 hover:border-amber-300 hover:bg-amber-50/50',
                  };
                  return (
                    <button
                      key={opt.label}
                      onClick={() => setErgebnis(opt.label)}
                      className={cn(
                        'w-full text-left rounded-lg border px-3 py-2.5 text-sm font-medium transition-all flex items-center gap-2',
                        colorMap[opt.farbe],
                      )}
                    >
                      <div className={cn(
                        'h-4 w-4 rounded-full border-2 shrink-0 flex items-center justify-center',
                        selected ? 'border-current bg-current' : 'border-slate-300',
                      )}>
                        {selected && <Check className="h-2.5 w-2.5 text-white" />}
                      </div>
                      {opt.label}
                    </button>
                  );
                })}
              </div>
            </div>
          )}

          {error && (
            <div className="flex items-center gap-2 rounded-lg bg-red-50 border border-red-100 px-3 py-2.5">
              <AlertTriangle className="h-4 w-4 text-red-500 shrink-0" />
              <p className="text-sm text-red-700">{(error as Error).message}</p>
            </div>
          )}
        </div>

        <div className="px-5 py-4 border-t border-slate-200 shrink-0 flex gap-3">
          <button
            onClick={onClose}
            className="flex-1 rounded-lg border border-slate-200 px-4 py-2.5 text-sm font-medium text-slate-700 hover:bg-slate-50 transition-colors"
          >
            Abbrechen
          </button>
          <button
            onClick={() => mutate()}
            disabled={!canComplete || isPending}
            className={cn(
              'flex-1 rounded-lg px-4 py-2.5 text-sm font-semibold flex items-center justify-center gap-2 transition-colors',
              canComplete && !isPending
                ? 'bg-blue-600 text-white hover:bg-blue-700'
                : 'bg-slate-100 text-slate-400 cursor-not-allowed',
            )}
          >
            {isPending
              ? <><Loader2 className="h-4 w-4 animate-spin" /> Wird gespeichert…</>
              : <><Check className="h-4 w-4" /> Abschliessen</>
            }
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── Main panel ───────────────────────────────────────────────────────────────

interface Props {
  objekt: UniObjekt;
  onRefresh?: () => void;
}

export function ObjektProzessPanel({ objekt }: Props) {
  const [activeModal, setActiveModal] = useState<SchrittProtokollEintrag | null>(null);

  const protokoll = objekt.schritt_protokoll ?? [];
  const doneCount = protokoll.filter(s => s.status === 'erledigt').length;
  const totalCount = protokoll.length;
  const allDone = totalCount > 0 && doneCount === totalCount;

  const statusCfg = objekt.obj_status && objekt.obj_status in OBJ_STATUS_CONFIG
    ? OBJ_STATUS_CONFIG[objekt.obj_status as keyof typeof OBJ_STATUS_CONFIG]
    : { label: objekt.obj_status ?? '—', color: 'bg-slate-100 text-slate-600' };

  return (
    <div className="flex-1 flex flex-col overflow-hidden bg-white">
      {/* Header */}
      <div className="px-6 py-4 border-b border-slate-200 shrink-0">
        <div className="flex items-start justify-between mb-1">
          <div className="min-w-0">
            <p className="text-xs font-mono text-slate-400">{formatObjectId(objekt.id)}</p>
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

        {protokoll.map(schritt => (
          <div
            key={schritt.position}
            className={cn(
              'rounded-xl border transition-all',
              schritt.status === 'erledigt' && 'border-green-100 bg-green-50/60',
              schritt.status === 'aktiv' && 'border-blue-200 bg-blue-50 shadow-sm ring-1 ring-blue-100',
              schritt.status === 'ausstehend' && 'border-slate-100 bg-white opacity-60',
              schritt.status === 'problem' && 'border-red-200 bg-red-50',
            )}
          >
            <div className="flex items-start gap-3 px-4 py-3">
              <div className={cn(
                'mt-0.5 flex h-7 w-7 items-center justify-center rounded-full shrink-0 text-xs font-bold',
                schritt.status === 'erledigt' && 'bg-green-500 text-white',
                schritt.status === 'aktiv' && 'bg-blue-600 text-white',
                schritt.status === 'ausstehend' && 'bg-slate-100 text-slate-400',
                schritt.status === 'problem' && 'bg-red-500 text-white',
              )}>
                {schritt.status === 'erledigt'
                  ? <Check className="h-3.5 w-3.5" />
                  : schritt.position}
              </div>

              <div className="flex-1 min-w-0">
                <p className={cn(
                  'text-sm font-medium',
                  schritt.status === 'erledigt' && 'text-green-800',
                  schritt.status === 'aktiv' && 'text-blue-900',
                  schritt.status === 'ausstehend' && 'text-slate-500',
                )}>
                  {schritt.beschreibung}
                </p>

                {schritt.status === 'erledigt' && (
                  <div className="mt-1 flex flex-wrap gap-x-3 gap-y-0.5">
                    <span className="text-xs text-green-600">
                      ✓ {schritt.ausgefuehrt_von} · {schritt.ausgefuehrt_am ? new Date(schritt.ausgefuehrt_am).toLocaleTimeString('de-CH', { hour: '2-digit', minute: '2-digit' }) : ''}
                    </span>
                    {schritt.ergebnis && (
                      <span className="text-xs font-medium text-green-700">{schritt.ergebnis}</span>
                    )}
                    {schritt.erfasste_daten && Object.entries(schritt.erfasste_daten).map(([k, v]) => (
                      <span key={k} className="text-xs text-slate-500">{k}: <span className="font-medium text-slate-700">{v}</span></span>
                    ))}
                  </div>
                )}
              </div>

              {schritt.status === 'aktiv' && (
                <button
                  onClick={() => setActiveModal(schritt)}
                  className="shrink-0 flex items-center gap-1.5 rounded-lg bg-blue-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-blue-700 active:bg-blue-800 transition-colors"
                >
                  Ausführen <ChevronRight className="h-3.5 w-3.5" />
                </button>
              )}
            </div>

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
        ))}
      </div>

      {activeModal && (
        <SchrittModal
          schritt={activeModal}
          instanzId={objekt.id}
          onClose={() => setActiveModal(null)}
        />
      )}
    </div>
  );
}
