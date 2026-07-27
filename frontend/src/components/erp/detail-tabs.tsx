'use client';

import type { ElementType } from 'react';
import { cn } from '@/lib/utils';

/**
 * Einheitliche Reiter-Leiste für ALLE ERP-Detailansichten (Artikel, Auftrag, Instanz,
 * Benutzer, Lagerplatz, Unternehmen). EINE Optik über alle Datensätze (Design-Token
 * `.erp-tab`), damit «Dokumente» & Co. überall gleich aussehen und sich gleich anfühlen.
 */
export type DetailTab<K extends string = string> = { key: K; label: string; icon: ElementType };

export function DetailTabs<K extends string>({ tabs, active, onChange, style }: {
  tabs: DetailTab<K>[];
  active: K;
  onChange: (key: K) => void;
  style?: React.CSSProperties;
}) {
  return (
    <div style={{ display: 'flex', gap: 2, ...style }}>
      {tabs.map((t) => {
        const Icon = t.icon;
        return (
          <button key={t.key} onClick={() => onChange(t.key)}
            // Der aktive Reiter markiert sich für die Testnotizen: eine Notiz weiss
            // dadurch, in welcher Ansicht sie gesetzt wurde (`context.view`).
            data-fb-tab={active === t.key ? t.label : undefined}
            className={cn('erp-tab', active === t.key && 'erp-tab-active')}>
            <Icon size={15} /> {t.label}
          </button>
        );
      })}
    </div>
  );
}
