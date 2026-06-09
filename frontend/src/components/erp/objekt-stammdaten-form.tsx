'use client';

import { useState, useRef, useEffect, useCallback } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Plus, Trash2, ChevronUp, ChevronDown, Loader2, CheckCircle2,
  Lock, AlertCircle, Package, ClipboardList, Wrench,
  GitBranch, ArrowDown, ThumbsUp, ThumbsDown, X, Network, Play,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { formatObjectId } from '@/lib/utils';
import { api } from '@/lib/api';
import { OBJ_STATUS_CONFIG } from '@/types';
import type {
  UniObjekt, ProzessSchrittDef, DatenFeldDef, ItemName, SchrittTyp, UniObjektSummary,
} from '@/types';

// ─── Helpers ──────────────────────────────────────────────────────────────────

function ObjStatusBadge({ status }: { status: string | null }) {
  const cfg = status && status in OBJ_STATUS_CONFIG
    ? OBJ_STATUS_CONFIG[status as keyof typeof OBJ_STATUS_CONFIG]
    : { label: status ?? '—', color: 'bg-slate-100 text-slate-600' };
  return (
    <span className={cn('inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-semibold', cfg.color)}>
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
  label: string; icon: React.ElementType; iconColor: string; headerBg: string;
  badge?: string; badgeColor?: string;
}> = {
  ressource: {
    label: 'Ressource', icon: Package, iconColor: 'text-orange-600', headerBg: 'bg-orange-50',
    badge: 'bestandswirksam', badgeColor: 'bg-orange-100 text-orange-700',
  },
  daten: {
    label: 'Daten', icon: ClipboardList, iconColor: 'text-blue-600', headerBg: 'bg-blue-50',
  },
  hilfsmittel: {
    label: 'Hilfsmittel', icon: Wrench, iconColor: 'text-slate-500', headerBg: 'bg-slate-50',
    badge: 'nicht bestandswirksam', badgeColor: 'bg-slate-100 text-slate-500',
  },
  gate: {
    label: 'Gate', icon: GitBranch, iconColor: 'text-violet-600', headerBg: 'bg-violet-50',
  },
  unterprozess: {
    label: 'Unterprozess', icon: Network, iconColor: 'text-teal-600', headerBg: 'bg-teal-50',
    badge: 'auto-start', badgeColor: 'bg-teal-100 text-teal-700',
  },
};

// ─── Type Chooser ─────────────────────────────────────────────────────────────

const TYPE_OPTIONS: { typ: SchrittTyp; desc: string }[] = [
  { typ: 'ressource', desc: 'Material/Teil verbrauchen (bestandswirksam)' },
  { typ: 'daten', desc: 'Einen Messwert oder Wert erfassen' },
  { typ: 'hilfsmittel', desc: 'Werkzeug/Messgerät referenzieren' },
  { typ: 'gate', desc: '👍 OK weiter  ·  👎 Problem → MRA' },
  { typ: 'unterprozess', desc: 'Anderen Objektprozess anstoßen (N Instanzen)' },
];

function TypeChooser({ onSelect, onClose }: { onSelect: (t: SchrittTyp) => void; onClose: () => void }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/25" onClick={onClose}>
      <div className="w-72 rounded-xl border border-slate-200 bg-white shadow-xl overflow-hidden" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between px-3 py-2.5 border-b border-slate-100">
          <p className="text-xs font-semibold text-slate-700 uppercase tracking-wide">Schritt-Typ wählen</p>
          <button type="button" onClick={onClose}><X className="h-3.5 w-3.5 text-slate-400" /></button>
        </div>
        <div className="p-1.5 space-y-0.5">
          {TYPE_OPTIONS.map(({ typ, desc }) => {
            const cfg = SCHRITT_TYP_CONFIG[typ];
            const Icon = cfg.icon;
            return (
              <button
                key={typ}
                type="button"
                onClick={() => onSelect(typ)}
                className="flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-left hover:bg-slate-50 transition-colors"
              >
                <div className={cn('flex h-7 w-7 shrink-0 items-center justify-center rounded-lg', cfg.headerBg)}>
                  <Icon className={cn('h-3.5 w-3.5', cfg.iconColor)} />
                </div>
                <div>
                  <p className="text-xs font-semibold text-slate-800">{cfg.label}</p>
                  <p className="text-[11px] text-slate-500 leading-snug">{desc}</p>
                </div>
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}

// ─── Live Object Search ───────────────────────────────────────────────────────

function ObjektSearchField({
  selectedId, selectedName, canEdit, onSelect, onClear, placeholder,
}: {
  selectedId: number | null; selectedName?: string | null; canEdit: boolean;
  onSelect: (id: number, name: string) => void; onClear: () => void; placeholder?: string;
}) {
  const [query, setQuery] = useState('');
  const [open, setOpen] = useState(false);
  const [results, setResults] = useState<UniObjektSummary[]>([]);
  const [loading, setLoading] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const wrapRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function onOut(e: MouseEvent) {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener('mousedown', onOut);
    return () => document.removeEventListener('mousedown', onOut);
  }, []);

  useEffect(() => {
    if (!query.trim()) { setResults([]); setOpen(false); return; }
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(async () => {
      setLoading(true);
      try {
        const items = await api.searchObjekte(query, 'FREIGEGEBEN');
        setResults(items);
        setOpen(true);
      } catch { setResults([]); }
      finally { setLoading(false); }
    }, 250);
    return () => { if (debounceRef.current) clearTimeout(debounceRef.current); };
  }, [query]);

  if (selectedId !== null) {
    return (
      <div className="flex items-center gap-2 rounded-lg border border-slate-200 bg-slate-50 px-2.5 py-1.5">
        <span className="font-mono text-[11px] text-slate-400 shrink-0">{formatObjectId(selectedId)}</span>
        <span className="flex-1 text-xs text-slate-700 truncate min-w-0">{selectedName || '—'}</span>
        {canEdit && (
          <button type="button" onClick={onClear} className="text-slate-400 hover:text-red-500 transition-colors shrink-0">
            <X className="h-3 w-3" />
          </button>
        )}
      </div>
    );
  }

  return (
    <div className="relative" ref={wrapRef}>
      <input
        type="text" value={query} disabled={!canEdit}
        onChange={(e) => setQuery(e.target.value)}
        onFocus={() => query.trim() && results.length > 0 && setOpen(true)}
        placeholder={placeholder ?? 'Objekt suchen (Nr. oder Name)…'}
        className="form-input text-xs pr-7 w-full disabled:bg-slate-50"
      />
      {loading && <Loader2 className="absolute right-2.5 top-1/2 -translate-y-1/2 h-3 w-3 animate-spin text-slate-400 pointer-events-none" />}
      {open && results.length > 0 && (
        <div className="absolute left-0 right-0 top-full z-50 mt-1 rounded-lg border border-slate-200 bg-white shadow-lg overflow-hidden max-h-44 overflow-y-auto">
          {results.map((r) => (
            <button
              key={r.id} type="button"
              onMouseDown={(e) => { e.preventDefault(); onSelect(r.id, r.name ?? String(r.id)); setQuery(''); setOpen(false); }}
              className="flex w-full items-center gap-2 px-2.5 py-1.5 text-left hover:bg-slate-50 border-b border-slate-100 last:border-0"
            >
              <span className="font-mono text-[11px] text-slate-400 shrink-0 w-20">{formatObjectId(r.id)}</span>
              <span className="text-xs text-slate-800 truncate">{r.name || '—'}</span>
            </button>
          ))}
        </div>
      )}
      {open && !loading && query.trim() && results.length === 0 && (
        <div className="absolute left-0 right-0 top-full z-50 mt-1 rounded-lg border border-slate-200 bg-white shadow-lg px-3 py-2">
          <p className="text-xs text-slate-500">Kein freigegebenes Objekt gefunden</p>
        </div>
      )}
    </div>
  );
}

// ─── Step content per type ────────────────────────────────────────────────────

function RessourceContent({ schritt, canEdit, onSave }: {
  schritt: ProzessSchrittDef; canEdit: boolean;
  onSave: (d: Parameters<typeof api.updateSchritt>[2]) => void;
}) {
  const [menge, setMenge] = useState(schritt.referenz_menge ?? 1);
  const [einheit, setEinheit] = useState(schritt.ressourcen?.[0]?.einheit ?? 'Stk');
  const [objName, setObjName] = useState<string | null>(schritt.ressourcen?.[0]?.name ?? null);

  useEffect(() => {
    setMenge(schritt.referenz_menge ?? 1);
    setEinheit(schritt.ressourcen?.[0]?.einheit ?? 'Stk');
    setObjName(schritt.ressourcen?.[0]?.name ?? null);
  }, [schritt.id]);

  function saveAll(id: number | null, name: string | null, m: number, e: string) {
    onSave({ referenz_objekt_id: id, referenz_menge: m, ressourcen: id ? [{ ref_id: id, name: name ?? String(id), menge: m, einheit: e }] : [] });
  }

  return (
    <div className="space-y-2">
      <ObjektSearchField
        selectedId={schritt.referenz_objekt_id} selectedName={objName} canEdit={canEdit}
        onSelect={(id, name) => { setObjName(name); saveAll(id, name, menge, einheit); }}
        onClear={() => { setObjName(null); saveAll(null, null, menge, einheit); }}
      />
      <div className="flex gap-2">
        <input type="number" value={menge} disabled={!canEdit} min={0.001} step={1} placeholder="Menge"
          onChange={(e) => { const v = parseFloat(e.target.value) || 1; setMenge(v); if (schritt.referenz_objekt_id) saveAll(schritt.referenz_objekt_id, objName, v, einheit); }}
          className="form-input text-xs w-20 disabled:bg-slate-50"
        />
        <input type="text" value={einheit} disabled={!canEdit} placeholder="Stk"
          onChange={(e) => { setEinheit(e.target.value); if (schritt.referenz_objekt_id) saveAll(schritt.referenz_objekt_id, objName, menge, e.target.value); }}
          className="form-input text-xs w-16 disabled:bg-slate-50"
        />
      </div>
    </div>
  );
}

function DatenContent({ schritt, canEdit, onSave }: {
  schritt: ProzessSchrittDef; canEdit: boolean;
  onSave: (d: Parameters<typeof api.updateSchritt>[2]) => void;
}) {
  const existing = schritt.daten_felder?.[0] ?? null;
  const [name, setName] = useState(existing?.name ?? '');
  const [typ, setTyp] = useState<DatenFeldDef['typ']>(existing?.typ ?? 'text');
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    const f = schritt.daten_felder?.[0];
    setName(f?.name ?? ''); setTyp(f?.typ ?? 'text');
  }, [schritt.id]);

  function save(n: string, t: DatenFeldDef['typ']) {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      onSave({ daten_felder: n.trim() ? [{ name: n.trim(), typ: t, pflicht: true }] : [] });
    }, 600);
  }

  return (
    <div className="flex gap-2">
      <input type="text" value={name} disabled={!canEdit} placeholder="Feldname…"
        onChange={(e) => { setName(e.target.value); save(e.target.value, typ); }}
        className="form-input flex-1 text-xs disabled:bg-slate-50"
      />
      <select value={typ} disabled={!canEdit}
        onChange={(e) => { const t = e.target.value as DatenFeldDef['typ']; setTyp(t); save(name, t); }}
        className="form-input w-20 text-xs disabled:bg-slate-50"
      >
        {DATENFELD_TYPEN.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
      </select>
    </div>
  );
}

function HilfsmittelContent({ schritt, canEdit, onSave }: {
  schritt: ProzessSchrittDef; canEdit: boolean;
  onSave: (d: Parameters<typeof api.updateSchritt>[2]) => void;
}) {
  const [objName, setObjName] = useState<string | null>(schritt.ressourcen?.[0]?.name ?? null);
  useEffect(() => { setObjName(schritt.ressourcen?.[0]?.name ?? null); }, [schritt.id]);

  return (
    <ObjektSearchField
      selectedId={schritt.referenz_objekt_id} selectedName={objName} canEdit={canEdit}
      onSelect={(id, name) => { setObjName(name); onSave({ referenz_objekt_id: id, ressourcen: [{ ref_id: id, name, menge: 1, einheit: '' }] }); }}
      onClear={() => { setObjName(null); onSave({ referenz_objekt_id: null, ressourcen: [] }); }}
    />
  );
}

function GateContent() {
  return (
    <div className="flex gap-2">
      <div className="flex-1 flex items-center gap-1.5 rounded-lg border border-green-200 bg-green-50 px-2.5 py-1.5">
        <ThumbsUp className="h-3 w-3 text-green-600 shrink-0" />
        <span className="text-[11px] font-medium text-green-700">OK → weiter</span>
      </div>
      <div className="flex-1 flex items-center gap-1.5 rounded-lg border border-red-200 bg-red-50 px-2.5 py-1.5">
        <ThumbsDown className="h-3 w-3 text-red-600 shrink-0" />
        <span className="text-[11px] font-medium text-red-700">Problem → MRA</span>
      </div>
    </div>
  );
}

function UnterprozessContent({ schritt, canEdit, onSave }: {
  schritt: ProzessSchrittDef; canEdit: boolean;
  onSave: (d: Parameters<typeof api.updateSchritt>[2]) => void;
}) {
  const [menge, setMenge] = useState(schritt.referenz_menge ?? 1);
  const [objName, setObjName] = useState<string | null>(schritt.ressourcen?.[0]?.name ?? null);

  useEffect(() => {
    setMenge(schritt.referenz_menge ?? 1);
    setObjName(schritt.ressourcen?.[0]?.name ?? null);
  }, [schritt.id]);

  function saveAll(id: number | null, name: string | null, m: number) {
    onSave({ referenz_objekt_id: id, referenz_menge: m, ressourcen: id ? [{ ref_id: id, name: name ?? String(id), menge: m, einheit: 'Stk' }] : [] });
  }

  return (
    <div className="space-y-2">
      <ObjektSearchField
        selectedId={schritt.referenz_objekt_id} selectedName={objName} canEdit={canEdit}
        placeholder="Prozess-Objekt suchen…"
        onSelect={(id, name) => { setObjName(name); saveAll(id, name, menge); }}
        onClear={() => { setObjName(null); saveAll(null, null, menge); }}
      />
      <div className="flex items-center gap-2">
        <span className="text-[11px] text-slate-500 shrink-0">Anzahl</span>
        <input type="number" value={menge} disabled={!canEdit} min={1} step={1} max={1000}
          onChange={(e) => { const m = Math.max(1, parseInt(e.target.value) || 1); setMenge(m); if (schritt.referenz_objekt_id) saveAll(schritt.referenz_objekt_id, objName, m); }}
          className="form-input text-xs w-16 disabled:bg-slate-50"
        />
        <span className="text-[11px] text-slate-400">Instanz(en) → warten bis alle fertig</span>
      </div>
    </div>
  );
}

// ─── Flowchart step card ──────────────────────────────────────────────────────

function FlowCard({
  schritt, position, isFirst, isLast, canEdit, objektId,
  onDelete, onMoveUp, onMoveDown, onSaved,
}: {
  schritt: ProzessSchrittDef; position: number; isFirst: boolean; isLast: boolean;
  canEdit: boolean; objektId: number;
  onDelete: () => void; onMoveUp: () => void; onMoveDown: () => void; onSaved: () => void;
}) {
  const qc = useQueryClient();
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const typ = (schritt.schritt_typ ?? 'ressource') as SchrittTyp;
  const cfg = SCHRITT_TYP_CONFIG[typ] ?? SCHRITT_TYP_CONFIG.ressource;
  const Icon = cfg.icon;

  const { mutate: save, isPending } = useMutation({
    mutationFn: (data: Parameters<typeof api.updateSchritt>[2]) => api.updateSchritt(objektId, schritt.id, data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['uni-objekt', objektId] }); onSaved(); },
  });

  const saveImm = useCallback((data: Parameters<typeof api.updateSchritt>[2]) => {
    if (!canEdit) return;
    if (debounceRef.current) clearTimeout(debounceRef.current);
    save(data);
  }, [canEdit, save]);

  const saveDebounced = useCallback((data: Parameters<typeof api.updateSchritt>[2]) => {
    if (!canEdit) return;
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => save(data), 500);
  }, [canEdit, save]);

  return (
    <div className="rounded-lg border border-slate-200 bg-white shadow-sm overflow-hidden">
      <div className={cn('flex items-center gap-2 px-2.5 py-1.5 border-b border-slate-200', cfg.headerBg)}>
        <span className={cn('flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-white/60 text-[10px] font-bold', cfg.iconColor)}>
          {position}
        </span>
        <Icon className={cn('h-3 w-3 shrink-0', cfg.iconColor)} />
        <span className={cn('text-[11px] font-semibold shrink-0', cfg.iconColor)}>{cfg.label}</span>
        {cfg.badge && <span className={cn('text-[10px] px-1 py-0.5 rounded-full', cfg.badgeColor)}>{cfg.badge}</span>}
        <input
          key={`${schritt.id}-d`} type="text" defaultValue={schritt.beschreibung} disabled={!canEdit}
          onChange={(e) => saveDebounced({ beschreibung: e.target.value })}
          className="flex-1 min-w-0 text-xs font-medium text-slate-800 bg-transparent border-none outline-none focus:ring-0 disabled:text-slate-600 placeholder:text-slate-400"
          placeholder="Beschreibung…"
        />
        {isPending && <Loader2 className="h-3 w-3 animate-spin text-slate-400 shrink-0" />}
        {canEdit && (
          <div className="flex items-center shrink-0">
            <button type="button" disabled={isFirst} onClick={onMoveUp} className="p-0.5 text-slate-400 hover:text-slate-700 disabled:opacity-25">
              <ChevronUp className="h-3 w-3" />
            </button>
            <button type="button" disabled={isLast} onClick={onMoveDown} className="p-0.5 text-slate-400 hover:text-slate-700 disabled:opacity-25">
              <ChevronDown className="h-3 w-3" />
            </button>
            <button type="button" onClick={onDelete} className="p-0.5 text-slate-400 hover:text-red-500">
              <Trash2 className="h-3 w-3" />
            </button>
          </div>
        )}
      </div>
      <div className="px-3 py-2">
        {typ === 'ressource' && <RessourceContent schritt={schritt} canEdit={canEdit} onSave={saveImm} />}
        {typ === 'daten' && <DatenContent schritt={schritt} canEdit={canEdit} onSave={saveImm} />}
        {typ === 'hilfsmittel' && <HilfsmittelContent schritt={schritt} canEdit={canEdit} onSave={saveImm} />}
        {typ === 'gate' && <GateContent />}
        {typ === 'unterprozess' && <UnterprozessContent schritt={schritt} canEdit={canEdit} onSave={saveImm} />}
      </div>
    </div>
  );
}

