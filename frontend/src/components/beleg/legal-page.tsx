'use client';

import { useEffect, useState } from 'react';
import { api } from '@/lib/api';
import { Paper, StageWord } from './paper';
import css from './beleg.module.css';

export type LegalKind = 'agb' | 'datenschutz' | 'impressum';

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
 * Der Text steht EINMAL: `backend/app/assets/legal/<art>/<gültig ab>.md`; Name, Anschrift und
 * Kontakt kommen aus dem ERP. Das Papier ist in A4-Seiten geteilt – der Download ergibt genau
 * diese Seiten.
 */
export function LegalPage({ kind }: { kind: LegalKind }) {
  const [html, setHtml] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);
  const { word, label } = WORDS[kind];

  useEffect(() => {
    let dead = false;
    api.publicLegal(kind)
      .then((a) => { if (!dead) setHtml(a.html); })
      .catch(() => { if (!dead) setFailed(true); });
    return () => { dead = true; };
  }, [kind]);

  return (
    <div className={`${css.page} ${html ? '' : css.loading}`}>
      <StageWord word={word} />
      {html && <Paper html={html} label={label} />}
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
