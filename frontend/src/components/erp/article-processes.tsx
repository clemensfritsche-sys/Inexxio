'use client';

import { useCallback, useEffect, useState } from 'react';
import { Plus, X, Trash2, Layers, Pencil, Check } from 'lucide-react';
import { api } from '@/lib/api';
import type { Process, ProcessSource, UserProfile } from '@/types';
import { ProcessSteps } from '@/components/erp/process-steps';
import { Segmented, TextField, ErrorText } from '@/components/erp/fields';

const SOURCE_LABEL: Record<ProcessSource, string> = {
  produce: 'Neu', stock: 'Bestand', instance: 'Instanz',
};
const SOURCE_HINT: Record<ProcessSource, string> = {
  produce: 'Quelle «Neu»: der Prozess erzeugt neue Instanzen (Produktion).',
  stock: 'Quelle «Bestand»: der Prozess entnimmt vorhandene Instanzen (FIFO) – z. B. Verkauf.',
  instance: 'Quelle «Instanz»: der Prozess wirkt auf eine konkrete Instanz – z. B. Wartung.',
};

/** Verwaltet die **mehreren Prozesse** eines Artikels (Entstehung, Verkauf, Wartung …)
 *  + zeigt die geerbten Standardprozesse. Der gewählte Prozess wird mit dem
 *  bestehenden Schritt-Editor (ProcessSteps) bearbeitet. */
