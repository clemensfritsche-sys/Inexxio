'use client';

import { useEffect, useMemo, useState } from 'react';
import { Plus, Trash2, Link2, User as UserIcon, Info, Eye, Check, GripVertical, X, ArrowLeft, Lock, Wrench, PackageMinus, Play, Flag, ShoppingCart, Truck, Globe, Building2, Ban, Users as UsersIcon, Shield } from 'lucide-react';
import { api } from '@/lib/api';
import type { Article, ArticleProcessStep, CaptureField, DocAudienceRole, Instance, LocationType, ProcessStepMode, ResourceMode, StepType, UserProfile } from '@/types';
import { userDisplayName } from '@/lib/utils';
import { unitLabel } from '@/lib/article';
import { STEP_META, locationTypeLabel, instanceLabel, isStockOperation } from '@/lib/process';
import { SUPPLIER_FIELD_CATALOG, MANDATORY_FIELD_KEYS, normalizeSharedFields, fieldLabel } from '@/lib/article-fields';
import { ErrorText, IconSwitch, InfoHint, Label, Segmented, SearchSelect, TextField, numericOnly, numericInputProps } from '@/components/erp/fields';
import { fmtObjId } from '@/components/erp/user-detail';
import { ObjId } from '@/components/erp/obj-id';

// Gültiger Webshop-Link: http(s) mit einem Host inkl. Punkt (z. B. shop.example.com).
function isValidWebshopUrl(v: string): boolean {
  try {
    const u = new URL(v.trim());
    return (u.protocol === 'http:' || u.protocol === 'https:') && u.hostname.includes('.');
  } catch {
    return false;
  }
}

type WField = { label: string; type: 'measure' | 'bool' | 'text' | 'photo' | 'signature'; target: string; tolerance: string; unit: string };
// EIN Ressource-Schritt; pro Zeile ein Modus (Verbrauch | Betriebsmittel).
type ResLine = { article_id: string; quantity: string; mode: ResourceMode };

// «Dokument»-Deklaration am Schritt (Freigabe-Struktur, gilt für alle Ausfertigungen).
type DocSignerRow = { signer_object_id: number; action: 'confirm' | 'sign' };
type DocCfg = {
  signers: DocSignerRow[];              // endliche Freigabe-Parteien (geordnet)
  sequential: boolean;                  // Reihenfolge erzwingen
  audience: '' | 'all' | 'roles' | 'persons';   // offenes Anerkennungs-Publikum
  roles: string[];                      // bei audience='roles'
  persons: number[];                    // bei audience='persons' (Objektnummern)
  visibility: 'public' | 'internal' | 'confidential';
};
function emptyDocCfg(): DocCfg {
  return { signers: [], sequential: false, audience: '', roles: [], persons: [], visibility: 'internal' };
}

// Zulässige Schritttypen je Kontext (Spiegel von Backend domain.event_types):
// Artikel = Herstellung (kein Verkauf); Auftrag = Operation am Bestand mit **allen**
// Typen – auch purchase (auswärtige Vergabe, z. B. Wartung) und resource (Verbrauchs-/
// Hilfsmaterial, Ersatzteile). So sind die Prozessschritte immer kompatibel.
const ARTICLE_STEP_ORDER: StepType[] = ['purchase', 'resource', 'inspection', 'movement', 'document'];
const ORDER_STEP_ORDER: StepType[] = ['purchase', 'resource', 'inspection', 'movement', 'scrap', 'sale', 'document'];

