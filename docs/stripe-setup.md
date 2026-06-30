# Stripe-Integration – Setup (Sandbox/Dev)

Diese Anleitung aktiviert die Stripe-Vollintegration (hosted Checkout + **Adaptive Pricing**
+ **Stripe Tax**) auf der Dev-Umgebung. Der Code aktiviert Stripe **automatisch**, sobald
`STRIPE_SECRET_KEY` im Backend gesetzt ist; ohne Key läuft der überbrückbare `manual`-Provider.

> Reihenfolge wichtig: **Erst** die Secrets im Google Secret Manager anlegen (Schritt 3),
> **dann** den PR nach `develop` mergen – sonst schlägt das Cloud-Run-Deploy fehl
> (`--set-secrets` referenziert nicht existierende Secrets).

> **Eingebettete Kasse (Embedded Checkout):** Die Zahlung läuft seit Phase 8 **on-site**
> (kein Redirect) – Stripe Checkout wird direkt auf `/shop/checkout` eingebettet. Dafür wird
> zusätzlich der **Publishable Key** (`pk_test_…`) benötigt. Er ist **öffentlich** (kein
> Secret) und wird **nicht** im Secret Manager, sondern in **Admin → Systemkonfiguration →
> Integrationen → «Stripe Publishable Key»** hinterlegt. Das Backend reicht ihn über
> `GET /api/v1/shop/config` an das Frontend; ohne ihn zeigt die Kasse einen Hinweis.

## 1. Stripe Sandbox aktivieren
Im Stripe-Dashboard oben das **Sandbox/Test**-Konto wählen (Account «Inexxio AG»). Alle
folgenden Schritte im **Sandbox-Modus** ausführen. Du brauchst zwei Keys unter
**Developers → API keys**:
- **Secret key** (`sk_test_…`) → Google Secret Manager (Schritt 4).
- **Publishable key** (`pk_test_…`) → Admin → Systemkonfiguration → Integrationen
  (öffentlich, für die eingebettete Kasse).

> **Stripe Tax ist aktuell DEAKTIVIERT** (`STRIPE_TAX_ENABLED=false`, Default). Der Checkout
> läuft ohne automatische Steuer (Bruttopreis wird so verrechnet). Zum Aktivieren später:
> Schritt 2 ausführen **und** im Deploy `STRIPE_TAX_ENABLED=true` setzen (env-var in
> `deploy-dev.yml`). Vorher NICHT aktivieren – sonst schlägt die Checkout-Erstellung fehl.

## 2. Adaptive Pricing + Stripe Tax (Dashboard)
1. **Adaptive Pricing** aktivieren: **Settings → Payments → Checkout and Payment Links →
   Adaptive Pricing → Enable** (Sandbox). Dadurch sieht der Kunde an der Kasse automatisch
   seine Lokalwährung – wir setzen KEINE Währung und brauchen keinen Umschalter.
2. **Stripe Tax** einrichten: **Settings → Tax**:
   - **Head office / Origin address**: Schweizer Firmenadresse.
   - **Default tax behavior**: **Inclusive** (unsere Basispreise sind brutto, inkl. MWST).
   - **Preset product tax code**: ein Sachgüter-Code (Default im Code: `txcd_99999999`
     «General – Tangible Goods»; bei rein digitalen Leistungen anpassen).
   - **Registrations**: mindestens **Schweiz (CH)** hinzufügen (und jedes weitere Land, in
     dem ihr steuerpflichtig verkauft). Ohne Registrierung berechnet Stripe für dieses Land
     **0 %** (kein Fehler) – Steuer wird nur dort erhoben, wo registriert.
3. **Zahlungsmethoden**: **Settings → Payment methods** die gewünschten aktivieren (Karten
   sind für Adaptive Pricing/Abos immer ok).

## 3. Webhook-Endpoint + Secret
1. **Developers → Webhooks → Add endpoint**.
2. **Endpoint URL**: `https://inexxio-dev.web.app/api/v1/shop/payments/webhook`
3. **Events** (mind.): `checkout.session.completed`, `checkout.session.async_payment_succeeded`,
   `checkout.session.expired`, `checkout.session.async_payment_failed`,
   `customer.subscription.deleted`, `invoice.paid`.
4. Endpoint speichern → **Signing secret** (`whsec_…`) kopieren.

## 4. Secrets im Google Secret Manager (Projekt `inexxio-dev`)
Lege **zwei** Secrets an (exakt diese Namen – das Deploy referenziert sie):

```bash
# Secret Key aus Schritt 1
printf '%s' 'sk_test_DEIN_KEY' | gcloud secrets create STRIPE_SECRET_KEY \
  --project=inexxio-dev --replication-policy=automatic --data-file=-

# Webhook Signing Secret aus Schritt 3
printf '%s' 'whsec_DEIN_SECRET' | gcloud secrets create STRIPE_WEBHOOK_SECRET \
  --project=inexxio-dev --replication-policy=automatic --data-file=-
```

