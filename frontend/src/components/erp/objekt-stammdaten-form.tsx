'use client';

import { useState, useRef, useEffect } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Plus, Trash2, ChevronUp, ChevronDown, Loader2, CheckCircle2,
  Lock, Search, AlertCircle,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { formatObjectId } from '@/lib/utils';
import { api } from '@/lib/api';
import { OBJ_STATUS_CONFIG } from '@/types';
import type {
  UniObjekt, ProzessSchrittDef, RessourceDef, DatenFeldDef, ErgebnisOption, ItemName,
} from '@/types';

// ─── Helpers ──────────────────────────────────────────────────────────────────

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

const ERGEBNIS_FARBEN = [
  { value: 'gruen', label: '🟢 Grün (OK)', cls: 'bg-green-100 text-green-700' },
  { value: 'gelb', label: '🟡 Gelb (Warnung)', cls: 'bg-amber-100 text-amber-700' },
  { value: 'rot', label: '🔴 Rot (Fehler)', cls: 'bg-red-100 text-red-700' },
];

const DATENFELD_TYPEN = [
  { value: 'text', label: 'Text' },
  { value: 'number', label: 'Zahl' },
  { value: 'datum', label: 'Datum' },
  { value: 'auswahl', label: 'Auswahl' },
];

// ─── Ressourcen inline (search by Objekt-Nummer) ──────────────────────────────

function RessourcenSection({
  ressourcen,
  canEdit,
  onUpdate,
}: {
  ressourcen: RessourceDef[];
  canEdit: boolean;
  onUpdate: (r: RessourceDef[]) => void;
}) {
  const [lookup, setLookup] = useState('');
  const [lookupErr, setLookupErr] = useState('');
  const [lookupLoading, setLookupLoading] = useState(false);

  async function handleLookup() {
    const nr = parseInt(lookup.trim(), 10);
    if (!nr) { setLookupErr('Bitte eine gültige 9-stellige Objekt-Nummer eingeben.'); return; }
    setLookupLoading(true);
    setLookupErr('');
    try {
      const obj = await api.lookupObjektByNummer(nr);
      if (ressourcen.some((r) => r.ref_id === obj.id)) {
        setLookupErr('Dieses Objekt ist bereits als Ressource eingetragen.'); return;
      }
      onUpdate([...ressourcen, { ref_id: obj.id, name: obj.name ?? String(obj.id), menge: 1, einheit: 'Stk' }]);
      setLookup('');
    } catch {
      setLookupErr('Kein freigegebenes Objekt mit dieser Nummer gefunden.');
    } finally {
      setLookupLoading(false);
    }
  }

  return (
    <div className="px-4 py-3">
      <p className="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-2">Ressourcen</p>
      {ressourcen.length > 0 && (
        <div className="space-y-1.5 mb-2">
          {ressourcen.map((r, i) => (
            <div key={i} className="flex items-center gap-2 text-sm">
              <span className="font-mono text-xs text-slate-400 w-24 shrink-0">{r.ref_id ? formatObjectId(r.ref_id) : '—'}</span>
              <span className="flex-1 text-slate-800 truncate min-w-0">{r.name}</span>
              <input
                type="number"
                value={r.menge}
                disabled={!canEdit}
                min={0.001}
                step={1}
                onChange={(e) => onUpdate(ressourcen.map((x, j) => j === i ? { ...x, menge: parseFloat(e.target.value) || 1 } : x))}
                className="w-16 text-right text-xs border border-slate-200 rounded px-2 py-1 disabled:bg-slate-50"
              />
              <input
                type="text"
                value={r.einheit}
                disabled={!canEdit}
                onChange={(e) => onUpdate(ressourcen.map((x, j) => j === i ? { ...x, einheit: e.target.value } : x))}
                className="w-14 text-xs border border-slate-200 rounded px-2 py-1 disabled:bg-slate-50"
                placeholder="Stk"
              />
              {canEdit && (
                <button
                  type="button"
                  onClick={() => onUpdate(ressourcen.filter((_, j) => j !== i))}
                  className="text-slate-400 hover:text-red-500 transition-colors shrink-0"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </button>
              )}
            </div>
          ))}
        </div>
      )}
      {canEdit && (
        <div className="space-y-1">
          <div className="flex gap-2">
            <input
              type="text"
              value={lookup}
              onChange={(e) => { setLookup(e.target.value); setLookupErr(''); }}
              onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); handleLookup(); } }}
              placeholder="Objekt-Nr. suchen (z.B. 100000001)…"
              className="form-input flex-1 text-xs"
            />
            <button
              type="button"
              onClick={handleLookup}
              disabled={lookupLoading || !lookup.trim()}
              className="btn-secondary text-xs px-3 py-1.5 disabled:opacity-50 shrink-0 flex items-center gap-1"
            >
              {lookupLoading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Search className="h-3.5 w-3.5" />}
            </button>
          </div>
          {lookupErr && <p className="text-xs text-red-500">{lookupErr}</p>}
        </div>
      )}
    </div>
  );
}

