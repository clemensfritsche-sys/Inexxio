'use client';

import { useEffect, useState } from 'react';
import { api, assetUrl } from '@/lib/api';
import { Paper, StageWord } from './paper';
import css from './beleg.module.css';

type LegalKind = 'agb' | 'datenschutz' | 'impressum';

/** Das grosse Wort und der Name des Papiers je Rechtstext. */
const WORDS: Record<LegalKind, { word: string; label: string }> = {
  agb: { word: 'AGB', label: 'Allgemeine Geschäftsbedingungen' },
  datenschutz: { word: 'Datenschutz', label: 'Datenschutzerklärung' },
  impressum: { word: 'Impressum', label: 'Impressum' },
};

/**
 * ►►► **Ein Rechtstext als A4-Dokument** – AGB, Datenschutz, Impressum: dieselbe Seite,
 * dieselbe Vorlage wie jeder Beleg, so wie der Server sie rendert
 * (`GET /public/legal/{kind}`). ◄◄◄
 *
 * AGB und Datenschutz sind Dokumente der Gesellschaft (die AGB die der Gesellschaft zum Land
 * des Besuchers); Name, Anschrift und Kontakt setzt das ERP ein. Das Papier ist in A4-Seiten geteilt – der Download ergibt genau
 * diese Seiten.
 */
export function LegalPage({ kind }: { kind: LegalKind }) {
  const [html, setHtml] = useState<string | null>(null);
  const [url, setUrl] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);
  const { word, label } = WORDS[kind];

  useEffect(() => {
    let dead = false;
    api.publicLegal(kind)
      .then((a) => { if (!dead) { setHtml(a.html ?? null); setUrl(a.url ?? null); } })
      .catch(() => { if (!dead) setFailed(true); });
    return () => { dead = true; };
  }, [kind]);

  return (
    <div className={`${css.page} ${html || url ? '' : css.loading}`}>
      <StageWord word={word} />
      {html && <Paper html={html} label={label} />}
      {/* Ein Rechtstext, der kein Text aus der Vorlage ist (ein PDF), steht, wie er ist. */}
      {!html && url && (
        <div className={css.wrap}>
          <iframe title={label} src={assetUrl(url)}
            style={{ width: '100%', aspectRatio: '210 / 297', border: '1px solid var(--border-1)', background: '#fff' }} />
        </div>
      )}
      {failed && (
        <div className={css.wrap}>
          <div className={css.note} role="alert">
            <h2 className={css.noteTitle}>{label} lässt sich gerade nicht laden.</h2>
            <p className={css.noteText}>Bitte laden Sie die Seite in einem Moment neu.</p>
          </div>
        </div>
      )}
    </div>
  );
}
