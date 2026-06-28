'use client';

import { useEffect, useRef, useState } from 'react';
import { ClipboardList, ArrowLeft, Workflow, MapPin, CheckCircle2, Loader2, Repeat, ChevronDown, Boxes, Factory, Warehouse, Target } from 'lucide-react';
import { api } from '@/lib/api';
import type { Article, CompanySettings, Instance, Order, OrderStep } from '@/types';
import { orderStatusConfig } from '@/lib/order';
import { unitLabel } from '@/lib/article';
import { toStepperState, STEP_META } from '@/lib/process';
import { useAutosave } from '@/lib/use-autosave';
import { isVersionConflict } from '@/lib/optimistic';
import type { StatusAction } from '@/lib/status-flow';
import { fmtObjId } from '@/components/erp/user-detail';
import { ObjId } from '@/components/erp/obj-id';
import { SearchSelect, StatusBadge, StatusFlow, Label } from '@/components/erp/fields';
import { DeactivateDialog, ReplacedBanner } from '@/components/erp/deactivate-dialog';
import { ProcessStepper } from '@/components/erp/process-stepper';
import { PurchaseStepPanel } from '@/components/erp/purchase-step-panel';
import { OrderInstances } from '@/components/erp/order-instances';
import { InspectionPanel } from '@/components/erp/inspection-panel';
import { MovementPanel } from '@/components/erp/movement-panel';
import { ResourcePanel } from '@/components/erp/resource-panel';
import { SalePanel } from '@/components/erp/sale-panel';
import { ProcessSteps } from '@/components/erp/process-steps';

type ViewerRole = 'staff' | 'supplier';

// Ziel der Auftragsanlage (Ziel-Karten): herstellen | aus Lager (FIFO) | bestimmte Stücke.
type OrderGoal = 'produce' | 'stock' | 'specific';

// Anker ist IMMER der Artikel + Menge. Was damit geschieht, ergibt sich aus dem Ablauf,
// der danach im Entwurf definiert wird (Erzeugung vs. Operation am Bestand). Optional
// lassen sich für eine Bestands-Operation bestimmte Instanzen fixieren (sonst FIFO).
type Form = { article_id: string; quantity: string; desired_delivery_date: string };

function seedFrom(record: Order | null): Form {
  if (!record) return { article_id: '', quantity: '', desired_delivery_date: '' };
  return {
    article_id: record.article_id != null ? String(record.article_id) : '',
    quantity: record.quantity != null ? String(record.quantity) : '',
    desired_delivery_date: record.desired_delivery_date ?? '',
  };
}

function localDate(iso: string | null | undefined): string {
  return iso ? new Date(iso).toLocaleDateString('de-CH') : '—';
}

function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

// Abgeleitete Subjektart des Auftrags (kein Modus-Flag) – für die Anzeige.
function subjectRoleLabel(role: string | null | undefined): string {
  return role === 'stock' ? 'Operation am Bestand' : 'Herstellung – erzeugt Instanzen';
}

// Auftrag-Lebenszyklus mit Freigabe-Schutz (Artikel + Menge nötig).
// Kein Reaktivieren – ein abgebrochener Auftrag wird neu gestartet (Ersetzen).
function orderActions(status: string, canRelease: boolean): StatusAction[] {
  if (status === 'draft')
    return [{ label: 'Freigeben', target: 'released', tone: 'primary', disabled: !canRelease,
      hint: canRelease ? undefined : 'Erst Artikel und Menge speichern' }];
  if (status === 'released')
    return [{ label: 'Ersetzen', target: 'replace', tone: 'neutral' },
            { label: 'Abbrechen', target: 'inactive', tone: 'danger' }];
  return [];   // inactive/completed → kein manueller Wechsel
}