// ─── Datenfelder inline ───────────────────────────────────────────────────────

function DatenfelderSection({
  datenFelder,
  canEdit,
  onUpdate,
}: {
  datenFelder: DatenFeldDef[];
  canEdit: boolean;
  onUpdate: (d: DatenFeldDef[]) => void;
}) {
  const [newName, setNewName] = useState('');
  const [newTyp, setNewTyp] = useState<DatenFeldDef['typ']>('text');

  function addFeld() {
    const name = newName.trim();
    if (!name) return;
    onUpdate([...datenFelder, { name, typ: newTyp, pflicht: true }]);
    setNewName('');
    setNewTyp('text');
  }

  return (
    <div className="px-4 py-3">
      <p className="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-2">Datenfelder</p>
      {datenFelder.length > 0 && (
        <div className="space-y-1.5 mb-2">
          {datenFelder.map((f, i) => (
            <div key={i} className="flex items-center gap-2 text-sm">
              <span className="flex-1 text-slate-800 text-xs">{f.name}</span>
              <span className="text-xs text-slate-500 bg-slate-100 px-1.5 py-0.5 rounded">
                {DATENFELD_TYPEN.find((t) => t.value === f.typ)?.label ?? f.typ}
              </span>
              {f.einheit && <span className="text-xs text-slate-400">{f.einheit}</span>}
              {canEdit && (
                <button
                  type="button"
                  onClick={() => onUpdate(datenFelder.filter((_, j) => j !== i))}
                  className="text-slate-400 hover:text-red-500 transition-colors shrink-0"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </button>
              )}
            </div>
          ))}
        </div>
      )}
      {canEdit && (
        <div className="flex gap-2">
          <input
            type="text"
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); addFeld(); } }}
            placeholder="Feldname…"
            className="form-input flex-1 text-xs"
          />
          <select
            value={newTyp}
            onChange={(e) => setNewTyp(e.target.value as DatenFeldDef['typ'])}
            className="form-input w-24 text-xs"
          >
            {DATENFELD_TYPEN.map((t) => (
              <option key={t.value} value={t.value}>{t.label}</option>
            ))}
          </select>
          <button
            type="button"
            onClick={addFeld}
            disabled={!newName.trim()}
            className="btn-secondary text-xs px-3 py-1.5 disabled:opacity-50 shrink-0"
          >
            <Plus className="h-3.5 w-3.5" />
          </button>
        </div>
      )}
    </div>
  );
}

// ─── Ergebnis-Optionen inline ─────────────────────────────────────────────────

function ErgebnisSection({
  optionen,
  canEdit,
  onUpdate,
}: {
  optionen: ErgebnisOption[];
  canEdit: boolean;
  onUpdate: (e: ErgebnisOption[]) => void;
}) {
  const [newLabel, setNewLabel] = useState('');
  const [newFarbe, setNewFarbe] = useState<ErgebnisOption['farbe']>('gruen');

  function addOption() {
    const label = newLabel.trim();
    if (!label) return;
    onUpdate([...optionen, { label, farbe: newFarbe }]);
    setNewLabel('');
    setNewFarbe('gruen');
  }

  return (
    <div className="px-4 py-3">
      <p className="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-2">Ergebnis-Optionen</p>
      <div className="flex flex-wrap gap-1.5 mb-2">
        {optionen.map((o, i) => {
          const cfg = ERGEBNIS_FARBEN.find((f) => f.value === o.farbe);
          return (
            <span key={i} className={cn('inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium', cfg?.cls ?? 'bg-slate-100 text-slate-600')}>
              {o.label}
              {canEdit && optionen.length > 1 && (
                <button type="button" onClick={() => onUpdate(optionen.filter((_, j) => j !== i))} className="opacity-60 hover:opacity-100 transition-opacity ml-0.5">
                  ×
                </button>
              )}
            </span>
          );
        })}
      </div>
      {canEdit && (
        <div className="flex gap-2">
          <input
            type="text"
            value={newLabel}
            onChange={(e) => setNewLabel(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); addOption(); } }}
            placeholder="Bezeichnung…"
            className="form-input flex-1 text-xs"
          />
          <select
            value={newFarbe}
            onChange={(e) => setNewFarbe(e.target.value as ErgebnisOption['farbe'])}
            className="form-input w-36 text-xs"
          >
            {ERGEBNIS_FARBEN.map((f) => (
              <option key={f.value} value={f.value}>{f.label}</option>
            ))}
          </select>
          <button
            type="button"
            onClick={addOption}
            disabled={!newLabel.trim()}
            className="btn-secondary text-xs px-3 py-1.5 disabled:opacity-50 shrink-0"
          >
            <Plus className="h-3.5 w-3.5" />
          </button>
        </div>
      )}
    </div>
  );
}