export function ArticleProcesses({ articleObjectId, suppliers, readOnly = false, onStepsCount }: {
  articleObjectId: number | null;
  suppliers: UserProfile[];
  readOnly?: boolean;
  onStepsCount?: (n: number) => void;
}) {
  const [procs, setProcs] = useState<Process[]>([]);
  const [selId, setSelId] = useState<number | null>(null);
  const [adding, setAdding] = useState(false);
  const [name, setName] = useState('');
  const [source, setSource] = useState<ProcessSource>('produce');
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [renameId, setRenameId] = useState<number | null>(null);
  const [renameVal, setRenameVal] = useState('');

  const load = useCallback(() => {
    if (articleObjectId == null) return;
    api.getArticleProcesses(articleObjectId).then((ps) => {
      setProcs(ps);
      setSelId((cur) => (cur && ps.some((p) => p.id === cur) ? cur : ps[0]?.id ?? null));
    }).catch(() => {});
  }, [articleObjectId]);

  useEffect(() => { load(); }, [load]);

  // Gesamt-Schrittzahl der EIGENEN Prozesse (für die Artikel-Freigabe) melden.
  useEffect(() => {
    const own = procs.filter((p) => !p.is_standard);
    onStepsCount?.(own.reduce((s, p) => s + (p.step_count ?? 0), 0));
  }, [procs, onStepsCount]);

  if (articleObjectId == null) {
    return (
      <div style={notice}><span>Artikel zuerst speichern – danach lassen sich Prozesse hinterlegen.</span></div>
    );
  }
  const aid = articleObjectId;
  const selected = procs.find((p) => p.id === selId) ?? null;
  const ownSelected = !!selected && !selected.is_standard;

  async function addProcess() {
    if (!name.trim()) { setError('Bitte einen Namen angeben'); return; }
    setSaving(true); setError(null);
    try {
      const p = await api.createArticleProcess(aid, { name: name.trim(), source });
      setProcs((prev) => [...prev, p]);
      setSelId(p.id);
      setAdding(false); setName(''); setSource('produce');
    } catch (e) { setError(e instanceof Error ? e.message : 'Fehler beim Anlegen'); }
    finally { setSaving(false); }
  }

  async function rename(id: number) {
    try {
      const p = await api.updateArticleProcess(aid, id, { name: renameVal.trim() });
      setProcs((prev) => prev.map((x) => (x.id === id ? p : x)));
      setRenameId(null);
    } catch { /* ignore */ }
  }

  async function remove(id: number) {
    try {
      await api.deleteArticleProcess(aid, id);
      setProcs((prev) => prev.filter((p) => p.id !== id));
      if (selId === id) setSelId(null);
    } catch (e) { setError(e instanceof Error ? e.message : 'Konnte nicht entfernt werden'); }
  }

  // ProcessSteps meldet die Schrittzahl des GEWÄHLTEN Prozesses → lokal aktualisieren.
  function onSelectedStepsCount(n: number) {
    setProcs((prev) => prev.map((p) => (p.id === selId ? { ...p, step_count: n } : p)));
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      {/* Prozess-Auswahl */}
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
        {procs.map((p) => {
          const active = p.id === selId;
          return (
            <button key={p.id} onClick={() => setSelId(p.id)} style={{
              display: 'flex', alignItems: 'center', gap: 6, padding: '6px 12px', borderRadius: 10,
              border: `1.5px solid ${active ? '#2563eb' : '#e2e8f0'}`, background: active ? '#eff6ff' : '#fff',
              cursor: 'pointer', textAlign: 'left',
            }}>
              <Layers size={14} style={{ color: active ? '#2563eb' : '#94a3b8' }} />
              <span style={{ fontSize: 13, fontWeight: 600, color: active ? '#1d4ed8' : '#0f172a' }}>{p.name}</span>
              <span style={{ fontSize: 10, fontWeight: 700, color: '#64748b', background: '#f1f5f9', padding: '1px 6px', borderRadius: 999 }}>
                {SOURCE_LABEL[p.source as ProcessSource] ?? p.source}
              </span>
              {p.is_standard && <span style={{ fontSize: 10, fontWeight: 700, color: '#7c3aed', background: '#f5f3ff', padding: '1px 6px', borderRadius: 999 }}>Standard</span>}
            </button>
          );
        })}
        {!readOnly && !adding && (
          <button onClick={() => setAdding(true)} style={addChip}><Plus size={14} /> Prozess</button>
        )}
      </div>

      {/* Neuer Prozess */}
      {adding && (
        <div style={card}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontSize: 13, fontWeight: 700, color: '#0f172a' }}>Neuer Prozess</span>
            <button onClick={() => { setAdding(false); setError(null); }} style={ghostIcon}><X size={16} /></button>
          </div>
          <TextField label="Name (frei wählbar)" value={name} onChange={setName} required placeholder="z. B. Verkauf, Jahreswartung" />
          <div>
            <Segmented label="Quelle (bestimmt das Verhalten – nicht der Name)" value={source}
              onChange={(v) => setSource(v as ProcessSource)} options={[
                { value: 'produce', label: 'Neu' }, { value: 'stock', label: 'Bestand' }, { value: 'instance', label: 'Instanz' },
              ]} />
            <div style={{ marginTop: 4, fontSize: 11, color: '#94a3b8' }}>{SOURCE_HINT[source]}</div>
          </div>
          {error && <ErrorText msg={error} />}
          <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
            <button onClick={() => { setAdding(false); setError(null); }} style={secondary}>Abbrechen</button>
            <button onClick={addProcess} disabled={saving} style={primary}>{saving ? 'Speichern…' : 'Anlegen'}</button>
          </div>
        </div>
      )}

      {/* Kopf des gewählten Prozesses */}
      {selected && (
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
          {renameId === selected.id ? (
            <div style={{ display: 'flex', gap: 6, alignItems: 'center', flex: 1 }}>
              <input value={renameVal} onChange={(e) => setRenameVal(e.target.value)}
                className="px-2.5 py-1.5 text-sm rounded-md border bg-white outline-none focus:ring-2 focus:ring-blue-500"
                style={{ borderColor: '#e2e8f0', flex: 1 }} />
              <button onClick={() => rename(selected.id)} style={primary}><Check size={14} /></button>
            </div>
          ) : (
            <div style={{ fontSize: 12, color: '#64748b' }}>
              {selected.is_standard
                ? 'Geerbter Standardprozess – zentral verwaltet, hier nur lesbar.'
                : SOURCE_HINT[selected.source as ProcessSource]}
            </div>
          )}
          {!readOnly && ownSelected && renameId !== selected.id && (
            <div style={{ display: 'flex', gap: 6, flexShrink: 0 }}>
              <button onClick={() => { setRenameId(selected.id); setRenameVal(selected.name); }} style={ghostIcon} title="Umbenennen"><Pencil size={14} /></button>
              {selected.source !== 'produce' && (
                <button onClick={() => remove(selected.id)} style={ghostIcon} title="Prozess entfernen"><Trash2 size={14} /></button>
              )}
            </div>
          )}
        </div>
      )}

      {/* Schritte des gewählten Prozesses (geerbte Standardprozesse: nur lesbar) */}
      <ProcessSteps
        processId={selId}
        suppliers={suppliers}
        readOnly={readOnly || !!selected?.is_standard}
        selfArticleObjectId={aid}
        onStepsCount={onSelectedStepsCount}
      />
    </div>
  );
}

const notice: React.CSSProperties = {
  display: 'flex', alignItems: 'flex-start', gap: 8, padding: '12px 14px',
  background: '#fffbeb', border: '1px solid #fde68a', borderRadius: 10, fontSize: 13, color: '#92400e',
};
const card: React.CSSProperties = {
  display: 'flex', flexDirection: 'column', gap: 12, background: '#fff',
  border: '1px solid #E2E8F0', borderRadius: 10, padding: '12px 14px',
};
const addChip: React.CSSProperties = {
  display: 'flex', alignItems: 'center', gap: 5, padding: '6px 12px', borderRadius: 10,
  border: '1px dashed #cbd5e1', background: '#fff', color: '#2563eb', fontSize: 13, fontWeight: 600, cursor: 'pointer',
};
const primary: React.CSSProperties = {
  padding: '7px 14px', borderRadius: 7, border: 'none', background: '#2563eb', color: '#fff', fontSize: 13, fontWeight: 600, cursor: 'pointer',
};
const secondary: React.CSSProperties = {
  padding: '7px 14px', borderRadius: 7, border: '1px solid #E2E8F0', background: '#fff', color: '#374151', fontSize: 13, cursor: 'pointer',
};
const ghostIcon: React.CSSProperties = {
  border: 'none', background: 'none', color: '#94a3b8', cursor: 'pointer', padding: 4,
};
