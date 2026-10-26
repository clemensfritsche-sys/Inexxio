'use client';

import { useRef, useState } from 'react';
import { FileText, Loader2, RotateCcw, Upload } from 'lucide-react';
import { api, attachmentUrl } from '@/lib/api';

/** Ein hochgeladenes Dokument – seine Nummer (der Beleg verweist darauf), Link und Name. */
export type Uploaded = { id: number; url: string; name: string };

/**
 * **Ein Dokument hochladen – PDF oder Bild** (Ausfuhrnachweis).
 *
 * Die Veranlagungsverfügung kommt vom Zoll als PDF per Mail; im Büro gibt es dafür keine
 * Kamera. Darum ist der Ausfuhrnachweis ein **Upload** – und nur er: was ein Vorgang am
 * Stück belegt (Erfassungspunkt «Bild»), bleibt eine Aufnahme (`PhotoShot`), damit ein
 * Nachweis nie auf zwei Arten entstehen kann.
 *
 * **Ein Aufruf trägt alles** (`onChange` mit Nummer, Link, Name) – zwei Aufrufe nacheinander
 * schrieben auf denselben alten Formularstand, und die Nummer ging verloren.
 */
export function FileUpload({ value, onChange }: {
  value: { url: string; name: string } | null;
  onChange: (file: Uploaded | null) => void;
}) {
  const input = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function pick(file: File | undefined) {
    if (!file) return;
    setBusy(true); setErr(null);
    try {
      const { id, url } = await api.uploadAttachment(file);
      onChange({ id, url, name: file.name });
    } catch (e) {
      setErr(e instanceof Error ? e.message : 'Hochladen fehlgeschlagen');
    } finally {
      setBusy(false);
      if (input.current) input.current.value = '';
    }
  }

  return (
    <div className="flex flex-col gap-1">
      <input ref={input} type="file" accept="application/pdf,image/*" hidden
        onChange={(e) => void pick(e.target.files?.[0])} />
      {value ? (
        <div className="flex items-center gap-2" style={{ minWidth: 0 }}>
          <a href={attachmentUrl(value.url)} target="_blank" rel="noopener noreferrer"
            className="inline-flex items-center gap-1.5 text-[12.5px] truncate"
            style={{ color: 'var(--accent-ink)', maxWidth: 220 }}>
            <FileText size={14} style={{ flex: 'none' }} />
            <span className="truncate">{value.name || 'Dokument'}</span>
          </a>
          <button type="button" className="erp-actbtn" style={{ height: 30 }} disabled={busy}
            onClick={() => input.current?.click()} data-tip="Ein anderes Dokument wählen">
            <RotateCcw size={13} /> Ersetzen
          </button>
        </div>
      ) : (
        <button type="button" className="erp-actbtn erp-actbtn-primary" style={{ height: 36 }}
          disabled={busy} onClick={() => input.current?.click()}>
          {busy ? <Loader2 size={15} className="animate-spin" /> : <Upload size={15} />} PDF oder Bild hochladen
        </button>
      )}
      {err && <span className="text-[11.5px]" style={{ color: 'var(--danger)' }}>{err}</span>}
    </div>
  );
}
