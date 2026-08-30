# Zahlungsdienst (Stripe) — Setup

Der Zahlungsdienst ist **optional**. Ohne Schlüssel läuft alles unverändert: bezahlt wird
per **Überweisung**, und die trägt ein Mensch ein. Das ist kein Fallback, sondern der
B2B-Normalfall — der Knopf «Zahllink erzeugen» erscheint dann gar nicht erst.

> **Das ERP nennt Betrag und Währung. Stripe kassiert.**
>
> Im Vorgängersystem stand es umgekehrt (dort hiess es wörtlich «Stripe ist Quelle der
> Wahrheit»), und daraus kam fast die ganze Komplexität: `stripe_*`-Snapshot-Spalten an
> vier Tabellen, ein Webhook, der **Aufträge erzeugte**, ein `CheckoutIntent` mit
> Reservierungen und ein Aufräumer für verlassene Warenkörbe. Heute schreibt der Webhook
> **eine Zeile Geld** (`services/payments.record`) und sonst nichts.

## 1. Sandbox-Schlüssel

Im Stripe-Dashboard oben das **Sandbox/Test**-Konto wählen. Unter
**Developers → API keys** den **Secret key** (`sk_test_…`) kopieren.

Ein *Publishable Key* wird **nicht** gebraucht: die Kasse läuft als gehostete
Checkout-Session (Weiterleitung), nicht eingebettet — es gibt also keinen öffentlichen
Schlüssel im Browser und keine Admin-Einstellung dafür.

## 2. Dashboard: Adaptive Pricing AUS

**Settings → Payments → Checkout and Payment Links → Adaptive Pricing → Disabled**
(das ist der Standard — **nicht** aktivieren).

Wir geben Betrag **und** Währung je Position vor (`stripe_pay.checkout_url`, `adaptive_
pricing: {enabled: false}`). Wäre Adaptive Pricing an, rechnete Stripe unsere Zahl mit
**seinem** Kurs erneut um: angezeigt € 11.80, belastet € 11.82. Genau diese Divergenz
vermeidet die eine Kursquelle.

**Stripe Tax bleibt aus.** Es berechnete eine Steuer, die wir nicht kennen — die
Umkehrung des Grundsatzes oben. Die Steuer gehört an den Beleg, wenn die Rechnung kommt.

## 3. Webhook-Endpoint

1. **Developers → Webhooks → Add endpoint**
2. **Endpoint URL**: `https://<backend-host>/api/v1/payments/webhook`
3. **Events** — genau diese zwei, mehr liest der Code nicht:
   - `checkout.session.completed`
   - `charge.refunded`
4. Speichern → **Signing secret** (`whsec_…`) kopieren.

Jedes andere Ereignis wird mit `200 {"status":"ignored"}` quittiert. Ein Fehlercode darauf
brächte Stripe nur dazu, es endlos erneut zuzustellen.

## 4. Secrets im Google Secret Manager (`inexxio-dev`)

```bash
printf '%s' 'sk_test_DEIN_KEY' | gcloud secrets create STRIPE_SECRET_KEY \
  --project=inexxio-dev --replication-policy=automatic --data-file=-

printf '%s' 'whsec_DEIN_SECRET' | gcloud secrets create STRIPE_WEBHOOK_SECRET \
  --project=inexxio-dev --replication-policy=automatic --data-file=-
```

Existieren sie schon, eine neue Version anhängen:

```bash
printf '%s' 'sk_test_…' | gcloud secrets versions add STRIPE_SECRET_KEY --project=inexxio-dev --data-file=-
printf '%s' 'whsec_…'   | gcloud secrets versions add STRIPE_WEBHOOK_SECRET --project=inexxio-dev --data-file=-
```

**Zugriff** (einmalig) für den Cloud-Run-Service-Account:

```bash
for S in STRIPE_SECRET_KEY STRIPE_WEBHOOK_SECRET; do
  gcloud secrets add-iam-policy-binding "$S" --project=inexxio-dev \
    --member="serviceAccount:cloudrun-backend@inexxio-dev.iam.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor"
done
```

> **Reihenfolge:** erst die Secrets anlegen, dann das Deploy — `--set-secrets`
> referenziert sonst etwas, das es nicht gibt, und der Start schlägt fehl.

## 5. Deploy verdrahten

In `.github/workflows/deploy-dev.yml` beim Cloud-Run-Deploy ergänzen:

```
--set-secrets STRIPE_SECRET_KEY=STRIPE_SECRET_KEY:latest,STRIPE_WEBHOOK_SECRET=STRIPE_WEBHOOK_SECRET:latest
```

**Ohne diese Zeile ist der Dienst schlicht nicht eingerichtet** — kein Fehler, kein Stub,
kein 503: `stripe_pay.available()` ist `False`, und der Zahllink-Knopf erscheint nicht
(`PurchaseEmbed.can` führt `link` dann gar nicht).

## 6. Testen (Sandbox)

1. Artikel mit einem **Verkauf**-Modul anlegen, Auftrag freigeben.
2. Am Beleg: Kunde wählen → «Angebot senden» → Zusage mit Betrag erfassen.
3. Unter den Stufen erscheint die Zahlungszeile: **offen · fällig**.
4. «Zahllink erzeugen» → die Adresse öffnen → Testkarte `4242 4242 4242 4242`,
   beliebiges künftiges Datum, beliebige CVC/PLZ.
5. Nach der Zahlung meldet der **Webhook** – nicht der Browser: die Zeile springt auf
   **Bezahlt**, mit der `pi_…`-Referenz in der Buchungsliste.
6. Erstattung **im Stripe-Dashboard** auslösen → `charge.refunded` bucht eine **negative**
   Zahlung (eigene Referenz `pi_…:refund`). Einen eigenen Erstattungs-Knopf gibt es
   bewusst nicht: der Dienst bietet ihn an, und «erstattet wird auf dem Weg, auf dem
   gezahlt wurde» ist dort ohnehin die einzige Möglichkeit.

## Was es bewusst NICHT gibt

| | warum |
|---|---|
| Ein `manual`-Provider | Er simulierte einen Zahlungsdienstleister samt eigener Bezahlseite. Eine Überweisung braucht keine Simulation — sie braucht ein Feld. |
| Ein Provider-Rahmen mit zwei Implementierungen | Eine Abstraktion über einer Zeile. Der Weg ist ein **Feld** an der Zahlung. |
| Stripe Tax | Es berechnete eine Zahl, die wir nicht kennen. |
| Customer Portal / Subscriptions | Wiederkehrende Aufträge werden eine **Schlaufe im Prozess** (PROCESS_CORE §13.7), kein Abo-Objekt beim Zahlungsdienst. |
| `stripe_customer_id` & Co. | Die Id steht in `payments.reference` — in derselben Spalte, in der bei einer Überweisung der Zahlungszweck steht. Ein Feld, zwei Wege. |
| Ein eigener Erstattungs-Knopf | Der Dienst bietet ihn an. Ein zweiter Auslöser wäre ein zweiter Weg zu derselben Buchung — der Webhook fängt sie ohnehin. |
| Eingebettete Kasse | Sie brauchte einen Publishable Key, eine Admin-Einstellung und ein React-Paket. Die gehostete Session ist eine URL. |

## Go-Live

Für die Produktion dieselben Schritte im Live-Modus und mit `inexxio-prod`; die
Endpoint-URL zeigt dann auf das Prod-Backend. **Zuerst in der Sandbox durchspielen** —
ein falsch gesetzter Webhook fällt sonst erst auf, wenn Geld fliesst.
