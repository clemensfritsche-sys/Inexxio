'use client';

import { Check, X, Truck } from 'lucide-react';
import { PURCHASE_STATUS } from '@/lib/purchase-order';
import { Connector, kindColor } from '@/components/erp/process-steps';

export type PState = 'done' | 'active' | 'pending' | 'rejected';
export interface PNode { key: string; label: string; state: PState; hint?: string }
export interface Delivery { pct: number; label: string; overdue: boolean; oi: number }

/**
 * **Der Beschaffungs-Ablauf ist ein Prozess IM Prozess** (Notiz #194) – und wird darum
 * genau so gezeichnet wie der Auftrags-Ablauf: senkrechte Karten, durch einen Konnektor
 * verbunden, in der Farbe ihres Moduls. Dieselben Bausteine (`Connector`, `kindColor`),
 * nur eine Nummer kleiner, weil sie IN einer Modul-Karte stehen.
 *
 * Zustand ohne Wort, exakt wie im Auftrags-Fluss: erledigte und noch nicht erreichte Stufen
 * treten zurück (gedämpft), nur die aktive trägt ihre Farbe; das Symbol rechts sagt Haken
 * (erledigt) bzw. Kreuz (abgelehnt), der Hover nennt Wer/Wann.
 *
 * **Eine Tönung, nicht drei** (Notiz #329). Vorher lagen drei Flächen ineinander, von denen
 * zwei identisch waren: die Modul-Karte in Beschaffungs-Ton, darin die Stufen im *gleichen*
 * Ton (also unsichtbar abgegrenzt), darin ein weisser Block für die Eingaben. Jetzt trägt
 * die Tönung nur die Modul-Karte; die Stufen stehen als **weisse Karten** darauf, getrennt
 * durch Haarlinien, und die aktive hebt sich über ihren **Rand** ab (Modulfarbe) statt über
 * eine weitere Fläche. Ihr Arbeitsbereich hängt nahtlos an ihr – dieselbe weisse Fläche,
 * kein Farbwechsel mitten in der Eingabe. Struktur vor Fläche.
 *
 * Die Lieferfrist ist **keine Stufe**, sondern eine Eigenschaft der Stufe «Bestellt» – ein
 * schmaler Balken in deren Karte, dort wo er gilt.
 *
 * Start-/Endknoten gibt es hier bewusst nicht: die umgebende Modul-Karte IST der Rahmen.
 */
export function PurchaseProgress({ nodes, delivery, renderActive }: {
  nodes: PNode[]; delivery?: Delivery;
  /** Inhalt der AKTIVEN Stufe – die Eingaben stehen dort, wo sie gebraucht werden
   *  (Notiz #248), genau wie das Schritt-Panel in seiner Modul-Karte. */
  renderActive?: () => React.ReactNode;
}) {
  const kc = kindColor('purchase');
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
      {nodes.map((n, i) => {
        const muted = n.state === 'done' || n.state === 'pending';
        const cfg = PURCHASE_STATUS[n.key as keyof typeof PURCHASE_STATUS];
        const Icon = cfg?.icon;
        return (
          <div key={n.key} style={{ width: '100%', display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
            {i > 0 && <Connector />}
            <div title={n.hint} style={{
              width: '100%', display: 'flex', alignItems: 'center', gap: 11,
              padding: '10px 13px',
              borderRadius: n.state === 'active' && renderActive ? 'var(--r-md) var(--r-md) 0 0' : 'var(--r-md)',
              // Weisse Karte auf der getönten Modul-Fläche; die aktive Stufe bekommt den
              // Modul-Rand (und trägt damit die Farbe an der Kante, nicht in der Fläche).
              border: `1px solid ${n.state === 'active' ? kc.fg : 'var(--border-1)'}`,
              background: '#fff',
              opacity: muted ? 0.55 : 1, cursor: n.hint ? 'help' : 'default',
            }}>
              <span style={{
                width: 30, height: 30, borderRadius: 'var(--r-sm)', flexShrink: 0,
                background: n.state === 'active' ? kc.bg : 'var(--bg-2)',
                color: n.state === 'rejected' ? 'var(--danger)' : kc.fg,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
              }}>
                {Icon ? <Icon size={15} /> : <span style={{ font: '700 12px var(--font-body)' }}>{i + 1}</span>}
              </span>

              <div style={{ minWidth: 0, flex: 1 }}>
                <span style={{ font: `${n.state === 'active' ? 800 : 600} 13.5px var(--font-display)`, color: 'var(--fg-1)' }}>
                  {n.label}
                </span>
                {/* Wer/Wann steht im **Hover** der Stufe (`title`), nicht in der Fläche
                    (Notiz #276) – wie beim Modul im Auftrags-Fluss. */}

                {/* Lieferfrist: Eigenschaft der Stufe «Bestellt», kein eigener Knoten. */}
                {delivery && i === delivery.oi && (
                  // Der Lastwagen steht auf dem echten Fortschritt und wippt leise; die
                  // gestrichelte Strasse läuft ihm entgegen (Notiz #251). Nichts daran
                  // täuscht Fortschritt vor – die Position IST die Restzeit.
                  <div style={{ marginTop: 9, display: 'flex', alignItems: 'center', gap: 10 }}>
                    <span style={{ position: 'relative', flex: 1, maxWidth: 210, height: 18 }}>
                      <span className="ix-road" style={{
                        position: 'absolute', left: 0, right: 0, top: '50%', height: 2, borderRadius: 2,
                        transform: 'translateY(-50%)',
                        background: `repeating-linear-gradient(90deg, var(--border-2) 0 6px, transparent 6px 12px)`,
                      }} />
                      <span style={{
                        position: 'absolute', left: 0, top: '50%', height: 2, borderRadius: 2,
                        transform: 'translateY(-50%)', width: `${delivery.pct}%`,
                        background: delivery.overdue ? 'var(--danger)' : 'var(--warning)',
                      }} />
                      <span className="ix-truck" style={{
                        position: 'absolute', left: `${delivery.pct}%`, top: '50%',
                        color: delivery.overdue ? 'var(--danger)' : 'var(--warning)', lineHeight: 0,
                      }}>
                        <Truck size={15} />
                      </span>
                    </span>
                    <span style={{ font: '600 11.5px var(--font-body)', color: delivery.overdue ? 'var(--danger)' : 'var(--warning)', whiteSpace: 'nowrap' }}>
                      {delivery.label}
                    </span>
                  </div>
                )}
              </div>

              {n.state === 'done' && <Check size={17} style={{ color: 'var(--success)', flexShrink: 0 }} />}
              {n.state === 'rejected' && <X size={17} style={{ color: 'var(--danger)', flexShrink: 0 }} />}
            </div>
            {/* Die aktive Stufe trägt ihre Eingaben und ihre Aktion – wie eine Modul-Karte
                im Auftrags-Fluss ihr Panel trägt (#248). */}
            {n.state === 'active' && renderActive && (
              // Der Arbeitsbereich hängt **nahtlos** an seiner Stufe: dieselbe weisse Fläche,
              // derselbe Rand, nur durch eine Haarlinie getrennt (Notiz #329). Vorher war er
              // eine weitere Fläche in einer anderen Farbe als die Karte darüber.
              <div style={{ width: '100%', border: `1px solid ${kc.fg}`, borderTop: `1px solid var(--border-1)`,
                borderRadius: '0 0 var(--r-md) var(--r-md)', background: '#fff', padding: '13px 13px 15px',
                marginTop: -1, display: 'flex', flexDirection: 'column', gap: 12 }}>
                {renderActive()}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
