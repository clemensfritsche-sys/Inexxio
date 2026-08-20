'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import {
  Package, FileText, Boxes, Trash2, Tag, AlertTriangle,
  Ruler, Box, Square, Scale, Droplet, Fingerprint, Layers,
  Scaling, Hash, Link2, Weight, Sparkles, Plus, Shield, Ban,
  ClipboardPlus, RotateCcw, ArrowRight, Blocks,
} from 'lucide-react';
import { api } from '@/lib/api';
import type { ArticleProcess as ArticleProcessType, Article, ArticleBom, ArticleInput, ArticleLink, ArticleStatus, ArticleUnit, ArticleSerialization, ArticleNameSuggestion } from '@/types';
import type { ModuleDraft } from '@/lib/modules';
import { toModulePayload } from '@/lib/modules';
import { ARTICLE_NAME_MAX_LENGTH } from '@/types';
import {
  unitLabel, serializationLabel, normalizeSize, normalizeWeight,
  validateName, validateSize, validateWeight,
} from '@/lib/article';
import { articleStatus } from '@/lib/record-status';
import type { DiagramStep } from '@/components/erp/process-diagram';
import { ProcessDesigner } from '@/components/erp/process-designer';
import { FREIGEGEBEN, INAKTIV } from '@/lib/process-status';
import { isVersionConflict } from '@/lib/optimistic';

import { ErrorText, SaveIndicator, IconSwitch, DetailHeader, HeaderAction, HeaderSep, SearchSelect, SPEC, SpecHead, SpecSection, ReadField } from '@/components/erp/fields';
import { ObjId } from '@/components/erp/obj-id';
import { StockView } from '@/components/erp/stock-view';
import { DetailTabs } from '@/components/erp/detail-tabs';
import { LabelButton } from '@/components/scan/object-label';

// Artikel-Lebenszyklus. **Es gibt keinen gespeicherten Entwurf mehr**: der Artikel
// entsteht erst mit seiner Freigabe (services/articles.py), und die verlangt beides –
// vollständige Spezifikation UND mindestens ein Prozessschrittmodul. Damit ist jeder
// vorhandene Artikel freigegeben und eingefroren.
//
// **Ausser Betrieb ist ein Zustand, kein Ende.** Hier stand «Inaktiv ist endgültig – kein
// Reaktivieren», und daraus folgte, dass es keine Gegenaktion gab. Es widersprach der
// Statusliste: `Status.terminal` gibt es nur auf der Stück-Achse, und «Inaktiv» trägt es
// nicht. Ein versehentlich stillgelegter Artikel wäre sonst für immer verloren – und der
// einzige Ausweg hiesse «dieselbe Sache noch einmal anlegen», also eine zweite Nummer.
//
// Es ist darum **ein Knopf in zwei Richtungen**, kein Dialog: was ein Ausserbetriebnehmen
// anrichtet, steht dauerhaft im Streifen über der Spezifikation («wird verbaut in») – und
// nicht in einem Fenster, das es einmal zeigt, dem, der klickt.

type TabKey = 'spezifikation' | 'bestand';

