# Inexxio – Lastenheft v1.0 (Final, verbindlich)

> **WICHTIG für Claude Code:** Dieses Dokument enthält alle verbindlichen Projektentscheide für Inexxio.
> Vor jeder Entwicklungsarbeit relevante Abschnitte konsultieren.

## Stammdaten

| Feld | Wert |
|------|------|
| Projektname | Inexxio Enterprise Central System |
| Rechtsform | Aktiengesellschaft (AG), Schweiz |
| Branche | Produzierendes Gewerbe / Maschinenbau |
| Mitarbeiter | ca. 10 |
| Artikel | ca. 1'000 |
| Domain Start | inexxio.web.app (Firebase Hosting, Phase 1) |
| Domain Prod | inexxio.com (Phase 2+) |
| E-Mail Phase 1 | info.inexxio@gmail.com |
| E-Mail Phase 2 | @inexxio.com (Google Workspace) |
| GitHub | vorhanden, Claude Code verbunden |

## Konsolidierte Entscheide (alle verbindlich)

| Thema | Entscheid |
|-------|-----------|
| MWST | Effektive Methode, Quartal. Pflichtig. Inland + Export korrekt behandelt. |
| MWST-Sätze CH | 8.1% Standard · 2.6% Reduziert · 3.8% Beherbergung · 0% Export |
| MWST EU B2B | 0% + Reverse Charge (VAT-ID auf Rechnung) |
| MWST-Nr | Platzhalter CHE-123.456.789 – Eingabemaske im Admin |
| UID | Platzhalter CHE-123.456.789 – Eingabemaske im Admin |
| Handelsregister-Nr. | Eingabemaske im Admin – nicht hardcodiert |
| IBAN / QR-IBAN | Eingabemaske im Admin. Stripe-Konto noch zu erstellen. |
| Firmendetails | Vollständige Eingabemaske im Admin ('Firmeneinstellungen') |
| OSS (EU B2C) | Architektur vorbereiten, noch nicht registriert – Flag 'OSS aktiv' im Admin |
| VIES EU-VAT | Validierung vorbereiten, noch nicht aktiv – Toggle im Admin |
| Stripe | Noch zu erstellen |
| Design System | Tailwind CSS, minimalistisch. Farben + Komponenten-Spezifikation in CLAUDE.md |
| Artikel-Typen | Eliminiert – nur optionale Admin-Kategorien + Equipment-Toggle |
| Serialisierung | qty=1 → Einzelteil. qty>1 → automatisch Batch. Kein 'Kein'-Modus. |
| ERP UI | Master-Detail / Repeater. Universaler Feed. Alles in einem Bildschirm. |
| QC-Checklisten | Integriert im Arbeitsplan als Schritt-Typ 'QC Check' |
| Gast-Checkout | Ja – Progressive Registration (Shadow Account im Hintergrund) |
| Onshape API | Phase 5 |
| TWINT | Phase 2 |
| ISO 14001 | Phase 5+ |
| Bexio Integration | Phase 5 (Architektur vorbereitet) |
| Pentest | Phase 5 |
| Label-Drucker | Nicht berücksichtigt |
| Buchhaltung | Auf eigener Platform. Swiss AG. Effektive MWST-Methode. |
| Soft-Delete | Überall – nur is_active=false, niemals hard delete |
| Timestamps | IMMER UTC server-seitig. Frontend konvertiert mit Intl.DateTimeFormat |
| Autosave | Debounced 3s. Rahmen leuchtet grün. 'Gespeichert um HH:MM' Anzeige. |
| Zahlungsfristen | Konfigurierbar per Firma (Net 10/30/60). Standard im Admin. |
| Skonto | Optionales Feld auf Rechnung. Kein Auto-Abzug. |
| Analytics | Plausible Analytics – DSGVO-konform, kein Cookie-Banner nötig |
| SPAM-Schutz | hCaptcha auf Kontaktform + Checkout |
| 2FA Admin | TOTP (Authenticator App) via Firebase MFA – verpflichtend |
| PWA | Ja – installierbar, Service Worker, Offline-Fallback |
| Echtzeit | Server-Sent Events (SSE) für Status-Updates im ERP |
| Scrapping-Nachweis | Foto + Canvas-Signatur für fehlerhafte/verschrottete Teile. ISO 9001. |
| Print | Print-CSS für Arbeitspläne (Shop-Floor). Kein PDF-Standard-Versand. |