export function OrderDetail({ record, articles, viewerRole, company, onSaved, onCancel, onBack }: {
  record: Order | null;            // null ⇒ Anlage-Modus (nur Mitarbeiter)
  articles: Article[];
  viewerRole: ViewerRole;
  company: Partial<CompanySettings> | null;
  onSaved: (o: Order) => void;
  onCancel: () => void;
  onBack: () => void;
}) {
  const isCreate = record === null;
  const isStaff = viewerRole === 'staff';
  const [form, setForm] = useState<Form>(() => seedFrom(record));
  const [dateOpen, setDateOpen] = useState<boolean>(!!record?.desired_delivery_date);
  const [savedSig, setSavedSig] = useState<string>(() => (record === null ? '' : JSON.stringify(seedFrom(record))));
  const [saving, setSaving] = useState(false);
  const [flash, setFlash] = useState(false);
  const [statusBusy, setStatusBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selStep, setSelStep] = useState<string | null>(null);
  const [dialog, setDialog] = useState<'deactivate' | 'replace' | null>(null);
  const verRef = useRef<string | null>(record?.updated_at ?? null);   // Optimistic Locking

  function set<K extends keyof Form>(key: K, value: Form[K]) {
    setForm((p) => ({ ...p, [key]: value }));
  }

  // Bedarf nur im Entwurf bearbeitbar (nach Freigabe read-only) und nur für Mitarbeiter
  const demandEditable = isStaff && (isCreate || record?.status === 'draft');
  const isCompleted = record?.status === 'completed';
  const hasPurchase = !!record?.purchase;

  // Auftrag-Prozess (mehrere Schritte, Mehr-Operationen-Routing) – Schlüssel ist die
  // Schritt-id, damit mehrere gleichartige Schritte unabhängig bedienbar sind.
  const steps = (record?.steps ?? []) as OrderStep[];
  const showProcess = isStaff && !!record && record.status !== 'draft' && steps.length > 0;
  const activeStepId = steps.find((s) => s.state === 'active')?.id
    ?? steps.find((s) => s.state === 'failed')?.id
    ?? steps[steps.length - 1]?.id ?? null;
  const currentStepId = selStep ?? (activeStepId != null ? String(activeStepId) : null);
  const currentStepObj = steps.find((s) => String(s.id) === currentStepId) ?? null;

  // Nur freigegebene Artikel sind referenzierbar
  const releasedArticles = articles.filter((a) => a.status === 'released');
  const selectedArticle = releasedArticles.find((a) => String(a.id) === form.article_id) ?? null;
  const qtyUnit = selectedArticle ? unitLabel(selectedArticle.unit) : (record?.article_unit ? unitLabel(record.article_unit) : '');

  // Anker: Artikel + Menge. Bedarf (Artikel/Menge/Termin) wird per Auto-Save persistiert.
  const qtyNum = form.quantity.trim() ? Number(form.quantity) : null;
  const demandValid = !!form.article_id && qtyNum != null && qtyNum > 0;
  const effectiveDate = dateOpen ? (form.desired_delivery_date || null) : null;
  const sig = JSON.stringify({ article_id: form.article_id, quantity: form.quantity.trim(), date: effectiveDate });
  const canSave = demandEditable && demandValid && sig !== savedSig && !saving;
  // Bestands-Operation? – sobald der Auftrag eigene Schritte trägt. Live über ProcessSteps;
  // initial aus der abgeleiteten Subjektart, bis ProcessSteps den echten Stand meldet.
  const [orderStepCount, setOrderStepCount] = useState<number | null>(null);
  const isDraftStaff = isStaff && !isCreate && record?.status === 'draft';
  const hasCustomSteps = orderStepCount != null ? orderStepCount > 0 : record?.subject_role === 'stock';

  // Fixierte (gewählte) Instanzen + verfügbarer Lagerbestand des Artikels (für die Ziel-Karten).
  const pins = (record?.instances ?? []).map((i) => i.object_id).filter((x): x is number => x != null);
  const pinnedQty = (record?.instances ?? []).reduce((s, i) => s + (i.quantity ?? 0), 0);
  const reqQty = record?.quantity ?? 0;
  const [pinPool, setPinPool] = useState<Instance[]>([]);
  useEffect(() => {
    if (!isDraftStaff || record?.article_id == null) { setPinPool([]); return; }
    api.getInstances(500).then(setPinPool).catch(() => {});
  }, [isDraftStaff, record?.article_id]);
  const articleStock = pinPool.filter((i) =>
    i.object_id != null && i.article_id === record?.article_id &&
    i.quality === 'passed' && i.disposition === 'in_stock' &&
    (i.reserved_for_order_object_id == null || i.reserved_for_order_object_id === record?.object_id));
  const availableQty = articleStock.reduce((s, i) => s + (i.quantity ?? 0), 0);
  // Genug Bestand für eine reine Bestands-Operation? (Menge darf den Lagerbestand nicht übersteigen)
  const enoughStock = reqQty > 0 && availableQty >= reqQty;

  // Ziel der Auftragsanlage (Ziel-Karten). Pins ⇒ «Instanz wählen»; eigene Schritte ⇒
  // «Aus Lager»; sonst «Herstellen». Über die Karten wechselbar (pickGoal räumt Pins beim
  // Verlassen von «Instanz wählen» auf, damit «Aus Lager» wirklich reines FIFO ist).
  const [goalSel, setGoalSel] = useState<OrderGoal | null>(null);
  const goal: OrderGoal = pins.length > 0
    ? 'specific'
    : hasCustomSteps
      ? (goalSel === 'specific' ? 'specific' : 'stock')
      : (goalSel ?? 'produce');

  function pickGoal(g: OrderGoal) {
    setGoalSel(g);
    if (g !== 'specific' && pins.length > 0) setPins([]);   // «Aus Lager»/«Herstellen» = ohne Pins
  }
  function togglePin(oid: number) {
    if (pins.includes(oid)) { setPins(pins.filter((x) => x !== oid)); return; }
    setPins([...pins, oid]);
  }

  // «Instanz wählen» verlangt, dass die gewählten Instanzen die Auftragsmenge GENAU decken.
  const specificComplete = goal !== 'specific' || pinnedQty === reqQty;
  // Freigabe erst möglich, wenn der Bedarf gespeichert ist UND (bei «Instanz wählen») die
  // Stückzahl vollständig gewählt wurde.
  const canRelease = !isCreate && !!record?.article_id && !!record?.quantity
    && sig === savedSig && specificComplete;

  async function setPins(ids: number[]) {
    if (!record) return;
    try {
      const saved = await api.updateOrder(record.object_id as number,
        { instance_object_ids: ids, expected_updated_at: verRef.current });
      verRef.current = saved.updated_at;
      onSaved(saved);
    } catch (e) { setError(e instanceof Error ? e.message : 'Fehler beim Festlegen der Instanzen'); }
  }

  async function save() {
    if (!demandValid) return;
    const current = sig;
    setSaving(true);
    setError(null);
    try {
      if (isCreate) {
        onSaved(await api.createOrder({ article_id: Number(form.article_id), quantity: qtyNum, desired_delivery_date: effectiveDate }));
      } else {
        const saved = await api.updateOrder(record.object_id as number, {
          article_id: form.article_id ? Number(form.article_id) : null,
          quantity: qtyNum, desired_delivery_date: effectiveDate, expected_updated_at: verRef.current,
        });
        verRef.current = saved.updated_at;
        onSaved(saved);
        setSavedSig(current);
        setFlash(true);
        setTimeout(() => setFlash(false), 700);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Fehler beim Speichern');
      if (!isCreate && isVersionConflict(e)) await resyncVersion();
    } finally {
      setSaving(false);
    }
  }

  async function resyncVersion() {
    if (!record) return;
    try {
      const fresh = await api.getOrder(record.object_id as number);
      verRef.current = fresh.updated_at;
      onSaved(fresh);
    } catch { /* ignore */ }
  }

  const flush = useAutosave(sig, canSave, save);

  // Nach Abschluss eines Prozessschritts automatisch zum nächsten aktiven springen
  function afterStep(o: Order) {
    onSaved(o);
    const next = (o.steps ?? []).find((s) => s.state === 'active');
    if (next) setSelStep(String(next.id));
  }

  async function changeStatus(target: string) {
    if (!record) return;
    setStatusBusy(true);
    setError(null);
    try {
      const saved = await api.updateOrder(record.object_id as number,
        { status: target as Order['status'], expected_updated_at: verRef.current });
      verRef.current = saved.updated_at;
      onSaved(saved);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Statuswechsel fehlgeschlagen');
      if (isVersionConflict(e)) await resyncVersion();
    } finally {
      setStatusBusy(false);
    }
  }

  // Abbrechen/Ersetzen laufen über einen Bestätigungsdialog.
  function onStatusAction(target: string) {
    if (target === 'inactive') { setDialog('deactivate'); return; }
    if (target === 'replace') { setDialog('replace'); return; }
    changeStatus(target);
  }

  async function confirmCancel() {
    if (!record) return;
    const saved = await api.updateOrder(record.object_id as number,
      { status: 'inactive', expected_updated_at: verRef.current });
    verRef.current = saved.updated_at;
    onSaved(saved);
    setDialog(null);
  }

  async function confirmReplace() {
    if (!record) return;
    onSaved(await api.replaceOrder(record.object_id as number));   // navigiert zum neuen Auftrag
    setDialog(null);
  }

  const articleOptions = [
    { value: '', label: '— Artikel wählen —' },
    ...releasedArticles.map((a) => ({ value: String(a.id), label: `${fmtObjId(a.object_id)} · ${a.name}` })),
  ];
  const companyAddr = company ? [company.street, company.street_number].filter(Boolean).join(' ') : '';

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div style={{ padding: '12px 20px', borderBottom: '1px solid #E2E8F0', background: '#fff', flexShrink: 0 }}>
        <button onClick={onBack} className="flex items-center gap-1 text-sm text-blue-600 mb-2 md:hidden">
          <ArrowLeft size={14} /> Zurück
        </button>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <div style={{ width: 44, height: 44, borderRadius: 10, flexShrink: 0, background: '#F1F5F9', color: '#64748b', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <ClipboardList size={20} />
          </div>
          <div style={{ minWidth: 0, flex: 1 }}>
            <div style={{ fontSize: 15, fontWeight: 700, color: '#0F172A' }}>Auftrag</div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 4 }}>
              {isCreate ? (
                <StatusBadge cfg={orderStatusConfig('draft')} />
              ) : (isCompleted || !isStaff) ? (
                <StatusBadge cfg={orderStatusConfig(record.status)} />
              ) : (
                <StatusFlow cfg={orderStatusConfig(record.status)} actions={orderActions(record.status, canRelease)} busy={statusBusy} onAction={onStatusAction} />
              )}
              {demandEditable && <SaveIndicator saving={saving} flash={flash} />}
            </div>
          </div>
          <div style={{ flexShrink: 0, textAlign: 'right' }}>
            <div style={{ fontSize: 10, color: '#CBD5E1', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' }}>Obj.-Nr.</div>
            <div style={{ fontSize: 12, fontFamily: 'monospace', fontWeight: 700, color: '#475569' }}>
              {isCreate ? 'wird vergeben' : fmtObjId(record.object_id)}
            </div>
          </div>
        </div>
        {!isCreate && (record.replaced_by_id != null || record.replaces_id != null) && (
          <ReplacedBanner replacedBy={record.replaced_by_id ?? null} replaces={record.replaces_id ?? null} />
        )}
      </div>

      {/* Content */}
      <div onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); flush(); } }}
        style={{ flex: 1, overflowY: 'auto', padding: '16px 20px', background: '#F8FAFC', boxShadow: flash ? 'inset 0 0 0 2px #16a34a' : 'none', transition: 'box-shadow 0.2s' }}>
        {isCompleted && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12, padding: '12px 14px', background: '#f0fdfa', border: '1px solid #99f6e4', borderRadius: 10, fontSize: 13, color: '#0f766e', fontWeight: 600 }}>
            <CheckCircle2 size={16} /> Auftrag abgeschlossen – alle Prozessschritte erledigt.
          </div>
        )}

        {/* Bedarf */}
        <SectionTitle>Bedarf</SectionTitle>
        <div style={cardStyle}>
          {demandEditable ? (
            <>
              <SearchSelect label="Artikel" value={form.article_id} onChange={(v) => set('article_id', v)} options={articleOptions} required />
              {isCreate && releasedArticles.length === 0 && (
                <div style={{ fontSize: 12, color: '#92400e', background: '#fffbeb', border: '1px solid #fde68a', borderRadius: 8, padding: '8px 10px' }}>
                  Kein freigegebener Artikel vorhanden. Nur freigegebene Artikel sind referenzierbar.
                </div>
              )}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
                <TextFieldUnit label="Menge" value={form.quantity} onChange={(v) => set('quantity', v)} unit={qtyUnit} required placeholder="z. B. 5" />
                <div>
                  <Label>Wunsch-Liefertermin</Label>
                  {dateOpen ? (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                      <input type="date" value={form.desired_delivery_date} min={todayIso()} onChange={(e) => set('desired_delivery_date', e.target.value)}
                        className="w-full px-2.5 py-1.5 text-sm rounded-md border bg-white outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent" style={{ borderColor: '#e2e8f0' }} />
                      <button type="button" onClick={() => { setDateOpen(false); set('desired_delivery_date', ''); }}
                        style={linkBtn}>Schnellstmöglich (kein Datum)</button>
                    </div>
                  ) : (
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <span style={{ fontSize: 13, fontWeight: 600, color: '#0F172A' }}>Schnellstmöglich</span>
                      <button type="button" onClick={() => setDateOpen(true)} style={linkBtn}>Termin festlegen</button>
                    </div>
                  )}
                </div>
              </div>
            </>
          ) : (
            <>
              <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, fontSize: 13 }}>
                <span style={{ color: '#94a3b8', flexShrink: 0 }}>Artikel</span>
                <span style={{ textAlign: 'right' }}>
                  {record?.article_object_id != null ? <ObjId value={record.article_object_id} /> : '—'}
                </span>
              </div>
              <Row k="Menge" v={record?.quantity != null ? `${record.quantity} ${record.article_unit ? unitLabel(record.article_unit) : ''}`.trim() : '—'} />
              <Row k="Wunsch-Liefertermin" v={record?.desired_delivery_date ? localDate(record.desired_delivery_date) : 'Schnellstmöglich'} />
              <Row k="Art" v={subjectRoleLabel(record?.subject_role)} />
            </>
          )}
        </div>

        {/* Wiederkehrend – nur im Entwurf einstellbar (ein freigegebener Auftrag
            ist „scharf" und lässt sich nicht mehr auf wiederkehrend umstellen). */}
        {isStaff && record?.status === 'draft' && <RecurrenceCard order={record} onSaved={onSaved} />}

        {/* Lieferung an (für Lieferant) */}
        {!isStaff && (
          <>
            <SectionTitle icon={MapPin}>Lieferung an</SectionTitle>
            <div style={cardStyle}>
              <Row k="Besteller" v={company?.company_name ?? 'Inexxio AG'} />
              {companyAddr && <Row k="Adresse" v={`${companyAddr}, ${company?.zip ?? ''} ${company?.city ?? ''}`.trim()} />}
            </div>
          </>
        )}

        {/* Bestands-Instanzen (bei Freigabe erzeugt) */}
        {record && <OrderInstances order={record} />}

        {/* Ziel der Auftragsanlage – «Was möchten Sie tun?» (DAU-sicher: Symbol + Farbe +
            Klartext, Live-Verfügbarkeit, unmögliche Optionen deaktiviert mit Begründung). */}
        {isStaff && record?.status === 'draft' && (
          <>
            <SectionTitle icon={Workflow}>Was möchten Sie tun?</SectionTitle>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr', gap: 10, marginBottom: 12 }}>
              <GoalCard icon={Factory} tone="#0f766e" active={goal === 'produce'}
                disabled={hasCustomSteps}
                disabledHint="Erst die Auftrags-Schritte entfernen"
                title="Herstellen / Beschaffen"
                desc={`Bei Freigabe entstehen ${reqQty || ''} ${qtyUnit} neu – der Prozess des Artikels wird gefahren.`}
                footer="Neuer Bestand"
                onClick={() => pickGoal('produce')} />
              <GoalCard icon={Warehouse} tone="#2563eb" active={goal === 'stock'}
                disabled={!enoughStock}
                disabledHint={availableQty < 1 ? 'Kein Bestand vorhanden' : `Nur ${availableQty} ${qtyUnit} am Lager (${reqQty} benötigt)`}
                title="Aus dem Lager"
                desc="Vorhandene Stück verarbeiten – das System wählt automatisch die ältesten (FIFO)."
                footer={`Lager: ${availableQty} ${qtyUnit} verfügbar`}
                onClick={() => pickGoal('stock')} />
              <GoalCard icon={Target} tone="#7c3aed" active={goal === 'specific'}
                disabled={!enoughStock}
                disabledHint={availableQty < 1 ? 'Kein Bestand vorhanden' : `Nur ${availableQty} ${qtyUnit} am Lager (${reqQty} benötigt)`}
                title="Instanz wählen"
                desc="Genau wählen, welche Instanzen verarbeitet werden (z. B. Reparatur, Reklamation)."
                footer={`Lager: ${availableQty} ${qtyUnit} verfügbar`}
                onClick={() => pickGoal('specific')} />
            </div>

            {/* Editor je nach Ziel */}
            {goal === 'produce' ? (
              <div style={{ ...cardStyle, flexDirection: 'row', alignItems: 'center', gap: 12 }}>
                <Factory size={18} style={{ color: '#0f766e', flexShrink: 0 }} />
                <div style={{ fontSize: 12, color: '#64748b', lineHeight: 1.5 }}>
                  <strong style={{ color: '#0f172a' }}>Herstellung.</strong> Bei der Freigabe werden{' '}
                  <strong style={{ color: '#0f172a' }}>{reqQty || ''} {qtyUnit}</strong> nach dem
                  Prozess des Artikels erzeugt – keine eigenen Auftrags-Schritte nötig.
                </div>
              </div>
            ) : (
              <>
                {/* «Instanz wählen»: Instanzen direkt hier wählen – genau die Auftragsmenge. */}
                {goal === 'specific' && (
                  <>
                    <SectionTitle icon={Boxes}>Instanzen wählen</SectionTitle>
                    <div style={cardStyle}>
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
                        <span style={{ fontSize: 12, color: '#64748b' }}>Genau {reqQty} {qtyUnit} wählen:</span>
                        <span style={{ fontSize: 12, fontWeight: 700, color: pinnedQty === reqQty ? '#16a34a' : '#d97706' }}>
                          {pinnedQty} / {reqQty} gewählt
                        </span>
                      </div>
                      {articleStock.length === 0 ? (
                        <div style={{ fontSize: 12, color: '#94a3b8' }}>Keine verfügbaren Instanzen.</div>
                      ) : (
                        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                          {articleStock.map((i) => {
                            const sel = pins.includes(i.object_id!);
                            const atLimit = !sel && pinnedQty + (i.quantity ?? 1) > reqQty;
                            return (
                              <button key={i.object_id} type="button" disabled={atLimit}
                                onClick={() => togglePin(i.object_id!)}
                                style={{
                                  display: 'inline-flex', alignItems: 'center', gap: 5, fontSize: 12, fontFamily: 'monospace',
                                  padding: '4px 10px', borderRadius: 999, cursor: atLimit ? 'not-allowed' : 'pointer',
                                  border: `1px solid ${sel ? '#7c3aed' : '#e2e8f0'}`,
                                  background: sel ? '#f5f3ff' : '#fff', color: sel ? '#6d28d9' : '#475569',
                                  opacity: atLimit ? 0.4 : 1,
                                }}>
                                {sel && <CheckCircle2 size={12} />}
                                {fmtObjId(i.object_id)}{(i.quantity ?? 1) > 1 ? ` ·${i.quantity}` : ''}
                              </button>
                            );
                          })}
                        </div>
                      )}
                    </div>
                  </>
                )}

                <SectionTitle icon={Workflow}>Ablauf</SectionTitle>
                <div style={cardStyle}>
                  <div style={{ fontSize: 12, color: '#64748b', lineHeight: 1.5 }}>
                    {goal === 'specific'
                      ? 'Schritte definieren, was mit den gewählten Instanzen geschieht (bewegen, verkaufen, prüfen …).'
                      : `Schritte definieren, was mit ${reqQty || ''} ${qtyUnit} ab Lager geschieht – die ältesten zuerst (FIFO).`}
                  </div>
                  <ProcessSteps owner="orders" ownerObjectId={record.object_id ?? null} suppliers={[]}
                    selfArticleObjectId={record.article_object_id ?? null} onStepsCount={setOrderStepCount} />
                </div>
              </>
            )}
          </>
        )}

        {/* Prozess */}
        {showProcess ? (
          <>
            <SectionTitle icon={Workflow}>Prozess</SectionTitle>
            <div style={{ ...cardStyle, paddingTop: 14, paddingBottom: 14 }}>
              <ProcessStepper
                nodes={steps.map((s) => ({ key: String(s.id), label: s.label, state: toStepperState(s.state), hint: stepHint(s), icon: STEP_META[s.step_type as keyof typeof STEP_META]?.icon }))}
                selectedKey={currentStepId ?? undefined}
                onSelect={setSelStep}
              />
            </div>
            <StepPanel key={currentStepId ?? 'none'} step={currentStepObj} order={record as Order} viewerRole={viewerRole} company={company} onSaved={afterStep} />
          </>
        ) : !isStaff && hasPurchase ? (
          <>
            <SectionTitle icon={Workflow}>Prozess</SectionTitle>
            <PurchaseStepPanel order={record as Order} viewerRole={viewerRole} company={company} onOrderUpdated={onSaved} />
          </>
        ) : null}
      </div>

      {/* Meta footer (edit only) */}
      {!isCreate && (
        <div style={{ padding: '8px 20px', borderTop: '1px solid #E2E8F0', background: '#fff', flexShrink: 0, fontSize: 11, color: '#94a3b8', display: 'flex', gap: 16 }}>
          <span>Erstellt: {localDate(record.created_at)}</span>
          <span>Zuletzt geändert: {localDate(record.updated_at)}</span>
        </div>
      )}

      {/* Footer-Status (Auto-Save, kein manueller Speichern-Knopf) */}
      {demandEditable && (
        <div style={{ padding: '10px 20px', background: '#fff', borderTop: '1px solid #E2E8F0', display: 'flex', alignItems: 'center', gap: 10, flexShrink: 0 }}>
          <span style={{ flex: 1, fontSize: 12, color: error ? '#dc2626' : '#94a3b8', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {error ?? (!demandValid ? 'Pflichtfelder: Artikel und Menge' : isCreate ? 'Wird automatisch angelegt, sobald vollständig' : 'Änderungen werden automatisch gespeichert')}
          </span>
          {isCreate && (
            <button onClick={onCancel}
              style={{ padding: '6px 14px', borderRadius: 7, border: '1px solid #E2E8F0', background: '#fff', fontSize: 13, color: '#374151', cursor: 'pointer', flexShrink: 0 }}>
              Abbrechen
            </button>
          )}
        </div>
      )}

      {dialog && record && (
        <DeactivateDialog
          mode={dialog}
          title={dialog === 'replace' ? 'Auftrag ersetzen' : 'Auftrag abbrechen'}
          message={dialog === 'replace'
            ? 'Ein neuer Auftrag (Entwurf, gleicher Artikel/Menge) wird angelegt und verknüpft; dieser wird abgebrochen.'
            : 'Reservierungen werden freigegeben und unfertige Instanzen verworfen.'}
          confirmLabel={dialog === 'replace' ? 'Ersetzen' : 'Abbrechen'}
          onConfirm={async () => { if (dialog === 'replace') await confirmReplace(); else await confirmCancel(); }}
          onClose={() => setDialog(null)}
        />
      )}
    </div>
  );
}

