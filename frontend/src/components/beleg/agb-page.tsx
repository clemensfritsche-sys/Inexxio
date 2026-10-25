'use client';

import { useEffect, useState } from 'react';
import { api } from '@/lib/api';
import { Paper, StageWord } from './paper';
import css from './beleg.module.css';

/**
 * ►►► **Die AGB als A4-Dokument** – dieselbe Vorlage wie jeder Beleg, beide Teile
 * (geschäftlich · privat), so wie der Server sie rendert (`GET /public/agb`). ◄◄◄
 *
 * Der Text steht EINMAL: `backend/app/assets/agb/<gültig ab>.md`. Jedes Dokument hängt genau
 * diese AGB als letzte Seite an – hier stehen sie für sich.
 */
export function AgbPage() {
  const [html, setHtml] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let dead = false;
    api.publicAgb()
      .then((a) => { if (!dead) setHtml(a.html); })
      .catch(() => { if (!dead) setFailed(true); });
    return () => { dead = true; };
  }, []);

  return (
    <div className={`${css.page} ${html ? '' : css.loading}`}>
      <StageWord word="AGB" />
      {html && <Paper html={html} label="Allgemeine Geschäftsbedingungen" />}
      {failed && (
        <div className={css.wrap}>
          <div className={css.note} role="alert">
            <h2 className={css.noteTitle}>Die AGB lassen sich gerade nicht laden.</h2>
            <p className={css.noteText}>Bitte laden Sie die Seite in einem Moment neu.</p>
          </div>
        </div>
      )}
    </div>
  );
}
