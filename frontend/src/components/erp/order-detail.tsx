'use client';

import { useState } from 'react';
import { ClipboardList, ArrowLeft, Rocket, Workflow, MapPin, CheckCircle2 } from 'lucide-react';
import { api } from '@/lib/api';
import type { Article, CompanySettings, Order, OrderStep, OrderUpdateInput } from '@/types';
import { orderStatusConfig } from '@/lib/order';
import { unitLabel } from '@/lib/article';
import { toStepperState } from '@/lib/process';
import type { StatusAction } from '@/lib/status-flow';
import { fmtObjId } from '@/components/erp/user-detail';
import { SelectField, StatusBadge, StatusFlow, Label } from '@/components/erp/fields';
import { ProcessStepper } from '@/components/erp/process-stepper';
import { PurchaseStepPanel } from '@/components/erp/purchase-step-panel';
import { SerializationPanel } from '@/components/erp/serialization-panel';
import { InspectionPanel } from '@/components/erp/inspection-panel';

type ViewerRole = 'staff' | 'supplier';

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

// Auftrag-Lebenszyklus mit Freigabe-Schutz (Artikel + Menge nötig).
function orderActions(status: string, canRelease: boolean): StatusAction[] {
  if (status === 'draft')
    return [{ label: 'Freigeben', target: 'released', tone: 'primary', disabled: !canRelease,
      hint: canRelease ? undefined : 'Erst Artikel und Menge speichern' }];
  if (status === 'released') return [{ label: 'Deaktivieren', target: 'inactive', tone: 'danger' }];
  if (status === 'inactive') return [{ label: 'Reaktivieren', target: 'released', tone: 'neutral' }];
  return [];   // completed → kein manueller Wechsel
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
  const [saving, setSaving] = useState(false);
  const [statusBusy, setStatusBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selStep, setSelStep] = useState<string | null>(null);

  function set<K extends keyof Form>(key: K, value: Form[K]) {
    setForm((p) => ({ ...p, [key]: value }));
  }

  // Bedarf nur im Entwurf bearbeitbar (nach Freigabe read-only) und nur für Mitarbeiter
  const demandEditable = isStaff && (isCreate || record?.status === 'draft');
  const isCompleted = record?.status === 'completed';
  const hasPurchase = !!record?.purchase;

  // Auftrag-Prozess (mehrere Schritte) – nur für Mitarbeiter nach Freigabe
  const steps = (record?.steps ?? []) as OrderStep[];
  const showProcess = isStaff && !!record && record.status !== 'draft' && steps.length > 0;
  const activeStepType = steps.find((s) => s.state === 'active')?.step_type
    ?? steps.find((s) => s.state === 'failed')?.step_type
    ?? steps[steps.length - 1]?.step_type ?? null;
  const currentStep = selStep ?? activeStepType;
  const currentStepState = steps.find((s) => s.step_type === currentStep)?.state ?? 'locked';

  const seed = seedFrom(record);
  const dirty = isCreate || (Object.keys(form) as (keyof Form)[]).some((k) => form[k] !== seed[k]);

  const qtyNum = form.quantity.trim() ? Number(form.quantity) : null;
  // Freigabe erst möglich, wenn Artikel + Menge gespeichert sind (keine offenen Änderungen)
  const canRelease = !!record?.article_id && !!record?.quantity && !dirty;

  // Nur freigegebene Artikel sind referenzierbar
  const releasedArticles = articles.filter((a) => a.status === 'released');
  const selectedArticle = releasedArticles.find((a) => String(a.id) === form.article_id) ?? null;
  const qtyUnit = selectedArticle ? unitLabel(selectedArticle.unit) : (record?.article_unit ? unitLabel(record.article_unit) : '');

  async function save() {
    setSaving(true);
    setError(null);
    try {
      const article_id = form.article_id ? Number(form.article_id) : null;
      const quantity = qtyNum;
      const desired_delivery_date = dateOpen ? (form.desired_delivery_date || null) : null;
      if (isCreate) {
        onSaved(await api.createOrder({ article_id, quantity, desired_delivery_date }));
      } else {
        const payload: OrderUpdateInput = {};
        if (article_id !== (record.article_id ?? null)) payload.article_id = article_id;
        if (quantity !== (record.quantity ?? null)) payload.quantity = quantity;
        if (desired_delivery_date !== (record.desired_delivery_date ?? null)) payload.desired_delivery_date = desired_delivery_date;
        onSaved(await api.updateOrder(record.object_id as number, payload));
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Fehler beim Speichern');
    } finally {
      setSaving(false);
    }
  }

  async function changeStatus(target: string) {
    if (!record) return;
    setStatusBusy(true);
    setError(null);
    try {
      onSaved(await api.updateOrder(record.object_id as number, { status: target as Order['status'] }));
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Statuswechsel fehlgeschlagen');
    } finally {
      setStatusBusy(false);
    }
  }

  const articleOptions = [
    { value: '', label: '— Artikel wählen —' },
    ...releasedArticles.map((a) => ({ value: String(a.id), label: `${a.name} · ${fmtObjId(a.object_id)}` })),
  ];
  const articleLabel = record?.article_name
    ? `${record.article_name} · ${fmtObjId(record.article_object_id)}`
    : '—';
  const companyAddr = company ? [company.street, company.street_number].filter(Boolean).join(' ') : '';
  const showSaveBar = isStaff && demandEditable && (isCreate || dirty || !!error);

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
                <StatusFlow cfg={orderStatusConfig(record.status)} actions={orderActions(record.status, canRelease)} busy={statusBusy} onAction={changeStatus} />
              )}
            </div>
          </div>
          <div style={{ flexShrink: 0, textAlign: 'right' }}>
            <div style={{ fontSize: 10, color: '#CBD5E1', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' }}>Obj.-Nr.</div>
            <div style={{ fontSize: 12, fontFamily: 'monospace', fontWeight: 700, color: '#475569' }}>
              {isCreate ? 'wird vergeben' : fmtObjId(record.object_id)}
            </div>
          </div>
        </div>
      </div>

      {/* Content */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '16px 20px', background: '#F8FAFC' }}>
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
              <SelectField label="Artikel" value={form.article_id} onChange={(v) => set('article_id', v)} options={articleOptions} required />
              {releasedArticles.length === 0 && (
                <div style={{ fontSize: 12, color: '#92400e', background: '#fffbeb', border: '1px solid #fde68a', borderRadius: 8, padding: '8px 10px' }}>
                  Kein freigegebener Artikel vorhanden. Nur Artikel im Status «Freigegeben» können referenziert werden.
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
              <Row k="Artikel" v={articleLabel} />
              <Row k="Menge" v={record?.quantity != null ? `${record.quantity} ${record.article_unit ? unitLabel(record.article_unit) : ''}`.trim() : '—'} />
              <Row k="Wunsch-Liefertermin" v={record?.desired_delivery_date ? localDate(record.desired_delivery_date) : 'Schnellstmöglich'} />
            </>
          )}
        </div>

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

        {/* Prozess */}
        {showProcess ? (
          <>
            <SectionTitle icon={Workflow}>Prozess</SectionTitle>
            <div style={{ ...cardStyle, paddingTop: 14, paddingBottom: 14 }}>
              <ProcessStepper
                nodes={steps.map((s) => ({ key: s.step_type, label: s.label, state: toStepperState(s.state) }))}
                selectedKey={currentStep ?? undefined}
                onSelect={setSelStep}
              />
            </div>
            <StepPanel type={currentStep} stepState={currentStepState} order={record as Order} viewerRole={viewerRole} onSaved={onSaved} />
          </>
        ) : !isStaff && hasPurchase ? (
          <>
            <SectionTitle icon={Workflow}>Prozess</SectionTitle>
            <PurchaseStepPanel order={record as Order} viewerRole={viewerRole} onOrderUpdated={onSaved} />
          </>
        ) : isStaff && demandEditable ? (
          <div style={{ display: 'flex', alignItems: 'flex-start', gap: 8, marginTop: 4, padding: '12px 14px', background: '#eff6ff', border: '1px solid #bfdbfe', borderRadius: 10, fontSize: 13, color: '#1e40af' }}>
            <Rocket size={15} style={{ flexShrink: 0, marginTop: 1 }} />
            <span><b>Freigeben</b> startet den hinterlegten Prozess des Artikels (Beschaffung,
              Serialisierung, Eingangskontrolle – je nach Artikel-Definition).</span>
          </div>
        ) : null}
      </div>

      {/* Meta footer (edit only) */}
      {!isCreate && (
        <div style={{ padding: '8px 20px', borderTop: '1px solid #E2E8F0', background: '#fff', flexShrink: 0, fontSize: 11, color: '#94a3b8', display: 'flex', gap: 16 }}>
          <span>Erstellt: {localDate(record.created_at)}</span>
          <span>Zuletzt geändert: {localDate(record.updated_at)}</span>
        </div>
      )}

      {/* Save bar (Bedarf erfassen/ändern, nur im Entwurf) */}
      {showSaveBar && (
        <div style={{ padding: '10px 20px', background: '#fff', borderTop: '1px solid #E2E8F0', display: 'flex', alignItems: 'center', gap: 10, flexShrink: 0 }}>
          <span style={{ flex: 1, fontSize: 13, color: error ? '#dc2626' : '#64748b', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {error ?? (isCreate ? 'Neuen Auftrag erfassen' : 'Ungespeicherte Änderungen')}
          </span>
          <button
            onClick={isCreate ? onCancel : () => { setForm(seedFrom(record)); setDateOpen(!!record?.desired_delivery_date); setError(null); }}
            style={{ padding: '6px 14px', borderRadius: 7, border: '1px solid #E2E8F0', background: '#fff', fontSize: 13, color: '#374151', cursor: 'pointer', flexShrink: 0 }}
          >
            {isCreate ? 'Abbrechen' : 'Verwerfen'}
          </button>
          <button
            onClick={save}
            disabled={saving}
            style={{ padding: '6px 14px', borderRadius: 7, border: 'none', background: saving ? '#93c5fd' : '#2563eb', color: '#fff', fontSize: 13, fontWeight: 600, cursor: saving ? 'wait' : 'pointer', flexShrink: 0 }}
          >
            {saving ? 'Speichern…' : isCreate ? 'Anlegen' : 'Speichern'}
          </button>
        </div>
      )}
    </div>
  );
}

// Rendert das Panel des gewählten Prozessschritts
function StepPanel({ type, stepState, order, viewerRole, onSaved }: {
  type: string | null;
  stepState: string;
  order: Order;
  viewerRole: ViewerRole;
  onSaved: (o: Order) => void;
}) {
  if (type === 'purchase') {
    return order.purchase
      ? <PurchaseStepPanel order={order} viewerRole={viewerRole} onOrderUpdated={onSaved} />
      : null;
  }
  if (type === 'serialization') {
    return <SerializationPanel order={order} stepState={stepState} onOrderUpdated={onSaved} />;
  }
  if (type === 'inspection') {
    return <InspectionPanel order={order} stepState={stepState} onOrderUpdated={onSaved} />;
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
