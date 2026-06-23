'use client';

import { useEffect, useState } from 'react';
import { ArrowLeft, Repeat, CheckCircle2, Ban, RotateCcw, Play } from 'lucide-react';
import { api } from '@/lib/api';
import type { Article, Instance, Process, RecurringOrder, RecurringOrderInput } from '@/types';
import { Segmented, TextField, SearchSelect, ErrorText } from '@/components/erp/fields';
import { fmtObjId } from '@/components/erp/user-detail';

const STATUS_CFG: Record<string, { label: string; color: string; bg: string }> = {
  draft: { label: 'Entwurf', color: '#d97706', bg: '#fffbeb' },
  released: { label: 'Aktiv', color: '#16a34a', bg: '#f0fdf4' },
  inactive: { label: 'Inaktiv', color: '#475569', bg: '#f1f5f9' },
};

/** Wiederkehrender Vorgang (Compliance/Termin oder Abo) – erzeugt automatisch Aufträge.
 *  Compliance: vor Ablauf erledigen (valid_until − Vorlaufzeit). Abo: fester Intervall. */
export function RecurringDetail({ record, onSaved, onBack }: {
  record: RecurringOrder | null;
  onSaved: (r: RecurringOrder) => void;
  onBack: () => void;
}) {
  const isCreate = record === null;
  const [processes, setProcesses] = useState<Process[]>([]);
  const [articles, setArticles] = useState<Article[]>([]);
  const [instances, setInstances] = useState<Instance[]>([]);

  const [name, setName] = useState(record?.name ?? '');
  const [processId, setProcessId] = useState(record?.process_id ? String(record.process_id) : '');
  const [articleId, setArticleId] = useState(record?.article_id ? String(record.article_id) : '');
  const [quantity, setQuantity] = useState(record?.quantity ? String(record.quantity) : '1');
  const [instanceId, setInstanceId] = useState(record?.subject_instance_id ? String(record.subject_instance_id) : '');
  const [mode, setMode] = useState<'compliance' | 'abo'>(record?.interval_days ? 'abo' : 'compliance');
  const [validUntil, setValidUntil] = useState(record?.valid_until ?? '');
  const [leadDays, setLeadDays] = useState(record?.lead_time_days != null ? String(record.lead_time_days) : '30');
  const [validityDays, setValidityDays] = useState(record?.validity_days ? String(record.validity_days) : '365');
  const [intervalDays, setIntervalDays] = useState(record?.interval_days ? String(record.interval_days) : '30');
  const [nextDue, setNextDue] = useState(record?.next_due_at ?? '');
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const status = record?.status ?? 'draft';

  useEffect(() => {
    api.getStandardProcesses().then((ps) => setProcesses(ps.filter((p) => p.status === 'released'))).catch(() => {});
    api.getArticles().then((a) => setArticles(a.filter((x) => x.status === 'released'))).catch(() => {});
    api.getInstances(200).then(setInstances).catch(() => {});
  }, []);

  const selProc = processes.find((p) => String(p.id) === processId) ?? null;
  const needsInstance = selProc?.source === 'instance';

  function payload(): RecurringOrderInput {
    return {
      name: name.trim(),
      process_id: processId ? Number(processId) : null,
      article_id: !needsInstance && articleId ? Number(articleId) : null,
      quantity: !needsInstance ? Math.max(1, Math.trunc(Number(quantity) || 1)) : null,
      subject_instance_id: needsInstance && instanceId ? Number(instanceId) : null,
      interval_days: mode === 'abo' ? Math.max(1, Math.trunc(Number(intervalDays) || 1)) : null,
      lead_time_days: mode === 'compliance' ? Math.max(0, Math.trunc(Number(leadDays) || 0)) : 0,
      validity_days: mode === 'compliance' ? Math.max(1, Math.trunc(Number(validityDays) || 1)) : null,
      valid_until: mode === 'compliance' && validUntil ? validUntil : null,
      next_due_at: mode === 'abo' && nextDue ? nextDue : null,
    };
  }

  async function save() {
    if (!name.trim()) { setError('Bitte einen Namen angeben'); return; }
    if (mode === 'compliance' && !validUntil) { setError('Bitte ein Ablaufdatum angeben'); return; }
    if (mode === 'abo' && !nextDue) { setError('Bitte einen ersten Termin angeben'); return; }
    setSaving(true); setError(null);
    try {
      const r = isCreate
        ? await api.createRecurringOrder(payload())
        : await api.updateRecurringOrder(record!.object_id!, payload());
      onSaved(r);
    } catch (e) { setError(e instanceof Error ? e.message : 'Fehler beim Speichern'); }
    finally { setSaving(false); }
  }

  async function patch(data: Parameters<typeof api.updateRecurringOrder>[1]) {
    if (!record?.object_id) return;
    try { onSaved(await api.updateRecurringOrder(record.object_id, data)); }
    catch (e) { setError(e instanceof Error ? e.message : 'Fehler'); }
  }

  async function run() {
    try { await api.runRecurringOrders(); if (record?.object_id) onSaved(await api.getRecurringOrder(record.object_id)); }
    catch (e) { setError(e instanceof Error ? e.message : 'Fehler'); }
  }

  const cfg = STATUS_CFG[status] ?? STATUS_CFG.draft;
  const procOpts = [{ value: '', label: '— Prozess wählen —' },
    ...processes.map((p) => ({ value: String(p.id), label: `${p.name} (${p.source})` }))];
  const artOpts = [{ value: '', label: '— Artikel wählen —' },
    ...articles.map((a) => ({ value: String(a.id), label: `${fmtObjId(a.object_id)} · ${a.name}` }))];
  const instOpts = [{ value: '', label: '— Instanz wählen —' },
    ...instances.filter((i) => i.object_id != null).map((i) => ({ value: String(i.object_id), label: `${fmtObjId(i.object_id)} · ${i.article_name ?? ''}` }))];

  return (
    <div style={{ flex: 1, overflowY: 'auto', padding: 20 }}>
      <button onClick={onBack} style={backBtn}><ArrowLeft size={14} /> Zurück</button>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, margin: '8px 0 4px' }}>
        <div style={{ width: 36, height: 36, borderRadius: 8, background: '#eff6ff', color: '#2563eb', display: 'flex', alignItems: 'center', justifyContent: 'center' }}><Repeat size={18} /></div>
        <div style={{ flex: 1 }}>
          <h2 style={{ fontSize: 16, fontWeight: 700, color: '#0f172a' }}>{isCreate ? 'Neuer wiederkehrender Vorgang' : record!.name}</h2>
          {!isCreate && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 2 }}>
              <span style={{ fontSize: 12, fontFamily: 'monospace', fontWeight: 600, color: '#475569' }}>{fmtObjId(record!.object_id)}</span>
              <span style={{ fontSize: 10, fontWeight: 700, padding: '1px 8px', borderRadius: 999, background: cfg.bg, color: cfg.color }}>{cfg.label}</span>
              {record!.due_now && <span style={{ fontSize: 10, fontWeight: 700, padding: '1px 8px', borderRadius: 999, background: '#fef2f2', color: '#dc2626' }}>fällig</span>}
            </div>
          )}
        </div>
      </div>

      {!isCreate && (
        <div style={{ display: 'flex', gap: 8, margin: '12px 0' }}>
          {status === 'draft' && <button onClick={() => patch({ status: 'released' })} style={action('#16a34a')}><CheckCircle2 size={14} /> Aktivieren</button>}
          {status === 'released' && <button onClick={() => patch({ status: 'inactive' })} style={action('#dc2626')}><Ban size={14} /> Pausieren</button>}
          {status === 'inactive' && <button onClick={() => patch({ status: 'released' })} style={action('#2563eb')}><RotateCcw size={14} /> Reaktivieren</button>}
          <button onClick={run} style={action('#7c3aed')} title="Fällige Vorgänge jetzt zu Aufträgen machen"><Play size={14} /> Jetzt prüfen</button>
        </div>
      )}

      <div style={{ display: 'flex', flexDirection: 'column', gap: 14, marginTop: 8, maxWidth: 560 }}>
        <TextField label="Name" value={name} onChange={setName} required placeholder="z. B. ISO-9001-Zertifizierung, Jahreswartung Presse A" />
        <SearchSelect label="Prozess" value={processId} onChange={setProcessId} required options={procOpts}
          placeholder="welcher Prozess wird ausgeführt?" />
        {selProc && (
          needsInstance ? (
            <SearchSelect label="Instanz (Subjekt)" value={instanceId} onChange={setInstanceId} required options={instOpts} />
          ) : (
            <div style={{ display: 'flex', gap: 8 }}>
              <div style={{ flex: 1 }}><SearchSelect label="Artikel" value={articleId} onChange={setArticleId} required options={artOpts} /></div>
              <div style={{ width: 110 }}><TextField label="Menge" value={quantity} onChange={setQuantity} /></div>
            </div>
          )
        )}

        <Segmented label="Takt" value={mode} onChange={(v) => setMode(v as 'compliance' | 'abo')} options={[
          { value: 'compliance', label: 'Compliance (Ablauf)' }, { value: 'abo', label: 'Abo (Intervall)' },
        ]} />
        {mode === 'compliance' ? (
          <>
            <TextField label="Gültig bis (Ablaufdatum)" value={validUntil} onChange={setValidUntil} placeholder="JJJJ-MM-TT" hint="z. B. ISO-Zertifikat-Ablauf" />
            <div style={{ display: 'flex', gap: 8 }}>
              <div style={{ flex: 1 }}><TextField label="Vorlaufzeit (Tage)" value={leadDays} onChange={setLeadDays} hint="so früh vor Ablauf starten" /></div>
              <div style={{ flex: 1 }}><TextField label="Gültigkeitsdauer (Tage)" value={validityDays} onChange={setValidityDays} hint="z. B. 365 (1 Jahr)" /></div>
            </div>
          </>
        ) : (
          <>
            <TextField label="Erster Termin" value={nextDue} onChange={setNextDue} placeholder="JJJJ-MM-TT" />
            <TextField label="Intervall (Tage)" value={intervalDays} onChange={setIntervalDays} hint="z. B. 30 (monatlich)" />
          </>
        )}
        {error && <ErrorText msg={error} />}
        <button onClick={save} disabled={saving} style={primary}>{saving ? 'Speichern…' : (isCreate ? 'Anlegen' : 'Speichern')}</button>
      </div>
    </div>
  );
}

const backBtn: React.CSSProperties = {
  display: 'inline-flex', alignItems: 'center', gap: 5, border: 'none', background: 'none',
  color: '#2563eb', cursor: 'pointer', fontSize: 13, fontWeight: 600, padding: 0,
};
const primary: React.CSSProperties = {
  padding: '8px 16px', borderRadius: 8, border: 'none', background: '#2563eb', color: '#fff', fontSize: 13, fontWeight: 600, cursor: 'pointer', alignSelf: 'flex-start',
};
function action(color: string): React.CSSProperties {
  return { display: 'inline-flex', alignItems: 'center', gap: 6, padding: '7px 14px', borderRadius: 8, border: `1px solid ${color}`, background: '#fff', color, fontSize: 13, fontWeight: 600, cursor: 'pointer' };
}
