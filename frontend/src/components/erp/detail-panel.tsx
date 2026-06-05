'use client';

import { formatDate, formatObjectId, relativeTime } from '@/lib/utils';
import { StatusBadge } from '@/components/ui/badge';
import { Tabs, TabList, TabTrigger, TabPanel } from '@/components/ui/tabs';
import { ProcessTracker, WORK_PLAN_STEPS, BOM_STEPS } from './process-tracker';
import { typeIcons, typeLabels } from './object-row';
import { Check, Clock, ExternalLink, FileText, Link as LinkIcon } from 'lucide-react';
import { UserDetail } from './user-detail';
import { ItemDetailForm } from './item-detail-form';
import type { UniversalObject } from '@/types';

interface DetailField {
  label: string;
  value: React.ReactNode;
}

function FieldGrid({ fields }: { fields: DetailField[] }) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-4">
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

interface DetailPanelProps {
  object: UniversalObject | null;
  currentUserRole?: string;
  onRefresh?: () => void;
  initialTab?: string;
  onNavigate?: (itemId: number, tab: string) => void;
}

function getSteps(objectType: string) {
  switch (objectType) {
    case 'work_plan': return WORK_PLAN_STEPS;
    case 'bom': return BOM_STEPS;
    default: return BOM_STEPS;
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
    if (d.role) base.push({ label: 'Rolle', value: <StatusBadge status={String(d.role)} /> });
    if (d.email) base.push({ label: 'E-Mail', value: <a href={`mailto:${d.email}`} className="text-blue-600 hover:underline">{String(d.email)}</a> });
    if (d.phone) base.push({ label: 'Telefon', value: <a href={`tel:${d.phone}`} className="text-blue-600 hover:underline">{String(d.phone)}</a> });
    if (d.website) base.push({
      label: 'Website',
      value: <a href={String(d.website)} target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline flex items-center gap-1">
        {String(d.website)}<ExternalLink className="h-3 w-3" />
      </a>,
    });
  }

  return base;
}

export function DetailPanel({ object, currentUserRole, onRefresh, initialTab, onNavigate }: DetailPanelProps) {
  // Items get the full editable form
  if (object?.object_type === 'item') {
    return (
      <ItemDetailForm
        key={object.id}
        itemId={object.id}
        currentUserRole={currentUserRole}
        onRefresh={onRefresh}
        initialTab={initialTab}
        onNavigate={onNavigate}
      />
    );
  }

  // Users get user detail
  if (object?.object_type === 'user') {
    return <UserDetail object={object} currentUserRole={currentUserRole} onRoleChanged={onRefresh} />;
  }

  // Empty state
  if (!object) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center text-center p-12">
        <div className="flex h-16 w-16 items-center justify-center rounded-full bg-slate-100 mb-4">
          <FileText className="h-7 w-7 text-slate-400" />
        </div>
        <h3 className="text-base font-semibold text-slate-900 mb-1">Kein Objekt ausgewählt</h3>
        <p className="text-sm text-slate-500 max-w-xs">
          Wählen Sie ein Element aus der Liste links oder erstellen Sie einen neuen Artikel über den + Button.
        </p>
      </div>
    );
  }

  const steps = getSteps(object.object_type);
  const fields = getFields(object);
  const savedAt = new Date(object.updated_at).toLocaleTimeString('de-CH', {
    hour: '2-digit', minute: '2-digit',
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
            <h2 className="text-lg font-semibold text-slate-900 leading-tight truncate">{object.title}</h2>
            {object.subtitle && <p className="text-sm text-slate-500 mt-0.5">{object.subtitle}</p>}
          </div>
          <div className="shrink-0 flex flex-col items-end gap-2">
            <StatusBadge status={object.status} />
            <div className="flex items-center gap-1.5 text-xs text-slate-400">
              <Check className="h-3.5 w-3.5" />
              <span>{savedAt}</span>
            </div>
          </div>
        </div>

        {(object.object_type === 'work_plan' || object.object_type === 'bom') && (
          <div className="mt-4">
            <ProcessTracker steps={steps} currentStep={object.status} />
          </div>
        )}
      </div>

      {/* Tabs */}
      <Tabs defaultTab="details" className="flex-1 flex flex-col overflow-hidden">
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
                  <p className="text-sm text-slate-900">Objekt erstellt</p>
                  <p className="text-xs text-slate-500 mt-0.5 flex items-center gap-1">
                    <Clock className="h-3 w-3" />{formatDate(object.created_at)}
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
                    <Clock className="h-3 w-3" />{relativeTime(object.updated_at)}
                  </p>
                </div>
              </div>
            </div>
          </TabPanel>
        </div>
      </Tabs>
    </div>
  );
}
