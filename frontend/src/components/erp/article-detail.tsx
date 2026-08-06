'use client';

import { useEffect, useRef, useState } from 'react';
import {
  Package, ArrowLeft, FileText, Workflow, Boxes, Trash2, Tag, QrCode, AlertTriangle,
  Ruler, TrendingUp, Box, Square, Scale, Droplet, Fingerprint, Layers, ExternalLink,
  Scaling, Hash, Truck, Banknote, Link2, Weight, Sparkles, Plus, Shield, Ban, FolderOpen,
  MapPin, ClipboardPlus,
} from 'lucide-react';
import { api } from '@/lib/api';
import type { Article, ArticleInput, ArticleStatus, ArticleUnit, ArticleSerialization, ArticleNameSuggestion, UserProfile, OrdersMode } from '@/types';
import { ARTICLE_NAME_MAX_LENGTH } from '@/types';
import {
  unitLabel, serializationLabel, normalizeSize, normalizeWeight,
  validateName, validateSize, validateWeight,
} from '@/lib/article';
import { articleStatus } from '@/lib/record-status';
import type { StatusAction } from '@/lib/status-flow';
import { useAutosave } from '@/lib/use-autosave';
import { isVersionConflict } from '@/lib/optimistic';

import { ErrorText, SaveIndicator, IconSwitch, StatusBadge, DetailHeader, HeaderAction, HeaderSep, SPEC, ReadField } from '@/components/erp/fields';
import { ProcessSteps } from '@/components/erp/process-steps';
import type { OrderSeed } from '@/components/erp/order-detail';
import { InstanceList } from '@/components/erp/instance-list';
import { SalesPanel } from '@/components/erp/sales-panel';
import { ObjectDocuments } from '@/components/erp/object-documents';
import { DetailTabs } from '@/components/erp/detail-tabs';
import { DeactivateDialog, ReplacedBanner } from '@/components/erp/deactivate-dialog';
import { printObjectLabel } from '@/components/scan/object-label';
import { formatAmount as fmtChf, formatObjectId, localDate } from '@/lib/utils';

// Artikel-Lebenszyklus: Die Freigabe friert den **ganzen Artikel** ein –
// Spezifikation UND Prozess. Sie ist nur möglich, wenn ein Prozess hinterlegt ist
// (sonst „kann" der Artikel nichts). **Inaktiv ist endgültig** – kein Reaktivieren
// (Neustart = neuer Artikel bzw. «Ersetzen»).
function articleActions(status: string, hasProcess: boolean): StatusAction[] {
  if (status === 'draft')
    return [{ label: 'Freigeben', target: 'released', tone: 'primary', disabled: !hasProcess,
      hint: hasProcess ? undefined : 'Erst im Reiter «Prozess» einen Schritt hinterlegen' }];
  // EIN «Deaktivieren»-Knopf – «Ersetzen» (Nachfolger anlegen) ist als Option im Dialog.
  if (status === 'released')
    return [{ label: 'Deaktivieren', target: 'inactive', tone: 'danger' }];
  return [];   // inaktiv → keine Aktionen (endgültig)
}

type TabKey = 'spezifikation' | 'prozess' | 'bestand' | 'verkauf' | 'dokumente';

const TABS: { key: TabKey; label: string; icon: React.ElementType }[] = [
  { key: 'spezifikation', label: 'Spezifikation', icon: FileText },
  { key: 'prozess', label: 'Prozess', icon: Workflow },
  { key: 'bestand', label: 'Bestand', icon: Boxes },
  { key: 'verkauf', label: 'Verkauf', icon: Tag },
  { key: 'dokumente', label: 'Dokumente', icon: FolderOpen },
];

type OptKey = 'material' | 'cad_url' | 'surface' | 'supplier_article_number' | 'min_order_qty' | 'safety_stock' | 'is_hazmat';
// Der frühere «Fixierte Standort» (GPS + Adresse am Artikel) ist ersatzlos entfallen
// (Notiz #168): Ein Artikel ist eine Gattung – einen Ort hat immer nur die Instanz.
type AddKey = OptKey;
type Form = {
  name: string; unit: string; serialization: string; size: string; weight_kg: string;
  material: string; cad_url: string; surface: string; supplier_article_number: string; min_order_qty: string; safety_stock: string;
  is_hazmat: string;
  // Beschaffungsquelle (Spezifikation): Modus + Lieferant (id als String für die Auswahl) / Webshop-Link
  procurement_mode: string; default_supplier_id: string; default_webshop_url: string;
};

// Optionale Stammdaten – dynamische Feldliste (nur bei Bedarf hinzufügen).
//
// **Die Beschriftung nennt die Sache, der Platzhalter erklärt sie** (Notizen #207, #212–#214,
// #216, #217): erklärende Zeilen UNTER einem Feld standen dauerhaft in der Fläche, obwohl
// man sie nur beim ersten Ausfüllen braucht – im Platzhalter sind sie genau dann da.
const OPTIONAL_FIELDS: { key: OptKey; label: string; numeric?: boolean; boolean?: boolean; placeholder: string }[] = [
  { key: 'material', label: 'Material', placeholder: 'z. B. Stahl 1.4301' },
  { key: 'cad_url', label: 'CAD-Link', placeholder: 'Link zur CAD-Datei/Zeichnung – https://…' },
  { key: 'surface', label: 'Oberfläche', placeholder: 'z. B. verzinkt, eloxiert' },
  { key: 'supplier_article_number', label: 'Lief.-Artikelnummer', placeholder: 'Artikelnummer des Lieferanten' },
  { key: 'min_order_qty', label: 'Mindestbestellmenge', numeric: true, placeholder: 'z. B. 50' },
  { key: 'safety_stock', label: 'Sicherheitsbestand', numeric: true, placeholder: 'darunter wird automatisch nachbestellt – z. B. 20' },
  { key: 'is_hazmat', label: 'Gefahrgut', boolean: true, placeholder: '' },
];