const TABS: { key: TabKey; label: string; icon: React.ElementType }[] = [
  { key: 'spezifikation', label: 'Spezifikation', icon: FileText },
  { key: 'bestand', label: 'Bestand', icon: Boxes },
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

// Vorübergehender Transportfehler (Server nicht erreichbar / Kaltstart) vs.
// fachlicher Fehler. Der API-Client wiederholt solche Anfragen bereits mehrfach;
// schlägt es danach noch fehl, bekommt der Nutzer einen Wiederhol-Hinweis.
function isTransient(msg: string): boolean {
  return /keine verbindung|server nicht erreichbar|netzwerkfehler|failed to fetch|networkerror|load failed/i.test(msg);
}

export function ArticleDetail({ record, onSaved, onBack, onRefresh, onCreateOrder }: {
  record: Article | null;          // null ⇒ Anlage-Modus
  onSaved: (a: Article) => void;
  onBack: () => void;
  /**
   * Den Feed neu laden. Nötig, weil eine **Ersetzung zwei** Datensätze verändert: der
   * Nachfolger entsteht, und der Vorgänger geht ausser Betrieb. `onSaved` meldet nur den
   * einen – ohne diesen Aufruf stünde der andere im Feed noch als freigegeben da.
   */
  onRefresh?: () => void;
  /** Shortcut «Auftrag» (#690): öffnet den Auftragsentwurf mit diesem Artikel vorgewählt. */
  onCreateOrder?: (articleObjectId: number) => void;
}) {
  const isCreate = record === null;
  const [tab, setTab] = useState<TabKey>('spezifikation');
  // **Welchen Artikel löst dieser hier ab?** Nur im Anlage-Modus – die Angabe hat genau
  // einen Moment (siehe `ArticleCreate.replaces_object_id`).
  const [replaces, setReplaces] = useState<Article | null>(null);

  // Shortcut «Auftrag»: das Anlage-Fenster mit diesem Artikel vorgewählt öffnen. Es
  // entsteht dabei **kein** Datensatz – einen Auftrag gibt es erst mit der Freigabe
  // (Testnotiz #386).
  //
  // **Vorgemerkt wird nur der Artikel** – wie an der Instanz nur die Instanz (#608): der
  // Knopf sagt, WORUM es geht; wie viel, woher und mit welchem Ablauf ist die Entscheidung,
  // und die trifft der Mensch. Eine vorausgefüllte «1» wäre eine Behauptung, die in den
  // meisten Fällen falsch ist und trotzdem freigebbar aussieht.
  function createOrderShortcut() {
    if (isCreate || record?.object_id == null || record.status !== FREIGEGEBEN) return;
    onCreateOrder?.(record.object_id);
  }
  // Optimistic Locking: zuletzt bekannter Stand (nur für den Statuswechsel).
  const verRef = useRef<string | null>(record?.updated_at ?? null);
  const [form, setForm] = useState<Form>(() => seedFrom(record));
  const [saving, setSaving] = useState(false);
  const [statusBusy, setStatusBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // **Der Entwurf lebt hier, nicht in der Datenbank.** Spezifikation und Prozess sind
  // zwei Hälften derselben Anlage: der Artikel entsteht erst, wenn beide stehen.
  const [steps, setSteps] = useState<ModuleDraft[]>([]);
  const [missing, setMissing] = useState<string[] | null>(null);
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

  // **Jeder gespeicherte Artikel ist freigegeben** und damit schreibgeschützt: es gibt
  // keinen Entwurf in der Datenbank mehr, also auch keinen Zustand, in dem man ihn noch
  // umbauen könnte (keine Versionierung – Änderung = neuer Artikel).
  const locked = !isCreate;

  // Gewicht wird read-only, sobald der Artikel verbaute Ressourcen hat: es ergibt
  // sich dann automatisch aus der Stückliste (über mehrere Ebenen, Backend).
  // Das aufsummierte Gewicht kam aus verbauten Ressourcen (Prozesslogik) – entfallen.
  const computedWeight: number | null = null;
  const weightIsComputed = false;

  // Pflichtfelder: Name, Mengeneinheit, Serialisierung, Grösse und Gewicht (Einheit/
  // Serialisierung tragen einen Default). Format-Fehler nur zeigen, wenn befüllt (nicht
  // aggressiv beim leeren Neuformular); die «leer»-Pflicht steuert das `valid`-Gate.
  const errs = {
    name: validateName(form.name),
    size: form.size.trim() ? validateSize(form.size) : null,
    weight: form.weight_kg.trim() ? validateWeight(form.weight_kg) : null,
  };
  // Der Entwurf, so wie ihn die Freigabe schickt. Was zur Freigabe fehlt, sagt der
  // **Server** (``POST /erp/articles/validate``) – nicht dieses Formular: sonst gäbe es
  // zwei Massstäbe für dieselbe Frage, und der schwächere entschiede, ob der Knopf leuchtet.
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
    // Beschaffungsquelle: nur das zum Modus passende Quellfeld senden.
    procurement_mode: (form.procurement_mode as 'supplier' | 'webshop') || 'supplier',
    default_supplier_id: form.procurement_mode === 'supplier' && form.default_supplier_id
      ? Number(form.default_supplier_id) : null,
    default_webshop_url: form.procurement_mode === 'webshop'
      ? (form.default_webshop_url.trim() || null) : null,
    // **Ersetzen ist Teil der Anlage** – ein Vorgang, ein Aufruf: der Vorgänger zeigt
    // danach hierher UND ist ausser Betrieb.
    replaces_object_id: replaces?.object_id ?? null,
    steps: steps.map(toModulePayload),
  }), [form, steps, replaces]);

  // Freigebbarkeit beim Server erfragen, nicht selbst behaupten.
  useEffect(() => {
    if (!isCreate) { setMissing(null); return; }
    let dead = false;
    const t = setTimeout(() => {
      api.validateArticle(payload)
        .then((v) => { if (!dead) setMissing(v.missing ?? []); })
        .catch(() => { if (!dead) setMissing(['Prüfung nicht erreichbar']); });
    }, 250);
    return () => { dead = true; clearTimeout(t); };
  }, [isCreate, payload]);

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

  // Welche Richtung der Lebenszyklus-Knopf zeigt. **Der Klick IST die Ausführung**
  // (Notiz #152): keine Rückfrage, weil es nichts Endgültiges zu bestätigen gibt –
  // derselbe Knopf führt zurück, und was der Wechsel ringsum bedeutet, steht dauerhaft im
  // Streifen darüber.
  const inactive = record?.status === INAKTIV;

  /**
   * **Freigeben = Anlegen.** Ein Aufruf, eine Transaktion: erst hier entsteht der
   * Datensatz und erst hier die Objektnummer. Bis dahin steht in der Datenbank nichts –
   * wer das Fenster verlässt, lässt keine Spur.
   */
  async function release() {
    setSaving(true);
    setError(null);
    try {
      onSaved(await api.createArticle(payload));
      // Eine Ersetzung ändert **zwei** Datensätze – der Vorgänger ist jetzt inaktiv.
      if (replaces) onRefresh?.();
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Freigabe fehlgeschlagen';
      setError(isTransient(msg) ? `${msg} – bitte erneut versuchen.` : msg);
    } finally {
      setSaving(false);
    }
  }

  // **Ein Entwurf hat keinen Zustand** – es gibt ihn ja noch nicht. Ein Wort dort wäre
  // eine Behauptung über einen Datensatz, den die Datenbank nicht kennt; früher stand
  // dafür «Entwurf», was genau diesen Datensatz voraussetzte.
  const statusCfg = record ? articleStatus({ status: record.status }) : undefined;
  const blocked = missing != null && missing.length > 0;

  return (
    <div className="flex flex-col h-full bg-bg-1">
      {/* Kopf – die EINE Anatomie aller Datensatz-Fenster (`DetailHeader`, Notiz #242). */}
      <DetailHeader
        type="article" title={form.name || null} placeholder="Neuer Artikel"
        objectId={isCreate ? null : record.object_id}
        objectIdText={isCreate ? '—' : undefined}
        objectIdHint={isCreate
          ? 'Die Objektnummer entsteht erst mit der Freigabe. Bis dahin existiert dieser Artikel nur in diesem Fenster.'
          : undefined}
        onBack={onBack}
        status={statusCfg}
        right={<SaveIndicator saving={saving} flash={false} />}
        actions={isCreate ? (
          // **Freigeben ist die Anlage.** Der Knopf sagt, was noch fehlt – ein stumm
          // graues «Freigeben» liesse den Nutzer suchen.
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
            {/* Shortcut «Auftrag»: aus dem freigegebenen Artikel direkt einen Auftrag
                auslösen (nur freigegebene Artikel sind auftragsfähig). */}
            {record.status === FREIGEGEBEN && (
              <button className="erp-idbtn erp-idbtn-act" data-tip="Auftrag" data-tip-pos="bottom"
                aria-label="Auftrag zu diesem Artikel anlegen"
                onClick={createOrderShortcut}>
                <ClipboardPlus size={15} />
              </button>
            )}
            {/* **Ein Knopf, zwei Richtungen** – wie am Benutzer-Datensatz. Der Zustand
                steht rechts als Badge; hier steht, was man tun kann. */}
            {inactive ? (
              <button className="erp-idbtn erp-idbtn-act" data-tip-pos="bottom"
                data-tip="Aktiv setzen – der Artikel erzeugt danach wieder neue Einzelinstanzen"
                aria-label="Aktiv setzen" disabled={statusBusy}
                onClick={() => changeStatus(FREIGEGEBEN)}>
                <RotateCcw size={15} />
              </button>
            ) : (
              <button className="erp-idbtn erp-idbtn-danger" data-tip-pos="bottom"
                data-tip="Inaktiv setzen – erzeugt keine neuen Einzelinstanzen mehr; bestehende laufen weiter"
                aria-label="Inaktiv setzen" disabled={statusBusy}
                onClick={() => changeStatus(INAKTIV)}>
                <Ban size={15} />
              </button>
            )}
          </>
        ) : undefined}
        tabs={<DetailTabs<TabKey> active={tab} onChange={setTab} tabs={TABS} />}
      >
      </DetailHeader>

      {/* Content */}
      {/* FIX: Enter im Container löst den Autosave-Flush aus – in TEXTAREAs (mehrzeilige
          Beschreibungen/Bild-URLs/Notizen) verschluckte preventDefault() aber jeden
          Zeilenumbruch. Textareas ausnehmen. */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '24px clamp(14px, 4vw, 28px) 88px', background: 'var(--bg-2)' }}>
        {tab === 'spezifikation' && (
          <div style={{ maxWidth: 880, marginInline: 'auto', width: '100%' }}>
            {/* **Wie steht dieser Artikel im Netz der anderen?** — Reihe (ersetzt /
                ersetzt durch), wer ihn verbaut, und was in seiner Stückliste ausser
                Betrieb ist. Bewusst ein schmaler Streifen **über** der Spezifikation:
                nicht zu prominent, aber ohne Klick sichtbar – und dieselbe Stelle, an
                der man bei der Anlage sagt, welchen Artikel dieser hier ablöst. */}
            {isCreate ? (
              <ReplacesPicker value={replaces} onChange={setReplaces} />
            ) : (
              <ContextStrip objectId={record.object_id} version={record.updated_at} />
            )}
            {locked ? (
              <SpecRead record={record!} form={form} weightIsComputed={weightIsComputed} computedWeight={computedWeight} />
            ) : (
              <div style={SPEC.card}>
                {/* Karten-Kopf «Spezifikation» + «+»-Knopf (nur Entwurf) für optionale Felder. */}
                <SpecHead icon={FileText} title="Spezifikation"
                  right={<SectionAddButton added={added} onAdd={addField} />} />
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
                  {added.length > 0 && (
                    <div style={SPEC.grid}>
                      {OPTIONAL_FIELDS.filter((f) => added.includes(f.key)).map((f) => (
                        <OptField key={f.key} f={f} form={form} onSet={set} onRemove={removeField} />
                      ))}
                    </div>
                  )}
                </div>
                {/* **Kein «Zur Freigabe fehlt …»** (Testnotiz #692). Der ausgegraute Knopf
                    im Kopf ist die Information – und er nennt den Grund im Hover, dort wo
                    man ihn sucht. Derselbe Satz ein zweites Mal in der Fläche sagt nichts
                    Neues. Ein echter **Fehler** bleibt: der ist keine Anleitung, sondern
                    eine Meldung. */}
                {error && (
                  <div style={{ font: '500 12.5px var(--font-body)', color: 'var(--danger)' }}>
                    {error}
                  </div>
                )}
              </div>
            )}

            {/* **Der Erzeugungsprozess steht direkt unter der Spezifikation** (Notiz #671).
                Ein eigener Reiter dafür war eine Trennung, die es fachlich nicht gibt:
                beide Hälften gehören zur selben Anlage, und der Artikel entsteht erst,
                wenn sie zusammen vollständig sind. Es ist **dieselbe** Komponente wie im
                Auftrag (`ProcessDesigner`) – nur ohne den Bereich darüber, in dem der
                Auftrag seine Einzelinstanzen definiert (PROCESS_CORE.md §8.1). */}
            <div style={{ marginTop: 22 }}>
              <ArticleProcess
                articleObjectId={record?.object_id ?? null}
                draft={steps}
                setDraft={setSteps}
              />
            </div>
          </div>
        )}

        {/* **Derselbe Bestand wie an der Instanz** – EIN Modul, zwei Umfänge
            (`stock-view.tsx`). Ohne Objektnummer gibt es den Artikel noch nicht, also
            auch nichts von ihm. */}
        {tab === 'bestand' && (
          <div style={{ maxWidth: 880, marginInline: 'auto', width: '100%' }}>
            {record?.object_id != null ? (
              <StockView scope={{ kind: 'article', objectId: record.object_id }} />
            ) : (
              <p className="text-sm text-fg-3">
                Noch kein Bestand – der Artikel entsteht mit seiner Freigabe.
              </p>
            )}
          </div>
        )}

      </div>
    </div>
  );
}

