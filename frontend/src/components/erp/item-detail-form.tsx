'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Loader2, Check, AlertCircle, Send, CheckCircle2, XCircle, Clock,
  Plus, Trash2, GripVertical, ArrowRight, ExternalLink, RotateCcw,
  ListChecks, ChevronDown, ChevronRight,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { api } from '@/lib/api';
import { Tabs, TabList, TabTrigger, TabPanel } from '@/components/ui/tabs';
import { formatObjectId, formatDate } from '@/lib/utils';
import { ITEM_STATUS_CONFIG, VAT_RATE_LABELS } from '@/types';
import type { Item, ItemName, ItemSurface, ItemCategory, ItemStatus, VatRate, ProzessSchritt, WhereUsedEntry } from '@/types';

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

// ─── Link display ────────────────────────────────────────────────────────────

function LinkDisplay({ value }: { value: string }) {
  if (!value) return <p className="text-sm text-slate-900 py-1"><span className="text-slate-400 italic">—</span></p>;
  return (
    <div className="flex items-center gap-2 py-1">
      <span className="text-sm text-slate-500 truncate max-w-[160px]" title={value}>{value.replace(/^https?:\/\//, '').split('/')[0]}</span>
      <a
        href={value}
        target="_blank"
        rel="noopener noreferrer"
        className="flex items-center gap-1 px-2 py-1 text-xs font-medium text-blue-600 bg-blue-50 hover:bg-blue-100 rounded-md transition-colors shrink-0"
      >
        <ExternalLink className="h-3 w-3" />
        Öffnen
      </a>
    </div>
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
  serialization_type: string;
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
  const size = d1 != null && d2 != null && d3 != null ? `${fmtNum(d1)}x${fmtNum(d2)}x${fmtNum(d3)}` : '';
  return {
    name: item.name ?? '',
    name_id: item.name_id ?? null,
    unit: item.unit ?? 'Stk',
    serialization_type: item.serialization_type ?? 'none',
    order_number: item.order_number ?? '',
    order_link: item.order_link ?? '',
    onshape_link: item.onshape_link ?? '',
    weight_g: fmtNum(item.weight_g),
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

function fmtNum(v: string | null | undefined): string {
  if (v == null || v === '') return '';
  const n = parseFloat(String(v));
  return isNaN(n) ? String(v) : String(n);
}

function buildPayload(form: FormState): Partial<Item> {
  const sizeResult = parseSizeInput(form.size_input);
  const payload: Record<string, unknown> = {
    name: form.name || undefined,
    name_id: form.name_id,
    unit: form.unit,
    serialization_type: form.serialization_type,
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

// ─── Prozess Tab ─────────────────────────────────────────────────────────────

const MODUS_LABELS: Record<string, string> = {
  konsumieren: 'Verbraucht',
  bereitstellen: 'Bereitstellen',
  erzeugen: 'Erzeugt',
  pruefen: 'Prüfen',
};

const AKTION_LABELS: Record<string, string> = {
  lager_abbuchen: 'Lager abbuchen',
  benachrichtigen: 'Benachrichtigen',
  dokument_erzeugen: 'Dokument erzeugen',
  objekt_erzeugen: 'Objekt erzeugen',
  gueltig_bis_setzen: 'Gültig-bis setzen',
};

function ProzessTab({
  itemId,
  isEditable,
}: {
  itemId: number;
  isEditable: boolean;
}) {
  const queryClient = useQueryClient();
  const [expanded, setExpanded] = useState<number | null>(null);
  const [adding, setAdding] = useState(false);
  const [newBeschreibung, setNewBeschreibung] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const dragIndexRef = useRef<number | null>(null);
  const [dragOverIdx, setDragOverIdx] = useState<number | null>(null);

  const { data: schritte = [], isLoading } = useQuery<ProzessSchritt[]>({
    queryKey: ['prozess-schritte', itemId],
    queryFn: () => api.getProzessSchritte(itemId),
    staleTime: 30_000,
  });

  async function handleAdd() {
    if (!newBeschreibung.trim()) return;
    setSaving(true);
    setError('');
    try {
      await api.createProzessSchritt(itemId, {
        position: schritte.length + 1,
        beschreibung: newBeschreibung.trim(),
      });
      queryClient.invalidateQueries({ queryKey: ['prozess-schritte', itemId] });
      setNewBeschreibung('');
      setAdding(false);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Fehler');
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(id: number) {
    try {
      await api.deleteProzessSchritt(itemId, id);
      queryClient.invalidateQueries({ queryKey: ['prozess-schritte', itemId] });
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Fehler');
    }
  }

  async function handleDrop(toIdx: number) {
    setDragOverIdx(null);
    const fromIdx = dragIndexRef.current;
    if (fromIdx === null || fromIdx === toIdx) return;
    dragIndexRef.current = null;
    const newOrder = [...schritte];
    const [moved] = newOrder.splice(fromIdx, 1);
    newOrder.splice(toIdx, 0, moved);
    try {
      await api.reorderProzessSchritte(itemId, newOrder.map((s) => s.id));
      queryClient.invalidateQueries({ queryKey: ['prozess-schritte', itemId] });
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Fehler');
    }
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-5 w-5 animate-spin text-slate-400" />
      </div>
    );
  }

  const inputCls = 'w-full px-3 py-2 text-sm border border-slate-200 rounded-lg bg-white focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none';

  return (
    <div className="px-6 py-5 space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wide">
          Prozessschritte ({schritte.length})
        </h3>
        {isEditable && (
          <button
            type="button"
            onClick={() => setAdding((v) => !v)}
            className="flex items-center gap-1.5 px-2.5 py-1.5 text-xs font-medium rounded-lg text-white transition-colors"
            style={{ background: '#E51A14' }}
          >
            <Plus className="h-3.5 w-3.5" />
            Schritt hinzufügen
          </button>
        )}
      </div>

      {error && (
        <p className="text-xs text-red-600 flex items-center gap-1.5">
          <AlertCircle className="h-3.5 w-3.5" />{error}
        </p>
      )}

      {schritte.length === 0 && !adding && (
        <div className="flex flex-col items-center justify-center py-10 text-center border border-dashed border-slate-200 rounded-xl">
          <ListChecks className="h-8 w-8 text-slate-300 mb-2" />
          <p className="text-sm text-slate-600 font-medium">Keine Prozessschritte</p>
          {isEditable && (
            <p className="text-xs text-slate-400 mt-1">Klicken Sie auf &quot;Schritt hinzufügen&quot;</p>
          )}
        </div>
      )}

      <div className="space-y-2">
        {schritte.map((schritt, idx) => (
          <div
            key={schritt.id}
            draggable={isEditable}
            onDragStart={() => { dragIndexRef.current = idx; }}
            onDragEnd={() => { setDragOverIdx(null); dragIndexRef.current = null; }}
            onDragOver={(e) => { e.preventDefault(); setDragOverIdx(idx); }}
            onDragLeave={() => setDragOverIdx(null)}
            onDrop={() => handleDrop(idx)}
            className={cn(
              'border rounded-xl overflow-hidden transition-colors',
              dragOverIdx === idx ? 'border-blue-300 bg-blue-50' : 'border-slate-200 bg-white',
            )}
          >
            <div
              className="flex items-center gap-3 px-3 py-2.5 cursor-pointer select-none hover:bg-slate-50 transition-colors"
              onClick={() => setExpanded(expanded === schritt.id ? null : schritt.id)}
            >
              {isEditable && (
                <GripVertical className="h-4 w-4 text-slate-300 shrink-0 cursor-grab" />
              )}
              <span className="text-xs font-mono font-semibold text-slate-400 shrink-0 w-5 text-center">
                {idx + 1}
              </span>
              <p className="flex-1 text-sm font-medium text-slate-900 truncate">
                {schritt.beschreibung}
              </p>
              <div className="flex items-center gap-1.5 shrink-0">
                {schritt.ressourcen && schritt.ressourcen.length > 0 && (
                  <span className="px-1.5 py-0.5 text-xs rounded bg-slate-100 text-slate-600">
                    {schritt.ressourcen.length} Res.
                  </span>
                )}
                {schritt.aktion && (
                  <span className="px-1.5 py-0.5 text-xs rounded bg-amber-50 text-amber-700">
                    {AKTION_LABELS[schritt.aktion.typ] ?? schritt.aktion.typ}
                  </span>
                )}
                {expanded === schritt.id
                  ? <ChevronDown className="h-4 w-4 text-slate-400" />
                  : <ChevronRight className="h-4 w-4 text-slate-400" />}
              </div>
            </div>

            {expanded === schritt.id && (
              <div className="px-4 pb-4 pt-1 border-t border-slate-100 space-y-3">
                {schritt.ressourcen && schritt.ressourcen.length > 0 && (
                  <div>
                    <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-1.5">Ressourcen</p>
                    <div className="space-y-1">
                      {schritt.ressourcen.map((r, i) => (
                        <div key={i} className="flex items-center gap-2 text-xs">
                          <span className="px-1.5 py-0.5 rounded bg-slate-100 text-slate-600 font-medium shrink-0">
                            {MODUS_LABELS[r.modus] ?? r.modus}
                          </span>
                          <span className="font-mono text-slate-700">{formatObjectId(r.objekt_id)}</span>
                          {r.menge != null && <span className="text-slate-500">× {r.menge}</span>}
                          {r.serial_pflicht && <span className="text-amber-600">S/N</span>}
                          {r.batch_pflicht && <span className="text-amber-600">Charge</span>}
                        </div>
                      ))}
                    </div>
                  </div>
                )}
                {schritt.daten_felder && schritt.daten_felder.length > 0 && (
                  <div>
                    <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-1.5">Datenfelder</p>
                    <div className="flex flex-wrap gap-1.5">
                      {schritt.daten_felder.map((f, i) => (
                        <span key={i} className="px-2 py-0.5 text-xs rounded-full bg-blue-50 text-blue-700 border border-blue-100">
                          {f.bezeichnung}{f.pflicht ? ' *' : ''}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
                {schritt.ergebnis_optionen && schritt.ergebnis_optionen.length > 0 && (
                  <div>
                    <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-1.5">Ergebnisoptionen</p>
                    <div className="flex gap-1.5">
                      {schritt.ergebnis_optionen.map((e, i) => (
                        <span key={i} className="px-2 py-0.5 text-xs rounded-full bg-green-50 text-green-700 border border-green-100">
                          {e.label}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
                {(schritt.onshape_link || schritt.dokument_link) && (
                  <div className="flex gap-2">
                    {schritt.onshape_link && (
                      <a href={schritt.onshape_link} target="_blank" rel="noopener noreferrer"
                        className="flex items-center gap-1 text-xs text-blue-600 hover:underline">
                        <ExternalLink className="h-3 w-3" />Onshape
                      </a>
                    )}
                    {schritt.dokument_link && (
                      <a href={schritt.dokument_link} target="_blank" rel="noopener noreferrer"
                        className="flex items-center gap-1 text-xs text-blue-600 hover:underline">
                        <ExternalLink className="h-3 w-3" />Dokument
                      </a>
                    )}
                  </div>
                )}
                {isEditable && (
                  <div className="flex justify-end pt-1 border-t border-slate-100">
                    <button
                      type="button"
                      onClick={() => handleDelete(schritt.id)}
                      className="flex items-center gap-1 px-2 py-1 text-xs text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                    >
                      <Trash2 className="h-3 w-3" />Löschen
                    </button>
                  </div>
                )}
              </div>
            )}
          </div>
        ))}
      </div>

      {adding && (
        <div className="p-4 border border-blue-200 bg-blue-50 rounded-xl space-y-3">
          <p className="text-xs font-semibold text-blue-700">Neuer Schritt</p>
          <input
            type="text"
            className={inputCls}
            placeholder="Beschreibung des Schritts…"
            value={newBeschreibung}
            onChange={(e) => setNewBeschreibung(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') handleAdd(); }}
            autoFocus
          />
          <div className="flex gap-2">
            <button
              type="button"
              onClick={handleAdd}
              disabled={!newBeschreibung.trim() || saving}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-white rounded-lg disabled:opacity-50 transition-colors"
              style={{ background: '#E51A14' }}
            >
              {saving ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Plus className="h-3.5 w-3.5" />}
              Hinzufügen
            </button>
            <button
              type="button"
              onClick={() => { setAdding(false); setNewBeschreibung(''); }}
              className="px-3 py-1.5 text-xs font-medium text-slate-600 bg-white border border-slate-200 rounded-lg hover:bg-slate-50 transition-colors"
            >
              Abbrechen
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

// ─── Where-Used Tab ──────────────────────────────────────────────────────────

function WhereUsedTab({ itemId, onNavigate }: { itemId: number; onNavigate?: (itemId: number, tab: string) => void }) {
  const { data: entries, isLoading, isError } = useQuery<WhereUsedEntry[]>({
    queryKey: ['where-used', itemId],
    queryFn: () => api.getItemWhereUsed(itemId),
    staleTime: 30_000,
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-5 w-5 animate-spin text-slate-400" />
      </div>
    );
  }

  if (isError) {
    return (
      <div className="px-6 py-5">
        <p className="text-sm text-red-600 flex items-center gap-2"><AlertCircle className="h-4 w-4" />Daten konnten nicht geladen werden.</p>
      </div>
    );
  }

  if (!entries || entries.length === 0) {
    return (
      <div className="px-6 py-12 flex flex-col items-center justify-center text-center">
        <ListChecks className="h-8 w-8 text-slate-300 mb-2" />
        <p className="text-sm font-medium text-slate-700">Keine Verwendungen gefunden</p>
        <p className="text-xs text-slate-400 mt-1">Dieser Artikel wird in keinem Prozessschritt als Komponente eingesetzt.</p>
      </div>
    );
  }

  return (
    <div className="px-6 py-5">
      <p className="text-xs text-slate-500 mb-3">
        Dieser Artikel wird in {entries.length} Prozessschritt{entries.length !== 1 ? 'en' : ''} verwendet:
      </p>
      <div className="border border-slate-200 rounded-xl overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 border-b border-slate-200">
            <tr>
              <th className="text-left px-3 py-2 text-xs font-semibold text-slate-500">Item</th>
              <th className="text-left px-3 py-2 text-xs font-semibold text-slate-500">Status</th>
              <th className="text-left px-3 py-2 text-xs font-semibold text-slate-500">Schritt</th>
              <th className="text-left px-3 py-2 text-xs font-semibold text-slate-500 w-20">Menge</th>
              <th className="w-10" />
            </tr>
          </thead>
          <tbody>
            {entries.map((e, i) => (
              <tr
                key={`${e.parent_item_id}-${i}`}
                onClick={() => onNavigate?.(e.parent_item_id, 'prozess')}
                className={cn('border-t border-slate-100 transition-colors', onNavigate ? 'hover:bg-blue-50 cursor-pointer' : 'hover:bg-slate-50')}
              >
                <td className="px-3 py-2.5">
                  <p className="text-sm font-medium text-slate-900">{e.parent_item_name}</p>
                  <p className="text-xs font-mono text-slate-400">{formatObjectId(e.parent_item_id)}</p>
                </td>
                <td className="px-3 py-2.5">
                  <span className={cn('px-2 py-0.5 rounded-full text-xs font-semibold', ITEM_STATUS_CONFIG[e.parent_item_status]?.color ?? 'bg-slate-100 text-slate-600')}>
                    {ITEM_STATUS_CONFIG[e.parent_item_status]?.label ?? e.parent_item_status}
                  </span>
                </td>
                <td className="px-3 py-2.5">
                  <p className="text-xs text-slate-700 truncate max-w-[180px]">{e.schritt_beschreibung}</p>
                  <p className="text-xs text-slate-400">Pos. {e.schritt_position}</p>
                </td>
                <td className="px-3 py-2.5 text-sm text-slate-700">{e.menge ?? '—'}</td>
                <td className="px-3 py-2.5">
                  <ArrowRight className={cn('h-4 w-4', onNavigate ? 'text-blue-400' : 'text-slate-400')} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ─── Invalidate Dialog ────────────────────────────────────────────────────────

function InvalidateDialog({
  item,
  onClose,
  onSuccess,
}: {
  item: Item;
  onClose: () => void;
  onSuccess: () => void;
}) {
  const [replacedByItem, setReplacedByItem] = useState<{ id: number; name: string } | null>(null);
  const [itemSearch, setItemSearch] = useState('');
  const [invalidating, setInvalidating] = useState(false);
  const [error, setError] = useState('');

  const { data: freigItems } = useQuery({
    queryKey: ['items-freigegeben'],
    queryFn: () => api.getItems({ status: 'FREIGEGEBEN', pageSize: 500 }),
    staleTime: 60_000,
  });

  const { data: whereUsed = [] } = useQuery<WhereUsedEntry[]>({
    queryKey: ['where-used', item.id],
    queryFn: () => api.getItemWhereUsed(item.id),
    staleTime: 30_000,
  });

  const activeParents = (whereUsed as WhereUsedEntry[]).filter(
    (e) => e.parent_item_status !== 'UNGUELTIG' && e.parent_item_status !== 'ERSETZT',
  );

  const filteredItems = (freigItems?.items ?? []).filter((i) => {
    if (i.id === item.id) return false;
    if (!itemSearch.trim()) return false;
    const q = itemSearch.trim().toLowerCase();
    return String(i.id).includes(q) || i.name.toLowerCase().includes(q);
  });

  async function doInvalidate(withReplacement: boolean) {
    setError('');
    setInvalidating(true);
    try {
      await api.invalidateItem(item.id, withReplacement && replacedByItem ? replacedByItem.id : undefined);
      onSuccess();
      onClose();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Fehler beim Speichern');
    } finally {
      setInvalidating(false);
    }
  }

  const inputCls = 'w-full px-3 py-2 text-sm border border-slate-200 rounded-lg bg-white focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none';

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-md mx-4 overflow-hidden">
        <div className="px-6 py-4 border-b border-slate-200">
          <h2 className="text-base font-semibold text-slate-900">Inaktiv / Ersetzen</h2>
          <p className="text-sm text-slate-500 mt-0.5">{item.name}</p>
        </div>
        <div className="px-6 py-4 space-y-4 max-h-96 overflow-y-auto">
          <div>
            <label className="block text-xs font-semibold text-slate-600 mb-2">
              Ersatzartikel <span className="text-slate-400 font-normal">(optional, nur FREIGEGEBEN)</span>
            </label>
            {replacedByItem ? (
              <div className="flex items-center gap-2 px-3 py-2 bg-green-50 border border-green-200 rounded-lg">
                <div className="flex-1 min-w-0">
                  <p className="text-xs font-mono font-semibold text-slate-900">{formatObjectId(replacedByItem.id)}</p>
                  <p className="text-xs text-slate-500 truncate">{replacedByItem.name}</p>
                </div>
                <button
                  type="button"
                  onClick={() => setReplacedByItem(null)}
                  className="shrink-0 p-0.5 rounded hover:bg-slate-100 text-slate-400 hover:text-slate-600"
                >
                  <XCircle className="h-4 w-4" />
                </button>
              </div>
            ) : (
              <>
                <input
                  className={inputCls}
                  placeholder="Artikelnummer oder Name suchen…"
                  value={itemSearch}
                  onChange={(e) => setItemSearch(e.target.value)}
                />
                {itemSearch.length > 0 && (
                  <div className="max-h-32 overflow-y-auto border border-slate-200 rounded-lg bg-white mt-1">
                    {filteredItems.length === 0 ? (
                      <p className="px-3 py-2 text-xs text-slate-400">Keine FREIGEGEBEN Artikel gefunden</p>
                    ) : (
                      filteredItems.slice(0, 10).map((i) => (
                        <button
                          key={i.id}
                          type="button"
                          onClick={() => { setReplacedByItem({ id: i.id, name: i.name }); setItemSearch(''); }}
                          className="flex w-full items-center gap-2 px-3 py-2 text-xs text-left hover:bg-slate-50 transition-colors"
                        >
                          <span className="font-mono font-semibold text-slate-900 shrink-0">{formatObjectId(i.id)}</span>
                          <span className="text-slate-600 truncate">{i.name}</span>
                        </button>
                      ))
                    )}
                  </div>
                )}
              </>
            )}
          </div>

          {activeParents.length > 0 && (
            <div className="p-3 bg-amber-50 border border-amber-200 rounded-xl">
              <p className="text-xs font-semibold text-amber-800 mb-2 flex items-center gap-1.5">
                <AlertCircle className="h-3.5 w-3.5 shrink-0" />
                {activeParents.length} übergeordnete Baugruppe{activeParents.length !== 1 ? 'n' : ''} werden auf Inaktiv gesetzt:
              </p>
              <ul className="space-y-1">
                {activeParents.map((e) => (
                  <li key={`${e.parent_item_id}-${e.schritt_position}`} className="flex items-center gap-2 text-xs text-amber-700">
                    <span className="font-mono font-semibold shrink-0">{formatObjectId(e.parent_item_id)}</span>
                    <span className="truncate">{e.parent_item_name}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {error && (
            <p className="text-xs text-red-600 flex items-center gap-1.5">
              <AlertCircle className="h-3.5 w-3.5 shrink-0" />{error}
            </p>
          )}
        </div>
        <div className="px-6 py-3 border-t border-slate-200 flex items-center justify-between gap-2">
          <button
            type="button"
            onClick={onClose}
            disabled={invalidating}
            className="px-3 py-2 text-sm font-medium text-slate-600 bg-white border border-slate-200 rounded-lg hover:bg-slate-50 transition-colors disabled:opacity-50"
          >
            Abbrechen
          </button>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => doInvalidate(false)}
              disabled={invalidating}
              className="flex items-center gap-1.5 px-3 py-2 text-sm font-medium text-red-600 bg-red-50 hover:bg-red-100 border border-red-200 rounded-lg disabled:opacity-50 transition-colors"
            >
              {invalidating && !replacedByItem && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
              Nur inaktiv setzen
            </button>
            <button
              type="button"
              onClick={() => doInvalidate(true)}
              disabled={invalidating || !replacedByItem}
              className="flex items-center gap-1.5 px-4 py-2 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-lg disabled:opacity-50 transition-colors"
            >
              {invalidating && !!replacedByItem && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
              Mit Ersatz ersetzen
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

// ─── Set Replacement Dialog ───────────────────────────────────────────────────

function SetReplacementDialog({
  item,
  onClose,
  onSuccess,
}: {
  item: Item;
  onClose: () => void;
  onSuccess: () => void;
}) {
  const [replacedByItem, setReplacedByItem] = useState<{ id: number; name: string } | null>(null);
  const [itemSearch, setItemSearch] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const { data: freigItems } = useQuery({
    queryKey: ['items-freigegeben'],
    queryFn: () => api.getItems({ status: 'FREIGEGEBEN', pageSize: 500 }),
    staleTime: 60_000,
  });

  const filteredItems = (freigItems?.items ?? []).filter((i) => {
    if (i.id === item.id) return false;
    if (!itemSearch.trim()) return false;
    const q = itemSearch.trim().toLowerCase();
    return String(i.id).includes(q) || i.name.toLowerCase().includes(q);
  });

  async function doSetReplacement() {
    if (!replacedByItem) return;
    setSaving(true);
    setError('');
    try {
      await api.setItemReplacement(item.id, replacedByItem.id);
      onSuccess();
      onClose();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Fehler beim Speichern');
    } finally {
      setSaving(false);
    }
  }

  const inputCls = 'w-full px-3 py-2 text-sm border border-slate-200 rounded-lg bg-white focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none';

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-md mx-4 overflow-hidden">
        <div className="px-6 py-4 border-b border-slate-200">
          <h2 className="text-base font-semibold text-slate-900">Ersatzartikel nachtragen</h2>
          <p className="text-sm text-slate-500 mt-0.5">{item.name}</p>
        </div>
        <div className="px-6 py-4 space-y-4">
          <div>
            <label className="block text-xs font-semibold text-slate-600 mb-2">
              Ersatzartikel <span className="text-red-500">*</span>
              <span className="text-slate-400 font-normal ml-1">(nur FREIGEGEBEN)</span>
            </label>
            {replacedByItem ? (
              <div className="flex items-center gap-2 px-3 py-2 bg-green-50 border border-green-200 rounded-lg">
                <div className="flex-1 min-w-0">
                  <p className="text-xs font-mono font-semibold text-slate-900">{formatObjectId(replacedByItem.id)}</p>
                  <p className="text-xs text-slate-500 truncate">{replacedByItem.name}</p>
                </div>
                <button
                  type="button"
                  onClick={() => setReplacedByItem(null)}
                  className="shrink-0 p-0.5 rounded hover:bg-slate-100 text-slate-400 hover:text-slate-600"
                >
                  <XCircle className="h-4 w-4" />
                </button>
              </div>
            ) : (
              <>
                <input
                  className={inputCls}
                  placeholder="Artikelnummer oder Name suchen…"
                  value={itemSearch}
                  onChange={(e) => setItemSearch(e.target.value)}
                />
                {itemSearch.length > 0 && (
                  <div className="max-h-32 overflow-y-auto border border-slate-200 rounded-lg bg-white mt-1">
                    {filteredItems.length === 0 ? (
                      <p className="px-3 py-2 text-xs text-slate-400">Keine FREIGEGEBEN Artikel gefunden</p>
                    ) : (
                      filteredItems.slice(0, 10).map((i) => (
                        <button
                          key={i.id}
                          type="button"
                          onClick={() => { setReplacedByItem({ id: i.id, name: i.name }); setItemSearch(''); }}
                          className="flex w-full items-center gap-2 px-3 py-2 text-xs text-left hover:bg-slate-50 transition-colors"
                        >
                          <span className="font-mono font-semibold text-slate-900 shrink-0">{formatObjectId(i.id)}</span>
                          <span className="text-slate-600 truncate">{i.name}</span>
                        </button>
                      ))
                    )}
                  </div>
                )}
              </>
            )}
          </div>
          {error && (
            <p className="text-xs text-red-600 flex items-center gap-1.5">
              <AlertCircle className="h-3.5 w-3.5 shrink-0" />{error}
            </p>
          )}
        </div>
        <div className="px-6 py-3 border-t border-slate-200 flex items-center justify-between">
          <button
            type="button"
            onClick={onClose}
            disabled={saving}
            className="px-3 py-2 text-sm font-medium text-slate-600 bg-white border border-slate-200 rounded-lg hover:bg-slate-50 transition-colors disabled:opacity-50"
          >
            Abbrechen
          </button>
          <button
            type="button"
            onClick={doSetReplacement}
            disabled={saving || !replacedByItem}
            className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-lg disabled:opacity-50 transition-colors"
          >
            {saving && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
            Ersatz speichern
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── Main component ──────────────────────────────────────────────────────────

interface ItemDetailFormProps {
  itemId: number;
  currentUserRole?: string;
  onRefresh?: () => void;
  initialTab?: string;
  onNavigate?: (itemId: number, tab: string) => void;
}

export function ItemDetailForm({ itemId, currentUserRole, onRefresh, initialTab, onNavigate }: ItemDetailFormProps) {
  const queryClient = useQueryClient();
  const [form, setForm] = useState<FormState | null>(null);
  const [sizeError, setSizeError] = useState<string | null>(null);
  const [saveStatus, setSaveStatus] = useState<'idle' | 'pending' | 'saved' | 'error'>('idle');
  const [validationErrors, setValidationErrors] = useState<string[]>([]);
  const [showInvalidateDialog, setShowInvalidateDialog] = useState(false);
  const [showSetReplacementDialog, setShowSetReplacementDialog] = useState(false);
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

  const { mutate: recallItem, isPending: recalling } = useMutation({
    mutationFn: () => api.recallItem(itemId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['item', itemId] });
      queryClient.invalidateQueries({ queryKey: ['objects'] });
      onRefresh?.();
    },
  });

  const handleSubmit = useCallback(() => {
    if (!form) return;
    const errors = validateForSubmit(form);
    if (!form.weight_g) {
      errors.push('Gewicht (g) ist erforderlich');
    }
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

      {/* Replacement / replaced info banners */}
      {item?.replaces_id && (
        <div className="mx-6 mt-3 p-3 bg-blue-50 border border-blue-200 rounded-lg flex items-center gap-2">
          <ArrowRight className="h-4 w-4 text-blue-500 shrink-0" />
          <p className="text-xs text-blue-700 min-w-0">
            <span className="font-medium">Ersatzartikel für: </span>
            <button
              type="button"
              onClick={() => onNavigate?.(item.replaces_id!, 'stammdaten')}
              className="font-mono font-semibold hover:underline"
            >
              {formatObjectId(item.replaces_id)}
            </button>
            {item.replaces_item_name && <span className="ml-1 text-blue-600">{item.replaces_item_name}</span>}
          </p>
        </div>
      )}
      {item?.replaced_by_id && (
        <div className="mx-6 mt-3 p-3 bg-slate-50 border border-slate-200 rounded-lg flex items-center gap-2">
          <ArrowRight className="h-4 w-4 text-slate-400 shrink-0" />
          <p className="text-xs text-slate-600 min-w-0">
            <span className="font-medium">Ersetzt durch: </span>
            <button
              type="button"
              onClick={() => onNavigate?.(item.replaced_by_id!, 'stammdaten')}
              className="font-mono font-semibold hover:underline text-blue-600"
            >
              {formatObjectId(item.replaced_by_id)}
            </button>
            {item.replaced_by_name && <span className="ml-1">{item.replaced_by_name}</span>}
          </p>
        </div>
      )}

      {/* Tabs */}
      <Tabs key={`${itemId}-${initialTab ?? 'stammdaten'}`} defaultTab={initialTab ?? 'stammdaten'} className="flex-1 flex flex-col overflow-hidden">
        <div className="px-6 bg-white border-b border-slate-200">
          <TabList>
            <TabTrigger value="stammdaten">Artikelstamm</TabTrigger>
            <TabTrigger value="sales">Sales & Shop</TabTrigger>
            <TabTrigger value="prozess">Prozess</TabTrigger>
            <TabTrigger value="verwendung">Verwendung</TabTrigger>
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
                  Serialisierung
                </label>
                {isEditable ? (
                  <select
                    value={form.serialization_type}
                    onChange={(e) => updateField('serialization_type', e.target.value)}
                    className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg bg-white focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none"
                  >
                    <option value="none">Einzelteil</option>
                    <option value="batch">Charge</option>
                    <option value="serial">Seriennummer</option>
                  </select>
                ) : (
                  <p className="text-sm text-slate-900 py-1">
                    {form.serialization_type === 'none' ? 'Einzelteil'
                      : form.serialization_type === 'batch' ? 'Charge'
                      : form.serialization_type === 'serial' ? 'Seriennummer'
                      : form.serialization_type}
                  </p>
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
                {isEditable
                  ? <FieldInput readOnly={false} value={form.order_link} onChange={(v) => updateField('order_link', v)} placeholder="https://…" type="url" />
                  : <LinkDisplay value={form.order_link} />}
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wide mb-1.5">Onshape-Link</label>
              {isEditable
                ? <FieldInput readOnly={false} value={form.onshape_link} onChange={(v) => updateField('onshape_link', v)} placeholder="https://cad.onshape.com/…" type="url" />
                : <LinkDisplay value={form.onshape_link} />}
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wide mb-1.5">
                  Gewicht (g)
                  {isEditable && <span className="text-red-500 ml-0.5">*</span>}
                </label>
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
                <p className="text-sm text-slate-900 py-1">
                  {item?.purchase_price != null ? fmtNum(String(item.purchase_price)) : <span className="text-slate-400 italic">—</span>}
                  {item?.purchase_price != null && <span className="ml-1 text-slate-500 text-xs">{form.purchase_currency}</span>}
                </p>
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wide mb-1.5">Lieferzeit (Tage)</label>
                <p className="text-sm text-slate-900 py-1">
                  {item?.lead_time_days != null ? item.lead_time_days : <span className="text-slate-400 italic">—</span>}
                  {item?.lead_time_days != null && <span className="ml-1 text-slate-500 text-xs">Tage</span>}
                </p>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wide mb-1.5">Lagerbestand</label>
                <p className="text-sm text-slate-900 py-1">{fmtNum(item?.stock_total ?? '0')} <span className="text-slate-500">{form.unit}</span></p>
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wide mb-1.5">Reserviert</label>
                <p className="text-sm text-slate-900 py-1">{fmtNum(item?.stock_reserved ?? '0')} <span className="text-slate-500">{form.unit}</span></p>
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
                      <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wide mb-1.5">
                        HS-Code
                      </label>
                      <div className="space-y-1">
                        <FieldInput readOnly={!isEditable} value={form.hs_code} onChange={(v) => updateField('hs_code', v)} placeholder="z.B. 8479.89.97" />
                        {isEditable && (
                          <p className="text-xs text-slate-400">
                            Harmonisierter System-Code für Zollanmeldungen.{' '}
                            <a
                              href="https://xtares.admin.ch/tares/login/loginFormFiller.do"
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-blue-500 hover:text-blue-700 inline-flex items-center gap-0.5"
                            >
                              Zolltarif CH (XTARES) <ExternalLink className="h-3 w-3" />
                            </a>
                          </p>
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              </>
            )}
          </TabPanel>

          {/* ── Prozess ── */}
          <TabPanel value="prozess">
            <ProzessTab itemId={itemId} isEditable={isEditable} />
          </TabPanel>

          {/* ── Verwendungsnachweise ── */}
          <TabPanel value="verwendung">
            <WhereUsedTab itemId={itemId} onNavigate={onNavigate} />
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
                    {item?.created_by_name && <span className="ml-1 font-medium">{item.created_by_name}</span>}
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
                      {item.submitted_by_name && <span className="ml-1 font-medium">{item.submitted_by_name}</span>}
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
                      {item.approved_by_name && <span className="ml-1 font-medium">{item.approved_by_name}</span>}
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
                        {sig.signed_by_name ?? `Benutzer #${sig.signed_by}`} · {formatDate(sig.signed_at)}
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
        {statusKey === 'IN_FREIGABE' && (
          <div className="flex items-center justify-between gap-3">
            <button
              type="button"
              onClick={() => recallItem()}
              disabled={recalling}
              className="flex items-center gap-2 px-3 py-2 text-sm font-medium text-slate-600 bg-white border border-slate-200 hover:bg-slate-50 rounded-lg transition-colors disabled:opacity-50"
            >
              {recalling ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RotateCcw className="h-3.5 w-3.5" />}
              Zurück zu Entwurf
            </button>
            {isAdmin && (
              <button
                type="button"
                onClick={() => approveItem()}
                disabled={approving}
                className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-green-600 hover:bg-green-700 rounded-lg transition-colors disabled:opacity-50"
              >
                {approving ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <CheckCircle2 className="h-3.5 w-3.5" />}
                Freigeben
              </button>
            )}
          </div>
        )}
        {statusKey === 'FREIGEGEBEN' && isAdmin && (
          <div className="flex items-center justify-end gap-2">
            <button
              type="button"
              onClick={() => setShowInvalidateDialog(true)}
              className="flex items-center gap-2 px-3 py-2 text-sm font-medium text-red-600 hover:bg-red-50 rounded-lg transition-colors"
            >
              <XCircle className="h-3.5 w-3.5" />
              Inaktiv / Ersetzen
            </button>
          </div>
        )}
        {(statusKey === 'ERSETZT' || statusKey === 'UNGUELTIG') && (
          <div className="flex items-center justify-between gap-3">
            <p className="text-xs text-slate-500 py-1">
              Dieser Artikel ist {statusKey === 'ERSETZT' ? 'ersetzt' : 'inaktiv'} und kann nicht mehr bearbeitet werden.
            </p>
            {isAdmin && !item?.replaced_by_id && (
              <button
                type="button"
                onClick={() => setShowSetReplacementDialog(true)}
                className="flex items-center gap-1.5 px-3 py-2 text-sm font-medium text-blue-600 hover:bg-blue-50 rounded-lg transition-colors shrink-0"
              >
                <Plus className="h-3.5 w-3.5" />
                Ersatzartikel nachtragen
              </button>
            )}
          </div>
        )}
      </div>

      {/* Dialogs */}
      {showInvalidateDialog && item && (
        <InvalidateDialog
          item={item}
          onClose={() => setShowInvalidateDialog(false)}
          onSuccess={() => {
            queryClient.invalidateQueries({ queryKey: ['item', itemId] });
            queryClient.invalidateQueries({ queryKey: ['objects'] });
            onRefresh?.();
          }}
        />
      )}
      {showSetReplacementDialog && item && (
        <SetReplacementDialog
          item={item}
          onClose={() => setShowSetReplacementDialog(false)}
          onSuccess={() => {
            queryClient.invalidateQueries({ queryKey: ['item', itemId] });
            queryClient.invalidateQueries({ queryKey: ['objects'] });
            onRefresh?.();
          }}
        />
      )}
    </div>
  );
}
