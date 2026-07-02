'use client';

import { useEffect, useMemo, useState } from 'react';
import { Plus, Trash2, Link2, User as UserIcon, Info, Eye, Check, GripVertical, ChevronDown, X, ArrowLeft, Lock, Wrench, PackageMinus } from 'lucide-react';
import { api } from '@/lib/api';
import type { Article, ArticleProcessStep, CaptureField, Instance, LocationType, ProcessStepMode, ResourceMode, StepType, StorageLocation, UserProfile } from '@/types';
import { userDisplayName } from '@/lib/utils';
import { PROCESS_MODE_LABEL } from '@/lib/purchase-order';
import { unitLabel } from '@/lib/article';
import { STEP_META, locationTypeLabel, instanceLabel, isStockOperation } from '@/lib/process';
import { SUPPLIER_FIELD_CATALOG, MANDATORY_FIELD_KEYS, normalizeSharedFields, fieldLabel } from '@/lib/article-fields';
import { ErrorText, Label, Segmented, SearchSelect, TextField } from '@/components/erp/fields';
import { fmtObjId } from '@/components/erp/user-detail';

type WField = { label: string; type: 'measure' | 'bool' | 'text'; target: string; tolerance: string; unit: string };
// EIN Ressource-Schritt; pro Zeile ein Modus (Verbrauch | Betriebsmittel).
type ResLine = { article_id: string; quantity: string; mode: ResourceMode };

// Zulässige Schritttypen je Kontext (Spiegel von Backend domain.event_types):
// Artikel = Herstellung (kein Verkauf); Auftrag = Operation am Bestand mit **allen**
// Typen – auch purchase (auswärtige Vergabe, z. B. Wartung) und resource (Verbrauchs-/
// Hilfsmaterial, Ersatzteile). So sind die Prozessschritte immer kompatibel.
const ARTICLE_STEP_ORDER: StepType[] = ['purchase', 'resource', 'inspection', 'movement'];
const ORDER_STEP_ORDER: StepType[] = ['purchase', 'resource', 'inspection', 'movement', 'scrap', 'sale'];

// Gültiger Webshop-Link: http(s) mit einem Host inkl. Punkt (z. B. shop.example.com).
function isValidWebshopUrl(v: string): boolean {
  try {
    const u = new URL(v.trim());
    return (u.protocol === 'http:' || u.protocol === 'https:') && u.hostname.includes('.');
  } catch {
    return false;
  }
}

