'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Download } from 'lucide-react';
import css from './beleg.module.css';

/**
 * **Der Kopf der Seite: das Wort, blass und gross** (wie `StageHero` der Website) – kein
 * Titel, kein Lead. Die Schrift richtet sich nach der Länge (`--n`), damit auch
 * «Auftragsbestätigung» in einer Zeile steht.
 */
export function StageWord({ word }: { word: string }) {
  return (
    <section className={css.stage} style={{ '--n': Math.max(word.length, 4) } as React.CSSProperties}>
      <h1 className={css.word}>{word}</h1>
    </section>
  );
}

/**
 * Nur für den Bildschirm: Luft um die Blätter, damit ihr Schatten nicht am Rand des iframe
 * endet. Der Druck bleibt das Dokument des Servers, unverändert.
 */
const FRAME_STYLE =
  '<style>@media screen{body{padding:32px 0 48px}}' +
  '@media screen and (max-width:860px){body{padding:16px 16px 32px}}</style>';

function framed(html: string): string {
  const at = html.indexOf('</head>');
  return at === -1 ? FRAME_STYLE + html : html.slice(0, at) + FRAME_STYLE + html.slice(at);
}

/**
 * ►►► **Das Papier – das Dokument, wie der Server es eingefroren hat.** ◄◄◄
 *
 * Hier wird nichts nachgebaut: das A4-HTML (`services/document.py`) steht in einem
 * `<iframe srcdoc>`, so hoch wie sein Inhalt. Ohne Skripte (`sandbox`); «Als PDF speichern»
 * ist der Druck des Browsers (die Vorlage trägt ihren A4-Druckstil selbst).
 */
export function Paper({ html, label }: { html: string; label: string }) {
  const frame = useRef<HTMLIFrameElement | null>(null);
  // Eine A4-Seite als Platz von Anfang an – der Inhalt verschiebt beim Laden nichts darunter.
  const [height, setHeight] = useState(1180);
  const doc = useMemo(() => framed(html), [html]);

  const measure = useCallback(() => {
    const body = frame.current?.contentDocument?.body;
    if (!body) return;
    const h = Math.ceil(body.getBoundingClientRect().height);
    if (h > 0) setHeight(h);
  }, []);

  useEffect(() => {
    window.addEventListener('resize', measure);
    return () => window.removeEventListener('resize', measure);
  }, [measure]);

  const onLoad = useCallback(() => {
    measure();
    // Die Schrift kommt nach dem Laden – sie ändert die Zeilen, also die Höhe.
    frame.current?.contentDocument?.fonts?.ready.then(measure).catch(() => undefined);
  }, [measure]);

  const print = useCallback(() => {
    const win = frame.current?.contentWindow;
    if (!win) return;
    // Der Dateiname des PDF ist der Titel der Seite – für die Dauer des Drucks der des Papiers.
    const before = document.title;
    const title = frame.current?.contentDocument?.title;
    if (title) document.title = title;
    try {
      win.focus();
      win.print();
    } finally {
      setTimeout(() => { document.title = before; }, 0);
    }
  }, []);

  return (
    <div className={css.paperZone}>
      <div className={css.paper}>
        <button type="button" className={css.dl} onClick={print}
          aria-label="Als PDF speichern" data-label="Als PDF speichern">
          <Download size={22} strokeWidth={1.75} />
        </button>
        <iframe ref={frame} title={label} srcDoc={doc} onLoad={onLoad}
          sandbox="allow-same-origin allow-modals" className={css.frame} style={{ height }} />
      </div>
    </div>
  );
}