function seedFrom(record: Article | null): Form {
  const base = { name: '', unit: 'Stk', serialization: 'unit', size: '', weight_kg: '',
    material: '', cad_url: '', surface: '', supplier_article_number: '', min_order_qty: '', safety_stock: '',
    is_hazmat: '',
    procurement_mode: 'supplier', default_supplier_id: '', default_webshop_url: '' };
  if (!record) return base;
  return {
    ...base,
    name: record.name, unit: record.unit, serialization: record.serialization,
    size: record.size ?? '', weight_kg: record.weight_kg != null ? String(record.weight_kg) : '',
    material: record.material ?? '', cad_url: record.cad_url ?? '', surface: record.surface ?? '',
    supplier_article_number: record.supplier_article_number ?? '',
    min_order_qty: record.min_order_qty != null ? String(record.min_order_qty) : '',
    safety_stock: record.safety_stock != null ? String(record.safety_stock) : '',
    is_hazmat: record.is_hazmat ? 'ja' : '',
    procurement_mode: record.procurement_mode ?? 'supplier',
    default_supplier_id: record.default_supplier_id != null ? String(record.default_supplier_id) : '',
    default_webshop_url: record.default_webshop_url ?? '',
  };
}

// Normalisierte Änderungs-Signatur des Formulars (Autosave-Erkennung). Grösse/Gewicht sind
// optional – leer bleibt leer (kein Fehl-Autosave beim Öffnen eines Artikels ohne diese Werte).
function signatureOf(form: Form): string {
  return JSON.stringify({
    name: form.name.trim(), unit: form.unit, serialization: form.serialization,
    size: form.size.trim() ? normalizeSize(form.size) : '',
    weight_kg: form.weight_kg.trim() ? normalizeWeight(form.weight_kg) : '',
    material: form.material.trim(), cad_url: form.cad_url.trim(), surface: form.surface.trim(),
    supplier_article_number: form.supplier_article_number.trim(),
    min_order_qty: form.min_order_qty.trim(), safety_stock: form.safety_stock.trim(),
    procurement_mode: form.procurement_mode,
    default_supplier_id: form.procurement_mode === 'supplier' ? form.default_supplier_id : '',
    default_webshop_url: form.procurement_mode === 'webshop' ? form.default_webshop_url.trim() : '',
  });
}

// Vorübergehender Transportfehler (Server nicht erreichbar / Kaltstart) vs.
// fachlicher Fehler. Der API-Client wiederholt solche Anfragen bereits mehrfach;
// schlägt es danach noch fehl, bekommt der Nutzer einen Wiederhol-Hinweis.
function isTransient(msg: string): boolean {
  return /keine verbindung|server nicht erreichbar|netzwerkfehler|failed to fetch|networkerror|load failed/i.test(msg);
}

