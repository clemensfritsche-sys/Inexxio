'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { Check, Loader2, ShieldCheck } from 'lucide-react';
import type { Stripe, StripeElements, StripePaymentElement } from '@stripe/stripe-js';
import { api } from '@/lib/api';
import type { PaymentSetup } from '@/types';

/**
 * ►►► **Bezahlen — in UNSERER Karte, nicht auf einer fremden Seite.** ◄◄◄
 *
 * Vorher war es ein **Zahllink**: der Kunde verliess das ERP und stand auf einer Seite
 * mit fremdem Namen, fremder Schrift und fremder Adresszeile. Hier bleibt er, wo er ist –
 * die Fläche, die Wörter, der Knopf und die Rückmeldung gehören uns.
 *
 * ## Was trotzdem vom Dienst kommt — und warum genau das
 *
 * Die **Eingabefelder** selbst (ein *Payment Element* in einem iframe). Das ist kein
 * Kompromiss, sondern ihr Sinn: so berührt **keine Kartennummer je unseren Server**, und
 * das ist der Unterschied zwischen «wir nehmen Karten an» und «wir sind PCI-pflichtig».
 * Die **3-D-Secure-Abfrage** gehört der Bank; sie liesse sich gar nicht nachbauen.
 *
 * Damit man den Unterschied nicht sieht, kommt das **Aussehen aus unseren Tokens**
 * (`appearance` unten liest die CSS-Variablen des Hauses aus) – nicht aus einer geratenen
 * Farbliste, die beim nächsten Design-Wechsel stehen bleibt.
 *
 * ## Was wir wissen, fragen wir nicht
 *
 * Name, E-Mail und Rechnungsadresse stehen im ERP und reisen mit der Vorbereitung mit
 * (`PaymentSetup.billing`). Was davon dasteht, wird dem Element als **feste Angabe**
 * übergeben (`fields: 'never'` + `payment_method_data`) – der Zahlende tippt es nicht ein
 * zweites Mal ab. Und **nur, was wirklich dasteht**: fehlt die Adresse, fragt das Element
 * sie; eine halbe Vorbelegung wäre schlechter als die Frage.
 *
 * ## Gebucht wird hier NICHTS
 *
 * Der Browser ist keine Quelle: wer ihn nach der Zahlung schliesst, darf keine Buchung
 * verschlucken. Die Zeile entsteht, wenn der Dienst sie meldet (Webhook →
 * `deal.record_payment`, idempotent über die Referenz). Diese Karte sagt darum «ausgeführt»
 * und nicht «gebucht» – und lädt den Auftrag nach, damit die Zeile erscheint, sobald sie
 * da ist.
 */
export function PayOnline({ orderObjectId, stepId, label, onDone, onClose }: {
  orderObjectId: number;
  stepId: number;
  /** Das Wort des Servers («Jetzt bezahlen») – die Karte hält keine eigene Konstante. */
  label: string;
  /** Der Auftrag soll neu geladen werden – die Zahlung kommt über den Webhook. */
  onDone: () => void;
  onClose: () => void;
}) {
  const host = useRef<HTMLDivElement | null>(null);
  const [setup, setSetup] = useState<PaymentSetup | null>(null);
  const [ready, setReady] = useState<{ stripe: Stripe; elements: StripeElements } | null>(null);
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // **Die Vorbereitung ist ein Aufruf, kein Zustand.** Sie erzeugt beim Dienst eine
  // Absicht über den offenen Betrag und ändert an unserem Vorgang keine Zeile.
  useEffect(() => {
    let dead = false;
    api.preparePayment(orderObjectId, stepId)
      .then((s) => { if (!dead) setSetup(s); })
      .catch((e) => { if (!dead) setError(e instanceof Error ? e.message : String(e)); });
    return () => { dead = true; };
  }, [orderObjectId, stepId]);

  // **Das SDK kommt erst auf Klick** (`await import`) – dieselbe Regel wie beim Decoder
  // des Scanners: was niemand öffnet, kostet niemanden etwas.
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
        if (!dead) setError(e instanceof Error ? e.message : String(e));
      }
    })();
    return () => { dead = true; el?.destroy(); };
  }, [setup]);

  const pay = useCallback(async () => {
    if (!ready || !setup) return;
    setBusy(true); setError(null);
    const known = setup.billing;
    const { error: err } = await ready.stripe.confirmPayment({
      elements: ready.elements,
      confirmParams: {
        // **Die Rückkehr-Adresse braucht jede Zahlungsart, die den Browser verlässt**
        // (TWINT, Banküberweisungen im Ausland). Eine Karte bleibt hier –
        // `redirect: 'if_required'` schickt nur weg, wen der Weg wirklich wegführt.
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
    setBusy(false);
    // **Die Meldung des Dienstes ist die ehrlichere** – sie nennt die Karte, die Bank
    // oder das fehlende Feld; ein eigener Satz daneben wäre eine Vermutung.
    if (err) { setError(err.message ?? 'Die Zahlung ist nicht zustande gekommen.'); return; }
    setDone(true);
    onDone();
  }, [ready, setup, onDone]);

  if (done) {
    return (
      <div className="flex items-center gap-2 text-[12.5px]"
        style={{
          padding: 10, borderRadius: 8, border: '1px solid var(--border-1)',
          color: 'var(--fg-2)',
        }}>
        <Check size={14} style={{ color: 'var(--success)', flex: 'none' }} />
        {/* **«Ausgeführt», nicht «gebucht».** Die Zeile entsteht, wenn der Dienst sie
            meldet – ein Satz, der eine Buchung behauptet, die noch nicht dasteht, ist
            beim nächsten Blick eine Lüge. */}
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

/**
 * **Das Aussehen kommt aus unseren Tokens, nicht aus einer geratenen Farbliste.**
 *
 * Gelesen wird, was im Blatt wirklich steht (`getComputedStyle`) – damit die Felder des
 * Dienstes dieselbe Fläche, dieselbe Schrift und denselben Rahmen tragen wie das Feld
 * daneben, und zwar auch nach dem nächsten Design-Wechsel. Feste Farben hier wären die
 * zweite Farbsprache, die das Haus gerade abgeschafft hat.
 */
function appearance() {
  const css = getComputedStyle(document.documentElement);
  const v = (name: string, fallback: string) => css.getPropertyValue(name).trim() || fallback;
  return {
    theme: 'stripe' as const,
    variables: {
      colorPrimary: v('--accent', '#2C6E8F'),
      colorBackground: v('--bg-1', '#ffffff'),
      colorText: v('--fg-1', '#181411'),
      colorDanger: v('--danger', '#b3261e'),
      fontFamily: v('--font-body', 'Inter, system-ui, sans-serif'),
      borderRadius: '8px',
      spacingUnit: '4px',
    },
  };
}
