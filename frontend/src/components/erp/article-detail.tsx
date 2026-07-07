'use client';

import { useEffect, useRef, useState } from 'react';
import {
  Package, ArrowLeft, FileText, Workflow, Boxes, Trash2, Tag, QrCode, AlertTriangle,
  Ruler, ShoppingCart, Box, Square, Scale, Droplet, Fingerprint, Layers, ExternalLink,
  Scaling, Hash, Truck, Banknote, Link2, Weight, Sparkles, Plus, Shield, Ban, FolderOpen,
} from 'lucide-react';
import { api } from '@/lib/api';
import type { Article, ArticleInput, ArticleStatus, ArticleUnit, ArticleSerialization, ArticleNameSuggestion, UserProfile, OrdersMode } from '@/types';
import { ARTICLE_NAME_MAX_LENGTH } from '@/types';
import {
  statusConfig,
  unitLabel, serializationLabel, normalizeSize, normalizeWeight,
  validateName, validateSize, validateWeight,
} from '@/lib/article';
import type { StatusAction } from '@/lib/status-flow';
import { useAutosave } from '@/lib/use-autosave';
import { isVersionConflict } from '@/lib/optimistic';
import { fmtObjId } from '@/components/erp/user-detail';
import { Label, ErrorText, SaveIndicator } from '@/components/erp/fields';
import { ProcessSteps } from '@/components/erp/process-steps';
import { InstanceList } from '@/components/erp/instance-list';
import { SalesPanel } from '@/components/erp/sales-panel';
import { ObjectDocuments } from '@/components/erp/object-documents';
import { DetailTabs } from '@/components/erp/detail-tabs';
import { DeactivateDialog, ReplacedBanner } from '@/components/erp/deactivate-dialog';
import { printObjectLabel } from '@/components/scan/object-label';
import { cn, formatAmount as fmtChf, localDate } from '@/lib/utils';

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

type OptKey = 'material' | 'cad_url' | 'surface' | 'supplier_article_number' | 'min_order_qty' | 'safety_stock' | 'reorder_target' | 'shelf_life_days';
type Form = {
  name: string; unit: string; serialization: string; size: string; weight_kg: string;
  material: string; cad_url: string; surface: string; supplier_article_number: string; min_order_qty: string; safety_stock: string;
  reorder_target: string; shelf_life_days: string;
  // Beschaffungsquelle (Spezifikation): Modus + Lieferant (id als String für die Auswahl) / Webshop-Link
  procurement_mode: string; default_supplier_id: string; default_webshop_url: string;
};

// Optionale Stammdaten – dynamische Feldliste (nur bei Bedarf hinzufügen)
const OPTIONAL_FIELDS: { key: OptKey; label: string; numeric?: boolean; placeholder: string; hint?: string }[] = [
  { key: 'material', label: 'Material', placeholder: 'z. B. Stahl 1.4301' },
  { key: 'cad_url', label: 'CAD-Link', placeholder: 'https://…', hint: 'Link zur CAD-Datei/Zeichnung' },
  { key: 'surface', label: 'Oberfläche', placeholder: 'z. B. verzinkt, eloxiert' },
  { key: 'supplier_article_number', label: 'Lief.-Artikelnummer', placeholder: 'Artikelnummer des Lieferanten' },
  { key: 'min_order_qty', label: 'MOQ (Mindestbestellmenge)', numeric: true, placeholder: 'z. B. 50' },
  { key: 'safety_stock', label: 'Meldebestand (Sicherheitsbestand)', numeric: true, placeholder: 'z. B. 20', hint: 'Fällt der freie Bestand darunter, wird automatisch nachbestellt.' },
  { key: 'reorder_target', label: 'Zielbestand (Nachbestellung)', numeric: true, placeholder: 'z. B. 100', hint: 'Auf diese Menge wird bei Nachbestellung aufgefüllt (leer = Meldebestand).' },
  { key: 'shelf_life_days', label: 'Haltbarkeit (Tage)', numeric: true, placeholder: 'z. B. 365', hint: 'Abgelaufene Teile werden ausgebucht und lösen ggf. eine Nachbestellung aus.' },
];