function Connector() {
  return (
    <div className="flex flex-col items-center py-0.5">
      <div className="w-px h-3 bg-slate-300" />
      <ArrowDown className="h-2.5 w-2.5 text-slate-300 -mt-0.5" />
    </div>
  );
}

// ─── Prozess Tab ──────────────────────────────────────────────────────────────

function ProzessTab({ objekt, canEdit, onSaved }: {
  objekt: UniObjekt; canEdit: boolean; onSaved: () => void;
}) {
  const qc = useQueryClient();
  const [showChooser, setShowChooser] = useState(false);

  const addMut = useMutation({
    mutationFn: (typ: SchrittTyp) => api.addSchritt(objekt.id, {
      position: (objekt.schritte.at(-1)?.position ?? 0) + 1,
      beschreibung: '',
      schritt_typ: typ,
    }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['uni-objekt', objekt.id] }); onSaved(); },
  });

  const delMut = useMutation({
    mutationFn: (id: number) => api.deleteSchritt(objekt.id, id),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['uni-objekt', objekt.id] }); onSaved(); },
  });

  const moveMut = useMutation({
    mutationFn: ({ id, pos }: { id: number; pos: number }) => api.updateSchritt(objekt.id, id, { position: pos }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['uni-objekt', objekt.id] }); onSaved(); },
  });

  const sorted = [...objekt.schritte].sort((a, b) => a.position - b.position);

  function moveUp(s: ProzessSchrittDef) {
    const i = sorted.findIndex((x) => x.id === s.id);
    if (i <= 0) return;
    moveMut.mutate({ id: s.id, pos: sorted[i - 1].position });
    moveMut.mutate({ id: sorted[i - 1].id, pos: s.position });
  }
  function moveDown(s: ProzessSchrittDef) {
    const i = sorted.findIndex((x) => x.id === s.id);
    if (i >= sorted.length - 1) return;
    moveMut.mutate({ id: s.id, pos: sorted[i + 1].position });
    moveMut.mutate({ id: sorted[i + 1].id, pos: s.position });
  }

  return (
    <div className="p-3">
      {!canEdit && (
        <div className="flex items-center gap-1.5 rounded-lg border border-slate-200 bg-slate-50 px-3 py-1.5 text-xs text-slate-500 mb-3">
          <Lock className="h-3 w-3 shrink-0" /> Freigegeben — Prozess gesperrt
        </div>
      )}
      <div className="flex justify-center mb-0.5">
        <div className="rounded-full border border-slate-300 bg-white px-3 py-0.5 text-[11px] font-semibold text-slate-500 shadow-sm">▶ START</div>
      </div>
      {sorted.length === 0 && <><Connector /><p className="text-center text-[11px] text-slate-400 py-2">Noch keine Schritte</p></>}
      {sorted.map((s, i) => (
        <div key={s.id}>
          <Connector />
          <FlowCard
            schritt={s} position={i + 1} isFirst={i === 0} isLast={i === sorted.length - 1}
            canEdit={canEdit} objektId={objekt.id}
            onDelete={() => delMut.mutate(s.id)}
            onMoveUp={() => moveUp(s)} onMoveDown={() => moveDown(s)}
            onSaved={onSaved}
          />
        </div>
      ))}
      {canEdit && (
        <>
          <Connector />
          <div className="flex justify-center">
            <button
              type="button" onClick={() => setShowChooser(true)} disabled={addMut.isPending}
              className="flex items-center gap-1.5 rounded-full border-2 border-dashed border-slate-300 px-4 py-1 text-xs text-slate-500 hover:border-red-400 hover:text-red-600 hover:bg-red-50 transition-colors disabled:opacity-50"
            >
              {addMut.isPending ? <Loader2 className="h-3 w-3 animate-spin" /> : <Plus className="h-3 w-3" />}
              Schritt hinzufügen
            </button>
          </div>
        </>
      )}
      {sorted.length > 0 && (
        <>
          <Connector />
          <div className="flex justify-center">
            <div className="rounded-full border-2 border-slate-400 bg-white px-3 py-0.5 text-[11px] font-bold text-slate-600 shadow-sm">⬛ ENDE</div>
          </div>
        </>
      )}
      {showChooser && (
        <TypeChooser
          onSelect={(t) => { setShowChooser(false); addMut.mutate(t); }}
          onClose={() => setShowChooser(false)}
        />
      )}
    </div>
  );
}