// ─── SchrittCard (always-expanded, flat inline editing) ───────────────────────

function SchrittCard({
  schritt,
  isFirst,
  isLast,
  canEdit,
  objektId,
  onDelete,
  onMoveUp,
  onMoveDown,
  onSaved,
}: {
  schritt: ProzessSchrittDef;
  isFirst: boolean;
  isLast: boolean;
  canEdit: boolean;
  objektId: number;
  onDelete: () => void;
  onMoveUp: () => void;
  onMoveDown: () => void;
  onSaved: () => void;
}) {
  const qc = useQueryClient();
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const [ressourcen, setRessourcen] = useState<RessourceDef[]>(schritt.ressourcen ?? []);
  const [datenFelder, setDatenFelder] = useState<DatenFeldDef[]>(schritt.daten_felder ?? []);
  const [ergebnisse, setErgebnisse] = useState<ErgebnisOption[]>(
    schritt.ergebnis_optionen?.length
      ? schritt.ergebnis_optionen
      : [{ label: 'Erledigt', farbe: 'gruen' }, { label: 'Problem', farbe: 'rot' }]
  );

  // Sync from parent when schritt changes
  useEffect(() => {
    setRessourcen(schritt.ressourcen ?? []);
    setDatenFelder(schritt.daten_felder ?? []);
    setErgebnisse(
      schritt.ergebnis_optionen?.length
        ? schritt.ergebnis_optionen
        : [{ label: 'Erledigt', farbe: 'gruen' }, { label: 'Problem', farbe: 'rot' }]
    );
  }, [schritt.id]);

  const { mutate: save, isPending } = useMutation({
    mutationFn: (data: Parameters<typeof api.updateSchritt>[2]) =>
      api.updateSchritt(objektId, schritt.id, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['uni-objekt', objektId] });
      onSaved();
    },
  });

  function saveNow(data: Parameters<typeof api.updateSchritt>[2]) {
    if (!canEdit) return;
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => save(data), 600);
  }

  function saveImmediate(data: Parameters<typeof api.updateSchritt>[2]) {
    if (!canEdit) return;
    if (debounceRef.current) clearTimeout(debounceRef.current);
    save(data);
  }

  return (
    <div className="rounded-xl border border-slate-200 bg-white shadow-sm overflow-hidden">
      {/* Step header */}
      <div className="flex items-center gap-3 px-4 py-3 bg-slate-50 border-b border-slate-200">
        <span className="flex h-6 w-6 items-center justify-center rounded-full bg-slate-200 text-xs font-bold text-slate-600 shrink-0">
          {schritt.position}
        </span>
        <input
          key={schritt.id}
          type="text"
          defaultValue={schritt.beschreibung}
          disabled={!canEdit}
          onChange={(e) => saveNow({ beschreibung: e.target.value })}
          className="flex-1 text-sm font-medium text-slate-900 bg-transparent border-none outline-none focus:ring-0 disabled:text-slate-600 min-w-0"
          placeholder="Schrittname…"
        />
        {isPending && <Loader2 className="h-3.5 w-3.5 animate-spin text-slate-400 shrink-0" />}
        {canEdit && (
          <div className="flex items-center gap-0.5 shrink-0">
            <button type="button" disabled={isFirst} onClick={onMoveUp} className="p-1 text-slate-400 hover:text-slate-600 disabled:opacity-30 transition-colors">
              <ChevronUp className="h-4 w-4" />
            </button>
            <button type="button" disabled={isLast} onClick={onMoveDown} className="p-1 text-slate-400 hover:text-slate-600 disabled:opacity-30 transition-colors">
              <ChevronDown className="h-4 w-4" />
            </button>
            <button type="button" onClick={onDelete} className="p-1 text-slate-400 hover:text-red-500 transition-colors">
              <Trash2 className="h-4 w-4" />
            </button>
          </div>
        )}
      </div>

      {/* Inline sections */}
      <div className="divide-y divide-slate-100">
        <RessourcenSection
          ressourcen={ressourcen}
          canEdit={canEdit}
          onUpdate={(r) => { setRessourcen(r); saveImmediate({ ressourcen: r }); }}
        />
        <DatenfelderSection
          datenFelder={datenFelder}
          canEdit={canEdit}
          onUpdate={(d) => { setDatenFelder(d); saveImmediate({ daten_felder: d }); }}
        />
        <ErgebnisSection
          optionen={ergebnisse}
          canEdit={canEdit}
          onUpdate={(e) => { setErgebnisse(e); saveImmediate({ ergebnis_optionen: e }); }}
        />
      </div>
    </div>
  );
}