export function ProcessSteps({ owner, ownerObjectId, suppliers, readOnly = false, onStepsCount, selfArticleObjectId = null }: {
  owner: 'articles' | 'orders';          // Prozess am Artikel (Entstehung) oder am Auftrag (CUSTOM)
  ownerObjectId: number | null;          // Objektnummer des Trägers
  suppliers: UserProfile[];
  readOnly?: boolean;
  onStepsCount?: (n: number, isStockOp: boolean) => void;
  selfArticleObjectId?: number | null;   // Artikel des Trägers (Ressource-Selbst-Ausschluss)
}) {
  const [steps, setSteps] = useState<ArticleProcessStep[]>([]);
  const [loading, setLoading] = useState(false);
  const [adding, setAdding] = useState<'choose' | StepType | null>(null);
  const [mode, setMode] = useState<ProcessStepMode>('supplier');
  const [supplierId, setSupplierId] = useState('');
  const [url, setUrl] = useState('');
  const [shared, setShared] = useState<string[]>(MANDATORY_FIELD_KEYS);
  const [samplePercent, setSamplePercent] = useState('100');
  const [wfields, setWfields] = useState<WField[]>([]);
  const [targetSel, setTargetSel] = useState('');   // kombiniertes Ziel "type:objid" ('' = frei)
  const [storageLocs, setStorageLocs] = useState<StorageLocation[]>([]);
  const [allUsers, setAllUsers] = useState<UserProfile[]>([]);
  const [allInstances, setAllInstances] = useState<Instance[]>([]);
  const [articles, setArticles] = useState<Article[]>([]);
  const [resLines, setResLines] = useState<ResLine[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [editId, setEditId] = useState<number | null>(null);
  const [editShared, setEditShared] = useState<string[]>(MANDATORY_FIELD_KEYS);
  const [drag, setDrag] = useState<number | null>(null);
  const [over, setOver] = useState<number | null>(null);

  useEffect(() => {
    if (ownerObjectId == null) return;
    setLoading(true);
    api.getSteps(owner, ownerObjectId!).then(setSteps).catch(() => {}).finally(() => setLoading(false));
    // Lagerplätze für den (editierbaren) Wareneingang-Zielselektor der Pflicht-Bewegung
    api.getStorageLocations().then(setStorageLocs).catch(() => {});
  }, [owner, ownerObjectId]);

  // Schrittanzahl + abgeleitete Auftragsart (Bestands-Operation vs. Herstellung) an das
  // Elternfenster melden – Letzteres über die deklarierte Subjekt-Rolle der Schritte
  // (Spiegel der Backend-Registry), damit ein Beschaffungs-/Ressourcen-Schritt korrekt
  // als «Herstellung» und nicht als «Bestands-Operation» erkannt wird.
  useEffect(() => {
    onStepsCount?.(steps.length, isStockOperation(steps.map((s) => s.step_type as StepType)));
  }, [steps, onStepsCount]);

  // Herkunfts-Artikel laden, um beim Beschaffungsschritt nur die **tatsächlich
  // gepflegten** optionalen Stammdatenfelder zur Freigabe anzubieten.
  const [selfArticle, setSelfArticle] = useState<Article | null>(null);
  useEffect(() => {
    if (selfArticleObjectId == null) { setSelfArticle(null); return; }
    api.getArticle(selfArticleObjectId).then(setSelfArticle).catch(() => {});
  }, [selfArticleObjectId]);
  const optionalShareKeys = useMemo<string[]>(() => {
    const out: string[] = [];
    if (selfArticle?.supplier_article_number) out.push('supplier_article_number');
    return out;
  }, [selfArticle]);

  // Bewegung braucht Lagerplätze/Personen/Instanzen als Zielauswahl; Ressource die Artikel.
  // (Beschaffung: keine Lieferadresse mehr am Schritt – kommt aus der Systemkonfiguration.)
  useEffect(() => {
    if (adding === 'resource') { api.getArticles().then(setArticles).catch(() => {}); return; }
    if (adding !== 'movement') return;
    api.getStorageLocations().then(setStorageLocs).catch(() => {});
    api.getUsers().then(setAllUsers).catch(() => {});
    api.getInstances().then(setAllInstances).catch(() => {});
  }, [adding]);

  if (ownerObjectId == null) {
    return (
      <div style={noticeStyle}>
        <Info size={15} style={{ flexShrink: 0, marginTop: 1 }} />
        <span>Prozess zuerst wählen – danach lassen sich Schritte hinterlegen.</span>
      </div>
    );
  }

  function resetForm() {
    setAdding(null); setMode('supplier'); setSupplierId(''); setUrl('');
    setShared(MANDATORY_FIELD_KEYS); setSamplePercent('100'); setWfields([]);
    setTargetSel(''); setResLines([]); setError(null);
  }

  // Nach Strukturänderungen die kanonische Liste neu laden (inkl. automatischer
  // Pflicht-Bewegungen + serverseitiger Positionen).
  async function reload() {
    try { setSteps(await api.getSteps(owner, ownerObjectId!)); } catch { /* ignore */ }
  }

  // Rolle einer Pflicht-Bewegung: Versand zum Kunden (mode=customer), Versand zum
  // Lieferanten (user-Ziel) oder Wareneingang.
  function lockedRole(s: ArticleProcessStep): 'versand' | 'wareneingang' | 'versandkunde' {
    if ((s.mode as string) === 'customer') return 'versandkunde';   // Versand zum Kunden (getaggt)
    return s.target_location_type === 'user' ? 'versand' : 'wareneingang';
  }

  // Wareneingang-Ziel der Pflicht-Bewegung setzen (Lagerplatz oder offen).
  async function setLockedTarget(stepId: number, value: string) {
    const tgt = value ? value.split(':') : null;
    try {
      const updated = await api.updateStep(owner, ownerObjectId!, stepId, {
        target_location_type: tgt ? (tgt[0] as LocationType) : null,
        target_location_id: tgt ? Number(tgt[1]) : null,
      });
      setSteps((p) => p.map((s) => (s.id === stepId ? updated : s)));
    } catch { /* ignore */ }
  }

  function buildCaptureFields(): CaptureField[] {
    return wfields
      .filter((f) => f.label.trim())
      .map((f) => ({
        key: '', label: f.label.trim(), type: f.type,
        target: f.type === 'measure' && f.target.trim() !== '' ? Number(f.target) : null,
        tolerance: f.type === 'measure' && f.tolerance.trim() !== '' ? Number(f.tolerance) : null,
        unit: f.unit.trim() || null,
      }));
  }

  async function addStep(type: StepType) {
    setError(null);
    if (type === 'purchase') {
      if (mode === 'supplier' && !supplierId) { setError('Bitte einen Lieferanten wählen'); return; }
      if (mode === 'webshop') {
        if (!url.trim()) { setError('Bitte einen Webshop-Link angeben'); return; }
        if (!isValidWebshopUrl(url)) { setError('Bitte einen gültigen Link angeben (z. B. https://shop.example.com/…)'); return; }
      }
    }
    if (type === 'inspection') {
      const p = Number(samplePercent);
      if (!Number.isFinite(p) || p < 1 || p > 100) { setError('Prüfumfang muss 1–100 % sein'); return; }
    }
    let resourcePayload: { article_id: number; quantity: number; mode: ResourceMode }[] | null = null;
    if (type === 'resource') {
      resourcePayload = resLines
        .filter((l) => l.article_id)
        .map((l) => ({ article_id: Number(l.article_id), quantity: Math.max(1, Math.trunc(Number(l.quantity) || 1)), mode: l.mode }));
      if (resourcePayload.length === 0) { setError('Bitte mindestens eine Ressource hinzufügen'); return; }
    }
    const tgt = type === 'movement' && targetSel ? targetSel.split(':') : null;
    setSaving(true);
    try {
      await api.createStep(owner, ownerObjectId!, {
        step_type: type,
        mode: type === 'purchase' ? mode : undefined,
        supplier_id: type === 'purchase' && mode === 'supplier' ? Number(supplierId) : null,
        webshop_url: type === 'purchase' && mode === 'webshop' ? url.trim() : null,
        shared_fields: type === 'purchase' ? shared : null,
        sample_percent: type === 'inspection' ? Math.trunc(Number(samplePercent)) : null,
        capture_fields: type === 'inspection' ? buildCaptureFields() : null,
        target_location_type: tgt ? (tgt[0] as LocationType) : null,
        target_location_id: tgt ? Number(tgt[1]) : null,
        resource_lines: resourcePayload,
      });
      // Server fügt evtl. Pflicht-Bewegungen hinzu → kanonische Liste neu laden.
      await reload();
      resetForm();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Fehler beim Speichern');
    } finally {
      setSaving(false);
    }
  }

  async function removeStep(stepId: number) {
    try {
      await api.deleteStep(owner, ownerObjectId!, stepId);
      // Entfernt eine Beschaffung evtl. zugehörige Pflicht-Bewegungen → neu laden.
      await reload();
    } catch { /* ignore */ }
  }

  async function saveShared(stepId: number) {
    try {
      const updated = await api.updateStep(owner, ownerObjectId!, stepId, { shared_fields: editShared });
      setSteps((p) => p.map((s) => (s.id === stepId ? updated : s)));
      setEditId(null);
    } catch { /* ignore */ }
  }

  async function persistOrder(orderedFull: ArticleProcessStep[]) {
    setSteps(orderedFull);  // optimistisch
    // Nur die frei sortierbaren (nicht-Pflicht) Schritte werden gesendet; der
    // Server fügt die Pflicht-Bewegungen automatisch wieder an der richtigen Stelle ein.
    const ids = orderedFull.filter((s) => !s.locked).map((s) => s.id);
    try { setSteps(await api.reorderSteps(owner, ownerObjectId!, ids)); }
    catch { reload(); }
  }

  function onDrop(targetIndex: number) {
    if (drag == null || drag === targetIndex) { setDrag(null); setOver(null); return; }
    const next = [...steps];
    const [moved] = next.splice(drag, 1);
    next.splice(targetIndex, 0, moved);
    persistOrder(next);
    setDrag(null); setOver(null);
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
      {loading && <div style={{ fontSize: 13, color: '#94a3b8' }}>Laden…</div>}

      {/* Start-Knoten (BPMN) */}
      {steps.length > 0 && <FlowNode label="Start" tone="start" />}

      {steps.map((s, i) => {
        const meta = STEP_META[s.step_type as StepType] ?? STEP_META.purchase;
        const Icon = meta.icon;
        const isLocked = s.locked;
        const canDrag = !readOnly && !isLocked;
        const isOver = over === i && drag !== null && drag !== i;
        return (
          <div key={s.id}>
            <Connector />
            <div
              draggable={canDrag}
              onDragStart={() => { if (canDrag) setDrag(i); }}
              onDragEnd={() => { setDrag(null); setOver(null); }}
              onDragOver={(e) => { if (!readOnly && drag !== null) { e.preventDefault(); setOver(i); } }}
              onDrop={(e) => { e.preventDefault(); onDrop(i); }}
              style={{
                ...cardStyle, flexDirection: 'column', alignItems: 'stretch', gap: 10,
                opacity: drag === i ? 0.4 : 1,
                background: isLocked ? '#f8fafc' : '#fff',
                borderColor: isOver ? '#2563eb' : '#E2E8F0',
                boxShadow: isOver ? '0 0 0 2px #dbeafe' : 'none',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                {!readOnly && (isLocked
                  ? <Lock size={14} style={{ color: '#cbd5e1', flexShrink: 0 }} />
                  : <GripVertical size={16} style={{ color: '#cbd5e1', cursor: 'grab', flexShrink: 0 }} />)}
                <div style={{ width: 32, height: 32, borderRadius: 8, flexShrink: 0, background: isLocked ? '#f1f5f9' : '#eff6ff', color: isLocked ? '#64748b' : '#2563eb', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  <Icon size={16} />
                </div>
                <div style={{ minWidth: 0, flex: 1 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <span style={{ fontSize: 13, fontWeight: 700, color: '#0F172A' }}>{i + 1}. {meta.label}</span>
                    {isLocked && <span style={{ fontSize: 10, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.04em', color: '#64748b', background: '#e2e8f0', padding: '1px 6px', borderRadius: 999 }}>Pflicht</span>}
                  </div>
                  <div style={{ marginTop: 3, fontSize: 12, color: '#64748b' }}>
                    {isLocked && (lockedRole(s) === 'versand'
                      ? <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}><UserIcon size={12} /> Versand zum Lieferanten{s.target_location_id ? ` · ${fmtObjId(s.target_location_id)}` : ''}</span>
                      : lockedRole(s) === 'versandkunde'
                        ? <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}><UserIcon size={12} /> Versand zum Kunden · Ziel beim Versand</span>
                        : (s.target_location_id
                          ? `Wareneingang → Lagerplatz ${fmtObjId(s.target_location_id)}`
                          : 'Wareneingang · frei beim Einlagern'))}
                    {!isLocked && s.step_type === 'purchase' && (
                      s.mode === 'supplier'
                        ? <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}><UserIcon size={12} /> {PROCESS_MODE_LABEL.supplier}: {s.supplier_name ?? `#${s.supplier_id}`}</span>
                        : <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}><Link2 size={12} /> {PROCESS_MODE_LABEL.webshop}</span>
                    )}
                    {s.step_type === 'inspection' && `Stichprobe ${s.sample_percent ?? 100}%${(s.capture_fields?.length ?? 0) > 0 ? ` · ${s.capture_fields!.length} Erfassungsfeld${s.capture_fields!.length === 1 ? '' : 'er'}` : ''}`}
                    {!isLocked && s.step_type === 'movement' && (s.target_location_id
                      ? `Ziel: ${locationTypeLabel(s.target_location_type)} · ${fmtObjId(s.target_location_id)}`
                      : 'Standort nicht definiert – Lagerist wählt beim Einlagern')}
                    {s.step_type === 'resource' && `${s.resource_lines?.length ?? 0} Position${(s.resource_lines?.length ?? 0) === 1 ? '' : 'en'}`}
                  </div>
                </div>
                {!readOnly && !isLocked && (
                  <button onClick={() => removeStep(s.id)} title="Entfernen" style={{ border: 'none', background: 'none', color: '#94a3b8', cursor: 'pointer', padding: 4, flexShrink: 0 }}><Trash2 size={15} /></button>
                )}
              </div>

              {/* Pflicht-Wareneingang: Ziel definierbar wie bei regulärer Bewegung */}
              {isLocked && !readOnly && lockedRole(s) === 'wareneingang' && (
                <div style={{ borderTop: '1px solid #f1f5f9', paddingTop: 8 }}>
                  <Label>Ziel-Lagerplatz (optional)</Label>
                  <SearchSelect
                    value={s.target_location_id ? `lagerplatz:${s.target_location_id}` : ''}
                    onChange={(v) => setLockedTarget(s.id, v)}
                    placeholder="frei – Lagerist wählt beim Einlagern"
                    options={[
                      { value: '', label: 'frei – Lagerist wählt beim Einlagern' },
                      ...storageLocs.filter((l) => l.status === 'released' && l.object_id != null).map((l) => ({
                        value: `lagerplatz:${l.object_id}`, label: `Lagerplatz ${fmtObjId(l.object_id)}` })),
                    ]} />
                  <div style={{ marginTop: 4, fontSize: 11, color: '#94a3b8' }}>
                    Vorgabe → beim Scannen erzwungen. Leer → frei einlagerbar (per Scan erfasst).
                  </div>
                </div>
              )}

              {/* Beschaffung: sichtbare Stammdaten */}
              {s.step_type === 'purchase' && (
                <div style={{ borderTop: '1px solid #f1f5f9', paddingTop: 8 }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
                    <span style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.04em', color: '#94a3b8' }}>
                      <Eye size={12} /> Für Lieferant sichtbar
                    </span>
                    {!readOnly && (editId === s.id ? (
                      <button onClick={() => saveShared(s.id)} style={miniPrimary}><Check size={12} /> Speichern</button>
                    ) : (
                      <button onClick={() => { setEditId(s.id); setEditShared(normalizeSharedFields(s.shared_fields)); }} style={miniGhost}>Ändern</button>
                    ))}
                  </div>
                  {!readOnly && editId === s.id ? (
                    <FieldChips value={editShared} onChange={setEditShared} optionalAvailable={optionalShareKeys} />
                  ) : (
                    <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap' }}>
                      {normalizeSharedFields(s.shared_fields).map((k) => <Chip key={k} label={fieldLabel(k)} on />)}
                    </div>
                  )}
                </div>
              )}

              {/* Datenerfassung: Maske-Übersicht */}
              {s.step_type === 'inspection' && (s.capture_fields?.length ?? 0) > 0 && (
                <div style={{ borderTop: '1px solid #f1f5f9', paddingTop: 8, display: 'flex', flexDirection: 'column', gap: 4 }}>
                  {s.capture_fields!.map((f, idx) => (
                    <div key={idx} style={{ fontSize: 12, color: '#475569' }}>
                      • {f.label} <span style={{ color: '#94a3b8' }}>
                        {f.type === 'measure' ? `(Soll ${f.target ?? '—'}${f.tolerance != null ? ` ± ${f.tolerance}` : ''}${f.unit ? ` ${f.unit}` : ''})` : f.type === 'bool' ? '(Gut/Schlecht)' : '(Text)'}
                      </span>
                    </div>
                  ))}
                </div>
              )}

              {/* Ressource: Zeilen (Artikel + Menge + Modus pro Zeile) */}
              {s.step_type === 'resource' && (s.resource_lines?.length ?? 0) > 0 && (
                <div style={{ borderTop: '1px solid #f1f5f9', paddingTop: 8, display: 'flex', flexDirection: 'column', gap: 4 }}>
                  {s.resource_lines!.map((l, idx) => (
                    <div key={idx} style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, color: '#475569' }}>
                      {l.mode === 'tool' ? <Wrench size={12} style={{ color: '#7c3aed', flexShrink: 0 }} /> : <PackageMinus size={12} style={{ color: '#0f766e', flexShrink: 0 }} />}
                      <span style={{ flex: 1, minWidth: 0 }}>{l.article_object_id ? `${fmtObjId(l.article_object_id)} · ` : ''}{l.article_name ?? `#${l.article_id}`}</span>
                      <span style={{ color: '#94a3b8' }}>{l.quantity}{l.unit ? ` ${unitLabel(l.unit)}` : ''}/Stk</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        );
      })}

      {steps.length > 0 && <Connector />}
      {steps.length > 0 && !adding && <FlowNode label="Ende" tone="end" />}

      {/* Hinzufügen */}
      {!readOnly && (
        <div style={{ marginTop: 12 }}>
          {adding == null ? (
            <button onClick={() => setAdding('choose')} style={addBtnStyle}>
              <Plus size={15} /> Prozessschritt hinzufügen
            </button>
          ) : adding === 'choose' ? (
            <div style={{ ...cardStyle, flexDirection: 'column', alignItems: 'stretch', gap: 10 }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <span style={{ fontSize: 13, fontWeight: 700, color: '#0F172A' }}>Welcher Schritt?</span>
                <button onClick={resetForm} style={{ border: 'none', background: 'none', color: '#94a3b8', cursor: 'pointer', padding: 2 }}><X size={16} /></button>
              </div>
              {(owner === 'articles' ? ARTICLE_STEP_ORDER : ORDER_STEP_ORDER).map((t) => {
                const m = STEP_META[t]; const Icon = m.icon;
                return (
                  <button key={t} onClick={() => setAdding(t)} style={chooserBtn}>
                    <div style={{ width: 32, height: 32, borderRadius: 8, background: '#eff6ff', color: '#2563eb', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}><Icon size={16} /></div>
                    <div style={{ textAlign: 'left' }}>
                      <div style={{ fontSize: 13, fontWeight: 600, color: '#0F172A' }}>{m.label}</div>
                      <div style={{ fontSize: 11, color: '#94a3b8' }}>{STEP_HINT[t]}</div>
                    </div>
                  </button>
                );
              })}
            </div>
          ) : (
            <div style={{ ...cardStyle, flexDirection: 'column', alignItems: 'stretch', gap: 14 }}>
              <button onClick={() => setAdding('choose')} style={{ display: 'flex', alignItems: 'center', gap: 5, border: 'none', background: 'none', color: '#2563eb', cursor: 'pointer', fontSize: 12, fontWeight: 600, padding: 0, alignSelf: 'flex-start' }}>
                <ArrowLeft size={13} /> {STEP_META[adding].label}
              </button>

              {adding === 'purchase' && (
                <>
                  <Segmented label="Bezugsquelle" value={mode} onChange={(v) => setMode(v as ProcessStepMode)}
                    options={[{ value: 'supplier', label: 'Lieferant' }, { value: 'webshop', label: 'Webshop-Link' }]} required />
                  {mode === 'supplier' ? (
                    suppliers.length > 0 ? (
                      <SearchSelect label="Lieferant" value={supplierId} onChange={setSupplierId} required
                        options={[{ value: '', label: '— wählen —' }, ...suppliers.map((u) => ({ value: String(u.id), label: `${fmtObjId(u.object_id)} · ${userDisplayName(u)}` }))]} />
                    ) : (
                      <div style={noticeStyle}><Info size={14} style={{ flexShrink: 0, marginTop: 1 }} /><span>Keine Lieferanten vorhanden. Bitte zuerst anlegen oder Webshop-Link nutzen.</span></div>
                    )
                  ) : (
                    <TextField label="Webshop-Link" value={url} onChange={setUrl} required placeholder="https://shop.example.com/artikel" />
                  )}
                  <div style={{ display: 'flex', alignItems: 'flex-start', gap: 8, padding: '10px 12px', background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: 8, fontSize: 12, color: '#64748b' }}>
                    <Info size={14} style={{ flexShrink: 0, marginTop: 1 }} />
                    <span>Lieferadresse aus der Systemkonfiguration. Der tatsächliche Lagerort wird beim Wareneingang erfasst.</span>
                  </div>
                  <div><Label>Für den Lieferanten sichtbare Spezifikation</Label><FieldChips value={shared} onChange={setShared} optionalAvailable={optionalShareKeys} /></div>
                </>
              )}

              {adding === 'inspection' && (
                <>
                  <TextField label="Prüfumfang (% der Menge)" value={samplePercent} onChange={setSamplePercent}
                    required placeholder="z. B. 10" hint="Stichprobe: wie viel Prozent geprüft werden muss (1–100)" />
                  <CaptureFieldsEditor fields={wfields} onChange={setWfields} />
                </>
              )}

              {adding === 'movement' && (
                <>
                  <SearchSelect label="Zielstandort (optional)" value={targetSel} onChange={setTargetSel}
                    placeholder="Nicht definiert – Lagerist wählt beim Einlagern"
                    options={[
                      { value: '', label: 'Nicht definiert – Lagerist wählt beim Einlagern' },
                      ...storageLocs.filter((l) => l.status === 'released' && l.object_id != null).map((l) => ({
                        value: `lagerplatz:${l.object_id}`, label: `Lagerplatz ${fmtObjId(l.object_id)}` })),
                      ...allUsers.filter((u) => u.object_id != null).map((u) => ({
                        value: `user:${u.object_id}`, label: `Person ${userDisplayName(u)} · ${fmtObjId(u.object_id)}` })),
                      ...allInstances.filter((i) => i.object_id != null).map((i) => ({
                        value: `instance:${i.object_id}`, label: `${instanceLabel(i.kind)} ${fmtObjId(i.object_id)}` })),
                    ]} />
                </>
              )}

              {adding === 'resource' && (
                <ResourceLinesEditor lines={resLines} onChange={setResLines}
                  articles={articles.filter((a) => a.status === 'released' && a.object_id !== selfArticleObjectId)} />
              )}

              {adding === 'sale' && (
                <div style={{ display: 'flex', alignItems: 'flex-start', gap: 8, padding: '10px 12px', background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: 8, fontSize: 12, color: '#64748b' }}>
                  <Info size={14} style={{ flexShrink: 0, marginTop: 1 }} />
                  <span>Kaufmännischer Verkauf (Spiegel der Beschaffung): Kunde, Betrag, Rechnung
                    und Zahlung werden beim Auftrag erfasst. Der Versand läuft über eine Bewegung
                    (Ziel = Kunde, mit Sendungsverfolgung).</span>
                </div>
              )}

              {error && <ErrorText msg={error} />}
              <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
                <button onClick={resetForm} style={secondaryBtn}>Abbrechen</button>
                <button onClick={() => addStep(adding)} disabled={saving} style={primaryBtn}>{saving ? 'Speichern…' : 'Hinzufügen'}</button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

const STEP_HINT: Record<StepType, string> = {
  purchase: 'Bestellung bei Lieferant oder Webshop',
  inspection: 'Stichprobe prüfen & Werte erfassen',
  movement: 'Instanzen an ihren Standort bringen',
  resource: 'Material verbrauchen oder Betriebsmittel nutzen',
  scrap: 'Defekte/nicht benötigte Instanzen ausschleusen',
  sale: 'Verkauf bzw. Gutschrift/Erstattung (bei verkaufter Ware) – Bestätigung → Rechnung → Zahlung',
};

// ─── Ressourcen-Zeilen (mini-BOM): Artikel + Menge + Modus-Toggle je Zeile ────
function ResourceLinesEditor({ lines, onChange, articles }: {
  lines: ResLine[]; onChange: (l: ResLine[]) => void; articles: Article[];
}) {
  function add() { onChange([...lines, { article_id: '', quantity: '1', mode: 'consume' }]); }
  function upd(i: number, patch: Partial<ResLine>) { onChange(lines.map((l, idx) => (idx === i ? { ...l, ...patch } : l))); }
  function del(i: number) { onChange(lines.filter((_, idx) => idx !== i)); }
  const options = [{ value: '', label: '— Artikel wählen —' },
    ...articles.map((a) => ({ value: String(a.id), label: `${fmtObjId(a.object_id)} · ${a.name}` }))];
  return (
    <div>
      <Label>Ressourcen</Label>
      {articles.length === 0 && (
        <div style={noticeStyle}><Info size={14} style={{ flexShrink: 0, marginTop: 1 }} /><span>Kein freigegebener Artikel referenzierbar.</span></div>
      )}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {lines.map((l, i) => {
          const tool = l.mode === 'tool';
          return (
            <div key={i} style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
              {/* Eleganter Modus-Toggle: ein Klick wechselt Verbrauch ↔ Betriebsmittel */}
              <button type="button" onClick={() => upd(i, { mode: tool ? 'consume' : 'tool' })}
                title={tool ? 'Betriebsmittel (nur genutzt) – klicken für Verbrauch' : 'Verbrauch (Lagerabgang, FIFO) – klicken für Betriebsmittel'}
                style={{ flexShrink: 0, width: 34, height: 34, borderRadius: 8, cursor: 'pointer',
                  border: `1px solid ${tool ? '#ddd6fe' : '#bbf7d0'}`, background: tool ? '#f5f3ff' : '#f0fdf4',
                  color: tool ? '#7c3aed' : '#0f766e', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                {tool ? <Wrench size={15} /> : <PackageMinus size={15} />}
              </button>
              <div style={{ flex: 1 }}>
                <SearchSelect value={l.article_id} onChange={(v) => upd(i, { article_id: v })} options={options} placeholder="Artikel wählen" />
              </div>
              <input value={l.quantity} onChange={(e) => upd(i, { quantity: e.target.value })} inputMode="numeric" placeholder="Menge/Stk"
                className="px-2.5 py-1.5 text-sm rounded-md border bg-white outline-none focus:ring-2 focus:ring-blue-500" style={{ borderColor: '#e2e8f0', width: 92 }} />
              <button onClick={() => del(i)} style={{ border: 'none', background: 'none', color: '#94a3b8', cursor: 'pointer' }}><Trash2 size={15} /></button>
            </div>
          );
        })}
      </div>
      <button onClick={add} style={{ ...addBtnStyle, marginTop: 8, padding: '8px' }}><Plus size={14} /> Ressource hinzufügen</button>
      <div style={{ marginTop: 6, fontSize: 11, color: '#94a3b8', display: 'flex', alignItems: 'center', gap: 12 }}>
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}><PackageMinus size={12} style={{ color: '#0f766e' }} /> Verbrauch (FIFO)</span>
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}><Wrench size={12} style={{ color: '#7c3aed' }} /> Betriebsmittel (genutzt)</span>
      </div>
    </div>
  );
}

// ─── Datenerfassungs-Maske bearbeiten ─────────────────────────────────────────
function CaptureFieldsEditor({ fields, onChange }: { fields: WField[]; onChange: (f: WField[]) => void }) {
  function add() { onChange([...fields, { label: '', type: 'measure', target: '', tolerance: '', unit: '' }]); }
  function upd(i: number, patch: Partial<WField>) { onChange(fields.map((f, idx) => (idx === i ? { ...f, ...patch } : f))); }
  function del(i: number) { onChange(fields.filter((_, idx) => idx !== i)); }
  return (
    <div>
      <Label>Erfassungsfelder (was wird geprüft?)</Label>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {fields.map((f, i) => (
          <div key={i} style={{ border: '1px solid #e2e8f0', borderRadius: 8, padding: '8px 10px', display: 'flex', flexDirection: 'column', gap: 8 }}>
            <div style={{ display: 'flex', gap: 8 }}>
              <input value={f.label} onChange={(e) => upd(i, { label: e.target.value })} placeholder="Bezeichnung (z. B. Länge)"
                className="px-2.5 py-1.5 text-sm rounded-md border bg-white outline-none focus:ring-2 focus:ring-blue-500" style={{ borderColor: '#e2e8f0', flex: 1 }} />
              <select value={f.type} onChange={(e) => upd(i, { type: e.target.value as WField['type'] })}
                className="px-2 py-1.5 text-sm rounded-md border bg-white" style={{ borderColor: '#e2e8f0' }}>
                <option value="measure">Soll-Ist</option>
                <option value="bool">Gut/Schlecht</option>
                <option value="text">Text</option>
              </select>
              <button onClick={() => del(i)} style={{ border: 'none', background: 'none', color: '#94a3b8', cursor: 'pointer' }}><Trash2 size={15} /></button>
            </div>
            {f.type === 'measure' && (
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 8 }}>
                <input value={f.target} onChange={(e) => upd(i, { target: e.target.value })} inputMode="decimal" placeholder="Soll"
                  className="px-2.5 py-1.5 text-sm rounded-md border bg-white" style={{ borderColor: '#e2e8f0' }} />
                <input value={f.tolerance} onChange={(e) => upd(i, { tolerance: e.target.value })} inputMode="decimal" placeholder="± Toleranz"
                  className="px-2.5 py-1.5 text-sm rounded-md border bg-white" style={{ borderColor: '#e2e8f0' }} />
                <input value={f.unit} onChange={(e) => upd(i, { unit: e.target.value })} placeholder="Einheit"
                  className="px-2.5 py-1.5 text-sm rounded-md border bg-white" style={{ borderColor: '#e2e8f0' }} />
              </div>
            )}
          </div>
        ))}
      </div>
      <button onClick={add} style={{ ...addBtnStyle, marginTop: 8, padding: '8px' }}><Plus size={14} /> Erfassungsfeld hinzufügen</button>
    </div>
  );
}

// ─── BPMN-Hilfen ──────────────────────────────────────────────────────────────
function Connector() {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', height: 22 }}>
      <div style={{ width: 2, flex: 1, background: '#cbd5e1' }} />
      <ChevronDown size={14} style={{ color: '#cbd5e1', marginTop: -4 }} />
    </div>
  );
}

function FlowNode({ label, tone }: { label: string; tone: 'start' | 'end' }) {
  const color = tone === 'start' ? '#16a34a' : '#64748b';
  return (
    <div style={{ display: 'flex', justifyContent: 'center' }}>
      <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, padding: '4px 14px', borderRadius: 999, border: `1.5px solid ${color}`, color, fontSize: 11, fontWeight: 700, background: '#fff' }}>
        {label}
      </span>
    </div>
  );
}

// ─── Stammdaten-Tags (Beschaffung) ────────────────────────────────────────────
// Nur wählbar, was es wirklich gibt: Pflichtfelder + die optionalen Felder, die der
// Artikel tatsächlich pflegt (``optionalAvailable``).
function FieldChips({ value, onChange, optionalAvailable = [] }: {
  value: string[]; onChange: (v: string[]) => void; optionalAvailable?: string[];
}) {
  const fields = SUPPLIER_FIELD_CATALOG.filter((f) => f.mandatory || optionalAvailable.includes(f.key));
  const hasOptional = fields.some((f) => !f.mandatory);
  function toggle(key: string) {
    const set = new Set(value);
    if (set.has(key)) set.delete(key); else set.add(key);
    onChange(normalizeSharedFields([...set]));
  }
  return (
    <div>
      <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap' }}>
        {fields.map((f) => (
          <Chip key={f.key} label={f.mandatory ? `${f.label} · Pflicht` : f.label}
            on={f.mandatory || value.includes(f.key)} locked={f.mandatory}
            onClick={f.mandatory ? undefined : () => toggle(f.key)} />
        ))}
      </div>
      <div style={{ marginTop: 6, fontSize: 11, color: '#94a3b8' }}>
        Pflicht-Stammdaten sind für den Lieferanten immer sichtbar.
        {!hasOptional && ' Optionale Felder erscheinen hier nur, wenn sie am Artikel gepflegt sind.'}
      </div>
    </div>
  );
}

function Chip({ label, on, locked, onClick }: { label: string; on?: boolean; locked?: boolean; onClick?: () => void }) {
  return (
    <button type="button" onClick={onClick} disabled={!onClick}
      style={{
        padding: '3px 9px', borderRadius: 12, fontSize: 11, fontWeight: 600,
        border: `1px solid ${on ? '#bfdbfe' : '#e2e8f0'}`,
        background: on ? '#eff6ff' : '#fff', color: on ? '#2563eb' : '#94a3b8',
        cursor: onClick ? 'pointer' : 'default', opacity: locked ? 0.85 : 1,
      }}>
      {label}
    </button>
  );
}

const cardStyle: React.CSSProperties = {
  display: 'flex', alignItems: 'center', gap: 12, background: '#fff',
  border: '1px solid #E2E8F0', borderRadius: 10, padding: '12px 14px',
};
const noticeStyle: React.CSSProperties = {
  display: 'flex', alignItems: 'flex-start', gap: 8, padding: '12px 14px',
  background: '#fffbeb', border: '1px solid #fde68a', borderRadius: 10, fontSize: 13, color: '#92400e',
};
const addBtnStyle: React.CSSProperties = {
  display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6, padding: '10px',
  borderRadius: 10, border: '1px dashed #cbd5e1', background: '#fff', color: '#2563eb',
  fontSize: 13, fontWeight: 600, cursor: 'pointer', width: '100%',
};
const chooserBtn: React.CSSProperties = {
  display: 'flex', alignItems: 'center', gap: 12, padding: '10px 12px', width: '100%',
  borderRadius: 10, border: '1px solid #E2E8F0', background: '#fff', cursor: 'pointer',
};
const primaryBtn: React.CSSProperties = {
  padding: '7px 14px', borderRadius: 7, border: 'none', background: '#2563eb',
  color: '#fff', fontSize: 13, fontWeight: 600, cursor: 'pointer',
};
const secondaryBtn: React.CSSProperties = {
  padding: '7px 14px', borderRadius: 7, border: '1px solid #E2E8F0', background: '#fff',
  color: '#374151', fontSize: 13, cursor: 'pointer',
};
const miniPrimary: React.CSSProperties = {
  display: 'flex', alignItems: 'center', gap: 4, padding: '3px 9px', borderRadius: 6,
  border: 'none', background: '#2563eb', color: '#fff', fontSize: 11, fontWeight: 600, cursor: 'pointer',
};
const miniGhost: React.CSSProperties = {
  padding: '3px 9px', borderRadius: 6, border: '1px solid #e2e8f0', background: '#fff',
  color: '#475569', fontSize: 11, fontWeight: 600, cursor: 'pointer',
};
