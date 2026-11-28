'use client';

import { useEffect, useState } from 'react';

/** Die drei Grundsätze – EINE Liste für Bühne und Handy. Die Bilder sind freigestellt (WebP mit
 *  Transparenz, Rand läuft weich aus). */
const PRINCIPLES = [
  { word: 'Funktioniert', line: 'Jeden Tag. Ohne Ausnahme.', image: '/brand/haltung-funktioniert.webp' },
  { word: 'Einfach', line: 'Schlank statt kompliziert.', image: '/brand/haltung-einfach.webp' },
  { word: 'Günstig', line: 'Vorhandenes nutzen, Unnötiges weglassen.', image: '/brand/haltung-guenstig.webp' },
] as const;

/** So lange steht ein Grundsatz auf der Bühne (die Linie unter ihm läuft genau so lange). */
const STEP_MS = 6000;

function Head() {
  return (
    <>
      <p className="erp-haltung-eyebrow">Unsere Haltung</p>
      <p className="erp-haltung-motto">Qualität in allem, was wir tun<em>.</em></p>
    </>
  );
}

/**
 * ►►► **Unsere Haltung** – was im ERP steht, wenn nichts geöffnet ist (Inhaber 28.11.2026). ◄◄◄
 * Am Computer eine **Bühne** wie auf der Website: links der Satz und die drei Grundsätze, rechts
 * EIN Bild gross; alle 6 s der nächste (eine Linie zeigt die Zeit), Klick wählt, bei «weniger
 * Bewegung» wechselt sie nicht von selbst. Am Handy (`compact`) alles auf einmal: drei
 * Zeilen, Bild links – derselbe Takt hebt eine nach der anderen hervor (Linie, Bild grösser);
 * oben in der Liste, scrollt mit weg.
 */
export function Haltung({ compact = false }: { compact?: boolean }) {
  const [at, setAt] = useCycle();
  if (compact) {
    return (
      <div className="erp-haltung-mob">
        <Head />
        <ul className="erp-haltung-list" style={{ ['--erp-haltung-t' as string]: `${STEP_MS}ms` }}>
          {PRINCIPLES.map((p, i) => (
            <li key={p.word} data-on={i === at || undefined} onClick={() => setAt(i)}>
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={p.image} alt="" width={88} height={88} />
              <p className="erp-haltung-word">{p.word}</p>
              <p className="erp-haltung-line">{p.line}</p>
            </li>
          ))}
        </ul>
      </div>
    );
  }
  return <Stage at={at} setAt={setAt} />;
}

/** Der Takt: alle `STEP_MS` der nächste Grundsatz; bei «weniger Bewegung» nur auf Klick. */
function useCycle(): [number, (i: number) => void] {
  const [at, setAt] = useState(0);
  const [still, setStill] = useState(false);
  useEffect(() => { setStill(window.matchMedia('(prefers-reduced-motion: reduce)').matches); }, []);
  useEffect(() => {
    if (still) return;
    const t = window.setTimeout(() => setAt((i) => (i + 1) % PRINCIPLES.length), STEP_MS);
    return () => window.clearTimeout(t);
  }, [at, still]);
  return [at, setAt];
}

function Stage({ at, setAt }: { at: number; setAt: (i: number) => void }) {
  return (
    <div className="erp-haltung-stage">
      <div className="erp-haltung-text">
        <Head />
        <ul className="erp-haltung-tabs">
          {PRINCIPLES.map((p, i) => (
            <li key={p.word}>
              <button type="button" aria-pressed={i === at} onClick={() => setAt(i)}
                style={{ ['--erp-haltung-t' as string]: `${STEP_MS}ms` }}>
                <span className="erp-haltung-word">{p.word}</span>
                <span className="erp-haltung-no">0{i + 1}</span>
                <span className="erp-haltung-line">{p.line}</span>
              </button>
            </li>
          ))}
        </ul>
      </div>
      <div className="erp-haltung-pic" aria-hidden="true">
        {PRINCIPLES.map((p, i) => (
          // eslint-disable-next-line @next/next/no-img-element
          <img key={p.word} src={p.image} alt="" data-on={i === at || undefined} />
        ))}
      </div>
    </div>
  );
}
