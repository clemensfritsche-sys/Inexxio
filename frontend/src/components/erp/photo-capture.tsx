'use client';

import { useCallback, useRef, useState } from 'react';
import { Camera, CameraOff, Loader2, RotateCcw, Zap } from 'lucide-react';
import { attachmentUrl } from '@/lib/api';
import { DraftSheet } from '@/components/erp/document-draft';
import { useCamera } from '@/components/scan/use-camera';

/**
 * **Ein Bild, aufgenommen — nicht hochgeladen** (Testnotizen #718/#720) – **und ein Dokument**:
 * die Aufnahme öffnet denselben Entwurf wie jede Datei (eine Ablage), das Stück als Referenz mit
 * Schloss (Feld `capture.photo`); erst die Freigabe macht sie zum Wert des Punkts.
 *
 * **Kein Hochladen**: eine Datei aus der Galerie belegt nichts über *diesen* Vorgang, und
 * ein Nachweis, der auf beide Arten entstehen kann, ist hinterher keiner.
 *
 * **Genau eine Aufnahme je Einzelinstanz.** Nicht mehr, auch nicht optional: bei mehreren
 * bliebe offen, welche die gemeinte ist. Neu aufnehmen geht (das verwirft die alte) –
 * *sammeln* geht nicht.
 *
 * **Und es ist dieselbe Kamera wie der Scanner** (`useCamera`): derselbe Stream, dieselbe
 * Linsenwahl, dieselbe Taschenlampe, dasselbe Aufräumen. Was hier fehlt, ist der
 * Decoder – dieses Bauteil sucht keine Codes, es hält fest, was zu sehen ist.
 */
export function PhotoShot({ value, unit, label, onChange, disabled = false }: {
  /** Die URL der Aufnahme – oder `null`, solange keine gemacht wurde. */
  value: string | null;
  /** Das Stück (`<Instanznr>-<Suffix>`), dem das Bild gilt – seine Referenz im Entwurf. */
  unit: string;
  /** Der Erfassungspunkt – die Art des Dokuments. */
  label: string;
  onChange: (url: string | null) => void;
  disabled?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const [shot, setShot] = useState<File | null>(null);
  const instance = Number(unit.split('-')[0]);

  if (value) {
    return (
      <div className="flex items-center gap-2">
        <a href={attachmentUrl(value)} target="_blank" rel="noopener noreferrer"
          className="rounded-ds-md overflow-hidden flex-none"
          style={{ width: 76, height: 76, border: '1px solid var(--border-1)' }}>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={attachmentUrl(value)} alt="Aufnahme"
            style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
        </a>
        {!disabled && (
          <button type="button" className="erp-actbtn" style={{ height: 30 }}
            onClick={() => { onChange(null); setOpen(true); }}
            data-tip="Verwirft die Aufnahme und öffnet die Kamera erneut">
            <RotateCcw size={13} /> Neu aufnehmen
          </button>
        )}
      </div>
    );
  }

  if (shot) {
    return (
      <DraftSheet onCancel={() => setShot(null)}
        seed={{ files: [shot], source: 'capture', art: label, name: unit,
                target: { object_id: instance, part: `unit:${unit}`, field: 'capture.photo', extra: {},
                          label: unit, lock: label } }}
        onFiled={(doc) => { setShot(null); setOpen(false); onChange(doc.file_url ?? null); }} />
    );
  }

  if (!open) {
    return (
      <div className="flex flex-col gap-1">
        <button type="button" className="erp-actbtn erp-actbtn-primary"
          style={{ height: 36 }} disabled={disabled}
          onClick={() => setOpen(true)}>
          <Camera size={15} /> Aufnehmen
        </button>
      </div>
    );
  }

  return (
    <Viewfinder
      busy={false}
      onCancel={() => setOpen(false)}
      onShot={(blob) => setShot(new File([blob], `${unit}.jpg`, { type: 'image/jpeg' }))}
    />
  );
}

/**
 * Der Sucher — **dieselbe Bildsprache wie der Scanner**: die Fläche IST das Kamerabild,
 * die Bedienelemente liegen als milchige Chips darin. Nur der Zielrahmen fehlt: hier
 * wird nichts gesucht, hier wird festgehalten, was da ist.
 */
function Viewfinder({ busy, onShot, onCancel }: {
  busy: boolean;
  onShot: (blob: Blob) => void;
  onCancel: () => void;
}) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const { videoRef, state, torch, setTorch } = useCamera(true);
  const live = state === 'starting' || state === 'scanning';

  /** Ein Einzelbild aus dem laufenden Strom – in seiner echten Auflösung. */
  const shoot = useCallback(() => {
    const video = videoRef.current;
    const canvas = canvasRef.current;
    if (!video || !canvas || !video.videoWidth) return;
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    canvas.getContext('2d')?.drawImage(video, 0, 0, canvas.width, canvas.height);
    canvas.toBlob((blob) => { if (blob) onShot(blob); }, 'image/jpeg', 0.9);
  }, [onShot, videoRef]);

  return (
    <div className="rounded-ds-lg overflow-hidden relative"
      style={{ background: '#0b0b0c', aspectRatio: '4 / 3' }}>
      {live ? (
        // eslint-disable-next-line jsx-a11y/media-has-caption
        <video ref={videoRef} muted playsInline autoPlay
          style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
      ) : (
        <div className="flex flex-col items-center justify-center h-full"
          style={{ color: 'rgba(255,255,255,.72)' }}>
          <CameraOff size={26} strokeWidth={1.5} />
          <span className="text-[11.5px] mt-2 px-4 text-center">
            {state === 'denied'
              ? 'Kein Kamerazugriff – ohne Kamera kann hier kein Bild erfasst werden.'
              : 'Dieses Gerät hat keine nutzbare Kamera.'}
          </span>
        </div>
      )}

      <canvas ref={canvasRef} style={{ display: 'none' }} />

      <div className="absolute inset-x-0 bottom-0 flex items-center justify-center gap-2 p-2.5">
        <CameraChip onClick={onCancel} label="Abbrechen">Abbrechen</CameraChip>
        <button type="button" onClick={shoot} disabled={!live || busy}
          aria-label="Auslösen"
          className="flex items-center justify-center rounded-full disabled:opacity-45"
          style={{ width: 52, height: 52, background: '#fff', color: '#0b0b0c',
                   border: '3px solid rgba(255,255,255,.55)' }}>
          {busy ? <Loader2 size={20} className="animate-spin" /> : <Camera size={20} />}
        </button>
        {torch !== null && (
          <CameraChip onClick={() => void setTorch(!torch)} label="Licht">
            <Zap size={13} />
          </CameraChip>
        )}
      </div>
    </div>
  );
}

/** Ein milchiger Chip **im Bild** – dieselbe Form wie im Scan-Dialog. */
function CameraChip({ onClick, label, children }: {
  onClick: () => void; label: string; children: React.ReactNode;
}) {
  return (
    <button type="button" onClick={onClick} aria-label={label}
      className="flex items-center gap-1.5 rounded-full px-3 text-[12px]"
      style={{ height: 32, background: 'rgba(255,255,255,.18)', color: '#fff',
               backdropFilter: 'blur(6px)' }}>
      {children}
    </button>
  );
}