// Kopf-/Chrome-Styles (Inexxio Design System, analog Instanz-Detail)
// Der Kopf kommt aus `fields.DetailHeader` (Notiz #242) – hier bleibt nur die Karte.
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

// Karten-Kopf und Lese-Unterabschnitt wohnen in `fields.tsx` (`SpecHead`/`SpecSection`) –
// sie sind die Anatomie JEDER Spezifikations-Karte, nicht die des Artikels: der Bestand
// benutzt denselben Kopf, und zwei fast gleiche Köpfe wären zwei Gestaltungen.

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
  return (
    <div style={SPEC.card}>
      {/* Karten-Kopf «Spezifikation» (ohne «+»-Knopf – freigegeben ist read-only). */}
      <SpecHead icon={FileText} title="Spezifikation" />
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
        <SpecSection icon={Box} title="Physische Eigenschaften">
          {record.size && <ReadField icon={Scaling} label="Abmessungen" value={record.size} unit="mm" mono />}
          {(weightIsComputed || record.weight_kg != null) && (
            <ReadField icon={Weight} label="Gewicht" value={weightIsComputed ? fmtWeight(computedWeight!) : String(record.weight_kg)}
              unit={weightIsComputed ? 'kg (berechnet)' : 'kg'} mono />
          )}
        </SpecSection>
      )}
    </div>
  );
}

