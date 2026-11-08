'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  Package, FileText, Trash2, AlertTriangle,
  Ruler, Box, Square, Scale, Droplet, Fingerprint, Layers,
  Scaling, Hash, Link2, Weight, Sparkles, Plus, Shield,
  ClipboardPlus, ArrowRight, Blocks, Wrench, Tag,
} from 'lucide-react';
import { api } from '@/lib/api';
import { qk, useDebouncedQuery } from '@/lib/queries';
import { useSearch } from '@/lib/use-search';

/** Namensvorschläge – eine stabile Funktion, damit die Suche nicht bei jedem Rendern neu läuft. */
const suggestNames = (q: string) => api.articleNameSuggestions(q, 8);
import type { Article, ArticleBom, ArticleInput, ArticleLink, ArticleUnit, ArticleSerialization, ArticleNameSuggestion } from '@/types';
import type { ModuleDraft } from '@/lib/modules';
import { moduleFromConfig, toModulePayload } from '@/lib/modules';
import { ARTICLE_NAME_MAX_LENGTH } from '@/types';
import {
  unitLabel, serializationLabel, normalizeSize, normalizeWeight,
  validateName, validateSize, validateWeight,
} from '@/lib/article';
import { articleStatus } from '@/lib/record-status';
import type { DiagramStep } from '@/lib/process-graph';
import { ProcessDesigner } from '@/components/erp/process-designer';
import { FREIGEGEBEN } from '@/lib/process-status';

import { ErrorText } from '@/components/erp/hints';
import { IconSwitch, inputCls } from '@/components/erp/controls';
import { Input, Select } from '@/components/form/field';
import { DetailBody, DetailHeader, HeaderAction, HeaderSep, SPEC, SpecHead, SpecSection, ReadField, SectionSep } from '@/components/erp/detail-frame';
import { History } from '@/components/erp/history';
import { MICRO_LABEL } from '@/components/erp/fields';
import { DocumentTiles } from '@/components/erp/documents';
import { ObjectSelect } from '@/components/erp/object-select';
import { ObjId } from '@/components/erp/obj-id';
import { StockView } from '@/components/erp/stock-view';
import { LabelButton } from '@/components/scan/object-label';
import { errorText } from '@/lib/use-action';

// Artikel-Lebenszyklus: der Artikel entsteht erst mit seiner Freigabe (vollständige
// Spezifikation UND mindestens ein Modul) und ist danach eingefroren. Ausser Betrieb geht er,
// wenn ein Nachfolger ihn ablöst. Keine Reiter: der Bestand steht in derselben Ansicht.

type OptKey = 'material' | 'cad_url' | 'surface' | 'supplier_article_number' | 'min_order_qty' | 'safety_stock' | 'is_hazmat'
  | 'hs_code' | 'origin_country';
// Kein Ort am Artikel: ein Artikel ist eine Gattung – einen Ort hat die Einzelinstanz.
type AddKey = OptKey;
type Form = {
  name: string; unit: string; serialization: string; size: string; weight_kg: string;
  /** **Ware oder Dienstleistung** (`goods` · `service`) – daraus folgen im Zahlungsmodul
   *  Steuersatz und Lieferbedingung. */
  kind: string;
  material: string; cad_url: string; surface: string; supplier_article_number: string; min_order_qty: string; safety_stock: string;
  is_hazmat: string; hs_code: string; origin_country: string;
};

// Optionale Stammdaten – dynamische Feldliste. Die Beschriftung nennt die Sache, der
// Platzhalter erklärt sie.
const OPTIONAL_FIELDS: { key: OptKey; label: string; numeric?: boolean; boolean?: boolean; placeholder: string }[] = [
  { key: 'material', label: 'Material', placeholder: 'z. B. Stahl 1.4301' },
  { key: 'cad_url', label: 'CAD-Link', placeholder: 'Link zur CAD-Datei/Zeichnung – https://…' },
  { key: 'surface', label: 'Oberfläche', placeholder: 'z. B. verzinkt, eloxiert' },
  { key: 'supplier_article_number', label: 'Lief.-Artikelnummer', placeholder: 'Artikelnummer des Lieferanten' },
  { key: 'min_order_qty', label: 'Mindestbestellmenge', numeric: true, placeholder: 'z. B. 50' },
  { key: 'safety_stock', label: 'Sicherheitsbestand', numeric: true, placeholder: 'darunter wird automatisch nachbestellt – z. B. 20' },
  { key: 'is_hazmat', label: 'Gefahrgut', boolean: true, placeholder: '' },
  // ►►► **Zoll-Angaben** – sie stehen auf JEDEM Beleg, nicht nur im Export. ◄◄◄
  // Die ersten sechs Stellen der Zolltarifnummer sind weltweit gleich (HS), der Rest national.
  // Das Ursprungsland ist weder aus der Nummer noch aus dem Versandland ableitbar.
  { key: 'hs_code', label: 'Zolltarifnummer (HS)', placeholder: '6 bis 8 Stellen – die ersten 6 gelten weltweit, z. B. 848210' },
  { key: 'origin_country', label: 'Ursprungsland', placeholder: 'Wo die Ware hergestellt wurde – z. B. CH' },
];