export function ArticleDetail({ record, suppliers = [], onSaved, onCancel, onBack, onRefresh, onCreateOrder }: {
  record: Article | null;          // null ⇒ Anlage-Modus
  suppliers?: UserProfile[];
  onSaved: (a: Article) => void;
  onCancel: () => void;
  onBack: () => void;
  onRefresh?: () => void;          // Feed nach Inaktiv/Ersetzen aktualisieren (Kaskade)
  /** Anlage-Fenster mit diesem Artikel vorgewählt öffnen (der Auftrag entsteht erst mit
   *  der Freigabe, #386). */
  onCreateOrder?: (seed: OrderSeed) => void;
}) {
  const isCreate = record === null;
  const [tab, setTab] = useState<TabKey>('spezifikation');
  const [dialog, setDialog] = useState<'deactivate' | null>(null);

  // Shortcut «Auftrag»: das Anlage-Fenster mit diesem Artikel vorgewählt öffnen. Es
  // entsteht dabei **kein** Datensatz – einen Auftrag gibt es erst mit der Freigabe
  // (Testnotiz #386).
  //
  // **Vorgemerkt wird nur der Artikel** – wie an der Instanz nur die Instanz (#608): der
  // Knopf sagt, WORUM es geht; wie viel, woher und mit welchem Ablauf ist die Entscheidung,
  // und die trifft der Mensch. Eine vorausgefüllte «1» wäre eine Behauptung, die in den
  // meisten Fällen falsch ist und trotzdem freigebbar aussieht.
  function createOrderShortcut() {
    if (isCreate || record == null || record.status !== 'released') return;
    onCreateOrder?.({ articleId: record.id });
  }
  // Optimistic Locking: zuletzt bekannter Stand; wird nach jedem Speichern aktualisiert.
  const verRef = useRef<string | null>(record?.updated_at ?? null);
  const [form, setForm] = useState<Form>(() => seedFrom(record));
  const [savedSig, setSavedSig] = useState<string>(() => (isCreate ? '' : signatureOf(seedFrom(record))));
  const [saving, setSaving] = useState(false);
  const [flash, setFlash] = useState(false);
  const [statusBusy, setStatusBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // Prozessschritt-Anzahl (für die Freigabe-Bedingung) – tab-unabhängig vorgeladen,
  // im Prozess-Reiter live über onStepsCount aktualisiert.
  const [stepsCount, setStepsCount] = useState<number | null>(null);
  useEffect(() => {
    if (isCreate || record?.object_id == null) { setStepsCount(0); return; }
    api.getSteps('articles', record.object_id).then((s) => setStepsCount(s.length)).catch(() => {});
  }, [isCreate, record?.object_id]);
  // Welche optionalen Felder werden angezeigt (mit Wert oder bewusst hinzugefügt)
  const [added, setAdded] = useState<AddKey[]>(() => {
    const s = seedFrom(record);
    return OPTIONAL_FIELDS.filter((f) => s[f.key].trim() !== '').map((f) => f.key);
  });

  function set<K extends keyof Form>(key: K, value: Form[K]) {
    setForm((p) => ({ ...p, [key]: value }));
  }

  function addField(key: AddKey) { setAdded((a) => (a.includes(key) ? a : [...a, key])); }
  function removeField(key: AddKey) {
    setAdded((a) => a.filter((k) => k !== key));
    set(key, '');
  }

  // Nach der Freigabe ist der Artikel schreibgeschützt (keine Versionierung).
  const locked = !isCreate && record !== null && record.status !== 'draft';

  // Gewicht wird read-only, sobald der Artikel verbaute Ressourcen hat: es ergibt
  // sich dann automatisch aus der Stückliste (über mehrere Ebenen, Backend).
  const computedWeight = record?.computed_weight_kg ?? null;
  const weightIsComputed = !isCreate && computedWeight != null;

  // Pflichtfelder: Name, Mengeneinheit, Serialisierung, Grösse und Gewicht (Einheit/
  // Serialisierung tragen einen Default). Format-Fehler nur zeigen, wenn befüllt (nicht
  // aggressiv beim leeren Neuformular); die «leer»-Pflicht steuert das `valid`-Gate.
  const errs = {
    name: validateName(form.name),
    size: form.size.trim() ? validateSize(form.size) : null,
    weight: form.weight_kg.trim() ? validateWeight(form.weight_kg) : null,
  };
  const missingCore = !form.name.trim() || !form.size.trim() || (!weightIsComputed && !form.weight_kg.trim());
  const valid = !errs.name && !errs.size && !errs.weight && !missingCore;

  // Konkreter, handlungsleitender Grund, warum (noch) nicht gespeichert wird.
  const blockReason: string | null = valid ? null
    : (!form.name.trim() ? 'Bitte einen Artikelnamen eingeben.'
      : !form.size.trim() ? 'Bitte die Abmessungen angeben (Pflichtfeld).'
      : (!weightIsComputed && !form.weight_kg.trim()) ? 'Bitte das Gewicht angeben (Pflichtfeld).'
      : errs.name || errs.size || errs.weight || 'Pflichtfelder ausfüllen: Name, Grösse, Gewicht');

  const sig = signatureOf(form);
  const canSave = !locked && valid && sig !== savedSig && !saving;

  // Bei Versions-Konflikt frischen Stand laden (Version aktualisieren, Feed melden).
  async function resyncVersion() {
    if (!record) return;
    try {
      const fresh = await api.getArticle(record.object_id as number);
      verRef.current = fresh.updated_at;
      onSaved(fresh);
    } catch { /* ignore */ }
  }

  async function changeStatus(target: string) {
    if (!record) return;
    setStatusBusy(true);
    setError(null);
    try {
      const saved = await api.updateArticle(record.object_id as number,
        { status: target as ArticleStatus, expected_updated_at: verRef.current });
      verRef.current = saved.updated_at;
      onSaved(saved);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Statuswechsel fehlgeschlagen');
      if (isVersionConflict(e)) await resyncVersion();
    } finally {
      setStatusBusy(false);
    }
  }

  // Deaktivieren läuft über den Dialog (Wirkungsanalyse + Auftrags-Wahl + optional Nachfolger).
  function onStatusAction(target: string) {
    if (target === 'inactive') { setDialog('deactivate'); return; }
    changeStatus(target);   // Freigeben / Reaktivieren
  }

  // EIN kombinierter Knopf: optional einen Nachfolger anlegen («Ersetzen») oder nur deaktivieren.
  async function confirmDeactivate(ordersMode: OrdersMode, createSuccessor: boolean) {
    if (!record) return;
    const result = createSuccessor
      ? await api.replaceArticle(record.object_id as number, ordersMode)   // Nachfolger + inaktiv
      : await api.deactivateArticle(record.object_id as number, ordersMode);
    setDialog(null); onRefresh?.(); onSaved(result);   // bei Nachfolger: navigiert zum neuen Artikel
  }

  async function save() {
    if (!valid) return;
    const current = sig;
    setSaving(true);
    setError(null);
    try {
      // Grösse/Gewicht sind optional – leer ⇒ null (z. B. bei einem Dokument-Artikel).
      const payload: ArticleInput = {
        name: form.name.trim(),
        unit: form.unit as ArticleUnit,
        serialization: form.serialization as ArticleSerialization,
        size: form.size.trim() ? normalizeSize(form.size) : null,
        weight_kg: form.weight_kg.trim() ? normalizeWeight(form.weight_kg) : null,
        material: form.material.trim() || null,
        cad_url: form.cad_url.trim() || null,
        surface: form.surface.trim() || null,
        supplier_article_number: form.supplier_article_number.trim() || null,
        min_order_qty: form.min_order_qty.trim() || null,
        safety_stock: form.safety_stock.trim() || null,
        is_hazmat: form.is_hazmat === 'ja',
        // Beschaffungsquelle: nur das zum Modus passende Quellfeld senden (Backend spiegelt das).
        procurement_mode: (form.procurement_mode as 'supplier' | 'webshop') || 'supplier',
        default_supplier_id: form.procurement_mode === 'supplier' && form.default_supplier_id
          ? Number(form.default_supplier_id) : null,
        default_webshop_url: form.procurement_mode === 'webshop'
          ? (form.default_webshop_url.trim() || null) : null,
      };
      if (isCreate) {
        onSaved(await api.createArticle(payload));
      } else {
        const saved = await api.updateArticle(record.object_id as number,
          { ...payload, expected_updated_at: verRef.current });
        verRef.current = saved.updated_at;
        onSaved(saved);
        setSavedSig(current);
        setFlash(true);
        setTimeout(() => setFlash(false), 700);
      }
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Fehler beim Speichern';
      // useAutosave wiederholt einen fehlgeschlagenen Stand NICHT automatisch
      // (kein Loop) – Hinweis: Änderung oder Enter löst einen neuen Versuch aus.
      setError(isTransient(msg) ? `${msg} – mit Enter erneut versuchen.` : msg);
      if (!isCreate && isVersionConflict(e)) await resyncVersion();
    } finally {
      setSaving(false);
    }
  }

  const flush = useAutosave(sig, canSave, save);

  const statusCfg = articleStatus({ status: isCreate || !record ? 'draft' : record.status });
  const actions = isCreate || !record ? [] : articleActions(record.status, (stepsCount ?? 0) > 0);

  return (
    <div className="flex flex-col h-full bg-bg-1">
      {/* Kopf – die EINE Anatomie aller Datensatz-Fenster (`DetailHeader`, Notiz #242). */}
      <DetailHeader
        icon={Package} iconBg="#F4EBDD" iconFg="#9A7238"
        eyebrow="Artikel" title={form.name || null} placeholder="Neuer Artikel"
        objectId={isCreate ? null : record.object_id}
        objectIdText={isCreate ? 'wird vergeben' : undefined}
        onBack={onBack}
        status={statusCfg}
        right={<SaveIndicator saving={saving} flash={flash} />}
        actions={!isCreate && record.object_id != null ? (
          <>
            <HeaderSep />
            <button className="erp-idbtn" data-tip="Etikett drucken (QR)" data-tip-pos="bottom" aria-label="Etikett drucken"
              onClick={() => printObjectLabel(record.object_id as number, form.name || record.name, 'Artikel')}>
              <QrCode size={15} />
            </button>
            {/* Shortcut «Auftrag»: aus dem freigegebenen Artikel direkt einen Auftrag
                auslösen (nur freigegebene Artikel sind auftragsfähig). */}
            {record.status === 'released' && (
              <button className="erp-idbtn erp-idbtn-act" data-tip="Auftrag" data-tip-pos="bottom"
                aria-label="Auftrag zu diesem Artikel anlegen"
                onClick={createOrderShortcut}>
                <ClipboardPlus size={15} />
              </button>
            )}
            {/* Deaktivieren/Ersetzen als kleines Symbol neben der Objektnummer. */}
            {record.status === 'released' && (
              <button className="erp-idbtn erp-idbtn-danger" data-tip="Deaktivieren / ersetzen" data-tip-pos="bottom"
                aria-label="Artikel deaktivieren oder ersetzen" disabled={statusBusy}
                onClick={() => onStatusAction('inactive')}>
                <Ban size={15} />
              </button>
            )}
            {/* Status-Aktion («Freigeben») bei den übrigen Objekt-Aktionen – genau wie
                am Auftrag (#167): rechts steht nur der Zustand. */}
            {actions.some((a) => a.tone !== 'danger') && (
              <>
                <HeaderSep />
                {actions.filter((a) => a.tone !== 'danger').map((a) => (
                  <HeaderAction key={a.target} label={a.label} tone={a.tone} hint={a.hint}
                    disabled={statusBusy || a.disabled} onClick={() => onStatusAction(a.target)} />
                ))}
              </>
            )}
          </>
        ) : undefined}
        tabs={<DetailTabs<TabKey> active={tab} onChange={setTab} tabs={TABS} />}
      >
        {!isCreate && (record.replaced_by_id != null || record.replaces_id != null) && (
          <ReplacedBanner replacedBy={record.replaced_by_id ?? null} replaces={record.replaces_id ?? null} />
        )}
      </DetailHeader>

      {/* Content */}
      {/* FIX: Enter im Container löst den Autosave-Flush aus – in TEXTAREAs (mehrzeilige
          Beschreibungen/Bild-URLs/Notizen) verschluckte preventDefault() aber jeden
          Zeilenumbruch. Textareas ausnehmen. */}
      <div onKeyDown={(e) => { if (e.key === 'Enter' && (e.target as HTMLElement).tagName !== 'TEXTAREA') { e.preventDefault(); flush(); } }}
        style={{ flex: 1, overflowY: 'auto', padding: '24px clamp(14px, 4vw, 28px) 88px', background: 'var(--bg-2)', boxShadow: flash ? 'inset 0 0 0 2px var(--success)' : 'none', transition: 'box-shadow 0.2s' }}>
        {tab === 'spezifikation' && (
          <div style={{ maxWidth: 880, marginInline: 'auto', width: '100%' }}>
            {locked ? (
              <SpecRead record={record!} form={form} weightIsComputed={weightIsComputed} computedWeight={computedWeight} />
            ) : (
              <div style={SPEC.card}>
                {/* Karten-Kopf «Spezifikation» + «+»-Knopf (nur Entwurf) für optionale Felder. */}
                <CardHead right={<SectionAddButton added={added} onAdd={addField} />} />
                {/* Standardmässig NUR die Pflichtfelder (Name, Mengeneinheit, Serialisierung,
                    Grösse, Gewicht) – Name über volle Breite, dann zwei gepaarte Zeilen. ALLE
                    weiteren Felder sind ausgeblendet und werden über den «+»-Knopf ergänzt. */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: 22 }}>
                  <NameField value={form.name} onChange={(v) => set('name', v)}
                    error={form.name.trim() ? errs.name : null} />
                  <div style={GRID2}>
                    <IconPick label="Mengeneinheit" required value={form.unit} onChange={(v) => set('unit', v)} options={UNIT_PICK} />
                    <IconPick label="Serialisierung" required value={form.serialization} onChange={(v) => set('serialization', v)} options={SERIAL_PICK} />
                  </div>
                  <div style={GRID2}>
                    <EditField label="Abmessungen (mm)" required value={form.size} onChange={(v) => set('size', v)} placeholder="z. B. 3x40x600" error={form.size ? errs.size : null} />
                    {weightIsComputed ? (
                      <ReadField icon={Weight} label="Gewicht" value={fmtWeight(computedWeight!)} unit="kg" autoHint="Automatisch aus der Stückliste berechnet" mono />
                    ) : (
                      <EditField label="Gewicht (kg)" required value={form.weight_kg} onChange={(v) => set('weight_kg', v)} placeholder="z. B. 2.5" error={form.weight_kg ? errs.weight : null} />
                    )}
                  </div>
                  {/* Bei Bedarf hinzugefügte optionale Felder + abgeleitete Auto-Werte (nur wenn vorhanden). */}
                  {(added.length > 0 || (!isCreate && (record!.lead_time_days_low != null || record!.landed_unit_cost != null))) && (
                    <div style={SPEC.grid}>
                      {OPTIONAL_FIELDS.filter((f) => added.includes(f.key)).map((f) => (
                        <OptField key={f.key} f={f} form={form} onSet={set} onRemove={removeField} />
                      ))}
                      {!isCreate && record!.lead_time_days_low != null && (
                        <ReadField icon={Truck} label="Lieferzeit" value={leadValue(record!)} spread={leadSpread(record!)}
                          autoHint="Median aus erledigten Aufträgen" />
                      )}
                      {!isCreate && costValue(record!) != null && (
                        <ReadField icon={Banknote} label="EK-Preis" value={costValue(record!)} unit="CHF" spread={costSpread(record!)}
                          autoHint="Median aus bisherigen Bestellungen" mono />
                      )}
                    </div>
                  )}
                </div>
                {/* **Kein Footer** (Testnotiz #653, wie #140 am Auftrag). Der Hinweis, warum
                    noch nicht gespeichert wird, gehört leise in die Karte, auf die er sich
                    bezieht – nicht als Leiste an den Fensterrand. Ein echter Fehler steht in
                    der Warnfarbe; der Speicher-Status ist ohnehin der grüne Flash im Kopf,
                    und verworfen wird durch Wegklicken (Notiz #389). */}
                {(error || blockReason) && (
                  <div style={{ font: '500 12.5px var(--font-body)',
                    color: error ? 'var(--danger)' : 'var(--fg-4)' }}>
                    {error ?? blockReason}
                  </div>
                )}
              </div>
            )}
          </div>
        )}
        {tab === 'prozess' && (
          <ProcessSteps owner="articles" ownerObjectId={record?.object_id ?? null} suppliers={suppliers}
            readOnly={record?.status !== 'draft'} selfArticleObjectId={record?.object_id ?? null}
            onStepsCount={setStepsCount} />
        )}
        {tab === 'bestand' && (
          <InstanceList articleObjectId={record?.object_id ?? null} unit={record ? unitLabel(record.unit) : undefined} />
        )}
        {tab === 'verkauf' && (
          <SalesPanel articleObjectId={record?.object_id ?? null} />
        )}
        {tab === 'dokumente' && (
          <ObjectDocuments objectId={record?.object_id ?? null} contextLabel="diesem Artikel" />
        )}
      </div>

      {dialog && record && (
        <DeactivateDialog
          mode="deactivate"
          articleObjectId={record.object_id}
          title="Artikel deaktivieren"
          offerSuccessor
          confirmLabel="Deaktivieren"
          onConfirm={confirmDeactivate}
          onClose={() => setDialog(null)}
        />
      )}
    </div>
  );
}

