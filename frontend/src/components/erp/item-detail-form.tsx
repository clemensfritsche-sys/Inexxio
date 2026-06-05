'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Loader2, Check, AlertCircle, Send, CheckCircle2, XCircle, Clock,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { api } from '@/lib/api';
import { Tabs, TabList, TabTrigger, TabPanel } from '@/components/ui/tabs';
import { formatObjectId, formatDate } from '@/lib/utils';
import { ITEM_STATUS_CONFIG, VAT_RATE_LABELS } from '@/types';
import type { Item, ItemName, ItemSurface, ItemCategory, ItemStatus, VatRate } from '@/types';

// ─── Simple field input ──────────────────────────────────────────────────────

function FieldInput({
  readOnly, value, onChange, placeholder, type = 'text', min, step,
}: {
  readOnly?: boolean;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  type?: string;
  min?: string;
  step?: string;
}) {
  if (readOnly) {
    return <p className="text-sm text-slate-900 py-1">{value || <span className="text-slate-400 italic">—</span>}</p>;
  }
  return (
    <input
      type={type}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder={placeholder}
      min={min}
      step={step}
      className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg bg-white focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none transition-all"
    />
  );
}

// ─── Status stepper ─────────────────────────────────────────────────────────

function StatusStepper({ status }: { status: ItemStatus }) {
  const terminalStatuses: ItemStatus[] = ['ERSETZT', 'UNGUELTIG'];
  if (terminalStatuses.includes(status)) {
    return (
      <div className="flex items-center gap-2 py-2">
        <span className={cn('px-3 py-1 rounded-full text-xs font-semibold', ITEM_STATUS_CONFIG[status]?.color)}>
          {ITEM_STATUS_CONFIG[status]?.label ?? status}
        </span>
        <span className="text-xs text-slate-400">Endstatus – keine weiteren Aktionen möglich</span>
      </div>
    );
  }

  const steps: { key: ItemStatus; label: string }[] = [
    { key: 'ENTWURF', label: 'Entwurf' },
    { key: 'IN_FREIGABE', label: 'In Freigabe' },
    { key: 'FREIGEGEBEN', label: 'Freigegeben' },
  ];
  const currentIndex = steps.findIndex((s) => s.key === status);

  return (
    <div className="flex items-center">
      {steps.map((step, index) => {
        const isDone = index < currentIndex;
        const isCurrent = index === currentIndex;
        return (
          <div key={step.key} className="flex items-center flex-1 last:flex-none">
            <div className="flex flex-col items-center">
              <div className={cn(
                'flex h-6 w-6 items-center justify-center rounded-full text-xs font-semibold border-2 transition-colors',
                isDone ? 'bg-green-600 border-green-600 text-white'
                  : isCurrent ? 'border-blue-600 text-blue-600 bg-white'
                  : 'border-slate-300 text-slate-400 bg-white',
              )}>
                {isDone ? <Check className="h-3 w-3" /> : index + 1}
              </div>
              <span className={cn(
                'mt-1 text-xs whitespace-nowrap',
                isDone ? 'text-green-600' : isCurrent ? 'text-blue-600 font-medium' : 'text-slate-400',
              )}>
                {step.label}
              </span>
            </div>
            {index < steps.length - 1 && (
              <div className={cn('flex-1 h-0.5 mx-2 mb-4', isDone ? 'bg-green-400' : 'bg-slate-200')} />
            )}
          </div>
        );
      })}
    </div>
  );
}

// ─── Form state ──────────────────────────────────────────────────────────────

interface FormState {
  name: string;
  name_id: number | null;
  unit: string;
  batch_allowed: boolean;
  order_number: string;
  order_link: string;
  onshape_link: string;
  weight_g: string;
  size_input: string;
  surface_id: number | null;
  purchase_price: string;
  purchase_currency: string;
  lead_time_days: string;
  is_sales_product: boolean;
  sales_price: string;
  sales_currency: string;
  category_id: number | null;
  vat_rate: string;
  shop_description_long: string;
  seo_title: string;
  seo_description: string;
  hs_code: string;
}