function seedFrom(record: Article | null, initial?: Record<string, string> | null): Form {
  const base: Form = { name: '', unit: 'Stk', serialization: 'unit', size: '', weight_kg: '', kind: 'goods',
    material: '', cad_url: '', surface: '', supplier_article_number: '', min_order_qty: '', safety_stock: '',
    is_hazmat: '', hs_code: '', origin_country: '' };
  if (!record) return initial ? fromValues(base, initial) : base;
  return {
    ...base,
    name: record.name, unit: record.unit, serialization: record.serialization,
    size: record.size ?? '', weight_kg: record.weight_kg != null ? String(record.weight_kg) : '',
    kind: record.is_service ? 'service' : 'goods',
    material: record.material ?? '', cad_url: record.cad_url ?? '', surface: record.surface ?? '',
    supplier_article_number: record.supplier_article_number ?? '',
    min_order_qty: record.min_order_qty != null ? String(record.min_order_qty) : '',
    safety_stock: record.safety_stock != null ? String(record.safety_stock) : '',
    is_hazmat: record.is_hazmat ? 'ja' : '',
    hs_code: record.hs_code ?? '', origin_country: record.origin_country ?? '',
  };
}

/** Ein Entwurf aus einem Handgriff – die Werte, die die KI kannte (Namen wie die Route sie nimmt). */
function fromValues(base: Form, v: Record<string, string>): Form {
  const known = Object.fromEntries(Object.entries(v).filter(([k]) => k in base && k !== 'kind'));
  return { ...base, ...known, ...(v.is_service === 'true' ? { kind: 'service' } : {}),
    ...(v.is_hazmat === 'true' ? { is_hazmat: 'ja' } : v.is_hazmat === 'false' ? { is_hazmat: '' } : {}) };
}

// Vorübergehender Transportfehler (Server nicht erreichbar / Kaltstart) vs. fachlicher Fehler.
function isTransient(msg: string): boolean {
  return /keine verbindung|server nicht erreichbar|netzwerkfehler|failed to fetch|networkerror|load failed/i.test(msg);
}

