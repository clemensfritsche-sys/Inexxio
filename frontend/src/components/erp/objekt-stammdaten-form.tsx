'use client';

import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Plus, Trash2, ChevronUp, ChevronDown, Loader2, Check,
  Lock, Package, Settings2, ArrowLeft, X, Search,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { formatObjectId } from '@/lib/utils';
import { api } from '@/lib/api';
import { OBJ_STATUS_CONFIG } from '@/types';
import { ObjektProzessPanel } from './objekt-prozess-panel';
import type {
  UniObjekt, ProzessSchrittDef, UniObjektSummary,
  RessourceDef, DatenFeldDef, ErgebnisOption,
} from '@/types';

// ─── Status badge ──────────────────────────────────────────────────────────────

function ObjStatusBadge({ status }: { status: string | null }) {
  const cfg = status && status in OBJ_STATUS_CONFIG
    ? OBJ_STATUS_CONFIG[status as keyof typeof OBJ_STATUS_CONFIG]
    : { label: status ?? '—', color: 'bg-slate-100 text-slate-600' };
  return (
    <span className={cn('inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold', cfg.color)}>
      {cfg.label}
    </span>
  );
}

// ─── Referenz-Objekt picker ────────────────────────────────────────────────────

function ReferenzObjektPicker({
  value,
  menge,
  onChange,
}: {
  value: number | null;
  menge: number;
  onChange: (id: number | null, menge: number, name?: string) => void;
}) {
  const [search, setSearch] = useState('');
  const [open, setOpen] = useState(false);

  const { data } = useQuery({
    queryKey: ['uni-objekte-freigegeben', search],
    queryFn: () => api.listUniObjekte({ stamm: true, q: search || undefined, page_size: 20 }),
    staleTime: 15_000,
  });

  const freigegeben = (data?.items ?? []).filter(o => o.obj_status === 'FREIGEGEBEN');

  const selectedObj = value
    ? (data?.items ?? []).find(o => o.id === value)
    : null;

  return (
    <div className="space-y-2">
      <div className="relative">
        <button
          type="button"
          onClick={() => setOpen(v => !v)}
          className="w-full flex items-center gap-2 rounded-lg border border-slate-200 px-3 py-2 text-sm text-left hover:border-blue-300 transition-colors"
        >
          <Search className="h-3.5 w-3.5 text-slate-400 shrink-0" />
          {selectedObj ? (
            <span className="flex-1 text-slate-800">{selectedObj.name} <span className="text-slate-400 font-mono text-xs">{formatObjectId(selectedObj.id)}</span></span>
          ) : (
            <span className="flex-1 text-slate-400">Objekt suchen…</span>
          )}
          {value && (
            <button
              type="button"
              onClick={e => { e.stopPropagation(); onChange(null, 1); }}
              className="p-0.5 text-slate-400 hover:text-red-500 transition-colors"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          )}
        </button>

        {open && (
          <div className="absolute top-full left-0 right-0 mt-1 z-40 bg-white rounded-xl border border-slate-200 shadow-lg overflow-hidden">
            <div className="p-2 border-b border-slate-100">
              <input
                autoFocus
                value={search}
                onChange={e => setSearch(e.target.value)}
                placeholder="Suchen…"
                className="w-full rounded-lg border border-slate-200 px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <div className="max-h-48 overflow-y-auto">
              {freigegeben.length === 0 && (
                <p className="text-xs text-slate-400 px-3 py-3 text-center">Keine freigegebenen Objekte gefunden</p>
              )}
              {freigegeben.map(obj => (
                <button
                  key={obj.id}
                  type="button"
                  onClick={() => { onChange(obj.id, menge, obj.name ?? ''); setOpen(false); setSearch(''); }}
                  className={cn(
                    'w-full flex items-center gap-3 px-3 py-2.5 text-sm text-left hover:bg-slate-50 transition-colors',
                    value === obj.id && 'bg-blue-50',
                  )}
                >
                  <span className="flex-1">{obj.name}</span>
                  <span className="text-xs font-mono text-slate-400">{formatObjectId(obj.id)}</span>
                </button>
              ))}
            </div>
          </div>
        )}
      </div>

      {value && (
        <div className="flex items-center gap-2">
          <label className="text-xs text-slate-500 shrink-0">Menge:</label>
          <input
            type="number"
            min={1}
            max={1000}
            value={menge}
            onChange={e => onChange(value, Math.max(1, parseInt(e.target.value) || 1))}
            className="w-24 rounded-lg border border-slate-200 px-2.5 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          <span className="text-xs text-slate-400">Instanzen werden beim Ausführen dieses Schritts erstellt</span>
        </div>
      )}
    </div>
  );
}

// ─── Schritt-Detail-Editor Modal ──────────────────────────────────────────────

