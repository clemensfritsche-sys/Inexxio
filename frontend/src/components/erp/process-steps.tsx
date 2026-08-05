'use client';

import { Lane } from '@/components/erp/flow-line';

import { useEffect, useMemo, useState } from 'react';
import { Trash2, User as UserIcon, Info, Check, GripVertical, X, Lock, Wrench, PackageMinus, Play, Flag, Globe, Building2, Ban, Users as UsersIcon, Shield, Ruler, ThumbsUp, Type, Camera, PenLine, Percent } from 'lucide-react';
import { api } from '@/lib/api';
import type { Article, ArticleProcessStep, ArticleProcessStepInput, ArticleProcessStepUpdateInput, CaptureField, DocAudienceRole, Instance, LocationType, ProcessStepMode, ResourceMode, StepType, UserProfile } from '@/types';
import { formatObjectId, userDisplayName } from '@/lib/utils';
import { unitLabel } from '@/lib/article';
import { STEP_META, locationTypeLabel, instanceLabel } from '@/lib/process';
import { SUPPLIER_FIELD_CATALOG, MANDATORY_FIELD_KEYS, normalizeSharedFields, fieldLabel } from '@/lib/article-fields';
import { apiStepStore, type StepStore } from '@/lib/step-store';
import { ErrorText, IconSwitch, InfoHint, Label, Palette, PaletteButton, Segmented, SearchSelect, TextField, numericOnly, numericInputProps } from '@/components/erp/fields';

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
// **Jedes Prozessschrittmodul ist universell einsetzbar** – am Artikel wie am Auftrag
// (Notiz #246, Spiegel von `domain/event_types.STEP_TYPES_BY_OWNER`). «Sperren» war zuvor
// in KEINER Liste und damit gar nicht wählbar.
const STEP_ORDER: StepType[] = ['purchase', 'resource', 'inspection', 'movement', 'scrap', 'sale', 'document'];
// «Sperren» ist kein eigener Palette-Eintrag mehr: es ist die zweite Wirkung desselben
// Moduls «Aussondern» und wird IM Editor gewählt (Notiz #277).