export function ArticleDetail({ record, initial, onSaved, onBack, onRefresh, onCreateOrder }: {
  record: Article | null;          // null ⇒ Anlage-Modus
  /** Anlage aus einem Handgriff: die Werte, die die KI kannte. */
  initial?: Record<string, string> | null;
  onSaved: (a: Article) => void;
  onBack: () => void;
  /** Den Feed neu laden: eine Ersetzung ändert zwei Datensätze, `onSaved` meldet nur einen. */
  onRefresh?: () => void;
  /** Shortcut «Auftrag»: öffnet den Auftragsentwurf mit diesem Artikel vorgewählt. */
  onCreateOrder?: (articleObjectId: number) => void;
}) {
  const isCreate = record === null;
  // **Welchen Artikel löst dieser hier ab?** Nur im Anlage-Modus – die Angabe hat genau
  // einen Moment (siehe `ArticleCreate.replaces_object_id`).
  const [replaces, setReplaces] = useState<Article | null>(null);

  // Shortcut «Auftrag»: das Anlage-Fenster mit diesem Artikel vorgewählt öffnen, ohne Datensatz.
  // Vorgemerkt wird nur der Artikel – Menge, Herkunft und Ablauf entscheidet der Mensch.
  function createOrderShortcut() {
    if (isCreate || record?.object_id == null || record.status !== FREIGEGEBEN) return;
    onCreateOrder?.(record.object_id);
  }
  const [form, setForm] = useState<Form>(() => seedFrom(record, initial));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // **Der Entwurf lebt hier, nicht in der Datenbank.** Spezifikation und Prozess sind
  // zwei Hälften derselben Anlage: der Artikel entsteht erst, wenn beide stehen.
  const [steps, setSteps] = useState<ModuleDraft[]>([]);
  // Welche optionalen Felder werden angezeigt (mit Wert oder bewusst hinzugefügt)
  const [added, setAdded] = useState<AddKey[]>(() => {
    const s = seedFrom(record, initial);
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

  // Jeder gespeicherte Artikel ist freigegeben und schreibgeschützt (Änderung = neuer Artikel).
  const locked = !isCreate;

  // Pflichtfelder: Name, Mengeneinheit, Serialisierung, Grösse, Gewicht. Format-Fehler nur,
  // wenn befüllt; die «leer»-Pflicht steuert das `valid`-Gate.
  const errs = {
    name: validateName(form.name),
    size: form.size.trim() ? validateSize(form.size) : null,
    weight: form.weight_kg.trim() ? validateWeight(form.weight_kg) : null,
  };
  // Der Entwurf, wie ihn die Freigabe schickt. Was fehlt, sagt der Server
  // (``POST /erp/articles/validate``) – ein Massstab, nicht zwei.
  const payload: ArticleInput & { steps: unknown[] } = useMemo(() => ({
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
    is_service: form.kind === 'service',
    // **Zoll-Angaben** – Grossschreibung beim Ursprungsland, damit «ch» und «CH»
    // nicht zwei Länder sind (ISO-2 ist grossgeschrieben).
    hs_code: form.hs_code.trim() || null,
    origin_country: form.origin_country.trim().toUpperCase() || null,
    // **Ersetzen ist Teil der Anlage** – ein Vorgang, ein Aufruf: der Vorgänger zeigt
    // danach hierher UND ist ausser Betrieb.
    replaces_object_id: replaces?.object_id ?? null,
    steps: steps.map(toModulePayload),
  }), [form, steps, replaces]);

  // Freigebbarkeit beim Server erfragen, nicht selbst behaupten. Scheitert die Prüfung,
  // nennt der Knopf den Grund – freigeben lässt er dann nicht.
  const check = useDebouncedQuery({
    name: 'article', input: isCreate ? payload : null, ask: api.validateArticle,
    what: 'Prüfung des Artikels',
  });
  const missing: string[] | null = !isCreate ? null
    : check.data ? (check.data.missing ?? [])
      : check.error ? [`Prüfung nicht möglich – ${check.error.message}`] : null;

  /** **Freigeben = Anlegen**: ein Aufruf, eine Transaktion; erst hier entstehen Datensatz und Nummer. */
  async function release() {
    setSaving(true);
    setError(null);
    try {
      onSaved(await api.createArticle(payload));
      // Eine Ersetzung ändert **zwei** Datensätze – der Vorgänger ist jetzt inaktiv.
      if (replaces) onRefresh?.();
    } catch (e) {
      const msg = errorText(e, 'Freigabe fehlgeschlagen');
      setError(isTransient(msg) ? `${msg} – bitte erneut versuchen.` : msg);
    } finally {
      setSaving(false);
    }
  }

  // **Ein Entwurf hat keinen Zustand** – es gibt ihn ja noch nicht.
  const statusCfg = record ? articleStatus({ status: record.status }) : undefined;
  const blocked = missing != null && missing.length > 0;

  return (
    <div className="flex flex-col h-full bg-bg-1">
      {/* Kopf – die EINE Anatomie aller Datensatz-Fenster (`DetailHeader`). */}
      <DetailHeader
        type="article" title={form.name || null} placeholder="Neuer Artikel"
        objectId={isCreate ? null : record.object_id}
        objectIdText={isCreate ? '—' : undefined}
        objectIdHint={isCreate
          ? 'Die Objektnummer entsteht erst mit der Freigabe. Bis dahin existiert dieser Artikel nur in diesem Fenster.'
          : undefined}
        onBack={onBack}
        status={statusCfg}
        actions={isCreate ? (
          // Freigeben ist die Anlage; der Knopf sagt, was noch fehlt.
          <HeaderAction
            label="Freigeben"
            hint={blocked ? `Es fehlt: ${missing!.join(' · ')}`
              : 'Legt den Artikel an und vergibt die Objektnummer'}
            disabled={saving || blocked || missing == null}
            onClick={release}
          />
        ) : record.object_id != null ? (
          <>
            <HeaderSep />
            <LabelButton objectId={record.object_id} title={form.name || record.name} kind="Artikel" />
            {/* Shortcut «Auftrag» (nur freigegebene Artikel sind auftragsfähig). */}
            {record.status === FREIGEGEBEN && (
              <button className="erp-idbtn erp-idbtn-act" data-tip="Auftrag" data-tip-pos="bottom"
                aria-label="Auftrag zu diesem Artikel anlegen"
                onClick={createOrderShortcut}>
                <ClipboardPlus size={15} />
              </button>
            )}
          </>
        ) : undefined}
      />

      <div style={{ flex: 1, overflowY: 'auto', padding: '24px clamp(14px, 4vw, 28px) 88px', background: 'var(--bg-2)' }}>
        <DetailBody>
            {/* Wie steht dieser Artikel im Netz der anderen? Schmaler Streifen über der
                Spezifikation – dieselbe Stelle, an der man bei der Anlage den Vorgänger wählt. */}
            {isCreate ? (
              <ReplacesPicker value={replaces} onChange={setReplaces} />
            ) : (
              <ContextStrip objectId={record.object_id} />
            )}
            {locked ? (
              <SpecRead record={record!} form={form} />
            ) : (
              <div style={SPEC.card}>
                {/* Karten-Kopf «Spezifikation» + «+»-Knopf (nur Entwurf) für optionale Felder. */}
                <SpecHead icon={FileText} title="Spezifikation"
                  right={<SectionAddButton added={added} onAdd={addField} />} />
                {/* Standardmässig nur die Pflichtfelder; weitere über den «+»-Knopf. */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: 22 }}>
                  <NameField value={form.name} onChange={(v) => set('name', v)}
                    error={form.name.trim() ? errs.name : null} />
                  <IconPick label="Art" required value={form.kind} onChange={(v) => set('kind', v)} options={KIND_PICK} />
                  <div style={GRID2}>
                    <IconPick label="Mengeneinheit" required value={form.unit} onChange={(v) => set('unit', v)} options={UNIT_PICK} />
                    <IconPick label="Serialisierung" required value={form.serialization} onChange={(v) => set('serialization', v)} options={SERIAL_PICK} />
                  </div>
                  <div style={GRID2}>
                    <EditField name="size" label="Abmessungen (mm)" required value={form.size} onChange={(v) => set('size', v)} placeholder="z. B. 3x40x600" error={form.size ? errs.size : null} />
                    <EditField name="weight_kg" label="Gewicht (kg)" required value={form.weight_kg} onChange={(v) => set('weight_kg', v)} placeholder="z. B. 2.5" error={form.weight_kg ? errs.weight : null} />
                  </div>
                  {/* Bei Bedarf hinzugefügte optionale Felder + abgeleitete Auto-Werte (nur wenn vorhanden). */}
                  {added.length > 0 && (
                    <div style={SPEC.grid}>
                      {OPTIONAL_FIELDS.filter((f) => added.includes(f.key)).map((f) => (
                        <OptField key={f.key} f={f} form={form} onSet={set} onRemove={removeField} />
                      ))}
                    </div>
                  )}
                </div>
                {/* Kein «Zur Freigabe fehlt …»: der ausgegraute Knopf nennt den Grund im Hover.
                    Ein echter Fehler bleibt als Meldung. */}
                {error && (
                  <div style={{ font: '500 12.5px var(--font-body)', color: 'var(--danger)' }}>
                    {error}
                  </div>
                )}
              </div>
            )}

            {/* Der Bestand steht zwischen Spezifikation und Prozess: was der Artikel ist, was
                es davon gibt, wie er entsteht. Ohne Objektnummer steht hier nichts. */}
            {record?.object_id != null && (
              <div style={{ marginTop: 22 }}>
                <StockView scope={{ kind: 'article', objectId: record.object_id }} />
              </div>
            )}

            {/* Der Erzeugungsprozess direkt unter der Spezifikation – dieselbe Komponente wie im
                Auftrag (`ProcessDesigner`), ohne den Bereich der Einzelinstanzen (PROCESS_CORE.md §8.1). */}
            <div style={{ marginTop: 22 }}>
              <ArticleProcess
                articleObjectId={record?.object_id ?? null}
                draft={steps}
                setDraft={setSteps}
              />
            </div>
            {record?.object_id != null && <DocumentTiles objectId={record.object_id} />}
            {record?.object_id != null && (
              <div style={{ marginTop: 22, display: 'flex', flexDirection: 'column', gap: 16 }}>
                <SectionSep label="Verlauf" />
                <History objectId={record.object_id} />
              </div>
            )}
        </DetailBody>

      </div>
    </div>
  );
}

// Der Kopf kommt aus `detail-frame.DetailHeader` – hier bleibt nur die Karte.
// Freies Namensfeld mit Vorschlägen bereits verwendeter Namen (`services/article_names.py`),
// gegen Dubletten.
function NameField({ value, onChange, error }: {
  value: string; onChange: (v: string) => void; error?: string | null;
}) {
  const [open, setOpen] = useState(false);
  const boxRef = useRef<HTMLDivElement>(null);

  // Vorschläge entprellt laden, solange das Feld aktiv ist (leere Eingabe → häufigste Namen).
  const { hits: sugs } = useSearch<ArticleNameSuggestion>(value, open ? suggestNames : null,
    { delay: 200, minLength: 0 });

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
      <Input
        name="name"
        value={value}
        maxLength={ARTICLE_NAME_MAX_LENGTH}
        placeholder="Artikelname eingeben…"
        onChange={(v) => { onChange(v); setOpen(true); }}
        onFocus={() => setOpen(true)}
        className={inputCls}
        style={error ? { borderColor: 'color-mix(in srgb, var(--danger) 45%, transparent)' } : undefined}
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

// ─── Spezifikation: sektionierte Ansicht ────────────────────
// Symbol-Auswahl je Einheit/Serialisierung – «Symbol + Wort».
const UNIT_PICK = [
  { value: 'Stk', label: 'Stk.', icon: Package },
  { value: 'mm', label: 'mm', icon: Ruler },
  { value: 'm2', label: 'm²', icon: Square },
  { value: 'm3', label: 'm³', icon: Box },
  { value: 'kg', label: 'kg', icon: Scale },
  { value: 'l', label: 'l', icon: Droplet },
];
// **Ware oder Dienstleistung** – Vorgabe Ware. Daraus folgen im Zahlungsmodul Steuersatz
// und Lieferbedingung (Ware: Lieferadresse; Dienstleistung: Sitz des Empfängers).
const KIND_PICK = [
  { value: 'goods', label: 'Ware', icon: Package },
  { value: 'service', label: 'Dienstleistung', icon: Wrench },
];
const SERIAL_PICK = [
  { value: 'unit', label: 'Einzelteil', icon: Fingerprint },
  { value: 'batch', label: 'Charge', icon: Layers },
];
// Zwei-Spalten-Raster für gepaarte Eingaben – kollabiert auf Mobile auf eine Spalte.
const GRID2: React.CSSProperties = {
  display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 260px), 1fr))', gap: '22px 40px',
};