export function ProcessSteps({ owner, ownerObjectId, suppliers = [], readOnly = false, onStepsCount, selfArticleObjectId = null, procurementReady }: {
  owner: 'articles' | 'orders';          // Prozess am Artikel (Entstehung) oder am Auftrag (CUSTOM)
  ownerObjectId: number | null;          // Objektnummer des Trägers
  suppliers?: UserProfile[];             // Auswahl der Bezugsquelle direkt im Beschaffungs-Schritt
  readOnly?: boolean;
  onStepsCount?: (n: number, isStockOp: boolean) => void;
  selfArticleObjectId?: number | null;   // Artikel des Trägers (Ressource-Selbst-Ausschluss)
  procurementReady?: boolean;            // Artikel-Beschaffungsquelle hinterlegt? (Warnung am purchase-Schritt)
}) {
  const [steps, setSteps] = useState<ArticleProcessStep[]>([]);
  const [loading, setLoading] = useState(false);
  const [adding, setAdding] = useState<'choose' | StepType | null>(null);
  // Bezugsquelle des Beschaffungs-Schritts (im Prozess definiert, je Schritt eigen):
  const [mode, setMode] = useState<ProcessStepMode>('supplier');
  const [supplierId, setSupplierId] = useState('');
  const [url, setUrl] = useState('');
  const [shared, setShared] = useState<string[]>(MANDATORY_FIELD_KEYS);
  const [samplePercent, setSamplePercent] = useState('100');
  const [wfields, setWfields] = useState<WField[]>([]);
  // Datenerfassung – Bilderfassung + Freigabe/Unterschrift
  const [docCfg, setDocCfg] = useState<DocCfg>(emptyDocCfg());   // «Dokument»-Freigabe-Deklaration
  const [targetSel, setTargetSel] = useState('');   // kombiniertes Ziel "type:objid" ('' = frei)
  const [company, setCompany] = useState<{ objectId: number; name: string } | null>(null);
  const [allUsers, setAllUsers] = useState<UserProfile[]>([]);
  const [allInstances, setAllInstances] = useState<Instance[]>([]);
  const [articles, setArticles] = useState<Article[]>([]);
  const [resLines, setResLines] = useState<ResLine[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [drag, setDrag] = useState<number | null>(null);
  const [over, setOver] = useState<number | null>(null);

  useEffect(() => {
    if (ownerObjectId == null) return;
    setLoading(true);
    api.getSteps(owner, ownerObjectId!).then(setSteps).catch(() => {}).finally(() => setLoading(false));
    // Das Unternehmen («im Betrieb») für den editierbaren Wareneingang-Zielselektor
    api.getPublicSettings()
      .then((c) => { if (c.object_id != null) setCompany({ objectId: c.object_id, name: c.company_name || 'Im Betrieb' }); })
      .catch(() => {});
  }, [owner, ownerObjectId]);

  // Schrittanzahl + abgeleitete Auftragsart (Bestands-Operation vs. Herstellung) an das
  // Elternfenster melden – Letzteres über die deklarierte Subjekt-Rolle der Schritte
  // (Spiegel der Backend-Registry), damit ein Beschaffungs-/Ressourcen-Schritt korrekt
  // als «Herstellung» und nicht als «Bestands-Operation» erkannt wird.
  useEffect(() => {
    onStepsCount?.(steps.length, isStockOperation(steps.map((s) => s.step_type as StepType)));
  }, [steps, onStepsCount]);

  // Personen laden, sobald ein «Dokument»-Schritt existiert – auch read-only (freigegebener
  // Prozess), damit die Freigabe-Parteien mit NAMEN statt nur als Zahl sichtbar sind.
  useEffect(() => {
    if (allUsers.length > 0) return;
    if (steps.some((s) => s.step_type === 'document')) {
      api.getUsers().then(setAllUsers).catch(() => {});
    }
  }, [steps, allUsers.length]);

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

  // Beim Öffnen des Beschaffungs-Formulars die Bezugsquelle mit dem **Artikel-Standard**
  // vorbelegen (Reiter «Spezifikation» → Beschaffung) – je Schritt frei überschreibbar, sodass
  // ein Prozess mehrere Beschaffungen mit unterschiedlichen Lieferanten abbilden kann.
  useEffect(() => {
    if (adding !== 'purchase') return;
    setMode((selfArticle?.procurement_mode as ProcessStepMode) || 'supplier');
    setSupplierId(selfArticle?.default_supplier_id != null ? String(selfArticle.default_supplier_id) : '');
    setUrl(selfArticle?.default_webshop_url ?? '');
  }, [adding, selfArticle]);

  // Bewegung braucht Personen/Instanzen/Unternehmen als Zielauswahl; Ressource die Artikel.
  // (Beschaffung: keine Lieferadresse mehr am Schritt – kommt aus der Systemkonfiguration.)
  useEffect(() => {
    if (adding === 'resource') { api.getArticles().then(setArticles).catch(() => {}); return; }
    if (adding === 'inspection') {
      setWfields([]);   // frisches Formular
      return;
    }
    if (adding === 'document') {
      // Personen für die Freigabe-Parteien + Publikums-Auswahl (jede Rolle wählbar).
      api.getUsers().then(setAllUsers).catch(() => {});
      setDocCfg(emptyDocCfg());
      return;
    }
    if (adding !== 'movement') return;
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
    setTargetSel(''); setResLines([]); setDocCfg(emptyDocCfg()); setError(null);
  }

  // Nach Strukturänderungen die kanonische Liste neu laden (inkl. einer beim Anlegen
  // gesäten Begleit-Bewegung + serverseitiger Positionen).
  async function reload() {
    try { setSteps(await api.getSteps(owner, ownerObjectId!)); } catch { /* ignore */ }
  }

  // Rolle einer gesäten Begleit-Bewegung: Versand zum Kunden (mode=customer) oder
  // Wareneingang. Die Rolle ist ein Hinweis, keine Sperre – der Schritt lässt sich wie
  // jeder andere verschieben und löschen.
  function companionRole(s: ArticleProcessStep): 'wareneingang' | 'versandkunde' {
    return (s.mode as string) === 'customer' ? 'versandkunde' : 'wareneingang';
  }

  // Wareneingang-Ziel setzen (Behälter/Unternehmen oder offen).
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
    // Beschaffung: Bezugsquelle wird **direkt im Prozessschritt** definiert (Lieferant ODER
    // Webshop-Link), vorbelegt aus dem Artikel-Standard, je Schritt frei überschreibbar – so
    // kann EIN Prozess mehrere Beschaffungen mit unterschiedlichen Quellen abbilden. Ein leer
    // gelassener Schritt erbt automatisch den Artikel-Standard (Fallback im Backend).
    if (type === 'purchase' && mode === 'webshop' && url.trim() && !isValidWebshopUrl(url)) {
      setError('Bitte einen gültigen Webshop-Link angeben (https://…)'); return;
    }
    if (type === 'inspection') {
      const p = Number(samplePercent);
      if (!Number.isFinite(p) || p < 1 || p > 100) { setError('Prüfumfang muss 1–100 % sein'); return; }
      // Eine Datenerfassung ohne definierte Information ist ein Schritt ohne Inhalt: das
      // Panel zeigt dann nichts zu erfassen und der Auftrag käme nicht weiter.
      if (buildCaptureFields().length === 0) {
        setError('Bitte mindestens ein Erfassungsfeld festlegen – ohne definierte Information gibt es nichts zu erfassen'); return;
      }
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
        // Bezugsquelle direkt am Schritt (leer = Artikel-Standard erben).
        mode: type === 'purchase' ? mode : undefined,
        supplier_id: type === 'purchase' && mode === 'supplier' && supplierId ? Number(supplierId) : null,
        webshop_url: type === 'purchase' && mode === 'webshop' && url.trim() ? url.trim() : null,
        shared_fields: type === 'purchase' ? shared : null,
        sample_percent: type === 'inspection' ? Math.trunc(Number(samplePercent)) : null,
        capture_fields: type === 'inspection' ? buildCaptureFields() : null,
        target_location_type: tgt ? (tgt[0] as LocationType) : null,
        target_location_id: tgt ? Number(tgt[1]) : null,
        resource_lines: resourcePayload,
        // «Dokument»-Freigabe-Deklaration (nur beim Dokument-Schritt gesetzt).
        doc_signers: type === 'document' && docCfg.signers.length ? docCfg.signers : null,
        sign_sequential: type === 'document' ? docCfg.sequential : false,
        doc_audience: type === 'document' && docCfg.audience ? docCfg.audience : null,
        doc_audience_roles: type === 'document' && docCfg.audience === 'roles' ? (docCfg.roles as DocAudienceRole[]) : null,
        doc_audience_person_ids: type === 'document' && docCfg.audience === 'persons' ? docCfg.persons : null,
        doc_visibility: type === 'document' ? docCfg.visibility : undefined,
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

  // Ein bestehender Schritt wird NICHT mehr nachträglich umkonfiguriert – wie bei jedem
  // anderen Modul: löschen und neu anlegen. Das hielt zwei Bearbeitungs-Zustände (Sichtbare
  // Felder, Dokument-Deklaration) am Leben, die es sonst nirgends gab.

  async function persistOrder(orderedFull: ArticleProcessStep[]) {
    setSteps(orderedFull);  // optimistisch
    // ALLE Schritte sind frei sortierbar – auch die gesäten Begleit-Bewegungen. Früher
    // wurden sie hier ausgefiltert und vom Server automatisch neu positioniert.
    const ids = orderedFull.map((s) => s.id);
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
        const isCompanion = s.companion;
        const canDrag = !readOnly;
        const isOver = over === i && drag !== null && drag !== i;
        const kc = kindColor(s.step_type as StepType);
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
                {!readOnly && <GripVertical size={16} style={{ color: 'var(--border-2)', cursor: 'grab', flexShrink: 0 }} />}
                <div style={{ width: 38, height: 38, borderRadius: 'var(--r-sm)', flexShrink: 0, background: '#fff', color: kc.fg, border: `1px solid ${kc.border}`, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  <Icon size={19} />
                </div>
                <div style={{ minWidth: 0, flex: 1 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <span style={{ font: '800 16px var(--font-display)', letterSpacing: '-.01em', color: 'var(--fg-1)' }}>{meta.label}</span>
                  </div>
                  <div style={{ marginTop: 3, fontSize: 12, color: 'var(--fg-3)' }}>
                    {isCompanion && (companionRole(s) === 'versandkunde'
                      ? <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}><UserIcon size={12} /> Versand zum Kunden · Ziel beim Versand</span>
                      : (s.target_location_id
                        ? `Wareneingang → ${fmtObjId(s.target_location_id)}`
                        : 'Wareneingang · frei beim Einlagern'))}
                    {!isCompanion && s.step_type === 'purchase' && (() => {
                      // Bezugsquelle am Schritt (Lieferant/Webshop) – oder geerbt vom Artikel-Standard.
                      if (s.mode === 'webshop' && s.webshop_url)
                        return <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}><ShoppingCart size={12} /> Webshop · {s.webshop_url.replace(/^https?:\/\//, '').slice(0, 40)}</span>;
                      if (s.mode === 'supplier' && s.supplier_id)
                        // Symbol statt Wort, und die Objektnummer ist klickbar (öffnet den
                        // Lieferanten). ``supplier_id`` ist der INTERNE Schlüssel – angezeigt
                        // wird ausschliesslich ``supplier_object_id``.
                        return (
                          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }} title="Lieferant">
                            <Truck size={12} />
                            {s.supplier_object_id != null && <ObjId value={s.supplier_object_id} />}
                            {s.supplier_name}
                          </span>
                        );
                      // Kein Schritt-Override → erbt den Artikel-Standard. Fehlt der ebenfalls, roter Hinweis.
                      return owner === 'articles' && procurementReady === false
                        ? <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, color: '#b91c1c', fontWeight: 600 }}><ShoppingCart size={12} /> Bezugsquelle fehlt – Schritt oder Spezifikation ergänzen</span>
                        : <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}><ShoppingCart size={12} /> Bezugsquelle vom Artikel-Standard</span>;
                    })()}
                    {/* Nur der Prüfumfang – WAS erfasst wird, steht ausformuliert im Schritt
                        selbst; die blosse Anzahl der Felder sagte nichts, was dort nicht steht. */}
                    {s.step_type === 'inspection' && `Stichprobe ${s.sample_percent ?? 100}%`}
                    {!isCompanion && s.step_type === 'movement' && (s.target_location_id
                      // Objektnummer zuerst, danach die Bezeichnung – überall dieselbe
                      // Lesereihenfolge wie in den Auswahllisten («100000002 · Person»).
                      ? `Ziel: ${fmtObjId(s.target_location_id)} · ${locationTypeLabel(s.target_location_type)}`
                      : 'Standort nicht definiert – Lagerist wählt beim Einlagern')}
                    {s.step_type === 'resource' && `${s.resource_lines?.length ?? 0} Position${(s.resource_lines?.length ?? 0) === 1 ? '' : 'en'}`}
                    {s.step_type === 'sale' && 'Verkauf / Gutschrift – Betrag & Kunde im Auftrag'}
                    {s.step_type === 'scrap' && 'Verschrotten – gewählte Instanzen im Auftrag'}
                    {s.step_type === 'document' && (
                      <span>{(() => {
                        const n = s.doc_signers?.length ?? 0;
                        const parts: string[] = [];
                        parts.push(n > 0 ? `${n} Freigabe-Partei${n === 1 ? '' : 'en'}${s.sign_sequential ? ' · sequenziell' : ''}` : 'ohne Freigabe-Parteien');
                        if (s.doc_audience) parts.push(`Publikum: ${s.doc_audience === 'all' ? 'alle' : s.doc_audience === 'roles' ? 'Rollen' : 'Personen'}`);
                        if (s.doc_visibility && s.doc_visibility !== 'internal') parts.push(s.doc_visibility === 'public' ? 'öffentlich' : 'vertraulich');
                        return parts.join(' · ');
                      })()}</span>
                    )}
                  </div>
                </div>
                {!readOnly && (
                  <button onClick={() => removeStep(s.id)} title="Modul löschen" style={delBtn}><Trash2 size={15} /></button>
                )}
              </div>

              {/* Wareneingang: Ziel definierbar wie bei regulärer Bewegung */}
              {isCompanion && !readOnly && companionRole(s) === 'wareneingang' && (
                <div style={cardBody}>
                  <Label>Ziel Wareneingang (optional)</Label>
                  <SearchSelect
                    value={s.target_location_id ? `${s.target_location_type}:${s.target_location_id}` : ''}
                    onChange={(v) => setLockedTarget(s.id, v)}
                    placeholder="frei – Lagerist wählt beim Einlagern"
                    options={[
                      { value: '', label: 'frei – Lagerist wählt beim Einlagern' },
                      ...(company ? [{ value: `company:${company.objectId}`, label: `Im Betrieb · ${company.name}` }] : []),
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
                  </div>
                  <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap' }}>
                    {normalizeSharedFields(s.shared_fields).map((k) => <Chip key={k} label={fieldLabel(k)} on />)}
                  </div>
                </div>
              )}

              {/* Dokument: Freigabe-Deklaration (Parteien/Publikum/Sichtbarkeit) – wie jedes
                  andere Modul nicht nachträglich änderbar: löschen und neu anlegen. */}
              {s.step_type === 'document' && (
                <div style={cardBody}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
                    <span style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.04em', color: 'var(--fg-4)' }}>
                      <Lock size={12} /> Freigabe & Anerkennung
                    </span>
                  </div>
                  <DocConfigView step={s} users={allUsers} />
                </div>
              )}

              {/* Datenerfassung: Maske-Übersicht */}
              {s.step_type === 'inspection' && (s.capture_fields?.length ?? 0) > 0 && (
                <div style={{ ...cardBody, display: 'flex', flexDirection: 'column', gap: 5 }}>
                  {s.capture_fields!.map((f, idx) => (
                    <div key={idx} style={{ fontSize: 12.5, color: 'var(--fg-2)' }}>
                      • {f.label} <span style={{ color: 'var(--fg-4)' }}>
                        {f.type === 'measure' ? `(Soll ${f.target ?? '—'}${f.tolerance != null ? ` ± ${f.tolerance}` : ''}${f.unit ? ` ${f.unit}` : ''})` : f.type === 'bool' ? '(Gut/Schlecht)' : f.type === 'photo' ? '(Foto)' : f.type === 'signature' ? '(Unterschrift)' : '(Text)'}
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
                  const m = STEP_META[t]; const Icon = m.icon; const kc = kindColor(t);
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
                  {/* Bezugsquelle direkt im Prozessschritt (Lieferant ODER Webshop-Link) –
                      vorbelegt aus dem Artikel-Standard, je Schritt frei überschreibbar, sodass
                      ein Prozess mehrere Beschaffungen mit unterschiedlichen Quellen abbilden kann. */}
                  <div>
                    <Label>Bezugsquelle</Label>
                    <IconSwitch<ProcessStepMode> symbolOnly value={mode} onChange={setMode}
                      options={[
                        { value: 'supplier', icon: Truck, label: 'Lieferant', hint: 'Bestellung bei einem Lieferanten' },
                        { value: 'webshop', icon: Globe, label: 'Webshop', hint: 'Kauf über einen Webshop-Link' },
                      ]} />
                  </div>
                  {mode === 'supplier' ? (
                    <SearchSelect label="Lieferant" value={supplierId} onChange={setSupplierId}
                      placeholder="Artikel-Standard erben"
                      options={[
                        { value: '', label: 'Artikel-Standard erben' },
                        ...suppliers.filter((s) => s.object_id != null).map((s) => ({
                          value: String(s.id), label: `${fmtObjId(s.object_id)} · ${userDisplayName(s)}` })),
                      ]} />
                  ) : (
                    <TextField label="Webshop-Link" value={url} onChange={setUrl}
                      placeholder="https://shop.example.com/artikel" hint="Leer lassen, um den Artikel-Standard zu erben." />
                  )}
                  {owner === 'articles' && procurementReady === false && mode === 'supplier' && !supplierId && (
                    <div style={{ display: 'flex', alignItems: 'flex-start', gap: 8, padding: '10px 12px', background: '#fef2f2', border: '1px solid #fecaca', borderRadius: 8, fontSize: 12, color: '#b91c1c' }}>
                      <Info size={14} style={{ flexShrink: 0, marginTop: 1 }} />
                      <span>Ohne Bezugsquelle (hier oder als Artikel-Standard) lässt sich der Artikel nicht freigeben.</span>
                    </div>
                  )}
                  <div><Label>Für Lieferant sichtbar</Label><FieldChips value={shared} onChange={setShared} optionalAvailable={optionalShareKeys} /></div>
                </>
              )}

              {adding === 'inspection' && (
                <>
                  <SampleScope value={samplePercent} onChange={setSamplePercent} />
                  <CaptureFieldsEditor fields={wfields} onChange={setWfields} />
                </>
              )}

              {adding === 'movement' && (
                <>
                  <SearchSelect label="Zielstandort (optional)" value={targetSel} onChange={setTargetSel}
                    placeholder="Nicht definiert – Lagerist wählt beim Einlagern"
                    options={[
                      { value: '', label: 'Nicht definiert – Lagerist wählt beim Einlagern' },
                      ...(company ? [{ value: `company:${company.objectId}`, label: `Im Betrieb · ${company.name}` }] : []),
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
                <DocConfigEditor cfg={docCfg} onChange={setDocCfg} users={allUsers} />
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
  block: 'Instanzen vorübergehend sperren (aufhebbar) – z. B. Maschine bis zur Wartung',
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
              <input value={l.quantity} onChange={(e) => upd(i, { quantity: numericOnly(e.target.value) })} {...numericInputProps} placeholder="Menge/Einh."
                className="px-2.5 py-1.5 text-sm rounded-md border bg-white outline-none focus:ring-2 focus:ring-[var(--accent)]" style={{ borderColor: 'var(--border-1)', width: 92 }} />
              <button onClick={() => del(i)} style={{ border: 'none', background: 'none', color: 'var(--fg-4)', cursor: 'pointer' }}><Trash2 size={15} /></button>
            </div>
          );
        })}
      </div>
      {/* Leere Liste braucht das Wort, danach genügt das Symbol (Bedeutung im Hover). */}
      <AddRowButton label="Ressource hinzufügen" compact={lines.length > 0} onClick={add} />
    </div>
  );
}

/**
 * **Prüfumfang** als Voreinstellungen statt Prozent-Eingabe: In der Praxis prüft man jedes
 * Stück, jedes zweite, jedes vierte oder eine Handvoll – vier Chips decken das ab und
 * brauchen keinen Erklärsatz. Ein abweichender Wert (z. B. 7 %) bleibt möglich: «…»
 * blendet das Zahlenfeld ein, und ein bereits gespeicherter Sonderwert erscheint als
 * eigener Chip, statt still verlorenzugehen.
 */
const SAMPLE_PRESETS = [
  { pct: '100', label: 'Alle', hint: '100 % – jedes Stück wird geprüft' },
  { pct: '50', label: 'Jedes 2.', hint: '50 % der Menge' },
  { pct: '25', label: 'Jedes 4.', hint: '25 % der Menge' },
  { pct: '10', label: 'Stichprobe', hint: '10 % der Menge' },
];

/** Zeile hinzufügen: solange die Liste leer ist mit Wort, danach nur noch «+» (Hover erklärt). */
function AddRowButton({ label, compact, onClick }: { label: string; compact: boolean; onClick: () => void }) {
  return (
    <button onClick={onClick} title={label} aria-label={label}
      style={{ ...addBtnStyle, marginTop: 8, padding: '8px', width: compact ? 38 : undefined }}>
      <Plus size={14} />{!compact && ` ${label}`}
    </button>
  );
}

function SampleScope({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  const isPreset = SAMPLE_PRESETS.some((p) => p.pct === value);
  const [custom, setCustom] = useState(!isPreset && value !== '');
  return (
    <div>
      <Label required>Prüfumfang</Label>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, alignItems: 'center' }}>
        {SAMPLE_PRESETS.map((p) => {
          const on = value === p.pct && !custom;
          return (
            <button key={p.pct} type="button" title={p.hint}
              onClick={() => { setCustom(false); onChange(p.pct); }}
              style={{
                padding: '6px 12px', borderRadius: 'var(--r-pill)', cursor: 'pointer',
                font: '600 12.5px var(--font-body)',
                border: `1px solid ${on ? 'var(--accent)' : 'var(--border-1)'}`,
                background: on ? 'var(--accent-soft)' : '#fff',
                color: on ? 'var(--accent-ink)' : 'var(--fg-3)',
              }}>
              {p.label}
            </button>
          );
        })}
        <button type="button" title="Anderer Prüfumfang in Prozent" onClick={() => setCustom(true)}
          style={{
            padding: '6px 12px', borderRadius: 'var(--r-pill)', cursor: 'pointer',
            font: '600 12.5px var(--font-body)',
            border: `1px solid ${custom ? 'var(--accent)' : 'var(--border-1)'}`,
            background: custom ? 'var(--accent-soft)' : '#fff',
            color: custom ? 'var(--accent-ink)' : 'var(--fg-3)',
          }}>
          …
        </button>
        {custom && (
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5 }}>
            <input value={value} onChange={(e) => onChange(numericOnly(e.target.value, { decimals: false }))}
              {...numericInputProps} placeholder="z. B. 7"
              className="px-2.5 py-1.5 text-sm rounded-md border bg-white outline-none focus:ring-2 focus:ring-[var(--accent)]"
              style={{ borderColor: 'var(--border-1)', width: 76 }} />
            <span style={{ font: '500 12.5px var(--font-body)', color: 'var(--fg-3)' }}>%</span>
          </span>
        )}
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
                <option value="photo">Bild</option>
                <option value="signature">Unterschrift</option>
              </select>
              <button onClick={() => del(i)} style={{ border: 'none', background: 'none', color: 'var(--fg-4)', cursor: 'pointer' }}><Trash2 size={15} /></button>
            </div>
            {f.type === 'measure' && (
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 96px), 1fr))', gap: 8 }}>
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
      <AddRowButton label="Erfassungsfeld hinzufügen" compact={fields.length > 0} onClick={add} />
    </div>
  );
}

// ─── Option-Umschalter (Datenerfassung: Bilderfassung / Freigabe) ─────────────
function OptionToggle({ checked, onChange, label, hint }: {
  checked: boolean; onChange: (v: boolean) => void; label: string; hint?: string;
}) {
  return (
    <label style={{ display: 'flex', alignItems: 'flex-start', gap: 9, cursor: 'pointer', padding: '2px 0' }}>
      <input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)}
        style={{ width: 16, height: 16, marginTop: 2, accentColor: 'var(--accent)' }} />
      <span style={{ minWidth: 0 }}>
        <span style={{ display: 'block', font: '700 13px var(--font-body)', color: 'var(--fg-1)' }}>{label}</span>
        {hint && <span style={{ display: 'block', font: '500 11.5px var(--font-body)', color: 'var(--fg-4)', marginTop: 1 }}>{hint}</span>}
      </span>
    </label>
  );
}

// ─── «Dokument»-Deklaration: Freigabe-Parteien + Publikum + Sichtbarkeit ──────
const AUDIENCE_ROLE_LABELS: Record<string, string> = {
  customer: 'Kunden', supplier: 'Lieferanten', employee: 'Mitarbeiter', admin: 'Admins',
};

// Read-only-Ansicht der «Dokument»-Deklaration (freigegebener bzw. nicht editierter Prozess):
// zeigt ALLE definierten Details – Freigabe-Parteien mit NAMEN, Aktion (Bestätigen/
// Unterschreiben) und Reihenfolge, Sichtbarkeit sowie Anerkennungs-Publikum (mit Namen/Rollen).
// So ist im freigegebenen Prozess vollständig nachvollziehbar, was der Dokument-Schritt tut.
function DocConfigView({ step, users }: { step: ArticleProcessStep; users: UserProfile[] }) {
  const nameOf = (oid: number) => {
    const u = users.find((x) => x.object_id === oid);
    return u ? userDisplayName(u) : `Objekt ${fmtObjId(oid)}`;
  };
  const signers = step.doc_signers ?? [];
  const vis = step.doc_visibility ?? 'internal';
  const visLabel = vis === 'public' ? 'Öffentlich' : vis === 'confidential' ? 'Vertraulich' : 'Intern';
  const aud = step.doc_audience;
  const audienceText = !aud
    ? 'Keine Anerkennungspflicht'
    : aud === 'all' ? 'Alle Angemeldeten'
    : aud === 'roles' ? ((step.doc_audience_roles ?? []).map((r) => AUDIENCE_ROLE_LABELS[r] ?? r).join(', ') || 'Rollen')
    : `Bestimmte Personen: ${(step.doc_audience_person_ids ?? []).map(nameOf).join(', ') || '—'}`;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      <div>
        <div style={dv.label}>Freigabe-Parteien{step.sign_sequential && signers.length > 1 ? ' · der Reihe nach' : ''}</div>
        {signers.length === 0 ? (
          <div style={dv.muted}>Keine – mit «Ausstellen» sofort freigegeben.</div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 5, marginTop: 5 }}>
            {signers.map((s, i) => (
              <div key={i} style={dv.row}>
                <span style={dv.idx}>{i + 1}.</span>
                <span style={dv.name}>{nameOf(s.signer_object_id)}</span>
                <span style={dv.tag}>{s.action === 'confirm' ? 'Bestätigen' : 'Unterschreiben'}</span>
                <span style={dv.nr}>{fmtObjId(s.signer_object_id)}</span>
              </div>
            ))}
          </div>
        )}
      </div>
      <div style={dv.kv}>
        <span style={dv.label}>Sichtbarkeit</span>
        <span style={dv.value}>{visLabel}</span>
      </div>
      <div>
        <div style={dv.label}>Anerkennungs-Publikum</div>
        <div style={{ ...dv.value, marginTop: 3 }}>{audienceText}</div>
      </div>
    </div>
  );
}

