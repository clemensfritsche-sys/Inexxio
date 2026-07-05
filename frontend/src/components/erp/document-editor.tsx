'use client';

import { useState } from 'react';
import { Plus, Trash2, FileDown, GripVertical } from 'lucide-react';
import type { DocumentContent, DocumentSection } from '@/types';

// Inexxio-Design-Tokens (Spiegel von styles/design-system/colors_and_type.css) – als
// Inline-Werte, damit die Web-Ansicht PIXELGENAU dem PDF-Render entspricht.
const RED = '#E51A14';
const INK = '#0A0A0B';
const BODY = '#3A3A3D';
const MUTED = '#6E6E73';
const HAIRLINE = '#E9E7E1';
const DISPLAY = "'Inter Tight', 'Inter', 'Helvetica Neue', Arial, sans-serif";

function emptyContent(): DocumentContent {
  return { title: '', subtitle: null, sections: [] };
}

function paragraphs(body: string): string[] {
  return (body || '').replace(/\r\n/g, '\n').split('\n').map((b) => b.trim()).filter(Boolean);
}

// ─── Ansicht (identisch zum PDF): weisses A4-Blatt im Inexxio-Design ──────────────
export function DocumentView({ content, objectNr, issuedAt }: {
  content: DocumentContent | null | undefined;
  objectNr?: string | null;         // = Instanz-Objektnummer (die Dokumentennummer)
  issuedAt?: string | null;         // = Instanz-Freigabedatum
}) {
  const c = content ?? emptyContent();
  const sections = c.sections ?? [];
  const meta: string[] = [];
  if (objectNr) meta.push(`Nr. ${objectNr}`);
  if (issuedAt) meta.push(`Datum ${new Date(issuedAt).toLocaleDateString('de-CH')}`);

  return (
    <div style={{
      background: '#fff', border: `1px solid ${HAIRLINE}`, borderRadius: 12,
      padding: '40px 44px', boxShadow: '0 1px 3px rgba(16,14,12,0.05)',
      color: BODY, fontSize: 14, lineHeight: 1.62,
    }}>
      <div style={{ fontSize: 11, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.18em', color: RED, marginBottom: 10 }}>
        Dokument
      </div>
      <h1 style={{ fontFamily: DISPLAY, fontWeight: 800, fontSize: 30, lineHeight: 1.05, letterSpacing: '-0.025em', color: INK, margin: 0 }}>
        {c.title || 'Ohne Titel'}
      </h1>
      {c.subtitle && (
        <div style={{ fontSize: 15, color: BODY, marginTop: 8, lineHeight: 1.4 }}>{c.subtitle}</div>
      )}
      <div style={{ height: 3, width: 46, background: RED, margin: '16px 0 0' }} />
      {meta.length > 0 && (
        <div style={{ marginTop: 16, paddingTop: 10, borderTop: `1px solid ${HAIRLINE}`, fontSize: 12, color: MUTED, display: 'flex', gap: 16, flexWrap: 'wrap', fontVariantNumeric: 'tabular-nums' }}>
          {meta.map((m, i) => <span key={i}>{m}</span>)}
        </div>
      )}
      <div style={{ marginTop: 30, display: 'flex', flexDirection: 'column', gap: 20 }}>
        {sections.length === 0 ? (
          <div style={{ color: MUTED, fontStyle: 'italic' }}>Dieses Dokument hat noch keinen Inhalt.</div>
        ) : sections.map((s, i) => (
          <section key={i}>
            <h2 style={{ fontFamily: DISPLAY, fontWeight: 700, fontSize: 17, color: INK, letterSpacing: '-0.01em', margin: '0 0 6px' }}>
              {s.heading || '—'}
            </h2>
            {paragraphs(s.body).map((p, j) => (
              <p key={j} style={{ margin: '0 0 8px' }}>{p}</p>
            ))}
          </section>
        ))}
      </div>
    </div>
  );
}

// ─── Editor: Titel/Untertitel/Datum + Abschnitte (Live-Vorschau darunter) ─────────
export function DocumentEditor({ value, onChange, onPreviewPdf }: {
  value: DocumentContent | null | undefined;
  onChange: (c: DocumentContent) => void;
  onPreviewPdf?: () => void;
}) {
  const c: DocumentContent = value ?? emptyContent();
  const sections = c.sections ?? [];

  const set = (patch: Partial<DocumentContent>) => onChange({ ...c, ...patch });
  const setSection = (i: number, patch: Partial<DocumentSection>) =>
    set({ sections: sections.map((s, idx) => (idx === i ? { ...s, ...patch } : s)) });
  const addSection = () => set({ sections: [...sections, { heading: '', body: '' }] });
  const delSection = (i: number) => set({ sections: sections.filter((_, idx) => idx !== i) });

  // Abschnitte per Drag & Drop umsortieren (Griff links; Feedback über den Ziel-Index).
  const [drag, setDrag] = useState<number | null>(null);
  const [over, setOver] = useState<number | null>(null);
  const onDrop = (target: number) => {
    if (drag === null || drag === target) { setDrag(null); setOver(null); return; }
    const next = [...sections];
    const [moved] = next.splice(drag, 1);
    next.splice(target, 0, moved);
    set({ sections: next });
    setDrag(null); setOver(null);
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        <input value={c.title ?? ''} onChange={(e) => set({ title: e.target.value })}
          placeholder="Titel des Dokuments (z. B. Rahmenvertrag Lieferant)"
          style={{ ...inp, fontFamily: DISPLAY, fontWeight: 700, fontSize: 18, color: INK }} />
        <input value={c.subtitle ?? ''} onChange={(e) => set({ subtitle: e.target.value || null })}
          placeholder="Untertitel (optional)" style={inp} />
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        {sections.map((s, i) => {
          const isOver = over === i && drag !== null && drag !== i;
          return (
            <div key={i}
              onDragOver={(e) => { if (drag !== null) { e.preventDefault(); setOver(i); } }}
              onDrop={(e) => { e.preventDefault(); onDrop(i); }}
              style={{
                border: `1px solid ${isOver ? RED : HAIRLINE}`, borderRadius: 10, padding: 12,
                display: 'flex', flexDirection: 'column', gap: 8, background: '#fff',
                opacity: drag === i ? 0.4 : 1,
                boxShadow: isOver ? `0 0 0 2px ${RED}22` : 'none',
              }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span draggable
                  onDragStart={() => setDrag(i)}
                  onDragEnd={() => { setDrag(null); setOver(null); }}
                  title="Zum Umsortieren ziehen"
                  style={{ cursor: 'grab', color: '#cbd5e1', display: 'flex', alignItems: 'center', flexShrink: 0 }}>
                  <GripVertical size={16} />
                </span>
                <span style={{ fontSize: 11, fontWeight: 700, color: MUTED, minWidth: 18 }}>{i + 1}.</span>
                <input value={s.heading ?? ''} onChange={(e) => setSection(i, { heading: e.target.value })}
                  placeholder="Überschrift (z. B. §1 Geltungsbereich)"
                  style={{ ...inp, fontFamily: DISPLAY, fontWeight: 700, flex: 1 }} />
                <button type="button" onClick={() => delSection(i)} title="Abschnitt entfernen"
                  style={{ border: 'none', background: 'none', color: '#94a3b8', cursor: 'pointer', padding: 4, flexShrink: 0 }}><Trash2 size={15} /></button>
              </div>
              <textarea value={s.body ?? ''} onChange={(e) => setSection(i, { body: e.target.value })}
                placeholder="Text des Abschnitts. Absätze durch Zeilenumbrüche trennen."
                rows={4} style={{ ...inp, resize: 'vertical', lineHeight: 1.55 }} />
            </div>
          );
        })}
      </div>

      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        <button type="button" onClick={addSection} style={addBtn}>
          <Plus size={14} /> Abschnitt hinzufügen
        </button>
        {onPreviewPdf && (
          <button type="button" onClick={onPreviewPdf} style={pdfBtn}>
            <FileDown size={14} /> PDF-Vorschau
          </button>
        )}
      </div>

      <div>
        <div style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em', color: MUTED, marginBottom: 8 }}>
          Vorschau
        </div>
        <DocumentView content={c} />
      </div>
    </div>
  );
}

const inp: React.CSSProperties = {
  width: '100%', padding: '9px 12px', fontSize: 14, borderRadius: 8,
  border: `1px solid ${HAIRLINE}`, background: '#fff', outline: 'none', color: BODY,
  fontFamily: 'inherit',
};
const addBtn: React.CSSProperties = {
  display: 'inline-flex', alignItems: 'center', gap: 6, padding: '9px 14px',
  borderRadius: 9, border: `1px dashed #cbd5e1`, background: '#fff', color: RED,
  fontSize: 13, fontWeight: 600, cursor: 'pointer',
};
const pdfBtn: React.CSSProperties = {
  display: 'inline-flex', alignItems: 'center', gap: 6, padding: '9px 14px',
  borderRadius: 9, border: `1px solid ${HAIRLINE}`, background: '#fff', color: INK,
  fontSize: 13, fontWeight: 600, cursor: 'pointer',
};