// Karten-Kopf und Lese-Unterabschnitt wohnen in `fields.tsx` (`SpecHead`/`SpecSection`) –
// die Anatomie jeder Spezifikations-Karte.
// Add-Menü: EIN Menü im Sektions-Kopf bietet alle noch nicht sichtbaren optionalen Felder an.
const ADD_MENU: { key: AddKey; label: string }[] =
  OPTIONAL_FIELDS.map((f) => ({ key: f.key as AddKey, label: f.label }));

// «Feld hinzufügen» als +-Symbol im Sektions-Kopf → Dropdown der noch nicht sichtbaren Felder.
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
        style={{ width: 28, height: 28, borderRadius: 'var(--r-sm)', border: '1px solid var(--border-2)', background: 'var(--bg-1)', color: 'var(--accent)', display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer' }}>
        <Plus size={16} />
      </button>
      {open && (
        <div style={{ position: 'absolute', top: 'calc(100% + 8px)', right: 0, zIndex: 30, width: 320, maxWidth: '80vw', background: 'var(--bg-1)', border: '1px solid var(--border-1)', borderRadius: 'var(--r-md)', boxShadow: 'var(--shadow-lg)', padding: 7, display: 'flex', flexDirection: 'column', gap: 2 }}>
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
        <Select name={f.key} value={form[f.key] === 'ja' ? 'ja' : ''} onChange={(v) => onSet(f.key, v)} className={inputCls}>
          <option value="">Nein</option>
          <option value="ja">Ja</option>
        </Select>
      ) : (
        <Input name={f.key} value={form[f.key]} placeholder={f.placeholder} onChange={(v) => onSet(f.key, v)} className={inputCls} />
      )}
    </div>
  );
}

