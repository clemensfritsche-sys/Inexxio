'use client';

import { useState, useRef, useEffect, useCallback } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Plus, Trash2, ChevronUp, ChevronDown, Loader2, CheckCircle2,
  Lock, Search, AlertCircle, Package, ClipboardList, Wrench,
  GitBranch, ArrowDown, ThumbsUp, ThumbsDown, X,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { formatObjectId } from '@/lib/utils';
import { api } from '@/lib/api';
import { OBJ_STATUS_CONFIG } from '@/types';
import type {
  UniObjekt, ProzessSchrittDef, DatenFeldDef, ItemName, SchrittTyp,
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

const DATENFELD_TYPEN = [
  { value: 'text', label: 'Text' },
  { value: 'number', label: 'Zahl' },
  { value: 'datum', label: 'Datum' },
  { value: 'auswahl', label: 'Auswahl' },
];

const SCHRITT_TYP_CONFIG: Record<SchrittTyp, {
  label: string;
  icon: React.ElementType;
  color: string;
  headerBg: string;
  badge?: string;
  badgeColor?: string;
}> = {
  ressource: {
    label: 'Ressource',
    icon: Package,
    color: 'text-orange-600',
    headerBg: 'bg-orange-50',
    badge: 'Bestandswirksam',
    badgeColor: 'bg-orange-100 text-orange-700',
  },
  daten: {
    label: 'Daten erfassen',
    icon: ClipboardList,
    color: 'text-blue-600',
    headerBg: 'bg-blue-50',
  },
  hilfsmittel: {
    label: 'Hilfsmittel',
    icon: Wrench,
    color: 'text-slate-600',
    headerBg: 'bg-slate-50',
    badge: 'Nicht bestandswirksam',
    badgeColor: 'bg-slate-100 text-slate-600',
  },
  gate: {
    label: 'Gate',
    icon: GitBranch,
    color: 'text-violet-600',
    headerBg: 'bg-violet-50',
  },
};

// ─── Type Chooser Panel ───────────────────────────────────────────────────────

const TYPE_OPTIONS: { typ: SchrittTyp; title: string; description: string; icon: React.ElementType }[] = [
  { typ: 'ressource', title: 'Ressource', description: 'Material / Teil verbrauchen (bestandswirksam)', icon: Package },
  { typ: 'daten', title: 'Daten erfassen', description: 'Felder zum Ausfüllen definieren', icon: ClipboardList },
  { typ: 'hilfsmittel', title: 'Hilfsmittel', description: 'Werkzeug / Messgerät referenzieren', icon: Wrench },
  { typ: 'gate', title: 'Gate', description: '👍 OK weiter  ·  👎 Problem → MRA', icon: GitBranch },
];

function TypeChooser({ onSelect, onClose }: { onSelect: (t: SchrittTyp) => void; onClose: () => void }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/20 backdrop-blur-sm" onClick={onClose}>
      <div
        className="w-80 rounded-2xl border border-slate-200 bg-white shadow-xl overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-4 py-3 border-b border-slate-100">
          <p className="text-sm font-semibold text-slate-800">Schritt-Typ wählen</p>
          <button type="button" onClick={onClose} className="text-slate-400 hover:text-slate-600 transition-colors">
            <X className="h-4 w-4" />
          </button>
        </div>
        <div className="p-2">
          {TYPE_OPTIONS.map(({ typ, title, description, icon: Icon }) => (
            <button
              key={typ}
              type="button"
              onClick={() => onSelect(typ)}
              className="flex w-full items-start gap-3 rounded-xl px-3 py-3 text-left hover:bg-slate-50 transition-colors"
            >
              <div className={cn('flex h-8 w-8 shrink-0 items-center justify-center rounded-lg', SCHRITT_TYP_CONFIG[typ].headerBg)}>
                <Icon className={cn('h-4 w-4', SCHRITT_TYP_CONFIG[typ].color)} />
              </div>
              <div>
                <p className="text-sm font-medium text-slate-800">{title}</p>
                <p className="text-xs text-slate-500 mt-0.5">{description}</p>
              </div>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

// ─── Object Lookup Field ──────────────────────────────────────────────────────

function ObjektLookupField({
  objektId,
  objektName,
  canEdit,
  onFound,
  onClear,
}: {
  objektId: number | null;
  objektName?: string | null;
  canEdit: boolean;
  onFound: (id: number, name: string) => void;
  onClear: () => void;
}) {
  const [input, setInput] = useState('');
  const [err, setErr] = useState('');
  const [loading, setLoading] = useState(false);

  async function handleLookup() {
    const nr = parseInt(input.trim(), 10);
    if (!nr) { setErr('Gültige 9-stellige Objekt-Nummer eingeben'); return; }
    setLoading(true);
    setErr('');
    try {
      const obj = await api.lookupObjektByNummer(nr);
      onFound(obj.id, obj.name ?? String(obj.id));
      setInput('');
    } catch {
      setErr('Kein freigegebenes Objekt mit dieser Nummer gefunden');
    } finally {
      setLoading(false);
    }
  }

  if (objektId !== null) {
    return (
      <div className="flex items-center gap-2 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2">
        <span className="font-mono text-xs text-slate-400 shrink-0">{formatObjectId(objektId)}</span>
        <span className="flex-1 text-sm text-slate-800 truncate min-w-0">{objektName || '—'}</span>
        {canEdit && (
          <button type="button" onClick={onClear} className="text-slate-400 hover:text-red-500 transition-colors shrink-0">
            <X className="h-3.5 w-3.5" />
          </button>
        )}
      </div>
    );
  }

  return (
    <div className="space-y-1">
      <div className="flex gap-2">
        <input
          type="text"
          value={input}
          disabled={!canEdit}
          onChange={(e) => { setInput(e.target.value); setErr(''); }}
          onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); handleLookup(); } }}
          placeholder="Objekt-Nr. eingeben (z.B. 100000001)…"
          className="form-input flex-1 text-xs"
        />
        <button
          type="button"
          onClick={handleLookup}
          disabled={loading || !input.trim()}
          className="btn-secondary text-xs px-3 py-1.5 disabled:opacity-50 shrink-0 flex items-center gap-1"
        >
          {loading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Search className="h-3.5 w-3.5" />}
        </button>
      </div>
      {err && <p className="text-xs text-red-500">{err}</p>}
    </div>
  );
}

// ─── Step Content by Type ─────────────────────────────────────────────────────

function RessourceContent({
  schritt,
  canEdit,
  onSave,
}: {
  schritt: ProzessSchrittDef;
  canEdit: boolean;
  onSave: (data: Partial<Parameters<typeof api.updateSchritt>[2]>) => void;
}) {
  const [menge, setMenge] = useState(schritt.referenz_menge ?? 1);
  const [einheit, setEinheit] = useState(() => {
    if (schritt.ressourcen?.[0]?.einheit) return schritt.ressourcen[0].einheit;
    return 'Stk';
  });
  const [objName, setObjName] = useState<string | null>(() => schritt.ressourcen?.[0]?.name ?? null);

  useEffect(() => {
    setMenge(schritt.referenz_menge ?? 1);
    setEinheit(schritt.ressourcen?.[0]?.einheit ?? 'Stk');
    setObjName(schritt.ressourcen?.[0]?.name ?? null);
  }, [schritt.id]);

  function saveRef(id: number | null, name: string | null, m: number, e: string) {
    onSave({
      referenz_objekt_id: id,
      referenz_menge: m,
      ressourcen: id ? [{ ref_id: id, name: name ?? String(id), menge: m, einheit: e }] : [],
    });
  }

  return (
    <div className="space-y-3">
      <div>
        <p className="text-xs font-medium text-slate-500 mb-1.5">Objekt (freigegeben)</p>
        <ObjektLookupField
          objektId={schritt.referenz_objekt_id}
          objektName={objName}
          canEdit={canEdit}
          onFound={(id, name) => {
            setObjName(name);
            saveRef(id, name, menge, einheit);
          }}
          onClear={() => { setObjName(null); saveRef(null, null, menge, einheit); }}
        />
      </div>
      <div className="flex gap-3">
        <div className="flex-1">
          <p className="text-xs font-medium text-slate-500 mb-1.5">Menge</p>
          <input
            type="number"
            value={menge}
            disabled={!canEdit}
            min={0.001}
            step={1}
            onChange={(e) => {
              const v = parseFloat(e.target.value) || 1;
              setMenge(v);
              if (schritt.referenz_objekt_id) saveRef(schritt.referenz_objekt_id, objName, v, einheit);
            }}
            className="form-input text-sm disabled:bg-slate-50"
          />
        </div>
        <div className="w-24">
          <p className="text-xs font-medium text-slate-500 mb-1.5">Einheit</p>
          <input
            type="text"
            value={einheit}
            disabled={!canEdit}
            onChange={(e) => {
              setEinheit(e.target.value);
              if (schritt.referenz_objekt_id) saveRef(schritt.referenz_objekt_id, objName, menge, e.target.value);
            }}
            className="form-input text-sm disabled:bg-slate-50"
            placeholder="Stk"
          />
        </div>
      </div>
    </div>
  );
}

function DatenContent({
  schritt,
  canEdit,
  onSave,
}: {
  schritt: ProzessSchrittDef;
  canEdit: boolean;
  onSave: (data: Partial<Parameters<typeof api.updateSchritt>[2]>) => void;
}) {
  const [felder, setFelder] = useState<DatenFeldDef[]>(schritt.daten_felder ?? []);
  const [newName, setNewName] = useState('');
  const [newTyp, setNewTyp] = useState<DatenFeldDef['typ']>('text');

  useEffect(() => {
    setFelder(schritt.daten_felder ?? []);
  }, [schritt.id]);

  function addFeld() {
    const name = newName.trim();
    if (!name) return;
    const updated = [...felder, { name, typ: newTyp, pflicht: true }];
    setFelder(updated);
    onSave({ daten_felder: updated });
    setNewName('');
    setNewTyp('text');
  }

  function removeFeld(i: number) {
    const updated = felder.filter((_, j) => j !== i);
    setFelder(updated);
    onSave({ daten_felder: updated });
  }

  return (
    <div className="space-y-2">
      {felder.length > 0 && (
        <div className="space-y-1.5">
          {felder.map((f, i) => (
            <div key={i} className="flex items-center gap-2 rounded-lg bg-slate-50 px-3 py-1.5">
              <span className="flex-1 text-sm text-slate-800 min-w-0 truncate">{f.name}</span>
              <span className="text-xs text-slate-500 bg-white border border-slate-200 px-1.5 py-0.5 rounded shrink-0">
                {DATENFELD_TYPEN.find((t) => t.value === f.typ)?.label ?? f.typ}
              </span>
              {canEdit && (
                <button type="button" onClick={() => removeFeld(i)} className="text-slate-400 hover:text-red-500 transition-colors shrink-0">
                  <X className="h-3.5 w-3.5" />
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
      {felder.length === 0 && !canEdit && (
        <p className="text-xs text-slate-400 italic">Keine Felder definiert.</p>
      )}
    </div>
  );
}

function HilfsmittelContent({
  schritt,
  canEdit,
  onSave,
}: {
  schritt: ProzessSchrittDef;
  canEdit: boolean;
  onSave: (data: Partial<Parameters<typeof api.updateSchritt>[2]>) => void;
}) {
  const [objName, setObjName] = useState<string | null>(() => schritt.ressourcen?.[0]?.name ?? null);

  useEffect(() => {
    setObjName(schritt.ressourcen?.[0]?.name ?? null);
  }, [schritt.id]);

  return (
    <div>
      <p className="text-xs font-medium text-slate-500 mb-1.5">Hilfsmittel (Objekt)</p>
      <ObjektLookupField
        objektId={schritt.referenz_objekt_id}
        objektName={objName}
        canEdit={canEdit}
        onFound={(id, name) => {
          setObjName(name);
          onSave({ referenz_objekt_id: id, ressourcen: [{ ref_id: id, name, menge: 1, einheit: '' }] });
        }}
        onClear={() => { setObjName(null); onSave({ referenz_objekt_id: null, ressourcen: [] }); }}
      />
    </div>
  );
}

function GateContent() {
  return (
    <div className="space-y-2">
      <div className="flex items-center gap-3 rounded-lg border border-green-200 bg-green-50 px-3 py-2.5">
        <ThumbsUp className="h-4 w-4 text-green-600 shrink-0" />
        <div>
          <p className="text-sm font-medium text-green-800">OK</p>
          <p className="text-xs text-green-600">Prozess weiter</p>
        </div>
      </div>
      <div className="flex items-center gap-3 rounded-lg border border-red-200 bg-red-50 px-3 py-2.5">
        <ThumbsDown className="h-4 w-4 text-red-600 shrink-0" />
        <div>
          <p className="text-sm font-medium text-red-800">Problem</p>
          <p className="text-xs text-red-600">MRA-Prozess anstoßen</p>
        </div>
      </div>
    </div>
  );
}

// ─── Flowchart Step Card ──────────────────────────────────────────────────────

function FlowSchrittCard({
  schritt,
  position,
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
  position: number;
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
  const typ = schritt.schritt_typ ?? 'ressource';
  const cfg = SCHRITT_TYP_CONFIG[typ as SchrittTyp] ?? SCHRITT_TYP_CONFIG.ressource;
  const Icon = cfg.icon;

  const { mutate: save, isPending } = useMutation({
    mutationFn: (data: Parameters<typeof api.updateSchritt>[2]) =>
      api.updateSchritt(objektId, schritt.id, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['uni-objekt', objektId] });
      onSaved();
    },
  });

  const saveImmediate = useCallback((data: Parameters<typeof api.updateSchritt>[2]) => {
    if (!canEdit) return;
    if (debounceRef.current) clearTimeout(debounceRef.current);
    save(data);
  }, [canEdit, save]);

  const saveDebounced = useCallback((data: Parameters<typeof api.updateSchritt>[2]) => {
    if (!canEdit) return;
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => save(data), 600);
  }, [canEdit, save]);

  return (
    <div className="rounded-xl border border-slate-200 bg-white shadow-sm overflow-hidden">
      {/* Header */}
      <div className={cn('flex items-center gap-2.5 px-4 py-2.5 border-b border-slate-200', cfg.headerBg)}>
        <div className={cn('flex h-5 w-5 items-center justify-center rounded-full bg-white/70 text-[10px] font-bold shrink-0', cfg.color)}>
          {position}
        </div>
        <Icon className={cn('h-3.5 w-3.5 shrink-0', cfg.color)} />
        <span className={cn('text-xs font-semibold shrink-0', cfg.color)}>{cfg.label}</span>
        {cfg.badge && (
          <span className={cn('text-[10px] font-medium px-1.5 py-0.5 rounded-full', cfg.badgeColor)}>
            {cfg.badge}
          </span>
        )}
        <input
          key={`${schritt.id}-desc`}
          type="text"
          defaultValue={schritt.beschreibung}
          disabled={!canEdit}
          onChange={(e) => saveDebounced({ beschreibung: e.target.value })}
          className="flex-1 min-w-0 text-sm font-medium text-slate-800 bg-transparent border-none outline-none focus:ring-0 disabled:text-slate-600 placeholder:text-slate-400"
          placeholder="Schritt beschreiben…"
        />
        {isPending && <Loader2 className="h-3.5 w-3.5 animate-spin text-slate-400 shrink-0" />}
        {canEdit && (
          <div className="flex items-center gap-0.5 shrink-0">
            <button type="button" disabled={isFirst} onClick={onMoveUp} className="p-1 text-slate-400 hover:text-slate-700 disabled:opacity-30 transition-colors">
              <ChevronUp className="h-3.5 w-3.5" />
            </button>
            <button type="button" disabled={isLast} onClick={onMoveDown} className="p-1 text-slate-400 hover:text-slate-700 disabled:opacity-30 transition-colors">
              <ChevronDown className="h-3.5 w-3.5" />
            </button>
            <button type="button" onClick={onDelete} className="p-1 text-slate-400 hover:text-red-500 transition-colors">
              <Trash2 className="h-3.5 w-3.5" />
            </button>
          </div>
        )}
      </div>

      {/* Type-specific content */}
      <div className="px-4 py-3">
        {typ === 'ressource' && (
          <RessourceContent schritt={schritt} canEdit={canEdit} onSave={saveImmediate} />
        )}
        {typ === 'daten' && (
          <DatenContent schritt={schritt} canEdit={canEdit} onSave={saveImmediate} />
        )}
        {typ === 'hilfsmittel' && (
          <HilfsmittelContent schritt={schritt} canEdit={canEdit} onSave={saveImmediate} />
        )}
        {typ === 'gate' && <GateContent />}
      </div>
    </div>
  );
}

// ─── Flowchart connector ──────────────────────────────────────────────────────

function FlowConnector() {
  return (
    <div className="flex flex-col items-center py-0.5">
      <div className="w-px h-4 bg-slate-300" />
      <ArrowDown className="h-3 w-3 text-slate-300 -mt-0.5" />
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
  const [showTypeChooser, setShowTypeChooser] = useState(false);

  const addMut = useMutation({
    mutationFn: (typ: SchrittTyp) => api.addSchritt(objekt.id, {
      position: objekt.schritte.length + 1,
      beschreibung: '',
      schritt_typ: typ,
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

  function handleTypeSelect(typ: SchrittTyp) {
    setShowTypeChooser(false);
    addMut.mutate(typ);
  }

  return (
    <div className="p-4">
      {!canEdit && (
        <div className="flex items-center gap-2 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-600 mb-4">
          <Lock className="h-3.5 w-3.5 shrink-0" />
          Prozess ist gesperrt — Objekt ist freigegeben.
        </div>
      )}

      {/* START node */}
      <div className="flex justify-center mb-1">
        <div className="flex items-center gap-1.5 rounded-full border border-slate-300 bg-white px-4 py-1 text-xs font-semibold text-slate-600 shadow-sm">
          ▶ START
        </div>
      </div>

      {sorted.length === 0 && (
        <>
          <FlowConnector />
          <p className="text-center text-xs text-slate-400 py-4">Noch keine Schritte — Schritt hinzufügen unten.</p>
        </>
      )}

      {sorted.map((s, idx) => (
        <div key={s.id}>
          <FlowConnector />
          <FlowSchrittCard
            schritt={s}
            position={idx + 1}
            isFirst={idx === 0}
            isLast={idx === sorted.length - 1}
            canEdit={canEdit}
            objektId={objekt.id}
            onDelete={() => deleteMut.mutate(s.id)}
            onMoveUp={() => moveUp(s)}
            onMoveDown={() => moveDown(s)}
            onSaved={onSaved}
          />
        </div>
      ))}

      {/* Add step */}
      {canEdit && (
        <>
          <FlowConnector />
          <div className="flex justify-center">
            <button
              type="button"
              onClick={() => setShowTypeChooser(true)}
              disabled={addMut.isPending}
              className="flex items-center gap-2 rounded-full border-2 border-dashed border-slate-300 px-5 py-2 text-sm text-slate-500 hover:border-red-400 hover:text-red-600 hover:bg-red-50 transition-colors disabled:opacity-50"
            >
              {addMut.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}
              Schritt hinzufügen
            </button>
          </div>
        </>
      )}

      {/* END node */}
      {sorted.length > 0 && (
        <>
          <FlowConnector />
          <div className="flex justify-center">
            <div className="flex items-center gap-1.5 rounded-full border-2 border-slate-400 bg-white px-4 py-1 text-xs font-bold text-slate-600 shadow-sm">
              ⬛ ENDE
            </div>
          </div>
        </>
      )}

      {showTypeChooser && (
        <TypeChooser onSelect={handleTypeSelect} onClose={() => setShowTypeChooser(false)} />
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

        {/* Tabs */}
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