function itemToFormState(item: Item): FormState {
  const d1 = item.dim_1_mm, d2 = item.dim_2_mm, d3 = item.dim_3_mm;
  const size = d1 != null && d2 != null && d3 != null ? `${d1}x${d2}x${d3}` : '';
  return {
    name: item.name ?? '',
    name_id: item.name_id ?? null,
    unit: item.unit ?? 'Stk',
    batch_allowed: item.batch_allowed ?? false,
    order_number: item.order_number ?? '',
    order_link: item.order_link ?? '',
    onshape_link: item.onshape_link ?? '',
    weight_g: item.weight_g != null ? String(item.weight_g) : '',
    size_input: size,
    surface_id: item.surface_id ?? null,
    purchase_price: item.purchase_price != null ? String(item.purchase_price) : '',
    purchase_currency: item.purchase_currency ?? 'CHF',
    lead_time_days: item.lead_time_days != null ? String(item.lead_time_days) : '',
    is_sales_product: item.is_sales_product ?? false,
    sales_price: item.sales_price != null ? String(item.sales_price) : '',
    sales_currency: item.sales_currency ?? 'CHF',
    category_id: item.category_id ?? null,
    vat_rate: item.vat_rate ?? '',
    shop_description_long: item.shop_description_long ?? '',
    seo_title: item.seo_title ?? '',
    seo_description: item.seo_description ?? '',
    hs_code: item.hs_code ?? '',
  };
}

function parseSizeInput(input: string): { valid: boolean; dims?: { dim_1_mm: number; dim_2_mm: number; dim_3_mm: number } } {
  if (!input.trim()) return { valid: true };
  const parts = input.split('x').map((s) => parseFloat(s.trim()));
  if (parts.length !== 3 || parts.some(isNaN) || parts.some((n) => n <= 0)) return { valid: false };
  const [a, b, c] = parts;
  if (a > b || b > c) return { valid: false };
  return { valid: true, dims: { dim_1_mm: a, dim_2_mm: b, dim_3_mm: c } };
}

function buildPayload(form: FormState): Partial<Item> {
  const sizeResult = parseSizeInput(form.size_input);
  const payload: Record<string, unknown> = {
    name: form.name || undefined,
    name_id: form.name_id,
    unit: form.unit,
    batch_allowed: form.batch_allowed,
    order_number: form.order_number || null,
    order_link: form.order_link || null,
    onshape_link: form.onshape_link || null,
    weight_g: form.weight_g ? parseFloat(form.weight_g) : null,
    surface_id: form.surface_id,
    purchase_price: form.purchase_price ? parseFloat(form.purchase_price) : null,
    purchase_currency: form.purchase_currency,
    lead_time_days: form.lead_time_days ? parseInt(form.lead_time_days) : null,
    is_sales_product: form.is_sales_product,
    sales_price: form.is_sales_product && form.sales_price ? parseFloat(form.sales_price) : null,
    sales_currency: form.sales_currency,
    category_id: form.is_sales_product ? form.category_id : null,
    vat_rate: form.is_sales_product ? (form.vat_rate || null) : null,
    shop_description_long: form.shop_description_long || null,
    seo_title: form.seo_title || null,
    seo_description: form.seo_description || null,
    hs_code: form.hs_code || null,
  };
  if (sizeResult.valid && sizeResult.dims) {
    payload.dim_1_mm = sizeResult.dims.dim_1_mm;
    payload.dim_2_mm = sizeResult.dims.dim_2_mm;
    payload.dim_3_mm = sizeResult.dims.dim_3_mm;
  } else if (sizeResult.valid) {
    payload.dim_1_mm = null;
    payload.dim_2_mm = null;
    payload.dim_3_mm = null;
  }
  return payload as Partial<Item>;
}