// ─── Umfeld: Reihe · wer verbaut mich · was fehlt mir ────────────────────────
//
// **Drei Auskünfte, eine Frage:** wie steht dieser Artikel im Netz der anderen? Sie
// gehören an den Datensatz und nicht in einen Dialog – ein Dialog zeigt sie einmal, dem,
// der klickt; der Datensatz zeigt sie immer, allen. Und sie sind **Auskünfte, keine
// Sperren**: ein Artikel mit einem ausser Betrieb genommenen Teil in der Stückliste
// bleibt erzeugbar, solange Restbestand da ist.
//
// Gestaltet als schmaler Streifen: Haarlinie, gedämpfte Schrift, Versalien-Mikro-Label –
// «nicht zu prominent, aber so, dass man es trotzdem sieht».

const STRIP: React.CSSProperties = {
  border: '1px solid var(--border-1)', borderRadius: 'var(--r-md)', background: 'var(--bg-1)',
  padding: '11px 14px', marginBottom: 18,
  display: 'flex', flexDirection: 'column', gap: 11,
};
const STRIP_LABEL: React.CSSProperties = {
  font: '700 10px var(--font-body)', textTransform: 'uppercase', letterSpacing: '.07em',
  color: 'var(--fg-4)', flex: 'none',
};
// **Innen enger als aussen.** Bricht eine Zeile auf einem Telefon um, muss man ihre
// Fortsetzung von der nächsten Zeile unterscheiden können – wären beide Abstände gleich,
// läse sich «100000318 Antriebseinheit» wie eine neue Auskunft statt wie der Rest der
// vorigen.
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
 * **Die Auskunft lädt sich selbst.** Der Feed liefert den Artikel ohne Umfeld (`bom` ist
 * dort `null` = «nicht geladen»), und das ist richtig so: zwei Abfragen je Artikel wären
 * im Feed zweihundert. Also holt der Streifen das Detail, wenn er gebraucht wird – wie
 * `ArticleProcess` und `StockView` daneben.
 *
 * `version` ist der `updated_at`-Stand: nach einem Statuswechsel ändert sich das Umfeld
 * (wer diesen Artikel verbaut, sieht ihn ab jetzt als Lücke), also wird neu gelesen.
 */