// ─── Stammdaten Tab ───────────────────────────────────────────────────────────

function StammdatenTab({ objekt, itemNames, canEdit, onSave }: {
  objekt: UniObjekt; itemNames: ItemName[]; canEdit: boolean;
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
    <div className="p-4 space-y-4">
      {!canEdit && (
        <div className="flex items-center gap-1.5 rounded-lg border border-slate-200 bg-slate-50 px-3 py-1.5 text-xs text-slate-500">
          <Lock className="h-3 w-3 shrink-0" /> Freigegeben — nicht editierbar
        </div>
      )}
      <div>
        <label className="block text-xs font-medium text-slate-700 mb-1">Name <span className="text-red-500">*</span></label>
        <input key={objekt.id} type="text" list="obj-namen" defaultValue={objekt.name ?? ''} disabled={!canEdit}
          onChange={(e) => schedule({ name: e.target.value })}
          className="form-input text-sm disabled:bg-slate-50 disabled:text-slate-500" placeholder="Objektname…"
        />
        <datalist id="obj-namen">{activeNames.map((n) => <option key={n.id} value={n.label} />)}</datalist>
      </div>
      <div>
        <label className="block text-xs font-medium text-slate-700 mb-1">Einheit</label>
        <input key={`${objekt.id}-e`} type="text" defaultValue={objekt.einheit ?? ''} disabled={!canEdit}
          onChange={(e) => schedule({ einheit: e.target.value })}
          className="form-input text-sm disabled:bg-slate-50 disabled:text-slate-500" placeholder="z.B. Stk…"
        />
      </div>
      <div>
        <label className="block text-xs font-medium text-slate-700 mb-1">Notiz</label>
        <textarea key={`${objekt.id}-n`} defaultValue={objekt.notiz ?? ''} disabled={!canEdit}
          onChange={(e) => schedule({ notiz: e.target.value })}
          rows={3} className="form-input resize-none text-sm disabled:bg-slate-50 disabled:text-slate-500" placeholder="Optionale Beschreibung…"
        />
      </div>
      <dl className="grid grid-cols-2 gap-3 pt-2 border-t border-slate-100">
        <div><dt className="text-[11px] text-slate-400 uppercase tracking-wide">Nr.</dt><dd className="mt-0.5 text-xs font-mono text-slate-900">{formatObjectId(objekt.id)}</dd></div>
        <div><dt className="text-[11px] text-slate-400 uppercase tracking-wide">Status</dt><dd className="mt-0.5"><ObjStatusBadge status={objekt.obj_status} /></dd></div>
        <div><dt className="text-[11px] text-slate-400 uppercase tracking-wide">Erstellt</dt><dd className="mt-0.5 text-xs text-slate-700">{new Date(objekt.created_at).toLocaleDateString('de-CH')}</dd></div>
        <div><dt className="text-[11px] text-slate-400 uppercase tracking-wide">Schritte</dt><dd className="mt-0.5 text-xs text-slate-700">{objekt.schritte.length}</dd></div>
      </dl>
    </div>
  );
}