function validateForSubmit(form: FormState): string[] {
  const errors: string[] = [];
  if (!form.name_id) errors.push('Artikelname muss aus der Namensliste ausgewählt werden');
  if (!form.unit) errors.push('Mengeneinheit ist erforderlich');
  if (form.size_input && !parseSizeInput(form.size_input).valid) {
    errors.push('Abmessungen: Format muss NxNxN (aufsteigend) sein, z.B. 23x45x2003');
  }
  if (form.is_sales_product) {
    if (!form.sales_price) errors.push('Verkaufspreis ist erforderlich (Verkaufsartikel)');
    if (!form.category_id) errors.push('Produktkategorie ist erforderlich (Verkaufsartikel)');
    if (!form.vat_rate) errors.push('MwSt-Satz ist erforderlich (Verkaufsartikel)');
  }
  return errors;
}

// ─── Main component ──────────────────────────────────────────────────────────

interface ItemDetailFormProps {
  itemId: number;
  currentUserRole?: string;
  onRefresh?: () => void;
}

export function ItemDetailForm({ itemId, currentUserRole, onRefresh }: ItemDetailFormProps) {
  const queryClient = useQueryClient();
  const [form, setForm] = useState<FormState | null>(null);
  const [sizeError, setSizeError] = useState<string | null>(null);
  const [saveStatus, setSaveStatus] = useState<'idle' | 'pending' | 'saved' | 'error'>('idle');
  const [validationErrors, setValidationErrors] = useState<string[]>([]);
  const saveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const initializedForRef = useRef<number | null>(null);

  const { data: item, isLoading } = useQuery({
    queryKey: ['item', itemId],
    queryFn: () => api.getItem(itemId),
    staleTime: 30_000,
  });

  const { data: itemNames = [] } = useQuery({
    queryKey: ['item-names'],
    queryFn: () => api.getItemNames(),
    staleTime: 120_000,
  });

  const { data: itemSurfaces = [] } = useQuery({
    queryKey: ['item-surfaces'],
    queryFn: () => api.getItemSurfaces(),
    staleTime: 120_000,
  });

  const { data: itemCategories = [] } = useQuery({
    queryKey: ['item-categories'],
    queryFn: () => api.getItemCategories(),
    staleTime: 120_000,
  });

  useEffect(() => {
    if (item && item.id === itemId && initializedForRef.current !== itemId) {
      setForm(itemToFormState(item));
      initializedForRef.current = itemId;
      setSaveStatus('idle');
      setSizeError(null);
      setValidationErrors([]);
    }
  }, [item, itemId]);

  useEffect(() => {
    if (initializedForRef.current !== null && initializedForRef.current !== itemId) {
      setForm(null);
      setSaveStatus('idle');
      setSizeError(null);
      setValidationErrors([]);
    }
  }, [itemId]);

  const isEditable = item?.status === 'ENTWURF';
  const isAdmin = currentUserRole === 'admin';

  const scheduleSave = useCallback((updatedForm: FormState) => {
    if (!isEditable) return;
    if (saveTimerRef.current) clearTimeout(saveTimerRef.current);
    setSaveStatus('pending');
    saveTimerRef.current = setTimeout(async () => {
      const sizeResult = parseSizeInput(updatedForm.size_input);
      if (updatedForm.size_input && !sizeResult.valid) { setSaveStatus('error'); return; }
      try {
        await api.updateItem(itemId, buildPayload(updatedForm));
        setSaveStatus('saved');
        queryClient.invalidateQueries({ queryKey: ['item', itemId] });
        queryClient.invalidateQueries({ queryKey: ['objects'] });
        onRefresh?.();
      } catch {
        setSaveStatus('error');
      }
    }, 3000);
  }, [isEditable, itemId, queryClient, onRefresh]);

  const updateField = useCallback(<K extends keyof FormState>(key: K, value: FormState[K]) => {
    if (key === 'size_input') {
      const result = parseSizeInput(String(value));
      setSizeError(result.valid ? null : 'Format: z.B. 23x45x2003 (aufsteigend, positive Zahlen)');
    }
    setForm((prev) => {
      if (!prev) return prev;
      const next = { ...prev, [key]: value };
      scheduleSave(next);
      return next;
    });
  }, [scheduleSave]);

  const { mutate: submitItem, isPending: submitting } = useMutation({
    mutationFn: () => api.submitItem(itemId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['item', itemId] });
      queryClient.invalidateQueries({ queryKey: ['objects'] });
      onRefresh?.();
      setValidationErrors([]);
    },
  });

  const { mutate: approveItem, isPending: approving } = useMutation({
    mutationFn: () => api.approveItem(itemId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['item', itemId] });
      queryClient.invalidateQueries({ queryKey: ['objects'] });
      onRefresh?.();
    },
  });

  const { mutate: invalidateItem, isPending: invalidating } = useMutation({
    mutationFn: () => api.invalidateItem(itemId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['item', itemId] });
      queryClient.invalidateQueries({ queryKey: ['objects'] });
      onRefresh?.();
    },
  });

  const handleSubmit = useCallback(() => {
    if (!form) return;
    const errors = validateForSubmit(form);
    if (errors.length > 0) { setValidationErrors(errors); return; }
    setValidationErrors([]);
    submitItem();
  }, [form, submitItem]);

  if (isLoading || !form) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <Loader2 className="h-6 w-6 animate-spin text-slate-400" />
      </div>
    );
  }

  const statusKey = (item?.status ?? 'ENTWURF') as ItemStatus;
  const activeNames = (itemNames as ItemName[]).filter((n) => n.is_active);
  const activeSurfaces = (itemSurfaces as ItemSurface[]).filter((s) => s.is_active);
  const activeCategories = (itemCategories as ItemCategory[]).filter((c) => c.is_active);

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      {/* Header */}
      <div className="px-6 py-4 border-b border-slate-200 bg-white">
        <div className="flex items-start justify-between mb-3">
          <div className="min-w-0 flex-1 mr-3">
            <p className="text-xs font-mono text-slate-400 mb-0.5">{formatObjectId(itemId)}</p>
            <h2 className="text-lg font-semibold text-slate-900 leading-tight truncate">
              {item?.name || 'Neuer Artikel'}
            </h2>
          </div>
          <div className="flex flex-col items-end gap-1.5 shrink-0">
            <span className={cn('px-2.5 py-0.5 rounded-full text-xs font-semibold', ITEM_STATUS_CONFIG[statusKey]?.color)}>
              {ITEM_STATUS_CONFIG[statusKey]?.label ?? statusKey}
            </span>
            {saveStatus === 'pending' && (
              <span className="flex items-center gap-1 text-xs text-slate-400">
                <Loader2 className="h-3 w-3 animate-spin" />Speichert…
              </span>
            )}
            {saveStatus === 'saved' && (
              <span className="flex items-center gap-1 text-xs text-green-600">
                <Check className="h-3 w-3" />Gespeichert
              </span>
            )}
            {saveStatus === 'error' && (
              <span className="flex items-center gap-1 text-xs text-red-500">
                <AlertCircle className="h-3 w-3" />Fehler
              </span>
            )}
          </div>
        </div>
        <StatusStepper status={statusKey} />
      </div>

      {/* Validation errors */}
      {validationErrors.length > 0 && (
        <div className="mx-6 mt-3 p-3 bg-red-50 border border-red-200 rounded-lg">
          <p className="text-xs font-semibold text-red-700 mb-1.5 flex items-center gap-1.5">
            <AlertCircle className="h-3.5 w-3.5" />Pflichtfelder fehlen:
          </p>
          <ul className="list-disc list-inside space-y-0.5">
            {validationErrors.map((e) => (
              <li key={e} className="text-xs text-red-600">{e}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Tabs */}
      <Tabs defaultTab="stammdaten" className="flex-1 flex flex-col overflow-hidden">
        <div className="px-6 bg-white border-b border-slate-200">
          <TabList>
            <TabTrigger value="stammdaten">Artikelstamm</TabTrigger>
            <TabTrigger value="sales">Sales & Shop</TabTrigger>
            <TabTrigger value="protokoll">Protokoll</TabTrigger>
          </TabList>
        </div>

        <div className="flex-1 overflow-y-auto">
          {/* ── Artikelstamm ── */}
          <TabPanel value="stammdaten" className="px-6 py-5 space-y-5">

            {/* Artikelname – predefined list only */}
            <div>
              <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wide mb-1.5">
                Artikelname <span className="text-red-500">*</span>
              </label>
              {isEditable ? (
                <select
                  value={form.name_id ?? ''}
                  onChange={(e) => {
                    const id = e.target.value ? Number(e.target.value) : null;
                    const found = activeNames.find((n) => n.id === id);
                    setForm((prev) => {
                      if (!prev) return prev;
                      const next = { ...prev, name_id: id, name: found?.label ?? prev.name };
                      scheduleSave(next);
                      return next;
                    });
                  }}
                  className={cn(
                    'w-full px-3 py-2 text-sm border rounded-lg bg-white focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none transition-all',
                    !form.name_id ? 'border-amber-300' : 'border-slate-200',
                  )}
                >
                  <option value="">— Artikelname auswählen —</option>
                  {activeNames.map((n) => (
                    <option key={n.id} value={n.id}>{n.label}</option>
                  ))}
                </select>
              ) : (
                <p className="text-sm text-slate-900 py-1">
                  {activeNames.find((n) => n.id === form.name_id)?.label || form.name || <span className="text-slate-400 italic">—</span>}
                </p>
              )}
              {isEditable && activeNames.length === 0 && (
                <p className="mt-1 text-xs text-amber-600">
                  Noch keine Artikelnamen definiert. Bitte zuerst unter Admin → Einstellungen → ERP-Konfiguration Namen anlegen.
                </p>
              )}
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wide mb-1.5">
                  Mengeneinheit <span className="text-red-500">*</span>
                </label>
                {isEditable ? (
                  <select
                    value={form.unit}
                    onChange={(e) => updateField('unit', e.target.value)}
                    className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg bg-white focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none"
                  >
                    {['Stk', 'mm', 'g', 'mm²'].map((u) => (
                      <option key={u} value={u}>{u}</option>
                    ))}
                  </select>
                ) : (
                  <p className="text-sm text-slate-900 py-1">{form.unit}</p>
                )}
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wide mb-1.5">
                  Chargenproduktion
                </label>
                {isEditable ? (
                  <label className="flex items-center gap-2 mt-2.5 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={form.batch_allowed}
                      onChange={(e) => updateField('batch_allowed', e.target.checked)}
                      className="h-4 w-4 rounded border-slate-300 text-blue-600"
                    />
                    <span className="text-sm text-slate-700">Erlaubt</span>
                  </label>
                ) : (
                  <p className="text-sm text-slate-900 py-1">{form.batch_allowed ? 'Ja' : 'Nein'}</p>
                )}
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wide mb-1.5">Bestellnummer</label>
                <FieldInput readOnly={!isEditable} value={form.order_number} onChange={(v) => updateField('order_number', v)} placeholder="z.B. SC-4521" />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wide mb-1.5">Bestelllink</label>
                <FieldInput readOnly={!isEditable} value={form.order_link} onChange={(v) => updateField('order_link', v)} placeholder="https://…" type="url" />
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wide mb-1.5">Onshape-Link</label>
              <FieldInput readOnly={!isEditable} value={form.onshape_link} onChange={(v) => updateField('onshape_link', v)} placeholder="https://cad.onshape.com/…" type="url" />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wide mb-1.5">Gewicht (g)</label>
                <FieldInput readOnly={!isEditable} value={form.weight_g} onChange={(v) => updateField('weight_g', v)} placeholder="z.B. 125" type="number" min="0" />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wide mb-1.5">Abmessungen (mm)</label>
                {isEditable ? (
                  <>
                    <input
                      type="text"
                      value={form.size_input}
                      onChange={(e) => updateField('size_input', e.target.value)}
                      placeholder="z.B. 23x45x2003"
                      className={cn(
                        'w-full px-3 py-2 text-sm border rounded-lg bg-white focus:ring-2 focus:border-transparent outline-none transition-all',
                        sizeError ? 'border-red-300 focus:ring-red-400' : 'border-slate-200 focus:ring-blue-500',
                      )}
                    />
                    {sizeError && <p className="mt-1 text-xs text-red-500">{sizeError}</p>}
                    {!sizeError && form.size_input && <p className="mt-1 text-xs text-slate-400">✓ Dim1 ≤ Dim2 ≤ Dim3</p>}
                  </>
                ) : (
                  <p className="text-sm text-slate-900 py-1">{form.size_input || <span className="text-slate-400 italic">—</span>}</p>
                )}
              </div>
            </div>

            {/* Oberfläche – predefined list only */}
            <div>
              <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wide mb-1.5">Oberfläche</label>
              {isEditable ? (
                <select
                  value={form.surface_id ?? ''}
                  onChange={(e) => updateField('surface_id', e.target.value ? Number(e.target.value) : null)}
                  className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg bg-white focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none"
                >
                  <option value="">— Keine Angabe —</option>
                  {activeSurfaces.map((s) => (
                    <option key={s.id} value={s.id}>{s.label}</option>
                  ))}
                </select>
              ) : (
                <p className="text-sm text-slate-900 py-1">
                  {activeSurfaces.find((s) => s.id === form.surface_id)?.label || <span className="text-slate-400 italic">—</span>}
                </p>
              )}
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wide mb-1.5">EK-Preis (CHF)</label>
                <FieldInput readOnly={!isEditable} value={form.purchase_price} onChange={(v) => updateField('purchase_price', v)} placeholder="0.00" type="number" min="0" step="0.01" />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wide mb-1.5">Lieferzeit (Tage)</label>
                <FieldInput readOnly={!isEditable} value={form.lead_time_days} onChange={(v) => updateField('lead_time_days', v)} placeholder="z.B. 14" type="number" min="0" />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wide mb-1.5">Lagerbestand</label>
                <p className="text-sm text-slate-900 py-1">{item?.stock_total ?? '0'}</p>
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wide mb-1.5">Reserviert</label>
                <p className="text-sm text-slate-900 py-1">{item?.stock_reserved ?? '0'}</p>
              </div>
            </div>
          </TabPanel>

          {/* ── Sales & Shop ── */}
          <TabPanel value="sales" className="px-6 py-5 space-y-5">
            <div className="flex items-center justify-between p-3 bg-slate-50 rounded-xl border border-slate-200">
              <div>
                <p className="text-sm font-medium text-slate-900">Verkaufsartikel</p>
                <p className="text-xs text-slate-500 mt-0.5">Artikel im Online-Shop anbieten</p>
              </div>
              {isEditable ? (
                <button
                  type="button"
                  onClick={() => updateField('is_sales_product', !form.is_sales_product)}
                  className={cn(
                    'relative w-11 h-6 rounded-full transition-colors',
                    form.is_sales_product ? 'bg-blue-600' : 'bg-slate-300',
                  )}
                >
                  <span className={cn(
                    'absolute top-0.5 left-0.5 h-5 w-5 rounded-full bg-white shadow transition-transform',
                    form.is_sales_product ? 'translate-x-5' : 'translate-x-0',
                  )} />
                </button>
              ) : (
                <span className="text-sm text-slate-900 font-medium">{form.is_sales_product ? 'Ja' : 'Nein'}</span>
              )}
            </div>

            {form.is_sales_product && (
              <>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wide mb-1.5">
                      Verkaufspreis (CHF) <span className="text-red-500">*</span>
                    </label>
                    <FieldInput readOnly={!isEditable} value={form.sales_price} onChange={(v) => updateField('sales_price', v)} placeholder="0.00" type="number" min="0" step="0.01" />
                  </div>
                  <div>
                    <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wide mb-1.5">
                      MwSt-Satz <span className="text-red-500">*</span>
                    </label>
                    {isEditable ? (
                      <select
                        value={form.vat_rate}
                        onChange={(e) => updateField('vat_rate', e.target.value)}
                        className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg bg-white focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none"
                      >
                        <option value="">— Wählen —</option>
                        {(Object.entries(VAT_RATE_LABELS) as [VatRate, string][]).map(([k, v]) => (
                          <option key={k} value={k}>{v}</option>
                        ))}
                      </select>
                    ) : (
                      <p className="text-sm text-slate-900 py-1">
                        {form.vat_rate ? VAT_RATE_LABELS[form.vat_rate as VatRate] ?? form.vat_rate : <span className="text-slate-400 italic">—</span>}
                      </p>
                    )}
                  </div>
                </div>

                {/* Produktkategorie – predefined list only */}
                <div>
                  <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wide mb-1.5">
                    Produktkategorie <span className="text-red-500">*</span>
                  </label>
                  {isEditable ? (
                    <select
                      value={form.category_id ?? ''}
                      onChange={(e) => updateField('category_id', e.target.value ? Number(e.target.value) : null)}
                      className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg bg-white focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none"
                    >
                      <option value="">— Kategorie auswählen —</option>
                      {activeCategories.map((c) => (
                        <option key={c.id} value={c.id}>{c.label}</option>
                      ))}
                    </select>
                  ) : (
                    <p className="text-sm text-slate-900 py-1">
                      {activeCategories.find((c) => c.id === form.category_id)?.label || <span className="text-slate-400 italic">—</span>}
                    </p>
                  )}
                </div>
              </>
            )}

            <div>
              <p className="text-xs font-semibold text-slate-400 uppercase tracking-widest mb-3 pt-2 border-t border-slate-100">SEO & Beschreibung</p>
              <div className="space-y-4">
                <div>
                  <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wide mb-1.5">Langbeschreibung</label>
                  {isEditable ? (
                    <textarea
                      value={form.shop_description_long}
                      onChange={(e) => updateField('shop_description_long', e.target.value)}
                      rows={4}
                      placeholder="Detaillierte Produktbeschreibung für den Online-Shop…"
                      className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg bg-white focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none resize-none transition-all"
                    />
                  ) : (
                    <p className="text-sm text-slate-900 whitespace-pre-wrap py-1">{form.shop_description_long || <span className="text-slate-400 italic">—</span>}</p>
                  )}
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wide mb-1.5">SEO-Titel</label>
                  <FieldInput readOnly={!isEditable} value={form.seo_title} onChange={(v) => updateField('seo_title', v)} placeholder="Seitentitel für Suchmaschinen" />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wide mb-1.5">SEO-Beschreibung</label>
                  {isEditable ? (
                    <textarea
                      value={form.seo_description}
                      onChange={(e) => updateField('seo_description', e.target.value)}
                      rows={2}
                      maxLength={200}
                      placeholder="Meta-Beschreibung (max. 160 Zeichen)"
                      className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg bg-white focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none resize-none transition-all"
                    />
                  ) : (
                    <p className="text-sm text-slate-900 py-1">{form.seo_description || <span className="text-slate-400 italic">—</span>}</p>
                  )}
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wide mb-1.5">HS-Code</label>
                  <FieldInput readOnly={!isEditable} value={form.hs_code} onChange={(v) => updateField('hs_code', v)} placeholder="z.B. 8479.89" />
                </div>
              </div>
            </div>
          </TabPanel>

          {/* ── Protokoll ── */}
          <TabPanel value="protokoll" className="px-6 py-5">
            <div className="space-y-4">
              <div className="flex items-start gap-3">
                <div className="flex h-7 w-7 items-center justify-center rounded-full bg-green-100 shrink-0">
                  <Check className="h-3.5 w-3.5 text-green-600" />
                </div>
                <div>
                  <p className="text-sm font-medium text-slate-900">Artikel erstellt</p>
                  <p className="text-xs text-slate-500 mt-0.5 flex items-center gap-1">
                    <Clock className="h-3 w-3" />{formatDate(item?.created_at ?? '')}
                  </p>
                </div>
              </div>
              {item?.submitted_at && (
                <div className="flex items-start gap-3">
                  <div className="flex h-7 w-7 items-center justify-center rounded-full bg-amber-100 shrink-0">
                    <Send className="h-3.5 w-3.5 text-amber-600" />
                  </div>
                  <div>
                    <p className="text-sm font-medium text-slate-900">Zur Freigabe eingereicht</p>
                    <p className="text-xs text-slate-500 mt-0.5 flex items-center gap-1">
                      <Clock className="h-3 w-3" />{formatDate(item.submitted_at)}
                    </p>
                  </div>
                </div>
              )}
              {item?.approved_at && (
                <div className="flex items-start gap-3">
                  <div className="flex h-7 w-7 items-center justify-center rounded-full bg-blue-100 shrink-0">
                    <CheckCircle2 className="h-3.5 w-3.5 text-blue-600" />
                  </div>
                  <div>
                    <p className="text-sm font-medium text-slate-900">Freigegeben</p>
                    <p className="text-xs text-slate-500 mt-0.5 flex items-center gap-1">
                      <Clock className="h-3 w-3" />{formatDate(item.approved_at)}
                    </p>
                  </div>
                </div>
              )}
              {item?.signatures && item.signatures.length > 0 && (
                <div className="mt-2 pt-3 border-t border-slate-100">
                  <p className="text-xs font-semibold text-slate-400 uppercase tracking-widest mb-2">Digitale Signaturen</p>
                  {item.signatures.map((sig) => (
                    <div key={sig.id} className="flex items-center gap-2 py-2 border-b border-slate-100 last:border-0">
                      <Check className="h-3.5 w-3.5 text-green-600 shrink-0" />
                      <span className="text-xs text-slate-600">
                        Benutzer #{sig.signed_by} · {formatDate(sig.signed_at)}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </TabPanel>
        </div>
      </Tabs>

      {/* Action bar */}
      <div className="px-6 py-3 border-t border-slate-200 bg-slate-50 shrink-0">
        {statusKey === 'ENTWURF' && (
          <div className="flex items-center justify-between gap-3">
            <p className="text-xs text-slate-500">Alle Pflichtfelder ausfüllen, dann zur Freigabe einreichen.</p>
            <button
              type="button"
              onClick={handleSubmit}
              disabled={submitting || !!sizeError}
              className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-white rounded-lg transition-colors disabled:opacity-50 shrink-0"
              style={{ background: '#E51A14' }}
            >
              {submitting ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Send className="h-3.5 w-3.5" />}
              Zur Freigabe einreichen
            </button>
          </div>
        )}
        {statusKey === 'IN_FREIGABE' && isAdmin && (
          <div className="flex items-center justify-between gap-3">
            <p className="text-xs text-slate-500">Artikel prüfen und freigeben.</p>
            <button
              type="button"
              onClick={() => approveItem()}
              disabled={approving}
              className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-green-600 hover:bg-green-700 rounded-lg transition-colors disabled:opacity-50"
            >
              {approving ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <CheckCircle2 className="h-3.5 w-3.5" />}
              Freigeben
            </button>
          </div>
        )}
        {statusKey === 'IN_FREIGABE' && !isAdmin && (
          <p className="text-xs text-slate-500 text-center py-1">
            Warte auf Freigabe durch einen Administrator.
          </p>
        )}
        {statusKey === 'FREIGEGEBEN' && isAdmin && (
          <div className="flex items-center justify-end gap-2">
            <button
              type="button"
              onClick={() => { if (confirm('Artikel wirklich ungültig setzen?')) invalidateItem(); }}
              disabled={invalidating}
              className="flex items-center gap-2 px-3 py-2 text-sm font-medium text-red-600 hover:bg-red-50 rounded-lg transition-colors disabled:opacity-50"
            >
              {invalidating ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <XCircle className="h-3.5 w-3.5" />}
              Ungültig setzen
            </button>
          </div>
        )}
        {(statusKey === 'ERSETZT' || statusKey === 'UNGUELTIG') && (
          <p className="text-xs text-slate-500 text-center py-1">
            Dieser Artikel ist {statusKey === 'ERSETZT' ? 'ersetzt' : 'ungültig'} und kann nicht mehr bearbeitet werden.
          </p>
        )}
      </div>
    </div>
  );
}
