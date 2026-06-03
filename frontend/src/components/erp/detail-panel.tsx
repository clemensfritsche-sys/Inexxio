'use client';

import { useState } from 'react';
import { formatDate, formatObjectId, relativeTime } from '@/lib/utils';
import { StatusBadge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Tabs, TabList, TabTrigger, TabPanel } from '@/components/ui/tabs';
import { ProcessTracker, ITEM_STEPS, WORK_PLAN_STEPS, BOM_STEPS } from './process-tracker';
import { typeIcons, typeLabels } from './object-row';
import { Check, Clock, ExternalLink, FileText, Link as LinkIcon } from 'lucide-react';
import type { UniversalObject } from '@/types';

interface DetailField {
  label: string;
  value: React.ReactNode;
}

function FieldGrid({ fields }: { fields: DetailField[] }) {
  return (
    <div className="grid grid-cols-2 gap-x-6 gap-y-4">
      {fields.map((field) => (
        <div key={field.label}>
          <dt className="text-xs font-medium text-slate-500 uppercase tracking-wide">
            {field.label}
          </dt>
          <dd className="mt-1 text-sm text-slate-900">
            {field.value ?? <span className="text-slate-400 italic">—</span>}
          </dd>
        </div>
      ))}
    </div>
  );
}

function AutosaveIndicator({ savedAt }: { savedAt?: string }) {
  return (
    <div className="flex items-center gap-1.5 text-xs text-green-600">
      <Check className="h-3.5 w-3.5" />
      <span>Gespeichert {savedAt || ''}</span>
    </div>
  );
}

interface DetailPanelProps {
  object: UniversalObject | null;
}

function getSteps(objectType: string) {
  switch (objectType) {
    case 'work_plan':
      return WORK_PLAN_STEPS;
    case 'bom':
      return BOM_STEPS;
    default:
      return ITEM_STEPS;
  }
}