// Kopf-/Chrome-Styles (Inexxio Design System, analog Instanz-Detail)
// Der Kopf kommt aus `fields.DetailHeader` (Notiz #242) – hier bleibt nur die Karte.
const H: Record<string, React.CSSProperties> = {
  card: { background: '#fff', border: '1px solid var(--border-1)', borderRadius: 'var(--r-lg)', padding: 'clamp(16px, 3vw, 24px)', display: 'flex', flexDirection: 'column', gap: 16, width: '100%' },
};

function fmtWeight(v: string | number): string {
  return Number(v).toLocaleString('de-CH', { maximumFractionDigits: 3 });
}

// Freies Namensfeld mit intelligenten Vorschlägen: das System schlägt beim Tippen bereits
// verwendete/ähnliche Namen vor (kostenlos/lexikalisch, `services/article_names.py`), damit
// keine Dubletten («Schraubendreher» vs. «Akkuschrauber») entstehen. Kein Katalog-Zwang mehr.
function NameField({ value, onChange, error }: {
  value: string; onChange: (v: string) => void; error?: string | null;
}) {
  const [open, setOpen] = useState(false);
  const [sugs, setSugs] = useState<ArticleNameSuggestion[]>([]);
  const boxRef = useRef<HTMLDivElement>(null);

  // Vorschläge entprellt laden, solange das Feld aktiv ist (leere Eingabe → häufigste Namen).
  useEffect(() => {
    if (!open) return;
    let stale = false;
    const t = setTimeout(() => {
      api.articleNameSuggestions(value.trim(), 8)
        .then((r) => { if (!stale) setSugs(r); })
        .catch(() => { if (!stale) setSugs([]); });
    }, 200);
    return () => { stale = true; clearTimeout(t); };
  }, [value, open]);

  // Klick ausserhalb schliesst die Vorschlagsliste.
  useEffect(() => {
    function onDoc(e: MouseEvent) {
      if (boxRef.current && !boxRef.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener('mousedown', onDoc);
    return () => document.removeEventListener('mousedown', onDoc);
  }, []);

  const q = value.trim().toLowerCase();
  const exact = sugs.find((s) => s.name.toLowerCase() === q && s.count > 0);
  const list = sugs.filter((s) => s.name.toLowerCase() !== q);

  return (
    <div ref={boxRef} style={{ position: 'relative' }}>
      <FieldLabel required>Name</FieldLabel>
      <input
        value={value}
        maxLength={ARTICLE_NAME_MAX_LENGTH}
        placeholder="Artikelname eingeben…"
        onChange={(e) => { onChange(e.target.value); setOpen(true); }}
        onFocus={() => setOpen(true)}
        className={FIN_CLS}
        style={error ? { borderColor: '#fca5a5' } : undefined}
      />
      {error ? <ErrorText msg={error} /> : exact ? (
        <div style={{ marginTop: 4, fontSize: 11, color: 'var(--warning)', display: 'flex', alignItems: 'center', gap: 4 }}>
          <AlertTriangle size={11} /> Ein Artikel mit diesem Namen besteht bereits ({exact.count}×) – ggf. wiederverwenden.
        </div>
      ) : null}
      {open && list.length > 0 && (
        <div className="absolute left-0 right-0 z-30 mt-1 max-h-60 overflow-y-auto rounded-ds-md border border-border-1 bg-bg-1 py-1 shadow-ds-md">
          {list.map((s) => (
            <button
              key={s.name}
              type="button"
              onMouseDown={(e) => e.preventDefault()}   // Blur vor Klick verhindern
              onClick={() => { onChange(s.name); setOpen(false); }}
              className="flex w-full items-center justify-between gap-2 px-3 py-1.5 text-left text-sm text-fg-2 hover:bg-bg-2"
            >
              <span className="truncate">{s.name}</span>
              <span style={{ flex: 'none', fontSize: 10.5, fontWeight: 600, color: s.count > 0 ? 'var(--warning)' : 'var(--fg-4)' }}>
                {s.count > 0 ? `${s.count}× vorhanden` : 'ähnlich'}
              </span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

// Read-only Gewicht (aus der Stückliste berechnet) – analog Preis-/Durchlaufzeit-Spanne.

// ─── Spezifikation: sektionierte Ansicht (Design-Redesign) ────────────────────
// Symbol-Auswahl je Einheit/Serialisierung (statt Dropdown/Segmented) – «Symbol + Wort».
const UNIT_PICK = [
  { value: 'Stk', label: 'Stk.', icon: Package },
  { value: 'mm', label: 'mm', icon: Ruler },
  { value: 'm2', label: 'm²', icon: Square },
  { value: 'm3', label: 'm³', icon: Box },
  { value: 'kg', label: 'kg', icon: Scale },
  { value: 'l', label: 'l', icon: Droplet },
];
const SERIAL_PICK = [
  { value: 'unit', label: 'Einzelteil', icon: Fingerprint },
  { value: 'batch', label: 'Charge', icon: Layers },
];
// Design `.grid2`: Zwei-Spalten-Raster für gepaarte Eingaben (Einheit/Serialisierung,
// Abmessungen/Gewicht) – kollabiert auf Mobile auf eine Spalte.
const GRID2: React.CSSProperties = {
  display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 260px), 1fr))', gap: '22px 40px',
};

// Karten-Kopf (Design `.card-h`): grosses getöntes Symbol + Titel «Spezifikation» +
// optionaler rechter Slot («+ Feld hinzufügen», nur im Entwurf). Keine Haarlinie – die
// Trennlinien tragen erst die Lese-Unterabschnitte.
function CardHead({ right }: { right?: React.ReactNode }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 24 }}>
      <span style={{ width: 34, height: 34, borderRadius: 'var(--r-sm)', background: '#F4EBDD', color: '#9A7238', display: 'flex', alignItems: 'center', justifyContent: 'center', flex: 'none' }}>
        <FileText size={17} />
      </span>
      <h2 style={{ font: '800 18px var(--font-display)', letterSpacing: '-.01em', margin: 0, flex: 1, color: 'var(--fg-1)' }}>Spezifikation</h2>
      {right && <span style={{ flex: 'none' }}>{right}</span>}
    </div>
  );
}

// Lese-Unterabschnitt (Design `.rsec` + `.rsec-h`): 32-px-Symbol + Titel (h3) über einer
// Haarlinie, darunter das Werte-Raster. Gliedert die freigegebene Spezifikation.
function SubSection({ icon: Icon, title, children }: {
  icon: React.ElementType; title: string; children: React.ReactNode;
}) {
  return (
    <div style={{ marginBottom: 8 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 11, paddingBottom: 14, margin: '18px 0 20px', borderBottom: '1px solid var(--border-1)' }}>
        <span style={{ width: 32, height: 32, borderRadius: 'var(--r-sm)', background: '#F4EBDD', color: '#9A7238', display: 'flex', alignItems: 'center', justifyContent: 'center', flex: 'none' }}>
          <Icon size={16} />
        </span>
        <h3 style={{ font: '800 16px var(--font-display)', letterSpacing: '-.01em', margin: 0, color: 'var(--fg-1)' }}>{title}</h3>
      </div>
      <div style={SPEC.grid}>{children}</div>
    </div>
  );
}

// Add-Menü: die optionalen Text-/Mengenfelder. EIN Menü im Sektions-Kopf bietet alle noch
// nicht sichtbaren Felder an.
const ADD_MENU: { key: AddKey; label: string }[] =
  OPTIONAL_FIELDS.map((f) => ({ key: f.key as AddKey, label: f.label }));

// «Feld hinzufügen» als kleines +-Symbol (Hover-Tooltip) im Sektions-Kopf → Dropdown der
// noch nicht sichtbaren optionalen Felder DIESER Sektion. Kein eigener «Zusätzliche»-Bereich.
function SectionAddButton({ added, onAdd }: {
  added: AddKey[]; onAdd: (k: AddKey) => void;
}) {
  const [open, setOpen] = useState(false);
  const boxRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    function h(e: MouseEvent) { if (boxRef.current && !boxRef.current.contains(e.target as Node)) setOpen(false); }
    document.addEventListener('mousedown', h);
    return () => document.removeEventListener('mousedown', h);
  }, []);
  const available = ADD_MENU.filter((f) => !added.includes(f.key));
  if (available.length === 0) return null;
  return (
    <div ref={boxRef} style={{ position: 'relative' }}>
      <button type="button" onClick={() => setOpen((o) => !o)} data-tip="Feld hinzufügen" data-tip-pos="left"
        aria-label="Feld hinzufügen"
        style={{ width: 28, height: 28, borderRadius: 'var(--r-sm)', border: '1px solid var(--border-2)', background: '#fff', color: 'var(--accent)', display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer' }}>
        <Plus size={16} />
      </button>
      {open && (
        <div style={{ position: 'absolute', top: 'calc(100% + 8px)', right: 0, zIndex: 30, width: 320, maxWidth: '80vw', background: '#fff', border: '1px solid var(--border-1)', borderRadius: 'var(--r-md)', boxShadow: 'var(--shadow-lg)', padding: 7, display: 'flex', flexDirection: 'column', gap: 2 }}>
          {available.map((f) => {
            const Icon = MENU_ICON[f.key] ?? Layers;
            return (
              <button key={f.key} type="button" onClick={() => { onAdd(f.key); setOpen(false); }}
                style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '9px 11px', border: 'none', background: 'transparent', borderRadius: 'var(--r-sm)', cursor: 'pointer', textAlign: 'left' }}
                onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.background = 'var(--bg-2)'; }}
                onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.background = 'transparent'; }}>
                <span style={{ width: 32, height: 32, borderRadius: 'var(--r-sm)', background: 'var(--bg-2)', color: 'var(--fg-2)', display: 'flex', alignItems: 'center', justifyContent: 'center', flex: 'none' }}>
                  <Icon size={16} />
                </span>
                <span style={{ minWidth: 0, font: '700 13.5px var(--font-body)', color: 'var(--fg-1)' }}>{f.label}</span>
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}

// Ein optionales Feld als Eingabe (in seiner Sektion) mit Entfernen-Symbol.
function OptField({ f, form, onSet, onRemove }: {
  f: typeof OPTIONAL_FIELDS[number]; form: Form; onSet: (k: OptKey, v: string) => void; onRemove: (k: OptKey) => void;
}) {
  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <FieldLabel>{f.label}</FieldLabel>
        <button type="button" onClick={() => onRemove(f.key)} title="Feld entfernen"
          style={{ border: 'none', background: 'none', color: 'var(--fg-4)', cursor: 'pointer', padding: 0, marginBottom: 6 }}>
          <Trash2 size={13} />
        </button>
      </div>
      {f.boolean ? (
        <select value={form[f.key] === 'ja' ? 'ja' : ''} onChange={(e) => onSet(f.key, e.target.value)} className={FIN_CLS}>
          <option value="">Nein</option>
          <option value="ja">Ja</option>
        </select>
      ) : (
        <input value={form[f.key]} placeholder={f.placeholder} onChange={(e) => onSet(f.key, e.target.value)} className={FIN_CLS} />
      )}
    </div>
  );
}

// Eingabefeld-Klasse analog Design-`.fin` (Rand border-2, r-md, 14/12-Padding, Akzent-Fokus mit 3-px-Ring).
const FIN_CLS = 'w-full rounded-ds-md border border-border-2 bg-white px-3.5 py-3 text-[15px] font-medium text-fg-1 outline-none placeholder:text-fg-4 focus:border-accent focus:ring-[3px] focus:ring-accent-soft';

// Feld-Label (Design `.lbl`): Versalien, enges Tracking, gedämpftes Grau; Pflicht-Stern in
// Marken-Rot. Lokal in der Spezifikation verwendet (das geteilte `Label` bleibt unangetastet).
function FieldLabel({ children, required }: { children: React.ReactNode; required?: boolean }) {
  return (
    <label style={{ display: 'block', font: '700 11px var(--font-body)', textTransform: 'uppercase', letterSpacing: '.07em', color: 'var(--fg-3)', marginBottom: 9 }}>
      {children}{required && <span style={{ color: 'var(--inexxio-red)' }}> *</span>}
    </label>
  );
}

// ── Abgeleitete Kennzahlen: der MEDIAN trägt die Aussage ────────────────────────
// Ein einzelner Eil-Auftrag oder eine Kleinstmenge zu Apothekerpreisen zieht einen
// Mittelwert weg – der Median bleibt bei dem, was üblich ist (Backend:
// `services/metrics.py`). Die Spanne steht untergeordnet daneben und nur dann, wenn
// sie etwas Neues sagt (bei einem einzigen Datenpunkt fällt sie mit dem Median zusammen).

function leadValue(r: Article): string {
  const v = r.lead_time_days_median ?? r.lead_time_days_low;
  return v == null ? '—' : formatDuration(Number(v));
}

function leadSpread(r: Article): string | undefined {
  const lo = r.lead_time_days_low; const hi = r.lead_time_days_high;
  if (lo == null || hi == null || Number(lo) === Number(hi)) return undefined;
  return `kürzeste ${formatDuration(Number(lo))} · längste ${formatDuration(Number(hi))}`;
}

function costValue(r: Article): string | null {
  const v = r.unit_cost_median ?? r.landed_unit_cost;
  return v == null ? null : fmtChf(v);
}

function costSpread(r: Article): string | undefined {
  const lo = r.unit_cost_low; const hi = r.unit_cost_high;
  if (lo == null || hi == null || Number(lo) === Number(hi)) return undefined;
  return `tiefster ${fmtChf(lo)} · höchster ${fmtChf(hi)} CHF`;
}

// Eingabe-Feld (Entwurf): Overline-Label + `.fin`-Input + Fehler/Hinweis.
function EditField({ label, value, onChange, placeholder, hint, error, required, full }: {
  label: string; value: string; onChange: (v: string) => void;
  placeholder?: string; hint?: string; error?: string | null; required?: boolean; full?: boolean;
}) {
  return (
    <div style={{ gridColumn: full ? '1 / -1' : undefined }}>
      <FieldLabel required={required}>{label}</FieldLabel>
      <input value={value} placeholder={placeholder} onChange={(e) => onChange(e.target.value)}
        className={FIN_CLS} style={error ? { borderColor: '#fca5a5' } : undefined} />
      {error ? <ErrorText msg={error} /> : hint ? (
        <div style={{ marginTop: 8, font: '500 12.5px var(--font-body)', color: 'var(--fg-4)' }}>{hint}</div>
      ) : null}
    </div>
  );
}

/**
 * **Schieberegler** für die beiden Achsen der Spezifikation (Mengeneinheit, Serialisierung).
 *
 * Dass die Optionen einander ausschliessen, zeigt die Bewegung des Reiters – nicht eine
 * Reihe gleich aussehender Pillen. Und nur die **aktive** Option trägt ihr Wort (Notizen
 * #219/#220): bei sechs Einheiten ringen sonst sechs Wörter nebeneinander um Aufmerksamkeit,
 * obwohl nur eines gilt. Die übrigen bleiben Symbol – ihr Name kommt im Hover.
 */
function IconPick({ label, value, onChange, options, required }: {
  label: string; value: string; onChange: (v: string) => void; required?: boolean;
  options: { value: string; label: string; icon: React.ElementType }[];
}) {
  return (
    <div>
      <FieldLabel required={required}>{label}</FieldLabel>
      <IconSwitch labelActiveOnly value={value} onChange={onChange}
        options={options.map((o) => ({ value: o.value, icon: o.icon, label: o.label }))} />
    </div>
  );
}

// Read-only-Spezifikation (freigegebener Artikel) – in Sektionen gegliedert.
function SpecRead({ record, form, weightIsComputed, computedWeight }: {
  record: Article; form: Form; weightIsComputed: boolean; computedWeight: string | number | null;
}) {
  const has = (k: OptKey) => form[k].trim() !== '';
  const hasPhysical = !!record.size || weightIsComputed || record.weight_kg != null;
  // KEIN Abschnitt «Beschaffung» mehr: WIE beschafft wird (Quelle, Lieferant, Webshop),
  // steht ausschliesslich am Beschaffungs-Schritt im Reiter «Prozess» – eine Überschrift
  // hier las sich, als würde es auch an zwei Stellen gepflegt. Was bleibt, sind zwei
  // ehrlich getrennte Dinge: **abgeleitete Kennzahlen** (aus der Historie gerechnet) und
  // die restlichen optionalen Angaben, die zur Spezifikation selbst gehören.
  const hasMetrics = record.lead_time_days_low != null || costValue(record) != null;
  return (
    <div style={SPEC.card}>
      {/* Karten-Kopf «Spezifikation» (ohne «+»-Knopf – freigegeben ist read-only). */}
      <CardHead />
      {/* Basis-Gruppe ohne eigenen Unter-Kopf – der Karten-Kopf trägt sie (Design `.rsec` #1). */}
      <div style={{ marginBottom: 8 }}>
        <div style={{ ...SPEC.grid, paddingTop: 2 }}>
          <ReadField icon={Tag} label="Artikelname" value={record.name} full />
          <ReadField icon={Ruler} label="Mengeneinheit" value={unitLabel(record.unit)} />
          <ReadField icon={Fingerprint} label="Serialisierung" value={serializationLabel(record.serialization)} />
          {has('surface') && <ReadField icon={Sparkles} label="Oberfläche" value={form.surface} />}
          {has('material') && <ReadField icon={Layers} label="Material" value={form.material} />}
          {has('supplier_article_number') && <ReadField icon={Hash} label="Bestellnummer" value={form.supplier_article_number} />}
          {has('min_order_qty') && <ReadField icon={Package} label="Mindestbestellmenge" value={form.min_order_qty} mono />}
          {has('safety_stock') && <ReadField icon={Shield} label="Sicherheitsbestand" value={form.safety_stock} mono />}
          {has('cad_url') && <ReadField icon={Link2} label="CAD-Link" link={form.cad_url} full />}
        </div>
      </div>
      {hasPhysical && (
        <SubSection icon={Box} title="Physische Eigenschaften">
          {record.size && <ReadField icon={Scaling} label="Abmessungen" value={record.size} unit="mm" mono />}
          {(weightIsComputed || record.weight_kg != null) && (
            <ReadField icon={Weight} label="Gewicht" value={weightIsComputed ? fmtWeight(computedWeight!) : String(record.weight_kg)}
              unit={weightIsComputed ? 'kg (berechnet)' : 'kg'} mono />
          )}
        </SubSection>
      )}
      {hasMetrics && (
        <SubSection icon={TrendingUp} title="Kennzahlen">
          {record.lead_time_days_low != null && (
            <ReadField icon={Truck} label="Lieferzeit" value={leadValue(record)} spread={leadSpread(record)}
              autoHint="Median aus erledigten Aufträgen" />
          )}
          {costValue(record) != null && (
            <ReadField icon={Banknote} label="EK-Preis" value={costValue(record)} unit="CHF" spread={costSpread(record)}
              autoHint="Median aus bisherigen Bestellungen" mono />
          )}
        </SubSection>
      )}
    </div>
  );
}

// Symbole für die optionalen Felder (im Sektions-«+»-Menü).
const MENU_ICON: Record<string, React.ElementType> = {
  material: Layers, surface: Sparkles, min_order_qty: Package, safety_stock: Shield,
};

function formatDuration(days: number): string {
  if (days >= 1) return `${days.toFixed(days < 10 ? 1 : 0)} Tag${days >= 2 ? 'e' : ''}`;
  const hours = days * 24;
  if (hours >= 1) return `${hours.toFixed(1)} Std`;
  return `${Math.max(1, Math.round(hours * 60))} Min`;
}

