# Passkeys (WebAuthn) & Cookie-Einwilligung

Diese Notiz beschreibt zwei zusammen ausgelieferte Bausteine:

1. **Passkeys** – passwortlose Anmeldung (FIDO2/WebAuthn) auf Basis von Firebase.
2. **Cookie-/Einwilligungs-Layer** – schlanke, professionelle Consent-Lösung.

---

## 1. Passkeys – wie es funktioniert

Firebase Authentication kennt **keinen** nativen Passkey-Provider. Wir führen die
WebAuthn-Zeremonie darum selbst im Backend (`py_webauthn`) und stellen bei Erfolg einen
Firebase **Custom Token** aus. Das Frontend meldet sich damit via `signInWithCustomToken`
an – ab da ist es eine ganz normale Firebase-Session (ID-Token → `get_current_user`). Der
restliche Auth-Fluss (Magic Link, Google SSO, Backend-Verifikation) bleibt unverändert.

```
Registrieren (angemeldet)                Anmelden (passwortlos)
───────────────────────────             ───────────────────────────
POST …/passkeys/register/options        POST …/passkeys/login/options
  → Challenge                             → Challenge (usernamelos)
navigator.credentials.create()          navigator.credentials.get()
POST …/passkeys/register/verify         POST …/passkeys/login/verify
  → Attestation prüfen, speichern         → Assertion prüfen
                                          → Firebase Custom Token
                                        signInWithCustomToken()  ✅
```

**Daten:** `webauthn_credentials` (registrierte Passkeys je Nutzer) und
`webauthn_challenges` (kurzlebige, einmalig gültige Challenges, DB-basiert für Cloud
Run). Migration `065_webauthn_passkeys.py`.

**RP-ID / Origin:** werden **pro Request aus dem `Origin`-Header abgeleitet** und gegen
`CORS_ORIGINS` (+ `WEBAUTHN_EXTRA_ORIGINS`) geprüft. Dasselbe Deployment funktioniert damit
auf `localhost`, `inexxio-dev.web.app` und `inexxio.com`, ohne die Domain fest zu
verdrahten. `WEBAUTHN_RP_ID` kann die abgeleitete RP-ID bei Bedarf überschreiben.

> Ein Passkey ist an **eine** Domain (RP-ID) gebunden. Ein auf `inexxio-dev.web.app`
> registrierter Passkey funktioniert nicht auf `inexxio.com` – das ist so gewollt (Schutz
> vor Phishing), Nutzer registrieren pro Domain einen Passkey.

### Deployment (WICHTIG): Custom-Token-Signierung auf Cloud Run

`firebase_admin.auth.create_custom_token()` muss den Token **signieren**. Läuft das
Backend ohne Service-Account-Key (nur ADC, wie auf Cloud Run), nutzt das Admin SDK die
IAM-Credentials-API (`signBlob`). Dafür braucht der **Laufzeit-Service-Account** die Rolle
`roles/iam.serviceAccountTokenCreator` **auf sich selbst**:

```bash
SA="$(gcloud run services describe inexxio-backend-dev --region=europe-west6 \
  --format='value(spec.template.spec.serviceAccountName)')"
gcloud iam service-accounts add-iam-policy-binding "$SA" \
  --member="serviceAccount:$SA" \
  --role="roles/iam.serviceAccountTokenCreator"
```

Fehlt die Rolle, liefert `…/passkeys/login/verify` einen klaren 500er
(„…Service Account Token Creator…"). Alternativ einen Service-Account-Key via
`FIREBASE_SERVICE_ACCOUNT_PATH` bereitstellen (signiert lokal, keine IAM-Rolle nötig).

### Frontend

* `lib/passkey.ts` – `registerPasskey`, `loginWithPasskey`, Support-Checks.
* `lib/firebase.ts: signInWithPasskey` – Custom Token → Firebase-Session.
* Login-Seite: Button **„Mit Passkey anmelden"** (nur wenn der Browser WebAuthn kann).
* Konto → Sicherheit: Karte **„Passkeys"** (hinzufügen, benennen, entfernen).

---

## 2. Cookie-/Einwilligungs-Layer

**Braucht Inexxio ein Cookie-Banner?** Rechtlich ist die Seite bewusst „cookie-arm":
Anmeldung/Warenkorb sind technisch notwendig (keine Einwilligung nötig), Plausible ist
cookielos und Stripe wird nur an der Kasse geladen. Ein Banner ist damit nicht zwingend –
für einen Shop mit EU-Kundschaft ist eine **transparente, granulare Einwilligung** aber
State of the Art und macht die (optionale) Statistik sauber zustimmungspflichtig.

**Umsetzung (bewusst schlank, keine Fremd-CMP):**

* `lib/consent.ts` – eine Wahrheit über den Einwilligungs-Status; Erstanbieter-Cookie
  `inexxio_consent` (+ localStorage-Spiegel), versioniert, 6 Monate. Meldet Änderungen
  per Event (`inexxio:consent-changed`).
* `components/consent/cookie-consent.tsx` – nicht blockierendes Banner + Einstellungs-
  Dialog. Genau **zwei** ehrliche Kategorien: **Notwendig** (immer aktiv) und **Statistik**
  (optional). „Nur notwendige" ist so leicht wie „Alle akzeptieren" (keine Dark Patterns).
* `components/analytics/plausible.tsx` – lädt Plausible **erst** mit Statistik-Einwilligung
  (Domain aus `company_settings.plausible_domain`). CSP in `firebase.json` erweitert.
* Footer-Link + Button in der Datenschutzerklärung („Cookie-Einstellungen") → jederzeit
  widerrufbar/änderbar.

Neue optionale Dienste (Marketing-Pixel etc.) einfach hinter `hasConsent('analytics')`
bzw. eine neue Kategorie in `lib/consent.ts` hängen und `CONSENT_VERSION` erhöhen (löst
eine erneute Abfrage aus).
