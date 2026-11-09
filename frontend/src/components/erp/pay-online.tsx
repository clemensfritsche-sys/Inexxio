'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { Check, Loader2, ShieldCheck } from 'lucide-react';
import type { Stripe, StripeElements, StripePaymentElement } from '@stripe/stripe-js';
import type { PaymentSetup } from '@/types';
import { errorText, useAction } from '@/lib/use-action';

/**
 * **Bezahlen — in UNSERER Karte, nicht auf einer fremden Seite** (§9.13).
 *
 * Vom Dienst kommen nur die **Eingabefelder** (Payment Element im iframe – keine
 * Kartennummer berührt unseren Server) und 3-D Secure; das Aussehen aus unseren Tokens.
 * **Was wir wissen, fragen wir nicht**: vorhandene Angaben aus `PaymentSetup.billing` gehen
 * fest mit (`fields: 'never'`). **Gebucht wird hier NICHTS** – nur vom Webhook
 * (`voucher.record_payment`); die Karte sagt «ausgeführt».
 */
export function PayOnline({ orderObjectId, stepId, prepare, label, onDone, onClose }: {
  orderObjectId: number;
  stepId: number;
  /** **Welches Modul bezahlt wird, sagt der Aufrufer** – eine stabile Referenz
   *  (`api.prepareVoucherPayment`); eine Pfeilfunktion liesse die Vorbereitung endlos laufen. */
  prepare: (objectId: number, stepId: number) => Promise<PaymentSetup>;
  /** Das Wort des Servers («Jetzt bezahlen») – die Karte hält keine eigene Konstante. */
  label: string;
  /** Der Auftrag soll neu geladen werden – die Zahlung kommt über den Webhook. */
  onDone: () => void;
  onClose: () => void;
}) {
  const host = useRef<HTMLDivElement | null>(null);
  const [setup, setSetup] = useState<PaymentSetup | null>(null);
  const [ready, setReady] = useState<{ stripe: Stripe; elements: StripeElements } | null>(null);
  const [done, setDone] = useState(false);
  const { busy, error, setError, run } = useAction();

  // Die Vorbereitung erzeugt beim Dienst eine Absicht und ändert an unserem Vorgang nichts.
  useEffect(() => {
    let dead = false;
    prepare(orderObjectId, stepId)
      .then((s) => { if (!dead) setSetup(s); })
      .catch((e) => { if (!dead) setError(errorText(e)); });
    return () => { dead = true; };
  }, [prepare, orderObjectId, stepId, setError]);

  // Das SDK kommt erst auf Klick (`await import`).
  useEffect(() => {
    if (!setup || !host.current) return;
    let dead = false;
    let el: StripePaymentElement | null = null;
    const mount = host.current;
    (async () => {
      try {
        const { loadStripe } = await import('@stripe/stripe-js');
        const stripe = await loadStripe(setup.publishable_key);
        if (dead || !stripe) {
          if (!dead) setError('Der Zahlungsdienst liess sich nicht laden.');
          return;
        }
        const elements = stripe.elements({
          clientSecret: setup.client_secret,
          appearance: appearance(),
        });
        const known = setup.billing;
        el = elements.create('payment', {
          // ►►► **Was wir wissen, fragt das Element nicht.** ◄◄◄ `never` heisst «wird
          // mitgeliefert» – und dann **muss** es beim Bestätigen auch mitkommen (unten).
          fields: {
            billingDetails: {
              name: known?.name ? 'never' : 'auto',
              email: known?.email ? 'never' : 'auto',
              address: known?.address ? 'never' : 'auto',
            },
          },
        });
        el.mount(mount);
        if (!dead) setReady({ stripe, elements });
      } catch (e) {
        if (!dead) setError(errorText(e));
      }
    })();
    return () => { dead = true; el?.destroy(); };
  }, [setup, setError]);

  const pay = useCallback(() => ready && setup && run(async () => {
    const known = setup.billing;
    const { error: err } = await ready.stripe.confirmPayment({
      elements: ready.elements,
      confirmParams: {
        // Rückkehr-Adresse für Zahlungsarten, die den Browser verlassen (`if_required`).
        return_url: window.location.href,
        payment_method_data: {
          billing_details: {
            ...(known?.name ? { name: known.name } : {}),
            ...(known?.email ? { email: known.email } : {}),
            ...(known?.address ? {
              address: {
                line1: known.address.line1,
                line2: known.address.line2 ?? null,
                postal_code: known.address.postal_code,
                city: known.address.city,
                country: known.address.country,
                state: null,
              },
            } : {}),
          },
        },
      },
      redirect: 'if_required',
    });
    // Die Meldung des Dienstes nennt den Grund – kein eigener Satz.
    if (err) throw new Error(err.message ?? 'Die Zahlung ist nicht zustande gekommen.');
    setDone(true);
    onDone();
  }), [ready, setup, onDone, run]);

  if (done) {
    return (
      <div className="flex items-center gap-2 text-[12.5px]"
        style={{
          padding: 10, borderRadius: 8, border: '1px solid var(--border-1)',
          color: 'var(--fg-2)',
        }}>
        <Check size={14} style={{ color: 'var(--success)', flex: 'none' }} />
        {/* «Ausgeführt», nicht «gebucht» – die Zeile entsteht mit der Meldung des Dienstes. */}
        Zahlung ausgeführt. Sie erscheint als Zeile, sobald der Zahlungsdienst sie
        bestätigt hat.
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-2" style={{
      padding: 10, borderRadius: 8, border: '1px solid var(--border-1)',
    }}>
      <div className="flex items-center gap-2 flex-wrap">
        <ShieldCheck size={13} style={{ color: 'var(--fg-4)', flex: 'none' }} />
        <span className="text-[12.5px]" style={{ color: 'var(--fg-2)' }}>{label}</span>
        {setup && (
          <span className="ix-tnum text-[12.5px] font-semibold" style={{ color: 'var(--fg-1)' }}>
            {setup.amount} {setup.currency}
          </span>
        )}
      </div>

      {/* Die Eingabefelder des Dienstes – in unserer Fläche, in unseren Farben. */}
      <div ref={host} style={{ minHeight: setup ? 40 : 0 }} />

      {!setup && !error && (
        <span className="flex items-center gap-1.5 text-[12.5px]" style={{ color: 'var(--fg-4)' }}>
          <Loader2 size={13} className="animate-spin" /> Zahlung wird vorbereitet …
        </span>
      )}
      {error && (
        <span className="text-[12.5px]" style={{ color: 'var(--danger)' }}>{error}</span>
      )}

      <div className="flex items-center gap-2">
        <button type="button" className="erp-actbtn erp-actbtn-primary"
          style={{ height: 30 }} disabled={!ready || busy} onClick={pay}>
          {busy ? <Loader2 size={13} className="animate-spin" /> : <Check size={13} />}
          {' '}{label}
        </button>
        <button type="button" className="erp-actbtn erp-actbtn-neutral"
          style={{ height: 30 }} disabled={busy} onClick={onClose}>Abbrechen</button>
      </div>
    </div>
  );
}