const dv: Record<string, React.CSSProperties> = {
  label: { font: '700 11px var(--font-body)', textTransform: 'uppercase', letterSpacing: '0.04em', color: 'var(--fg-4)' },
  muted: { font: '500 12.5px var(--font-body)', color: 'var(--fg-4)', marginTop: 3 },
  row: { display: 'flex', alignItems: 'center', gap: 8, padding: '6px 9px', borderRadius: 8, border: '1px solid var(--border-1)', background: '#fff' },
  idx: { font: '700 11px var(--font-body)', color: 'var(--fg-4)', minWidth: 16 },
  name: { flex: 1, font: '600 13px var(--font-body)', color: 'var(--fg-1)', minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' },
  tag: { font: '600 11px var(--font-body)', color: 'var(--accent-ink)', background: 'var(--accent-soft)', padding: '2px 8px', borderRadius: 999, flexShrink: 0 },
  nr: { fontFamily: 'var(--font-mono)', fontSize: 11.5, color: 'var(--fg-4)', fontVariantNumeric: 'tabular-nums', flexShrink: 0 },
  kv: { display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 },
  value: { font: '600 13px var(--font-body)', color: 'var(--fg-2)' },
};

/**
 * Beschriftung im Dokument-Schritt als **Frage**: «Wer muss freigeben?» sagt einem Laien
 * sofort, was hier einzustellen ist – «Freigabe-Parteien (Unterschrift / Bestätigung)»
 * setzt das Vokabular des Systems voraus. Die genaue Wirkung steht im ⓘ-Hover, nicht als
 * Absatz in der Fläche.
 */
function DocLabel({ text, hint }: { text: string; hint?: string }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 5, marginBottom: 6 }}>
      <span style={{ font: '600 11px var(--font-body)', textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--fg-3)' }}>
        {text}
      </span>
      {hint && <InfoHint text={hint} />}
    </div>
  );
}

