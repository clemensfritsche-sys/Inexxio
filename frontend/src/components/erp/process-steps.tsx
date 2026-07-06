'use client';

import { useEffect, useMemo, useState } from 'react';
import { Plus, Trash2, Link2, User as UserIcon, Info, Eye, Check, GripVertical, X, ArrowLeft, Lock, Wrench, PackageMinus, Play, Flag, ShoppingCart } from 'lucide-react';
import { api } from '@/lib/api';
import type { Article, ArticleProcessStep, CaptureField, Instance, LocationType, ResourceMode, StepType, StorageLocation, UserProfile } from '@/types';
import { userDisplayName } from '@/lib/utils';
import { unitLabel } from '@/lib/article';
import { STEP_META, locationTypeLabel, instanceLabel, isStockOperation } from '@/lib/process';
import { SUPPLIER_FIELD_CATALOG, MANDATORY_FIELD_KEYS, normalizeSharedFields, fieldLabel } from '@/lib/article-fields';
import { ErrorText, Label, SearchSelect, TextField } from '@/components/erp/fields';
import { fmtObjId } from '@/components/erp/user-detail';

type WField = { label: string; type: 'measure' | 'bool' | 'text'; target: string; tolerance: string; unit: string };
// EIN Ressource-Schritt; pro Zeile ein Modus (Verbrauch | Betriebsmittel).
type ResLine = { article_id: string; quantity: string; mode: ResourceMode };

// Zulässige Schritttypen je Kontext (Spiegel von Backend domain.event_types):
// Artikel = Herstellung (kein Verkauf); Auftrag = Operation am Bestand mit **allen**
// Typen – auch purchase (auswärtige Vergabe, z. B. Wartung) und resource (Verbrauchs-/
// Hilfsmaterial, Ersatzteile). So sind die Prozessschritte immer kompatibel.
const ARTICLE_STEP_ORDER: StepType[] = ['purchase', 'resource', 'inspection', 'movement', 'document'];
const ORDER_STEP_ORDER: StepType[] = ['purchase', 'resource', 'inspection', 'movement', 'scrap', 'sale', 'document'];