Falls die Secrets schon existieren, neue Version anhängen:
```bash
printf '%s' 'sk_test_…' | gcloud secrets versions add STRIPE_SECRET_KEY --project=inexxio-dev --data-file=-
printf '%s' 'whsec_…'   | gcloud secrets versions add STRIPE_WEBHOOK_SECRET --project=inexxio-dev --data-file=-
```

**Zugriff**: die Cloud-Run-Service-Account `cloudrun-backend@inexxio-dev.iam.gserviceaccount.com`
braucht die Rolle **Secret Manager Secret Accessor** auf beiden Secrets (einmalig):
```bash
for S in STRIPE_SECRET_KEY STRIPE_WEBHOOK_SECRET; do
  gcloud secrets add-iam-policy-binding "$S" --project=inexxio-dev \
    --member="serviceAccount:cloudrun-backend@inexxio-dev.iam.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor"
done
```

## 5. Deploy
Der PR verdrahtet Cloud Run bereits:
- `--set-secrets … STRIPE_SECRET_KEY=…:latest, STRIPE_WEBHOOK_SECRET=…:latest`
- `--set-env-vars … FRONTEND_BASE_URL=https://inexxio-dev.web.app, PRICES_TAX_INCLUSIVE=true`

Nach Schritt 4 den PR nach `develop` mergen → Deploy injiziert die Secrets, der Provider
schaltet automatisch auf `stripe`.

## 6. Testen (Sandbox)
1. **Publishable Key** in Admin → Systemkonfiguration → Integrationen hinterlegen (`pk_test_…`).
2. Artikel im ERP **Verkauf**-Reiter publizieren (Preis in CHF brutto, make oder stock; mehrere
   Preis-Optionen möglich – Einmalkauf / Nutzungsabo / Produktabo).
3. Als Kunde einloggen → `/shop` → Produkt → Option wählen → **In den Warenkorb** →
   `/shop/cart` → **Zur Kasse** → die **eingebettete** Stripe-Kasse erscheint auf `/shop/checkout`.
4. **Adaptive Pricing testen**: an der Kasse die Lokalwährung prüfen. (Optional simulieren:
   eine Kunden-E-Mail mit Suffix `+location_DE@…` zeigt EUR-Preise.) Die **Lieferadresse** ist
   aus dem Profil vorausgefüllt (sofern hinterlegt).
5. **Testkarte**: `4242 4242 4242 4242`, beliebiges künftiges Datum, beliebige CVC/PLZ.
6. Nach Zahlung: Rückkehr auf `/shop/success` → der Webhook **erzeugt** je Warenkorb-Position
   den Auftrag (make) bzw. finalisiert den reservierten (stock), setzt den Verkauf auf **paid**
   und friert den **real bezahlten Betrag/Währung/Steuer** je Position als Snapshot ein.
7. **Abo**: Preis-Option «Nutzungsabo» oder «Produktabo» → Checkout `mode=subscription` (wird
   **einzeln** gekauft). «Zahlungen & Abos verwalten» öffnet das **Stripe Customer Portal**
   (kündbar, kein Enddatum).

## Architektur (Kurz)
- **Provider-Auswahl** (`services/payments/__init__.py`): `company_settings.payments_provider`
  → sonst automatisch `stripe`, wenn `STRIPE_SECRET_KEY` gesetzt → sonst `manual`.
- **Checkout** (`services/payments/stripe_provider.py`): Checkout Session ohne Währung
  (Adaptive Pricing), `automatic_tax=enabled` (Stripe Tax), `tax_behavior=inclusive`,
  `mode=payment|subscription`, Customer-Mapping, Shipping-Adresse für physische Güter.
- **Defer-Modell**: der Auftrag wird **erst bei bestätigter Zahlung** freigegeben (Webhook
  `checkout.session.completed`). Ausnahme: `stock` reserviert schon bei der Bestellung.
- **Snapshot**: Stripe ist Quelle der Wahrheit – `sales.stripe_snapshot` hält Settlement
  (CHF) + Adaptive-Pricing-Lokalwährung + Steuer; `sales.stripe_payment_intent_id`,
  `orders.stripe_subscription_id`.

## Bewusst (noch) NICHT gebaut
- Folge-Fulfillment-Auftrag je Abo-Zyklus (Stripe verrechnet wiederkehrend; wir spiegeln den
  Status – Auto-Fulfillment je Zyklus ist die nächste Erweiterung).
- Live-Keys/Go-Live (zuerst Sandbox-Tests; danach `STRIPE_SECRET_KEY`/`STRIPE_WEBHOOK_SECRET`
  in `deploy-prod`/Secret Manager `inexxio-prod` analog setzen).