// ─── Prozess Tab ──────────────────────────────────────────────────────────────

function ProzessTab({
  objekt,
  canEdit,
  onSaved,
}: {
  objekt: UniObjekt;
  canEdit: boolean;
  onSaved: () => void;
}) {
  const qc = useQueryClient();

  const addMut = useMutation({
    mutationFn: () => api.addSchritt(objekt.id, {
      position: objekt.schritte.length + 1,
      beschreibung: 'Neuer Schritt',
      ergebnis_optionen: [
        { label: 'Erledigt', farbe: 'gruen' },
        { label: 'Problem', farbe: 'rot' },
      ],
    }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['uni-objekt', objekt.id] });
      onSaved();
    },
  });

  const deleteMut = useMutation({
    mutationFn: (id: number) => api.deleteSchritt(objekt.id, id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['uni-objekt', objekt.id] });
      onSaved();
    },
  });

  const moveMut = useMutation({
    mutationFn: ({ id, pos }: { id: number; pos: number }) =>
      api.updateSchritt(objekt.id, id, { position: pos }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['uni-objekt', objekt.id] });
      onSaved();
    },
  });

  const sorted = [...objekt.schritte].sort((a, b) => a.position - b.position);

  function moveUp(schritt: ProzessSchrittDef) {
    const idx = sorted.findIndex((s) => s.id === schritt.id);
    if (idx <= 0) return;
    const prev = sorted[idx - 1];
    moveMut.mutate({ id: schritt.id, pos: prev.position });
    moveMut.mutate({ id: prev.id, pos: schritt.position });
  }

  function moveDown(schritt: ProzessSchrittDef) {
    const idx = sorted.findIndex((s) => s.id === schritt.id);
    if (idx >= sorted.length - 1) return;
    const next = sorted[idx + 1];
    moveMut.mutate({ id: schritt.id, pos: next.position });
    moveMut.mutate({ id: next.id, pos: schritt.position });
  }

  return (
    <div className="p-4 space-y-3">
      {!canEdit && (
        <div className="flex items-center gap-2 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-600">
          <Lock className="h-3.5 w-3.5 shrink-0" />
          Prozess ist gesperrt — Objekt ist freigegeben.
        </div>
      )}
      {sorted.length === 0 && (
        <p className="text-sm text-slate-500 text-center py-8">Noch keine Schritte definiert.</p>
      )}
      {sorted.map((s, idx) => (
        <SchrittCard
          key={s.id}
          schritt={s}
          isFirst={idx === 0}
          isLast={idx === sorted.length - 1}
          canEdit={canEdit}
          objektId={objekt.id}
          onDelete={() => deleteMut.mutate(s.id)}
          onMoveUp={() => moveUp(s)}
          onMoveDown={() => moveDown(s)}
          onSaved={onSaved}
        />
      ))}
      {canEdit && (
        <button
          type="button"
          onClick={() => addMut.mutate()}
          disabled={addMut.isPending}
          className="w-full flex items-center justify-center gap-2 py-2.5 rounded-xl border-2 border-dashed border-slate-200 text-sm text-slate-500 hover:border-blue-300 hover:text-blue-600 hover:bg-blue-50 transition-colors disabled:opacity-50"
        >
          {addMut.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}
          Schritt hinzufügen
        </button>
      )}
    </div>
  );
}

