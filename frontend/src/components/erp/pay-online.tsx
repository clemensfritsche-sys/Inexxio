'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { Check, Loader2, ShieldCheck } from 'lucide-react';
import type { Stripe, StripeElements, StripePaymentElement } from '@stripe/stripe-js';
import type { PaymentSetup } from '@/types';

/**
 * **Bezahlen — in UNSERER Karte, nicht auf einer fremden Seite** (§9.13): kein Zahllink;
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
 * `voucher.record_payment`, idempotent über die Referenz). Diese Karte sagt darum «ausgeführt»
 * und nicht «gebucht» – und lädt den Auftrag nach, damit die Zeile erscheint, sobald sie
 * da ist.
 */
export function PayOnline({ orderObjectId, stepId, prepare, label, onDone, onClose }: {
  orderObjectId: number;
  stepId: number;
  /**
   * **Welches Modul bezahlt wird, sagt der Aufrufer** (#959): die Karte kennt keinen
   * Endpunkt. Übergeben wird eine **prototypgebundene** Methode des Clients
   * (`api.prepareVoucherPayment`) – eine stabile Referenz; eine hier gebaute
   * Pfeilfunktion wäre bei jedem Rendern neu und liesse die Vorbereitung endlos laufen.
   * Eine Rechnungsnummer braucht es nicht: je Modul gibt es eine, und sie ist der Beleg.
   */
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
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // **Die Vorbereitung ist ein Aufruf, kein Zustand.** Sie erzeugt beim Dienst eine
  // Absicht über den offenen Betrag und ändert an unserem Vorgang keine Zeile.
  useEffect(() => {
    let dead = false;
    prepare(orderObjectId, stepId)
      .then((s) => { if (!dead) setSetup(s); })
      .catch((e) => { if (!dead) setError(e instanceof Error ? e.message : String(e)); });
    return () => { dead = true; };
  }, [prepare, orderObjectId, stepId]);

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
        {/* Die Rechnungsnummer steht nicht noch einmal hier (#891): die Karte klappt unter
            der Zeile dieser Rechnung auf. Mitgeliefert wird sie trotzdem (`setup.invoice`,
            Beschreibung und Metadaten beim Zahlungsdienst). */}
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
  // Ohne Rückfall-Farbe: die Tokens sind immer definiert (`colors_and_type.css`), und eine
  // Hex-Zahl hier wäre genau die zweite Farbsprache von oben.
  const v = (name: string) => css.getPropertyValue(name).trim();
  return {
    theme: 'stripe' as const,
    // Die Beschriftung steht über dem Feld (#892) – dieselbe Anatomie wie `fields.Label`.
    labels: 'above' as const,
    // Dichte Felder (#901).
    inputs: 'condensed' as const,
    variables: {
      colorPrimary: v('--accent'),
      colorBackground: v('--bg-1'),
      colorText: v('--fg-1'),
      colorDanger: v('--danger'),
      fontFamily: v('--font-body'),
      // `inputCls` ist `rounded-ds-md` – 8 px. Ein Feld des Dienstes neben einem Feld des
      // Hauses zeigt jede Abweichung sofort, weil sie **nebeneinander** stehen.
      borderRadius: '8px',
      // Schrift und Raster wie `inputCls` (#901): `text-sm` = 14 px; das Haus rechnet in
      // 8 px, die Hälfte davon ist 4.
      fontSizeBase: '14px',
      spacingUnit: '4px',
    },
    rules: {
      // Dieselbe Polsterung und dieselbe Zeilenhöhe wie `inputCls` (`py-2 px-3`,
      // `text-sm` = 14/20 px → 20 ÷ 14 = 1.43).
      '.Input': { padding: '8px 12px', lineHeight: '1.43' },
      // Buchstabengleich `fields.Label` – 11 px, 600, Versalien, .05em, `--fg-4`.
      '.Label': {
        fontSize: '11px', fontWeight: '600', textTransform: 'uppercase',
        letterSpacing: '.05em', color: v('--fg-4'), marginBottom: '4px',
      },
    },
  };
}