export function ProcessSteps({ owner, ownerObjectId, store, suppliers = [], readOnly = false, onStepsCount, selfArticleObjectId = null }: {
  owner: 'articles' | 'orders';          // Prozess am Artikel (Entstehung) oder am Auftrag (CUSTOM)
  ownerObjectId: number | null;          // Objektnummer des Trägers
  /** **Woher die Schritte kommen** – ohne Angabe die API des Trägers. Ein Auftrags-Entwurf
   *  reicht hier seinen Browser-Speicher herein: ihn gibt es in der Datenbank noch nicht
   *  (Testnotiz #386), der Editor ist trotzdem derselbe. */
  store?: StepStore;
  suppliers?: UserProfile[];             // Auswahl der Bezugsquelle direkt im Beschaffungs-Schritt
  readOnly?: boolean;
  onStepsCount?: (n: number) => void;
  selfArticleObjectId?: number | null;   // Artikel des Trägers (Ressource-Selbst-Ausschluss)
}) {
  // **Der Speicher, nicht die Komponente, weiss wohin geschrieben wird.** Ohne `store`
  // (der Normalfall) ist es die API des Trägers; ein Auftrags-Entwurf reicht seinen
  // Browser-Speicher herein. `null` = noch kein Träger → der Editor ruht.
  const repo = useMemo<StepStore | null>(
    () => store ?? (ownerObjectId != null ? apiStepStore(owner, ownerObjectId) : null),
    [store, owner, ownerObjectId],
  );
  const [steps, setSteps] = useState<ArticleProcessStep[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // Nachschlage-Listen, die die Karten brauchen (Ziel-/Ressourcen-/Parteien-Auswahl).
  const [company, setCompany] = useState<{ objectId: number; name: string } | null>(null);
  const [allUsers, setAllUsers] = useState<UserProfile[]>([]);
  const [allInstances, setAllInstances] = useState<Instance[]>([]);
  const [articles, setArticles] = useState<Article[]>([]);
  const [drag, setDrag] = useState<number | null>(null);
  const [over, setOver] = useState<number | null>(null);

  useEffect(() => {
    if (!repo) return;
    setLoading(true);
    repo.list().then(setSteps).catch(() => {}).finally(() => setLoading(false));
    // Das Unternehmen («im Betrieb») für den editierbaren Wareneingang-Zielselektor
    api.getPublicSettings()
      .then((c) => { if (c.object_id != null) setCompany({ objectId: c.object_id, name: c.company_name || 'Im Betrieb' }); })
      .catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [owner, ownerObjectId, store]);

  // Schrittanzahl an das Elternfenster melden. Sie IST zugleich die Auftragsart: ein
  // eigener Ablauf greift auf vorhandenen Bestand zu, keiner fährt den Artikel-Prozess
  // und nur DER erzeugt (Testnotiz #622). Darum kein zweiter Wert mehr.
  useEffect(() => {
    onStepsCount?.(steps.length);
  }, [steps, onStepsCount]);

  // **Nachgeladen wird nach dem, was DA ist** – nicht nach dem, was man gerade anlegt.
  // Seit ein Modul sofort im Fluss steht und dort konfiguriert wird (Testnotiz #635),
  // brauchen die Karten ihre Listen, solange es sie gibt: Personen für Bewegung und
  // Dokument, Instanzen als Bewegungsziel, Artikel für die Ressourcen-Zeilen. Auch
  // read-only – sonst stünden dort Objektnummern ohne Namen.
  const kinds = useMemo(() => new Set(steps.map((s) => s.step_type)), [steps]);
  useEffect(() => {
    if ((kinds.has('movement') || kinds.has('document')) && allUsers.length === 0) {
      api.getUsers().then(setAllUsers).catch(() => {});
    }
    if (kinds.has('movement') && allInstances.length === 0) {
      api.getInstances().then(setAllInstances).catch(() => {});
    }
    if (kinds.has('resource') && articles.length === 0) {
      api.getArticles().then(setArticles).catch(() => {});
    }
  }, [kinds, allUsers.length, allInstances.length, articles.length]);

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

  if (!repo) {
    return (
      <div style={noticeStyle}>
        <Info size={15} style={{ flexShrink: 0, marginTop: 1 }} />
        <span>Prozess zuerst wählen – danach lassen sich Schritte hinterlegen.</span>
      </div>
    );
  }

  // Nach Strukturänderungen die kanonische Liste neu laden (serverseitige Positionen).
  async function reload() {
    try { setSteps(await repo!.list()); } catch { /* ignore */ }
  }

  /**
   * **Ein Klick auf das Symbol legt das Modul an – fertig** (Testnotiz #635).
   *
   * Vorher führte derselbe Klick in ein Formular mit «Abbrechen» und «Hinzufügen»: zwei
   * Knöpfe, zwei Zustände (in Arbeit ↔ angelegt) und zwei Darstellungen desselben Moduls
   * (Formular ↔ Karte). Jetzt gibt es EINE Karte, und sie steht sofort im Fluss – dort,
   * wo sie auch später steht. Konfiguriert wird sie IN der Karte (Auto-Save wie überall),
   * weg kommt sie über den Papierkorb.
   *
   * Ein Modul startet dabei bewusst **unfertig** (eine Datenerfassung ohne Feld, eine
   * Beschaffung ohne Quelle). Das ist kein Verlust an Strenge, sondern eine Verschiebung
   * an die richtige Stelle: geprüft wird bei der **Freigabe** – die ist ohnehin das Gate,
   * ab dem der Prozess wirklich läuft, und sie nennt beim Namen, was noch fehlt.
   */
  async function addStep(type: StepType) {
    setError(null);
    try {
      await repo!.create({ step_type: type, ...defaultsFor(type, selfArticle) });
      await reload();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Fehler beim Anlegen');
    }
  }

  async function patchStep(stepId: number, patch: ArticleProcessStepUpdateInput) {
    try {
      const updated = await repo!.update(stepId, patch);
      setSteps((p) => p.map((s) => (s.id === stepId ? updated : s)));
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Fehler beim Speichern');
    }
  }

  async function removeStep(stepId: number) {
    try {
      await repo!.remove(stepId);
      await reload();
    } catch { /* ignore */ }
  }

  async function persistOrder(orderedFull: ArticleProcessStep[]) {
    setSteps(orderedFull);  // optimistisch
    const ids = orderedFull.map((s) => s.id);
    try { setSteps(await repo!.reorder(ids)); }
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
    // **Der Editor steht in derselben Spur wie der laufende Fluss** (Testnotiz #597): eine
    // feste Breite statt einer Obergrenze je Karte – sonst war ein Modul beim Hinzufügen,
    // nach dem Zwischenspeichern und nach der Freigabe verschieden breit, je nachdem wie
    // viel Platz gerade da war.
    // **Und sie steht in der Mitte** (Testnotiz #609): eine feste Breite richtet sich im
    // Block-Fluss links aus. Im laufenden Auftrag zentriert ``Row`` sie, beim Anlegen
    // eines gewöhnlichen Auftrags (ohne Halter, also ohne Rahmen) niemand.
    <div style={{ display: 'flex', justifyContent: 'center', width: '100%' }}>
    <Lane>
      {loading && <div style={{ fontSize: 13, color: 'var(--fg-4)' }}>Laden…</div>}

      {/* Start-Knoten (BPMN) – **immer**, auch bei leerem Prozess (Notiz #269): ohne ihn
          stand die Modul-Palette ohne Kontext da und man erkannte nicht, dass man hier
          einen Ablauf definiert. */}
      {(steps.length > 0 || !readOnly) && <FlowTerm kind="start" />}

      {steps.map((s, i) => (
        <div key={s.id} style={{ width: '100%', display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
          <Connector />
          <StepCard
            step={s} readOnly={readOnly}
            over={over === i && drag !== null && drag !== i}
            dragging={drag === i}
            onDragStart={() => { if (!readOnly) setDrag(i); }}
            onDragEnd={() => { setDrag(null); setOver(null); }}
            onDragOver={(e) => { if (!readOnly && drag !== null) { e.preventDefault(); setOver(i); } }}
            onDrop={(e) => { e.preventDefault(); onDrop(i); }}
            onPatch={(patch) => patchStep(s.id, patch)}
            onDelete={() => removeStep(s.id)}
            suppliers={suppliers} users={allUsers} instances={allInstances}
            articles={articles} company={company}
            optionalShareKeys={optionalShareKeys}
            selfArticleObjectId={selfArticleObjectId}
          />
        </div>
      ))}

      {/* **Die Palette steht IM Prozess, nicht dahinter** (Testnotiz #519): ein Modul wird
          in den Ablauf eingefügt – also liegt die Auswahl vor der Zielflagge, dort wo das
          nächste Modul hinkommt. Der Endknoten schliesst den Fluss danach ab.
          **Die Linie führt IMMER heran** (#557); **sie gehört zur Palette** (#599). */}
      {!readOnly && <Connector />}

      {/* **Die Palette steht offen** (Notiz #223): «jeder Klick ist ein Klick zu viel» –
          die verfügbaren Module liegen sichtbar am Ende des Flusses, ein Klick legt an. */}
      {!readOnly && (
        <div style={{ width: '100%' }}>
          <Palette>
            {STEP_ORDER.map((t) => {
              const m = STEP_META[t]; const kc = kindColor(t);
              return (
                <PaletteButton key={t} icon={m.icon} label={m.label}
                  tone={kc.fg} bg={kc.bg} border={kc.border} onClick={() => addStep(t)} />
              );
            })}
          </Palette>
          {error && <div style={{ marginTop: 8 }}><ErrorText msg={error} /></div>}
        </div>
      )}
      {/* Der Endknoten schliesst den Fluss ab – NACH der Auswahl (#519). */}
      {(steps.length > 0 || !readOnly) && (
        <>
          <Connector />
          <FlowTerm kind="end" />
        </>
      )}
    </Lane>
    </div>
  );
}

/**
 * **Womit ein Modul startet.** Nur das, was ohne Nachdenken richtig ist: die Beschaffung
 * erbt die Quelle des Artikels (falls gepflegt), die Datenerfassung prüft erst einmal
 * alles, das Dokument bleibt intern. Alles Weitere entscheidet der Mensch in der Karte.
 */
function defaultsFor(type: StepType, art: Article | null): Partial<ArticleProcessStepInput> {
  switch (type) {
    case 'purchase':
      return {
        mode: (art?.procurement_mode as ProcessStepMode) || 'supplier',
        supplier_id: art?.procurement_mode !== 'webshop' && art?.default_supplier_id != null
          ? art.default_supplier_id : null,
        webshop_url: art?.procurement_mode === 'webshop' ? (art?.default_webshop_url ?? null) : null,
        shared_fields: MANDATORY_FIELD_KEYS,
      };
    case 'inspection':
      // Ein Feld ist da – sonst stünde eine Datenerfassung ohne alles im Fluss. Es ist
      // dasselbe, das die Engine ohne Maske ohnehin erfassen würde (Gut/Schlecht);
      // umbenennen, ergänzen oder ersetzen kostet einen Klick.
      return { sample_percent: 100,
               capture_fields: [{ key: '', label: 'Gut/Schlecht', type: 'bool',
                                  target: null, tolerance: null, unit: null }] };
    case 'resource':
      return { resource_lines: [] };
    case 'document':
      return { doc_visibility: 'internal', sign_sequential: false };
    default:
      return {};
  }
}

/**
 * **Eine Karte, ein Layout – egal ob Entwurf oder freigegeben** (Testnotiz #635).
 *
 * Vorher gab es je Modul drei Darstellungen: das Anlage-Formular, die Karte im Entwurf
 * (Zusammenfassung in Stichworten) und die Karte im freigegebenen Prozess. Drei Layouts
 * für dieselbe Sache – und beim Anfassen liefen sie auseinander.
 *
 * Jetzt zeigt die Karte **immer** dieselben Felder; ist der Träger freigegeben, sind sie
 * schlicht **gesperrt** (`fieldset[disabled]` – eine Zeile statt eines zweiten Layouts).
 * Geändert wird per **Auto-Save**, wie in jedem anderen Fenster des ERP.
 */
function StepCard({
  step, readOnly, over, dragging, onDragStart, onDragEnd, onDragOver, onDrop, onPatch,
  onDelete, suppliers, users, instances, articles, company, optionalShareKeys,
  selfArticleObjectId,
}: {
  step: ArticleProcessStep;
  readOnly: boolean;
  over: boolean; dragging: boolean;
  onDragStart: () => void; onDragEnd: () => void;
  onDragOver: (e: React.DragEvent) => void; onDrop: (e: React.DragEvent) => void;
  onPatch: (patch: ArticleProcessStepUpdateInput) => void;
  onDelete: () => void;
  suppliers: UserProfile[]; users: UserProfile[]; instances: Instance[]; articles: Article[];
  company: { objectId: number; name: string } | null;
  optionalShareKeys: string[];
  selfArticleObjectId: number | null;
}) {
  const type = step.step_type as StepType;
  const meta = STEP_META[type] ?? STEP_META.purchase;
  const Icon = meta.icon;
  const kc = kindColor(type);
  return (
    <div
      draggable={!readOnly}
      onDragStart={onDragStart} onDragEnd={onDragEnd} onDragOver={onDragOver} onDrop={onDrop}
      style={{
        position: 'relative', width: '100%',
        border: `1px solid ${over ? 'var(--accent)' : kc.border}`,
        borderRadius: 'var(--r-lg)', background: kc.bg,
        boxShadow: over ? '0 0 0 3px var(--accent-soft)' : 'var(--shadow-sm)',
        opacity: dragging ? 0.4 : 1, transition: 'box-shadow .16s,border-color .16s',
      }}
    >
      {/* Kopf: Symbol-Kachel + Titel + Löschen. Dieselbe Anatomie wie die Karte im
          laufenden Fluss (`order-flow.StepCard`, Notiz #597). */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '13px 16px' }}>
        {!readOnly && <GripVertical size={16} style={{ color: 'var(--border-2)', cursor: 'grab', flexShrink: 0 }} />}
        <div style={{ width: 34, height: 34, borderRadius: 'var(--r-sm)', flexShrink: 0, background: '#fff', color: kc.fg, border: `1px solid ${kc.border}`, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <Icon size={17} />
        </div>
        <span style={{ flex: 1, minWidth: 0, font: '800 15px var(--font-display)', letterSpacing: '-.01em', color: 'var(--fg-1)' }}>
          {meta.label}
        </span>
        {!readOnly && (
          <button onClick={onDelete} data-tip="Modul entfernen" aria-label="Modul entfernen" style={delBtn}><Trash2 size={15} /></button>
        )}
      </div>

      {/* **Der Inhalt ist immer derselbe – gesperrt statt nachgebaut.** `fieldset[disabled]`
          nimmt jedem Feld darin nativ die Bedienbarkeit; es braucht dafür kein zweites
          Layout und keine `disabled`-Kette durch jede Komponente. */}
      <fieldset disabled={readOnly}
        style={{ border: 'none', margin: 0, padding: 0, minWidth: 0,
          opacity: readOnly ? 0.85 : 1 }}>
        <StepBody step={step} type={type} readOnly={readOnly} onPatch={onPatch}
          suppliers={suppliers} users={users} instances={instances} articles={articles}
          company={company} optionalShareKeys={optionalShareKeys}
          selfArticleObjectId={selfArticleObjectId} />
      </fieldset>
    </div>
  );
}

/** Der Inhalt einer Modul-Karte – je Typ genau seine Felder, sonst nichts. */
function StepBody({
  step, type, readOnly, onPatch, suppliers, users, instances, articles, company,
  optionalShareKeys, selfArticleObjectId,
}: {
  step: ArticleProcessStep; type: StepType; readOnly: boolean;
  onPatch: (patch: ArticleProcessStepUpdateInput) => void;
  suppliers: UserProfile[]; users: UserProfile[]; instances: Instance[]; articles: Article[];
  company: { objectId: number; name: string } | null;
  optionalShareKeys: string[];
  selfArticleObjectId: number | null;
}) {
  if (type === 'purchase') {
    const mode = (step.mode as ProcessStepMode) || 'supplier';
    return (
      <div style={cardBody}>
        {/* Die Bezugsquelle wird HIER festgelegt (Lieferant ODER Webshop-Link), je Schritt
            eigen – kein «erben» mehr (#166). Das Symbol des Lieferanten ist ein Gebäude,
            nicht ein Lastwagen (#164): gemeint ist die Firma, nicht der Transport. */}
        <div>
          <Label>Bezugsquelle</Label>
          <IconSwitch<ProcessStepMode> symbolOnly value={mode}
            onChange={(v) => onPatch({ mode: v, ...(v === 'supplier' ? { webshop_url: null } : { supplier_id: null }) })}
            options={[
              { value: 'supplier', icon: Building2, label: 'Lieferant', hint: 'Bestellung bei einem Lieferanten' },
              { value: 'webshop', icon: Globe, label: 'Webshop', hint: 'Kauf über einen Webshop-Link' },
            ]} />
        </div>
        {mode === 'supplier' ? (
          <SearchSelect label="Lieferant" required
            value={step.supplier_id != null ? String(step.supplier_id) : ''}
            onChange={(v) => onPatch({ supplier_id: v ? Number(v) : null })}
            options={suppliers.filter((s) => s.object_id != null).map((s) => ({
              value: String(s.id), label: `${formatObjectId(s.object_id)} · ${userDisplayName(s)}` }))} />
        ) : (
          <AutoText label="Webshop-Link" required value={step.webshop_url ?? ''}
            placeholder="https://shop.example.com/artikel"
            onCommit={(v) => onPatch({ webshop_url: v.trim() || null })} />
        )}
        <div>
          <Label>Für Lieferant sichtbar</Label>
          <FieldChips value={normalizeSharedFields(step.shared_fields)}
            onChange={(v) => onPatch({ shared_fields: v })}
            optionalAvailable={optionalShareKeys} />
        </div>
      </div>
    );
  }

  if (type === 'scrap' || type === 'block') {
    // **Aussondern: EINE Entscheidung** – endgültig oder vorübergehend (#277). Symbol-only
    // wie die Bezugsquelle (#633); der Name steht im Hover, der Grund ist ohnehin Pflicht
    // und braucht keine Zeile in der Fläche (#634).
    return (
      <div style={cardBody}>
        <IconSwitch<'scrap' | 'block'> symbolOnly value={type}
          onChange={(v) => onPatch({ step_type: v })}
          options={[
            { value: 'scrap', icon: Trash2, label: 'Verschrotten', hint: 'Endgültig aus dem Bestand – die Instanz ist danach Ausschuss und standortlos.' },
            { value: 'block', icon: Lock, label: 'Sperren', hint: 'Vorübergehend nicht verwendbar – bleibt am Standort, wird an der Instanz wieder freigegeben.' },
          ]} />
      </div>
    );
  }

  if (type === 'inspection') {
    return (
      <div style={cardBody}>
        <SampleScope value={String(step.sample_percent ?? 100)}
          onChange={(v) => onPatch({ sample_percent: Math.trunc(Number(v) || 0) || 100 })} />
        <CaptureFieldsEditor fields={toWFields(step.capture_fields)}
          onChange={(f) => onPatch({ capture_fields: fromWFields(f) })} />
      </div>
    );
  }

  if (type === 'movement') {
    return (
      <div style={cardBody}>
        <SearchSelect label="Zielstandort (optional)"
          value={step.target_location_id ? `${step.target_location_type}:${step.target_location_id}` : ''}
          onChange={(v) => {
            const tgt = v ? v.split(':') : null;
            onPatch({ target_location_type: tgt ? (tgt[0] as LocationType) : null,
                      target_location_id: tgt ? Number(tgt[1]) : null });
          }}
          placeholder="Nicht definiert – Lagerist wählt beim Einlagern"
          options={[
            { value: '', label: 'Nicht definiert – Lagerist wählt beim Einlagern' },
            ...(company ? [{ value: `company:${company.objectId}`, label: `Im Betrieb · ${company.name}` }] : []),
            ...users.filter((u) => u.object_id != null).map((u) => ({
              value: `user:${u.object_id}`, label: `Person ${userDisplayName(u)} · ${formatObjectId(u.object_id)}` })),
            ...instances.filter((i) => i.object_id != null).map((i) => ({
              value: `instance:${i.object_id}`, label: `${instanceLabel()} ${formatObjectId(i.object_id)}` })),
          ]} />
      </div>
    );
  }

  if (type === 'resource') {
    return (
      <div style={cardBody}>
        <ResourceLinesEditor
          lines={(step.resource_lines ?? []).map((l) => ({
            article_id: String(l.article_id), quantity: String(l.quantity ?? 1),
            mode: (l.mode as ResourceMode) || 'consume' }))}
          onChange={(lines) => onPatch({ resource_lines: lines
            .filter((l) => l.article_id)
            .map((l) => {
              const q = Math.round((Number(l.quantity) || 1) * 1000) / 1000;
              return { article_id: Number(l.article_id), quantity: q > 0 ? q : 1, mode: l.mode };
            }) })}
          articles={articles.filter((a) => a.status === 'released' && a.object_id !== selfArticleObjectId)} />
      </div>
    );
  }

  if (type === 'document') {
    // Die **Struktur** der Freigabe (Parteien, Reihenfolge, Publikum, Sichtbarkeit) –
    // read-only als Liste mit Namen, sonst als Editor.
    return (
      <div style={cardBody}>
        {readOnly
          ? <DocConfigView step={step} users={users} />
          : <DocConfigEditor cfg={toDocCfg(step)} users={users}
              onChange={(cfg) => onPatch({
                doc_signers: cfg.signers.length ? cfg.signers : null,
                sign_sequential: cfg.sequential,
                doc_audience: cfg.audience || null,
                doc_audience_roles: cfg.audience === 'roles' ? (cfg.roles as DocAudienceRole[]) : null,
                doc_audience_person_ids: cfg.audience === 'persons' ? cfg.persons : null,
                doc_visibility: cfg.visibility,
              })} />}
      </div>
    );
  }

  // Verkauf trägt keine Konfiguration: Kunde, Betrag und Zahlung entstehen im Auftrag.
  return null;
}

/** Die Erfassungsfelder in die Formular-Form und zurück – eine Stelle, zwei Richtungen. */
function toWFields(fields: CaptureField[] | null | undefined): WField[] {
  return (fields ?? []).map((f) => ({
    label: f.label ?? '', type: (f.type as WField['type']) || 'measure',
    target: f.target != null ? String(f.target) : '',
    tolerance: f.tolerance != null ? String(f.tolerance) : '',
    unit: f.unit ?? '',
  }));
}

function fromWFields(fields: WField[]): CaptureField[] {
  return fields
    .filter((f) => f.label.trim())
    .map((f) => ({
      key: '', label: f.label.trim(), type: f.type,
      target: f.type === 'measure' && f.target.trim() !== '' ? Number(f.target) : null,
      tolerance: f.type === 'measure' && f.tolerance.trim() !== '' ? Number(f.tolerance) : null,
      unit: f.unit.trim() || null,
    }));
}

function toDocCfg(step: ArticleProcessStep): DocCfg {
  return {
    signers: (step.doc_signers ?? []).map((s) => ({
      signer_object_id: s.signer_object_id, action: (s.action as 'confirm' | 'sign') || 'sign' })),
    sequential: !!step.sign_sequential,
    audience: (step.doc_audience as DocCfg['audience']) || '',
    roles: (step.doc_audience_roles ?? []) as string[],
    persons: step.doc_audience_person_ids ?? [],
    visibility: (step.doc_visibility as DocCfg['visibility']) || 'internal',
  };
}

/**
 * Ein Textfeld, das **beim Verlassen** speichert (und mit Enter).
 *
 * Auto-Save wie überall – aber nicht bei jedem Tastendruck: ein halb getippter Link wäre
 * sonst zwischendurch eine ungültige Bezugsquelle.
 */
function AutoText({ label, value, placeholder, required, onCommit }: {
  label: string; value: string; placeholder?: string; required?: boolean;
  onCommit: (v: string) => void;
}) {
  const [draft, setDraft] = useState(value);
  useEffect(() => { setDraft(value); }, [value]);
  return (
    <TextField label={label} value={draft} onChange={setDraft} required={required}
      placeholder={placeholder}
      onBlur={() => { if (draft !== value) onCommit(draft); }}
      onKeyDown={(e) => { if (e.key === 'Enter') (e.target as HTMLInputElement).blur(); }} />
  );
}


// ─── Ressourcen-Zeilen (mini-BOM): Artikel + Menge + Modus-Toggle je Zeile ────
function ResourceLinesEditor({ lines, onChange, articles }: {
  lines: ResLine[]; onChange: (l: ResLine[]) => void; articles: Article[];
}) {
  // **Kein «hinzufügen»-Klick** (Notiz #231): unten steht immer eine leere Zeile bereit;
  // sobald sie einen Artikel bekommt, wächst die nächste nach. «Jeder Klick ist ein Klick
  // zu viel» – und leere Zeilen werden beim Speichern ohnehin verworfen.
  const rows: ResLine[] = [...lines, { article_id: '', quantity: '1', mode: 'consume' as ResourceMode }];
  function upd(i: number, patch: Partial<ResLine>) {
    const next = [...rows];
    next[i] = { ...next[i], ...patch };
    onChange(next.filter((l, idx) => l.article_id !== '' || idx < lines.length));
  }
  function del(i: number) { onChange(lines.filter((_, idx) => idx !== i)); }
  const options = [{ value: '', label: '— Artikel wählen —' },
    ...articles.map((a) => ({ value: String(a.id), label: `${formatObjectId(a.object_id)} · ${a.name}` }))];
  return (
    <div>
      <Label>Ressourcen</Label>
      {articles.length === 0 && (
        <div style={noticeStyle}><Info size={14} style={{ flexShrink: 0, marginTop: 1 }} /><span>Kein freigegebener Artikel referenzierbar.</span></div>
      )}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {rows.map((l, i) => {
          const tool = l.mode === 'tool';
          const isDraftRow = i === rows.length - 1;
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
              <button onClick={() => del(i)} disabled={isDraftRow} title="Zeile entfernen"
                style={{ border: 'none', background: 'none', color: 'var(--fg-4)', cursor: isDraftRow ? 'default' : 'pointer', opacity: isDraftRow ? 0 : 1 }}><Trash2 size={15} /></button>
            </div>
          );
        })}
      </div>
    </div>
  );
}

/**
 * **Prüfumfang: ein Anteil bekommt WORTE, keine geratenen Symbole** (Testnotiz #636).
 *
 * In der Praxis prüft man jedes Stück, jedes zweite, jedes vierte oder eine Handvoll – vier
 * Möglichkeiten, die keinen Erklärsatz brauchen. Nur: ein Anteil lässt sich nicht zeichnen
 * (#618). Zwei Anläufe mit Symbolen (Haken · Zeilen · Kolben) haben genau das bewiesen –
 * man musste sie raten, und ein Symbol, das man raten muss, ist keines.
 *
 * Also stehen die vier Möglichkeiten als Wort da. Das ist keine Ausnahme von «Symbole statt
 * Text», sondern dessen Kehrseite: das Symbol trägt, wo es die Sache ZEIGEN kann (Modul,
 * Bezugsquelle, Wirkung) – und wo nicht, ist das Wort die ehrlichere Antwort.
 *
 * Ein abweichender Wert (z. B. 7 %) bleibt möglich: «%» blendet das Zahlenfeld ein, und ein
 * bereits gespeicherter Sonderwert erscheint als eigene Option, statt still verlorenzugehen.
 */
const SAMPLE_PRESETS = [
  { pct: '100', label: 'Alle', hint: 'Jedes Stück wird geprüft (100 %)' },
  { pct: '50', label: 'Jedes 2.', hint: 'Jedes zweite Stück (50 %)' },
  { pct: '25', label: 'Jedes 4.', hint: 'Jedes vierte Stück (25 %)' },
  { pct: '10', label: 'Stichprobe', hint: 'Eine Handvoll (10 %)' },
];

function SampleScope({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  const isPreset = SAMPLE_PRESETS.some((p) => p.pct === value);
  const [custom, setCustom] = useState(!isPreset && value !== '');
  const chip = (active: boolean): React.CSSProperties => ({
    padding: '6px 11px', font: '600 12.5px var(--font-body)', borderRadius: 8,
    cursor: 'pointer', whiteSpace: 'nowrap',
    border: `1px solid ${active ? 'var(--accent)' : 'var(--border-2)'}`,
    background: active ? 'var(--accent-soft)' : '#fff',
    color: active ? 'var(--accent-ink)' : 'var(--fg-3)',
  });
  return (
    <div>
      <Label required>Prüfumfang</Label>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, alignItems: 'center' }}>
        {SAMPLE_PRESETS.map((p) => (
          <button key={p.pct} type="button" data-tip={p.hint}
            onClick={() => { setCustom(false); onChange(p.pct); }}
            style={chip(!custom && value === p.pct)}>
            {p.label}
          </button>
        ))}
        <button type="button" data-tip="Anderer Prüfumfang in Prozent"
          aria-label="Anderer Prüfumfang" onClick={() => setCustom(true)}
          style={{ ...chip(custom), display: 'inline-flex', alignItems: 'center' }}>
          <Percent size={14} />
        </button>
        {custom && (
          <input value={value} onChange={(e) => onChange(numericOnly(e.target.value, { decimals: false }))}
            {...numericInputProps} placeholder="z. B. 7"
            className="px-2.5 py-1.5 text-sm rounded-md border bg-white outline-none focus:ring-2 focus:ring-[var(--accent)]"
            style={{ borderColor: 'var(--border-1)', width: 76 }} />
        )}
      </div>
    </div>
  );
}

// ─── Datenerfassungs-Maske bearbeiten ─────────────────────────────────────────
//
// **Dieselbe Geste wie beim Prozessschritt** (Notiz #172): erst wählt man, WAS für ein Feld
// es ist – aus einer Palette aus Symbolen, deren Name beim Hover aufklappt (`.erp-palette`) –,
// dann konfiguriert man es. Vorher hiess der Weg «Feld hinzufügen» → leere Zeile → Auswahl aus
// einem Dropdown: drei Handgriffe für eine Entscheidung, und eine Zeile, die vor der Wahl
// bereits ein «Soll-Ist» behauptete.
const CAPTURE_KINDS: { value: WField['type']; label: string; icon: React.ElementType; hint: string }[] = [
  { value: 'measure', label: 'Soll-Ist', icon: Ruler, hint: 'Messwert mit Sollwert und Toleranz – bestanden, wenn er darin liegt.' },
  { value: 'bool', label: 'Gut/Schlecht', icon: ThumbsUp, hint: 'Eine Ja/Nein-Beurteilung ohne Zahl.' },
  { value: 'text', label: 'Text', icon: Type, hint: 'Freie Notiz – wird erfasst, aber nicht bewertet.' },
  { value: 'photo', label: 'Bild', icon: Camera, hint: 'Aufnahme mit der Kamera.' },
  { value: 'signature', label: 'Unterschrift', icon: PenLine, hint: 'Handschriftliche Unterschrift auf dem Gerät.' },
];

function CaptureFieldsEditor({ fields, onChange }: { fields: WField[]; onChange: (f: WField[]) => void }) {
  // **Die Palette steht offen** (Notiz #229, wie #223): ein Klick auf das Symbol legt das
  // Feld an – der frühere Zwischenschritt «Erfassungsfeld hinzufügen» ist entfallen.
  function add(type: WField['type']) {
    onChange([...fields, { label: '', type, target: '', tolerance: '', unit: '' }]);
  }
  function upd(i: number, patch: Partial<WField>) { onChange(fields.map((f, idx) => (idx === i ? { ...f, ...patch } : f))); }
  function del(i: number) { onChange(fields.filter((_, idx) => idx !== i)); }
  return (
    <div>
      <Label>Erfassungsfelder</Label>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {fields.map((f, i) => {
          const kind = CAPTURE_KINDS.find((k) => k.value === f.type) ?? CAPTURE_KINDS[0];
          const KindIcon = kind.icon;
          return (
            // **Leichter** (Testnotiz #612): eine Zeile, keine Kachel. Ein Kasten je Feld
            // in einem Editor, der selbst schon eine Karte ist, sind drei Rahmen um
            // dieselbe Sache; getrennt wird mit einer Haarlinie.
            <div key={i} style={{ padding: i === 0 ? '0 0 8px' : '8px 0', display: 'flex',
              flexDirection: 'column', gap: 8,
              borderTop: i === 0 ? 'none' : '1px solid var(--border-1)' }}>
              <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                {/* Die Art steht fest, sobald man sie gewählt hat – sie ist kein Feld mehr,
                    sondern das Symbol der Zeile (umentscheiden = löschen + neu, wie beim Schritt). */}
                <span title={kind.label} style={{ display: 'inline-flex', alignItems: 'center', justifyContent: 'center', width: 30, height: 30, borderRadius: 'var(--r-sm)', background: 'var(--bg-2)', color: 'var(--fg-2)', flexShrink: 0 }}>
                  <KindIcon size={15} />
                </span>
                <input value={f.label} onChange={(e) => upd(i, { label: e.target.value })} placeholder="Bezeichnung (z. B. Länge)"
                  className="px-2.5 py-1.5 text-sm rounded-md border bg-white outline-none focus:ring-2 focus:ring-[var(--accent)]" style={{ borderColor: 'var(--border-1)', flex: 1, minWidth: 0 }} />
                <button onClick={() => del(i)} title="Feld entfernen" style={{ border: 'none', background: 'none', color: 'var(--fg-4)', cursor: 'pointer' }}><Trash2 size={15} /></button>
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
          );
        })}
      </div>
      {/* **Im Formular wird alles vom linken Rand gelesen** (Testnotiz #619): die Palette
          steht zentriert, wo sie unter einer zentrierten Achse hängt (Modul-Palette im
          Fluss, Unterdeckungs-Dialog) – hier steht sie unter einer linksbündigen
          Beschriftung, also richtet sie sich danach. */}
      <Palette
        style={{ justifyContent: 'flex-start', marginTop: fields.length > 0 ? 10 : 0 }}>
        {CAPTURE_KINDS.map((k) => (
          <PaletteButton key={k.value} icon={k.icon} label={k.label} size={18}
            onClick={() => add(k.value)} />
        ))}
      </Palette>
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

/**
 * Read-only-Ansicht der «Dokument»-Deklaration im fertigen Schritt.
 *
 * **Aufgeräumt** (Notiz #241): eine Liste der Parteien in EINEM Raster (Nummer · Name ·
 * Aktion · Objektnummer) und darunter die beiden Ein-Wert-Angaben als schlichte
 * Schlüssel-Wert-Zeilen an einer Haarlinie. Vorher stapelten sich fünf Blöcke mit je
 * eigener Versalien-Überschrift – dieselbe Information, dreimal so hoch. Die Überschrift
 * «Freigabe-Parteien» ist entfallen: der Karten-Kopf sagt bereits «Dokumentenfreigabe».
 */
function DocConfigView({ step, users }: { step: ArticleProcessStep; users: UserProfile[] }) {
  const nameOf = (oid: number) => {
    const u = users.find((x) => x.object_id === oid);
    return u ? userDisplayName(u) : `Objekt ${formatObjectId(oid)}`;
  };
  const signers = step.doc_signers ?? [];
  const vis = step.doc_visibility ?? 'internal';
  const visLabel = vis === 'public' ? 'Öffentlich' : vis === 'confidential' ? 'Vertraulich' : 'Intern';
  const aud = step.doc_audience;
  const audienceText = !aud
    ? 'keine'
    : aud === 'all' ? 'Alle Angemeldeten'
    : aud === 'roles' ? ((step.doc_audience_roles ?? []).map((r) => AUDIENCE_ROLE_LABELS[r] ?? r).join(', ') || 'Rollen')
    : ((step.doc_audience_person_ids ?? []).map(nameOf).join(', ') || '—');

  return (
    <div style={{ display: 'flex', flexDirection: 'column' }}>
      {signers.length === 0 ? (
        <div style={dv.muted}>Ohne Partei – mit «Ausstellen» sofort freigegeben.</div>
      ) : (
        signers.map((sg, i) => (
          <div key={i} style={dv.row}>
            <span style={dv.idx}>{i + 1}</span>
            <span style={dv.name}>{nameOf(sg.signer_object_id)}</span>
            <span style={dv.tag}>{sg.action === 'confirm' ? 'Bestätigen' : 'Unterschreiben'}</span>
            <span style={dv.nr}>{formatObjectId(sg.signer_object_id)}</span>
          </div>
        ))
      )}
      {signers.length > 1 && step.sign_sequential && (
        <div style={dv.muted}>der Reihe nach</div>
      )}
      <div style={dv.kv}><span style={dv.label}>Leseberechtigung</span><span style={dv.value}>{visLabel}</span></div>
      <div style={dv.kv}><span style={dv.label}>Anerkennung</span><span style={dv.value}>{audienceText}</span></div>
    </div>
  );
}

// EIN Raster für alle Zeilen der Deklaration – Parteien wie Schlüssel-Wert-Angaben.
const dv: Record<string, React.CSSProperties> = {
  label: { font: '500 12.5px var(--font-body)', color: 'var(--fg-3)' },
  muted: { font: '500 12px var(--font-body)', color: 'var(--fg-4)', padding: '5px 0' },
  row: { display: 'flex', alignItems: 'center', gap: 10, padding: '6px 0', minHeight: 26 },
  idx: { font: '600 11.5px var(--font-body)', color: 'var(--fg-4)', minWidth: 12, fontVariantNumeric: 'tabular-nums' },
  name: { flex: 1, font: '600 13px var(--font-body)', color: 'var(--fg-1)', minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' },
  tag: { font: '500 11.5px var(--font-body)', color: 'var(--fg-3)', flexShrink: 0 },
  nr: { fontFamily: 'var(--font-mono)', fontSize: 11.5, color: 'var(--fg-4)', fontVariantNumeric: 'tabular-nums', flexShrink: 0 },
  kv: {
    display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 10,
    padding: '6px 0', borderTop: '1px solid var(--border-1)', minHeight: 26,
  },
  value: { font: '600 13px var(--font-body)', color: 'var(--fg-1)', textAlign: 'right' },
};

/**
 * Beschriftung im Dokument-Schritt: **die Sache beim Namen** – «Dokumentenfreigabe»,
 * «Leseberechtigung», «Anerkennung» (Notizen #237/#238). Die früheren Fragen («Wer muss
 * freigeben?») und ihre Erklär-ⓘ sind entfallen (#235/#239). Ursprünglich war das als
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
    return u ? userDisplayName(u) : `Objekt ${formatObjectId(oid)}`;
  };
  const chosen = new Set(cfg.signers.map((s) => s.signer_object_id));
  const signerOptions = [
    { value: '', label: '+ Freigabe-Partei hinzufügen…' },
    ...pickable.filter((u) => !chosen.has(u.object_id!)).map((u) => ({
      value: String(u.object_id), label: `${userDisplayName(u)} · ${formatObjectId(u.object_id!)}` })),
  ];
  const personOptions = [
    { value: '', label: '+ Person hinzufügen…' },
    ...pickable.filter((u) => !cfg.persons.includes(u.object_id!)).map((u) => ({
      value: String(u.object_id), label: `${userDisplayName(u)} · ${formatObjectId(u.object_id!)}` })),
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
        <DocLabel text="Dokumentenfreigabe" />
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
        <DocLabel text="Leseberechtigung" />
        <IconSwitch<DocCfg['visibility']> value={cfg.visibility} onChange={(v) => set({ visibility: v })}
          options={[
            { value: 'public', icon: Globe, label: 'Alle', hint: 'Jeder mit Zugang zum Auftrag – auch Kunden und Lieferanten.' },
            { value: 'internal', icon: Building2, label: 'Intern', hint: 'Nur Personal; benannte Parteien sehen es trotzdem.' },
            { value: 'confidential', icon: Lock, label: 'Vertraulich', hint: 'Nur Personal und die benannten Parteien.' },
          ]} />
      </div>

      {/* Anerkennungs-Publikum (offen, blockiert den Auftrag NIE) */}
      <div>
        <DocLabel text="Anerkennung" />
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
  // Eigene, kühl-graublaue Familie: `var(--bg-2)` war exakt die Flächenfarbe des
  // Fensters – die Karte verschwand darin (Notiz #236).
  document:   { bg: '#F2F5F7', border: '#DBE3E8', fg: '#4A6572' },
  sale:       { bg: '#F0FBF4', border: '#CDEBD6', fg: '#15803D' },
  // Aussondern ist EIN Modul (#277) – beide Wirkungen tragen dieselbe rote Familie;
  // unterschieden wird im Modul, nicht über die Farbe.
  scrap:      { bg: '#FDF3F2', border: '#F1D6D2', fg: 'var(--danger)' },
  block:      { bg: '#FDF3F2', border: '#F1D6D2', fg: 'var(--danger)' },
};
// Begleit-Bewegungen sind normale Schritte und werden darum auch normal eingefärbt –
// die frühere Graufärbung signalisierte «gesperrt» und ist mit der Sperre entfallen.
export function kindColor(type: StepType) {
  return KIND_COLORS[type] ?? KIND_COLORS.purchase;
}

/**
 * Die Verbindung zwischen zwei Knoten des Flusses.
 *
 * ``dashed`` für alles, was **nicht** zu diesem Prozess gehört, aber an ihn anschliesst –
 * der Weg zum Eltern-Auftrag und wieder zurück (Notiz #409). Gestrichelt heisst: hier endet
 * der eigene Ablauf und es geht in einen anderen Auftrag über. Eine Variante desselben
 * Bausteins, keine zweite Linie.
 */
export function Connector({ dashed = false, height }: { dashed?: boolean; height?: number } = {}) {
  if (dashed) {
    return (
      <div style={{
        width: 2, height: height ?? 22, flex: 'none',
        backgroundImage: 'linear-gradient(var(--border-2) 55%, transparent 55%)',
        backgroundSize: '2px 7px',
      }} />
    );
  }
  return <div style={{ width: 2, height: height ?? 28, background: 'var(--border-2)', flex: 'none' }} />;
}

// Start-/Endknoten als runder Terminal-Knoten (grün «Start» / dunkel «Ende»).
/**
 * Start-/Endknoten des Flusses.
 *
 * ``size`` verkleinert ihn für den **Abzweig** (Notiz #410): ein Unter-Auftrag ist ein
 * eigener Prozess und bekommt darum eigene Terminal-Knoten – aber eine Nummer kleiner, damit
 * er sich dem Hauptfluss unterordnet. Dieselben Farben und Symbole: was «Start» bedeutet,
 * darf nicht davon abhängen, in welcher Ebene man gerade liest.
 */
export function FlowTerm({ kind, size = 52, title }: {
  kind: 'start' | 'end'; size?: number;
  /** Welcher Prozess hier anfängt bzw. endet – die Objektnummer im Hover (Notizen #443/#444). */
  title?: string;
}) {
  const start = kind === 'start';
  return (
    <div style={{
      width: size, height: size, borderRadius: '50%', flex: 'none', boxShadow: 'var(--shadow-sm)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      background: start ? 'var(--success)' : 'var(--fg-1)', color: '#fff',
    }} title={title ?? (start ? 'Start' : 'Ende')}>
      {start ? <Play size={Math.round(size * 0.42)} /> : <Flag size={Math.round(size * 0.38)} />}
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

// **EINE Breite für den Prozess – überall** (Testnotizen #534/#597): egal ob Entwurf oder
// freigegeben, Haupt- oder Unter-Auftrag, Artikel-Prozess oder laufender Ablauf. Sie ist
// **fest**, nicht eine Obergrenze je Karte: eine Obergrenze schwankt mit dem Platz, und
// genau daher kam die wechselnde Modul-Breite zwischen Hinzufügen, Zwischenspeichern und
// Freigeben. Die Breite gehört zum Linien-Layout, darum steht sie dort (`flow-line.Lane`).
// Karten-Unterbereich (unter dem Kopf): Haarlinie oben, gleiche horizontale Polsterung.
const cardBody: React.CSSProperties = {
  // Gleiche horizontale Polsterung wie der Karten-Kopf (16 px, #597) – sonst springt die
  // Inhalts-Spalte zwischen Kopf und Körper derselben Karte.
  borderTop: '1px solid var(--border-1)', padding: '12px 16px 14px',
};
// Editor-/Palette-Karte (neutral, für «Schritt hinzufügen»).
const delBtn: React.CSSProperties = {
  border: 'none', background: 'none', color: 'var(--fg-4)', cursor: 'pointer', padding: 4, flexShrink: 0,
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
