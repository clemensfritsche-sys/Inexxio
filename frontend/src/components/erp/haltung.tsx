'use client';

import { useId } from 'react';
import { cn } from '@/lib/utils';

/** Die drei Grundsätze – EINE Liste für den Kreis und seine Beschreibung. */
const PRINCIPLES = [
  { word: 'Funktioniert', line: 'Jeden Tag. Ohne Ausnahme.', image: '/brand/haltung-funktioniert.webp', x: 280, y: 100 },
  { word: 'Einfach', line: 'Schlank statt kompliziert.', image: '/brand/haltung-einfach.webp', x: 150, y: 325 },
  { word: 'Günstig', line: 'Vorhandenes nutzen, Unnötiges weglassen.', image: '/brand/haltung-guenstig.webp', x: 410, y: 325 },
] as const;

const R = 52;

/**
 * ►►► **Unsere Haltung** – was im ERP steht, wenn nichts geöffnet ist (Inhaber 28.11.2026): der
 * grosse Satz und darunter ein Kreis, auf dem die drei Grundsätze zusammen stehen, in der Mitte
 * «So arbeiten wir». ◄◄◄ Am Computer füllt sie den leeren Detailbereich, am Handy steht sie
 * oben in der Liste und scrollt mit weg (`compact`: ohne Unterzeilen, sie wären zu klein).
 */
export function Haltung({ compact = false }: { compact?: boolean }) {
  const id = useId().replace(/:/g, '');
  const label = PRINCIPLES.map((p) => `${p.word}: ${p.line}`).join(' ') + ' In der Mitte: So arbeiten wir.';
  return (
    <div className={cn('erp-haltung', compact && 'erp-haltung-compact')}>
      <p className="erp-haltung-eyebrow">Unsere Haltung</p>
      <p className="erp-haltung-motto">Qualität in allem, was wir tun<em>.</em></p>
      <svg className="erp-haltung-kreis" viewBox={compact ? '0 12 560 404' : '0 -12 560 446'} role="img" aria-label={label}>
        <defs>
          {PRINCIPLES.map((p, i) => (
            <clipPath key={p.word} id={`${id}-${i}`}><circle cx={p.x} cy={p.y} r={R} /></clipPath>
          ))}
        </defs>
        <circle className="erp-haltung-ring" cx={280} cy={250} r={150} />
        <g className="erp-haltung-g erp-haltung-g4">
          <text className="erp-haltung-mid" x={280} y={compact ? 242 : 246} textAnchor="middle">So arbeiten</text>
          <text className="erp-haltung-mid" x={280} y={compact ? 274 : 268} textAnchor="middle">wir</text>
        </g>
        {PRINCIPLES.map((p, i) => {
          const top = p.y < 250;
          return (
            <g key={p.word} className={`erp-haltung-g erp-haltung-g${i + 1}`}>
              <circle className="erp-haltung-node" cx={p.x} cy={p.y} r={R} />
              <image href={p.image} x={p.x - R} y={p.y - R} width={R * 2} height={R * 2}
                clipPath={`url(#${id}-${i})`} preserveAspectRatio="xMidYMid slice" />
              <circle className="erp-haltung-edge" cx={p.x} cy={p.y} r={R} />
              <text className="erp-haltung-word" x={p.x} y={top ? (compact ? p.y - R - 14 : 14) : p.y + R + (compact ? 30 : 26)} textAnchor="middle">{p.word}</text>
              {!compact && (
                <text className="erp-haltung-line" x={p.x} y={top ? 34 : p.y + R + 46} textAnchor="middle">{p.line}</text>
              )}
            </g>
          );
        })}
      </svg>
    </div>
  );
}
