'use client';

import { useCallback, useEffect, useState } from 'react';
import { Plus, X, Trash2, Layers, Pencil, Check, Link2, Star } from 'lucide-react';
import { api } from '@/lib/api';
import type { Process, UserProfile } from '@/types';
import { ProcessSteps } from '@/components/erp/process-steps';
import { TextField, ErrorText, SearchSelect, StatusBadge, StatusFlow } from '@/components/erp/fields';
import { sourceLabel, processStatusConfig } from '@/lib/process';
import { lifecycleActions, type StatusAction } from '@/lib/status-flow';
import { ObjId } from '@/components/erp/obj-id';
import { fmtObjId } from '@/components/erp/user-detail';

// Lebenszyklus-Aktionen eines (eigenen) Prozesses: Freigeben erst mit ≥1 Schritt.
function processActions(p: Process): StatusAction[] {
  if (p.status === 'draft')
    return [{ label: 'Freigeben', target: 'released', tone: 'primary',
      disabled: (p.step_count ?? 0) === 0, hint: (p.step_count ?? 0) === 0 ? 'Erst einen Schritt hinzufügen' : undefined }];
  return lifecycleActions(p.status, { canReactivate: true, canReplace: true });
}

/** Prozessstückliste eines Artikels: verlinkte Prozesse + geerbte Standardprozesse.
 *  Hinzufügen/Entfernen wirkt nur auf **diesen** Artikel (Link); Freigeben/Deaktivieren/
 *  Ersetzen wirkt am Prozess-Objekt (und damit auf alle Artikel, die ihn führen). */
