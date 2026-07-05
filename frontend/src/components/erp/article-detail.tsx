'use client';

import { useEffect, useRef, useState } from 'react';
import {
  Package, ArrowLeft, FileText, Workflow, Boxes, Lock, Trash2, Clock, Tag, QrCode, AlertTriangle,
  Ruler, ShoppingCart, Box, Square, Scale, Droplet, Fingerprint, Layers, PlusCircle, ExternalLink,
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
import { TextField, Label, ErrorText, SaveIndicator, inputCls } from '@/components/erp/fields';
import { ProcessSteps } from '@/components/erp/process-steps';
import { InstanceList } from '@/components/erp/instance-list';
import { SalesPanel } from '@/components/erp/sales-panel';
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

type TabKey = 'stammdaten' | 'prozess' | 'bestand' | 'verkauf';

const TABS: { key: TabKey; label: string; icon: React.ElementType }[] = [
  { key: 'stammdaten', label: 'Spezifikation', icon: FileText },
  { key: 'prozess', label: 'Prozess', icon: Workflow },
  { key: 'bestand', label: 'Bestand', icon: Boxes },
  { key: 'verkauf', label: 'Verkauf', icon: Tag },
];

type OptKey = 'material' | 'cad_url' | 'surface' | 'supplier_article_number' | 'min_order_qty' | 'safety_stock';
type Form = {
  name: string; unit: string; serialization: string; size: string; weight_kg: string;
  material: string; cad_url: string; surface: string; supplier_article_number: string; min_order_qty: string; safety_stock: string;
};

// Optionale Stammdaten – dynamische Feldliste (nur bei Bedarf hinzufügen)
const OPTIONAL_FIELDS: { key: OptKey; label: string; numeric?: boolean; placeholder: string; hint?: string }[] = [
  { key: 'material', label: 'Material', placeholder: 'z. B. Stahl 1.4301' },
  { key: 'cad_url', label: 'CAD-Link', placeholder: 'https://…', hint: 'Link zur CAD-Datei/Zeichnung' },
  { key: 'surface', label: 'Oberfläche', placeholder: 'z. B. verzinkt, eloxiert' },
  { key: 'supplier_article_number', label: 'Lief.-Artikelnummer', placeholder: 'Artikelnummer des Lieferanten' },
  { key: 'min_order_qty', label: 'MOQ (Mindestbestellmenge)', numeric: true, placeholder: 'z. B. 50' },
  { key: 'safety_stock', label: 'Sicherheitsbestand', numeric: true, placeholder: 'z. B. 20' },
];

function seedFrom(record: Article | null): Form {
  const base = { name: '', unit: 'Stk', serialization: 'unit', size: '', weight_kg: '',
    material: '', cad_url: '', surface: '', supplier_article_number: '', min_order_qty: '', safety_stock: '' };
  if (!record) return base;
  return {
    ...base,
    name: record.name, unit: record.unit, serialization: record.serialization,
    size: record.size ?? '', weight_kg: record.weight_kg != null ? String(record.weight_kg) : '',
    material: record.material ?? '', cad_url: record.cad_url ?? '', surface: record.surface ?? '',
    supplier_article_number: record.supplier_article_number ?? '',
    min_order_qty: record.min_order_qty != null ? String(record.min_order_qty) : '',
    safety_stock: record.safety_stock != null ? String(record.safety_stock) : '',
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
  const [tab, setTab] = useState<TabKey>('stammdaten');
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
            {actions.length > 0 && (
              <div style={{ display: 'flex', gap: 8 }}>
                {actions.map((a) => (
                  <button
                    key={a.target}
                    onClick={() => onStatusAction(a.target)}
                    disabled={statusBusy || a.disabled}
                    data-tip={a.hint}
                    data-tip-pos="bottom"
                    className={cn('erp-actbtn', a.tone === 'primary' ? 'erp-actbtn-primary' : a.tone === 'danger' ? 'erp-actbtn-danger' : 'erp-actbtn-neutral')}
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

        {/* Tabs */}
        <div style={{ display: 'flex', gap: 2, marginTop: 16 }}>
          {TABS.map((t) => {
            const active = tab === t.key;
            const Icon = t.icon;
            return (
              <button key={t.key} onClick={() => setTab(t.key)} className={cn('erp-tab', active && 'erp-tab-active')}>
                <Icon size={15} /> {t.label}
              </button>
            );
          })}
        </div>
      </div>

      {/* Content */}
      {/* FIX: Enter im Container löst den Autosave-Flush aus – in TEXTAREAs (mehrzeilige
          Beschreibungen/Bild-URLs/Notizen) verschluckte preventDefault() aber jeden
          Zeilenumbruch. Textareas ausnehmen. */}
      <div onKeyDown={(e) => { if (e.key === 'Enter' && (e.target as HTMLElement).tagName !== 'TEXTAREA') { e.preventDefault(); flush(); } }}
        style={{ flex: 1, overflowY: 'auto', padding: '24px 28px', background: 'var(--bg-2)', boxShadow: flash ? 'inset 0 0 0 2px var(--success)' : 'none', transition: 'box-shadow 0.2s' }}>
        {tab === 'stammdaten' && (
          <div style={{ maxWidth: 880 }}>
            {locked ? (
              <SpecRead record={record!} form={form} weightIsComputed={weightIsComputed} computedWeight={computedWeight} />
            ) : (
              <div style={SPEC.card}>
                <SpecSection icon={FileText} title="Stammdaten">
                  <div style={{ gridColumn: '1 / -1' }}>
                    <NameField value={form.name} onChange={(v) => set('name', v)}
                      error={form.name.trim() ? errs.name : null} />
                  </div>
                  <IconPick label="Mengeneinheit" required value={form.unit} onChange={(v) => set('unit', v)} options={UNIT_PICK} />
                  <IconPick label="Serialisierung" required value={form.serialization} onChange={(v) => set('serialization', v)} options={SERIAL_PICK} />
                </SpecSection>

                <SpecSection icon={Ruler} title="Physische Eigenschaften">
                  <TextField label="Abmessungen (mm)" value={form.size} onChange={(v) => set('size', v)} placeholder="z. B. 3x40x600 (optional)" hint="Masse in mm, aufsteigend & mit 'x' getrennt – optional" error={form.size ? errs.size : null} />
                  {weightIsComputed ? (
                    <ComputedWeight value={computedWeight!} />
                  ) : (
                    <TextField label="Gewicht (kg)" value={form.weight_kg} onChange={(v) => set('weight_kg', v)} placeholder="z. B. 2.5 (optional)" hint="Grösser als 0, max. 3 Nachkommastellen – optional" error={form.weight_kg ? errs.weight : null} />
                  )}
                </SpecSection>

                <SpecSection icon={ShoppingCart} title="Zusätzliche Angaben" last>
                  <div style={{ gridColumn: '1 / -1' }}>
                    <OptionalFieldsEditor added={added} form={form} onSet={set} onAdd={addField} onRemove={removeField} />
                  </div>
                </SpecSection>
              </div>
            )}
            {!isCreate && (record!.unit_cost_low != null || record!.lead_time_days_low != null) && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 14, marginTop: 16 }}>
                <PriceRange record={record!} />
                <LeadTimeRange record={record!} />
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
      </div>

      {/* Meta footer (edit only) */}
      {!isCreate && (
        <div style={{ padding: '9px 28px', borderTop: '1px solid var(--border-1)', background: '#fff', flexShrink: 0, fontSize: 11.5, color: 'var(--fg-4)', display: 'flex', gap: 18 }}>
          <span>Einheit: {unitLabel(record.unit)}</span>
          <span>Erfassung: {serializationLabel(record.serialization)}</span>
          <span>Erstellt: {localDate(record.created_at)}</span>
        </div>
      )}

      {/* Footer-Status (Auto-Save, kein manueller Speichern-Knopf) */}
      {!locked && tab === 'stammdaten' && (
        <div style={{ padding: '11px 28px', background: '#fff', borderTop: '1px solid var(--border-1)', display: 'flex', alignItems: 'center', gap: 10, flexShrink: 0 }}>
          <span style={{ flex: 1, fontSize: 12.5, color: error ? 'var(--danger)' : 'var(--fg-4)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {error ?? blockReason ?? (isCreate ? 'Wird automatisch angelegt, sobald vollständig' : 'Änderungen werden automatisch gespeichert')}
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

const lockedNotice: React.CSSProperties = {
  display: 'flex', alignItems: 'flex-start', gap: 8, padding: '11px 13px',
  background: 'var(--bg-2)', border: '1px solid var(--border-1)', borderRadius: 'var(--r-md)',
  fontSize: 12.5, color: 'var(--fg-2)',
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
        className={inputCls}
        style={{ borderColor: error ? '#fca5a5' : '#e2e8f0' }}
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
function ComputedWeight({ value }: { value: string }) {
  return (
    <div>
      <Label>Gewicht (kg)</Label>
      <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--accent-ink)' }}>{fmtWeight(value)} kg</div>
      <div style={{ marginTop: 4, fontSize: 11, color: 'var(--fg-3)' }}>
        Automatisch aus den verbauten Ressourcen (Stückliste) berechnet – über alle Ebenen.
      </div>
    </div>
  );
}

function PriceRange({ record }: { record: Article }) {
  const low = record.unit_cost_low;
  const high = record.unit_cost_high;
  if (low == null && high == null) return null;
  const same = low == null || high == null || Number(low) === Number(high);
  return (
    <div>
      <Label>Stückpreis netto / Stück</Label>
      <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--accent-ink)' }}>
        {same ? `CHF ${fmtChf((low ?? high) as string | number)}` : `CHF ${fmtChf(low as string | number)} – ${fmtChf(high as string | number)}`}
      </div>
      <div style={{ marginTop: 4, fontSize: 11, color: 'var(--fg-3)' }}>
        {same
          ? 'Aus akzeptierten Bestellungen – ohne MWST.'
          : 'Spanne über akzeptierte Bestellungen: kleinste bis grösste Bestellmenge – ohne MWST.'}
      </div>
    </div>
  );
}

// ─── Spezifikation: sektionierte Ansicht (Design-Redesign) ────────────────────
// Symbol-Auswahl je Einheit/Serialisierung (statt Dropdown/Segmented) – «Symbol + Wort».
const UNIT_PICK = [
  { value: 'Stk', label: 'Stk.', icon: Box },
  { value: 'mm', label: 'mm', icon: Ruler },
  { value: 'm2', label: 'm²', icon: Square },
  { value: 'kg', label: 'kg', icon: Scale },
  { value: 'l', label: 'l', icon: Droplet },
];
const SERIAL_PICK = [
  { value: 'unit', label: 'Einzelteil', icon: Fingerprint },
  { value: 'batch', label: 'Batch', icon: Layers },
];

const SPEC = {
  card: { background: '#fff', border: '1px solid var(--border-1)', borderRadius: 'var(--r-lg)', padding: '26px 28px' } as React.CSSProperties,
  grid: { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '22px 40px' } as React.CSSProperties,
};

// Abschnitts-Kopf (getöntes Symbol + Versalien-Titel + Haarlinie) – EIN Look über alle Sektionen.
function SpecSection({ icon: Icon, title, last, children }: {
  icon: React.ElementType; title: string; last?: boolean; children: React.ReactNode;
}) {
  return (
    <div style={{ marginBottom: last ? 0 : 32 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 11, paddingBottom: 12, marginBottom: 22, borderBottom: '1px solid var(--border-1)' }}>
        <span style={{ width: 32, height: 32, borderRadius: 'var(--r-sm)', background: '#F4EBDD', color: '#9A7238', display: 'flex', alignItems: 'center', justifyContent: 'center', flex: 'none' }}>
          <Icon size={17} />
        </span>
        <span style={{ font: '800 14px var(--font-display)', letterSpacing: '.02em', color: 'var(--fg-1)' }}>{title}</span>
      </div>
      <div style={SPEC.grid}>{children}</div>
    </div>
  );
}

// Read-only-Feld: Versalien-Overline + kräftiger Wert (optional Einheit/mono).
function ReadField({ label, value, unit, mono, full }: {
  label: string; value: React.ReactNode; unit?: string; mono?: boolean; full?: boolean;
}) {
  return (
    <div style={{ gridColumn: full ? '1 / -1' : undefined }}>
      <div style={{ font: '600 11.5px var(--font-body)', textTransform: 'uppercase', letterSpacing: '.07em', color: 'var(--fg-3)' }}>{label}</div>
      <div style={{ font: '600 15.5px var(--font-body)', color: 'var(--fg-1)', marginTop: 7, lineHeight: 1.4, ...(mono ? { fontFamily: 'var(--font-mono)', fontVariantNumeric: 'tabular-nums', fontSize: 14 } : null) }}>
        {value}{unit && <span style={{ font: '500 13px var(--font-body)', color: 'var(--fg-3)', marginLeft: 4 }}>{unit}</span>}
      </div>
    </div>
  );
}

function ReadLink({ label, href, full }: { label: string; href: string; full?: boolean }) {
  let host = href;
  try { host = new URL(href).hostname.replace(/^www\./, ''); } catch { /* roher Wert */ }
  return (
    <div style={{ gridColumn: full ? '1 / -1' : undefined }}>
      <div style={{ font: '600 11.5px var(--font-body)', textTransform: 'uppercase', letterSpacing: '.07em', color: 'var(--fg-3)' }}>{label}</div>
      <a href={href} target="_blank" rel="noreferrer"
        style={{ display: 'inline-flex', alignItems: 'center', gap: 6, marginTop: 7, font: '600 14.5px var(--font-body)', color: 'var(--accent-ink)' }}>
        {host} <ExternalLink size={13} />
      </a>
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
    || has('safety_stock') || record.landed_unit_cost != null;
  return (
    <div style={SPEC.card}>
      <div style={{ ...lockedNotice, marginBottom: 24 }}>
        <Lock size={14} style={{ flexShrink: 0, marginTop: 1 }} />
        <span>Artikel ist freigegeben und schreibgeschützt. Für Änderungen einen neuen Artikel anlegen.</span>
      </div>
      <SpecSection icon={FileText} title="Stammdaten" last={!hasPhysical && !hasProcurement}>
        <ReadField label="Artikelname" value={record.name} full />
        <ReadField label="Mengeneinheit" value={unitLabel(record.unit)} />
        <ReadField label="Serialisierung" value={serializationLabel(record.serialization)} />
        {has('surface') && <ReadField label="Oberfläche" value={form.surface} />}
        {has('material') && <ReadField label="Material" value={form.material} />}
      </SpecSection>
      {hasPhysical && (
        <SpecSection icon={Ruler} title="Physische Eigenschaften" last={!hasProcurement}>
          {record.size && <ReadField label="Abmessungen" value={record.size} unit="mm" mono />}
          {(weightIsComputed || record.weight_kg != null) && (
            <ReadField label="Gewicht" value={weightIsComputed ? fmtWeight(computedWeight!) : String(record.weight_kg)}
              unit={weightIsComputed ? 'kg (berechnet)' : 'kg'} mono />
          )}
        </SpecSection>
      )}
      {hasProcurement && (
        <SpecSection icon={ShoppingCart} title="Beschaffung" last>
          {has('supplier_article_number') && <ReadField label="Bestellnummer" value={form.supplier_article_number} />}
          {record.landed_unit_cost != null && <ReadField label="EK-Preis" value={fmtChf(record.landed_unit_cost)} unit="CHF" mono />}
          {has('min_order_qty') && <ReadField label="Mindestbestellmenge" value={form.min_order_qty} mono />}
          {has('safety_stock') && <ReadField label="Sicherheitsbestand" value={form.safety_stock} mono />}
          {has('cad_url') && <ReadLink label="CAD-Link" href={form.cad_url} full />}
        </SpecSection>
      )}
    </div>
  );
}

// Optionale Stammdaten als dynamische Feldliste (nur bei Bedarf hinzufügen)
function OptionalFieldsEditor({ added, form, onSet, onAdd, onRemove }: {
  added: OptKey[]; form: Form;
  onSet: (key: OptKey, v: string) => void; onAdd: (key: OptKey) => void; onRemove: (key: OptKey) => void;
}) {
  const available = OPTIONAL_FIELDS.filter((f) => !added.includes(f.key));
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      {added.length === 0 && (
        <p style={{ font: '500 13px var(--font-body)', color: 'var(--fg-4)', lineHeight: 1.5, margin: 0 }}>
          Noch keine zusätzlichen Felder. Füge bei Bedarf optionale Attribute hinzu – z. B. Oberfläche, Material,
          CAD-Link oder Sicherheitsbestand.
        </p>
      )}
      {OPTIONAL_FIELDS.filter((f) => added.includes(f.key)).map((f) => (
        <div key={f.key} style={{ display: 'flex', alignItems: 'flex-start', gap: 8 }}>
          <div style={{ flex: 1 }}>
            <TextField label={f.label} value={form[f.key]} onChange={(v) => onSet(f.key, v)} placeholder={f.placeholder} hint={f.hint} />
          </div>
          <button type="button" onClick={() => onRemove(f.key)} data-tip="Feld entfernen"
            className="erp-tool" style={{ marginTop: 21 }}>
            <Trash2 size={15} />
          </button>
        </div>
      ))}
      {available.length > 0 ? (
        <select value="" onChange={(e) => { if (e.target.value) onAdd(e.target.value as OptKey); }}
          className="px-2.5 py-1.5 text-sm rounded-md border bg-white outline-none focus:ring-2 focus:ring-accent"
          style={{ borderColor: 'var(--border-2)', alignSelf: 'flex-start', color: 'var(--accent)', fontWeight: 600 }}>
          <option value="">+ Feld hinzufügen…</option>
          {available.map((f) => <option key={f.key} value={f.key}>{f.label}</option>)}
        </select>
      ) : (
        added.length === 0 && <div style={{ fontSize: 12, color: 'var(--fg-3)' }}>Keine optionalen Felder.</div>
      )}
    </div>
  );
}

function formatDuration(days: number): string {
  if (days >= 1) return `${days.toFixed(days < 10 ? 1 : 0)} Tag${days >= 2 ? 'e' : ''}`;
  const hours = days * 24;
  if (hours >= 1) return `${hours.toFixed(1)} Std`;
  return `${Math.max(1, Math.round(hours * 60))} Min`;
}

function LeadTimeRange({ record }: { record: Article }) {
  const low = record.lead_time_days_low;
  const high = record.lead_time_days_high;
  if (low == null && high == null) return null;
  const same = low == null || high == null || Number(low) === Number(high);
  return (
    <div>
      <Label>Durchlaufzeit (Freigabe → Abschluss)</Label>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 14, fontWeight: 700, color: 'var(--accent-ink)' }}>
        <Clock size={14} />
        {same ? formatDuration((low ?? high) as number) : `${formatDuration(low as number)} – ${formatDuration(high as number)}`}
      </div>
      <div style={{ marginTop: 4, fontSize: 11, color: 'var(--fg-3)' }}>
        {same ? 'Aus erledigten Aufträgen.' : 'Spanne über erledigte Aufträge: kürzeste bis längste.'}
      </div>
    </div>
  );
}