export function ProcessSteps({ owner, ownerObjectId, readOnly = false, onStepsCount, selfArticleObjectId = null, procurementReady }: {
  owner: 'articles' | 'orders';          // Prozess am Artikel (Entstehung) oder am Auftrag (CUSTOM)
  ownerObjectId: number | null;          // Objektnummer des Trägers
  suppliers?: UserProfile[];             // (nicht mehr genutzt – Bezugsquelle kommt vom Artikel)
  readOnly?: boolean;
  onStepsCount?: (n: number, isStockOp: boolean) => void;
  selfArticleObjectId?: number | null;   // Artikel des Trägers (Ressource-Selbst-Ausschluss)
  procurementReady?: boolean;            // Artikel-Beschaffungsquelle hinterlegt? (Warnung am purchase-Schritt)
}) {
  const [steps, setSteps] = useState<ArticleProcessStep[]>([]);
  const [loading, setLoading] = useState(false);
  const [adding, setAdding] = useState<'choose' | StepType | null>(null);
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
    setAdding(null);
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
    // Beschaffung: die Bezugsquelle kommt AUSSCHLIESSLICH aus der Artikel-Spezifikation –
    // kein Schritt-Override mehr (nichts hier zu validieren/erfassen).
    if (type === 'inspection') {
      const p = Number(samplePercent);
      if (!Number.isFinite(p) || p < 1 || p > 100) { setError('Prüfumfang muss 1–100 % sein'); return; }
    }
    let resourcePayload: { article_id: number; quantity: number; mode: ResourceMode }[] | null = null;
    if (type === 'resource') {
      // Menge pro Stück Produkt – Bruchmengen erlaubt (0.5 kg Material je Stück), auf 3 NK
      // gerundet; nie ≤ 0 (mind. 0.001). KEIN Math.trunc mehr (hätte 0.5 auf 0→1 verfälscht).
      resourcePayload = resLines
        .filter((l) => l.article_id)
        .map((l) => {
          const q = Math.round((Number(l.quantity) || 1) * 1000) / 1000;
          return { article_id: Number(l.article_id), quantity: q > 0 ? q : 1, mode: l.mode };
        });
      if (resourcePayload.length === 0) { setError('Bitte mindestens eine Ressource hinzufügen'); return; }
    }
    const tgt = type === 'movement' && targetSel ? targetSel.split(':') : null;
    setSaving(true);
    try {
      await api.createStep(owner, ownerObjectId!, {
        step_type: type,
        // Beschaffung: keine Quelle am Schritt – sie kommt aus der Artikel-Spezifikation.
        supplier_id: null,
        webshop_url: null,
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

  // Jeder Artikel kann alle Schritttypen enthalten (universelle Prozessschrittmodule).
  const chooserTypes: StepType[] = owner === 'articles' ? ARTICLE_STEP_ORDER : ORDER_STEP_ORDER;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
      {loading && <div style={{ fontSize: 13, color: 'var(--fg-4)' }}>Laden…</div>}

      {/* Start-Knoten (BPMN) */}
      {steps.length > 0 && <FlowTerm kind="start" />}

      {steps.map((s, i) => {
        const meta = STEP_META[s.step_type as StepType] ?? STEP_META.purchase;
        const Icon = meta.icon;
        const isLocked = s.locked;
        const canDrag = !readOnly && !isLocked;
        const isOver = over === i && drag !== null && drag !== i;
        const kc = kindColor(s.step_type as StepType, isLocked);
        return (
          <div key={s.id} style={{ width: '100%', display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
            <Connector />
            <div
              draggable={canDrag}
              onDragStart={() => { if (canDrag) setDrag(i); }}
              onDragEnd={() => { setDrag(null); setOver(null); }}
              onDragOver={(e) => { if (!readOnly && drag !== null) { e.preventDefault(); setOver(i); } }}
              onDrop={(e) => { e.preventDefault(); onDrop(i); }}
              style={{
                position: 'relative', width: '100%', maxWidth: STEP_MAXW,
                border: `1px solid ${isOver ? 'var(--accent)' : kc.border}`,
                borderRadius: 'var(--r-lg)', background: kc.bg,
                boxShadow: isOver ? '0 0 0 3px var(--accent-soft)' : 'var(--shadow-sm)',
                opacity: drag === i ? 0.4 : 1, transition: 'box-shadow .16s,border-color .16s',
              }}
            >
              {/* Kopf: Symbol-Kachel + Titel (+ Pflicht) + Löschen */}
              <div style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '15px 18px' }}>
                {!readOnly && (isLocked
                  ? <Lock size={14} style={{ color: 'var(--fg-4)', flexShrink: 0 }} />
                  : <GripVertical size={16} style={{ color: 'var(--border-2)', cursor: 'grab', flexShrink: 0 }} />)}
                <div style={{ width: 38, height: 38, borderRadius: 'var(--r-sm)', flexShrink: 0, background: '#fff', color: kc.fg, border: `1px solid ${kc.border}`, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  <Icon size={19} />
                </div>
                <div style={{ minWidth: 0, flex: 1 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <span style={{ font: '800 16px var(--font-display)', letterSpacing: '-.01em', color: 'var(--fg-1)' }}>{meta.label}</span>
                    {isLocked && <span style={pflichtBadge}>Pflicht</span>}
                  </div>
                  <div style={{ marginTop: 3, fontSize: 12, color: 'var(--fg-3)' }}>
                    {isLocked && (lockedRole(s) === 'versand'
                      ? <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}><UserIcon size={12} /> Versand zum Lieferanten{s.target_location_id ? ` · ${fmtObjId(s.target_location_id)}` : ''}</span>
                      : lockedRole(s) === 'versandkunde'
                        ? <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}><UserIcon size={12} /> Versand zum Kunden · Ziel beim Versand</span>
                        : (s.target_location_id
                          ? `Wareneingang → Lagerplatz ${fmtObjId(s.target_location_id)}`
                          : 'Wareneingang · frei beim Einlagern'))}
                    {!isLocked && s.step_type === 'purchase' && (
                      // Die Bezugsquelle kommt immer aus der Produktspezifikation (kein Schritt-
                      // Override). Fehlt sie am Artikel, klarer roter Hinweis (keine Freigabe möglich).
                      owner === 'articles' && procurementReady === false
                        ? <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, color: '#b91c1c', fontWeight: 600 }}><ShoppingCart size={12} /> Bezugsquelle fehlt – bitte in der Spezifikation hinterlegen</span>
                        : <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}><ShoppingCart size={12} /> Bezugsquelle vom Artikel</span>
                    )}
                    {s.step_type === 'inspection' && `Stichprobe ${s.sample_percent ?? 100}%${(s.capture_fields?.length ?? 0) > 0 ? ` · ${s.capture_fields!.length} Erfassungsfeld${s.capture_fields!.length === 1 ? '' : 'er'}` : ''}`}
                    {!isLocked && s.step_type === 'movement' && (s.target_location_id
                      ? `Ziel: ${locationTypeLabel(s.target_location_type)} · ${fmtObjId(s.target_location_id)}`
                      : 'Standort nicht definiert – Lagerist wählt beim Einlagern')}
                    {s.step_type === 'resource' && `${s.resource_lines?.length ?? 0} Position${(s.resource_lines?.length ?? 0) === 1 ? '' : 'en'}`}
                    {s.step_type === 'document' && (
                      <span>Inhalt wird im Auftrag verfasst</span>
                    )}
                  </div>
                </div>
                {!readOnly && !isLocked && (
                  <button onClick={() => removeStep(s.id)} title="Modul löschen" style={delBtn}><Trash2 size={15} /></button>
                )}
              </div>

              {/* Pflicht-Wareneingang: Ziel definierbar wie bei regulärer Bewegung */}
              {isLocked && !readOnly && lockedRole(s) === 'wareneingang' && (
                <div style={cardBody}>
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
                  <div style={{ marginTop: 4, fontSize: 11, color: 'var(--fg-4)' }}>
                    Vorgabe → beim Scannen erzwungen. Leer → frei einlagerbar (per Scan erfasst).
                  </div>
                </div>
              )}

              {/* Beschaffung: sichtbare Stammdaten */}
              {s.step_type === 'purchase' && (
                <div style={cardBody}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
                    <span style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.04em', color: 'var(--fg-4)' }}>
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
                <div style={{ ...cardBody, display: 'flex', flexDirection: 'column', gap: 5 }}>
                  {s.capture_fields!.map((f, idx) => (
                    <div key={idx} style={{ fontSize: 12.5, color: 'var(--fg-2)' }}>
                      • {f.label} <span style={{ color: 'var(--fg-4)' }}>
                        {f.type === 'measure' ? `(Soll ${f.target ?? '—'}${f.tolerance != null ? ` ± ${f.tolerance}` : ''}${f.unit ? ` ${f.unit}` : ''})` : f.type === 'bool' ? '(Gut/Schlecht)' : '(Text)'}
                      </span>
                    </div>
                  ))}
                </div>
              )}

              {/* Ressource: Positionen (Artikel/Werkzeug + Menge) als Zeilen */}
              {s.step_type === 'resource' && (s.resource_lines?.length ?? 0) > 0 && (
                <div style={{ borderTop: '1px solid var(--border-1)' }}>
                  {s.resource_lines!.map((l, idx) => {
                    const tool = l.mode === 'tool';
                    return (
                      <div key={idx} style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '11px 18px', borderBottom: idx < s.resource_lines!.length - 1 ? '1px solid var(--border-1)' : 'none' }}>
                        <span style={{ width: 32, height: 32, borderRadius: 'var(--r-sm)', flexShrink: 0, background: '#fff', border: `1px solid ${tool ? '#E4D6EA' : '#EADFCB'}`, color: tool ? '#7E5586' : '#9A7238', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                          {tool ? <Wrench size={16} /> : <PackageMinus size={16} />}
                        </span>
                        {l.article_object_id != null && <span style={{ fontFamily: 'var(--font-mono)', fontSize: 13, fontVariantNumeric: 'tabular-nums', color: 'var(--fg-2)', fontWeight: 600, flexShrink: 0 }}>{fmtObjId(l.article_object_id)}</span>}
                        <span style={{ flex: 1, minWidth: 0, font: '600 14px var(--font-body)', color: 'var(--fg-1)', display: 'flex', alignItems: 'center', gap: 9 }}>
                          <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{l.article_name ?? `#${l.article_id}`}</span>
                          {tool && <span style={toolTag}>Werkzeug</span>}
                        </span>
                        <span style={{ font: '700 14px var(--font-body)', color: 'var(--fg-1)', fontVariantNumeric: 'tabular-nums', flexShrink: 0 }}>{l.quantity}<span style={{ font: '500 12px var(--font-body)', color: 'var(--fg-4)', marginLeft: 3 }}>{l.unit ? unitLabel(l.unit) : 'Stk'}</span></span>
                      </div>
                    );
                  })}
                </div>
              )}

            </div>
          </div>
        );
      })}

      {steps.length > 0 && !adding && <Connector />}
      {steps.length > 0 && !adding && <FlowTerm kind="end" />}

      {/* Hinzufügen */}
      {!readOnly && (
        <div style={{ width: '100%', maxWidth: STEP_MAXW, marginTop: 16 }}>
          {adding == null ? (
            <button onClick={() => setAdding('choose')} style={addBtnStyle}>
              <Plus size={15} /> Prozessschritt hinzufügen
            </button>
          ) : adding === 'choose' ? (
            <div style={{ ...editorCard, gap: 14 }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <span style={{ font: '800 15px var(--font-display)', letterSpacing: '-.01em', color: 'var(--fg-1)' }}>Welcher Schritt?</span>
                <button onClick={resetForm} style={{ border: 'none', background: 'none', color: 'var(--fg-4)', cursor: 'pointer', padding: 2 }}><X size={16} /></button>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(150px, 1fr))', gap: 8 }}>
                {chooserTypes.map((t) => {
                  const m = STEP_META[t]; const Icon = m.icon; const kc = kindColor(t, false);
                  return (
                    <button key={t} onClick={() => setAdding(t)} title={STEP_HINT[t]} style={paletteTile}>
                      <div style={{ width: 36, height: 36, borderRadius: 'var(--r-sm)', background: '#fff', border: `1px solid ${kc.border}`, color: kc.fg, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}><Icon size={18} /></div>
                      <span style={{ font: '600 13px var(--font-body)', color: 'var(--fg-1)' }}>{m.label}</span>
                    </button>
                  );
                })}
              </div>
            </div>
          ) : (
            <div style={{ ...editorCard, gap: 14 }}>
              <button onClick={() => setAdding('choose')} style={{ display: 'flex', alignItems: 'center', gap: 5, border: 'none', background: 'none', color: 'var(--accent)', cursor: 'pointer', fontSize: 12, fontWeight: 600, padding: 0, alignSelf: 'flex-start' }}>
                <ArrowLeft size={13} /> {STEP_META[adding].label}
              </button>

              {adding === 'purchase' && (
                <>
                  {/* Die Bezugsquelle (Lieferant/Link) gehört zur Produktspezifikation (Reiter
                      «Spezifikation» → Beschaffung) – NICHT an den Schritt. Kein Override. */}
                  <div style={{ display: 'flex', alignItems: 'flex-start', gap: 8, padding: '10px 12px', background: 'var(--bg-2)', border: '1px solid var(--border-1)', borderRadius: 8, fontSize: 12, color: 'var(--fg-3)' }}>
                    <Info size={14} style={{ flexShrink: 0, marginTop: 1 }} />
                    <span>Bezugsquelle (Lieferant/Link) kommt aus der Produktspezifikation (Reiter «Spezifikation» → Beschaffung). Lieferadresse aus der Systemkonfiguration; der tatsächliche Lagerort wird beim Wareneingang erfasst.</span>
                  </div>
                  {owner === 'articles' && procurementReady === false && (
                    <div style={{ display: 'flex', alignItems: 'flex-start', gap: 8, padding: '10px 12px', background: '#fef2f2', border: '1px solid #fecaca', borderRadius: 8, fontSize: 12, color: '#b91c1c' }}>
                      <Info size={14} style={{ flexShrink: 0, marginTop: 1 }} />
                      <span>Noch keine Bezugsquelle am Artikel hinterlegt – ohne diese lässt sich der Artikel nicht freigeben. Bitte im Reiter «Spezifikation» → Beschaffung ergänzen.</span>
                    </div>
                  )}
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
                <div style={{ display: 'flex', alignItems: 'flex-start', gap: 8, padding: '10px 12px', background: 'var(--bg-2)', border: '1px solid var(--border-1)', borderRadius: 8, fontSize: 12, color: 'var(--fg-3)' }}>
                  <Info size={14} style={{ flexShrink: 0, marginTop: 1 }} />
                  <span>Kaufmännischer Verkauf (Spiegel der Beschaffung): Kunde, Betrag, Rechnung
                    und Zahlung werden beim Auftrag erfasst. Der Versand läuft über eine Bewegung
                    (Ziel = Kunde, mit Sendungsverfolgung).</span>
                </div>
              )}

              {adding === 'document' && (
                <div style={{ display: 'flex', alignItems: 'flex-start', gap: 8, padding: '10px 12px', background: 'var(--bg-2)', border: '1px solid var(--border-1)', borderRadius: 8, fontSize: 12, color: 'var(--fg-3)' }}>
                  <Info size={14} style={{ flexShrink: 0, marginTop: 1 }} />
                  <span>An diesem Schritt entsteht ein Dokument. Den <strong>Inhalt</strong> (Titel,
                    Abschnitte) verfasst du erst im <strong>Auftrag</strong> – dort wird es als
                    nummeriertes PDF im Inexxio-Design ausgestellt (Nummer = Instanz, Datum = Freigabe).</span>
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
  document: 'Dokument (Vertrag, AGB, Zertifikat) – Inhalt im Auftrag verfasst',
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
              <input value={l.quantity} onChange={(e) => upd(i, { quantity: e.target.value })} inputMode="decimal" placeholder="Menge/Einh."
                className="px-2.5 py-1.5 text-sm rounded-md border bg-white outline-none focus:ring-2 focus:ring-[var(--accent)]" style={{ borderColor: 'var(--border-1)', width: 92 }} />
              <button onClick={() => del(i)} style={{ border: 'none', background: 'none', color: 'var(--fg-4)', cursor: 'pointer' }}><Trash2 size={15} /></button>
            </div>
          );
        })}
      </div>
      <button onClick={add} style={{ ...addBtnStyle, marginTop: 8, padding: '8px' }}><Plus size={14} /> Ressource hinzufügen</button>
      <div style={{ marginTop: 6, fontSize: 11, color: 'var(--fg-4)', display: 'flex', alignItems: 'center', gap: 12 }}>
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
          <div key={i} style={{ border: '1px solid var(--border-1)', borderRadius: 8, padding: '8px 10px', display: 'flex', flexDirection: 'column', gap: 8 }}>
            <div style={{ display: 'flex', gap: 8 }}>
              <input value={f.label} onChange={(e) => upd(i, { label: e.target.value })} placeholder="Bezeichnung (z. B. Länge)"
                className="px-2.5 py-1.5 text-sm rounded-md border bg-white outline-none focus:ring-2 focus:ring-[var(--accent)]" style={{ borderColor: 'var(--border-1)', flex: 1 }} />
              <select value={f.type} onChange={(e) => upd(i, { type: e.target.value as WField['type'] })}
                className="px-2 py-1.5 text-sm rounded-md border bg-white" style={{ borderColor: 'var(--border-1)' }}>
                <option value="measure">Soll-Ist</option>
                <option value="bool">Gut/Schlecht</option>
                <option value="text">Text</option>
              </select>
              <button onClick={() => del(i)} style={{ border: 'none', background: 'none', color: 'var(--fg-4)', cursor: 'pointer' }}><Trash2 size={15} /></button>
            </div>
            {f.type === 'measure' && (
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 8 }}>
                <input value={f.target} onChange={(e) => upd(i, { target: e.target.value })} inputMode="decimal" placeholder="Soll"
                  className="px-2.5 py-1.5 text-sm rounded-md border bg-white" style={{ borderColor: 'var(--border-1)' }} />
                <input value={f.tolerance} onChange={(e) => upd(i, { tolerance: e.target.value })} inputMode="decimal" placeholder="± Toleranz"
                  className="px-2.5 py-1.5 text-sm rounded-md border bg-white" style={{ borderColor: 'var(--border-1)' }} />
                <input value={f.unit} onChange={(e) => upd(i, { unit: e.target.value })} placeholder="Einheit"
                  className="px-2.5 py-1.5 text-sm rounded-md border bg-white" style={{ borderColor: 'var(--border-1)' }} />
              </div>
            )}
          </div>
        ))}
      </div>
      <button onClick={add} style={{ ...addBtnStyle, marginTop: 8, padding: '8px' }}><Plus size={14} /> Erfassungsfeld hinzufügen</button>
    </div>
  );
}