/** **Das Aussehen kommt aus unseren Tokens** (`getComputedStyle`) – die Felder des Dienstes
 *  sehen aus wie `inputCls`. */
function appearance() {
  const css = getComputedStyle(document.documentElement);
  // Ohne Rückfall-Farbe: die Tokens sind immer definiert.
  const v = (name: string) => css.getPropertyValue(name).trim();
  return {
    theme: 'stripe' as const,
    // Die Beschriftung steht über dem Feld – wie `controls.Label`.
    labels: 'above' as const,
    // Dichte Felder.
    inputs: 'condensed' as const,
    variables: {
      colorPrimary: v('--accent'),
      colorBackground: v('--bg-1'),
      colorText: v('--fg-1'),
      colorDanger: v('--danger'),
      fontFamily: v('--font-body'),
      // Wie `inputCls` (`rounded-ds-md` = 8 px).
      borderRadius: '8px',
      // Schrift und Raster wie `inputCls` (`text-sm` = 14 px, 4-px-Schritte).
      fontSizeBase: '14px',
      spacingUnit: '4px',
    },
    rules: {
      // Dieselbe Polsterung und dieselbe Zeilenhöhe wie `inputCls` (`py-2 px-3`,
      // `text-sm` = 14/20 px → 20 ÷ 14 = 1.43).
      '.Input': { padding: '8px 12px', lineHeight: '1.43' },
      // Buchstabengleich `controls.Label` – 11 px, 600, Versalien, .05em, `--fg-4`.
      '.Label': {
        fontSize: '11px', fontWeight: '600', textTransform: 'uppercase',
        letterSpacing: '.05em', color: v('--fg-4'), marginBottom: '4px',
      },
    },
  };
}