function ContextStrip({ objectId, version }: { objectId: number | null; version?: string }) {
  const [full, setFull] = useState<Article | null>(null);
  useEffect(() => {
    if (objectId == null) { setFull(null); return; }
    let dead = false;
    api.getArticle(objectId)
      .then((a) => { if (!dead) setFull(a); })
      .catch(() => { if (!dead) setFull(null); });
    return () => { dead = true; };
  }, [objectId, version]);

  if (!full) return null;
  const bom: ArticleBom | null | undefined = full.bom;
  const before = full.replaces ?? null;
  const after = full.replaced_by ?? null;
  const usedIn = bom?.used_in ?? [];
  const gaps = bom?.retired_inputs ?? [];
  if (!before && !after && usedIn.length === 0 && gaps.length === 0) return null;

  return (
    <div style={STRIP}>
      {/* **Die Reihe** – wen dieser Artikel ablöst und wer ihn ablöst. Eine Zeile, weil
          es eine Kette ist: das Bild sagt die Richtung, ohne dass ein Wort sie erklärt. */}
      {(before || after) && (
        <div style={STRIP_ROW}>
          <span style={STRIP_LABEL}>Reihe</span>
          {before && (<><LinkChip link={before} muted /><Arrow /></>)}
          <span style={{ font: '700 12px var(--font-body)', color: 'var(--fg-1)' }}
            data-tip="Dieser Artikel">dieser</span>
          {after && (<><Arrow /><LinkChip link={after} /></>)}
        </div>
      )}

      {/* **Wer mich verbaut** – die Antwort auf «was mache ich kaputt, wenn ich diesen
          Artikel inaktiv setze». Sie steht darum bei der Aktion, nicht hinter ihr. */}
      {usedIn.length > 0 && (
        <div style={STRIP_ROW}>
          <span style={STRIP_LABEL} data-tip="Artikel, deren Stückliste diesen hier nennt">
            Wird verbaut in
          </span>
          {usedIn.map((a) => <LinkChip key={a.object_id} link={a} />)}
        </div>
      )}

      {/* **Was mir fehlt** – transitiv, mit dem Weg dorthin und dem Nachfolger, falls es
          einen gibt. Warnfarbe, aber keine Sperre: der Artikel bleibt erzeugbar. */}
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

/** **Welchen Artikel löst dieser hier ab?** – nur bei der Anlage, an derselben Stelle,
 *  an der später die Reihe steht.
 *
 *  Die Angabe steht am **Nachfolger**, weil sie genau einen Moment hat. Wirkung: der
 *  gewählte Artikel zeigt danach hierher UND geht ausser Betrieb – ein Vorgang, ein
 *  Aufruf, keine zweite Gelegenheit, die Hälfte zu vergessen.
 */
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
        data-tip="Der abgelöste Artikel geht dabei ausser Betrieb">
        <Plus size={13} /> Ersetzt einen Artikel
      </button>
    );
  }
  return (
    <div style={{ ...STRIP, gap: 8 }}>
      <div style={{ display: 'flex', alignItems: 'flex-end', gap: 8 }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <SearchSelect
            label="Ersetzt Artikel"
            value={value ? String(value.object_id) : ''}
            options={value ? [{ value: String(value.object_id), label: `${value.object_id} · ${value.name}` }] : []}
            placeholder="Nummer oder Name suchen…"
            search={async (q) => {
              const rows = await api.getArticles(q, 20);
              // **Angeboten wird nur, was auch abgelöst werden kann** – ein bereits
              // ersetzter Artikel würde von der Freigabe abgewiesen, und eine Auswahl,
              // die danach scheitert, ist keine.
              return rows
                .filter((a) => a.object_id != null && !a.replaced_by_id)
                .map((a) => ({ value: String(a.object_id), label: `${a.object_id} · ${a.name}` }));
            }}
            onChange={async (v) => {
              if (!v) { onChange(null); return; }
              try { onChange(await api.getArticle(Number(v))); } catch { onChange(null); }
            }}
          />
        </div>
        {/* Zurücknehmen – solange nichts freigegeben ist, ist es eine Angabe wie jede
            andere und muss sich löschen lassen. */}
        <button type="button" className="erp-idbtn" data-tip="Ohne Vorgänger anlegen"
          aria-label="Vorgänger entfernen"
          onClick={() => { onChange(null); setOpen(false); }}>
          <Trash2 size={14} />
        </button>
      </div>
      <span style={{ font: '500 11.5px var(--font-body)', color: 'var(--fg-4)' }}>
        Der abgelöste Artikel geht mit der Freigabe ausser Betrieb – er erzeugt danach
        nichts Neues mehr, seine Stücke laufen weiter.
      </span>
    </div>
  );
}