function seedFrom(record: Article | null): Form {
  const base = { name: '', unit: 'Stk', serialization: 'unit', size: '', weight_kg: '',
    material: '', cad_url: '', surface: '', supplier_article_number: '', min_order_qty: '', safety_stock: '',
    reorder_target: '', shelf_life_days: '',
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
    reorder_target: record.reorder_target != null ? String(record.reorder_target) : '',
    shelf_life_days: record.shelf_life_days != null ? String(record.shelf_life_days) : '',
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

export function ArticleDetail({ record, suppliers = [], onSaved, onCancel, onBack, onRefresh }: {
  record: Article | null;          // null ⇒ Anlage-Modus
  suppliers?: UserProfile[];
  onSaved: (a: Article) => void;
  onCancel: () => void;
  onBack: () => void;
  onRefresh?: () => void;          // Feed nach Inaktiv/Ersetzen aktualisieren (Kaskade)
}) {
  const isCreate = record === null;
  const [tab, setTab] = useState<TabKey>('spezifikation');
  const [dialog, setDialog] = useState<'deactivate' | null>(null);
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
  const [added, setAdded] = useState<OptKey[]>(() => {
    const s = seedFrom(record);
    return OPTIONAL_FIELDS.filter((f) => s[f.key].trim() !== '').map((f) => f.key);
  });

  function set<K extends keyof Form>(key: K, value: Form[K]) {
    setForm((p) => ({ ...p, [key]: value }));
  }

  function addField(key: OptKey) { setAdded((a) => (a.includes(key) ? a : [...a, key])); }
  function removeField(key: OptKey) { setAdded((a) => a.filter((k) => k !== key)); set(key, ''); }

  // Nach der Freigabe ist der Artikel schreibgeschützt (keine Versionierung).
  const locked = !isCreate && record !== null && record.status !== 'draft';

  // Gewicht wird read-only, sobald der Artikel verbaute Ressourcen hat: es ergibt
  // sich dann automatisch aus der Stückliste (über mehrere Ebenen, Backend).
  const computedWeight = record?.computed_weight_kg ?? null;
  const weightIsComputed = !isCreate && computedWeight != null;

  // Pflicht ist nur der Name. Grösse/Gewicht sind optional – nur validieren, wenn befüllt.
  const errs = {
    name: validateName(form.name),
    size: form.size.trim() ? validateSize(form.size) : null,
    weight: form.weight_kg.trim() ? validateWeight(form.weight_kg) : null,
  };
  const valid = !errs.name && !errs.size && !errs.weight;

  // Konkreter, handlungsleitender Grund, warum (noch) nicht gespeichert wird –
  // statt des generischen «Pflichtfelder …». Namensgebung ist frei (kein Katalog mehr).
  const blockReason: string | null = valid ? null
    : (!form.name.trim()
        ? 'Bitte einen Artikelnamen eingeben.'
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
        reorder_target: form.reorder_target.trim() || null,
        shelf_life_days: form.shelf_life_days.trim() ? Math.trunc(Number(form.shelf_life_days)) : null,
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

  const statusCfg = statusConfig(isCreate || !record ? 'draft' : record.status);
  const StatusCfgIcon = statusCfg.icon;
  const actions = isCreate || !record ? [] : articleActions(record.status, (stepsCount ?? 0) > 0);

  return (
    <div className="flex flex-col h-full bg-bg-1">
      {/* Header */}
      <div style={H.dhead}>
        <button onClick={onBack} className="flex items-center gap-1 text-sm mb-3 md:hidden" style={{ color: 'var(--accent)' }}>
          <ArrowLeft size={15} /> Zurück
        </button>
        <div style={H.top}>
          <div style={H.ico}><Package size={26} /></div>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={H.eyebrow}>Artikel</div>
            <h1 style={{ ...H.title, ...(form.name ? null : H.titleEmpty) }}>{form.name || 'Neuer Artikel'}</h1>
            <div style={H.sub}>
              <span style={H.subN}>{isCreate ? 'wird vergeben' : fmtObjId(record.object_id)}</span>
              {!isCreate && record.object_id != null && (
                <>
                  <span style={H.idsep} />
                  <button className="erp-idbtn" data-tip="Etikett drucken (QR)" data-tip-pos="bottom" aria-label="Etikett drucken"
                    onClick={() => printObjectLabel(record.object_id as number, form.name || record.name, 'Artikel')}>
                    <QrCode size={15} />
                  </button>
                  {/* Deaktivieren/Ersetzen als kleines Symbol neben der Objektnummer (Claude-Design):
                      nur bei freigegebenem Artikel, öffnet den Dialog (mit «Ersetzen»-Option). */}
                  {record.status === 'released' && (
                    <button className="erp-idbtn" data-tip="Deaktivieren / ersetzen" data-tip-pos="bottom"
                      aria-label="Artikel deaktivieren oder ersetzen" disabled={statusBusy}
                      style={{ color: 'var(--danger)' }} onClick={() => onStatusAction('inactive')}>
                      <Ban size={15} />
                    </button>
                  )}
                </>
              )}
            </div>
          </div>
          <div style={H.right}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <SaveIndicator saving={saving} flash={flash} />
              <span style={{ ...H.statusbig, background: statusCfg.bg, color: statusCfg.color }}>
                {StatusCfgIcon && <StatusCfgIcon size={15} strokeWidth={2.5} />}{statusCfg.label}
              </span>
            </div>
            {/* «Deaktivieren» (danger) ist als kleines Symbol neben der Objektnummer platziert –
                hier nur die übrigen Aktionen (z. B. «Freigeben» beim Entwurf). */}
            {actions.some((a) => a.tone !== 'danger') && (
              <div style={{ display: 'flex', gap: 8 }}>
                {actions.filter((a) => a.tone !== 'danger').map((a) => (
                  <button
                    key={a.target}
                    onClick={() => onStatusAction(a.target)}
                    disabled={statusBusy || a.disabled}
                    data-tip={a.hint}
                    data-tip-pos="bottom"
                    className={cn('erp-actbtn', a.tone === 'primary' ? 'erp-actbtn-primary' : 'erp-actbtn-neutral')}
                  >
                    {a.label}
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>

        {!isCreate && (record.replaced_by_id != null || record.replaces_id != null) && (
          <ReplacedBanner replacedBy={record.replaced_by_id ?? null} replaces={record.replaces_id ?? null} />
        )}

        {/* Tabs (einheitliche Optik über alle Datensätze) */}
        <DetailTabs<TabKey> style={{ marginTop: 16 }} active={tab} onChange={setTab} tabs={TABS} />
      </div>

      {/* Content */}
      {/* FIX: Enter im Container löst den Autosave-Flush aus – in TEXTAREAs (mehrzeilige
          Beschreibungen/Bild-URLs/Notizen) verschluckte preventDefault() aber jeden
          Zeilenumbruch. Textareas ausnehmen. */}
      <div onKeyDown={(e) => { if (e.key === 'Enter' && (e.target as HTMLElement).tagName !== 'TEXTAREA') { e.preventDefault(); flush(); } }}
        style={{ flex: 1, overflowY: 'auto', padding: '24px 28px 88px', background: 'var(--bg-2)', boxShadow: flash ? 'inset 0 0 0 2px var(--success)' : 'none', transition: 'box-shadow 0.2s' }}>
        {tab === 'spezifikation' && (
          <div style={{ maxWidth: 880 }}>
            {locked ? (
              <SpecRead record={record!} form={form} weightIsComputed={weightIsComputed} computedWeight={computedWeight} />
            ) : (
              <div style={SPEC.card}>
                <SpecSection icon={FileText} title="Spezifikation"
                  right={<SectionAddButton keys={SEC_STAMM} added={added} onAdd={addField} />}>
                  <div style={{ gridColumn: '1 / -1' }}>
                    <NameField value={form.name} onChange={(v) => set('name', v)}
                      error={form.name.trim() ? errs.name : null} />
                  </div>
                  <IconPick label="Mengeneinheit" required value={form.unit} onChange={(v) => set('unit', v)} options={UNIT_PICK} />
                  <IconPick label="Serialisierung" required value={form.serialization} onChange={(v) => set('serialization', v)} options={SERIAL_PICK} />
                  {OPTIONAL_FIELDS.filter((f) => SEC_STAMM.includes(f.key) && added.includes(f.key)).map((f) => (
                    <OptField key={f.key} f={f} form={form} onSet={set} onRemove={removeField} />
                  ))}
                </SpecSection>

                <SpecSection icon={Box} title="Physische Eigenschaften">
                  <EditField label="Abmessungen (mm)" value={form.size} onChange={(v) => set('size', v)} placeholder="z. B. 3x40x600" hint="Masse in mm, aufsteigend & mit 'x' getrennt – optional" error={form.size ? errs.size : null} />
                  {weightIsComputed ? (
                    <ReadField icon={Weight} label="Gewicht" value={fmtWeight(computedWeight!)} unit="kg" autoHint="Automatisch aus der Stückliste berechnet" mono />
                  ) : (
                    <EditField label="Gewicht (kg)" value={form.weight_kg} onChange={(v) => set('weight_kg', v)} placeholder="z. B. 2.5" hint="Grösser als 0, max. 3 Nachkommastellen – optional" error={form.weight_kg ? errs.weight : null} />
                  )}
                </SpecSection>

                <SpecSection icon={ShoppingCart} title="Beschaffung" last
                  right={<SectionAddButton keys={SEC_BESCH} added={added} onAdd={addField} />}>
                  {/* Bezugsquelle & Lieferant werden AUSSCHLIESSLICH im Beschaffungs-Prozessschritt
                      gepflegt (one single source of truth) – hier nur reine Artikel-Attribute. */}
                  <div style={{ gridColumn: '1 / -1', font: '500 11.5px var(--font-body)', color: 'var(--fg-4)', lineHeight: 1.5 }}>
                    Bezugsquelle &amp; Lieferant legst du im Reiter «Prozess» am Beschaffungs-Schritt fest.
                  </div>
                  <EditField label="Bestellnummer" value={form.supplier_article_number} onChange={(v) => set('supplier_article_number', v)} placeholder="Artikelnummer des Lieferanten" />
                  <EditField label="CAD-/Onshape-Link" value={form.cad_url} onChange={(v) => set('cad_url', v)} placeholder="https://cad.onshape.com/…" />
                  {!isCreate && record!.lead_time_days_low != null && (
                    <ReadField icon={Truck} label="Lieferzeit" value={leadRangeText(record!)} autoHint="Automatisch aus vorherigen Lieferungen" />
                  )}
                  {!isCreate && record!.landed_unit_cost != null && (
                    <ReadField icon={Banknote} label="EK-Preis" value={fmtChf(record!.landed_unit_cost)} unit="CHF" autoHint="Aus der letzten Freigabe" mono />
                  )}
                  {OPTIONAL_FIELDS.filter((f) => SEC_BESCH.includes(f.key) && added.includes(f.key)).map((f) => (
                    <OptField key={f.key} f={f} form={form} onSet={set} onRemove={removeField} />
                  ))}
                </SpecSection>
              </div>
            )}
          </div>
        )}
        {tab === 'prozess' && (
          <ProcessSteps owner="articles" ownerObjectId={record?.object_id ?? null} suppliers={suppliers}
            readOnly={record?.status !== 'draft'} selfArticleObjectId={record?.object_id ?? null}
            onStepsCount={setStepsCount}
            procurementReady={form.procurement_mode === 'webshop' ? !!form.default_webshop_url.trim() : !!form.default_supplier_id} />
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

      {/* Kein dekorativer Footer mehr. Die Aktions-/Status-Leiste erscheint nur, wenn sie etwas
          tut: beim Anlegen (Hinweis + Abbrechen) oder wenn ein Fehler/Blocker anzuzeigen ist –
          im normalen (gültigen) Bearbeiten bleibt das Fenster ohne Footer. Der Speichern-Status
          steckt ohnehin als grüner Flash im Kopf (SaveIndicator). */}
      {!locked && tab === 'spezifikation' && (isCreate || error || blockReason) && (
        <div style={{ padding: '11px 28px', background: '#fff', borderTop: '1px solid var(--border-1)', display: 'flex', alignItems: 'center', gap: 10, flexShrink: 0 }}>
          <span style={{ flex: 1, fontSize: 12.5, color: error ? 'var(--danger)' : 'var(--fg-4)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {error ?? blockReason ?? 'Wird automatisch angelegt, sobald vollständig'}
          </span>
          {isCreate && (
            <button onClick={onCancel} className="erp-actbtn erp-actbtn-neutral" style={{ flexShrink: 0 }}>
              Abbrechen
            </button>
          )}
        </div>
      )}

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
const H: Record<string, React.CSSProperties> = {
  dhead: { padding: '18px 28px', borderBottom: '1px solid var(--border-1)', background: 'rgba(255,255,255,.93)', backdropFilter: 'blur(8px)', flexShrink: 0 },
  top: { display: 'flex', alignItems: 'flex-start', gap: 16 },
  ico: { width: 56, height: 56, borderRadius: 'var(--r-md)', background: '#F4EBDD', color: '#9A7238', display: 'flex', alignItems: 'center', justifyContent: 'center', flex: 'none' },
  eyebrow: { font: 'var(--overline)', letterSpacing: 'var(--tracking-overline)', textTransform: 'uppercase', color: 'var(--inexxio-red)', marginBottom: 6 },
  title: { font: '800 26px var(--font-display)', letterSpacing: '-.03em', margin: 0, lineHeight: 1.05, color: 'var(--fg-1)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' },
  titleEmpty: { color: 'var(--fg-4)', fontStyle: 'italic', fontWeight: 700 },
  sub: { display: 'flex', alignItems: 'center', gap: 9, marginTop: 9 },
  subN: { fontFamily: 'var(--font-mono)', fontVariantNumeric: 'tabular-nums', color: 'var(--fg-3)', fontSize: 13 },
  idsep: { width: 1, height: 16, background: 'var(--border-2)', margin: '0 2px' },
  right: { display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 12, flex: 'none' },
  statusbig: { display: 'inline-flex', alignItems: 'center', gap: 7, padding: '6px 13px', borderRadius: 'var(--r-pill)', font: '600 13.5px var(--font-body)', whiteSpace: 'nowrap' },
  card: { background: '#fff', border: '1px solid var(--border-1)', borderRadius: 'var(--r-lg)', padding: '22px 24px', display: 'flex', flexDirection: 'column', gap: 16, maxWidth: 720 },
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
      <Label required>Name</Label>
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
      ) : (
        <div style={{ marginTop: 4, fontSize: 11, color: '#94a3b8' }}>
          Frei wählbar (max. {ARTICLE_NAME_MAX_LENGTH} Zeichen). Vorschläge helfen, Dubletten zu vermeiden.
        </div>
      )}
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
const SPEC = {
  card: { background: '#fff', border: '1px solid var(--border-1)', borderRadius: 'var(--r-lg)', padding: '28px 30px' } as React.CSSProperties,
  grid: { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 260px), 1fr))', gap: '26px 44px' } as React.CSSProperties,
};

// Abschnitts-Kopf (getöntes Symbol + Versalien-Titel + Haarlinie + optionaler rechter Slot,
// z. B. «+ Feld hinzufügen») – EIN Look über alle Sektionen.
function SpecSection({ icon: Icon, title, last, right, children }: {
  icon: React.ElementType; title: string; last?: boolean; right?: React.ReactNode; children: React.ReactNode;
}) {
  return (
    <div style={{ marginBottom: last ? 0 : 40 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 11, paddingBottom: 12, marginBottom: 24, borderBottom: '1px solid var(--border-1)' }}>
        <span style={{ width: 32, height: 32, borderRadius: 'var(--r-sm)', background: '#F4EBDD', color: '#9A7238', display: 'flex', alignItems: 'center', justifyContent: 'center', flex: 'none' }}>
          <Icon size={17} />
        </span>
        <span style={{ font: '800 14px var(--font-display)', letterSpacing: '.02em', color: 'var(--fg-1)' }}>{title}</span>
        {right && <span style={{ marginLeft: 'auto' }}>{right}</span>}
      </div>
      <div style={SPEC.grid}>{children}</div>
    </div>
  );
}

// «Feld hinzufügen» als kleines +-Symbol (Hover-Tooltip) im Sektions-Kopf → Dropdown der
// noch nicht sichtbaren optionalen Felder DIESER Sektion. Kein eigener «Zusätzliche»-Bereich.
function SectionAddButton({ keys, added, onAdd }: {
  keys: OptKey[]; added: OptKey[]; onAdd: (k: OptKey) => void;
}) {
  const [open, setOpen] = useState(false);
  const boxRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    function h(e: MouseEvent) { if (boxRef.current && !boxRef.current.contains(e.target as Node)) setOpen(false); }
    document.addEventListener('mousedown', h);
    return () => document.removeEventListener('mousedown', h);
  }, []);
  const available = OPTIONAL_FIELDS.filter((f) => keys.includes(f.key) && !added.includes(f.key));
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
                <span style={{ minWidth: 0 }}>
                  <span style={{ display: 'block', font: '700 13.5px var(--font-body)', color: 'var(--fg-1)' }}>{f.label}</span>
                  {f.hint && <span style={{ display: 'block', font: '500 11.5px var(--font-body)', color: 'var(--fg-4)', marginTop: 1 }}>{f.hint}</span>}
                </span>
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
        <Label>{f.label}</Label>
        <button type="button" onClick={() => onRemove(f.key)} title="Feld entfernen"
          style={{ border: 'none', background: 'none', color: 'var(--fg-4)', cursor: 'pointer', padding: 0, marginBottom: 6 }}>
          <Trash2 size={13} />
        </button>
      </div>
      <input value={form[f.key]} placeholder={f.placeholder} onChange={(e) => onSet(f.key, e.target.value)} className={FIN_CLS} />
      {f.hint && <div style={{ marginTop: 5, font: '500 11px var(--font-body)', color: 'var(--fg-4)' }}>{f.hint}</div>}
    </div>
  );
}

// Optionale Felder je Sektion (Kontext-Zuordnung): Stammdaten ↔ Oberfläche/Material,
// Beschaffung ↔ MOQ/Sicherheitsbestand.
const SEC_STAMM: OptKey[] = ['surface', 'material'];
const SEC_BESCH: OptKey[] = ['min_order_qty', 'safety_stock'];

// Eingabefeld-Klasse analog Design-`.fin` (Rand border-2, r-md, Akzent-Fokus).
const FIN_CLS = 'w-full rounded-ds-md border border-border-2 bg-white px-3 py-2.5 text-[15px] font-medium text-fg-1 outline-none placeholder:text-fg-4 focus:border-accent focus:ring-2 focus:ring-accent-soft';

function linkHost(href: string): string {
  try { return new URL(href).hostname.replace(/^www\./, ''); } catch { return href; }
}

function leadRangeText(r: Article): string {
  const lo = r.lead_time_days_low; const hi = r.lead_time_days_high;
  if (lo == null && hi == null) return '—';
  const same = lo == null || hi == null || Number(lo) === Number(hi);
  return same ? formatDuration((lo ?? hi) as number) : `${formatDuration(lo as number)} – ${formatDuration(hi as number)}`;
}

// Read-only-Feld (Design-`.frow`): kleines Symbol + Versalien-Overline + kräftiger Wert.
// Optional Einheit/mono, Link («Öffnen») oder ⓘ-Auto-Hinweis (abgeleiteter Wert).
function ReadField({ icon: Icon, label, value, unit, mono, full, autoHint, link }: {
  icon?: React.ElementType; label: string; value?: React.ReactNode; unit?: string;
  mono?: boolean; full?: boolean; autoHint?: string; link?: string;
}) {
  return (
    <div style={{ display: 'flex', gap: 11, alignItems: 'flex-start', gridColumn: full ? '1 / -1' : undefined }}>
      {Icon && (
        <span style={{ width: 22, height: 22, color: 'var(--fg-4)', display: 'flex', alignItems: 'center', justifyContent: 'center', flex: 'none', marginTop: 1 }}>
          <Icon size={18} />
        </span>
      )}
      <div style={{ minWidth: 0, flex: 1 }}>
        <div style={{ font: '600 11px var(--font-body)', textTransform: 'uppercase', letterSpacing: '.07em', color: 'var(--fg-4)' }}>{label}</div>
        {link ? (
          <a href={link} target="_blank" rel="noreferrer"
            style={{ display: 'inline-flex', alignItems: 'center', gap: 6, marginTop: 3, font: '600 14.5px var(--font-body)', color: 'var(--accent-ink)' }}>
            {linkHost(link)} <ExternalLink size={13} />
          </a>
        ) : (
          <div style={{ font: '600 15.5px var(--font-body)', color: 'var(--fg-1)', marginTop: 3, lineHeight: 1.35, ...(mono ? { fontFamily: 'var(--font-mono)', fontVariantNumeric: 'tabular-nums', fontSize: 14 } : null) }}>
            {value}{unit && <span style={{ font: '500 13px var(--font-body)', color: 'var(--fg-3)', marginLeft: 4 }}>{unit}</span>}
          </div>
        )}
        {autoHint && (
          <div style={{ marginTop: 5, display: 'inline-flex', alignItems: 'center', gap: 4, font: '500 11px var(--font-body)', color: 'var(--fg-4)' }}>
            <Sparkles size={11} /> {autoHint}
          </div>
        )}
      </div>
    </div>
  );
}

// Eingabe-Feld (Entwurf): Overline-Label + `.fin`-Input + Fehler/Hinweis.
function EditField({ label, value, onChange, placeholder, hint, error, required, full }: {
  label: string; value: string; onChange: (v: string) => void;
  placeholder?: string; hint?: string; error?: string | null; required?: boolean; full?: boolean;
}) {
  return (
    <div style={{ gridColumn: full ? '1 / -1' : undefined }}>
      <Label required={required}>{label}</Label>
      <input value={value} placeholder={placeholder} onChange={(e) => onChange(e.target.value)}
        className={FIN_CLS} style={error ? { borderColor: '#fca5a5' } : undefined} />
      {error ? <ErrorText msg={error} /> : hint ? (
        <div style={{ marginTop: 5, font: '500 11px var(--font-body)', color: 'var(--fg-4)' }}>{hint}</div>
      ) : null}
    </div>
  );
}

// Symbol-Auswahl (Pille mit Icon + Wort); aktiv = Akzent. Ersetzt Dropdown/Segmented.
function IconPick({ label, value, onChange, options, required }: {
  label: string; value: string; onChange: (v: string) => void; required?: boolean;
  options: { value: string; label: string; icon: React.ElementType }[];
}) {
  return (
    <div>
      <Label required={required}>{label}</Label>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
        {options.map((o) => {
          const on = value === o.value; const Icon = o.icon;
          return (
            <button key={o.value} type="button" onClick={() => onChange(o.value)}
              style={{ display: 'inline-flex', alignItems: 'center', gap: 7, padding: '7px 12px 7px 10px', borderRadius: 'var(--r-pill)', cursor: 'pointer', transition: 'all .13s',
                border: `1px solid ${on ? 'var(--accent)' : 'var(--border-2)'}`, background: on ? 'var(--accent-soft)' : '#fff' }}>
              <Icon size={15} style={{ color: on ? 'var(--accent-ink)' : 'var(--fg-4)' }} />
              <b style={{ font: '700 12.5px var(--font-body)', color: on ? 'var(--accent-ink)' : 'var(--fg-2)' }}>{o.label}</b>
            </button>
          );
        })}
      </div>
    </div>
  );
}

// Read-only-Spezifikation (freigegebener Artikel) – in Sektionen gegliedert.
function SpecRead({ record, form, weightIsComputed, computedWeight }: {
  record: Article; form: Form; weightIsComputed: boolean; computedWeight: string | number | null;
}) {
  const has = (k: OptKey) => form[k].trim() !== '';
  const hasPhysical = !!record.size || weightIsComputed || record.weight_kg != null;
  const hasProcurement = has('supplier_article_number') || has('cad_url') || has('min_order_qty')
    || has('safety_stock') || record.landed_unit_cost != null || record.lead_time_days_low != null;
  return (
    <div style={SPEC.card}>
      <SpecSection icon={FileText} title="Spezifikation" last={!hasPhysical && !hasProcurement}>
        <ReadField icon={Tag} label="Artikelname" value={record.name} full />
        <ReadField icon={Ruler} label="Mengeneinheit" value={unitLabel(record.unit)} />
        <ReadField icon={Fingerprint} label="Serialisierung" value={serializationLabel(record.serialization)} />
        {has('surface') && <ReadField icon={Sparkles} label="Oberfläche" value={form.surface} />}
        {has('material') && <ReadField icon={Layers} label="Material" value={form.material} />}
      </SpecSection>
      {hasPhysical && (
        <SpecSection icon={Box} title="Physische Eigenschaften" last={!hasProcurement}>
          {record.size && <ReadField icon={Scaling} label="Abmessungen" value={record.size} unit="mm" mono />}
          {(weightIsComputed || record.weight_kg != null) && (
            <ReadField icon={Weight} label="Gewicht" value={weightIsComputed ? fmtWeight(computedWeight!) : String(record.weight_kg)}
              unit={weightIsComputed ? 'kg (berechnet)' : 'kg'} mono />
          )}
        </SpecSection>
      )}
      {hasProcurement && (
        <SpecSection icon={ShoppingCart} title="Beschaffung" last>
          {has('supplier_article_number') && <ReadField icon={Hash} label="Bestellnummer" value={form.supplier_article_number} />}
          {record.lead_time_days_low != null && <ReadField icon={Truck} label="Lieferzeit" value={leadRangeText(record)} autoHint="Automatisch aus vorherigen Lieferungen" />}
          {record.landed_unit_cost != null && <ReadField icon={Banknote} label="EK-Preis" value={fmtChf(record.landed_unit_cost)} unit="CHF" mono />}
          {has('min_order_qty') && <ReadField icon={Package} label="Mindestbestellmenge" value={form.min_order_qty} mono />}
          {has('safety_stock') && <ReadField icon={Shield} label="Sicherheitsbestand" value={form.safety_stock} mono />}
          {has('cad_url') && <ReadField icon={Link2} label="CAD-Link" link={form.cad_url} full />}
        </SpecSection>
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

