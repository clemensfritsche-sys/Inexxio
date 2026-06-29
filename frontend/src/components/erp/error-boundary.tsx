'use client';

import { Component, type ErrorInfo, type ReactNode } from 'react';
import { AlertTriangle, RotateCcw } from 'lucide-react';

/**
 * Fängt Render-Fehler (inkl. «Maximum update depth exceeded») in einem Teilbaum ab,
 * damit ein einzelner fehlerhafter Datensatz NICHT die ganze ERP-Oberfläche einfriert.
 * Zeigt eine freundliche, erholbare Meldung statt eines weissen Bildschirms; ``resetKey``
 * (z. B. die gewählte Objektnummer) setzt den Fehlerzustand beim Navigieren zurück.
 */
export class ErrorBoundary extends Component<
  { children: ReactNode; resetKey?: string | number | null; onReset?: () => void },
  { error: Error | null }
> {
  state: { error: Error | null } = { error: null };

  static getDerivedStateFromError(error: Error) {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    // Komponentenstapel in die Konsole – damit sich der Auslöser (welcher Datensatz/welche
    // Komponente) im Fehlerfall punktgenau bestimmen lässt, ohne die ganze App zu sperren.
    console.error('[ERP ErrorBoundary]', error, info.componentStack);
  }

  componentDidUpdate(prev: { resetKey?: string | number | null }) {
    // Beim Wechsel des Schlüssels (andere Auswahl) den Fehler zurücksetzen → erneut versuchen.
    if (this.state.error && prev.resetKey !== this.props.resetKey) {
      this.setState({ error: null });
    }
  }

  render() {
    if (this.state.error) {
      return (
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 12, padding: 24, textAlign: 'center' }}>
          <AlertTriangle size={40} strokeWidth={1.5} style={{ color: '#dc2626' }} />
          <div style={{ fontSize: 15, fontWeight: 700, color: '#0f172a' }}>Anzeige konnte nicht geladen werden</div>
          <div style={{ fontSize: 13, color: '#64748b', maxWidth: 340 }}>
            Bei diesem Datensatz ist ein Anzeige-Fehler aufgetreten. Du kannst zurück zur Liste und einen
            anderen Datensatz öffnen – deine Daten sind nicht verloren.
          </div>
          <code style={{ fontSize: 11, color: '#94a3b8', maxWidth: 360, wordBreak: 'break-word' }}>
            {this.state.error.message}
          </code>
          <button onClick={() => { this.setState({ error: null }); this.props.onReset?.(); }}
            style={{ display: 'inline-flex', alignItems: 'center', gap: 6, padding: '8px 14px', borderRadius: 8, border: '1px solid #e2e8f0', background: '#fff', color: '#2563eb', fontSize: 13, fontWeight: 600, cursor: 'pointer' }}>
            <RotateCcw size={14} /> Zurück
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