// Eingabefeld-Klasse analog Design-`.fin`.
// Feld-Label der Spezifikation (Design `.lbl`); Pflicht-Stern in Marken-Rot.
function FieldLabel({ children, required }: { children: React.ReactNode; required?: boolean }) {
  return (
    <label style={{ ...MICRO_LABEL, display: 'block', color: 'var(--fg-3)', marginBottom: 9 }}>
      {children}{required && <span style={{ color: 'var(--inexxio-red)' }}> *</span>}
    </label>
  );
}

// Eingabe-Feld (Entwurf): Overline-Label + `.fin`-Input + Fehler/Hinweis.
function EditField({ name, label, value, onChange, placeholder, hint, error, required, full }: {
  name: string; label: string; value: string; onChange: (v: string) => void;
  placeholder?: string; hint?: string; error?: string | null; required?: boolean; full?: boolean;
}) {
  return (
    <div style={{ gridColumn: full ? '1 / -1' : undefined }}>
      <FieldLabel required={required}>{label}</FieldLabel>
      <Input name={name} value={value} placeholder={placeholder} onChange={onChange}
        className={inputCls} style={error ? { borderColor: 'color-mix(in srgb, var(--danger) 45%, transparent)' } : undefined} />
      {error ? <ErrorText msg={error} /> : hint ? (
        <div style={{ marginTop: 8, font: '500 12.5px var(--font-body)', color: 'var(--fg-4)' }}>{hint}</div>
      ) : null}
    </div>
  );
}