export function ArticleProcesses({ articleObjectId, suppliers, readOnly = false, onChanged }: {
  articleObjectId: number | null;
  suppliers: UserProfile[];
  readOnly?: boolean;
  onChanged?: () => void;   // Prozess-Feed aktualisieren (Stückliste/Lebenszyklus geändert)
}) {
  const [procs, setProcs] = useState<Process[]>([]);
  const [selId, setSelId] = useState<number | null>(null);
  const [adding, setAdding] = useState<'new' | 'link' | null>(null);
  const [name, setName] = useState('');
  const [linkPick, setLinkPick] = useState('');
  const [catalog, setCatalog] = useState<Process[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [statusBusy, setStatusBusy] = useState(false);
  const [renameId, setRenameId] = useState<number | null>(null);
  const [renameVal, setRenameVal] = useState('');

  const load = useCallback(async (selectId?: number) => {
    if (articleObjectId == null) return;
    try {
      const ps = await api.getArticleProcesses(articleObjectId);
      setProcs(ps);
      setSelId((cur) => {
        const want = selectId ?? cur;
        return want && ps.some((p) => p.id === want) ? want : ps[0]?.id ?? null;
      });
    } catch { /* ignore */ }
  }, [articleObjectId]);

  useEffect(() => { void load(); }, [load]);

  // Nach einer Mutation neu laden UND den Prozess-Feed aktualisieren (kein Reload nötig).
  const reload = useCallback(async (selectId?: number) => { await load(selectId); onChanged?.(); }, [load, onChanged]);

  // Katalog (alle verlinkbaren Prozesse) erst bei Bedarf laden.
  useEffect(() => {
    if (adding !== 'link') return;
    api.getProcesses().then(setCatalog).catch(() => {});
  }, [adding]);

  if (articleObjectId == null) {
    return <div style={notice}><span>Artikel zuerst speichern – danach lässt sich die Prozessstückliste pflegen.</span></div>;
  }
  const aid = articleObjectId;
  const selected = procs.find((p) => p.id === selId) ?? null;
  const ownSelected = !!selected && !selected.is_standard;
  const linkedIds = new Set(procs.map((p) => p.id));
  const linkable = catalog.filter((p) => !p.is_standard && !linkedIds.has(p.id));

  async function addProcess() {
    if (!name.trim()) { setError('Bitte einen Namen angeben'); return; }
    setSaving(true); setError(null);
    try {
      const p = await api.createArticleProcess(aid, { name: name.trim() });
      await reload(p.id);
      setAdding(null); setName('');
    } catch (e) { setError(e instanceof Error ? e.message : 'Fehler beim Anlegen'); }
    finally { setSaving(false); }
  }

  async function linkProcess() {
    if (!linkPick) { setError('Bitte einen Prozess wählen'); return; }
    setSaving(true); setError(null);
    try {
      const p = await api.addProcessLink(aid, Number(linkPick));
      await reload(p.id);
      setAdding(null); setLinkPick('');
    } catch (e) { setError(e instanceof Error ? e.message : 'Konnte nicht verlinkt werden'); }
    finally { setSaving(false); }
  }

  async function rename(p: Process) {
    if (!p.object_id) return;
    try {
      await api.updateProcess(p.object_id, { name: renameVal.trim() });
      setRenameId(null);
      await reload(p.id);
    } catch (e) { setError(e instanceof Error ? e.message : 'Umbenennen fehlgeschlagen'); }
  }

  async function unlink(p: Process) {
    setError(null);
    try {
      await api.removeProcessLink(aid, p.id);
      await reload();
    } catch (e) { setError(e instanceof Error ? e.message : 'Konnte nicht entfernt werden'); }
  }

  async function onProcessAction(target: string) {
    if (!selected?.object_id) return;
    setStatusBusy(true); setError(null);
    try {
      if (target === 'replace') {
        const np = await api.replaceProcess(selected.object_id);
        await reload(np.id);
      } else {
        await api.updateProcess(selected.object_id, { status: target as 'draft' | 'released' | 'inactive' });
        await reload(selected.id);
      }
    } catch (e) { setError(e instanceof Error ? e.message : 'Statuswechsel fehlgeschlagen'); }
    finally { setStatusBusy(false); }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      {/* Stückliste: schlichte Chips – Name, Status-Punkt, ggf. Standard-Stern */}
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
        {procs.map((p) => {
          const active = p.id === selId;
          const scfg = processStatusConfig(p.status);
          return (
            <button key={p.id} onClick={() => setSelId(p.id)} style={{
              display: 'flex', alignItems: 'center', gap: 6, padding: '6px 12px', borderRadius: 10,
              border: `1.5px solid ${active ? '#2563eb' : '#e2e8f0'}`, background: active ? '#eff6ff' : '#fff',
              cursor: 'pointer', textAlign: 'left',
            }} title={`${scfg.label}${p.is_standard ? ' · Standard' : ''}`}>
              <span style={{ width: 8, height: 8, borderRadius: 999, background: scfg.color, flexShrink: 0 }} />
              <span style={{ fontSize: 13, fontWeight: 600, color: active ? '#1d4ed8' : '#0f172a' }}>{p.name}</span>
              {p.is_standard && <Star size={12} fill="#f59e0b" color="#f59e0b" strokeWidth={2} />}
            </button>
          );
        })}
        {!readOnly && !adding && (
          <>
            <button onClick={() => { setAdding('new'); setError(null); }} style={addChip}><Plus size={14} /> Neuer Prozess</button>
            <button onClick={() => { setAdding('link'); setError(null); }} style={addChip}><Link2 size={14} /> Verlinken</button>
          </>
        )}
      </div>

      {/* Neuer Prozess */}
      {adding === 'new' && (
        <div style={card}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontSize: 13, fontWeight: 700, color: '#0f172a' }}>Neuer Prozess (Entwurf)</span>
            <button onClick={() => { setAdding(null); setError(null); }} style={ghostIcon}><X size={16} /></button>
          </div>
          <TextField label="Name (frei wählbar)" value={name} onChange={setName} required placeholder="z. B. Verkauf, Jahreswartung" />
          <div style={{ fontSize: 11, color: '#94a3b8' }}>Das Verhalten ergibt sich aus den Schritten (im Anschluss definieren).</div>
          {error && <ErrorText msg={error} />}
          <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
            <button onClick={() => { setAdding(null); setError(null); }} style={secondary}>Abbrechen</button>
            <button onClick={addProcess} disabled={saving} style={primary}>{saving ? 'Speichern…' : 'Anlegen & verlinken'}</button>
          </div>
        </div>
      )}

      {/* Bestehenden Prozess verlinken */}
      {adding === 'link' && (
        <div style={card}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontSize: 13, fontWeight: 700, color: '#0f172a' }}>Bestehenden Prozess verlinken</span>
            <button onClick={() => { setAdding(null); setError(null); }} style={ghostIcon}><X size={16} /></button>
          </div>
          <SearchSelect label="Prozess" value={linkPick} onChange={setLinkPick}
            placeholder="Prozess suchen (Name oder Nummer)…"
            options={[{ value: '', label: '— wählen —' }, ...linkable.map((p) => ({
              value: String(p.id), label: `${fmtObjId(p.object_id)} · ${p.name}` }))]} />
          <div style={{ fontSize: 11, color: '#94a3b8' }}>
            Derselbe Prozess kann bei mehreren Artikeln liegen. Inaktiv/Ersetzen wirkt dann auf alle.
          </div>
          {error && <ErrorText msg={error} />}
          <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
            <button onClick={() => { setAdding(null); setError(null); }} style={secondary}>Abbrechen</button>
            <button onClick={linkProcess} disabled={saving || !linkPick} style={primary}>{saving ? 'Verlinken…' : 'Verlinken'}</button>
          </div>
        </div>
      )}

      {/* Kopf des gewählten Prozesses */}
      {selected && (
        <div style={{ ...card, gap: 10 }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8, flexWrap: 'wrap' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
              <Layers size={15} style={{ color: '#7c3aed' }} />
              {renameId === selected.id ? (
                <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                  <input value={renameVal} onChange={(e) => setRenameVal(e.target.value)}
                    className="px-2.5 py-1.5 text-sm rounded-md border bg-white outline-none focus:ring-2 focus:ring-blue-500"
                    style={{ borderColor: '#e2e8f0' }} />
                  <button onClick={() => rename(selected)} style={primary}><Check size={14} /></button>
                </div>
              ) : (
                <>
                  <span style={{ fontSize: 14, fontWeight: 700, color: '#0f172a' }}>{selected.name}</span>
                  <span style={{ fontSize: 12 }}><ObjId value={selected.object_id} /></span>
                </>
              )}
              <StatusBadge cfg={processStatusConfig(selected.status)} />
              {selected.is_standard && <Star size={13} fill="#f59e0b" color="#f59e0b" strokeWidth={2} />}
            </div>
            {!readOnly && ownSelected && renameId !== selected.id && (
              <div style={{ display: 'flex', gap: 6, flexShrink: 0 }}>
                {selected.status === 'draft' && (
                  <button onClick={() => { setRenameId(selected.id); setRenameVal(selected.name); }} style={ghostIcon} title="Umbenennen"><Pencil size={14} /></button>
                )}
                {selected.source !== 'produce' && (
                  <button onClick={() => unlink(selected)} style={ghostIcon} title="Aus Stückliste entfernen"><Trash2 size={14} /></button>
                )}
              </div>
            )}
          </div>
          <div style={{ fontSize: 12, color: '#64748b' }}>
            {selected.is_standard
              ? 'Geerbter Standardprozess – zentral verwaltet, hier nur lesbar.'
              : `Subjekt: ${sourceLabel(selected.source)}${selected.linked_article_count > 1 ? ` · bei ${selected.linked_article_count} Artikeln` : ''}`}
          </div>
          {!readOnly && ownSelected && (
            <StatusFlow cfg={processStatusConfig(selected.status)} actions={processActions(selected)} busy={statusBusy} onAction={onProcessAction} />
          )}
          {error && <ErrorText msg={error} />}
        </div>
      )}

      {/* Schritte des gewählten Prozesses (geerbte Standards & freigegebene: nur lesbar) */}
      <ProcessSteps
        processId={selId}
        suppliers={suppliers}
        readOnly={readOnly || !!selected?.is_standard || selected?.status !== 'draft'}
        selfArticleObjectId={aid}
        onStepsCount={(n) => setProcs((prev) => prev.map((p) => (p.id === selId ? { ...p, step_count: n } : p)))}
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