function getFields(object: UniversalObject): DetailField[] {
  const base: DetailField[] = [
    { label: 'Objekt-Nr.', value: <span className="font-mono">{formatObjectId(object.id)}</span> },
    { label: 'Typ', value: typeLabels[object.object_type] },
    { label: 'Status', value: <StatusBadge status={object.status} /> },
    { label: 'Erstellt am', value: formatDate(object.created_at) },
    { label: 'Aktualisiert', value: relativeTime(object.updated_at) },
  ];

  if (object.data) {
    const d = object.data as unknown as Record<string, unknown>;
    if (d.unit) base.push({ label: 'Einheit', value: String(d.unit) });
    if (d.item_type) base.push({ label: 'Artikeltyp', value: String(d.item_type) });
    if (d.material) base.push({ label: 'Material', value: String(d.material) });
    if (d.weight_kg) base.push({ label: 'Gewicht', value: `${d.weight_kg} kg` });
    if (d.dimensions) base.push({ label: 'Abmessungen', value: String(d.dimensions) });
    if (d.drawing_number) base.push({ label: 'Zeichnungs-Nr.', value: String(d.drawing_number) });
    if (d.lead_time_days) base.push({ label: 'Lieferzeit', value: `${d.lead_time_days} Tage` });
    if (d.cost_price) base.push({ label: 'Einkaufspreis', value: `CHF ${d.cost_price}` });
    if (d.sales_price) base.push({ label: 'Verkaufspreis', value: `CHF ${d.sales_price}` });
    if (d.role) base.push({ label: 'Rolle', value: <StatusBadge status={String(d.role)} /> });
    if (d.email) base.push({ label: 'E-Mail', value: <a href={`mailto:${d.email}`} className="text-blue-600 hover:underline">{String(d.email)}</a> });
    if (d.phone) base.push({ label: 'Telefon', value: <a href={`tel:${d.phone}`} className="text-blue-600 hover:underline">{String(d.phone)}</a> });
    if (d.website) base.push({ label: 'Website', value: <a href={String(d.website)} target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline flex items-center gap-1">{String(d.website)}<ExternalLink className="h-3 w-3"/></a> });
  }

  return base;
}

export function DetailPanel({ object }: DetailPanelProps) {
  const [, setTab] = useState('details');

  if (!object) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center text-center p-12">
        <div className="flex h-16 w-16 items-center justify-center rounded-full bg-slate-100 mb-4">
          <FileText className="h-7 w-7 text-slate-400" />
        </div>
        <h3 className="text-base font-semibold text-slate-900 mb-1">Kein Objekt ausgewählt</h3>
        <p className="text-sm text-slate-500 max-w-xs">
          Wählen Sie ein Element aus der Liste links oder erstellen Sie ein neues Objekt.
        </p>
      </div>
    );
  }

  const steps = getSteps(object.object_type);
  const fields = getFields(object);
  const savedAt = new Date(object.updated_at).toLocaleTimeString('de-CH', {
    hour: '2-digit',
    minute: '2-digit',
  });

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      {/* Header */}
      <div className="px-6 py-4 border-b border-slate-200 bg-white">
        <div className="flex items-start gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-slate-100 text-slate-600 shrink-0 mt-0.5">
            {typeIcons[object.object_type]}
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-0.5">
              <span className="text-xs font-mono text-slate-400">{formatObjectId(object.id)}</span>
              <span className="text-xs text-slate-400">·</span>
              <span className="text-xs text-slate-400">{typeLabels[object.object_type]}</span>
            </div>
            <h2 className="text-lg font-semibold text-slate-900 leading-tight truncate">
              {object.title}
            </h2>
            {object.subtitle && (
              <p className="text-sm text-slate-500 mt-0.5">{object.subtitle}</p>
            )}
          </div>
          <div className="shrink-0 flex flex-col items-end gap-2">
            <StatusBadge status={object.status} />
            <AutosaveIndicator savedAt={savedAt} />
          </div>
        </div>

        {/* Process tracker */}
        {(object.object_type === 'item' || object.object_type === 'work_plan' || object.object_type === 'bom') && (
          <div className="mt-4">
            <ProcessTracker steps={steps} currentStep={object.status} />
          </div>
        )}
      </div>

      {/* Tabs */}
      <Tabs defaultTab="details" onChange={setTab} className="flex-1 flex flex-col overflow-hidden">
        <div className="px-6 bg-white border-b border-slate-200">
          <TabList>
            <TabTrigger value="details">Details</TabTrigger>
            <TabTrigger value="related">Verwandte</TabTrigger>
            <TabTrigger value="log">Protokoll</TabTrigger>
          </TabList>
        </div>

        <div className="flex-1 overflow-y-auto">
          <TabPanel value="details" className="px-6 py-4">
            <FieldGrid fields={fields} />

            {object.data && (
              (() => {
                const d = object.data as unknown as Record<string, unknown>;
                return d.description ? (
                  <div className="mt-6">
                    <h4 className="text-xs font-medium text-slate-500 uppercase tracking-wide mb-2">Beschreibung</h4>
                    <p className="text-sm text-slate-700 leading-relaxed">{String(d.description)}</p>
                  </div>
                ) : null;
              })()
            )}
          </TabPanel>

          <TabPanel value="related" className="px-6 py-4">
            <div className="text-center py-8">
              <LinkIcon className="h-8 w-8 text-slate-300 mx-auto mb-3" />
              <p className="text-sm text-slate-500">Keine verwandten Objekte gefunden.</p>
            </div>
          </TabPanel>

          <TabPanel value="log" className="px-6 py-4">
            <div className="space-y-3">
              <div className="flex items-start gap-3">
                <div className="flex h-7 w-7 items-center justify-center rounded-full bg-green-100 shrink-0 mt-0.5">
                  <Check className="h-3.5 w-3.5 text-green-600" />
                </div>
                <div>
                  <p className="text-sm text-slate-900">
                    Objekt erstellt
                  </p>
                  <p className="text-xs text-slate-500 mt-0.5 flex items-center gap-1">
                    <Clock className="h-3 w-3" />
                    {formatDate(object.created_at)}
                  </p>
                </div>
              </div>
              <div className="flex items-start gap-3">
                <div className="flex h-7 w-7 items-center justify-center rounded-full bg-blue-100 shrink-0 mt-0.5">
                  <Clock className="h-3.5 w-3.5 text-blue-600" />
                </div>
                <div>
                  <p className="text-sm text-slate-900">Zuletzt aktualisiert</p>
                  <p className="text-xs text-slate-500 mt-0.5 flex items-center gap-1">
                    <Clock className="h-3 w-3" />
                    {relativeTime(object.updated_at)}
                  </p>
                </div>
              </div>
            </div>
          </TabPanel>
        </div>
      </Tabs>

      {/* Action bar */}
      {object.object_type === 'item' && object.status === 'Entwurf' && (
        <div className="px-6 py-3 border-t border-slate-200 bg-slate-50 flex items-center justify-between">
          <p className="text-xs text-slate-500">
            Artikel freigeben, um ihn in Stücklisten verwenden zu können.
          </p>
          <Button size="sm" variant="primary">
            Artikel freigeben
          </Button>
        </div>
      )}
    </div>
  );
}