function SaveIndicator({ saving, flash }: { saving: boolean; flash: boolean }) {
  if (saving) return <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, fontSize: 11, color: '#94a3b8' }}><Loader2 size={12} className="animate-spin" /> Speichert…</span>;
  if (flash) return <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, fontSize: 11, color: '#16a34a' }}><CheckCircle2 size={12} /> Gespeichert</span>;
  return null;
}

function stepHint(s: OrderStep): string | undefined {
  if (s.state !== 'done' || !s.completed_at) return undefined;
  const who = s.completed_by ?? 'System';
  return `${who} · ${new Date(s.completed_at).toLocaleString('de-CH', { dateStyle: 'short', timeStyle: 'short' })}`;
}

// Rendert das Panel des gewählten Prozessschritts. Der jeweilige Ausführungs-Embed
// des konkreten Schritts wird auf die Top-Level-Felder gelegt, damit die Panels
// unverändert lesen können; die Schritt-id wird für das Routing weitergereicht.
function StepPanel({ step, order, viewerRole, company, onSaved }: {
  step: OrderStep | null;
  order: Order;
  viewerRole: ViewerRole;
  company?: Partial<import('@/types').CompanySettings> | null;
  onSaved: (o: Order) => void;
}) {
  if (!step) return null;
  const stepOrder: Order = {
    ...order,
    purchase: (step.purchase ?? order.purchase) as Order['purchase'],
    sale: step.sale ?? order.sale,
    inspection: step.inspection ?? order.inspection,
    movement: step.movement ?? order.movement,
    resource: step.resource ?? order.resource,
  };
  const stepState = step.state;
  const stepId = step.id;
  if (step.step_type === 'purchase') {
    return stepOrder.purchase
      ? <PurchaseStepPanel order={stepOrder} viewerRole={viewerRole} company={company} onOrderUpdated={onSaved} />
      : null;
  }
  if (step.step_type === 'sale') {
    return <SalePanel order={stepOrder} stepState={stepState} stepId={stepId} onOrderUpdated={onSaved} />;
  }
  if (step.step_type === 'inspection') {
    return <InspectionPanel order={stepOrder} stepState={stepState} stepId={stepId} onOrderUpdated={onSaved} />;
  }
  if (step.step_type === 'movement') {
    return <MovementPanel order={stepOrder} stepState={stepState} stepId={stepId} onOrderUpdated={onSaved} />;
  }
  if (step.step_type === 'resource' || step.step_type === 'consume' || step.step_type === 'tool') {
    return <ResourcePanel order={stepOrder} stepState={stepState} stepId={stepId} onOrderUpdated={onSaved} />;
  }
  return null;
}

