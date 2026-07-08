'use client';

import { useRef, useState } from 'react';
import { FileDown, Check, Bold, Italic, Heading2, List, ListOrdered, Table as TableIcon, Link2, Image as ImageIcon, Quote, Loader2 } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import type { Components } from 'react-markdown';
import type { CompanySettings, DocumentContent, SignoffView } from '@/types';
import { api, attachmentUrl } from '@/lib/api';

// Inexxio-Design-Tokens (Spiegel von styles/design-system/colors_and_type.css) – als
// Inline-Werte, damit die Web-Ansicht dem PDF-Render entspricht.
const RED = '#E51A14';
const INK = '#0A0A0B';
const BODY = '#3A3A3D';
const MUTED = '#6E6E73';
const HAIRLINE = '#E9E7E1';
const SAND = '#F4F3F0';
const DISPLAY = "'Inter Tight', 'Inter', 'Helvetica Neue', Arial, sans-serif";
// A4-Seitenbreite bei 96 dpi (210 mm) – die Vorschau ist auf dieses Blatt-Format begrenzt,
// damit man sofort sieht, was aufs echte Dokument passt (WYSIWYG mit dem PDF-Render).
const A4_WIDTH = 794;

function emptyContent(): DocumentContent {
  return { title: '', subtitle: null, body: '' };
}

function addressLines(company?: Partial<CompanySettings> | null): string[] {
  if (!company) return [];
  const street = [company.street, company.street_number].filter(Boolean).join(' ');
  const place = [company.zip, company.city].filter(Boolean).join(' ');
  const contact = [company.email, company.phone].filter(Boolean).join(' · ');
  const ids = [
    company.uid ? `UID ${company.uid}` : null,
    company.vat_number ? `MWST ${company.vat_number}` : null,
  ].filter(Boolean).join(' · ');
  return [company.company_name || 'Inexxio', street, place, company.country, contact, ids]
    .map((x) => (x ?? '').toString().trim()).filter(Boolean);
}

// ─── Markdown-Renderer (Inexxio-Design): fett, Listen, Tabellen, Bilder, Zitate, Code ──
const MD: Components = {
  h1: (p) => <h1 style={{ fontFamily: DISPLAY, fontWeight: 800, fontSize: 22, color: INK, letterSpacing: '-0.02em', margin: '22px 0 8px', lineHeight: 1.15 }} {...p} />,
  h2: (p) => <h2 style={{ fontFamily: DISPLAY, fontWeight: 700, fontSize: 18, color: INK, letterSpacing: '-0.01em', margin: '22px 0 7px' }} {...p} />,
  h3: (p) => <h3 style={{ fontFamily: DISPLAY, fontWeight: 700, fontSize: 15.5, color: INK, margin: '18px 0 5px' }} {...p} />,
  h4: (p) => <h4 style={{ fontFamily: DISPLAY, fontWeight: 700, fontSize: 14, color: INK, margin: '14px 0 4px' }} {...p} />,
  p: (p) => <p style={{ margin: '0 0 10px', lineHeight: 1.62 }} {...p} />,
  ul: (p) => <ul style={{ margin: '0 0 10px', paddingLeft: 22 }} {...p} />,
  ol: (p) => <ol style={{ margin: '0 0 10px', paddingLeft: 22 }} {...p} />,
  li: (p) => <li style={{ margin: '0 0 4px', lineHeight: 1.55 }} {...p} />,
  strong: (p) => <strong style={{ fontWeight: 700, color: INK }} {...p} />,
  em: (p) => <em style={{ fontStyle: 'italic' }} {...p} />,
  a: (p) => <a style={{ color: RED, textDecoration: 'none' }} target="_blank" rel="noreferrer" {...p} />,
  blockquote: (p) => <blockquote style={{ margin: '10px 0', padding: '4px 0 4px 16px', borderLeft: `3px solid ${HAIRLINE}`, color: MUTED }} {...p} />,
  hr: () => <hr style={{ border: 'none', borderTop: `1px solid ${HAIRLINE}`, margin: '18px 0' }} />,
  // eslint-disable-next-line @next/next/no-img-element, jsx-a11y/alt-text
  img: (p) => <img style={{ maxWidth: '100%', height: 'auto', margin: '10px 0', borderRadius: 6 }} {...p} />,
  code: (p) => <code style={{ fontFamily: 'monospace', fontSize: 12.5, background: SAND, padding: '1px 5px', borderRadius: 4 }} {...p} />,
  pre: (p) => <pre style={{ background: SAND, padding: '12px 14px', borderRadius: 8, whiteSpace: 'pre-wrap', overflowWrap: 'anywhere', margin: '10px 0' }} {...p} />,
  // table-layout:fixed + Wortumbruch → die Tabelle passt IMMER in die (A4-)Blattbreite,
  // egal wie viele/breite Spalten; kein horizontaler Überlauf mehr (WYSIWYG mit dem PDF).
  table: (p) => <table style={{ borderCollapse: 'collapse', width: '100%', tableLayout: 'fixed', fontSize: 13, margin: '12px 0' }} {...p} />,
  th: (p) => <th style={{ border: `1px solid ${HAIRLINE}`, padding: '6px 9px', textAlign: 'left', background: SAND, fontWeight: 700, color: INK, overflowWrap: 'anywhere', wordBreak: 'break-word' }} {...p} />,
  td: (p) => <td style={{ border: `1px solid ${HAIRLINE}`, padding: '6px 9px', textAlign: 'left', verticalAlign: 'top', overflowWrap: 'anywhere', wordBreak: 'break-word' }} {...p} />,
};