/**
 * **Schieberegler** für Mengeneinheit und Serialisierung: die Bewegung des Reiters zeigt den
 * Ausschluss; nur die aktive Option trägt ihr Wort, die übrigen sind Symbol mit Hover.
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
function SpecRead({ record, form }: { record: Article; form: Form }) {
  const has = (k: OptKey) => form[k].trim() !== '';
  const hasPhysical = !!record.size || record.weight_kg != null;
  // Bei wem beschafft wird, steht am Zahlungsmodul, nicht hier.
  return (
    <div style={SPEC.card}>
      {/* Karten-Kopf «Spezifikation» (ohne «+»-Knopf – freigegeben ist read-only). */}
      <SpecHead icon={FileText} title="Spezifikation" />
      {/* Basis-Gruppe ohne eigenen Unter-Kopf – der Karten-Kopf trägt sie. */}
      <div style={{ marginBottom: 8 }}>
        <div style={{ ...SPEC.grid, paddingTop: 2 }}>
          {/* Kein «Artikelname»: der Kopf trägt ihn; im Entwurf bleibt das Feld. */}
          <ReadField icon={Ruler} label="Mengeneinheit" value={unitLabel(record.unit)} />
          <ReadField icon={Fingerprint} label="Serialisierung" value={serializationLabel(record.serialization)} />
          <ReadField icon={Tag} label="Art" value={record.is_service ? 'Dienstleistung' : 'Ware'} />
          {has('surface') && <ReadField icon={Sparkles} label="Oberfläche" value={form.surface} />}
          {has('material') && <ReadField icon={Layers} label="Material" value={form.material} />}
          {has('supplier_article_number') && <ReadField icon={Hash} label="Bestellnummer" value={form.supplier_article_number} />}
          {has('min_order_qty') && <ReadField icon={Package} label="Mindestbestellmenge" value={form.min_order_qty} mono />}
          {has('safety_stock') && <ReadField icon={Shield} label="Sicherheitsbestand" value={form.safety_stock} mono />}
          {has('cad_url') && <ReadField icon={Link2} label="CAD-Link" link={form.cad_url} full />}
        </div>
      </div>
      {hasPhysical && (
        <SpecSection icon={Box} title="Physische Eigenschaften">
          {record.size && <ReadField icon={Scaling} label="Abmessungen" value={record.size} unit="mm" mono />}
          {record.weight_kg != null && (
            <ReadField icon={Weight} label="Gewicht" value={String(record.weight_kg)} unit="kg" mono />
          )}
        </SpecSection>
      )}
    </div>
  );
}

// ─── Umfeld: Reihe · wer verbaut mich · was fehlt mir ────────────────────────
// Wie steht dieser Artikel im Netz der anderen? Am Datensatz, nicht im Dialog; Auskünfte,
// keine Sperren. Schmaler Streifen: nicht prominent, aber sichtbar.

const STRIP: React.CSSProperties = {
  border: '1px solid var(--border-1)', borderRadius: 'var(--r-md)', background: 'var(--bg-1)',
  padding: '11px 14px', marginBottom: 18,
  display: 'flex', flexDirection: 'column', gap: 11,
};
const STRIP_LABEL: React.CSSProperties = { ...MICRO_LABEL, fontSize: 10, flex: 'none' };
// Innen enger als aussen: eine umgebrochene Zeile bleibt von der nächsten unterscheidbar.
const STRIP_ROW: React.CSSProperties = {
  display: 'flex', alignItems: 'center', columnGap: 10, rowGap: 3,
  flexWrap: 'wrap', minHeight: 20,
};