// Symbole für die optionalen Felder (im Sektions-«+»-Menü).
const MENU_ICON: Record<string, React.ElementType> = {
  material: Layers, surface: Sparkles, min_order_qty: Package, safety_stock: Shield,
};



// Der Reiter «Bestand» ist `stock-view.tsx` – **dasselbe Modul**, das die Instanz zeigt,
// nur mit dem grösseren Umfang. Hier stand vorher eine zweite, kürzere Fassung, die nur
// eine Instanzliste lud; der Bestand ist eine eigene Frage mit drei Ebenen, und sie zur
// Hälfte im Artikel-Detail zu beantworten hiesse, sie an zwei Stellen zu pflegen.

/**
 * **Der Erzeugungsprozess eines Artikels** – die Vorlage: wie ein Stück entsteht.
 *
 * Es ist **dieselbe Komponente wie im Auftrag** (`ProcessDesigner`), nicht eine zweite
 * Implementierung. Der einzige Unterschied ist der fehlende Bereich darüber: welche
 * Einzelinstanzen durchlaufen, entscheidet ausschliesslich der Auftrag. Ein Artikel hat
 * keine, und ein Editor, der sie voraussetzt, wäre hier nicht wiederverwendbar
 * (PROCESS_CORE.md §8.1/§8.2).
 *
 * **Im Entwurf lebt die Liste im Browser** – wie der Auftragsentwurf, und aus demselben
 * Grund: der Artikel entsteht erst mit der Freigabe. Danach ist sie eingefroren; einen
 * Endpunkt, der sie nachträglich ändert, gibt es nicht – die Eingefrorenheit ist also
 * kein bewachtes Verbot, sondern ein fehlendes Bedienelement.
 */