## Navigation & UX (verbindlich)

- **Nach Login:** Nutzer bleibt auf der Seite, auf der er war. Fallback: Startseite `/`.
- **ERP-Zugang:** Via "ERP"-Link im Website-Header (sichtbar wenn eingeloggt).
- **ERP als Unterseite:** ERP-Seiten behalten Website-Navbar und -Footer. ERP-Sidebar ist inneres Element.
- **Nutzerverwaltung / Berechtigungen:** Ausstehend (Phase 1 abschluss).

## Technologie-Stack (verbindlich)

| Schicht | Technologie |
|---------|-------------|
| Frontend | Next.js 14, TypeScript, App Router, Tailwind CSS, PWA, Static Export |
| Backend | FastAPI (Python 3.12), SQLAlchemy 2.0, Pydantic v2, Alembic |
| DB | PostgreSQL 15 (Cloud SQL), universeller 9-stelliger Nummernkreis |
| Auth | Firebase Authentication (Magic Link + Google SSO + TOTP MFA für Admin) |
| Storage | Google Cloud Storage |
| Search | Typesense (Phase 2) |
| Email | Gmail API (info.inexxio@gmail.com Phase 1 → @inexxio.com Phase 2) |
| Payments | Stripe (Phase 2) |
| KI | Claude API (Anthropic) |
| Infra | Google Cloud Run + Firebase Hosting |
| Analytics | Plausible Analytics (DSGVO-konform) |

## Repository-Struktur (Monorepo)

```
inexxio/
├── CLAUDE.md              ← Haupt-Kontext (IMMER zuerst lesen)
├── docs/
│   ├── Lastenheft_v1.0.md ← Dieses Dokument (verbindliche Entscheide)
│   └── adr/               ← Architecture Decision Records
├── frontend/              ← Next.js 14 App
│   ├── src/app/
│   │   ├── (public)/      ← Öffentliche Website-Seiten (mit Navbar + Footer)
│   │   ├── (auth)/        ← Login / Magic-Link-Verify (minimales Layout)
│   │   └── (erp)/         ← ERP-Seiten (MIT Website-Navbar + Footer + ERP-Sidebar)
│   └── ...
├── backend/               ← FastAPI Python
└── shared/                ← Geteilte TypeScript-Typen
```

## Git-Workflow

| Branch | Ziel | Deployment |
|--------|------|-----------|
| main | Production (inexxio.com) | Manuell via PR |
| develop | Dev (inexxio-dev.web.app) | Auto via Cloud Build |
| feature/xxx oder claude/xxx | Lokale Entwicklung | PR auf develop |

**Commit-Konvention:** `feat:` / `fix:` / `refactor:` / `docs:` / `test:`
**Regel:** Nach jedem funktionierenden Feature committen. Nie 'work in progress' committen.
**Regel:** CLAUDE.md nach jeder Session aktualisieren (Status + nächste Aufgabe).

## Nummernkreis

Universell 9-stellig: 100'000'001 – 999'999'999. Gilt für ALLE Objekte.
Tabelle: `objects(id, object_type, created_at, updated_at, created_by, updated_by, is_active)`

## Phasenplan

| Phase | Zeitraum | Inhalt |
|-------|----------|--------|
| 1 – Fundament | Mt. 1–5 | Google Cloud, Firebase Auth, Website DE+EN, ERP Kern |
| 2 – Kernprozesse | Mt. 6–10 | PO + Lieferantenportal, Produktion, SO + Kundenportal, Stripe |
| 3 – Erweiterungen | Mt. 11–16 | NCR/8D, CAPA, Audit, Risiko, ISO 9001, HR, Buchhaltung |
| 4 – KI & Auto | Mt. 17–22 | Bestellvorschlag KI, Semantische Suche, OCR |
| 5 – Advanced | Mt. 23+ | Bexio-Integration, Onshape API, ISO 14001 |

## Budget

- Claude Pro ($20/Monat): Tägliche Entwicklung, Reviews, Planung
- API Credits (Pay-as-you-go): Komplexe Automatisierungen, Batch-Verarbeitung