function SchrittDetailModal({
  schritt,
  objektId,
  onClose,
}: {
  schritt: ProzessSchrittDef;
  objektId: number;
  onClose: () => void;
}) {
  const qc = useQueryClient();

  const [desc, setDesc] = useState(schritt.beschreibung);
  const [ressourcen, setRessourcen] = useState<RessourceDef[]>(schritt.ressourcen ?? []);
  const [datenFelder, setDatenFelder] = useState<DatenFeldDef[]>(schritt.daten_felder ?? []);
  const [ergebnisse, setErgebnisse] = useState<ErgebnisOption[]>(schritt.ergebnis_optionen ?? []);
  const [refObjektId, setRefObjektId] = useState<number | null>(schritt.referenz_objekt_id ?? null);
  const [refMenge, setRefMenge] = useState<number>(schritt.referenz_menge ?? 1);

  const { mutate: save, isPending, error } = useMutation({
    mutationFn: () =>
      api.updateSchritt(objektId, schritt.id, {
        beschreibung: desc.trim() || schritt.beschreibung,
        ressourcen: ressourcen.length > 0 ? ressourcen : undefined,
        daten_felder: datenFelder.length > 0 ? datenFelder.map(f => ({ ...f, pflicht: true })) : undefined,
        ergebnis_optionen: ergebnisse.length > 0 ? ergebnisse : undefined,
        referenz_objekt_id: refObjektId ?? undefined,
        referenz_menge: refMenge,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['uni-objekt', objektId] });
      onClose();
    },
  });

  const addRessource = () => setRessourcen(p => [...p, { name: '', menge: 1, einheit: 'Stk' }]);
  const updateRessource = (i: number, field: keyof RessourceDef, val: string | number) =>
    setRessourcen(p => p.map((r, idx) => idx === i ? { ...r, [field]: val } : r));
  const removeRessource = (i: number) => setRessourcen(p => p.filter((_, idx) => idx !== i));

  const addDatenFeld = () => setDatenFelder(p => [...p, { name: '', typ: 'text', pflicht: true }]);
  const updateDatenFeld = (i: number, field: keyof DatenFeldDef, val: string | boolean) =>
    setDatenFelder(p => p.map((f, idx) => idx === i ? { ...f, [field]: val } : f));
  const removeDatenFeld = (i: number) => setDatenFelder(p => p.filter((_, idx) => idx !== i));

  const addErgebnis = () => setErgebnisse(p => [...p, { label: '', farbe: 'gruen' }]);
  const updateErgebnis = (i: number, field: keyof ErgebnisOption, val: string) =>
    setErgebnisse(p => p.map((e, idx) => idx === i ? { ...e, [field]: val } : e));
  const removeErgebnis = (i: number) => setErgebnisse(p => p.filter((_, idx) => idx !== i));

  const inputCls = 'rounded-lg border border-slate-200 px-2.5 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500';

  return (
    <div className="fixed inset-0 bg-black/50 flex items-end sm:items-center justify-center z-50 p-0 sm:p-4">
      <div className="bg-white w-full sm:rounded-xl sm:shadow-2xl sm:max-w-2xl max-h-[90vh] flex flex-col">
        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-200 shrink-0">
          <div>
            <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-0.5">Schritt {schritt.position}</p>
            <h3 className="text-base font-semibold text-slate-900">Details bearbeiten</h3>
          </div>
          <button onClick={onClose} className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 transition-colors">
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-5 py-4 space-y-6">
          {/* Beschreibung */}
          <div>
            <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">Beschreibung</label>
            <input value={desc} onChange={e => setDesc(e.target.value)} className={cn(inputCls, 'w-full')} placeholder="Schrittbeschreibung…" />
          </div>

          {/* Ressourcen */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="text-xs font-semibold text-slate-500 uppercase tracking-wider">📦 Ressourcen ({ressourcen.length})</label>
              <button type="button" onClick={addRessource} className="text-xs text-blue-600 hover:text-blue-800 font-medium flex items-center gap-1">
                <Plus className="h-3.5 w-3.5" /> Hinzufügen
              </button>
            </div>
            {ressourcen.length === 0 && (
              <p className="text-xs text-slate-400 italic py-2">Keine Ressourcen — Material das bereitgestellt werden muss.</p>
            )}
            <div className="space-y-2">
              {ressourcen.map((r, i) => (
                <div key={i} className="flex items-center gap-2">
                  <input value={r.name} onChange={e => updateRessource(i, 'name', e.target.value)} placeholder="Name / Artikel" className={cn(inputCls, 'flex-1')} />
                  <input type="number" value={r.menge} min={0.001} step="any" onChange={e => updateRessource(i, 'menge', parseFloat(e.target.value) || 0)} className={cn(inputCls, 'w-20')} />
                  <input value={r.einheit} onChange={e => updateRessource(i, 'einheit', e.target.value)} placeholder="Stk" className={cn(inputCls, 'w-16')} />
                  <button type="button" onClick={() => removeRessource(i)} className="p-1.5 text-slate-400 hover:text-red-600 transition-colors"><Trash2 className="h-3.5 w-3.5" /></button>
                </div>
              ))}
            </div>
          </div>

          {/* Datenfelder — all mandatory */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="text-xs font-semibold text-slate-500 uppercase tracking-wider">📋 Datenfelder ({datenFelder.length})</label>
              <button type="button" onClick={addDatenFeld} className="text-xs text-blue-600 hover:text-blue-800 font-medium flex items-center gap-1">
                <Plus className="h-3.5 w-3.5" /> Hinzufügen
              </button>
            </div>
            {datenFelder.length === 0 && (
              <p className="text-xs text-slate-400 italic py-2">Keine Datenfelder — Werte die beim Ausführen erfasst werden. Alle Felder sind Pflichtfelder.</p>
            )}
            <div className="space-y-2">
              {datenFelder.map((f, i) => (
                <div key={i} className="flex items-center gap-2">
                  <input value={f.name} onChange={e => updateDatenFeld(i, 'name', e.target.value)} placeholder="Feldname" className={cn(inputCls, 'flex-1')} />
                  <select value={f.typ} onChange={e => updateDatenFeld(i, 'typ', e.target.value)} className={cn(inputCls, 'w-28')}>
                    <option value="text">Text</option>
                    <option value="number">Zahl</option>
                    <option value="datum">Datum</option>
                    <option value="auswahl">Auswahl</option>
                  </select>
                  <input value={f.einheit ?? ''} onChange={e => updateDatenFeld(i, 'einheit', e.target.value)} placeholder="Einheit" className={cn(inputCls, 'w-16')} />
                  <button type="button" onClick={() => removeDatenFeld(i)} className="p-1.5 text-slate-400 hover:text-red-600 transition-colors"><Trash2 className="h-3.5 w-3.5" /></button>
                </div>
              ))}
            </div>
          </div>

          {/* Ergebnis-Optionen */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="text-xs font-semibold text-slate-500 uppercase tracking-wider">✅ Ergebnis-Optionen ({ergebnisse.length})</label>
              <button type="button" onClick={addErgebnis} className="text-xs text-blue-600 hover:text-blue-800 font-medium flex items-center gap-1">
                <Plus className="h-3.5 w-3.5" /> Hinzufügen
              </button>
            </div>
            {ergebnisse.length === 0 && (
              <p className="text-xs text-slate-400 italic py-2">
                Keine Optionen definiert — mind. 1 Option erforderlich zum Ausführen.
              </p>
            )}
            <div className="space-y-2">
              {ergebnisse.map((e, i) => (
                <div key={i} className="flex items-center gap-2">
                  <input value={e.label} onChange={ev => updateErgebnis(i, 'label', ev.target.value)} placeholder="Ergebnisbezeichnung" className={cn(inputCls, 'flex-1')} />
                  <select value={e.farbe} onChange={ev => updateErgebnis(i, 'farbe', ev.target.value)} className={cn(inputCls, 'w-36')}>
                    <option value="gruen">🟢 Grün (OK)</option>
                    <option value="gelb">🟡 Gelb (Warnung)</option>
                    <option value="rot">🔴 Rot (Fehler/Stop)</option>
                  </select>
                  <button type="button" onClick={() => removeErgebnis(i)} className="p-1.5 text-slate-400 hover:text-red-600 transition-colors"><Trash2 className="h-3.5 w-3.5" /></button>
                </div>
              ))}
            </div>
          </div>

          {/* Referenz-Objekt */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="text-xs font-semibold text-slate-500 uppercase tracking-wider">🔗 Referenz-Objekt</label>
              {refObjektId && (
                <span className="text-xs text-blue-600 bg-blue-50 px-2 py-0.5 rounded">
                  Erstellt {refMenge}× beim Ausführen
                </span>
              )}
            </div>
            <p className="text-xs text-slate-400 mb-2">
              Optional: Wenn dieser Schritt ausgeführt wird, werden automatisch N Instanzen des gewählten Objekts erstellt.
            </p>
            <ReferenzObjektPicker
              value={refObjektId}
              menge={refMenge}
              onChange={(id, m) => { setRefObjektId(id); setRefMenge(m); }}
            />
          </div>

          {error && (
            <p className="text-sm text-red-600 bg-red-50 rounded-lg px-3 py-2">{(error as Error).message}</p>
          )}
        </div>

        <div className="px-5 py-4 border-t border-slate-200 shrink-0 flex gap-3">
          <button onClick={onClose} className="flex-1 rounded-lg border border-slate-200 px-4 py-2.5 text-sm font-medium text-slate-700 hover:bg-slate-50 transition-colors">
            Abbrechen
          </button>
          <button
            onClick={() => save()}
            disabled={isPending}
            className="flex-1 rounded-lg bg-blue-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-50 transition-colors flex items-center justify-center gap-2"
          >
            {isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Check className="h-4 w-4" />}
            Speichern
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── Schritt card ─────────────────────────────────────────────────────────────

function SchrittCard({
  schritt, isFirst, isLast, onDelete, onMoveUp, onMoveDown, objektId, readonly,
}: {
  schritt: ProzessSchrittDef;
  isFirst: boolean;
  isLast: boolean;
  onDelete: () => void;
  onMoveUp: () => void;
  onMoveDown: () => void;
  objektId: number;
  readonly: boolean;
}) {
  const qc = useQueryClient();
  const [editing, setEditing] = useState(false);
  const [text, setText] = useState(schritt.beschreibung);
  const [showDetail, setShowDetail] = useState(false);

  const { mutate: saveDesc } = useMutation({
    mutationFn: (desc: string) => api.updateSchritt(objektId, schritt.id, { beschreibung: desc }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['uni-objekt', objektId] }),
  });

  function handleBlur() {
    setEditing(false);
    if (text.trim() && text !== schritt.beschreibung) saveDesc(text.trim());
  }

  const hasRef = !!schritt.referenz_objekt_id;
  const hasMeta = (schritt.ressourcen?.length ?? 0) > 0 ||
    (schritt.daten_felder?.length ?? 0) > 0 ||
    (schritt.ergebnis_optionen?.length ?? 0) > 0 ||
    hasRef;

  return (
    <>
      <div className={cn('rounded-xl border bg-white', readonly ? 'border-slate-100 opacity-80' : 'border-slate-200')}>
        <div className="flex items-start gap-3 px-4 py-3">
          <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-slate-100 text-xs font-bold text-slate-600 mt-0.5">
            {schritt.position}
          </div>
          <div className="flex-1 min-w-0">
            {editing && !readonly ? (
              <input
                autoFocus
                value={text}
                onChange={e => setText(e.target.value)}
                onBlur={handleBlur}
                onKeyDown={e => {
                  if (e.key === 'Enter') handleBlur();
                  if (e.key === 'Escape') { setText(schritt.beschreibung); setEditing(false); }
                }}
                className="w-full rounded-lg border border-blue-300 px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
              />
            ) : (
              <p
                className={cn('text-sm text-slate-800', !readonly && 'cursor-pointer hover:text-blue-700 transition-colors')}
                onClick={() => !readonly && setEditing(true)}
              >
                {schritt.beschreibung}
              </p>
            )}
            {hasMeta && (
              <div className="flex flex-wrap gap-1.5 mt-1.5">
                {(schritt.ressourcen?.length ?? 0) > 0 && (
                  <span className="text-xs bg-amber-50 text-amber-700 rounded px-1.5 py-0.5">
                    📦 {schritt.ressourcen!.length} Ressource{schritt.ressourcen!.length !== 1 ? 'n' : ''}
                  </span>
                )}
                {(schritt.daten_felder?.length ?? 0) > 0 && (
                  <span className="text-xs bg-blue-50 text-blue-700 rounded px-1.5 py-0.5">
                    📋 {schritt.daten_felder!.length} Datenfeld{schritt.daten_felder!.length !== 1 ? 'er' : ''}
                  </span>
                )}
                {(schritt.ergebnis_optionen?.length ?? 0) > 0 && (
                  <span className="text-xs bg-green-50 text-green-700 rounded px-1.5 py-0.5">
                    ✅ {schritt.ergebnis_optionen!.length} Ergebnis{schritt.ergebnis_optionen!.length !== 1 ? 'se' : ''}
                  </span>
                )}
                {hasRef && (
                  <span className="text-xs bg-violet-50 text-violet-700 rounded px-1.5 py-0.5">
                    🔗 {schritt.referenz_menge}× Objekt
                  </span>
                )}
              </div>
            )}
          </div>
          {!readonly && (
            <div className="flex items-center gap-1 shrink-0">
              <button type="button" onClick={() => setShowDetail(true)} title="Details bearbeiten" className="p-1 rounded text-slate-400 hover:text-blue-600 transition-colors">
                <Settings2 className="h-4 w-4" />
              </button>
              <button type="button" disabled={isFirst} onClick={onMoveUp} className="p-1 rounded text-slate-400 hover:text-slate-600 disabled:opacity-30 transition-colors">
                <ChevronUp className="h-4 w-4" />
              </button>
              <button type="button" disabled={isLast} onClick={onMoveDown} className="p-1 rounded text-slate-400 hover:text-slate-600 disabled:opacity-30 transition-colors">
                <ChevronDown className="h-4 w-4" />
              </button>
              <button type="button" onClick={onDelete} className="p-1 rounded text-slate-400 hover:text-red-600 transition-colors">
                <Trash2 className="h-4 w-4" />
              </button>
            </div>
          )}
        </div>
      </div>

      {showDetail && (
        <SchrittDetailModal
          schritt={schritt}
          objektId={objektId}
          onClose={() => setShowDetail(false)}
        />
      )}
    </>
  );
}

// ─── Add step form ─────────────────────────────────────────────────────────────

function AddSchrittForm({ objektId, nextPosition, onDone }: { objektId: number; nextPosition: number; onDone: () => void }) {
  const qc = useQueryClient();
  const [desc, setDesc] = useState('');
  const { mutate, isPending } = useMutation({
    mutationFn: () => api.addSchritt(objektId, { position: nextPosition, beschreibung: desc.trim() }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['uni-objekt', objektId] }); setDesc(''); onDone(); },
  });
  return (
    <div className="flex gap-2 mt-2">
      <input
        autoFocus
        value={desc}
        onChange={e => setDesc(e.target.value)}
        placeholder="Schrittbeschreibung eingeben…"
        onKeyDown={e => { if (e.key === 'Enter' && desc.trim()) mutate(); if (e.key === 'Escape') onDone(); }}
        className="flex-1 rounded-lg border border-slate-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
      />
      <button
        type="button"
        disabled={!desc.trim() || isPending}
        onClick={() => mutate()}
        className="rounded-lg bg-blue-600 px-3 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-50 transition-colors flex items-center gap-1.5"
      >
        {isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Check className="h-4 w-4" />}
        Hinzufügen
      </button>
      <button type="button" onClick={onDone} className="rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-600 hover:bg-slate-50 transition-colors">
        Abbrechen
      </button>
    </div>
  );
}

// ─── Neue Instanz Dialog (in Instanzen tab) ────────────────────────────────────

function NeueInstanzDialog({
  objekt,
  onClose,
  onDone,
}: {
  objekt: UniObjekt;
  onClose: () => void;
  onDone: (instances: UniObjektSummary[]) => void;
}) {
  const [lagerort, setLagerort] = useState('');
  const { mutate, isPending, error } = useMutation({
    mutationFn: () => api.ausfuehren(objekt.id, { menge: 1, lagerort: lagerort.trim() || undefined }),
    onSuccess: onDone,
  });

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-xl shadow-2xl w-full max-w-sm">
        <div className="px-5 py-4 border-b border-slate-200">
          <h3 className="text-base font-semibold text-slate-900">Neue Instanz erstellen</h3>
          <p className="text-sm text-slate-500 mt-0.5">{objekt.name} · {objekt.schritte.length} Prozessschritte</p>
        </div>
        <div className="px-5 py-4 space-y-4">
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1.5">Lagerort / Ort (optional)</label>
            <input
              type="text"
              value={lagerort}
              onChange={e => setLagerort(e.target.value)}
              placeholder="z.B. Arbeitsplatz 3"
              className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          {error && <p className="text-sm text-red-600">{(error as Error).message}</p>}
        </div>
        <div className="px-5 py-4 border-t border-slate-200 flex gap-3">
          <button type="button" onClick={onClose} className="flex-1 rounded-lg border border-slate-200 px-4 py-2.5 text-sm font-medium text-slate-700 hover:bg-slate-50 transition-colors">
            Abbrechen
          </button>
          <button
            type="button"
            disabled={isPending}
            onClick={() => mutate()}
            className="flex-1 rounded-lg bg-blue-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-50 transition-colors flex items-center justify-center gap-2"
          >
            {isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}
            Erstellen
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── Instanzen tab ────────────────────────────────────────────────────────────

function InstanzenTab({
  objekt,
  onSelectInstance,
}: {
  objekt: UniObjekt;
  onSelectInstance: (id: number) => void;
}) {
  const qc = useQueryClient();
  const [showCreate, setShowCreate] = useState(false);
  const canCreate = objekt.obj_status === 'FREIGEGEBEN';

  const { data, isLoading } = useQuery({
    queryKey: ['uni-objekt-instanzen', objekt.id],
    queryFn: () => api.listInstanzen(objekt.id),
    staleTime: 10_000,
  });

  return (
    <div className="space-y-3">
      {canCreate && (
        <button
          type="button"
          onClick={() => setShowCreate(true)}
          className="flex w-full items-center justify-center gap-2 rounded-xl border-2 border-dashed border-blue-200 py-3 text-sm text-blue-600 hover:border-blue-400 hover:bg-blue-50/50 transition-colors"
        >
          <Plus className="h-4 w-4" />
          Neue Instanz erstellen
        </button>
      )}

      {!canCreate && objekt.obj_status === 'ENTWURF' && (
        <div className="rounded-lg bg-amber-50 border border-amber-100 px-4 py-3 text-xs text-amber-700">
          Vorlage muss zuerst freigegeben werden, bevor Instanzen erstellt werden können.
        </div>
      )}

      {isLoading && <div className="flex justify-center py-8"><Loader2 className="h-5 w-5 animate-spin text-slate-400" /></div>}

      {!isLoading && !data?.items.length && (
        <div className="text-center py-8">
          <p className="text-sm text-slate-500">Noch keine Instanzen vorhanden.</p>
          <p className="text-xs text-slate-400 mt-1">Instanzen können auch durch Prozessschritte anderer Objekte erstellt werden.</p>
        </div>
      )}

      {data?.items.map(inst => {
        const cfg = inst.obj_status && inst.obj_status in OBJ_STATUS_CONFIG
          ? OBJ_STATUS_CONFIG[inst.obj_status as keyof typeof OBJ_STATUS_CONFIG]
          : { label: inst.obj_status ?? '—', color: 'bg-slate-100 text-slate-600' };
        return (
          <button
            key={inst.id}
            type="button"
            onClick={() => onSelectInstance(inst.id)}
            className="w-full flex items-center justify-between rounded-xl border border-slate-200 px-4 py-3 hover:bg-slate-50 transition-colors text-left"
          >
            <div>
              <p className="text-xs font-mono text-slate-400">{formatObjectId(inst.id)}</p>
              <p className="text-sm font-medium text-slate-800">{inst.name}</p>
              {inst.lagerort && <p className="text-xs text-slate-500 mt-0.5">{inst.lagerort}</p>}
            </div>
            <span className={cn('rounded-full px-2.5 py-0.5 text-xs font-semibold shrink-0', cfg.color)}>
              {cfg.label}
            </span>
          </button>
        );
      })}

      {data && data.total > 0 && (
        <p className="text-xs text-slate-400 text-right">{data.total} Instanz{data.total !== 1 ? 'en' : ''} gesamt</p>
      )}

      {showCreate && (
        <NeueInstanzDialog
          objekt={objekt}
          onClose={() => setShowCreate(false)}
          onDone={() => {
            setShowCreate(false);
            qc.invalidateQueries({ queryKey: ['uni-objekt-instanzen', objekt.id] });
            qc.invalidateQueries({ queryKey: ['uni-objekt', objekt.id] });
          }}
        />
      )}
    </div>
  );
}

// ─── Instance view (process panel embedded) ────────────────────────────────────

function InstanceView({ instanceId, onBack }: { instanceId: number; onBack: () => void }) {
  const { data, isLoading } = useQuery({
    queryKey: ['uni-objekt', instanceId],
    queryFn: () => api.getUniObjekt(instanceId),
    staleTime: 5_000,
  });

  return (
    <div className="flex flex-col flex-1 overflow-hidden">
      <button
        type="button"
        onClick={onBack}
        className="flex items-center gap-2 px-4 py-2.5 border-b border-slate-200 text-sm font-medium text-slate-600 hover:text-slate-900 hover:bg-slate-50 transition-colors shrink-0"
      >
        <ArrowLeft className="h-4 w-4" />
        Zurück zur Vorlage
      </button>
      {isLoading ? (
        <div className="flex flex-1 items-center justify-center">
          <Loader2 className="h-6 w-6 animate-spin text-slate-400" />
        </div>
      ) : data ? (
        <ObjektProzessPanel objekt={data} />
      ) : null}
    </div>
  );
}

// ─── Name combo field ──────────────────────────────────────────────────────────

function NameComboField({ objekt }: { objekt: UniObjekt }) {
  const qc = useQueryClient();
  const [val, setVal] = useState(objekt.name ?? '');

  const { data: typen } = useQuery({
    queryKey: ['objekttypen'],
    queryFn: () => api.listObjektTypen(),
    staleTime: 60_000,
  });

  const { mutate: saveName } = useMutation({
    mutationFn: (name: string) => api.updateUniObjekt(objekt.id, { name }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['uni-objekt', objekt.id] }),
  });

  function handleBlur() {
    if (val.trim() && val !== objekt.name) saveName(val.trim());
  }

  return (
    <div>
      <input
        list={`objtypen-${objekt.id}`}
        value={val}
        onChange={e => setVal(e.target.value)}
        onBlur={handleBlur}
        onKeyDown={e => { if (e.key === 'Enter') handleBlur(); }}
        placeholder="Name eingeben oder aus Liste wählen…"
        className="text-lg font-semibold text-slate-900 w-full rounded-lg border border-blue-300 px-2 py-0.5 focus:outline-none focus:ring-2 focus:ring-blue-400"
      />
      <datalist id={`objtypen-${objekt.id}`}>
        {(typen ?? []).map(t => <option key={t.id} value={t.name} />)}
      </datalist>
    </div>
  );
}

// ─── Main component ────────────────────────────────────────────────────────────

interface Props {
  objekt: UniObjekt;
  currentUserRole?: string;
  onRefresh?: () => void;
}

type Tab = 'stammdaten' | 'prozess' | 'instanzen';

export function ObjektStammdatenForm({ objekt, currentUserRole: _role, onRefresh }: Props) {
  const qc = useQueryClient();
  const [tab, setTab] = useState<Tab>('stammdaten');
  const [addingStep, setAddingStep] = useState(false);
  const [selectedInstanceId, setSelectedInstanceId] = useState<number | null>(null);

  const canEdit = objekt.obj_status === 'ENTWURF';
  const canFreigeben = objekt.obj_status === 'ENTWURF' && objekt.schritte.length > 0;

  const { mutate: freigeben, isPending: freigabeLoading } = useMutation({
    mutationFn: () => api.freigeben(objekt.id),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['uni-objekt', objekt.id] }); onRefresh?.(); },
  });

  const { mutate: deleteSchritt } = useMutation({
    mutationFn: (schrittId: number) => api.deleteSchritt(objekt.id, schrittId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['uni-objekt', objekt.id] }),
  });

  const { mutate: moveSchritt } = useMutation({
    mutationFn: ({ id, pos }: { id: number; pos: number }) =>
      api.updateSchritt(objekt.id, id, { position: pos }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['uni-objekt', objekt.id] }),
  });

  function handleMoveUp(schritt: ProzessSchrittDef) {
    const sorted = [...objekt.schritte].sort((a, b) => a.position - b.position);
    const idx = sorted.findIndex(s => s.id === schritt.id);
    if (idx <= 0) return;
    const prev = sorted[idx - 1];
    moveSchritt({ id: schritt.id, pos: prev.position });
    moveSchritt({ id: prev.id, pos: schritt.position });
  }

  function handleMoveDown(schritt: ProzessSchrittDef) {
    const sorted = [...objekt.schritte].sort((a, b) => a.position - b.position);
    const idx = sorted.findIndex(s => s.id === schritt.id);
    if (idx >= sorted.length - 1) return;
    const next = sorted[idx + 1];
    moveSchritt({ id: schritt.id, pos: next.position });
    moveSchritt({ id: next.id, pos: schritt.position });
  }

  if (selectedInstanceId !== null) {
    return (
      <InstanceView
        instanceId={selectedInstanceId}
        onBack={() => setSelectedInstanceId(null)}
      />
    );
  }

  const sortedSchritte = [...objekt.schritte].sort((a, b) => a.position - b.position);

  return (
    <div className="flex flex-col overflow-hidden flex-1 bg-white">
      {/* Header */}
      <div className="px-6 py-4 border-b border-slate-200 shrink-0">
        <div className="flex items-start gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-orange-50 text-orange-600 shrink-0 mt-0.5">
            <Package className="h-4 w-4" />
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-xs font-mono text-slate-400 mb-0.5">{formatObjectId(objekt.id)}</p>
            {canEdit ? (
              <NameComboField objekt={objekt} />
            ) : (
              <h2 className="text-lg font-semibold text-slate-900 leading-tight truncate">
                {objekt.name || <span className="text-slate-400 italic">Kein Name</span>}
              </h2>
            )}
          </div>
          <div className="shrink-0 flex flex-col items-end gap-2">
            <ObjStatusBadge status={objekt.obj_status} />
            {canFreigeben && (
              <button
                type="button"
                disabled={freigabeLoading}
                onClick={() => freigeben()}
                className="flex items-center gap-1.5 rounded-lg bg-green-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-green-700 disabled:opacity-50 transition-colors"
              >
                {freigabeLoading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Lock className="h-3.5 w-3.5" />}
                Freigeben
              </button>
            )}
          </div>
        </div>

        {/* Tabs */}
        <div className="flex gap-1 mt-4 -mb-px">
          {(['stammdaten', 'prozess', 'instanzen'] as Tab[]).map(t => (
            <button
              key={t}
              type="button"
              onClick={() => setTab(t)}
              className={cn(
                'px-3 py-1.5 text-sm font-medium rounded-t-lg border-b-2 transition-colors',
                tab === t
                  ? 'border-blue-600 text-blue-700 bg-blue-50/50'
                  : 'border-transparent text-slate-500 hover:text-slate-700 hover:bg-slate-50',
              )}
            >
              {t === 'stammdaten' ? 'Stammdaten' : t === 'prozess' ? `Prozess (${objekt.schritte.length})` : `Instanzen (${objekt.instanzen_count})`}
            </button>
          ))}
        </div>
      </div>

      {/* Body */}
      <div className="flex-1 overflow-y-auto px-6 py-4">
        {tab === 'stammdaten' && (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <dt className="text-xs font-medium text-slate-500 uppercase tracking-wide">Einheit</dt>
              <dd className="mt-1 text-sm text-slate-900">{objekt.einheit ?? '—'}</dd>
            </div>
            <div>
              <dt className="text-xs font-medium text-slate-500 uppercase tracking-wide">Status</dt>
              <dd className="mt-1"><ObjStatusBadge status={objekt.obj_status} /></dd>
            </div>
            <div className="sm:col-span-2">
              <dt className="text-xs font-medium text-slate-500 uppercase tracking-wide">Notiz</dt>
              {canEdit ? (
                <NotizEditor objekt={objekt} />
              ) : (
                <dd className="mt-1 text-sm text-slate-900 whitespace-pre-wrap">
                  {objekt.notiz || <span className="text-slate-400 italic">—</span>}
                </dd>
              )}
            </div>
            {!canEdit && (
              <div className="sm:col-span-2 flex items-center gap-2 rounded-lg bg-slate-50 border border-slate-200 px-3 py-2.5">
                <Lock className="h-3.5 w-3.5 text-slate-400 shrink-0" />
                <p className="text-xs text-slate-500">
                  Vorlage ist <strong>gesperrt</strong> — nur ENTWURF-Vorlagen können bearbeitet werden.
                </p>
              </div>
            )}
          </div>
        )}

        {tab === 'prozess' && (
          <div className="space-y-2">
            {sortedSchritte.length === 0 && !addingStep && canEdit && (
              <p className="text-sm text-slate-500 text-center py-8">Noch keine Schritte — auf ⚙ klicken nach dem Hinzufügen um Ressourcen &amp; Datenfelder zu konfigurieren.</p>
            )}
            {sortedSchritte.map((s, idx) => (
              <SchrittCard
                key={s.id}
                schritt={s}
                isFirst={idx === 0}
                isLast={idx === sortedSchritte.length - 1}
                objektId={objekt.id}
                readonly={!canEdit}
                onDelete={() => deleteSchritt(s.id)}
                onMoveUp={() => handleMoveUp(s)}
                onMoveDown={() => handleMoveDown(s)}
              />
            ))}
            {addingStep && (
              <AddSchrittForm
                objektId={objekt.id}
                nextPosition={sortedSchritte.length + 1}
                onDone={() => setAddingStep(false)}
              />
            )}
            {canEdit && !addingStep && (
              <button
                type="button"
                onClick={() => setAddingStep(true)}
                className="mt-1 flex w-full items-center justify-center gap-2 rounded-xl border-2 border-dashed border-slate-200 py-3 text-sm text-slate-500 hover:border-blue-300 hover:text-blue-600 transition-colors"
              >
                <Plus className="h-4 w-4" />
                Schritt hinzufügen
              </button>
            )}
            {!canEdit && (
              <div className="mt-3 rounded-lg bg-slate-50 border border-slate-200 px-4 py-3">
                <p className="text-xs text-slate-500 flex items-center gap-1.5">
                  <Lock className="h-3.5 w-3.5" />
                  Prozess gesperrt — Status: <ObjStatusBadge status={objekt.obj_status} />
                </p>
              </div>
            )}
          </div>
        )}

        {tab === 'instanzen' && (
          <InstanzenTab
            objekt={objekt}
            onSelectInstance={id => setSelectedInstanceId(id)}
          />
        )}
      </div>
    </div>
  );
}

// ─── Notiz inline editor ──────────────────────────────────────────────────────

function NotizEditor({ objekt }: { objekt: UniObjekt }) {
  const qc = useQueryClient();
  const [val, setVal] = useState(objekt.notiz ?? '');
  const [saved, setSaved] = useState(false);

  const { mutate } = useMutation({
    mutationFn: (notiz: string) => api.updateUniObjekt(objekt.id, { notiz }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['uni-objekt', objekt.id] });
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    },
  });

  return (
    <div className="mt-1">
      <textarea
        value={val}
        onChange={e => setVal(e.target.value)}
        onBlur={() => { if (val !== objekt.notiz) mutate(val); }}
        rows={3}
        className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
        placeholder="Notiz hinzufügen…"
      />
      {saved && <p className="text-xs text-green-600 mt-0.5">Gespeichert</p>}
    </div>
  );
}