// ─── Ansicht (nah am PDF): weisses A4-Blatt im Inexxio-Design ─────────────────────
export function DocumentView({ content, objectNr, issuedAt, company, signoffs }: {
  content: DocumentContent | null | undefined;
  objectNr?: string | null;
  issuedAt?: string | null;
  company?: Partial<CompanySettings> | null;
  signoffs?: SignoffView[] | null;
}) {
  const c = content ?? emptyContent();
  const meta: string[] = [];
  if (objectNr) meta.push(`Nr. ${objectNr}`);
  if (issuedAt) meta.push(`Datum ${new Date(issuedAt).toLocaleDateString('de-CH')}`);
  const addr = addressLines(company);
  const companyName = company?.company_name || 'Inexxio';

  return (
    <div style={{ width: '100%', maxWidth: A4_WIDTH, marginLeft: 'auto', marginRight: 'auto', background: '#fff', border: `1px solid ${HAIRLINE}`, borderRadius: 12, padding: 'clamp(20px, 5vw, 48px)', boxShadow: '0 1px 3px rgba(16,14,12,0.05)', color: BODY, fontSize: 14, lineHeight: 1.62, overflowWrap: 'anywhere' }}>
      {(company || addr.length > 0) && (
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 24, paddingBottom: 12, borderBottom: `2px solid ${INK}`, marginBottom: 28, flexWrap: 'wrap' }}>
          {company?.logo_url
            // eslint-disable-next-line @next/next/no-img-element
            ? <img src={company.logo_url} alt="" style={{ height: 34, width: 'auto' }} />
            : <div style={{ fontFamily: DISPLAY, fontWeight: 800, fontSize: 20, letterSpacing: '-0.02em', color: INK }}>{companyName}<span style={{ color: RED }}>.</span></div>}
          <div style={{ fontSize: 11, color: MUTED, textAlign: 'right', lineHeight: 1.55 }}>
            {addr.map((ln, i) => <div key={i}>{ln}</div>)}
          </div>
        </div>
      )}
      <div style={{ fontSize: 11, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.18em', color: RED, marginBottom: 10 }}>Dokument</div>
      <h1 style={{ fontFamily: DISPLAY, fontWeight: 800, fontSize: 30, lineHeight: 1.05, letterSpacing: '-0.025em', color: INK, margin: 0 }}>{c.title || 'Ohne Titel'}</h1>
      {c.subtitle && <div style={{ fontSize: 15, color: BODY, marginTop: 8, lineHeight: 1.4 }}>{c.subtitle}</div>}
      <div style={{ height: 3, width: 46, background: RED, margin: '16px 0 0' }} />
      {meta.length > 0 && (
        <div style={{ marginTop: 16, paddingTop: 10, borderTop: `1px solid ${HAIRLINE}`, fontSize: 12, color: MUTED, display: 'flex', gap: 16, flexWrap: 'wrap', fontVariantNumeric: 'tabular-nums' }}>
          {meta.map((m, i) => <span key={i}>{m}</span>)}
        </div>
      )}
      <div style={{ marginTop: 28 }}>
        {c.body?.trim()
          ? <ReactMarkdown remarkPlugins={[remarkGfm]} components={MD}>{c.body}</ReactMarkdown>
          : <div style={{ color: MUTED, fontStyle: 'italic' }}>Dieses Dokument hat noch keinen Inhalt.</div>}
      </div>

      {signoffs && signoffs.length > 0 && (
        <div style={{ marginTop: 34, paddingTop: 16, borderTop: `2px solid ${INK}` }}>
          <div style={{ fontSize: 11, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.14em', color: RED, marginBottom: 14 }}>Freigaben</div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 24 }}>
            {signoffs.map((s) => (
              <div key={s.id} style={{ minWidth: 200, flex: '1 1 200px', maxWidth: 300 }}>
                <div style={{ display: 'flex', alignItems: 'flex-end', borderBottom: `1px solid ${INK}`, paddingBottom: 4, minHeight: 62 }}>
                  {s.status === 'signed' && s.signature_url
                    // eslint-disable-next-line @next/next/no-img-element
                    ? <img src={attachmentUrl(s.signature_url)} alt="Unterschrift" style={{ width: 168, aspectRatio: '600 / 200', objectFit: 'contain' }} />
                    : s.status === 'signed'
                      ? <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, color: '#15803D', fontWeight: 700, fontSize: 13 }}><Check size={15} /> Bestätigt</span>
                      : s.status === 'rejected'
                        ? <span style={{ color: RED, fontWeight: 700, fontSize: 13 }}>Abgelehnt</span>
                        : <span style={{ color: MUTED, fontStyle: 'italic', fontSize: 12 }}>ausstehend</span>}
                </div>
                <div style={{ marginTop: 6, fontSize: 12.5, fontWeight: 700, color: INK }}>{s.signer_name ?? `Objekt ${s.signer_object_id}`}</div>
                <div style={{ fontSize: 11, color: MUTED }}>
                  {s.action === 'sign' ? 'Unterschrift' : 'Bestätigung'}
                  {s.acted_at ? ` · ${new Date(s.acted_at).toLocaleDateString('de-CH')}` : ''}
                </div>
                {s.status === 'rejected' && s.reason && <div style={{ fontSize: 11, color: RED, marginTop: 2 }}>{s.reason}</div>}
              </div>
            ))}
          </div>
        </div>
      )}

      {(company || objectNr) && (
        <div style={{ marginTop: 30, paddingTop: 10, borderTop: `1px solid ${HAIRLINE}`, fontSize: 11, color: MUTED, fontVariantNumeric: 'tabular-nums' }}>
          {companyName} · Dok. {objectNr ?? '—'}
        </div>
      )}
    </div>
  );
}