// ─── Stammdaten Tab ───────────────────────────────────────────────────────────

function StammdatenTab({
  objekt,
  itemNames,
  canEdit,
  onSave,
}: {
  objekt: UniObjekt;
  itemNames: ItemName[];
  canEdit: boolean;
  onSave: (data: { name?: string; notiz?: string; einheit?: string }) => void;
}) {
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  function schedule(data: { name?: string; notiz?: string; einheit?: string }) {
    if (!canEdit) return;
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => onSave(data), 3000);
  }

  const activeNames = itemNames.filter((n) => n.is_active);

  return (
    <div className="p-6 space-y-5">
      {!canEdit && (
        <div className="flex items-center gap-2 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-600">
          <Lock className="h-3.5 w-3.5 shrink-0" />
          Freigegebene Objekte können nicht bearbeitet werden.
        </div>
      )}

      <div>
        <label className="block text-sm font-medium text-slate-700 mb-1.5">
          Name <span className="text-red-500">*</span>
        </label>
        <input
          key={objekt.id}
          type="text"
          list="objekt-namen-list"
          defaultValue={objekt.name ?? ''}
          disabled={!canEdit}
          onChange={(e) => schedule({ name: e.target.value })}
          className="form-input disabled:bg-slate-50 disabled:text-slate-500"
          placeholder="Objektname wählen oder eingeben…"
        />
        <datalist id="objekt-namen-list">
          {activeNames.map((n) => <option key={n.id} value={n.label} />)}
        </datalist>
      </div>

      <div>
        <label className="block text-sm font-medium text-slate-700 mb-1.5">Einheit</label>
        <input
          key={`${objekt.id}-einheit`}
          type="text"
          defaultValue={objekt.einheit ?? ''}
          disabled={!canEdit}
          onChange={(e) => schedule({ einheit: e.target.value })}
          className="form-input disabled:bg-slate-50 disabled:text-slate-500"
          placeholder="z.B. Stk, Set, m…"
        />
      </div>

      <div>
        <label className="block text-sm font-medium text-slate-700 mb-1.5">Notiz</label>
        <textarea
          key={`${objekt.id}-notiz`}
          defaultValue={objekt.notiz ?? ''}
          disabled={!canEdit}
          onChange={(e) => schedule({ notiz: e.target.value })}
          rows={4}
          className="form-input resize-none disabled:bg-slate-50 disabled:text-slate-500"
          placeholder="Optionale Beschreibung…"
        />
      </div>

      <div className="grid grid-cols-2 gap-x-6 gap-y-3 pt-2 border-t border-slate-100">
        <div>
          <dt className="text-xs font-medium text-slate-500 uppercase tracking-wide">Objekt-Nr.</dt>
          <dd className="mt-1 text-sm font-mono text-slate-900">{formatObjectId(objekt.id)}</dd>
        </div>
        <div>
          <dt className="text-xs font-medium text-slate-500 uppercase tracking-wide">Status</dt>
          <dd className="mt-1"><ObjStatusBadge status={objekt.obj_status} /></dd>
        </div>
        <div>
          <dt className="text-xs font-medium text-slate-500 uppercase tracking-wide">Erstellt</dt>
          <dd className="mt-1 text-sm text-slate-900">
            {new Date(objekt.created_at).toLocaleDateString('de-CH')}
          </dd>
        </div>
        <div>
          <dt className="text-xs font-medium text-slate-500 uppercase tracking-wide">Prozessschritte</dt>
          <dd className="mt-1 text-sm text-slate-900">{objekt.schritte.length}</dd>
        </div>
      </div>
    </div>
  );
}

// ─── Main component ────────────────────────────────────────────────────────────

type Tab = 'prozess' | 'stammdaten';

interface Props {
  objekt: UniObjekt;
  currentUserRole?: string;
  onRefresh?: () => void;
}