/** Ein anderer Artikel, wie ihn eine Auskunft nennt: Nummer + Name, Nummer klickbar. */
function LinkChip({ link, muted }: { link: ArticleLink; muted?: boolean }) {
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, minWidth: 0 }}>
      <ObjId value={link.object_id} />
      <span style={{
        font: '500 12px var(--font-body)', color: muted ? 'var(--fg-4)' : 'var(--fg-3)',
        overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: 180,
      }}>{link.name}</span>
    </span>
  );
}

function Arrow() {
  return <ArrowRight size={13} style={{ color: 'var(--fg-4)', flex: 'none' }} />;
}

/**
 * Die Auskunft lädt sich selbst (der Feed liefert `bom: null` = «nicht geladen»).
 * Neu gelesen wird über `lib/feed.TOUCHES`.
 */
function ContextStrip({ objectId }: { objectId: number | null }) {
  const full = useQuery({
    queryKey: qk.article(objectId ?? 0),
    queryFn: ({ signal }) => api.getArticle(objectId!, { signal }),
    enabled: objectId != null,
    meta: { what: 'Umfeld des Artikels' },
  }).data;

  if (!full) return null;
  const bom: ArticleBom | null | undefined = full.bom;
  const before = full.replaces ?? null;
  const after = full.replaced_by ?? null;
  const gaps = bom?.retired_inputs ?? [];
  if (!before && !after && gaps.length === 0) return null;

  return (
    <div style={STRIP}>
      {/* Die Reihe – wen dieser Artikel ablöst und wer ihn ablöst. */}
      {(before || after) && (
        <div style={STRIP_ROW}>
          <span style={STRIP_LABEL}>Reihe</span>
          {before && (<><LinkChip link={before} muted /><Arrow /></>)}
          <span style={{ font: '700 12px var(--font-body)', color: 'var(--fg-1)' }}
            data-tip="Dieser Artikel">dieser</span>
          {after && (<><Arrow /><LinkChip link={after} /></>)}
        </div>
      )}

      {/* «Wird verbaut in» ist vorerst ausgeblendet; die Ableitung (`services/bom.used_in`)
          bleibt und kommt ohne zweite Abfrage mit. */}

      {/* Was mir fehlt – transitiv, mit Weg und Nachfolger. Warnfarbe, keine Sperre. */}
      {gaps.map((g) => {
        const via = g.via ?? [];
        return (
        <div key={g.article.object_id} style={STRIP_ROW}>
          <span style={{ ...STRIP_LABEL, color: 'var(--warning)', display: 'inline-flex', alignItems: 'center', gap: 5 }}>
            <AlertTriangle size={12} /> Ausser Betrieb
          </span>
          <LinkChip link={g.article} />
          {via.length > 0 && (
            <span style={{ font: '500 11.5px var(--font-body)', color: 'var(--fg-4)', display: 'inline-flex', alignItems: 'center', gap: 5 }}
              data-tip="Der Weg durch die Stückliste bis dorthin">
              <Blocks size={12} />
              {via.map((v) => v.name).join(' › ')}
            </span>
          )}
          {g.replaced_by && (
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}
              data-tip="Nachfolger – die Stückliste eines neuen Artikels nennt ihn">
              <Arrow /><LinkChip link={g.replaced_by} />
            </span>
          )}
        </div>
        );
      })}
    </div>
  );
}

/** **Welchen Artikel löst dieser hier ab?** – nur bei der Anlage. Der gewählte Artikel zeigt
 *  danach hierher UND geht ausser Betrieb – ein Vorgang, ein Aufruf. */
