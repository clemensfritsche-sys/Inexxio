'use client';

import { useState } from 'react';
import {
  Check, ChevronRight, X, Loader2, Zap,
  Package, AlertTriangle, MapPin, Clock,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { formatObjectId } from '@/lib/utils';
import { ProcessTracker } from './process-tracker';
import type { ProcessStep } from './process-tracker';

// ─── Types ────────────────────────────────────────────────────────────────────

interface Ressource {
  name: string;
  menge: number;
  einheit: string;
  ref_id?: number;
}

interface DatenFeld {
  name: string;
  typ: 'text' | 'number' | 'datum' | 'auswahl';
  pflicht: boolean;
  optionen?: string[];
  einheit?: string;
}

interface ErgebnisOption {
  label: string;
  farbe: 'gruen' | 'rot' | 'gelb';
}

export interface ProzessSchritt {
  id: number;
  position: number;
  beschreibung: string;
  status: 'ausstehend' | 'aktiv' | 'erledigt' | 'problem';
  ressourcen?: Ressource[];
  daten_felder?: DatenFeld[];
  ergebnis_optionen?: ErgebnisOption[];
  system_aktion?: string;
  ausgefuehrt_von?: string;
  ausgefuehrt_am?: string;
  ergebnis?: string;
  erfasste_daten?: Record<string, string>;
}

export interface DemoObjekt {
  id: number;
  name: string;
  stamm_name: string;
  auftrag_ref?: string;
  schritte: ProzessSchritt[];
}

// ─── Demo Data ────────────────────────────────────────────────────────────────

export const DEMO_KAFFEEMASCHINE: DemoObjekt = {
  id: 100000235,
  name: 'Kaffeemaschine Typ A',
  stamm_name: 'Kaffeemaschine Typ A',
  auftrag_ref: 'Fertigungsauftrag #001 · Los 5 Stk',
  schritte: [
    {
      id: 1,
      position: 1,
      beschreibung: 'Rüsten & Material bereitlegen',
      status: 'erledigt',
      ressourcen: [
        { name: 'Gehäuse Typ A', menge: 1, einheit: 'Stk', ref_id: 100000010 },
        { name: 'Schraube M5 DIN912', menge: 10, einheit: 'Stk', ref_id: 100000003 },
        { name: 'Motor EC-42', menge: 1, einheit: 'Stk', ref_id: 100000015 },
        { name: 'Steuerplatine v2', menge: 1, einheit: 'Stk', ref_id: 100000021 },
      ],
      ausgefuehrt_von: 'Max Muster',
      ausgefuehrt_am: '08:12',
      ergebnis: 'Material OK',
    },
    {
      id: 2,
      position: 2,
      beschreibung: 'Montage',
      status: 'aktiv',
      ressourcen: [
        { name: 'Schraube M5 DIN912', menge: 10, einheit: 'Stk', ref_id: 100000003 },
      ],
      daten_felder: [
        { name: 'Seriennummer', typ: 'text', pflicht: true },
        { name: 'Anzugsmoment Schrauben', typ: 'number', pflicht: true, einheit: 'Nm' },
      ],
      ergebnis_optionen: [
        { label: 'Montage OK — weiter zu Test', farbe: 'gruen' },
        { label: 'Problem — NCR auslösen', farbe: 'rot' },
      ],
    },
    {
      id: 3,
      position: 3,
      beschreibung: 'Funktionstest',
      status: 'ausstehend',
      daten_felder: [
        { name: 'Testprotokoll Nr.', typ: 'text', pflicht: true },
        { name: 'Leistung gemessen', typ: 'number', pflicht: true, einheit: 'W' },
        { name: 'Temperatur gemessen', typ: 'number', pflicht: true, einheit: '°C' },
      ],
      ergebnis_optionen: [
        { label: 'Test bestanden', farbe: 'gruen' },
        { label: 'Nacharbeit nötig', farbe: 'gelb' },
        { label: 'Verschrotten', farbe: 'rot' },
      ],
    },
    {
      id: 4,
      position: 4,
      beschreibung: 'Einlagern',
      status: 'ausstehend',
      daten_felder: [
        { name: 'Lagerort', typ: 'text', pflicht: true },
      ],
      system_aktion: 'lager_verbuchen → Status VERFÜGBAR',
      ergebnis_optionen: [
        { label: 'Eingelagert', farbe: 'gruen' },
      ],
    },
  ],
};

// ─── Step Execution Modal ─────────────────────────────────────────────────────

function SchrittModal({
  schritt,
  onClose,
  onComplete,
}: {
  schritt: ProzessSchritt;
  onClose: () => void;
  onComplete: (ergebnis: string, daten: Record<string, string>) => void;
}) {
  const [daten, setDaten] = useState<Record<string, string>>({});
  const [ergebnis, setErgebnis] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const pflichtErfuellt = !schritt.daten_felder ||
    schritt.daten_felder.filter(f => f.pflicht).every(f => (daten[f.name] ?? '').trim() !== '');
  const ergebnisErfuellt = !schritt.ergebnis_optionen || schritt.ergebnis_optionen.length === 0 || ergebnis !== null;
  const canComplete = pflichtErfuellt && ergebnisErfuellt;

  async function handleComplete() {
    if (!canComplete) return;
    setSaving(true);
    await new Promise(r => setTimeout(r, 700));
    onComplete(ergebnis ?? 'Erledigt', daten);
  }

  return (
    <div className="fixed inset-0 bg-black/50 flex items-end sm:items-center justify-center z-50 p-0 sm:p-4">
      <div className="bg-white w-full sm:rounded-xl sm:shadow-2xl sm:max-w-lg max-h-[90vh] flex flex-col">
        {/* Header */}
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

        {/* Body */}
        <div className="flex-1 overflow-y-auto px-5 py-4 space-y-5">

          {/* Ressourcen */}
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

          {/* System-Aktion */}
          {schritt.system_aktion && (
            <div className="flex items-center gap-2.5 rounded-lg bg-blue-50 border border-blue-100 px-3 py-2.5">
              <Zap className="h-4 w-4 text-blue-600 shrink-0" />
              <div>
                <p className="text-xs font-semibold text-blue-700">Automatische System-Aktion</p>
                <p className="text-xs text-blue-600 mt-0.5">{schritt.system_aktion}</p>
              </div>
            </div>
          )}

          {/* Datenfelder */}
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

          {/* Ergebnis */}
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
        </div>

        {/* Footer */}
        <div className="px-5 py-4 border-t border-slate-200 shrink-0 flex gap-3">
          <button
            onClick={onClose}
            className="flex-1 rounded-lg border border-slate-200 px-4 py-2.5 text-sm font-medium text-slate-700 hover:bg-slate-50 transition-colors"
          >
            Abbrechen
          </button>
          <button
            onClick={handleComplete}
            disabled={!canComplete || saving}
            className={cn(
              'flex-1 rounded-lg px-4 py-2.5 text-sm font-semibold flex items-center justify-center gap-2 transition-colors',
              canComplete && !saving
                ? 'bg-blue-600 text-white hover:bg-blue-700'
                : 'bg-slate-100 text-slate-400 cursor-not-allowed',
            )}
          >
            {saving
              ? <><Loader2 className="h-4 w-4 animate-spin" /> Wird gespeichert…</>
              : <><Check className="h-4 w-4" /> Abschliessen</>
            }
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── Main Panel ───────────────────────────────────────────────────────────────

export function ObjektProzessPanel({ initialData = DEMO_KAFFEEMASCHINE }: { initialData?: DemoObjekt }) {
  const [objekt, setObjekt] = useState<DemoObjekt>(initialData);
  const [activeModal, setActiveModal] = useState<ProzessSchritt | null>(null);

  const doneCount = objekt.schritte.filter(s => s.status === 'erledigt').length;
  const totalCount = objekt.schritte.length;
  const allDone = doneCount === totalCount;

  const trackerSteps: ProcessStep[] = objekt.schritte.map(s => ({
    key: String(s.id),
    label: s.beschreibung.split(' ')[0],
  }));

  const activeSchritt = objekt.schritte.find(s => s.status === 'aktiv');
  const currentTrackerKey = activeSchritt
    ? String(activeSchritt.id)
    : allDone
      ? String(objekt.schritte[totalCount - 1].id + 1) // past last = all done
      : String(objekt.schritte[0].id);

  function handleComplete(schritt: ProzessSchritt, ergebnis: string, daten: Record<string, string>) {
    const now = new Date().toLocaleTimeString('de-CH', { hour: '2-digit', minute: '2-digit' });
    setObjekt(prev => {
      const schritte = prev.schritte.map((s, i) => {
        if (s.id === schritt.id) {
          return { ...s, status: 'erledigt' as const, ausgefuehrt_von: 'Du', ausgefuehrt_am: now, ergebnis, erfasste_daten: daten };
        }
        if (s.status === 'ausstehend' && prev.schritte[i - 1]?.id === schritt.id) {
          return { ...s, status: 'aktiv' as const };
        }
        return s;
      });
      return { ...prev, schritte };
    });
    setActiveModal(null);
  }

  return (
    <div className="flex-1 flex flex-col overflow-hidden bg-white">
      {/* Header */}
      <div className="px-6 py-4 border-b border-slate-200 shrink-0">
        <div className="flex items-start justify-between mb-1">
          <div className="min-w-0">
            <p className="text-xs font-mono text-slate-400">{formatObjectId(objekt.id)}</p>
            <h2 className="text-lg font-semibold text-slate-900 leading-tight">{objekt.name}</h2>
            {objekt.auftrag_ref && (
              <p className="text-xs text-slate-500 mt-0.5 flex items-center gap-1">
                <Clock className="h-3 w-3" />{objekt.auftrag_ref}
              </p>
            )}
          </div>
          <span className={cn(
            'shrink-0 ml-3 rounded-full px-2.5 py-1 text-xs font-semibold',
            allDone ? 'bg-green-100 text-green-700' : 'bg-blue-100 text-blue-700',
          )}>
            {allDone ? 'VERFÜGBAR' : 'IN PRODUKTION'}
          </span>
        </div>

        {/* Progress bar */}
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

        {/* ProcessTracker */}
        <div className="mt-4 overflow-x-auto pb-1">
          <ProcessTracker steps={trackerSteps} currentStep={currentTrackerKey} />
        </div>
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
                <MapPin className="h-3 w-3" /> Objekt ist jetzt VERFÜGBAR im Lager
              </p>
            </div>
          </div>
        )}

        {objekt.schritte.map(schritt => (
          <div
            key={schritt.id}
            className={cn(
              'rounded-xl border transition-all',
              schritt.status === 'erledigt' && 'border-green-100 bg-green-50/60',
              schritt.status === 'aktiv' && 'border-blue-200 bg-blue-50 shadow-sm ring-1 ring-blue-100',
              schritt.status === 'ausstehend' && 'border-slate-100 bg-white opacity-60',
            )}
          >
            <div className="flex items-start gap-3 px-4 py-3">
              {/* Status dot */}
              <div className={cn(
                'mt-0.5 flex h-7 w-7 items-center justify-center rounded-full shrink-0 text-xs font-bold',
                schritt.status === 'erledigt' && 'bg-green-500 text-white',
                schritt.status === 'aktiv' && 'bg-blue-600 text-white',
                schritt.status === 'ausstehend' && 'bg-slate-100 text-slate-400',
              )}>
                {schritt.status === 'erledigt'
                  ? <Check className="h-3.5 w-3.5" />
                  : schritt.position}
              </div>

              {/* Content */}
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
                      ✓ {schritt.ausgefuehrt_von} · {schritt.ausgefuehrt_am}
                    </span>
                    {schritt.ergebnis && (
                      <span className="text-xs font-medium text-green-700">{schritt.ergebnis}</span>
                    )}
                    {schritt.erfasste_daten && Object.entries(schritt.erfasste_daten).map(([k, v]) => (
                      <span key={k} className="text-xs text-slate-500">{k}: <span className="font-medium text-slate-700">{v}</span></span>
                    ))}
                  </div>
                )}

                {schritt.status === 'aktiv' && (
                  <div className="mt-1 flex flex-wrap gap-2">
                    {schritt.ressourcen && schritt.ressourcen.length > 0 && (
                      <span className="text-xs bg-amber-100 text-amber-700 rounded-md px-1.5 py-0.5">
                        {schritt.ressourcen.length} Ressource{schritt.ressourcen.length !== 1 ? 'n' : ''}
                      </span>
                    )}
                    {schritt.daten_felder && schritt.daten_felder.length > 0 && (
                      <span className="text-xs bg-blue-100 text-blue-700 rounded-md px-1.5 py-0.5">
                        {schritt.daten_felder.length} Datenfeld{schritt.daten_felder.length !== 1 ? 'er' : ''}
                      </span>
                    )}
                    {schritt.system_aktion && (
                      <span className="text-xs bg-violet-100 text-violet-700 rounded-md px-1.5 py-0.5 flex items-center gap-1">
                        <Zap className="h-3 w-3" /> System-Aktion
                      </span>
                    )}
                  </div>
                )}
              </div>

              {/* Execute button */}
              {schritt.status === 'aktiv' && (
                <button
                  onClick={() => setActiveModal(schritt)}
                  className="shrink-0 flex items-center gap-1.5 rounded-lg bg-blue-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-blue-700 active:bg-blue-800 transition-colors"
                >
                  Ausführen <ChevronRight className="h-3.5 w-3.5" />
                </button>
              )}
            </div>

            {/* Expanded detail for active step */}
            {schritt.status === 'aktiv' && schritt.ressourcen && schritt.ressourcen.length > 0 && (
              <div className="px-4 pb-3 border-t border-blue-100 mt-0 pt-2.5 space-y-1.5">
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

      {/* Modal */}
      {activeModal && (
        <SchrittModal
          schritt={activeModal}
          onClose={() => setActiveModal(null)}
          onComplete={(ergebnis, daten) => handleComplete(activeModal, ergebnis, daten)}
        />
      )}
    </div>
  );
}