export function ObjektStammdatenForm({ objekt, currentUserRole: _role, onRefresh }: Props) {
  const qc = useQueryClient();
  const [tab, setTab] = useState<Tab>('prozess');
  const [lastSaved, setLastSaved] = useState<Date | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const canEdit = objekt.obj_status === 'ENTWURF';
  const canFreigeben = canEdit && objekt.schritte.length > 0 && (objekt.name ?? '').trim().length > 0;

  const { data: itemNames = [] } = useQuery({
    queryKey: ['item-names'],
    queryFn: () => api.getItemNames(),
    staleTime: 60_000,
  });

  const { mutate: saveStamm } = useMutation({
    mutationFn: (data: { name?: string; notiz?: string; einheit?: string }) =>
      api.updateUniObjekt(objekt.id, data),
    onMutate: () => { setSaving(true); setError(''); },
    onSuccess: (updated) => {
      qc.setQueryData(['uni-objekt', objekt.id], updated);
      qc.invalidateQueries({ queryKey: ['objects'] });
      setLastSaved(new Date());
      setSaving(false);
      onRefresh?.();
    },
    onError: (e: Error) => { setError(e.message); setSaving(false); },
  });

  const { mutate: freigeben, isPending: freigebeLoading } = useMutation({
    mutationFn: () => api.freigeben(objekt.id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['uni-objekt', objekt.id] });
      qc.invalidateQueries({ queryKey: ['objects'] });
      setLastSaved(new Date());
      onRefresh?.();
    },
    onError: (e: Error) => setError(e.message),
  });

  function markSaved() {
    setLastSaved(new Date());
  }

  const savedTime = lastSaved
    ? lastSaved.toLocaleTimeString('de-CH', { hour: '2-digit', minute: '2-digit' })
    : null;

  return (
    <div className="flex flex-col overflow-hidden flex-1 bg-white">
      {/* Header */}
      <div className="px-6 py-4 border-b border-slate-200 shrink-0">
        <div className="flex items-start gap-3">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-0.5">
              <span className="text-xs font-mono text-slate-400">{formatObjectId(objekt.id)}</span>
              <span className="text-xs text-slate-400">·</span>
              <span className="text-xs text-slate-400">Objekt</span>
              {!canEdit && <Lock className="h-3 w-3 text-slate-400" />}
            </div>
            <h2 className="text-lg font-semibold text-slate-900 leading-tight truncate">
              {objekt.name || <span className="text-slate-400 italic font-normal">Unbenannt</span>}
            </h2>
          </div>
          <div className="shrink-0 flex flex-col items-end gap-2">
            <ObjStatusBadge status={objekt.obj_status} />
            <div className="flex items-center gap-1.5 text-xs min-h-[1rem]">
              {saving && <><Loader2 className="h-3 w-3 animate-spin text-slate-400" /><span className="text-slate-400">Speichert…</span></>}
              {!saving && savedTime && (
                <><CheckCircle2 className="h-3 w-3 text-green-500" /><span className="text-green-600">Gespeichert {savedTime}</span></>
              )}
            </div>
          </div>
        </div>

        {error && (
          <div className="mt-2 flex items-center gap-2 text-xs text-red-600">
            <AlertCircle className="h-3.5 w-3.5 shrink-0" />{error}
          </div>
        )}

        {canFreigeben && (
          <button
            type="button"
            disabled={freigebeLoading}
            onClick={() => freigeben()}
            className="mt-3 flex items-center gap-1.5 rounded-lg bg-green-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-green-700 disabled:opacity-50 transition-colors"
          >
            {freigebeLoading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Lock className="h-3.5 w-3.5" />}
            Freigeben
          </button>
        )}

        {/* Tabs — Prozess first */}
        <div className="flex gap-1 mt-4 -mb-px">
          {(['prozess', 'stammdaten'] as Tab[]).map((t) => (
            <button
              key={t}
              type="button"
              onClick={() => setTab(t)}
              className={cn(
                'px-3 py-1.5 text-sm font-medium rounded-t-lg border-b-2 transition-colors',
                tab === t
                  ? 'border-red-500 text-red-700 bg-red-50/40'
                  : 'border-transparent text-slate-500 hover:text-slate-700 hover:bg-slate-50',
              )}
            >
              {t === 'prozess' ? `Prozess (${objekt.schritte.length})` : 'Stammdaten'}
            </button>
          ))}
        </div>
      </div>

      {/* Body */}
      <div className="flex-1 overflow-y-auto">
        {tab === 'prozess' && (
          <ProzessTab
            objekt={objekt}
            canEdit={canEdit}
            onSaved={markSaved}
          />
        )}
        {tab === 'stammdaten' && (
          <StammdatenTab
            objekt={objekt}
            itemNames={itemNames}
            canEdit={canEdit}
            onSave={saveStamm}
          />
        )}
      </div>
    </div>
  );
}