// Mengen-Eingabe mit Einheit-Suffix des referenzierten Artikels
function TextFieldUnit({ label, value, onChange, unit, required, placeholder }: {
  label: string; value: string; onChange: (v: string) => void; unit?: string; required?: boolean; placeholder?: string;
}) {
  return (
    <div>
      <Label required={required}>{unit ? `${label} (${unit})` : label}</Label>
      <input
        value={value}
        placeholder={placeholder}
        onChange={(e) => onChange(e.target.value)}
        className="w-full px-2.5 py-1.5 text-sm rounded-md border bg-white outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
        style={{ borderColor: '#e2e8f0' }}
      />
    </div>
  );
}

const cardStyle: React.CSSProperties = {
  background: '#fff', border: '1px solid #E2E8F0', borderRadius: 10,
  padding: '16px 18px', marginBottom: 12, display: 'flex', flexDirection: 'column', gap: 14,
};

const linkBtn: React.CSSProperties = {
  alignSelf: 'flex-start', border: 'none', background: 'none', padding: 0,
  fontSize: 12, color: '#2563eb', cursor: 'pointer', fontWeight: 600,
};

// Ziel-Karte («Was möchten Sie tun?»): Symbol + Farbe + Klartext + Live-Fussnote.
// Unmögliche Optionen sind deaktiviert und nennen den Grund (DAU-sicher).
function GoalCard({ icon: Icon, tone, active, disabled, disabledHint, title, desc, footer, onClick }: {
  icon: React.ElementType; tone: string; active: boolean; disabled?: boolean;
  disabledHint?: string; title: string; desc: string; footer: string; onClick: () => void;
}) {
  return (
    <button type="button" onClick={disabled ? undefined : onClick} disabled={disabled}
      style={{
        display: 'flex', alignItems: 'flex-start', gap: 12, textAlign: 'left', width: '100%',
        padding: '12px 14px', borderRadius: 10, cursor: disabled ? 'not-allowed' : 'pointer',
        border: `1.5px solid ${active ? tone : '#E2E8F0'}`,
        background: disabled ? '#f8fafc' : active ? `${tone}14` : '#fff',
        opacity: disabled ? 0.65 : 1, transition: 'border-color 0.15s, background 0.15s',
      }}>
      <div style={{ width: 34, height: 34, borderRadius: 8, flexShrink: 0, background: active ? tone : '#F1F5F9', color: active ? '#fff' : tone, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <Icon size={18} />
      </div>
      <div style={{ minWidth: 0, flex: 1 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontSize: 13.5, fontWeight: 700, color: '#0f172a' }}>{title}</span>
          {active && <CheckCircle2 size={15} style={{ color: tone, flexShrink: 0 }} />}
        </div>
        <div style={{ fontSize: 12, color: '#64748b', lineHeight: 1.45, marginTop: 2 }}>{desc}</div>
        <div style={{ fontSize: 11, fontWeight: 600, color: disabled ? '#dc2626' : tone, marginTop: 5 }}>
          {disabled ? (disabledHint ?? 'Nicht möglich') : footer}
        </div>
      </div>
    </button>
  );
}

function SectionTitle({ icon: Icon, children }: { icon?: React.ElementType; children: React.ReactNode }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 6, margin: '4px 2px 8px' }}>
      {Icon && <Icon size={13} style={{ color: '#94a3b8' }} />}
      <span style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.07em', color: '#64748b' }}>{children}</span>
    </div>
  );
}