// ─── BPMN-Hilfen (zentrierter vertikaler Fluss) ───────────────────────────────
// Farbfamilie je Schritttyp (Design-Redesign): dezente Tönung, Symbol = Bedeutung.
// Pflicht-Schritte bleiben neutral (grau), um «nicht editierbar» zu signalisieren.
const KIND_COLORS: Record<StepType, { bg: string; border: string; fg: string }> = {
  movement:   { bg: '#F3F8FB', border: '#D8E7EF', fg: 'var(--accent-ink)' },
  resource:   { bg: '#FBF6ED', border: '#EADFCB', fg: '#9A7238' },
  purchase:   { bg: '#FBF3EF', border: '#EBD9CF', fg: '#A65A3C' },
  inspection: { bg: '#F3F8FB', border: '#D8E7EF', fg: 'var(--accent-ink)' },
  document:   { bg: 'var(--bg-2)', border: 'var(--border-1)', fg: 'var(--fg-2)' },
  sale:       { bg: '#F0FBF4', border: '#CDEBD6', fg: '#15803D' },
  scrap:      { bg: '#FDF3F2', border: '#F1D6D2', fg: 'var(--danger)' },
};
function kindColor(type: StepType, locked: boolean) {
  if (locked) return { bg: 'var(--bg-2)', border: 'var(--border-1)', fg: 'var(--fg-3)' };
  return KIND_COLORS[type] ?? KIND_COLORS.purchase;
}