function ReplacesPicker({ value, onChange }: {
  value: Article | null; onChange: (a: Article | null) => void;
}) {
  const [open, setOpen] = useState(false);
  if (!open && !value) {
    return (
      <button type="button" onClick={() => setOpen(true)}
        style={{
          display: 'inline-flex', alignItems: 'center', gap: 6, marginBottom: 18,
          border: 'none', background: 'none', padding: 0, cursor: 'pointer',
          font: '600 12px var(--font-body)', color: 'var(--accent)',
        }}
        data-tip="Der abgelöste Artikel geht dabei ausser Betrieb: er erzeugt nichts Neues mehr. Bestehende Stücke bleiben und lassen sich weiter ab Lager abwickeln – Neues entsteht hier.">
        <Plus size={13} /> Ersetzt einen Artikel
      </button>
    );
  }
  return (
    <div style={{ ...STRIP, gap: 8 }}>
      {/* Dasselbe Referenzfeld wie überall (`ObjectSelect`); «nichts» ist eine Zeile in der
          Liste. `object_id` ist hier immer gesetzt, die Auswahl verengt den Typ. */}
      <ObjectSelect<Article & { object_id: number }>
        label="Ersetzt Artikel"
        value={value?.object_id ?? null}
        selected={value?.object_id != null ? (value as Article & { object_id: number }) : null}
        kind="article"
        scanLabel="Artikel"
        emptyOption="Ohne Vorgänger anlegen"
        find={(q) => api.getArticles(q, 20)
          // Angeboten wird nur, was abgelöst werden kann (`articles.replaceable_problem`).
          .then((rows) => rows.filter(
            (a): a is Article & { object_id: number } => a.object_id != null && !a.replaced_by_id))}
        onChange={(_nr, opt) => { onChange(opt); if (!opt) setOpen(false); }}
      />
      {/* Was die Ablösung bewirkt – und was nicht (`articles.may_create`): «inaktiv» ist die
          Folge von `replaced_by_id`, kein Schalter; Stücke ab Lager bleiben verwendbar. */}
      <span style={{ font: '500 11.5px var(--font-body)', color: 'var(--fg-4)' }}>
        Der abgelöste Artikel geht mit der Freigabe ausser Betrieb – er erzeugt danach
        nichts Neues mehr. Seine vorhandenen Stücke laufen weiter und lassen sich ab Lager
        weiter verwenden, auch als Ersatzteil.
      </span>
    </div>
  );
}

// Symbole für die optionalen Felder (im Sektions-«+»-Menü).
const MENU_ICON: Record<string, React.ElementType> = {
  material: Layers, surface: Sparkles, min_order_qty: Package, safety_stock: Shield,
};



// Der Bestand ist `stock-view.tsx` – dasselbe Modul wie an der Instanz.

/**
 * **Der Erzeugungsprozess eines Artikels** – dieselbe Komponente wie im Auftrag
 * (`ProcessDesigner`), ohne Einzelinstanzen (PROCESS_CORE.md §8.1/§8.2). Im Entwurf lebt die
 * Liste im Browser; danach ist sie eingefroren – es gibt keinen Endpunkt, der sie ändert.
 */
/** Eingefroren nimmt niemand eine Änderung entgegen – eine Stelle, kein Literal je Aufruf. */
const NO_CHANGE = () => {};

function ArticleProcess({ articleObjectId, draft, setDraft }: {
  articleObjectId: number | null;
  draft: ModuleDraft[];
  setDraft: (m: ModuleDraft[]) => void;
}) {
  // Ein gespeicherter Artikel ist freigegeben – seine Vorlage wird nur noch gelesen.
  const query = useQuery({
    queryKey: qk.articleProcess(articleObjectId ?? 0),
    queryFn: ({ signal }) => api.getArticleProcess(articleObjectId!, { signal }),
    enabled: !!articleObjectId,
    staleTime: Infinity,
    meta: { what: 'Erzeugungsprozess' },
  });
  const proc = articleObjectId ? query.data ?? null : null;
  const err = query.error && !query.data ? query.error.message : null;

  const frozen = articleObjectId !== null;
  const steps: DiagramStep[] | undefined = frozen
    ? (proc?.steps ?? []).map((s) => ({
      id: s.id, moduleType: s.module_type, label: s.label,
      tone: s.tone, terminal: s.terminal,
    }))
    : undefined;

  // ►► **Der eingefrorene Stand ist derselbe Entwurf, nur unveränderlich.** ◄◄
  // `moduleFromConfig` bringt die Konfiguration zurück in die Eingabeform – derselbe Feldsatz,
  // gesperrt.
  const frozenModules: ModuleDraft[] = useMemo(
    () => (proc?.steps ?? []).map(
      (s) => moduleFromConfig(s.id, s.module_type,
                              s.config as Record<string, unknown> | null)),
    [proc],
  );

  return (
    <div>
      {err && (
        <p className="mb-3 text-sm px-3 py-2 rounded-ds-lg"
          style={{ color: 'var(--danger)', background: 'var(--danger-bg)' }}>{err}</p>
      )}
      <ProcessDesigner
        modules={frozen ? frozenModules : draft}
        // Eingefroren nimmt niemand eine Änderung entgegen; `fieldset[disabled]` meldet nichts.
        onChange={frozen ? NO_CHANGE : setDraft}
        frozen={frozen}
        readOnlySteps={steps}
      />
    </div>
  );
}