function DocConfigEditor({ cfg, onChange, users }: {
  cfg: DocCfg; onChange: (c: DocCfg) => void; users: UserProfile[];
}) {
  const [drag, setDrag] = useState<number | null>(null);
  const set = (patch: Partial<DocCfg>) => onChange({ ...cfg, ...patch });
  const pickable = users.filter((u) => u.object_id != null);
  const nameOf = (oid: number) => {
    const u = users.find((x) => x.object_id === oid);
    return u ? userDisplayName(u) : `Objekt ${fmtObjId(oid)}`;
  };
  const chosen = new Set(cfg.signers.map((s) => s.signer_object_id));
  const signerOptions = [
    { value: '', label: '+ Freigabe-Partei hinzufügen…' },
    ...pickable.filter((u) => !chosen.has(u.object_id!)).map((u) => ({
      value: String(u.object_id), label: `${userDisplayName(u)} · ${fmtObjId(u.object_id!)}` })),
  ];
  const personOptions = [
    { value: '', label: '+ Person hinzufügen…' },
    ...pickable.filter((u) => !cfg.persons.includes(u.object_id!)).map((u) => ({
      value: String(u.object_id), label: `${userDisplayName(u)} · ${fmtObjId(u.object_id!)}` })),
  ];

  function addSigner(v: string) {
    if (!v) return;
    set({ signers: [...cfg.signers, { signer_object_id: Number(v), action: 'sign' }] });
  }
  function delSigner(i: number) { set({ signers: cfg.signers.filter((_, idx) => idx !== i) }); }
  function setAction(i: number, a: 'confirm' | 'sign') {
    set({ signers: cfg.signers.map((s, idx) => (idx === i ? { ...s, action: a } : s)) });
  }
  function moveSigner(target: number) {
    if (drag === null || drag === target) { setDrag(null); return; }
    const next = [...cfg.signers];
    const [m] = next.splice(drag, 1);
    next.splice(target, 0, m);
    set({ signers: next }); setDrag(null);
  }
  function toggleRole(r: string) {
    set({ roles: cfg.roles.includes(r) ? cfg.roles.filter((x) => x !== r) : [...cfg.roles, r] });
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      {/* Freigabe-Parteien (endlich, gated die Freigabe) */}
      <div>
        <DocLabel text="Wer muss freigeben?"
          hint="Das Dokument gilt erst als freigegeben, wenn ALLE hier genannten Personen unterschrieben bzw. bestätigt haben. Niemand eingetragen = mit «Ausstellen» sofort freigegeben." />
        {cfg.signers.length > 0 && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginBottom: 8 }}>
            {cfg.signers.map((s, i) => (
              <div key={s.signer_object_id}
                onDragOver={(e) => { if (drag !== null) e.preventDefault(); }}
                onDrop={(e) => { e.preventDefault(); moveSigner(i); }}
                style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '7px 9px', borderRadius: 9,
                  border: '1px solid var(--border-1)', background: '#fff', opacity: drag === i ? 0.4 : 1 }}>
                <span draggable onDragStart={() => setDrag(i)} onDragEnd={() => setDrag(null)}
                  title="Reihenfolge ziehen" style={{ cursor: 'grab', color: '#cbd5e1', display: 'flex' }}>
                  <GripVertical size={15} />
                </span>
                <span style={{ font: '700 11px var(--font-body)', color: 'var(--fg-4)', minWidth: 16 }}>{i + 1}.</span>
                <span style={{ flex: 1, font: '600 13px var(--font-body)', color: 'var(--fg-1)', minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {nameOf(s.signer_object_id)}
                </span>
                <Segmented label="" value={s.action}
                  onChange={(v) => setAction(i, v as 'confirm' | 'sign')}
                  options={[{ value: 'confirm', label: 'Bestätigen' }, { value: 'sign', label: 'Unterschreiben' }]} />
                <button type="button" onClick={() => delSigner(i)} title="Entfernen"
                  style={{ border: 'none', background: 'none', color: '#94a3b8', cursor: 'pointer', padding: 3, flexShrink: 0 }}><Trash2 size={14} /></button>
              </div>
            ))}
          </div>
        )}
        {signerOptions.length > 1
          ? <SearchSelect value="" onChange={addSigner} options={signerOptions} placeholder="+ Freigabe-Partei hinzufügen…" />
          : <div style={{ font: '500 12px var(--font-body)', color: 'var(--fg-4)' }}>Keine weiteren Personen verfügbar.</div>}
        {cfg.signers.length >= 2 && (
          <div style={{ marginTop: 8 }}>
            <OptionToggle checked={cfg.sequential} onChange={(v) => set({ sequential: v })}
              label="Nacheinander statt gleichzeitig" />
          </div>
        )}
      </div>

      {/* Sichtbarkeit – Schieber mit Symbolen, Bedeutung im Hover. */}
      <div>
        <DocLabel text="Wer darf es lesen?" />
        <IconSwitch<DocCfg['visibility']> value={cfg.visibility} onChange={(v) => set({ visibility: v })}
          options={[
            { value: 'public', icon: Globe, label: 'Alle', hint: 'Jeder mit Zugang zum Auftrag – auch Kunden und Lieferanten.' },
            { value: 'internal', icon: Building2, label: 'Intern', hint: 'Nur Personal; benannte Parteien sehen es trotzdem.' },
            { value: 'confidential', icon: Lock, label: 'Vertraulich', hint: 'Nur Personal und die benannten Parteien.' },
          ]} />
      </div>

      {/* Anerkennungs-Publikum (offen, blockiert den Auftrag NIE) */}
      <div>
        <DocLabel text="Wer muss es zur Kenntnis nehmen?"
          hint="Nach der Freigabe müssen diese Personen das Dokument aktiv anerkennen (z. B. neue AGB). Das hält den Auftrag NICHT auf – es erscheint bei ihnen als offene Aufgabe." />
        <IconSwitch<'none' | 'all' | 'roles' | 'persons'>
          value={(cfg.audience || 'none') as 'none' | 'all' | 'roles' | 'persons'}
          onChange={(v) => set({ audience: (v === 'none' ? '' : v) as DocCfg['audience'] })}
          options={[
            { value: 'none', icon: Ban, label: 'Niemand', hint: 'Keine Anerkennung nötig.' },
            { value: 'all', icon: UsersIcon, label: 'Alle', hint: 'Jede angemeldete Person.' },
            { value: 'roles', icon: Shield, label: 'Rollen', hint: 'Alle Personen bestimmter Rollen (z. B. alle Lieferanten).' },
            { value: 'persons', icon: UserIcon, label: 'Personen', hint: 'Namentlich ausgewählte Personen.' },
          ]} />
        {cfg.audience === 'roles' && (
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 8 }}>
            {(['customer', 'supplier', 'employee', 'admin'] as const).map((r) => {
              const on = cfg.roles.includes(r);
              return (
                <button key={r} type="button" onClick={() => toggleRole(r)}
                  style={{ display: 'inline-flex', alignItems: 'center', gap: 6, padding: '6px 11px', borderRadius: 'var(--r-pill)', cursor: 'pointer',
                    border: `1px solid ${on ? 'var(--accent)' : 'var(--border-2)'}`, background: on ? 'var(--accent-soft)' : '#fff',
                    font: '600 12.5px var(--font-body)', color: on ? 'var(--accent-ink)' : 'var(--fg-2)' }}>
                  {on && <Check size={13} />} {AUDIENCE_ROLE_LABELS[r]}
                </button>
              );
            })}
          </div>
        )}
        {cfg.audience === 'persons' && (
          <div style={{ marginTop: 8, display: 'flex', flexDirection: 'column', gap: 6 }}>
            {cfg.persons.length > 0 && (
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                {cfg.persons.map((oid) => (
                  <span key={oid} style={{ display: 'inline-flex', alignItems: 'center', gap: 6, padding: '5px 10px', borderRadius: 'var(--r-pill)', background: 'var(--accent-soft)', font: '600 12px var(--font-body)', color: 'var(--accent-ink)' }}>
                    {nameOf(oid)}
                    <button type="button" onClick={() => set({ persons: cfg.persons.filter((x) => x !== oid) })}
                      style={{ border: 'none', background: 'none', color: 'var(--accent-ink)', cursor: 'pointer', display: 'flex', padding: 0 }}><X size={12} /></button>
                  </span>
                ))}
              </div>
            )}
            {personOptions.length > 1 && (
              <SearchSelect value="" onChange={(v) => v && set({ persons: [...cfg.persons, Number(v)] })}
                options={personOptions} placeholder="+ Person hinzufügen…" />
            )}
          </div>
        )}
      </div>
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
  // Eigene Farbfamilie (gedämpftes Pflaume): Datenerfassung und Bewegung trugen exakt
  // dieselbe Tönung – zwei verschiedene Schritttypen sahen damit gleich aus.
  inspection: { bg: '#F7F4FA', border: '#E2DBEC', fg: '#6B5B8A' },
  document:   { bg: 'var(--bg-2)', border: 'var(--border-1)', fg: 'var(--fg-2)' },
  sale:       { bg: '#F0FBF4', border: '#CDEBD6', fg: '#15803D' },
  scrap:      { bg: '#FDF3F2', border: '#F1D6D2', fg: 'var(--danger)' },
  // Sperren: warnend, nicht endgültig – bewusst amber statt dem Rot des Verschrottens.
  block:      { bg: '#FDF8EE', border: '#EFE0C4', fg: 'var(--warning)' },
};
// Begleit-Bewegungen sind normale Schritte und werden darum auch normal eingefärbt –
// die frühere Graufärbung signalisierte «gesperrt» und ist mit der Sperre entfallen.
function kindColor(type: StepType) {
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