// ─── Editor: Titel/Untertitel + Markdown-Body (Werkzeugleiste + Live-Vorschau) ────
export function DocumentEditor({ value, onChange, onPreviewPdf, company }: {
  value: DocumentContent | null | undefined;
  onChange: (c: DocumentContent) => void;
  onPreviewPdf?: () => void;
  company?: Partial<CompanySettings> | null;
}) {
  const c: DocumentContent = value ?? emptyContent();
  const set = (patch: Partial<DocumentContent>) => onChange({ ...c, ...patch });
  const taRef = useRef<HTMLTextAreaElement | null>(null);
  const [uploading, setUploading] = useState(false);

  // Markdown-Syntax an der Cursor-Position einfügen (Auswahl umschliessen).
  function wrap(before: string, after = before, placeholder = 'Text') {
    const ta = taRef.current;
    const body = c.body ?? '';
    if (!ta) { set({ body: body + before + placeholder + after }); return; }
    const s = ta.selectionStart, e = ta.selectionEnd;
    const sel = body.slice(s, e) || placeholder;
    const next = body.slice(0, s) + before + sel + after + body.slice(e);
    set({ body: next });
    requestAnimationFrame(() => { ta.focus(); ta.selectionStart = s + before.length; ta.selectionEnd = s + before.length + sel.length; });
  }
  function prefixLines(prefix: string) {
    const ta = taRef.current;
    const body = c.body ?? '';
    if (!ta) { set({ body: body + '\n' + prefix + 'Punkt' }); return; }
    const s = ta.selectionStart, e = ta.selectionEnd;
    const startLine = body.lastIndexOf('\n', s - 1) + 1;
    const block = body.slice(startLine, e) || 'Punkt';
    const numbered = prefix === '1. ';
    const withPrefix = block.split('\n').map((ln, i) => (numbered ? `${i + 1}. ` : prefix) + ln).join('\n');
    set({ body: body.slice(0, startLine) + withPrefix + body.slice(e) });
    requestAnimationFrame(() => ta.focus());
  }
  function insertBlock(text: string) {
    const ta = taRef.current;
    const body = c.body ?? '';
    const at = ta ? ta.selectionStart : body.length;
    const pad = (at > 0 && body[at - 1] !== '\n') ? '\n\n' : '';
    set({ body: body.slice(0, at) + pad + text + '\n' + body.slice(at) });
    requestAnimationFrame(() => ta?.focus());
  }
  async function insertImage(file: File) {
    setUploading(true);
    try {
      const { url } = await api.uploadAttachment(file);
      insertBlock(`![Bild](${url})`);
    } catch { /* ignore */ } finally { setUploading(false); }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      <input value={c.title ?? ''} onChange={(e) => set({ title: e.target.value })}
        placeholder="Titel des Dokuments (z. B. Rahmenvertrag Lieferant)"
        style={{ ...inp, fontFamily: DISPLAY, fontWeight: 700, fontSize: 18, color: INK }} />
      <input value={c.subtitle ?? ''} onChange={(e) => set({ subtitle: e.target.value || null })}
        placeholder="Untertitel (optional)" style={inp} />

      {/* Werkzeugleiste */}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, padding: 6, border: `1px solid ${HAIRLINE}`, borderRadius: 10, background: '#fff' }}>
        <Tool icon={Bold} tip="Fett" onClick={() => wrap('**')} />
        <Tool icon={Italic} tip="Kursiv" onClick={() => wrap('*')} />
        <Tool icon={Heading2} tip="Überschrift" onClick={() => prefixLines('## ')} />
        <Sep />
        <Tool icon={List} tip="Aufzählung" onClick={() => prefixLines('- ')} />
        <Tool icon={ListOrdered} tip="Nummerierte Liste" onClick={() => prefixLines('1. ')} />
        <Tool icon={Quote} tip="Zitat" onClick={() => prefixLines('> ')} />
        <Sep />
        <Tool icon={TableIcon} tip="Tabelle" onClick={() => insertBlock('| Spalte 1 | Spalte 2 |\n| --- | --- |\n| Wert | Wert |')} />
        <Tool icon={Link2} tip="Link" onClick={() => wrap('[', '](https://…)', 'Linktext')} />
        <label style={{ ...toolStyle, cursor: uploading ? 'default' : 'pointer' }} title="Bild einfügen">
          {uploading ? <Loader2 size={15} className="animate-spin" /> : <ImageIcon size={15} />}
          <input type="file" accept="image/*" hidden disabled={uploading}
            onChange={(e) => { const f = e.target.files?.[0]; if (f) insertImage(f); e.currentTarget.value = ''; }} />
        </label>
        {onPreviewPdf && (
          <>
            <div style={{ flex: 1 }} />
            <button type="button" onClick={onPreviewPdf} style={{ ...toolStyle, width: 'auto', padding: '0 12px', gap: 6, color: INK }}>
              <FileDown size={14} /> <span style={{ fontSize: 12.5, fontWeight: 600 }}>PDF-Vorschau</span>
            </button>
          </>
        )}
      </div>

      <textarea ref={taRef} value={c.body ?? ''} onChange={(e) => set({ body: e.target.value })}
        placeholder="Inhalt als Markdown – **fett**, Listen, Tabellen, Bilder. Die KI-Schreibhilfe füllt das ebenfalls."
        rows={16}
        style={{ ...inp, resize: 'vertical', lineHeight: 1.6, fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace', fontSize: 13.5 }} />

      <div>
        <div style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em', color: MUTED, marginBottom: 8 }}>Vorschau</div>
        <DocumentView content={c} company={company} />
      </div>
    </div>
  );
}

function Tool({ icon: Icon, tip, onClick }: { icon: React.ElementType; tip: string; onClick: () => void }) {
  return (
    <button type="button" onClick={onClick} title={tip} aria-label={tip} style={toolStyle}
      onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.background = SAND; }}
      onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.background = 'transparent'; }}>
      <Icon size={15} />
    </button>
  );
}
function Sep() { return <span style={{ width: 1, background: HAIRLINE, margin: '4px 3px' }} />; }

const toolStyle: React.CSSProperties = {
  width: 30, height: 30, borderRadius: 7, border: 'none', background: 'transparent', color: BODY,
  display: 'inline-flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer',
};
const inp: React.CSSProperties = {
  width: '100%', padding: '9px 12px', fontSize: 14, borderRadius: 8,
  border: `1px solid ${HAIRLINE}`, background: '#fff', outline: 'none', color: BODY,
  fontFamily: 'inherit',
};