function Connector() {
  return <div style={{ width: 2, height: 28, background: 'var(--border-2)', flex: 'none' }} />;
}

// Start-/Endknoten als runder Terminal-Knoten (grün «Start» / dunkel «Ende»).
function FlowTerm({ kind }: { kind: 'start' | 'end' }) {
  const start = kind === 'start';
  return (
    <div style={{
      width: 52, height: 52, borderRadius: '50%', flex: 'none', boxShadow: 'var(--shadow-sm)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      background: start ? 'var(--success)' : 'var(--fg-1)', color: '#fff',
    }} title={start ? 'Start' : 'Ende'}>
      {start ? <Play size={22} /> : <Flag size={20} />}
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
      <div style={{ marginTop: 6, fontSize: 11, color: 'var(--fg-4)' }}>
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
        border: `1px solid ${on ? 'var(--accent-soft)' : 'var(--border-1)'}`,
        background: on ? 'var(--accent-soft)' : '#fff', color: on ? 'var(--accent)' : 'var(--fg-4)',
        cursor: onClick ? 'pointer' : 'default', opacity: locked ? 0.85 : 1,
      }}>
      {label}
    </button>
  );
}

const STEP_MAXW = 600;   // Kartenbreite im zentrierten Fluss
// Karten-Unterbereich (unter dem Kopf): Haarlinie oben, gleiche horizontale Polsterung.
const cardBody: React.CSSProperties = {
  borderTop: '1px solid var(--border-1)', padding: '12px 18px 15px',
};
// Editor-/Palette-Karte (neutral, für «Schritt hinzufügen»).
const editorCard: React.CSSProperties = {
  width: '100%', display: 'flex', flexDirection: 'column', alignItems: 'stretch',
  background: '#fff', border: '1px solid var(--border-1)', borderRadius: 'var(--r-lg)',
  boxShadow: 'var(--shadow-sm)', padding: '16px 18px',
};
const pflichtBadge: React.CSSProperties = {
  fontSize: 10, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.04em',
  color: 'var(--fg-3)', background: 'var(--bg-3)', padding: '1px 6px', borderRadius: 999,
};
const delBtn: React.CSSProperties = {
  border: 'none', background: 'none', color: 'var(--fg-4)', cursor: 'pointer', padding: 4, flexShrink: 0,
};
const paletteTile: React.CSSProperties = {
  display: 'flex', alignItems: 'center', gap: 10, padding: '10px 12px',
  borderRadius: 'var(--r-md)', border: '1px solid var(--border-1)', background: '#fff', cursor: 'pointer',
};
const toolTag: React.CSSProperties = {
  fontSize: 10, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.04em',
  color: '#7E5586', background: '#F6F1F8', padding: '1px 6px', borderRadius: 4, flexShrink: 0,
};
const noticeStyle: React.CSSProperties = {
  display: 'flex', alignItems: 'flex-start', gap: 8, padding: '12px 14px',
  background: '#fffbeb', border: '1px solid #fde68a', borderRadius: 10, fontSize: 13, color: '#92400e',
};
const addBtnStyle: React.CSSProperties = {
  display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6, padding: '12px',
  borderRadius: 'var(--r-lg)', border: '1px dashed var(--border-2)', background: '#fff', color: 'var(--accent)',
  fontSize: 13, fontWeight: 600, cursor: 'pointer', width: '100%',
};
const primaryBtn: React.CSSProperties = {
  padding: '7px 14px', borderRadius: 7, border: 'none', background: 'var(--accent)',
  color: '#fff', fontSize: 13, fontWeight: 600, cursor: 'pointer',
};
const secondaryBtn: React.CSSProperties = {
  padding: '7px 14px', borderRadius: 7, border: '1px solid var(--border-1)', background: '#fff',
  color: 'var(--fg-2)', fontSize: 13, cursor: 'pointer',
};
const miniPrimary: React.CSSProperties = {
  display: 'flex', alignItems: 'center', gap: 4, padding: '3px 9px', borderRadius: 6,
  border: 'none', background: 'var(--accent)', color: '#fff', fontSize: 11, fontWeight: 600, cursor: 'pointer',
};
const miniGhost: React.CSSProperties = {
  padding: '3px 9px', borderRadius: 6, border: '1px solid var(--border-1)', background: '#fff',
  color: 'var(--fg-2)', fontSize: 11, fontWeight: 600, cursor: 'pointer',
};