function Row({ k, v }: { k: string; v: string }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, fontSize: 13 }}>
      <span style={{ color: '#94a3b8', flexShrink: 0 }}>{k}</span>
      <span style={{ color: '#0F172A', fontWeight: 600, textAlign: 'right' }}>{v}</span>
    </div>
  );
}

const recInput = "w-full px-2.5 py-1.5 text-sm rounded-md border bg-white outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent";

/** «Wiederkehrend» direkt am Auftrag: bei Abschluss entsteht automatisch der nächste
 *  (Entwurf), Termin = Termin + Periode. Nur im Entwurf einstellbar. */
function RecurrenceCard({ order, onSaved }: { order: Order; onSaved: (o: Order) => void }) {
  const [active, setActive] = useState(!!order.recurrence_active);
  const [interval, setIntervalDays] = useState(order.recurrence_interval_days ? String(order.recurrence_interval_days) : '365');
  const [anchor, setAnchor] = useState(order.recurrence_anchor ?? '');
  const [lead, setLead] = useState(order.recurrence_lead_time_days != null ? String(order.recurrence_lead_time_days) : '30');
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function save() {
    setBusy(true); setErr(null);
    try {
      const o = await api.updateOrder(order.object_id as number, {
        recurrence_active: active,
        recurrence_interval_days: active ? Math.max(1, Math.trunc(Number(interval) || 0)) : null,
        recurrence_lead_time_days: active ? Math.max(0, Math.trunc(Number(lead) || 0)) : 0,
        recurrence_anchor: active && anchor ? anchor : null,
      });
      onSaved(o); setSaved(true); setTimeout(() => setSaved(false), 1500);
    } catch (e) { setErr(e instanceof Error ? e.message : 'Fehler beim Speichern'); }
    finally { setBusy(false); }
  }

  // Dezent: standardmässig eingeklappt (ein unscheinbarer Link), nur offen wenn aktiv.
  const [open, setOpen] = useState(!!order.recurrence_active);
  if (!open) {
    return (
      <button onClick={() => setOpen(true)} style={{
        display: 'inline-flex', alignItems: 'center', gap: 6, alignSelf: 'flex-start', margin: '0 2px 12px',
        border: 'none', background: 'none', color: '#94a3b8', cursor: 'pointer', fontSize: 12, fontWeight: 600,
      }}>
        <Repeat size={13} /> Wiederkehrend einrichten
        {order.recurrence_active && <span style={{ fontSize: 10, fontWeight: 700, color: '#2563eb', background: '#eff6ff', padding: '1px 6px', borderRadius: 999 }}>aktiv</span>}
        <ChevronDown size={13} />
      </button>
    );
  }

  return (
    <>
      <button onClick={() => setOpen(false)} style={{ display: 'flex', alignItems: 'center', gap: 6, margin: '4px 2px 8px', border: 'none', background: 'none', cursor: 'pointer' }}>
        <Repeat size={13} style={{ color: '#94a3b8' }} />
        <span style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.07em', color: '#64748b' }}>Wiederkehrend</span>
        <ChevronDown size={13} style={{ color: '#94a3b8', transform: 'rotate(180deg)' }} />
      </button>
      <div style={cardStyle}>
        <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, cursor: 'pointer' }}>
          <input type="checkbox" checked={active} onChange={(e) => setActive(e.target.checked)} />
          <span style={{ fontWeight: 600, color: '#0f172a' }}>Diesen Auftrag wiederkehrend ausführen</span>
        </label>
        {active && (
          <>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
              <div>
                <Label>Periode (Tage)</Label>
                <input value={interval} onChange={(e) => setIntervalDays(e.target.value)} inputMode="numeric"
                  className={recInput} style={{ borderColor: '#e2e8f0' }} placeholder="z. B. 365" />
              </div>
              <div>
                <Label>Vorlaufzeit (Tage)</Label>
                <input value={lead} onChange={(e) => setLead(e.target.value)} inputMode="numeric"
                  className={recInput} style={{ borderColor: '#e2e8f0' }} placeholder="z. B. 30" />
              </div>
            </div>
            <div>
              <Label>Nächster Termin / Ablauf (optional)</Label>
              <input type="date" value={anchor} onChange={(e) => setAnchor(e.target.value)}
                className={recInput} style={{ borderColor: '#e2e8f0' }} />
            </div>
            <div style={{ fontSize: 11, color: '#94a3b8' }}>
              Beim Abschluss entsteht automatisch der nächste Auftrag (Entwurf) – Termin = dieser
              Termin + Periode. Die Vorlaufzeit markiert ihn rechtzeitig als «fällig».
            </div>
          </>
        )}
        {err && <span style={{ fontSize: 12, color: '#dc2626' }}>{err}</span>}
        <button onClick={save} disabled={busy} style={{
          alignSelf: 'flex-start', padding: '7px 14px', borderRadius: 8, border: 'none',
          background: saved ? '#16a34a' : '#2563eb', color: '#fff', fontSize: 13, fontWeight: 600, cursor: 'pointer',
        }}>
          {busy ? 'Speichern…' : saved ? 'Gespeichert ✓' : 'Speichern'}
        </button>
      </div>
    </>
  );
}