function ArticleProcess({ articleObjectId, draft, setDraft }: {
  articleObjectId: number | null;
  draft: ModuleDraft[];
  setDraft: (m: ModuleDraft[]) => void;
}) {
  const [proc, setProc] = useState<ArticleProcessType | null>(null);
  const [err, setErr] = useState<string | null>(null);

  // Ein gespeicherter Artikel ist freigegeben – seine Vorlage wird nur noch gelesen.
  useEffect(() => {
    if (!articleObjectId) { setProc(null); return; }
    let dead = false;
    api.getArticleProcess(articleObjectId)
      .then((p) => { if (!dead) setProc(p); })
      .catch((e) => { if (!dead) setErr(e instanceof Error ? e.message : String(e)); });
    return () => { dead = true; };
  }, [articleObjectId]);

  const frozen = articleObjectId !== null;
  const steps: DiagramStep[] | undefined = frozen
    ? (proc?.steps ?? []).map((s) => ({
      id: s.id, moduleType: s.module_type, label: s.label,
      tone: s.tone, terminal: s.terminal,
    }))
    : undefined;

  return (
    <div>
      {err && (
        <p className="mb-3 text-sm px-3 py-2 rounded-ds-lg"
          style={{ color: 'var(--danger)', background: 'var(--danger-bg)' }}>{err}</p>
      )}
      <ProcessDesigner
        modules={draft}
        onChange={setDraft}
        frozen={frozen}
        readOnlySteps={steps}
      />
    </div>
  );
}