// ─── Main component ────────────────────────────────────────────────────────────

type Tab = 'prozess' | 'stammdaten';

export function ObjektStammdatenForm({ objekt, currentUserRole: _role, onRefresh, onNavigate }: {
  objekt: UniObjekt; currentUserRole?: string; onRefresh?: () => void; onNavigate?: (id: number) => void;
}) {
  const qc = useQueryClient();
  const [tab, setTab] = useState<Tab>('prozess');
  const [lastSaved, setLastSaved] = useState<Date | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const canEdit = objekt.obj_status === 'ENTWURF';
  const canFreigeben = canEdit && objekt.schritte.length > 0 && (objekt.name ?? '').trim().length > 0;

  const { data: itemNames = [] } = useQuery({
    queryKey: ['item-names'], queryFn: () => api.getItemNames(), staleTime: 60_000,
  });

  const { mutate: saveStamm } = useMutation({
    mutationFn: (data: { name?: string; notiz?: string; einheit?: string }) => api.updateUniObjekt(objekt.id, data),
    onMutate: () => { setSaving(true); setError(''); },
    onSuccess: (updated) => {
      qc.setQueryData(['uni-objekt', objekt.id], updated);
      qc.invalidateQueries({ queryKey: ['objects'] });
      setLastSaved(new Date()); setSaving(false); onRefresh?.();
    },
    onError: (e: Error) => { setError(e.message); setSaving(false); },
  });

  const { mutate: freigeben, isPending: freigebeLoading } = useMutation({
    mutationFn: () => api.freigeben(objekt.id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['uni-objekt', objekt.id] });
      qc.invalidateQueries({ queryKey: ['objects'] });
      setLastSaved(new Date()); onRefresh?.();
    },
    onError: (e: Error) => setError(e.message),
  });

  const { mutate: ausfuehren, isPending: ausfuehrenLoading } = useMutation({
    mutationFn: () => api.ausfuehren(objekt.id, { menge: 1 }),
    onSuccess: (instanzen) => {
      qc.invalidateQueries({ queryKey: ['objects'] });
      if (instanzen[0]?.id && onNavigate) {
        onNavigate(instanzen[0].id);
      }
      onRefresh?.();
    },
    onError: (e: Error) => setError(e.message),
  });

  const savedTime = lastSaved ? lastSaved.toLocaleTimeString('de-CH', { hour: '2-digit', minute: '2-digit' }) : null;

  return (
    <div className="flex flex-col overflow-hidden flex-1 bg-white">
      <div className="px-4 py-3 border-b border-slate-200 shrink-0">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="flex items-center gap-1.5 mb-0.5">
              <span className="text-[11px] font-mono text-slate-400">{formatObjectId(objekt.id)}</span>
              <span className="text-[11px] text-slate-300">·</span>
              <span className="text-[11px] text-slate-400">Vorlage</span>
              {!canEdit && <Lock className="h-2.5 w-2.5 text-slate-400" />}
            </div>
            <h2 className="text-base font-semibold text-slate-900 leading-tight truncate">
              {objekt.name || <span className="text-slate-400 italic font-normal text-sm">Unbenannt</span>}
            </h2>
          </div>
          <div className="shrink-0 flex flex-col items-end gap-1.5">
            <ObjStatusBadge status={objekt.obj_status} />
            <div className="flex items-center gap-1 text-[11px] h-4">
              {saving && <><Loader2 className="h-2.5 w-2.5 animate-spin text-slate-400" /><span className="text-slate-400">…</span></>}
              {!saving && savedTime && <><CheckCircle2 className="h-2.5 w-2.5 text-green-500" /><span className="text-green-600">{savedTime}</span></>}
            </div>
          </div>
        </div>

        {error && (
          <div className="mt-1.5 flex items-center gap-1.5 text-xs text-red-600">
            <AlertCircle className="h-3 w-3 shrink-0" />{error}
          </div>
        )}

        <div className="flex items-center gap-2 mt-2">
          {canFreigeben && (
            <button type="button" disabled={freigebeLoading} onClick={() => freigeben()}
              className="flex items-center gap-1.5 rounded-lg bg-green-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-green-700 disabled:opacity-50 transition-colors"
            >
              {freigebeLoading ? <Loader2 className="h-3 w-3 animate-spin" /> : <Lock className="h-3 w-3" />}
              Freigeben
            </button>
          )}
          {objekt.obj_status === 'FREIGEGEBEN' && (
            <button type="button" disabled={ausfuehrenLoading} onClick={() => ausfuehren()}
              className="flex items-center gap-1.5 rounded-lg bg-blue-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-blue-700 disabled:opacity-50 transition-colors"
            >
              {ausfuehrenLoading ? <Loader2 className="h-3 w-3 animate-spin" /> : <Play className="h-3.5 w-3.5" />}
              Ausführen
            </button>
          )}
        </div>

        <div className="flex gap-1 mt-3 -mb-px">
          {(['prozess', 'stammdaten'] as Tab[]).map((t) => (
            <button key={t} type="button" onClick={() => setTab(t)}
              className={cn(
                'px-3 py-1 text-xs font-medium rounded-t-lg border-b-2 transition-colors',
                tab === t ? 'border-red-500 text-red-700 bg-red-50/40' : 'border-transparent text-slate-500 hover:text-slate-700 hover:bg-slate-50',
              )}
            >
              {t === 'prozess' ? `Prozess (${objekt.schritte.length})` : 'Stammdaten'}
            </button>
          ))}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto">
        {tab === 'prozess' && <ProzessTab objekt={objekt} canEdit={canEdit} onSaved={() => setLastSaved(new Date())} />}
        {tab === 'stammdaten' && <StammdatenTab objekt={objekt} itemNames={itemNames} canEdit={canEdit} onSave={saveStamm} />}
      </div>
    </div>
  );
}
